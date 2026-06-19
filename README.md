# CCAS Python Toolkit

A Python equivalent of `bash_api.sh` for the Check Point Certified Automation
Specialist (CCAS) lab, designed to run from the **A-GUI** Windows VM rather
than from the A-SMS expert shell.

## What this is

`bash_api.sh` (and its `bash_api_v4.sh` evolution in this repo) is a thin bash
wrapper around `mgmt_cli` that lets students batch up Check Point Management
API calls from the SMS expert shell, auto-publishing every 80 successful
changes. It's the standard pattern taught from CCAS Lab 3A onwards.

This toolkit is the Python counterpart: a thin Python wrapper around
`mgmt_cli.exe` (which ships with SmartConsole on A-GUI) that uses the same
session-file pattern, the same publish-every-80 batching, and the same
`Success 1.1 / 1.2 / ...` output format as the bash version. The commands
themselves are unchanged — `add-host`, `add-group`, `set-network`, etc. are
exactly the same names students learn in the labs.

Useful when:

  - You want the automation workflow to live on A-GUI instead of A-SMS
  - You want Python's orchestration features (loops, conditionals, error
    handling, integration with other libraries) without leaving the
    courseware's command vocabulary
  - You want a tool that aligns with what most Check Point customers
    actually run in production — `mgmt_cli` plus a scripting layer — rather
    than introducing an SDK-based parallel universe

## Prerequisites

  - A Check Point R81.x or R82 Security Management Server reachable over
    the Management API (TCP/443 by default, TCP/4434 if AppCtrl/URLF are
    enabled on the SMS)
  - An API user on the SMS, or an API key issued by an admin
  - The Management API enabled for "All IP addresses" or at least the
    A-GUI IP — Lab 2A-2 (`api restart`) in the CCAS curriculum
  - **SmartConsole installed on A-GUI** — provides `mgmt_cli.exe`. This is
    done in Lab 2A of the CCAS course; if you're using this toolkit on a
    fresh A-GUI image you'll need SmartConsole in place first.
  - Windows lab VM with internet access for the initial install (only)

The installer handles Python and the toolkit files. Python's only external
dependency is `python-dotenv`, used optionally for loading `.env` files.

## Quick install (irm | iex)

On A-GUI, in an elevated PowerShell:

```powershell
irm https://raw.githubusercontent.com/Don-Paterson/CCAS-Python-Toolkit/main/Install-PythonOnAGUI.ps1 | iex
```

The installer:

  1. Installs Python 3.13 (amd64) silently from python.org if it isn't already
     present at version 3.11 or higher
  2. Updates pip and installs `python-dotenv`
  3. Locates `mgmt_cli.exe` (checks PATH, then walks the SmartConsole
     install tree) and reports the path
  4. Downloads `mgmt_api.py`, `lab_example.py`, `lab_batch_example.py`,
     `requirements.txt`, and `env.example.txt` into `C:\CCAS-Python\`
  5. Adds the `mgmt_cli.exe` directory to the machine `PATH` (when run
     elevated) so the toolkit resolves it automatically

## Manual install

```powershell
py -3 -m pip install python-dotenv
git clone https://github.com/Don-Paterson/CCAS-Python-Toolkit C:\CCAS-Python
cd C:\CCAS-Python\python
```

`mgmt_cli.exe` must be either on `PATH` or pointed to by the `CP_MGMT_CLI`
environment variable; otherwise the toolkit auto-detects it under
`C:\Program Files (x86)\CheckPoint\SmartConsole\*\PROGRAM\`.

## Configuration

The toolkit reads settings from either environment variables or a `.env`
file in the current directory:

| Variable           | Purpose                                                          |
|--------------------|------------------------------------------------------------------|
| `CP_MGMT_HOST`     | Management server IP / hostname (default `10.1.1.101`)           |
| `CP_MGMT_USER`     | API username                                                     |
| `CP_MGMT_PASS`     | API password                                                     |
| `CP_MGMT_API_KEY`  | API key (alternative to username / password)                     |
| `CP_MGMT_DOMAIN`   | MDS / Multi-Domain domain name (omit on a standalone SMS)        |
| `CP_MGMT_CLI`      | Full path to `mgmt_cli.exe` (overrides auto-detection)           |

Set up the `.env`:

```powershell
cd C:\CCAS-Python
copy env.example.txt .env
notepad .env
```

If neither env vars nor `.env` are set, the script prompts interactively for
the username and password (password input is masked via `getpass`).

## Usage

### Smoke test

The simplest end-to-end check:

```powershell
py -3 mgmt_api.py
```

This logs in, adds a host called `python_api_host` (3.3.3.3, pink), publishes,
and logs out. Open SmartConsole afterwards to verify it appears.

You can override the target SMS at the command line:

```powershell
py -3 mgmt_api.py --host 192.168.11.101
py -3 mgmt_api.py --host 10.1.1.101 --domain "Bravo_Domain"
```

### Lab example

`lab_example.py` creates three test hosts and a group containing them — same
pattern as the `mgmtCmd add host ...` sequences in the courseware:

```powershell
py -3 lab_example.py
```

Expected output:

```
Success 1.1
Success 1.2
Success 1.3
Success 1.4
```

In SmartConsole afterwards: `Test-host-1`, `Test-host-2`, `Test-host-3` and
`Test-hosts-group`, all in `crete blue`.

To re-run, delete the four objects from SmartConsole first (the example
follows the courseware "run once on a fresh management" pattern; it
deliberately does not include idempotency machinery).

### Bulk creation (loop vs native batch)

`lab_batch_example.py` demonstrates the two ways to create many objects at
once. Both create a group, then 20 hosts attached to it.

```powershell
py -3 lab_batch_example.py            # Python for-loop: one add per host
py -3 lab_batch_example.py --batch    # native mgmt_cli --batch: one CSV, one call
```

The two are **not** equivalent in cost:

  - **The loop** calls `mgmt_cmd("add host", {...})` once per object. It's the
    readable, courseware-friendly translation of a bash `while` loop, but it's
    still one `mgmt_cli.exe` process and one API call per host.
  - **`--batch`** hands a whole CSV to a single `mgmt_cli add host --batch
    <file>` invocation. One process, one API call, every row created
    server-side. This is the courseware slide pattern and the right choice
    when N is large.

Both demos attach each host to the group **at creation** via the `groups`
parameter (`add host ... groups.1 <name>`) rather than building the group with
`members` afterwards. The group is created once and each host inserts itself
into it — which sidesteps the fact that `add group` can't be re-run with
`set-if-exists`. The hosts carry `set-if-exists` so they overwrite on re-run;
the group does not, so delete the group in SmartConsole to re-run cleanly.

To call native batch mode from your own script:

```python
from mgmt_api import LabAPIClient

with LabAPIClient(host="10.1.1.101") as api:
    # hosts.csv: header row of parameter names, one row per object
    #   name,ip-address,color,groups.1
    #   web-01,10.0.0.1,cyan,Web-Servers
    #   web-02,10.0.0.2,cyan,Web-Servers
    api.mgmt_cmd_batch("add host", "hosts.csv")
```

`mgmt_cmd_batch()` shares the same session, error reporting, and
publish-every-80 behaviour as `mgmt_cmd()`; the whole batch counts as one
change against the publish counter.

### Writing your own script

Use `LabAPIClient` as a context manager. Every `mgmt_cmd()` call invokes
`mgmt_cli` once under the hood. Publishes happen automatically every 80
successful changes, and the context manager publishes and logs out on exit.

Minimal example:

```python
from mgmt_api import LabAPIClient

with LabAPIClient(host="10.1.1.101") as api:
    api.mgmt_cmd("add-host", {
        "name":       "my-host",
        "ip-address": "1.2.3.4",
        "color":      "pink",
    })
```

More substantial example — create a network, a host, a group containing them,
publish mid-session, then install the database:

```python
from mgmt_api import LabAPIClient

with LabAPIClient(host="10.1.1.101") as api:
    api.mgmt_cmd("add-network", {
        "name":         "A-LAB-NET",
        "subnet4":      "192.168.99.0",
        "mask-length4": 24,
        "color":        "crete blue",
        "comments":     "Test lab network",
    })
    api.mgmt_cmd("add-host", {
        "name":       "A-LAB-HOST",
        "ip-address": "192.168.99.10",
        "color":      "crete blue",
    })
    api.mgmt_cmd("add-group", {
        "name":    "A-LAB-OBJECTS",
        "members": ["A-LAB-NET", "A-LAB-HOST"],
        "color":   "crete blue",
    })

    # Explicit publish; otherwise it happens automatically on __exit__
    api.publish()

    api.mgmt_cmd("install-database", {"targets": "A-SMS"})
```

Custom session name and batch size:

```python
with LabAPIClient(
    host="10.1.1.101",
    session_name="Lab 3B Policy",
    session_description="Policy layer build for Lab 3B",
    publish_every=50,
) as api:
    ...
```

### Lists in payloads

Python list values are auto-expanded into mgmt_cli's indexed form:

```python
api.mgmt_cmd("add-group", {
    "members": ["A-HOST", "B-HOST", "C-HOST"],
})
```

invokes mgmt_cli as if you'd typed:

```
mgmt_cli add-group ... members.1 A-HOST members.2 B-HOST members.3 C-HOST
```

— exactly the syntax from the `bash_api.sh` examples in master.txt.

### Output format

Every successful `mgmt_cmd` prints:

```
Success <batch>.<count>
```

So `Success 1.1`, `Success 1.2`, ... `Success 1.80`, then a publish, then
`Success 2.1` and the second batch begins. This matches the bash version
exactly so log output is directly comparable.

Failures print:

```
Failed: <command> <payload>  (<error message from mgmt_cli>)
```

The script continues on failure rather than aborting — same as the bash.
To abort on the first error:

```python
if not api.mgmt_cmd("add-host", {...}):
    raise SystemExit("Stopping on first failure")
```

## Mapping bash to Python

| Bash (`bash_api_v4.sh`)        | Python (`mgmt_api.py`)                  |
|--------------------------------|-----------------------------------------|
| `mgmtCmd add host name ...`    | `api.mgmt_cmd("add-host", {...})`       |
| `mgmt_cli add host --batch f`  | `api.mgmt_cmd_batch("add host", "f")`   |
| `publish` function             | `api.publish()`                         |
| `login` / `logout` functions   | `with LabAPIClient() as api:`           |
| `publishEvery=80`              | `LabAPIClient(publish_every=80)`        |
| `apiPort=$(api status ...)`    | `mgmt_cli` handles port selection       |
| Session cookie file            | Same — a temp file, cleaned up on exit  |
| `./bash_api_v4.sh "Domain"`    | `LabAPIClient(domain="Domain")`         |

Both versions ultimately invoke `mgmt_cli` against the same Management API.
The Python layer adds dict-style payload construction, auto-expansion of
list parameters, JSON parsing of errors, and context-manager safety.

## MDS / Multi-Domain

Pass `domain="<Domain_Name>"` to `LabAPIClient`, or set `CP_MGMT_DOMAIN`. The
mgmt_cli invocation adds `-d <Domain_Name>` at login.

```python
with LabAPIClient(host="10.1.1.101", domain="Alpha_Domain") as api:
    api.mgmt_cmd("add-host", {"name": "h1", "ip-address": "1.2.3.4"})
```

## Troubleshooting

**`mgmt_cli executable not found`**
SmartConsole isn't installed, or the install is in an unusual location.
Either install SmartConsole (CCAS Lab 2A) or set `CP_MGMT_CLI` to the
full executable path in your `.env`.

**Login fails with "unauthorized" / "err_login_failed"**
Confirm credentials at the shell first:

```powershell
& "C:\Program Files (x86)\CheckPoint\SmartConsole\R82\PROGRAM\mgmt_cli.exe" --management 10.1.1.101 login user admin password "Chkp!234"
```

If that works, the toolkit will too. If not, confirm in SmartConsole that
the API user has appropriate permissions, and on a fresh lab make sure
`api restart` was run after creating the API user (Lab 2A-2).

**Calls time out**
mgmt_cli defaults to port 443. If AppCtrl/URLF blades are enabled on the
SMS, the API moves to port 4434. Add a `--port 4434` arg to the mgmt_cli
invocations in `mgmt_api.py`, or set it via the `CP_MGMT_HOST` shape.

**`Failed: <command> ...` on a known-good command**
Check the error message in parentheses — the toolkit surfaces the actual
`errors[]` / `warnings[]` detail from mgmt_cli, not just the generic
"Validation failed with 1 warning and 1 error" summary. Most common causes:
the object already exists (`More than one object named '...' exists.` — delete
it or use `set-if-exists`), a referenced object doesn't exist (typo or commands
ran out of order), or the parameter isn't valid for that command in this
R-version (e.g. `set-if-exists` is **not** accepted on `add-group` in any
current build — create the group once and attach members at host creation via
`groups` instead).

**First connection prompts for / appears to hang on the fingerprint**
On first contact with a management, mgmt_cli normally asks you to accept the
API server's fingerprint. The toolkit passes `--unsafe-auto-accept true` at
login so this is accepted automatically — appropriate for a disposable lab
management. Do not carry that flag into scripts targeting a production SMS
without verifying the fingerprint out of band first.

**Connectivity check**
From PowerShell on A-GUI:

```powershell
Test-NetConnection 10.1.1.101 -Port 443
```

## Notes

  - Designed for Skillable A-GUI (Hyper-V, Intel Xeon Gold 6330, x86-64);
    the installer downloads the amd64 Python build accordingly.
  - The bash-side companion `bash_api_v4.sh` is included in this repo for
    cross-reference and for tasks that still need to run on A-SMS itself.
  - The toolkit's only Python dependency is `python-dotenv` (optional —
    env vars work fine without it). Everything else is the standard library.
  - `mgmt_cli.exe` invocations happen with `--format json` so error
    messages come back parseable. Adjust in `_run()` if you want verbose
    success output.
  - The seed credentials file is named `env.example.txt` rather than
    `.env.example` to avoid AV/proxy filtering on the `.env` substring and
    PowerShell IWR's known issues with leading-dot files.

## License

MIT — see `LICENSE`.
