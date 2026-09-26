#!/usr/bin/env python3
"""Foundation C C6c — the callable offline owner-key submission path
(`aq-epoch-bump submit --signed <file> --socket <path>`). Cross-surface
Service-Coverage test, mirroring `test-c6a-authorize-launch-service-coverage.py`
/ `test-c2-sci-service-coverage.py`.

Two parts:

1. Static cross-surface assertions — the CLI's `submit` subparser exposes
   `--socket`, the socket-delivery branch of `cmd_submit` contains neither
   `_load_owner_key` nor `apply_bump`/`DurableReplayLedger` (no host key, no
   in-process 0700 write — those stay confined to the landed
   fallback/`bump` paths), `cmd_bump` carries the DEPRECATED note, the
   dashboard API/JS surface `owner_epoch_bump_lever`, and the registry
   registers this check (offline, no service, no network).
2. A LIVE `revocation_epoch_transport.serve()` exercise on a temp-dir control
   socket (mirrors `test-c6a-...`'s `_LaunchHarness`): a fixture allowlist
   with one ACTIVE owner key + one REVOKED key. A freshly-built, offline-
   signed bump delivered via the real `aq-epoch-bump submit --signed
   --socket` subprocess is ACCEPTED and advances the epoch by exactly +1;
   resubmitting the IDENTICAL signed file is deterministic (never a second
   +1); a bad-signature doc is rejected; a revoked-key doc is rejected; an
   unknown-key doc is rejected; and the submit path never creates the
   `--ledger-dir`/`--epoch-path`/`--owner-keys` paths it is also given
   (proving they are genuinely unused on the socket-delivery branch — no
   owner-UID write to what would be the authority's 0700 StateDirectory).
   Also unit-exercises the dashboard lever's four-state decision matrix
   directly (`_owner_epoch_bump_lever_state`), including the
   active-key-but-authority-unreachable -> `degraded(authority-unreachable)`
   case the binding review's Finding 1 requires, and the live
   `_owner_epoch_bump_probe_authority` read-epoch probe against the same
   fixture socket.
"""
from __future__ import annotations

import importlib.util
import json
import os
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
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

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
    cli_path = os.path.join(ROOT, "scripts", "ai", "aq-epoch-bump")
    cli = open(cli_path).read()
    need('"submit"' in cli, "aq-epoch-bump must declare the submit subcommand")
    need("--socket" in cli, "the submit subparser must expose --socket")
    need("import os" in cli.splitlines()[0:60].__str__() or "\nimport os\n" in cli,
         "aq-epoch-bump must import os at module level (the landed cmd_bump NameError fix)")
    need("DEPRECATED" in cli, "cmd_bump must carry an explicit deprecation note steering owners to submit --signed --socket")

    # The socket-delivery branch of cmd_submit must read NO host private key and
    # perform NO in-process apply_bump/ledger write — isolate that branch's own
    # source slice (between "if args.socket:" and the landed-path comment) and
    # assert the absence of both.
    start = cli.index("def cmd_submit(")
    end = cli.index("def _load_owner_key(")
    submit_fn = cli[start:end]
    branch_start = submit_fn.index("if args.socket:")
    branch_end = submit_fn.index("# Landed in-process path")
    socket_branch = submit_fn[branch_start:branch_end]
    # Call-shaped substrings (trailing "(") so this cannot false-positive on the
    # branch's own explanatory comment, which names these functions in prose.
    need("_load_owner_key(" not in socket_branch, "the --socket delivery branch of cmd_submit must not call _load_owner_key (no host private key)")
    need("apply_bump(" not in socket_branch, "the --socket delivery branch of cmd_submit must not call apply_bump in-process")
    need("DurableReplayLedger(" not in socket_branch, "the --socket delivery branch of cmd_submit must not construct a DurableReplayLedger (no owner-UID 0700 write)")
    need("send_request(" in socket_branch, "the --socket delivery branch must deliver via revocation_epoch_transport.send_request")

    api = open(os.path.join(ROOT, "dashboard", "backend", "api", "routes", "aistack.py")).read()
    need('result["owner_epoch_bump_lever"]' in api, "aistack.py must expose result[\"owner_epoch_bump_lever\"]")
    for state in ("operational", "degraded(authority-unreachable)", "none(revoked-only)", "unavailable"):
        need(f'"{state}"' in api, f"owner_epoch_bump_lever must declare the {state} state")
    need("_owner_epoch_bump_probe_authority" in api, "aistack.py must define the live read-epoch reachability probe")
    need("_owner_epoch_bump_lever_state" in api, "aistack.py must define the pure four-state decision function")

    js = open(os.path.join(ROOT, "assets", "dashboard.js")).read()
    need("owner_epoch_bump_lever" in js, "dashboard.js must read the owner_epoch_bump_lever section")

    reg = json.load(open(os.path.join(ROOT, "config", "validation-check-registry.json")))
    ids = {c.get("id") for c in _iter_dicts(reg) if isinstance(c, dict) and c.get("id")}
    need("c6c-owner-submission-coverage" in ids, "validation-check-registry.json must register c6c-owner-submission-coverage")

    # The owner-keys allowlist file itself must remain untouched (dormant baseline).
    keys_doc = json.load(open(os.path.join(ROOT, "config", "aqos", "c6-owner-public-keys.json")))
    need(keys_doc.get("revision") == 4, "the live c6-owner-public-keys.json revision must remain untouched at 4")
    live_keys = keys_doc.get("keys") or []
    need(all(k.get("status") == "revoked" for k in live_keys if isinstance(k, dict)),
         "the live allowlist must remain all-revoked (dormant; P-F4 is a separate later owner act)")


# --------------------------------------------------------------------------
# 2. Live control-socket exercise + dashboard-lever decision-matrix unit test
# --------------------------------------------------------------------------


class _ControlHarness:
    """Binds `revocation_epoch_transport.serve()` to a real control-socket UDS
    under a fresh temp dir, on a background thread."""

    def __init__(self, active_pub_hex: str, revoked_pub_hex: str, initial_epoch: str = "0") -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.epoch_path = root / "epoch"
        self.epoch_path.write_text(initial_epoch, encoding="utf-8")
        self.ledger_dir = root / "ledger"
        self.owner_keys_path = root / "owner-keys.json"
        self.owner_keys_path.write_text(
            json.dumps({
                "schema_version": "1",
                "revision": 1,
                "keys": [
                    {
                        "key_id": "fixture-active-2026",
                        "ed25519_public_key": active_pub_hex,
                        "status": "active",
                        "not_before": None,
                        "not_after": None,
                    },
                    {
                        "key_id": "fixture-revoked-2026",
                        "ed25519_public_key": revoked_pub_hex,
                        "status": "revoked",
                        "not_before": None,
                        "not_after": None,
                    },
                ],
            }),
            encoding="utf-8",
        )
        self.control_path = str(root / "control.sock")
        self.root = root
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        os.environ["AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH"] = str(self.owner_keys_path)
        os.environ["AQ_REVOCATION_EPOCH_EPOCH_PATH"] = str(self.epoch_path)
        os.environ["AQ_REVOCATION_EPOCH_LEDGER_DIR"] = str(self.ledger_dir)
        handler = ret.build_env_handler()
        self._thread = threading.Thread(target=ret.serve, args=(self.control_path, handler), daemon=True)
        self._thread.start()
        deadline = time.time() + 5.0
        while not os.path.exists(self.control_path):
            if time.time() > deadline:
                raise RuntimeError("serve() control socket never appeared")
            time.sleep(0.02)

    def cleanup(self) -> None:
        self.tmp.cleanup()


def _build_signed_bump(private_key: Ed25519PrivateKey, actor_key_id: str, expected_epoch: int, request_id: str | None = None) -> dict:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    rid = request_id or f"c6c-coverage::{actor_key_id}::{expected_epoch}::{now.timestamp()}"
    doc = {
        "schema_version": re_lib.BUMP_SCHEMA_VERSION,
        "request_id": rid,
        "idempotency_key": rid,
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(seconds=3600)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor_key_id": actor_key_id,
        "expected_epoch": expected_epoch,
        "reason_code": "incident",
        "scope": re_lib.SCOPE_FLEET,
        "signature": "",
    }
    signature = private_key.sign(re_lib.canonical_bump_payload(doc))
    doc["signature"] = signature.hex()
    return doc


def _run_submit(signed_path: str, socket_path: str, root: Path) -> tuple[int, dict]:
    import subprocess

    never_ledger = root / "never-created-ledger"
    never_epoch = root / "never-created-epoch"
    never_keys = root / "never-created-keys.json"
    proc = subprocess.run(
        [
            "python3", os.path.join(ROOT, "scripts", "ai", "aq-epoch-bump"),
            "submit", "--signed", signed_path, "--socket", socket_path,
            "--ledger-dir", str(never_ledger),
            "--epoch-path", str(never_epoch),
            "--owner-keys", str(never_keys),
        ],
        capture_output=True, text=True, timeout=15, check=False,
    )
    need(not never_ledger.exists(), "submit --socket must never create --ledger-dir (proves the in-process path is unused)")
    need(not never_epoch.exists(), "submit --socket must never create --epoch-path (proves the in-process path is unused)")
    need(not never_keys.exists(), "submit --socket must never create --owner-keys (proves the in-process path is unused)")
    try:
        resp = json.loads(proc.stdout)
    except json.JSONDecodeError:
        resp = {"ok": False, "reason": f"non-json-output:{proc.stdout!r}:{proc.stderr!r}"}
    return proc.returncode, resp


def _check_live_accept_resubmit_and_denies() -> None:
    active_priv = Ed25519PrivateKey.generate()
    active_pub_hex = active_priv.public_key().public_bytes_raw().hex()
    revoked_priv = Ed25519PrivateKey.generate()
    revoked_pub_hex = revoked_priv.public_key().public_bytes_raw().hex()

    harness = _ControlHarness(active_pub_hex, revoked_pub_hex, initial_epoch="0")
    try:
        harness.start()
        root = harness.root

        # -- Accept: a fresh, offline-signed bump from the active key advances epoch 0 -> 1.
        good_doc = _build_signed_bump(active_priv, "fixture-active-2026", expected_epoch=0, request_id="c6c-accept-1")
        signed_path = root / "signed-accept.json"
        signed_path.write_text(json.dumps(good_doc), encoding="utf-8")
        code, resp = _run_submit(str(signed_path), harness.control_path, root)
        need(code == 0 and resp.get("ok") is True, f"a valid signed bump from an active key must be accepted (got exit={code} resp={resp})")
        need(resp.get("receipt", {}).get("new_epoch") == 1, "the accepted bump must advance the epoch to 1")
        need(harness.epoch_path.read_text().strip() == "1", "the durable epoch file must read 1 after the accepted bump")

        # -- Resubmit: the IDENTICAL signed file again must be deterministic and must
        #    NEVER produce a second +1. Once the bump has cleanly committed, the frozen
        #    `expected_epoch` in the identical bytes (old_epoch) is now stale relative to
        #    the durable current epoch (new_epoch) — apply_bump's stateless
        #    optimistic-concurrency check (§3.1 step, BEFORE the journal/index dedup)
        #    denies this deterministically as `DENY_EPOCH_MISMATCH` every time, which is
        #    itself the "never a double-bump" guarantee for a resubmit of an
        #    already-fully-committed transaction (the journal/index dedup path this
        #    design's §3 describes governs the CRASH/in-flight-retry window instead —
        #    exercised by C6d's own `test-revocation-epoch.py`, not re-tested here).
        code2, resp2 = _run_submit(str(signed_path), harness.control_path, root)
        need(resp2.get("ok") is False and resp2.get("reason") == re_lib.DENY_EPOCH_MISMATCH,
             f"resubmitting an already-committed identical signed doc must deterministically deny DENY_EPOCH_MISMATCH, never a second bump (got exit={code2} resp={resp2})")
        need(harness.epoch_path.read_text().strip() == "1", "the durable epoch file must STILL read 1 after the resubmit (never a double-bump)")

        # -- Bad signature: flip the last hex character of the signature.
        bad_doc = _build_signed_bump(active_priv, "fixture-active-2026", expected_epoch=1, request_id="c6c-badsig-1")
        sig = bad_doc["signature"]
        flipped = ("0" if sig[-1] != "0" else "1")
        bad_doc["signature"] = sig[:-1] + flipped
        bad_path = root / "signed-badsig.json"
        bad_path.write_text(json.dumps(bad_doc), encoding="utf-8")
        code3, resp3 = _run_submit(str(bad_path), harness.control_path, root)
        need(resp3.get("ok") is False and resp3.get("reason") == re_lib.DENY_BAD_SIGNATURE,
             f"a tampered signature must deny DENY_BAD_SIGNATURE (got {resp3})")

        # -- Revoked key: actor_key_id matches the revoked allowlist entry.
        revoked_doc = _build_signed_bump(revoked_priv, "fixture-revoked-2026", expected_epoch=1, request_id="c6c-revoked-1")
        revoked_path = root / "signed-revoked.json"
        revoked_path.write_text(json.dumps(revoked_doc), encoding="utf-8")
        code4, resp4 = _run_submit(str(revoked_path), harness.control_path, root)
        need(resp4.get("ok") is False and resp4.get("reason") == re_lib.DENY_KEY_NOT_ACTIVE,
             f"a revoked-key document must deny DENY_KEY_NOT_ACTIVE (got {resp4})")

        # -- Unknown key: actor_key_id absent from the allowlist entirely.
        unknown_doc = _build_signed_bump(active_priv, "fixture-unknown-key-id", expected_epoch=1, request_id="c6c-unknown-1")
        unknown_path = root / "signed-unknown.json"
        unknown_path.write_text(json.dumps(unknown_doc), encoding="utf-8")
        code5, resp5 = _run_submit(str(unknown_path), harness.control_path, root)
        need(resp5.get("ok") is False and resp5.get("reason") == re_lib.DENY_UNKNOWN_KEY,
             f"an unknown actor_key_id must deny DENY_UNKNOWN_KEY (got {resp5})")
    finally:
        harness.cleanup()


def _load_aistack_module():
    # aistack.py uses package-relative imports (`from ..config import ...`); the live
    # service runs it as `api.routes.aistack` with `WorkingDirectory=dashboard/backend`
    # (`nix/modules/services/command-center-dashboard.nix`, `uvicorn api.main:app`) — mirror
    # that resolution exactly rather than loading it as a standalone file.
    backend_dir = os.path.join(ROOT, "dashboard", "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    return importlib.import_module("api.routes.aistack")


def _check_dashboard_lever_decision_matrix() -> None:
    aistack = _load_aistack_module()

    need(aistack._owner_epoch_bump_lever_state(False, None, True, True) == "unavailable",
         "an unreadable allowlist must map to unavailable regardless of reachability")
    need(aistack._owner_epoch_bump_lever_state(True, 0, True, True) == "none(revoked-only)",
         "zero active keys must map to none(revoked-only) regardless of reachability")
    need(aistack._owner_epoch_bump_lever_state(True, 1, True, False) == "degraded(authority-unreachable)",
         "an active key with an UNREACHABLE authority must map to degraded(authority-unreachable), never operational (binding-review Finding 1)")
    need(aistack._owner_epoch_bump_lever_state(True, 1, True, True) == "operational",
         "an active key with a REACHABLE authority and the verb present must map to operational")
    need(aistack._owner_epoch_bump_lever_state(True, 1, False, True) == "unavailable",
         "an absent submit verb must map to unavailable even with an active key and reachable authority")

    # Live-probe the same reachability helper the endpoint uses, against a real fixture
    # control socket — proves the probe genuinely round-trips read-epoch, not a stub.
    active_priv = Ed25519PrivateKey.generate()
    active_pub_hex = active_priv.public_key().public_bytes_raw().hex()
    harness = _ControlHarness(active_pub_hex, active_pub_hex, initial_epoch="7")
    try:
        harness.start()
        need(aistack._owner_epoch_bump_probe_authority(harness.control_path) is True,
             "the live read-epoch probe must succeed against a running fixture authority")
    finally:
        harness.cleanup()
    need(aistack._owner_epoch_bump_probe_authority(str(harness.tmp.name) + "/gone.sock") is False,
         "the live read-epoch probe must return False against an absent/unreachable socket")


def main() -> int:
    _check_static()
    _check_live_accept_resubmit_and_denies()
    _check_dashboard_lever_decision_matrix()

    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        print(f"\n{len(fails)} assertion(s) failed")
        return 1
    print("PASS: C6c owner epoch-bump submission (signed-submit accept/resubmit-deterministic/bad-sig-deny/revoked-deny/unknown-deny, no host key, no 0700 write, dashboard lever four-state matrix)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
