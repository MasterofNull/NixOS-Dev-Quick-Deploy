#!/usr/bin/env python3
"""Offline hermetic tests — Foundation C, C2-SCI subslice B3: the
`capability_lease_gate.py` outbound client + the `dispatch.py` authenticated
ingress adapter. Both flag-gated on `CAPABILITY_SCHEDULER_CONTEXT_ISSUER`
(default "0"/unset). See
`.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md`
(rev4) §1/§3/§4 and the FREEZE doc's B3 scope.

No network, no live `aq-c2-scheduler-context-issuer` service, no `/run/secrets`.
A throwaway UDS "mock issuer" (a plain socket accept loop, no systemd unit)
stands in for the confined service on the gate side. All Ed25519 keypairs are
generated offline for the test run only.

Covers:
  1. Flag-OFF byte-parity (regression): `gate.enforce()` decisions never carry
     a `scheduler_context` key; `dispatch.py`'s ingress adapter is structurally
     unreferenced by any existing hot-path function (`main`, `dispatch_task`).
  2. Flag-ON: an ADMIT decision (both the candidate-lease path and the
     first-party-lease path) triggers an outbound mint call to the mock
     issuer, and the minted context is attached to that decision.
  3. Flag-ON, failed issuer (unreachable socket, or a typed issuer deny):
     the tool-admission decision (admitted/not-admitted) is UNCHANGED — only
     the optional `scheduler_context` attachment is absent.
  4. Dispatch ingress: accepts a validly-signed context (via a real
     `scheduler_context_issuer.mint_scheduler_context` round-trip); rejects a
     forged signature, wrong audience, expired, epoch-stale, wrong schema,
     and a caller-supplied non-mapping "context". Keys-file fail-closed.

Run directly: `python3 scripts/testing/test-c2-gate-dispatch-wiring.py`
Exits 0 iff every check passes.
"""
from __future__ import annotations

import inspect
import json
import os
import socket
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SWITCHBOARD_DIR = str(_REPO_ROOT / "ai-stack" / "switchboard")
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
for _p in (_SWITCHBOARD_DIR, _LIB_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

import capability_lease as cl  # noqa: E402
import capability_lease_gate as gate  # noqa: E402
import scheduler_context_issuer as sci  # noqa: E402
import switchboard as _swb  # noqa: E402 — live _TOOL_LEASE_PRIORITY source (bundle equality)
import dispatch  # noqa: E402

# --------------------------------------------------------------------------
# Test harness (no external deps)
# --------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))


def _report_and_exit() -> None:
    failed = [r for r in _RESULTS if not r[1]]
    for name, ok, detail in _RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    print(f"\n{len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed")
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
        sys.exit(1)
    sys.exit(0)


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------

PROD_KEY = b"test-production-signing-key-not-the-dev-key-0123456789"
BUNDLE_TOOLS = set(_swb._TOOL_LEASE_PRIORITY.keys())
NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
CORRELATION = {"task_id": "task-1", "principal": "agent-1", "dispatch_mode": "agent"}

_ENV_KEYS = (
    "CAPABILITY_SCHEDULER_CONTEXT_ISSUER",
    "AQ_SCHEDULER_CONTEXT_SOCKET_PATH",
)


def prod_resolver():
    return PROD_KEY, False


def reset_gate_state() -> None:
    gate.reset_first_party_lease_cache()
    gate.reset_manifest_cache()


def base_ctx(**overrides) -> dict:
    ctx = {
        "zero_trust_behavior": "none",
        "candidate_leases": [],
        "bundle_tools": BUNDLE_TOOLS,
    }
    ctx.update(overrides)
    return ctx


def _clear_env() -> dict:
    """Snapshot + clear the flag/socket-path env vars this test suite touches.
    Returns the snapshot for restoration."""
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    return saved


def _restore_env(saved: dict) -> None:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _keypair() -> tuple[bytes, str]:
    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return priv_raw, pub_hex


def _keys_json(key_id: str, pub_hex: str, status: str = "active") -> dict:
    return {
        "schema_version": "1",
        "revision": 1,
        "keys": [{"key_id": key_id, "ed25519_public_key": pub_hex, "status": status}],
    }


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_lease(*, lease_priv: bytes, lease_key_id: str, issued_at: datetime, expires_at: datetime) -> dict:
    lease = {
        "lease_id": "lease-1",
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
        "grant_digest": "digest-1",
        "policy_revision": 1,
        "sig_scheme": cl.SIG_SCHEME_ED25519,
        "issuer_key_id": lease_key_id,
        "signature": "",
    }
    lease["signature"] = cl.sign_ed25519(lease, lease_priv)
    return lease


def _build_context(
    *,
    ctx_priv: bytes,
    ctx_key_id: str,
    audience: str = sci.AUDIENCE,
    expires_at: datetime,
    revocation_epoch: int = 0,
    schema: str = sci.CONTEXT_SCHEMA,
    sign: bool = True,
) -> dict:
    context = {
        "schema": schema,
        "schema_version": sci.CONTEXT_SCHEMA_VERSION,
        "context_id": "sched-ctx::lease-1::digest-1",
        "lease_id": "lease-1",
        "grant_digest": "digest-1",
        "task_id": "task-1",
        "audience": audience,
        "principal": "agent-1",
        "dispatch_mode": "agent",
        "action_class": "run_cmd",
        "trust_tier": 2,
        "policy_revision": 1,
        "issued_at": _iso(NOW),
        "expires_at": _iso(expires_at),
        "revocation_epoch": revocation_epoch,
        "issuer_key_id": ctx_key_id,
        "sig_scheme": cl.SIG_SCHEME_ED25519,
        "signature": "",
    }
    if sign:
        context["signature"] = cl.sign_ed25519(context, ctx_priv)
    return context


def _start_mock_issuer(response: dict, capture: list | None = None):
    """One-shot-per-connection UDS mock issuer: replies with `response` (JSON,
    newline-terminated) to every connection until stopped. If `capture` is a
    list, the decoded request frame from each connection is appended to it.
    Returns (socket_path, stop_fn)."""
    tmpdir = tempfile.mkdtemp(prefix="c2-sci-mock-")
    sock_path = os.path.join(tmpdir, "issuer.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path)
    srv.listen(4)
    srv.settimeout(1.0)
    stop_flag = threading.Event()

    def _loop():
        while not stop_flag.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                conn.settimeout(5.0)
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                if capture is not None and buf:
                    try:
                        capture.append(json.loads(buf.split(b"\n", 1)[0].decode("utf-8")))
                    except Exception:
                        pass
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    t = threading.Thread(target=_loop, daemon=True)
    t.start()

    def _stop():
        stop_flag.set()
        try:
            srv.close()
        except Exception:
            pass

    return sock_path, _stop


# --------------------------------------------------------------------------
# 1. Flag-OFF byte-parity (the single most important property this file
#    proves for the LIVE gate).
# --------------------------------------------------------------------------


def test_flag_off_no_scheduler_context_key_and_tool_still_admitted():
    saved = _clear_env()  # flag unset -> "0" default
    try:
        reset_gate_state()
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("flag_off_run_command_admitted", "run_command" in admitted, f"admitted={admitted}")
        d = next(x for x in decisions if x["tool"] == "run_command")
        check("flag_off_no_scheduler_context_key", "scheduler_context" not in d, d)
    finally:
        _restore_env(saved)
        reset_gate_state()


def test_flag_explicitly_zero_matches_unset():
    saved = _clear_env()
    os.environ["CAPABILITY_SCHEDULER_CONTEXT_ISSUER"] = "0"
    try:
        reset_gate_state()
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        d = next(x for x in decisions if x["tool"] == "run_command")
        check("flag_zero_no_scheduler_context_key", "scheduler_context" not in d, d)
        check("flag_zero_enabled_helper_false", gate._scheduler_context_issuer_enabled() is False)
    finally:
        _restore_env(saved)
        reset_gate_state()


def test_flag_off_request_scheduler_context_returns_none_without_import_attempt():
    saved = _clear_env()
    try:
        result = gate._request_scheduler_context({"lease_id": "x"}, {})
        check("flag_off_request_scheduler_context_none", result is None, result)
    finally:
        _restore_env(saved)


def test_flag_off_dispatch_ingress_not_wired_into_hot_path():
    """Structural regression guard for the B1-style inertness this subslice
    follows: dispatch.py performs NO context deserialization on any existing
    call path today, and the new ingress adapter must not have been spliced
    into `main()` / `dispatch_task()` to preserve that byte-parity guarantee."""
    src_main = inspect.getsource(dispatch.main)
    src_task = inspect.getsource(dispatch.dispatch_task)
    check(
        "ingress_not_referenced_in_main",
        "verify_ingress_scheduler_context" not in src_main,
        src_main[:200],
    )
    check(
        "ingress_not_referenced_in_dispatch_task",
        "verify_ingress_scheduler_context" not in src_task,
        src_task[:200],
    )
    check(
        "dispatch_flag_off_by_default",
        dispatch._scheduler_context_issuer_enabled() is False,
    )


# --------------------------------------------------------------------------
# 2/3. Flag-ON: outbound mint on ALLOW; failed/deny issuer never changes
#    tool-admission.
# --------------------------------------------------------------------------


def test_flag_on_first_party_admit_mints_context_via_mock_issuer():
    saved = _clear_env()
    captured: list = []
    stub_context = {"schema": sci.CONTEXT_SCHEMA, "stub_marker": "b3-first-party"}
    sock_path, stop = _start_mock_issuer({"ok": True, "context": stub_context}, capture=captured)
    os.environ["CAPABILITY_SCHEDULER_CONTEXT_ISSUER"] = "1"
    os.environ["AQ_SCHEDULER_CONTEXT_SOCKET_PATH"] = sock_path
    try:
        reset_gate_state()
        admitted, decisions = gate.enforce(
            {"run_command"}, base_ctx(scheduler_correlation=CORRELATION), 0, prod_resolver,
        )
        check("flag_on_fp_run_command_admitted", "run_command" in admitted, f"admitted={admitted}")
        d = next(x for x in decisions if x["tool"] == "run_command")
        check("flag_on_fp_scheduler_context_attached", d.get("scheduler_context") == stub_context, d)
        check("flag_on_fp_issuer_received_a_request", len(captured) >= 1, captured)
        if captured:
            check("flag_on_fp_request_carries_lease", "lease" in captured[0], captured[0])
            check(
                "flag_on_fp_request_carries_correlation",
                captured[0].get("correlation") == CORRELATION,
                captured[0],
            )
    finally:
        stop()
        _restore_env(saved)
        reset_gate_state()


def test_flag_on_candidate_admit_mints_context_via_mock_issuer():
    saved = _clear_env()
    stub_context = {"schema": sci.CONTEXT_SCHEMA, "stub_marker": "b3-candidate"}
    sock_path, stop = _start_mock_issuer({"ok": True, "context": stub_context})
    os.environ["CAPABILITY_SCHEDULER_CONTEXT_ISSUER"] = "1"
    os.environ["AQ_SCHEDULER_CONTEXT_SOCKET_PATH"] = sock_path
    try:
        reset_gate_state()
        # NOTE: `cl.verify()` (the legacy HMAC path `_admission_verify` falls
        # back to for a lease with no `sig_scheme`) checks `is_expired()`
        # against the REAL wall-clock `datetime.now()`, not an injected `now`
        # — so this fixture must use real-time-relative timestamps, unlike
        # the ingress tests below which thread a fixed `now=NOW` explicitly
        # through `dispatch.verify_ingress_scheduler_context`.
        _real_now = datetime.now(timezone.utc)
        lease = {
            "lease_id": "candidate::custom_ext_tool::x",
            "version": 1,
            "source": "capability-intake-shadow",
            "owner": "capability-intake-shadow",
            "issued_to": "candidate:test",
            "issued_at": _iso(_real_now),
            "expires_at": _iso(_real_now + timedelta(hours=1)),
            "permissions": {"actions": ["custom_ext_tool"], "resources": [], "constraints": {}},
            "input_schema": {},
            "output_schema": {},
            "trust_tier": 3,
            "zero_trust_behavior": "none",
            "cost_class": "shadow",
            "parent_lease_id": None,
            "revocation_epoch": 0,
            "signature": "",
        }
        lease["signature"] = cl.sign(lease, PROD_KEY)
        admitted, decisions = gate.enforce(
            {"custom_ext_tool"},
            base_ctx(candidate_leases=[lease], scheduler_correlation=CORRELATION),
            0,
            prod_resolver,
        )
        check("flag_on_candidate_admitted", "custom_ext_tool" in admitted, f"admitted={admitted}")
        d = next(x for x in decisions if x["tool"] == "custom_ext_tool")
        check("flag_on_candidate_scheduler_context_attached", d.get("scheduler_context") == stub_context, d)
    finally:
        stop()
        _restore_env(saved)
        reset_gate_state()


def test_flag_on_unreachable_issuer_does_not_change_admission():
    saved = _clear_env()
    os.environ["CAPABILITY_SCHEDULER_CONTEXT_ISSUER"] = "1"
    # Socket path that nothing is listening on.
    tmpdir = tempfile.mkdtemp(prefix="c2-sci-dead-")
    os.environ["AQ_SCHEDULER_CONTEXT_SOCKET_PATH"] = os.path.join(tmpdir, "nobody-home.sock")
    try:
        reset_gate_state()
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check(
            "flag_on_unreachable_issuer_still_admits",
            "run_command" in admitted,
            f"admitted={admitted}",
        )
        d = next(x for x in decisions if x["tool"] == "run_command")
        check("flag_on_unreachable_issuer_no_context_key", "scheduler_context" not in d, d)
    finally:
        _restore_env(saved)
        reset_gate_state()


def test_flag_on_issuer_deny_reply_does_not_change_admission():
    saved = _clear_env()
    sock_path, stop = _start_mock_issuer({"ok": False, "reason": "lease-unverified", "context": None})
    os.environ["CAPABILITY_SCHEDULER_CONTEXT_ISSUER"] = "1"
    os.environ["AQ_SCHEDULER_CONTEXT_SOCKET_PATH"] = sock_path
    try:
        reset_gate_state()
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check(
            "flag_on_issuer_deny_still_admits_tool",
            "run_command" in admitted,
            f"admitted={admitted}",
        )
        d = next(x for x in decisions if x["tool"] == "run_command")
        check("flag_on_issuer_deny_no_context_key", "scheduler_context" not in d, d)
    finally:
        stop()
        _restore_env(saved)
        reset_gate_state()


def test_flag_on_malformed_issuer_reply_does_not_change_admission():
    saved = _clear_env()
    sock_path, stop = _start_mock_issuer({"unexpected": "shape"})
    os.environ["CAPABILITY_SCHEDULER_CONTEXT_ISSUER"] = "1"
    os.environ["AQ_SCHEDULER_CONTEXT_SOCKET_PATH"] = sock_path
    try:
        reset_gate_state()
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check(
            "flag_on_malformed_reply_still_admits_tool",
            "run_command" in admitted,
            f"admitted={admitted}",
        )
    finally:
        stop()
        _restore_env(saved)
        reset_gate_state()


# --------------------------------------------------------------------------
# 4. dispatch.py ingress adapter — accept genuine, reject everything else.
# --------------------------------------------------------------------------


def test_ingress_accepts_a_real_minted_context():
    lease_priv, lease_pub_hex = _keypair()
    lease_key_id = "test-lease-signer"
    lease_keys_json = _keys_json(lease_key_id, lease_pub_hex)
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)

    lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2),
    )
    ledger = sci.InMemorySingleUseLedger()
    minted = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("fixture_mint_ok", minted["ok"] is True, minted)
    context = minted["context"]

    result = dispatch.verify_ingress_scheduler_context(context, ctx_keys_json, current_epoch=0, now=NOW)
    check("ingress_accepts_valid_context", result["ok"] is True, result)
    check("ingress_returns_the_context", result["context"] == context, result)


def test_ingress_rejects_forged_signature():
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)
    context = _build_context(ctx_priv=ctx_priv, ctx_key_id=ctx_key_id, expires_at=NOW + timedelta(hours=1))
    context["principal"] = "attacker-widened-principal"  # tamper post-sign
    result = dispatch.verify_ingress_scheduler_context(context, ctx_keys_json, current_epoch=0, now=NOW)
    check("ingress_rejects_forged", result["ok"] is False, result)
    check("ingress_forged_reason", result["reason"] == dispatch.DENY_INGRESS_UNVERIFIED, result)


def test_ingress_rejects_wrong_audience():
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)
    context = _build_context(
        ctx_priv=ctx_priv, ctx_key_id=ctx_key_id,
        audience="some-other-consumer", expires_at=NOW + timedelta(hours=1),
    )
    result = dispatch.verify_ingress_scheduler_context(context, ctx_keys_json, current_epoch=0, now=NOW)
    check("ingress_rejects_wrong_audience", result["ok"] is False, result)
    check("ingress_wrong_audience_reason", result["reason"] == dispatch.DENY_INGRESS_WRONG_AUDIENCE, result)


def test_ingress_rejects_expired_context():
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)
    context = _build_context(ctx_priv=ctx_priv, ctx_key_id=ctx_key_id, expires_at=NOW - timedelta(minutes=1))
    result = dispatch.verify_ingress_scheduler_context(context, ctx_keys_json, current_epoch=0, now=NOW)
    check("ingress_rejects_expired", result["ok"] is False, result)
    check("ingress_expired_reason", result["reason"] == dispatch.DENY_INGRESS_EXPIRED, result)


def test_ingress_rejects_epoch_stale_context():
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)
    context = _build_context(
        ctx_priv=ctx_priv, ctx_key_id=ctx_key_id,
        expires_at=NOW + timedelta(hours=1), revocation_epoch=0,
    )
    result = dispatch.verify_ingress_scheduler_context(context, ctx_keys_json, current_epoch=5, now=NOW)
    check("ingress_rejects_epoch_stale", result["ok"] is False, result)
    check("ingress_epoch_stale_reason", result["reason"] == dispatch.DENY_INGRESS_EPOCH_STALE, result)


def test_ingress_rejects_wrong_schema():
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)
    context = _build_context(
        ctx_priv=ctx_priv, ctx_key_id=ctx_key_id,
        expires_at=NOW + timedelta(hours=1), schema="not-the-scheduler-context-schema",
    )
    result = dispatch.verify_ingress_scheduler_context(context, ctx_keys_json, current_epoch=0, now=NOW)
    check("ingress_rejects_wrong_schema", result["ok"] is False, result)
    check("ingress_wrong_schema_reason", result["reason"] == dispatch.DENY_INGRESS_WRONG_SCHEMA, result)


def test_ingress_rejects_caller_supplied_non_context():
    for candidate in ("just a string", 42, ["a", "list"], None, {"totally": "unrelated"}):
        result = dispatch.verify_ingress_scheduler_context(candidate, {}, current_epoch=0, now=NOW)
        check(
            f"ingress_rejects_non_context_{type(candidate).__name__}",
            result["ok"] is False and result["context"] is None,
            (candidate, result),
        )


def test_ingress_never_raises_on_a_malformed_but_signed_looking_context():
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)
    context = _build_context(ctx_priv=ctx_priv, ctx_key_id=ctx_key_id, expires_at=NOW + timedelta(hours=1))
    context["expires_at"] = "not-a-valid-timestamp"
    try:
        result = dispatch.verify_ingress_scheduler_context(context, ctx_keys_json, current_epoch=0, now=NOW)
        check("ingress_malformed_timestamp_never_raises", result["ok"] is False, result)
    except Exception as exc:  # pragma: no cover — this branch itself is the failure
        check("ingress_malformed_timestamp_never_raises", False, f"raised {exc!r}")


def test_keys_file_fail_closed():
    missing_path = Path(tempfile.mkdtemp(prefix="c2-sci-nokeys-")) / "does-not-exist.json"
    loaded = dispatch._load_scheduler_signer_keys_json(path=missing_path)
    check("keys_file_missing_yields_empty_sentinel", loaded == {}, loaded)

    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    context = _build_context(ctx_priv=ctx_priv, ctx_key_id=ctx_key_id, expires_at=NOW + timedelta(hours=1))
    result = dispatch.verify_ingress_scheduler_context(context, {}, current_epoch=0, now=NOW)
    check("keys_file_empty_dict_denies_verify", result["ok"] is False, result)

    malformed_path = Path(tempfile.mkdtemp(prefix="c2-sci-badkeys-")) / "bad.json"
    malformed_path.write_text("not json at all {{{")
    loaded_bad = dispatch._load_scheduler_signer_keys_json(path=malformed_path)
    check("keys_file_malformed_json_yields_empty_sentinel", loaded_bad == {}, loaded_bad)


# --------------------------------------------------------------------------
# Run all
# --------------------------------------------------------------------------

_TESTS = [
    test_flag_off_no_scheduler_context_key_and_tool_still_admitted,
    test_flag_explicitly_zero_matches_unset,
    test_flag_off_request_scheduler_context_returns_none_without_import_attempt,
    test_flag_off_dispatch_ingress_not_wired_into_hot_path,
    test_flag_on_first_party_admit_mints_context_via_mock_issuer,
    test_flag_on_candidate_admit_mints_context_via_mock_issuer,
    test_flag_on_unreachable_issuer_does_not_change_admission,
    test_flag_on_issuer_deny_reply_does_not_change_admission,
    test_flag_on_malformed_issuer_reply_does_not_change_admission,
    test_ingress_accepts_a_real_minted_context,
    test_ingress_rejects_forged_signature,
    test_ingress_rejects_wrong_audience,
    test_ingress_rejects_expired_context,
    test_ingress_rejects_epoch_stale_context,
    test_ingress_rejects_wrong_schema,
    test_ingress_rejects_caller_supplied_non_context,
    test_ingress_never_raises_on_a_malformed_but_signed_looking_context,
    test_keys_file_fail_closed,
]


if __name__ == "__main__":
    for _t in _TESTS:
        _t()
    _report_and_exit()
