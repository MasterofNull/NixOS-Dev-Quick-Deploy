#!/usr/bin/env python3
"""Offline hermetic tests for the C2 scheduler-context issuer's B2.5 durable single-use
ledger (`scheduler_context_issuer.DurableSingleUseLedger`).

No network, no service, no `/run/secrets`. Proves the three properties the B2.5 subslice
exists to guarantee (see the class docstring in `scripts/ai/lib/scheduler_context_issuer.py`):

  1. DURABILITY: a key recorded by one `DurableSingleUseLedger` instance is still
     "already used" to a SECOND, independently constructed instance pointed at the SAME
     `ledger_dir` — i.e. a process restart never forgets a consumed `{lease_id,
     grant_digest}` (the exact gap `InMemorySingleUseLedger` leaves open).
  2. ATOMICITY under concurrency: many callers (threads AND separate OS processes) racing
     `check_and_record` on the IDENTICAL key must yield EXACTLY ONE `True` — never zero,
     never more than one (a second `True` would be a double-mint = fail-open).
  3. FAIL-CLOSED on a genuine storage fault: an unwritable ledger dir raises out of
     `check_and_record` (never silently returns `True`/`False` as if nothing were wrong) —
     `mint_scheduler_context` turns any raised exception into `DENY_LEDGER_UNAVAILABLE`.

Also covers: independent keys don't collide; `stats()` counts; and one end-to-end
`mint_scheduler_context` call wired to a real `DurableSingleUseLedger` (not just the
bare ledger contract) to prove the seam in `scheduler_context_transport.build_env_handler`
composes correctly.
"""
from __future__ import annotations

import multiprocessing
import os
import shutil
import stat
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB_DIR = os.path.join(REPO_ROOT, "scripts", "ai", "lib")
sys.path.insert(0, LIB_DIR)
if os.environ.get("AQ_CANDIDATE_LIB_DIR"):
    sys.path.insert(0, os.environ["AQ_CANDIDATE_LIB_DIR"])

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

import capability_lease as cl  # noqa: E402
import scheduler_context_issuer as sci  # noqa: E402

passed = 0
failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")


# --------------------------------------------------------------------------
# 1) Basic record + in-instance replay deny.
# --------------------------------------------------------------------------


def test_basic_record_and_replay() -> None:
    tmp = tempfile.mkdtemp(prefix="sci-ledger-basic-")
    try:
        ledger_dir = os.path.join(tmp, "ledger")
        ledger = sci.DurableSingleUseLedger(ledger_dir)
        key = ("lease-a", "digest-a")
        check("first record -> True", ledger.check_and_record(key) is True)
        check("immediate replay (same instance) -> False", ledger.check_and_record(key) is False)
        check("stats: recorded == 1 after one new key", ledger.stats()["recorded"] == 1)
        check("stats: replays == 1 after one replay attempt", ledger.stats()["replays"] == 1)

        other_key = ("lease-b", "digest-b")
        check("a DIFFERENT key is independent -> True", ledger.check_and_record(other_key) is True)
        check("stats: recorded == 2 after a second distinct key", ledger.stats()["recorded"] == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 2) DURABILITY — restart simulation: a NEW instance on the SAME dir must
#    see the key as already-used.
# --------------------------------------------------------------------------


def test_durability_restart_simulation() -> None:
    tmp = tempfile.mkdtemp(prefix="sci-ledger-durable-")
    try:
        ledger_dir = os.path.join(tmp, "ledger")
        key = ("lease-restart", "digest-restart")

        ledger_before_restart = sci.DurableSingleUseLedger(ledger_dir)
        check(
            "pre-restart: first use of the key -> True",
            ledger_before_restart.check_and_record(key) is True,
        )
        # Drop the reference entirely — nothing but the on-disk marker file
        # survives past this point, simulating a process exit/restart.
        del ledger_before_restart

        ledger_after_restart = sci.DurableSingleUseLedger(ledger_dir)
        check(
            "post-restart (new instance, same dir): replay of the SAME key -> False",
            ledger_after_restart.check_and_record(key) is False,
        )
        check(
            "post-restart: a genuinely NEW key still records fine -> True",
            ledger_after_restart.check_and_record(("lease-restart-2", "digest-restart-2")) is True,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 3) ATOMIC CONCURRENCY — threads racing the identical key.
# --------------------------------------------------------------------------


def test_atomic_concurrency_threads() -> None:
    tmp = tempfile.mkdtemp(prefix="sci-ledger-race-threads-")
    try:
        ledger_dir = os.path.join(tmp, "ledger")
        ledger = sci.DurableSingleUseLedger(ledger_dir)
        key = ("lease-race", "digest-race")

        n_threads = 32
        barrier = threading.Barrier(n_threads)
        results: list[bool] = [False] * n_threads

        def worker(i: int) -> None:
            barrier.wait()  # maximize the chance every thread hits check_and_record together
            results[i] = ledger.check_and_record(key)

        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            list(pool.map(worker, range(n_threads)))

        winners = sum(1 for r in results if r)
        check(
            f"exactly ONE of {n_threads} racing threads wins check_and_record for the same key "
            f"(got {winners})",
            winners == 1,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 4) ATOMIC CONCURRENCY — separate OS PROCESSES racing the identical key
#    (the stronger proof: O_CREAT|O_EXCL atomicity is a kernel/filesystem
#    guarantee, not merely a Python-level lock, so it must hold across
#    process boundaries too, not just threads sharing one interpreter).
# --------------------------------------------------------------------------


def _process_worker(ledger_dir: str, lease_id: str, grant_digest: str, out_queue) -> None:
    # Fresh DurableSingleUseLedger per process (a real restart-like construction,
    # not a shared Python object — multiprocessing.Process cannot share one
    # anyway, which is exactly the point: each process only shares the
    # FILESYSTEM, proving the atomicity is a kernel guarantee).
    ledger = sci.DurableSingleUseLedger(ledger_dir)
    result = ledger.check_and_record((lease_id, grant_digest))
    out_queue.put(result)


def test_atomic_concurrency_processes() -> None:
    tmp = tempfile.mkdtemp(prefix="sci-ledger-race-procs-")
    try:
        ledger_dir = os.path.join(tmp, "ledger")
        os.makedirs(ledger_dir, mode=0o700, exist_ok=True)
        lease_id, grant_digest = "lease-race-proc", "digest-race-proc"

        ctx = multiprocessing.get_context("fork")
        n_procs = 16
        out_queue = ctx.Queue()
        procs = [
            ctx.Process(target=_process_worker, args=(ledger_dir, lease_id, grant_digest, out_queue))
            for _ in range(n_procs)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=30)
            check(f"process worker exited cleanly (pid={p.pid})", p.exitcode == 0)

        results = [out_queue.get_nowait() for _ in range(n_procs)]
        winners = sum(1 for r in results if r)
        check(
            f"exactly ONE of {n_procs} racing OS PROCESSES wins check_and_record for the same key "
            f"(got {winners})",
            winners == 1,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 5) FAIL-CLOSED on a genuine storage fault (unwritable ledger dir).
# --------------------------------------------------------------------------


def test_fail_closed_on_unwritable_dir() -> None:
    if os.geteuid() == 0:
        print("SKIP: fail-closed-unwritable-dir test (running as root; permission bits don't restrict root)")
        return
    tmp = tempfile.mkdtemp(prefix="sci-ledger-unwritable-")
    try:
        ledger_dir = os.path.join(tmp, "ledger")
        ledger = sci.DurableSingleUseLedger(ledger_dir)
        # Strip write+execute so os.open(..., O_CREAT) inside the dir fails with
        # PermissionError -- a genuine storage fault, distinct from the
        # expected-and-handled FileExistsError replay path.
        os.chmod(ledger_dir, stat.S_IRUSR)
        raised = False
        try:
            ledger.check_and_record(("lease-unwritable", "digest-unwritable"))
        except OSError:
            raised = True
        check("unwritable ledger dir -> check_and_record RAISES (fail-closed, not a silent False)", raised)
    finally:
        os.chmod(ledger_dir, stat.S_IRWXU)
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 6) End-to-end: mint_scheduler_context wired to a real DurableSingleUseLedger
#    (proves the transport seam's composition, not just the bare ledger).
# --------------------------------------------------------------------------


def _keypair() -> tuple[bytes, str]:
    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return priv_raw, pub_hex


def _keys_json(key_id: str, pub_hex: str) -> dict:
    return {
        "schema_version": "1",
        "revision": 1,
        "keys": [{"key_id": key_id, "ed25519_public_key": pub_hex, "status": "active"}],
    }


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_lease(*, lease_priv: bytes, lease_key_id: str, issued_at: datetime, expires_at: datetime) -> dict:
    lease = {
        "lease_id": "lease-e2e",
        "version": 1,
        "source": "test",
        "owner": "test",
        "issued_to": "switchboard-local-tool-executor",
        "issued_at": _iso(issued_at),
        "expires_at": _iso(expires_at),
        "permissions": {"actions": ["run_cmd"], "resources": [], "constraints": {}},
        "input_schema": {},
        "output_schema": {},
        "trust_tier": 2,
        "zero_trust_behavior": "none",
        "cost_class": "first-party",
        "parent_lease_id": None,
        "revocation_epoch": 0,
        "grant_digest": "b" * 64,
        "policy_revision": 1,
        "sig_scheme": cl.SIG_SCHEME_ED25519,
        "issuer_key_id": lease_key_id,
        "signature": "",
    }
    lease["signature"] = cl.sign_ed25519(lease, lease_priv)
    return lease


def test_end_to_end_mint_with_durable_ledger_then_restart_denies_replay() -> None:
    tmp = tempfile.mkdtemp(prefix="sci-ledger-e2e-")
    try:
        ledger_dir = os.path.join(tmp, "ledger")
        NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        CORRELATION = {"task_id": "task-e2e", "principal": "agent-e2e", "dispatch_mode": "agent"}

        lease_priv, lease_pub_hex = _keypair()
        lease_key_id = "test-lease-signer-e2e"
        lease_keys_json = _keys_json(lease_key_id, lease_pub_hex)
        ctx_priv, ctx_key_id = _keypair()[0], "test-context-signer-e2e"

        lease = _build_lease(
            lease_priv=lease_priv, lease_key_id=lease_key_id,
            issued_at=NOW, expires_at=NOW + timedelta(hours=2),
        )

        ledger1 = sci.DurableSingleUseLedger(ledger_dir)
        result1 = sci.mint_scheduler_context(
            lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
            private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
            ledger=ledger1, now=NOW,
        )
        check("e2e: first mint against a durable ledger -> ok=True", result1["ok"] is True)

        # Simulate a service restart: a brand-new DurableSingleUseLedger on the
        # same dir, then attempt the identical mint again.
        ledger2 = sci.DurableSingleUseLedger(ledger_dir)
        result2 = sci.mint_scheduler_context(
            lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
            private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
            ledger=ledger2, now=NOW,
        )
        check(
            "e2e: SAME lease re-presented after a simulated restart -> ok=False (no double-mint)",
            result2["ok"] is False,
        )
        check("e2e: post-restart replay -> DENY_REPLAY", result2["reason"] == sci.DENY_REPLAY)
        check("e2e: post-restart replay -> no context minted", result2["context"] is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    test_basic_record_and_replay()
    test_durability_restart_simulation()
    test_atomic_concurrency_threads()
    test_atomic_concurrency_processes()
    test_fail_closed_on_unwritable_dir()
    test_end_to_end_mint_with_durable_ledger_then_restart_denies_replay()

    print(f"\n{passed} passed, {failed} failed (of {passed + failed} assertions)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
