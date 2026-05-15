# CCAS Python Toolkit

A Python equivalent of `bash_api.sh` for the Check Point Certified Automation
Specialist (CCAS) lab, designed to run from the **A-GUI** Windows VM rather
than from the A-SMS expert shell.

## What this is

`bash_api.sh` (and its `bash_api_v4.sh` evolution in this repo) is a thin
wrapper that lets students batch up Check Point Management API calls from the
SMS expert shell, auto-publishing every 80 successful changes. It's the
standard pattern taught from CCAS Lab 3A onwards.

This toolkit ports that exact pattern to Python so the same lab objectives can
be carried out from the A-GUI Windows VM. Same publish-every-80 batching, same
`Success 1.1 / 1.2 / ...` output format, same notion of named sessions — but
driven via the official Check Point Management API Python SDK (`cpapi`) rather
than `mgmt_cli` shell calls.

Useful when:

  - You want the automation workflow to live on A-GUI instead of A-SMS
  - You want to script Check Point automation from a non-Gaia host
  - You want a Python base to extend (native JSON / dict handling, easy
    integration with `requests`, `pandas`, etc.)

## Prerequisites

  - A Check Point R81.x or R82 Security Management Server reachable over the
    Management API (TCP/443 by default, TCP/4434 if AppCtrl/URLF are enabled
    on the SMS)
  - An API user on the SMS, or an API key issued by an admin
  - The Management API enabled for "All IP addresses" or at least the A-GUI
    IP — this is what Lab 2A-2 (`api restart`) is for in the CCAS curriculum
  - A Windows lab VM (Skillable A-GUI or equivalent) with internet access for
    the initial install

The installer handles Python itself, the pip packages, and the toolkit files.

## Quick install (irm | iex)

On A-GUI, in an elevated PowerShell:

```powershell
irm https://raw.githubusercontent.com/Don-Paterson/CCAS-Python-Toolkit/main/Install-PythonOnAGUI.ps1 | iex
```

This:

  1. Installs Python 3.13 (amd64) silently from python.org if it isn't already
     present at version 3.11 or higher
  2. Updates pip
  3. Installs `cpapi`, `requests`, `urllib3`, `python-dotenv`, `tabulate`,
     `colorama`
  4. Downloads `mgmt_api.py`, `lab_example.py`, `requirements.txt`, and
     `.env.example` into `C:\CCAS-Python\`

## Manual install

If you'd rather do it by hand:

```powershell
py -3 -m pip install -r https://raw.githubusercontent.com/Don-Paterson/CCAS-Python-Toolkit/main/python/requirements.txt
git clone https://github.com/Don-Paterson/CCAS-Python-Toolkit C:\CCAS-Python
cd C:\CCAS-Python\python
```

## Configuration

The toolkit reads credentials and the management IP from either environment
variables or a `.env` file in the current directory:

| Variable           | Purpose                                                  |
|--------------------|----------------------------------------------------------|
| `CP_MGMT_HOST`     | Management server IP / hostname (default `10.1.1.101`)   |
| `CP_MGMT_USER`     | API username                                             |
| `CP_MGMT_PASS`     | API password                                             |
| `CP_MGMT_API_KEY`  | API key (alternative to username / password)             |
| `CP_MGMT_DOMAIN`   | MDS / Multi-Domain domain name (omit on a standalone SMS) |

Set up the `.env`:

```powershell
cd C:\CCAS-Python
copy .env.example .env
notepad .env
```

If neither env vars nor `.env` are set, the script prompts interactively for
the username and password (password input is masked via `getpass`).

## Usage

### Smoke test

The simplest check that everything works end-to-end:

```powershell
py -3 mgmt_api.py
```

This logs in, adds a host called `python_api_host` (3.3.3.3, pink) using
`set-if-exists` so it's idempotent, publishes, and logs out. Open
SmartConsole afterwards to verify it appears.

You can override the target SMS at the command line:

```powershell
py -3 mgmt_api.py --host 192.168.11.101
py -3 mgmt_api.py --host 10.1.1.101 --domain "Bravo_Domain"
```

### Lab 3A-3 example

`lab_example.py` replicates Lab 3A-3 (Alpha-Nets group, SecurityGateways
group, LDAP-Services service group). Run it after the host and network
objects from Labs 3A-1 and 3A-2 already exist:

```powershell
py -3 lab_example.py
```

### Writing your own script

Use `LabAPIClient` as a context manager. Every `mgmt_cmd()` call is one
Management API call. Publishes happen automatically every 80 successful
changes, and the context manager publishes and logs out on exit.

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

### Output format

Every successful `mgmt_cmd` prints:

```
Success <batch>.<count>
```

So you get `Success 1.1`, `Success 1.2`, ... `Success 1.80`, then a publish,
then `Success 2.1` and the second batch begins. This matches the bash version
exactly so log output is directly comparable.

Failures print:

```
Failed: <command> <payload>  (<error message from SDK>)
```

The script continues on failure rather than aborting — same as the bash. If
you'd rather abort on the first error, wrap the call:

```python
if not api.mgmt_cmd("add-host", {...}):
    raise SystemExit("Stopping on first failure")
```

## Mapping bash to Python

| Bash (`bash_api_v4.sh`)        | Python (`mgmt_api.py`)                  |
|--------------------------------|-----------------------------------------|
| `mgmtCmd add host name ...`    | `api.mgmt_cmd("add-host", {...})`       |
| `publish` function             | `api.publish()`                         |
| `login` / `logout` functions   | `with LabAPIClient() as api:`           |
| `publishEvery=80`              | `LabAPIClient(publish_every=80)`        |
| `apiPort=$(api status ...)`    | Handled by the SDK                      |
| Session cookie file            | In-memory SID inside the SDK            |
| `./bash_api_v4.sh "Domain"`    | `LabAPIClient(domain="Domain")`         |

## MDS / Multi-Domain

Pass `domain="<Domain_Name>"` to `LabAPIClient`, or set `CP_MGMT_DOMAIN`. The
SDK login then targets that domain instead of the global MDS.

```python
with LabAPIClient(host="10.1.1.101", domain="Alpha_Domain") as api:
    api.mgmt_cmd("add-host", {"name": "h1", "ip-address": "1.2.3.4"})
```

## Troubleshooting

**`Missing dependency: cpapi`**
The PyPI package name has wandered over time. Try `pip install cpapi`. If
that resolves to nothing useful or a stale version, check the current name
at <https://github.com/CheckPointSW/cp_mgmt_api_python_sdk>.

**Login fails with "fingerprint" / TLS errors**
The SDK is invoked with `unsafe=True, unsafe_auto_accept=True` so a
self-signed cert is accepted automatically. If you still see fingerprint
errors, there's probably an HTTPS Inspection-capable gateway between A-GUI
and the SMS interfering with TLS. Disable HI for the test, or target the
SMS's management IP that bypasses the inspecting gateway.

**Login fails with "unauthorized"**
Confirm in SmartConsole that the API user has appropriate permissions
(typically `Read/Write All`, or a custom profile that includes the
operations you're calling). On a fresh lab: make sure `api restart` was
run after creating the API user (Lab 2A-2).

**Calls time out**
The SDK defaults to port 443. If AppCtrl/URLF blades are enabled on the
SMS, the API moves to port 4434 — pass `port=4434` to `APIClientArgs`
inside `mgmt_api.py`, or expose it through `LabAPIClient` as a constructor
argument in your own fork.

**`Failed: <command> ...` on a known-good command**
Check the error message in parentheses. Most common causes:
referenced object doesn't exist (typo, or commands ran out of order), or
the object already exists and you didn't pass `"set-if-exists": True`.

## Notes

  - The SDK is invoked with `unsafe=True, unsafe_auto_accept=True` for lab
    convenience. Production deployments should pin fingerprints properly.
  - Designed for Skillable A-GUI (Hyper-V, Intel Xeon Gold 6330, x86-64);
    the installer downloads the amd64 Python build accordingly.
  - The bash-side companion `bash_api_v4.sh` is included in this repo for
    cross-reference and for tasks that still need to run on A-SMS itself.

## License

MIT — see `LICENSE`.
