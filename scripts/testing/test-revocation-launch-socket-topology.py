#!/usr/bin/env python3
"""Foundation C C6-S — dedicated TEG-only launch socket + principal topology (mechanism B).

Two parts, mirroring the ALA/C2-SCI Service-Coverage tests (`test-ala-service-coverage.py`,
`test-c2-sci-service-coverage.py`) plus a LIVE integration exercise (mirroring
`test-revocation-epoch-authority.py`'s `_ServerHarness`, which binds `serve()` on a real
temp-dir `AF_UNIX` socket):

1. Static cross-surface assertions — the Nix module declares the launch socket/group/env
   correctly, `enable` stays false, the dashboard API/JS surface the topology, and the
   registry registers this check (offline, no service, no network).
2. A live `serve_multi()` exercise on temp-dir sockets: BOTH sockets bind and accept, the
   control socket's `read-epoch`/`bump` behavior is byte-identical to `serve()` (byte-parity),
   and the launch socket denies every request while the TEG peer is unresolved — never a crash,
   never a distinguishing response. (C6a replaced the original deny-all stub with the real
   `authorize_launch`/`consume_launch` ops, gated by the op-specific TEG SO_PEERCRED check this
   topology test's static section still requires; the C6a-specific issue->consume->duplicate-
   deny exercise lives in `test-c6a-authorize-launch-service-coverage.py`.)
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
    # env-contract: the two new canonicals, no capability flag
    import yaml

    ec = yaml.safe_load(open(os.path.join(ROOT, "config", "env-contract.yaml")))
    entries = ec.get("environment_variables") or ec.get("variables") or ec.get("env") or []
    if not entries:
        entries = list(_iter_dicts(ec))
    launch_sock_env = next((e for e in entries if isinstance(e, dict) and e.get("canonical") == "AQ_REVOCATION_LAUNCH_SOCKET_PATH"), None)
    need(launch_sock_env is not None, "env-contract must declare AQ_REVOCATION_LAUNCH_SOCKET_PATH")
    need(
        launch_sock_env is None or launch_sock_env.get("default") == "/run/aq-revocation-epoch-authority/launch.sock",
        "AQ_REVOCATION_LAUNCH_SOCKET_PATH must default to the shared runtime dir's launch.sock",
    )
    launch_grp_env = next((e for e in entries if isinstance(e, dict) and e.get("canonical") == "AQ_REVOCATION_LAUNCH_CLIENT_GROUP"), None)
    need(launch_grp_env is not None, "env-contract must declare AQ_REVOCATION_LAUNCH_CLIENT_GROUP")
    need(
        launch_grp_env is None or launch_grp_env.get("default") == "aq-revocation-launch-clients",
        "AQ_REVOCATION_LAUNCH_CLIENT_GROUP must default to aq-revocation-launch-clients",
    )
    control_sock_env = next((e for e in entries if isinstance(e, dict) and e.get("canonical") == "AQ_REVOCATION_EPOCH_SOCKET_PATH"), None)
    need(control_sock_env is not None, "env-contract must still declare the unchanged AQ_REVOCATION_EPOCH_SOCKET_PATH")

    # Nix module: launch socket / group / membership topology, enable=false preserved
    nix = open(os.path.join(ROOT, "nix", "modules", "services", "revocation-epoch-authority.nix")).read()
    need("default = false;" in nix, "revocation-epoch-authority.nix must default enable=false")
    need("launchSocketPath" in nix, "module must declare a launchSocketPath option")
    need('users.groups.aq-revocation-launch-clients = {};' in nix, "the launch-client group must be declared EMPTY (no inline members)")
    need(
        'extraGroups = ["aq-revocation-epoch-clients" "aq-revocation-launch-clients"];' in nix,
        "the authority user must join BOTH client groups (chgrp-only role on the launch group)",
    )
    need(
        'users.users.${primaryUser}.extraGroups = mkAfter ["aq-revocation-epoch-clients"];' in nix,
        "the owner/primaryUser line must be UNCHANGED — control-socket group ONLY, never the launch group",
    )
    need("AQ_REVOCATION_LAUNCH_SOCKET_PATH=${cfg.launchSocketPath}" in nix, "unit Environment must wire the launch socket path")
    need("AQ_REVOCATION_LAUNCH_CLIENT_GROUP=aq-revocation-launch-clients" in nix, "unit Environment must wire the launch client group")
    need("AF_UNIX" in nix, "service must stay AF_UNIX-only (no network)")

    # Transport: serve() unmodified in spirit (still present, still callable), serve_multi +
    # deny-all stub added, __main__ switched to serve_multi
    transport = open(os.path.join(ROOT, "scripts", "ai", "lib", "revocation_epoch_transport.py")).read()
    need("def serve(" in transport, "serve() must still exist (unmodified, byte-parity)")
    need("def serve_multi(" in transport, "serve_multi() must exist as a sibling of serve()")
    need("def build_launch_handler(" in transport, "the C6a launch handler (authorize_launch/consume_launch) must exist for the launch socket")
    need("serve_multi(" in transport.split("if __name__")[-1], "__main__ must call serve_multi(), not serve(), so both sockets bind")
    need("AQ_REVOCATION_LAUNCH_SOCKET_PATH" in transport.split("if __name__")[-1], "__main__ must read AQ_REVOCATION_LAUNCH_SOCKET_PATH")

    # Dashboard API + JS
    api = open(os.path.join(ROOT, "dashboard", "backend", "api", "routes", "aistack.py")).read()
    need('result["revocation_epoch_authority"]' in api, "aistack.py must expose result[\"revocation_epoch_authority\"]")
    need('"launch_group_teg_only"' in api and '"control_socket"' in api and '"launch_socket"' in api,
         "the revocation_epoch_authority section must report control_socket + launch_socket + launch_group_teg_only")
    js = open(os.path.join(ROOT, "assets", "dashboard.js")).read()
    need("revocation_epoch_authority" in js, "dashboard.js must read the revocation_epoch_authority section")
    need("launch_group_teg_only" in js, "dashboard.js must render the launch_group_teg_only row")

    # focused-ci registry
    reg = json.load(open(os.path.join(ROOT, "config", "validation-check-registry.json")))
    ids = {c.get("id") for c in _iter_dicts(reg) if isinstance(c, dict) and c.get("id")}
    need("revocation-launch-socket-topology" in ids, "validation-check-registry.json must register revocation-launch-socket-topology")


# --------------------------------------------------------------------------
# 2. Live serve_multi() exercise on temp-dir sockets
# --------------------------------------------------------------------------


class _MultiHarness:
    """Binds `revocation_epoch_transport.serve_multi()` to two real UDS's under a fresh temp
    dir, on a background thread — mirrors `test-revocation-epoch-authority.py`'s
    `_ServerHarness`, extended to both sockets."""

    def __init__(self, initial_epoch: str = "0") -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.epoch_path = root / "epoch"
        self.epoch_path.write_text(initial_epoch, encoding="utf-8")
        self.ledger_dir = root / "ledger"
        self.owner_keys_path = root / "owner-keys.json"
        self.owner_keys_path.write_text(json.dumps({"schema_version": "1", "revision": 1, "keys": []}), encoding="utf-8")
        self.control_path = str(root / "control.sock")
        self.launch_path = str(root / "launch.sock")
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        os.environ["AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH"] = str(self.owner_keys_path)
        os.environ["AQ_REVOCATION_EPOCH_EPOCH_PATH"] = str(self.epoch_path)
        os.environ["AQ_REVOCATION_EPOCH_LEDGER_DIR"] = str(self.ledger_dir)
        # No TEG uid provisioned in this topology test (C6b's concern) --
        # the launch op must stay unreachable regardless of ambient env
        # pollution from another test in the same process.
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


def _check_live() -> None:
    harness = _MultiHarness(initial_epoch="7")
    try:
        harness.start()

        need(os.path.exists(harness.control_path), "control socket must exist after serve_multi() starts")
        need(os.path.exists(harness.launch_path), "launch socket must exist after serve_multi() starts")

        control_mode = oct(os.stat(harness.control_path).st_mode & 0o777)
        launch_mode = oct(os.stat(harness.launch_path).st_mode & 0o777)
        need(control_mode == "0o660", f"control socket must be 0660, got {control_mode}")
        need(launch_mode == "0o660", f"launch socket must be 0660, got {launch_mode}")

        # Control socket byte-parity: read-epoch behaves exactly as serve() would.
        read_resp = harness.send_control({"op": "read-epoch"})
        need(read_resp.get("ok") is True and read_resp.get("epoch") == 7,
             "serve_multi()'s control listener must answer read-epoch identically to serve()")

        # Malformed control request still typed-denies (byte-parity with serve()'s framing).
        bad_resp = harness.send_control({"not_a_bump_field": True})
        need(bad_resp.get("ok") is False and bad_resp.get("reason") == ret.DENY_MALFORMED_BUMP,
             "serve_multi()'s control listener must deny malformed requests identically to serve()")

        # Launch socket: EVERY well-formed request denies while the TEG peer is unresolved
        # (empty AQ_REVOCATION_LAUNCH_TEG_UID, C6a design §2.3 item 3 — fail-closed until C6b) —
        # no reachable op for this non-TEG test peer, same typed reason for any request shape.
        launch_resp1 = harness.send_launch({"op": "authorize_launch", "context_digest": "ab", "task_id": "t", "task_revision": 1, "gateway_instance": "gw"})
        need(launch_resp1.get("ok") is False and launch_resp1.get("reason") == re_lib.DENY_NOT_TEG_PEER,
             "launch socket must deny an authorize_launch-shaped request with the TEG-peer-check reason while unresolved")
        launch_resp2 = harness.send_launch({"anything": "else"})
        need(launch_resp2.get("ok") is False and launch_resp2.get("reason") == re_lib.DENY_NOT_TEG_PEER,
             "launch socket must deny ANY well-formed request with the SAME typed reason (no distinguishing response)")

        # Garbage bytes on the launch socket must not crash the shared accept loop — the
        # control socket keeps serving right after.
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(harness.launch_path)
        sock.sendall(b"\xff\xfe not valid json\n")
        sock.close()
        read_resp2 = harness.send_control({"op": "read-epoch"})
        need(read_resp2.get("ok") is True and read_resp2.get("epoch") == 7,
             "serve_multi()'s shared accept loop must survive a bad launch-socket connection and keep serving the control socket")
    finally:
        harness.cleanup()


def main() -> int:
    _check_static()
    _check_live()

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"\n{len(fails)} assertion(s) failed")
        return 1
    print("PASS: revocation launch-socket topology (launch.sock + empty launch group + serve_multi + deny-all stub + control-socket byte-parity)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
