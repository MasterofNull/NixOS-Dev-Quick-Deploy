#!/usr/bin/env python3
"""ServiceManager builds exact per-unit systemctl commands (single and all); sudo is mocked."""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

from api.services import service_manager as sm  # noqa: E402


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


LISTING_NOPASSWD = """Matching Defaults entries for u on h:
    env_keep+=TERMINFO

User u may run the following commands on h:
    (ALL : ALL) SETENV: ALL
    (ALL : ALL) NOPASSWD: /store/systemctl --no-block restart ai-aidb.service, /store/systemctl --no-block restart qdrant.service
"""
# Password-tagged match: `sudo -n -l <cmd>` would still exit 0 (listpw=any).
LISTING_PASSWD = """User u may run the following commands on h:
    (ALL : ALL) NOPASSWD: /store/other
    (ALL : ALL) PASSWD: /store/systemctl --no-block restart ai-aidb.service
    (ALL : ALL) /store/systemctl *
"""


def run_with(sudo_ok: bool, coro_factory, listing=None):
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        if "-l" in cmd:  # full `sudo -n -l` listing
            if not sudo_ok:
                return SimpleNamespace(returncode=1, stdout="", stderr="a password is required")
            return SimpleNamespace(returncode=0, stdout=listing or LISTING_NOPASSWD, stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with mock.patch.object(sm.subprocess, "run", fake_run), \
         mock.patch.object(sm, "SUDO_BIN", "/sudo"), \
         mock.patch.object(sm, "SYSTEMCTL_BIN", "/store/systemctl"), \
         mock.patch.object(sm, "get_monitored_units", lambda include_dashboard=True: ["ai-aidb", "qdrant"]):
        result = asyncio.run(coro_factory(sm.ServiceManager()))
    return result, calls


def main() -> None:
    result, calls = run_with(True, lambda m: m.restart_service("ai-aidb"))
    assert_true(result["success"], f"single action failed: {result}")
    assert_true(
        ["/sudo", "-n", "/store/systemctl", "--no-block", "restart", "ai-aidb.service"] in calls,
        f"single sudo command wrong: {calls}",
    )
    assert_true(["/sudo", "-n", "-l"] in calls, "probe must read the full `sudo -n -l` listing")

    result, calls = run_with(True, lambda m: m.restart_service("ai-aidb"), LISTING_PASSWD)
    assert_true(
        ["/store/systemctl", "--no-block", "restart", "ai-aidb.service"] in calls
        and not any(c[:3] == ["/sudo", "-n", "/store/systemctl"] for c in calls),
        f"PASSWD-tagged match must not use sudo: {calls}",
    )
    assert_true(
        sm.listing_allows_nopasswd(LISTING_NOPASSWD, ["/store/systemctl", "--no-block", "restart", "qdrant.service"])
        and not sm.listing_allows_nopasswd(LISTING_NOPASSWD, ["/store/systemctl", "--no-block", "stop", "qdrant.service"]),
        "listing parser: exact NOPASSWD command matches, others do not",
    )

    result, calls = run_with(False, lambda m: m.stop_service("qdrant"))
    assert_true(
        ["/store/systemctl", "--no-block", "stop", "qdrant.service"] in calls
        and not any(c[:3] == ["/sudo", "-n", "/store/systemctl"] for c in calls),
        f"without sudo rule the plain systemctl must run: {calls}",
    )

    start_listing = (
        "User u may run the following commands on h:\n"
        "    (ALL : ALL) NOPASSWD: /store/systemctl --no-block start ai-aidb.service, "
        "/store/systemctl --no-block start qdrant.service\n"
    )
    result, calls = run_with(True, lambda m: m.start_all_services(), start_listing)
    assert_true(result["success"] and result["succeeded"] == 2, f"batch failed: {result}")
    executed = [c for c in calls if "-l" not in c]
    assert_true(
        executed == [
            ["/sudo", "-n", "/store/systemctl", "--no-block", "start", "ai-aidb.service"],
            ["/sudo", "-n", "/store/systemctl", "--no-block", "start", "qdrant.service"],
        ],
        f"'all' must be one exact call per unit: {executed}",
    )
    print("PASS: service_manager single and all actions build exact per-unit commands")


if __name__ == "__main__":
    main()
