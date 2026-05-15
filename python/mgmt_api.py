#!/usr/bin/env python3
"""
CCAS lab Management API helper - Python wrapper around mgmt_cli.exe.

This is the Python equivalent of bash_api_v4.sh. It orchestrates the
Check Point mgmt_cli.exe utility (shipped with SmartConsole on A-GUI)
using the same patterns as the bash version:

  - Login writes the session response to a temp file
  - Subsequent commands reference that file via  -s <sessionfile>
  - Publish runs automatically every 80 successful commands
  - Logout publishes once more, then logs out, then cleans up

The Python layer adds:

  - Native dict-based command payloads, auto-converted to mgmt_cli args.
    Lists expand to indexed form, e.g. members=["a","b"] becomes
    members.1 a  members.2 b   (the same form used in the courseware).
  - --format json output parsing on every command
  - A context manager for safe session lifecycle

The command name accepted by mgmt_cmd() may be in either form:

    api.mgmt_cmd("add host",  {...})     # courseware/bash form
    api.mgmt_cmd("add-host",  {...})     # API wire form

Both are tokenised and passed through to mgmt_cli, which accepts either.

No SDK dependency. mgmt_cli.exe must be installed (it ships with SmartConsole).

Environment variables (optional - prompted otherwise):
    CP_MGMT_HOST     - Management server  (default: 10.1.1.101)
    CP_MGMT_USER     - API username
    CP_MGMT_PASS     - API password
    CP_MGMT_API_KEY  - Alternative to user/pass
    CP_MGMT_DOMAIN   - MDS domain (omit on a standalone SMS)
    CP_MGMT_CLI      - Full path to mgmt_cli.exe (auto-detected otherwise)

A .env file in the working directory is auto-loaded if python-dotenv is installed.
"""

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional


# ---------------------------------------------------------------------------
# mgmt_cli discovery
# ---------------------------------------------------------------------------

def _find_mgmt_cli() -> str:
    """
    Locate the mgmt_cli executable.

    Order:
      1. CP_MGMT_CLI env var (full path)
      2. PATH (mgmt_cli / mgmt_cli.exe)
      3. C:\\Program Files (x86)\\CheckPoint\\SmartConsole\\*\\PROGRAM\\mgmt_cli.exe
         (highest version wins)
    """
    explicit = os.environ.get("CP_MGMT_CLI")
    if explicit and Path(explicit).is_file():
        return explicit

    on_path = shutil.which("mgmt_cli") or shutil.which("mgmt_cli.exe")
    if on_path:
        return on_path

    if sys.platform == "win32":
        program_files = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        sc_base = program_files / "CheckPoint" / "SmartConsole"
        if sc_base.is_dir():
            candidates: List[Path] = []
            for version_dir in sc_base.iterdir():
                if not version_dir.is_dir():
                    continue
                exe = version_dir / "PROGRAM" / "mgmt_cli.exe"
                if exe.is_file():
                    candidates.append(exe)
            if candidates:
                # Lexicographic sort on version dir name works for R-prefix
                # versions (R82 > R81.20 > R81.10 > R81).
                candidates.sort(key=lambda p: p.parent.parent.name, reverse=True)
                return str(candidates[0])

    raise FileNotFoundError(
        "mgmt_cli executable not found. Checked CP_MGMT_CLI, PATH, and "
        "'C:\\Program Files (x86)\\CheckPoint\\SmartConsole\\*\\PROGRAM'. "
        "Install SmartConsole or set CP_MGMT_CLI to the full path."
    )


# ---------------------------------------------------------------------------
# Payload -> mgmt_cli args conversion
# ---------------------------------------------------------------------------

def _stringify(value: Any) -> str:
    """Convert a Python value into mgmt_cli's expected string form."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _payload_to_args(payload: Dict[str, Any]) -> List[str]:
    """
    Convert a Python dict payload into mgmt_cli's positional argument form.

    Examples:
        {"name": "h1"}
            -> ["name", "h1"]

        {"members": ["a", "b", "c"]}
            -> ["members.1", "a", "members.2", "b", "members.3", "c"]

        {"nat-settings": {"auto-rule": True, "method": "hide"}}
            -> ["nat-settings.auto-rule", "true",
                "nat-settings.method",    "hide"]
    """
    args: List[str] = []
    for key, value in payload.items():
        if isinstance(value, list):
            for i, item in enumerate(value, start=1):
                args.extend([f"{key}.{i}", _stringify(item)])
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                args.extend([f"{key}.{sub_key}", _stringify(sub_value)])
        else:
            args.extend([key, _stringify(value)])
    return args


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LabAPIClient:
    """
    Python wrapper around mgmt_cli.exe.

    Mirrors bash_api_v4.sh's session-file, batching, and success-counter
    patterns. Used as a context manager:

        with LabAPIClient(host="10.1.1.101") as api:
            api.mgmt_cmd("add host", {"name": "h1", "ip-address": "1.2.3.4"})
    """

    def __init__(
        self,
        host: str = "10.1.1.101",
        session_name: str = "Initial Build",
        session_description: str = "Building my initial config for a new lab management.",
        publish_every: int = 80,
        domain: Optional[str] = None,
        mgmt_cli_path: Optional[str] = None,
    ):
        self.host = host
        self.session_name = session_name
        self.session_description = session_description
        self.publish_every = publish_every
        self.domain = domain
        self.mgmt_cli = mgmt_cli_path or _find_mgmt_cli()

        self.change_count = 1
        self.publish_batch = 1
        self._session_file: Optional[str] = None

    # ---- session lifecycle ----

    def login(
        self,
        user: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        api_key = api_key or os.environ.get("CP_MGMT_API_KEY")

        # Temp file to hold the login response. mgmt_cli's `-s <file>` reads
        # the SID out of this file on every subsequent call - same pattern
        # as bash_api_v4.sh's sessionCookie.
        fd, self._session_file = tempfile.mkstemp(prefix="cpsess_", suffix=".txt")
        os.close(fd)

        # Global flags (--management, -d) before the subcommand, matching the
        # courseware:
        #     mgmt_cli --format json --management "10.1.1.101" login api-key "..."
        cmd = [self.mgmt_cli, "--management", self.host]
        if self.domain:
            cmd.extend(["-d", self.domain])
        cmd.append("login")

        if api_key:
            cmd.extend(["api-key", api_key])
        else:
            user = user or os.environ.get("CP_MGMT_USER") \
                   or input("SmartConsole admin username: ")
            password = password or os.environ.get("CP_MGMT_PASS") \
                       or getpass.getpass("Password: ")
            cmd.extend(["user", user, "password", password])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError as e:
            self._cleanup_session_file()
            raise FileNotFoundError(f"Could not execute mgmt_cli: {e}") from e

        if result.returncode != 0:
            self._cleanup_session_file()
            err = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
            raise RuntimeError(f"Login failed: {err}")

        # Save the raw login response - same as bash_api_v4 redirects stdout
        # to its session cookie file.
        with open(self._session_file, "w") as f:
            f.write(result.stdout)

        # Name and describe the session (setupSession in bash)
        self._run("set session", {
            "new-name":    self.session_name,
            "description": self.session_description,
        }, quiet=True)

    def logout(self) -> None:
        if self._session_file is None:
            return
        try:
            try:
                self.publish()
            except Exception:
                pass  # don't let publish failure block logout
            self._run("logout", {}, quiet=True)
        finally:
            self._cleanup_session_file()

    def publish(self) -> None:
        if self._session_file is None:
            raise RuntimeError("Not logged in")
        self._run("publish", {}, quiet=True)

    # ---- the bash mgmtCmd equivalent ----

    def mgmt_cmd(self, command: str, payload: Dict[str, Any]) -> bool:
        """
        Run a single mgmt_cli command. Mirrors mgmtCmd() in bash_api_v4.sh.

        The command may be in either the courseware form ("add host") or
        the API wire form ("add-host"). Both work.

        Returns True on success, False on failure. Auto-publishes every
        `publish_every` successful changes.
        """
        success, _ = self._run(command, payload, quiet=False)

        if success:
            print(f"Success {self.publish_batch}.{self.change_count}")
            self.change_count += 1
        # Failure message is printed inside _run when quiet=False.

        if self.change_count > self.publish_every:
            print("Publishing...")
            self.publish()
            self._run("set session", {
                "new-name":    self.session_name,
                "description": self.session_description,
            }, quiet=True)
            self.change_count = 1
            self.publish_batch += 1

        return success

    # ---- internal helpers ----

    def _run(
        self,
        command: str,
        payload: Dict[str, Any],
        quiet: bool = False,
    ) -> Tuple[bool, dict]:
        """
        Execute one mgmt_cli call against the active session.

        Returns (success, parsed_json). On failure, prints a `Failed: ...`
        line unless `quiet` is True.

        The command string is tokenised on whitespace, so both "add host" and
        "add-host" expand correctly. Global flags (-s, --format) come BEFORE
        the subcommand tokens, then payload args.
        """
        if self._session_file is None:
            raise RuntimeError("Not logged in")

        cmd = [self.mgmt_cli, "-s", self._session_file, "--format", "json"]
        cmd.extend(command.split())
        cmd.extend(_payload_to_args(payload))

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        parsed: dict = {}
        if result.stdout.strip():
            try:
                parsed = json.loads(result.stdout)
            except json.JSONDecodeError:
                parsed = {}

        if result.returncode == 0:
            return True, parsed

        if not quiet:
            err = (
                parsed.get("message")
                or result.stderr.strip()
                or result.stdout.strip()
                or f"exit {result.returncode}"
            )
            print(f"Failed: {command} {payload}  ({err})")
        return False, parsed

    def _cleanup_session_file(self) -> None:
        if self._session_file is None:
            return
        try:
            os.remove(self._session_file)
        except OSError:
            pass
        self._session_file = None

    # ---- context manager sugar ----

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()


# ---------------------------------------------------------------------------
# CLI entrypoint (smoke test)
# ---------------------------------------------------------------------------

def _parse_args():
    p = argparse.ArgumentParser(
        description="CCAS lab Management API client (mgmt_cli wrapper)"
    )
    p.add_argument("--host",   default=os.environ.get("CP_MGMT_HOST", "10.1.1.101"))
    p.add_argument("--domain", default=os.environ.get("CP_MGMT_DOMAIN", None),
                   help="MDS domain name (omit for standalone SMS)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    with LabAPIClient(host=args.host, domain=args.domain) as api:
        # Single smoke-test command
        api.mgmt_cmd("add host", {
            "name":       "python_api_host",
            "ip-address": "3.3.3.3",
            "color":      "pink",
            "comments":   "Python API script test",
        })
