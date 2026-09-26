#!/usr/bin/env python3
"""Foundation C C6a — `authorize_launch` + single-use launch-token `consume_launch` on the
C6-S launch socket. Cross-surface Service-Coverage test, mirroring
`test-c2-sci-service-coverage.py` / `test-revocation-launch-socket-topology.py`.

Two parts:

1. Static cross-surface assertions — env-contract documents
   `AQ_REVOCATION_LAUNCH_TEG_UID` (empty default, no capability flag), the Nix module declares
   the launch-ledger StateDirectory subtree + the TEG-uid env reference with `enable` staying
   false, the dashboard API/JS surface `revocation_launch_authorization`, and the registry
   registers this check (offline, no service, no network).
2. A LIVE `serve_multi()` exercise on temp-dir sockets (mirrors
   `test-revocation-launch-socket-topology.py`'s `_MultiHarness`): with an EMPTY TEG uid,
   authorize_launch/consume_launch deny (fail-closed); with a FIXTURE TEG uid resolved to this
   test process's own uid (so `SO_PEERCRED` genuinely matches), issue -> consume succeeds
   exactly once, a duplicate consume denies, a non-TEG peer denies, an expired token denies, an
   epoch bumped after issuance denies, and the op is reachable ONLY over the launch socket (the
   control socket never dispatches it).
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB_DIR = os.path.join(ROOT, "scripts", "ai", "lib")
sys.path.insert(0, LIB_DIR)

import revocation_epoch as re_lib  # noqa: E402
import revocation_epoch_transport as ret  # noqa: E402

fails: list[str] = []


def need(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def _iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_dicts(v)


# --------------------------------------------------------------------------
# 1. Static cross-surface assertions
# --------------------------------------------------------------------------


def _check_static() -> None:
    import yaml

    ec = yaml.safe_load(open(os.path.join(ROOT, "config", "env-contract.yaml")))
    entries = ec.get("environment_variables") or ec.get("variables") or ec.get("env") or []
    if not entries:
        entries = list(_iter_dicts(ec))
    teg_uid_env = next((e for e in entries if isinstance(e, dict) and e.get("canonical") == "AQ_REVOCATION_LAUNCH_TEG_UID"), None)
    need(teg_uid_env is not None, "env-contract must declare AQ_REVOCATION_LAUNCH_TEG_UID")
    need(
        teg_uid_env is None or teg_uid_env.get("default") == "",
        "AQ_REVOCATION_LAUNCH_TEG_UID must default to empty (fail-closed until C6b)",
    )

    nix = open(os.path.join(ROOT, "nix", "modules", "services", "revocation-epoch-authority.nix")).read()
    need("default = false;" in nix, "revocation-epoch-authority.nix must still default enable=false")
    need("launchTegUid" in nix, "module must declare a launchTegUid option")
    need("AQ_REVOCATION_LAUNCH_TEG_UID=${cfg.launchTegUid}" in nix, "unit Environment must wire the TEG uid reference")
    need("launch-ledger/issued" in nix, "tmpfiles rules must declare the launch-ledger issued StateDir")
    need("launch-ledger/consumed" in nix, "tmpfiles rules must declare the launch-ledger consumed StateDir")
    need("launch-ledger/expired" in nix, "tmpfiles rules must declare the launch-ledger expired StateDir")

    transport = open(os.path.join(ROOT, "scripts", "ai", "lib", "revocation_epoch_transport.py")).read()
    need("def build_launch_handler(" in transport, "the C6a launch handler must exist")
    need("def build_launch_deny_all_handler(" not in transport, "the C6-S deny-all stub must be RETIRED (replaced by C6a)")
    need("AQ_REVOCATION_LAUNCH_TEG_UID" in transport, "the launch handler must read AQ_REVOCATION_LAUNCH_TEG_UID")

    lib_src = open(os.path.join(ROOT, "scripts", "ai", "lib", "revocation_epoch.py")).read()
    need("def authorize_launch(" in lib_src, "revocation_epoch.py must define authorize_launch")
    need("def consume_launch(" in lib_src, "revocation_epoch.py must define consume_launch")
    need("def recover_launch_ledger(" in lib_src, "revocation_epoch.py must define recover_launch_ledger")

    api = open(os.path.join(ROOT, "dashboard", "backend", "api", "routes", "aistack.py")).read()
    need('result["revocation_launch_authorization"]' in api, "aistack.py must expose result[\"revocation_launch_authorization\"]")
    need(
        '"teg_peer_check_enforced"' in api and '"ledger_durable"' in api,
        "the revocation_launch_authorization section must report ledger_durable + teg_peer_check_enforced",
    )
    js = open(os.path.join(ROOT, "assets", "dashboard.js")).read()
    need("revocation_launch_authorization" in js, "dashboard.js must read the revocation_launch_authorization section")
    need("teg_peer_check_enforced" in js, "dashboard.js must render the TEG peer-check row")

    reg = json.load(open(os.path.join(ROOT, "config", "validation-check-registry.json")))
    ids = {c.get("id") for c in _iter_dicts(reg) if isinstance(c, dict) and c.get("id")}
    need("c6a-authorize-launch-coverage" in ids, "validation-check-registry.json must register c6a-authorize-launch-coverage")


# --------------------------------------------------------------------------
# 2. Live serve_multi() exercise on temp-dir sockets
# --------------------------------------------------------------------------


class _LaunchHarness:
    """Binds `revocation_epoch_transport.serve_multi()` to two real UDS's under a fresh temp
    dir, on a background thread — mirrors `test-revocation-launch-socket-topology.py`'s
    `_MultiHarness`."""

    def __init__(self, initial_epoch: str = "0", teg_uid: str = "") -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.epoch_path = root / "epoch"
        self.epoch_path.write_text(initial_epoch, encoding="utf-8")
        self.ledger_dir = root / "ledger"
        self.owner_keys_path = root / "owner-keys.json"
        self.owner_keys_path.write_text(json.dumps({"schema_version": "1", "revision": 1, "keys": []}), encoding="utf-8")
        self.control_path = str(root / "control.sock")
        self.launch_path = str(root / "launch.sock")
        self.teg_uid = teg_uid
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        os.environ["AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH"] = str(self.owner_keys_path)
        os.environ["AQ_REVOCATION_EPOCH_EPOCH_PATH"] = str(self.epoch_path)
        os.environ["AQ_REVOCATION_EPOCH_LEDGER_DIR"] = str(self.ledger_dir)
        if self.teg_uid:
            os.environ["AQ_REVOCATION_LAUNCH_TEG_UID"] = self.teg_uid
        else:
            os.environ.pop("AQ_REVOCATION_LAUNCH_TEG_UID", None)
        control_handler = ret.build_env_handler()
        launch_handler = ret.build_launch_handler()
        self._thread = threading.Thread(
            target=ret.serve_multi,
            args=(self.control_path, control_handler, self.launch_path, launch_handler),
            daemon=True,
        )
        self._thread.start()
        deadline = time.time() + 5.0
        while not (os.path.exists(self.control_path) and os.path.exists(self.launch_path)):
            if time.time() > deadline:
                raise RuntimeError("serve_multi() sockets never appeared")
            time.sleep(0.02)

    def send_control(self, request: dict) -> dict:
        return ret.send_request(self.control_path, request)

    def send_launch(self, request: dict) -> dict:
        return ret.send_request(self.launch_path, request)

    def cleanup(self) -> None:
        self.tmp.cleanup()


_BASE_LAUNCH_FIELDS = {
    "context_digest": "ab12",
    "task_id": "task-1",
    "task_revision": 1,
    "gateway_instance": "gw-1",
}


def _check_fail_closed_empty_teg_uid() -> None:
    harness = _LaunchHarness(initial_epoch="0", teg_uid="")
    try:
        harness.start()
        resp = harness.send_launch(dict(_BASE_LAUNCH_FIELDS, op="authorize_launch"))
        need(resp.get("ok") is False and resp.get("reason") == re_lib.DENY_NOT_TEG_PEER,
             "empty AQ_REVOCATION_LAUNCH_TEG_UID must deny authorize_launch with DENY_NOT_TEG_PEER")
        resp2 = harness.send_launch({"op": "consume_launch", "nonce": "ab" * 32, **_BASE_LAUNCH_FIELDS, "epoch": 0})
        need(resp2.get("ok") is False and resp2.get("reason") == re_lib.DENY_NOT_TEG_PEER,
             "empty AQ_REVOCATION_LAUNCH_TEG_UID must deny consume_launch with DENY_NOT_TEG_PEER")
    finally:
        harness.cleanup()


def _check_live_issue_consume_exactly_once() -> None:
    harness = _LaunchHarness(initial_epoch="9", teg_uid=str(os.getuid()))
    try:
        harness.start()

        # Reachable ONLY over the launch socket — the control socket never dispatches it.
        control_resp = harness.send_control(dict(_BASE_LAUNCH_FIELDS, op="authorize_launch"))
        need(control_resp.get("ok") is False and control_resp.get("reason") == ret.DENY_MALFORMED_BUMP,
             "authorize_launch on the CONTROL socket must fall through to bump handling and deny malformed-bump, never dispatch the launch op")

        issue_resp = harness.send_launch(dict(_BASE_LAUNCH_FIELDS, op="authorize_launch"))
        need(issue_resp.get("ok") is True, "authorize_launch over the launch socket with a matching TEG uid must succeed")
        token = issue_resp.get("token") or {}
        need(token.get("epoch") == 9, "issued token must bind the current epoch (9)")
        need(token.get("deadline_ms", 999) <= 250, "issued token deadline_ms must be <= 250")
        nonce = token.get("nonce")
        need(isinstance(nonce, str) and len(nonce) == 64, "issued token nonce must be a 256-bit hex string")

        consume_req = {"op": "consume_launch", "nonce": nonce, "epoch": token.get("epoch"), **_BASE_LAUNCH_FIELDS}
        consume1 = harness.send_launch(consume_req)
        need(consume1.get("ok") is True, "the first consume_launch of a freshly-issued token must succeed")

        consume2 = harness.send_launch(consume_req)
        need(consume2.get("ok") is False and consume2.get("reason") == re_lib.DENY_LAUNCH_ALREADY_CONSUMED,
             "a second consume_launch of the SAME token must deny DENY_LAUNCH_ALREADY_CONSUMED (the duplicate-deny)")

        # Non-TEG peer: send from a hand-crafted connection is not controllable over
        # send_request's own uid, so exercise it directly through the library-level
        # handler instead (same handler instance the socket serves).
        other_peer = (os.getpid(), os.getuid() + 1, os.getgid())
        direct_handler = ret.build_launch_handler()
        non_teg_resp = direct_handler(dict(_BASE_LAUNCH_FIELDS, op="authorize_launch"), other_peer)
        need(non_teg_resp.get("ok") is False and non_teg_resp.get("reason") == re_lib.DENY_NOT_TEG_PEER,
             "a non-TEG peer uid must deny DENY_NOT_TEG_PEER")
    finally:
        harness.cleanup()


def _check_live_expired_denies() -> None:
    harness = _LaunchHarness(initial_epoch="0", teg_uid=str(os.getuid()))
    try:
        harness.start()
        issue_resp = harness.send_launch(dict(_BASE_LAUNCH_FIELDS, op="authorize_launch"))
        token = issue_resp["token"]
        time.sleep((token["deadline_ms"] / 1000.0) + 0.15)
        consume_resp = harness.send_launch({"op": "consume_launch", "nonce": token["nonce"], "epoch": token["epoch"], **_BASE_LAUNCH_FIELDS})
        need(consume_resp.get("ok") is False and consume_resp.get("reason") == re_lib.DENY_LAUNCH_EXPIRED,
             "a consume attempted after the <=250ms deadline must deny DENY_LAUNCH_EXPIRED")
    finally:
        harness.cleanup()


def _check_live_epoch_superseded_denies() -> None:
    harness = _LaunchHarness(initial_epoch="4", teg_uid=str(os.getuid()))
    try:
        harness.start()
        issue_resp = harness.send_launch(dict(_BASE_LAUNCH_FIELDS, op="authorize_launch"))
        token = issue_resp["token"]
        need(token.get("epoch") == 4, "issued token must bind epoch 4 before the simulated bump")

        # Simulate an epoch bump landing after issuance (design §4's "bump after issuance
        # is ordered strictly after the declared launch point") — direct file write is
        # sufficient here since consume_launch's supersession check only re-reads
        # read_epoch(), agnostic to how the epoch advanced.
        harness.epoch_path.write_text("5\n", encoding="utf-8")

        consume_resp = harness.send_launch({"op": "consume_launch", "nonce": token["nonce"], "epoch": token["epoch"], **_BASE_LAUNCH_FIELDS})
        need(consume_resp.get("ok") is False and consume_resp.get("reason") == re_lib.DENY_LAUNCH_EPOCH_SUPERSEDED,
             "a consume of a token whose epoch was superseded by a later bump must deny DENY_LAUNCH_EPOCH_SUPERSEDED")
    finally:
        harness.cleanup()


def main() -> int:
    _check_static()
    _check_fail_closed_empty_teg_uid()
    _check_live_issue_consume_exactly_once()
    _check_live_expired_denies()
    _check_live_epoch_superseded_denies()

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"\n{len(fails)} assertion(s) failed")
        return 1
    print("PASS: C6a authorize_launch + single-use launch-token consume (issue->consume->duplicate-deny->non-TEG-deny->expired-deny->epoch-superseded-deny)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
