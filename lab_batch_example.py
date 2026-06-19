#!/usr/bin/env python3
"""
Bulk-creation examples for the CCAS Python Toolkit.

Shows the two ways to create many objects at once, so you can compare them:

  1. loop_demo()   - a plain Python for-loop calling mgmt_cmd() once per host.
                     This is the direct equivalent of a bash while-loop. It is
                     simple and readable, but it is still ONE mgmt_cli process
                     and ONE API call per host (convenience, not efficiency).

  2. batch_demo()  - mgmt_cli's NATIVE --batch mode via mgmt_cmd_batch(). One
                     process, one API call, the whole CSV created server-side.
                     This is the courseware slide:
                         mgmt_cli add host --batch hosts-file.csv
                     Use this when N is large.

Both create a group first, then 20 hosts. The loop assigns each host into the
group AT CREATION using the `groups` parameter (add host ... groups.1 <name>),
which avoids the "add group can't be re-run" problem - the group is created
once and each host attaches itself to the existing group.

Run on a fresh management. The group is created with a plain `add group`, so to
re-run cleanly, delete the group (and its hosts) in SmartConsole first. The
hosts themselves use set-if-exists, so re-running overwrites them rather than
erroring.

Run:
    py -3 lab_batch_example.py            # runs the loop demo
    py -3 lab_batch_example.py --batch    # runs the native batch demo
"""

import argparse
import csv
import os
import tempfile

from mgmt_api import LabAPIClient


HOST_COUNT = 20


def loop_demo(api: LabAPIClient) -> None:
    """Python for-loop: one add host per object, group assigned at creation."""
    group = "Loop-Group"

    api.mgmt_cmd("add group", {
        "name":     group,
        "color":    "purple",
        "comments": "Created by lab_batch_example loop demo",
    })

    for i in range(1, HOST_COUNT + 1):
        api.mgmt_cmd("add host", {
            "name":          f"Loop-host-{i:02d}",
            "ip-address":    f"192.168.50.{i}",
            "color":         "purple",
            "set-if-exists": True,        # re-runnable: overwrite if it exists
            "groups":        [group],     # attach to the existing group now
            "comments":      "Created by lab_batch_example loop demo",
        })


def batch_demo(api: LabAPIClient) -> None:
    """Native mgmt_cli --batch: build a CSV, create all hosts in one call."""
    group = "Batch-Group"

    api.mgmt_cmd("add group", {
        "name":     group,
        "color":    "purple",
        "comments": "Created by lab_batch_example batch demo",
    })

    # CSV header row = parameter names; each following row = one host.
    fieldnames = ["name", "ip-address", "color", "groups.1", "comments"]
    rows = [
        {
            "name":      f"Batch-host-{i:02d}",
            "ip-address": f"192.168.60.{i}",
            "color":     "purple",
            "groups.1":  group,           # attach to the existing group
            "comments":  "Created by lab_batch_example batch demo",
        }
        for i in range(1, HOST_COUNT + 1)
    ]

    # Write to a temp CSV, hand it to mgmt_cli, then clean up.
    fd, path = tempfile.mkstemp(prefix="hosts_", suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        api.mgmt_cmd_batch("add host", path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="CCAS bulk-creation demos")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Use native mgmt_cli --batch CSV mode instead of the Python loop",
    )
    args = parser.parse_args()

    with LabAPIClient() as api:
        if args.batch:
            batch_demo(api)
        else:
            loop_demo(api)


if __name__ == "__main__":
    main()
