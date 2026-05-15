#!/usr/bin/env python3
"""
Self-contained smoke test for the CCAS Python Toolkit.

Creates a small set of clearly-marked test objects to prove the toolkit can
log in, create objects, publish, and log out. Re-runnable thanks to
'set-if-exists: true' on every call - no cleanup needed between runs.

No dependencies on any previous lab step.

Run:
    py -3 lab_example.py

Expected output:
    Success 1.1
    Success 1.2
    Success 1.3
    Success 1.4
    Success 1.5
    Publishing...

Then open SmartConsole and look for five new objects coloured 'sea green'
with names beginning 'PYTEST_':
    - PYTEST_HOST_1, PYTEST_HOST_2, PYTEST_HOST_3 (hosts)
    - PYTEST_NET                                  (network)
    - PYTEST_GROUP                                (group containing all four)

To remove the test objects when you're done, delete PYTEST_GROUP first, then
the network and hosts, from SmartConsole.
"""

from mgmt_api import LabAPIClient


# A clear prefix and an unmistakable colour so the test objects are easy to
# find and clean up in SmartConsole.
PREFIX = "PYTEST_"
COLOUR = "sea green"
COMMENT = "Created by CCAS Python Toolkit smoke test"


def main():
    with LabAPIClient() as api:

        # Three test hosts, in a deliberately non-overlapping subnet
        for i in range(1, 4):
            api.mgmt_cmd("add-host", {
                "name":          f"{PREFIX}HOST_{i}",
                "ip-address":    f"10.99.99.{i}",
                "color":         COLOUR,
                "comments":      COMMENT,
                "set-if-exists": True,
            })

        # A test network covering the host range above
        api.mgmt_cmd("add-network", {
            "name":          f"{PREFIX}NET",
            "subnet4":       "10.99.99.0",
            "mask-length4":  24,
            "color":         COLOUR,
            "comments":      COMMENT,
            "set-if-exists": True,
        })

        # A group bundling everything created above. Members are referenced by
        # name; they're visible inside this session even before the publish.
        api.mgmt_cmd("add-group", {
            "name":          f"{PREFIX}GROUP",
            "members": [
                f"{PREFIX}HOST_1",
                f"{PREFIX}HOST_2",
                f"{PREFIX}HOST_3",
                f"{PREFIX}NET",
            ],
            "color":         COLOUR,
            "comments":      COMMENT,
            "set-if-exists": True,
        })

        # Implicit publish + logout happens on __exit__


if __name__ == "__main__":
    main()
