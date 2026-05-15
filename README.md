# CCAS Python Toolkit

Python equivalent of `bash_api.sh` for the Check Point Certified Automation
Specialist (CCAS) lab, designed to run from the **A-GUI** Windows VM rather
than from the A-SMS expert shell.

Sister to the bash version: same publish-every-80 batching, same
`Success 1.1 / 1.2 / ...` output format, same lab objectives — but uses the
official Check Point Management API Python SDK (`cpapi`) rather than
`mgmt_cli`.

## Quick start

On A-GUI, in an elevated PowerShell:

```powershell
irm https://raw.githubusercontent.com/Don-Paterson/CCAS-Python-Toolkit/main/Install-PythonOnAGUI.ps1 | iex
```

That installs Python 3.13 (amd64), the required pip packages, and drops the
toolkit into `C:\CCAS-Python\`. Then:

```powershell
cd C:\CCAS-Python
copy .env.example .env
notepad .env                    # set CP_MGMT_HOST and credentials
py -3 lab_example.py            # runs the Lab 3A-3 equivalent
```

## Layout

```
CCAS-Python-Toolkit/
├── Install-PythonOnAGUI.ps1     irm | iex installer
├── README.md
└── python/
    ├── mgmt_api.py              LabAPIClient class (mgmtCmd equivalent)
    ├── lab_example.py           Lab 3A-3 reimplemented in Python
    ├── requirements.txt
    └── .env.example
```

## Usage

The `LabAPIClient` class is a context manager that:

  - Logs in (interactive prompts if no env vars / `.env`)
  - Names the session ("Initial Build", same as the bash version)
  - Runs `mgmt_cmd("command-name", {payload-dict})` calls
  - Auto-publishes every 80 successful changes
  - Publishes and logs out on `__exit__`

Example:

```python
from mgmt_api import LabAPIClient

with LabAPIClient(host="10.1.1.101") as api:
    api.mgmt_cmd("add-host", {
        "name":       "my-host",
        "ip-address": "1.2.3.4",
        "color":      "pink",
    })
```

For MDS, pass `domain="Domain_Name"` to the constructor, or set
`CP_MGMT_DOMAIN` in `.env`.

## Mapping to the bash version

| Bash (`bash_api_v4.sh`)       | Python (`mgmt_api.py`)              |
|-------------------------------|-------------------------------------|
| `mgmtCmd <cmd> <args...>`     | `api.mgmt_cmd("cmd", {...})`        |
| `login` / `logout`            | `with LabAPIClient() as api:`       |
| `publishEvery=80`             | `LabAPIClient(publish_every=80)`    |
| `apiPort=$(api status ...)`   | handled by the SDK                  |
| Session cookie file           | in-memory SID inside the SDK        |

## Notes

  - The SDK is invoked with `unsafe=True, unsafe_auto_accept=True` so the
    SMS's self-signed certificate is accepted without manual fingerprinting.
    Fine for the lab; production deployments should use proper certificate
    verification.
  - The `cpapi` PyPI name has historically had alternative spellings. If
    `pip install cpapi` fails on a future Python build, verify the current
    name on PyPI or in the `CheckPointSW/cp_mgmt_api_python_sdk` GitHub repo.
  - Designed for Skillable A-GUI (Hyper-V, Intel Xeon Gold 6330, x86-64).
    The installer pulls the amd64 Python build accordingly.
