#!/usr/bin/env python3
"""
Smoke test for the CCAS Python Toolkit.

Creates three test hosts and a group containing them, mirroring the standard
mgmt_cli pattern from the courseware. One add per object, no idempotency.

Run on a fresh management. If the objects already exist, delete them in
SmartConsole first.

Run:
    py -3 lab_example.py
"""

from mgmt_api import LabAPIClient


def main():
    with LabAPIClient() as api:

        api.mgmt_cmd("add host", {
            "name":       "Test-host-1",
            "ip-address": "192.168.99.201",
            "color":      "crete blue",
            "comments":   "Created by python automation test script",
        })

        api.mgmt_cmd("add host", {
            "name":       "Test-host-2",
            "ip-address": "192.168.99.202",
            "color":      "crete blue",
            "comments":   "Created by python automation test script",
        })

        api.mgmt_cmd("add host", {
            "name":       "Test-host-3",
            "ip-address": "192.168.99.203",
            "color":      "crete blue",
            "comments":   "Created by python automation test script",
        })

        api.mgmt_cmd("add group", {
            "name":     "Test-hosts-group",
            "comments": "Group of test hosts",
            "color":    "crete blue",
            "members":  ["Test-host-1", "Test-host-2", "Test-host-3"],
        })


if __name__ == "__main__":
    main()
