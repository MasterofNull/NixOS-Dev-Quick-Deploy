#!/usr/bin/env python3
"""Cohort REJECT binding-review 20260925, finding 3 -- `revocation_launch_authorization`
in `dashboard/backend/api/routes/aistack.py` must report the daemon's RESOLVED RUNTIME
STATE (socket present/connectable, the service's own resolved StateDirectory env var,
`aq-revocation-launch-clients` group membership via `grp`) -- NEVER by grepping/reading
`revocation_epoch_transport.py`'s source text. A source-substring match is always true
once the code is committed and proves nothing about whether the RUNNING instance actually
enforces anything.

This test EXERCISES the real `get_capability_enforcement()` function (no reimplemented
duplicate logic) with controlled fixtures for `subprocess.run` (the daemon's OWN resolved
`systemctl show` environment) and `socket.socket.connect` (the launch socket's actual
reachability) -- proving the runtime-probe path itself, not a source grep.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "dashboard" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from api.routes import aistack  # noqa: E402

fails: list[str] = []


def need(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


_LAUNCH_SOCK = "/run/aq-revocation-epoch-authority/launch.sock"
_CONTROL_SOCK = "/run/aq-revocation-epoch-authority/control.sock"


def _fake_systemctl_show(epoch_path: str, teg_uid: str):
    """`side_effect` for `subprocess.run` -- returns the AI-switchboard call
    (sections 1-3, must succeed with returncode=0 or the whole function
    returns early) untouched/empty, and the revocation-epoch-authority
    call (section 7) with the given RESOLVED environment -- the daemon's
    OWN environment, never a hardcoded guess."""

    def _run(args, **kwargs):
        unit = args[2] if len(args) > 2 else ""
        if unit == "aq-revocation-epoch-authority.service":
            stdout = f"AQ_REVOCATION_EPOCH_EPOCH_PATH={epoch_path} AQ_REVOCATION_LAUNCH_TEG_UID={teg_uid}"
        else:
            stdout = ""
        return mock.MagicMock(returncode=0, stdout=stdout, stderr="")

    return _run


def test_resolved_ledger_path_follows_the_daemons_own_env_var() -> None:
    """The ledger path is resolved from `AQ_REVOCATION_EPOCH_EPOCH_PATH` as
    reported by the daemon's OWN `systemctl show` environment -- never the
    old hardcoded `/var/lib/aq-revocation-epoch-authority/launch-ledger`
    guess. Proven here with a ledger tree at an arbitrary temp path the
    hardcoded guess could never have found."""
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "custom-state-root"
        epoch_path = state_root / "epoch"
        ledger_root = state_root / "launch-ledger"
        for sub in ("issued", "consumed", "expired"):
            (ledger_root / sub).mkdir(parents=True, exist_ok=True)
            os.chmod(str(ledger_root / sub), 0o700)

        with mock.patch("subprocess.run", side_effect=_fake_systemctl_show(str(epoch_path), "")):
            result = aistack.get_capability_enforcement()

        rla = result.get("revocation_launch_authorization") or {}
        need(
            rla.get("resolved_ledger_state_path") == str(ledger_root),
            f"resolved_ledger_state_path must follow the daemon's own env var, got {rla.get('resolved_ledger_state_path')!r}",
        )
        need(rla.get("ledger_durable") is True, "a genuinely 0700 issued/consumed/expired tree at the RESOLVED path must report ledger_durable=True")


def test_unresolvable_env_reports_unknown_not_a_hardcoded_fallback() -> None:
    """When the daemon's environment cannot be resolved (never provisioned/
    started on this host), the ledger path/durability must be `None`
    (unknown) -- NOT silently fall back to the old hardcoded
    `/var/lib/...` guess (which could report a stale/unrelated tree as
    this instance's own state)."""
    with mock.patch("subprocess.run", side_effect=_fake_systemctl_show("", "")):
        # empty epoch_path -> AQ_REVOCATION_EPOCH_EPOCH_PATH="" is falsy, resolved_epoch_path is ""
        result = aistack.get_capability_enforcement()
    rla = result.get("revocation_launch_authorization") or {}
    need(rla.get("resolved_ledger_state_path") is None, "an unresolved env var must report resolved_ledger_state_path=None, never a hardcoded guess")
    need(rla.get("ledger_durable") is None, "an unresolved ledger path must report ledger_durable=None (unknown), never True/False")


def test_teg_peer_check_enforced_reflects_resolved_uid_not_a_source_grep() -> None:
    """`teg_peer_check_enforced` must come from the daemon's OWN resolved
    `AQ_REVOCATION_LAUNCH_TEG_UID` -- an empty/unresolved value (C6a's
    designed fail-closed resting state) is genuinely enforced (denies
    every peer); a PROVISIONED (non-empty) value is only reported enforced
    once the launch group's live `grp` membership confirms the frozen
    C6a topology -- on a host with no `aq-revocation-launch-clients`
    group provisioned (this dev box), that membership is unconfirmable
    (`None`), so a provisioned uid must NOT be reported enforced."""
    with mock.patch("subprocess.run", side_effect=_fake_systemctl_show("", "")):
        empty_result = aistack.get_capability_enforcement()
    need(
        (empty_result.get("revocation_launch_authorization") or {}).get("teg_peer_check_enforced") is True,
        "an empty/unresolved AQ_REVOCATION_LAUNCH_TEG_UID is C6a's fail-closed resting state -- must report enforced=True",
    )

    with mock.patch("subprocess.run", side_effect=_fake_systemctl_show("", "4242")):
        provisioned_result = aistack.get_capability_enforcement()
    rla = provisioned_result.get("revocation_launch_authorization") or {}
    need(
        rla.get("teg_peer_check_enforced") is False,
        "a provisioned TEG uid whose launch-group topology cannot be confirmed live must NOT be reported enforced=True",
    )


def test_launch_op_requires_a_connectable_socket_not_mere_presence() -> None:
    """`authorize_launch_op` must reflect whether the launch socket is
    ACTUALLY connectable (a live probe), never merely whether a stale
    socket FILE exists -- and never a source-tree grep for
    `build_launch_handler`/`authorize_launch`/`consume_launch` (which is
    always true once the code is committed, regardless of whether
    anything is listening)."""
    real_exists = Path.exists

    def fake_exists(self):
        if str(self) in (_LAUNCH_SOCK, _CONTROL_SOCK):
            return True
        return real_exists(self)

    # (a) socket path present but nothing listening -- connect() must fail, and the
    # op must report absent despite the file "existing".
    def refusing_connect(self, address):
        if address == _LAUNCH_SOCK:
            raise ConnectionRefusedError("nothing listening")
        raise OSError("unexpected address in test")

    with mock.patch("subprocess.run", side_effect=_fake_systemctl_show("", "")), \
         mock.patch("pathlib.Path.exists", fake_exists), \
         mock.patch("socket.socket.connect", refusing_connect):
        present_not_connectable = aistack.get_capability_enforcement()
    need(
        (present_not_connectable.get("revocation_launch_authorization") or {}).get("authorize_launch_op") == "op_absent",
        "a present-but-unconnectable launch socket must report op_absent, not op_present",
    )

    # (b) socket path present AND genuinely connectable.
    def accepting_connect(self, address):
        if address == _LAUNCH_SOCK:
            return None
        raise OSError("unexpected address in test")

    with mock.patch("subprocess.run", side_effect=_fake_systemctl_show("", "")), \
         mock.patch("pathlib.Path.exists", fake_exists), \
         mock.patch("socket.socket.connect", accepting_connect):
        connectable = aistack.get_capability_enforcement()
    need(
        (connectable.get("revocation_launch_authorization") or {}).get("authorize_launch_op") == "op_present",
        "a present AND connectable launch socket must report op_present",
    )


def test_source_text_of_revocation_transport_is_never_read_for_this_section() -> None:
    """Regression guard: `aistack.py` must not reintroduce a
    `revocation_epoch_transport.py` source read/grep for this section --
    the exact finding-3 defect. Static, cheap, catches a silent revert."""
    src = (ROOT / "dashboard" / "backend" / "api" / "routes" / "aistack.py").read_text()
    # Section 6 (`revocation_epoch_authority`, PASS in the review) legitimately never reads
    # source either; the retired defect was specifically reading revocation_epoch_transport.py
    # inside get_capability_enforcement's section 7.
    need(
        'ret_src = (_repo_root() / "scripts" / "ai" / "lib" / "revocation_epoch_transport.py").read_text()' not in src,
        "the retired source-grep of revocation_epoch_transport.py must not reappear in aistack.py",
    )
    need(
        '"AQ_REVOCATION_EPOCH_EPOCH_PATH"' in src,
        "aistack.py must resolve the ledger path from the daemon's own AQ_REVOCATION_EPOCH_EPOCH_PATH env var",
    )


def main() -> int:
    test_resolved_ledger_path_follows_the_daemons_own_env_var()
    test_unresolvable_env_reports_unknown_not_a_hardcoded_fallback()
    test_teg_peer_check_enforced_reflects_resolved_uid_not_a_source_grep()
    test_launch_op_requires_a_connectable_socket_not_mere_presence()
    test_source_text_of_revocation_transport_is_never_read_for_this_section()

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"\n{len(fails)} assertion(s) failed")
        return 1
    print("PASS: C6a launch dashboard runtime-probe (resolved env path, connectable-socket op, live TEG-uid enforcement, no source grep)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
