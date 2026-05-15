#!/usr/bin/env python3
"""
CCAS lab Management API helper - Python equivalent of bash_api_v4.sh.

Uses the official Check Point Management API Python SDK (cp-mgmt-api-sdk,
imported as cpapi) to drive the same kind of automation as the bash version,
but from the A-GUI lab VM (Windows) rather than from the SMS expert shell.

Environment variables (optional - prompted otherwise):
    CP_MGMT_HOST     - Management server  (default: 10.1.1.101)
    CP_MGMT_USER     - API username
    CP_MGMT_PASS     - API password
    CP_MGMT_API_KEY  - Alternative to user/pass
    CP_MGMT_DOMAIN   - MDS domain (omit on a standalone SMS)

A .env file in the working directory is auto-loaded if python-dotenv is installed.
"""

import argparse
import getpass
import os
import sys
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional - prompts/env vars still work

try:
    from cpapi import APIClient, APIClientArgs
except ImportError:
    sys.exit(
        "Missing dependency: cp-mgmt-api-sdk (imported as cpapi).\n"
        "Run:  py -3 -m pip install cp-mgmt-api-sdk\n"
        "(or rerun Install-PythonOnAGUI.ps1)"
    )


class LabAPIClient:
    """
    Wraps cpapi with publish-batching and success tracking,
    matching the bash_api.sh / bash_api_v4.sh pattern.

    Use as a context manager:

        with LabAPIClient(host="10.1.1.101") as api:
            api.mgmt_cmd("add-host", {"name": "h1", "ip-address": "1.2.3.4"})
    """

    def __init__(
        self,
        host: str = "10.1.1.101",
        session_name: str = "Initial Build",
        session_description: str = "Building my initial config for a new lab management.",
        publish_every: int = 80,
        domain: Optional[str] = None,
    ):
        self.host = host
        self.session_name = session_name
        self.session_description = session_description
        self.publish_every = publish_every
        self.domain = domain

        self.change_count = 1
        self.publish_batch = 1

        self._client: Optional[APIClient] = None

    # ---- session lifecycle ----

    def login(
        self,
        user: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        api_key = api_key or os.environ.get("CP_MGMT_API_KEY")

        # Lab: accept the SMS's self-signed cert without manual fingerprinting.
        args = APIClientArgs(server=self.host, unsafe=True, unsafe_auto_accept=True)
        self._client = APIClient(args)

        if api_key:
            if self.domain:
                login_res = self._client.login_with_api_key(api_key, domain=self.domain)
            else:
                login_res = self._client.login_with_api_key(api_key)
        else:
            user     = user     or os.environ.get("CP_MGMT_USER") or input("SmartConsole admin username: ")
            password = password or os.environ.get("CP_MGMT_PASS") or getpass.getpass("Password: ")
            if self.domain:
                login_res = self._client.login(user, password, domain=self.domain)
            else:
                login_res = self._client.login(user, password)

        if not login_res.success:
            raise RuntimeError(f"Login failed: {login_res.error_message}")

        # Name and describe the session (same as setupSession in bash)
        self._client.api_call(
            "set-session",
            {"new-name": self.session_name, "description": self.session_description},
        )

    def logout(self) -> None:
        if self._client is None:
            return
        try:
            self.publish()
        finally:
            self._client.api_call("logout", {})
            self._client = None

    def publish(self) -> None:
        if self._client is None:
            raise RuntimeError("Not logged in")
        self._client.api_call("publish", {})

    # ---- the bash_api mgmtCmd equivalent ----

    def mgmt_cmd(self, command: str, payload: dict) -> bool:
        """
        Run a single Management API call. Mirrors mgmtCmd() in bash_api_v4.sh.

        Returns True on success, False on failure. Auto-publishes every
        `publish_every` successful changes (default 80, matches the bash).
        """
        if self._client is None:
            raise RuntimeError("Not logged in")

        result = self._client.api_call(command, payload)
        if result.success:
            print(f"Success {self.publish_batch}.{self.change_count}")
            self.change_count += 1
        else:
            err = getattr(result, "error_message", "(no error_message)")
            print(f"Failed: {command} {payload}  ({err})")

        if self.change_count > self.publish_every:
            print("Publishing...")
            self.publish()
            self._client.api_call(
                "set-session",
                {"new-name": self.session_name, "description": self.session_description},
            )
            self.change_count = 1
            self.publish_batch += 1

        return result.success

    # ---- context manager sugar ----

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()


def _parse_args():
    p = argparse.ArgumentParser(description="CCAS lab Management API client (Python)")
    p.add_argument("--host",   default=os.environ.get("CP_MGMT_HOST", "10.1.1.101"))
    p.add_argument("--domain", default=os.environ.get("CP_MGMT_DOMAIN", None),
                   help="MDS domain name (omit for standalone SMS)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    with LabAPIClient(host=args.host, domain=args.domain) as api:
        # Equivalent of v4's smoke-test command
        api.mgmt_cmd(
            "add-host",
            {
                "name":          "python_api_host",
                "ip-address":    "3.3.3.3",
                "comments":      "Python API script test",
                "color":         "pink",
                "set-if-exists": True,
            },
        )
