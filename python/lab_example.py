#!/usr/bin/env python3
"""
CCAS Lab 3A-3 equivalent - run from A-GUI via Python.

The original lab task creates the Alpha-Nets group, the SecurityGateways
group, and the LDAP-Services service group using the bash_api.sh wrapper
on A-SMS. This script does the same job from the A-GUI Windows VM using
the Python SDK.

Pre-requisites:
  - Install-PythonOnAGUI.ps1 has been run on this A-GUI
  - .env contains CP_MGMT_HOST, CP_MGMT_USER, CP_MGMT_PASS (or rely on prompts)
  - The host and network objects from Lab 3A-1 and 3A-2 already exist
"""

from mgmt_api import LabAPIClient


def main():
    with LabAPIClient() as api:

        # /Create the Alpha-Nets group
        api.mgmt_cmd("add-group", {
            "name":     "Alpha-Nets",
            "comments": "Alpha Corporation Headquarters Networks",
            "color":    "crete blue",
            "members":  ["A-DMZ-NET", "A-INT-NET", "A-MGMT-NET"],
        })

        # /Create the SecurityGateways group (empty for now - gateways added later)
        api.mgmt_cmd("add-group", {
            "name":     "SecurityGateways",
            "comments": "Alpha Corporation Security Gateways",
            "color":    "pink",
        })

        # /Create the LDAP-Services service group
        api.mgmt_cmd("add-service-group", {
            "name":     "LDAP-Services",
            "comments": "LDAP Services Group",
            "color":    "turquoise",
            "members": [
                "ALL_DCE_RPC",
                "Kerberos_v5_TCP",
                "Kerberos_v5_UDP",
                "kerberos-udp",
                "ldap",
                "ldap-ssl",
                "ldap_udp",
                "smb",
                "smb-udp",
            ],
        })

        # Implicit publish + logout happens via the context manager's __exit__


if __name__ == "__main__":
    main()
