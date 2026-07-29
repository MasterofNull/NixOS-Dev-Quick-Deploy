#!/usr/bin/env python3
"""Offline acceptance tests — Foundation C2 capability-lease enforcement gate.

Exercises `ai-stack/switchboard/capability_lease_gate.py::enforce()` as a
pure function AND the real `ai-stack/switchboard/switchboard.py::_admit_tool_call`
executor-chokepoint helper (stubbed inputs, no live server, no network) per
`.agents/plans/aqos-foundation-c/C2-DESIGN-AND-AUTHORIZATION.md` +
`C2-AMENDMENT-BUILTIN-TOOLS.md`.

Run directly: `python3 scripts/testing/test-capability-lease-gate.py`
Exits 0 iff every test passes; each failure prints tool/expected/actual.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SWITCHBOARD_DIR = str(_REPO_ROOT / "ai-stack" / "switchboard")
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
for _p in (_SWITCHBOARD_DIR, _LIB_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import capability_lease as cl  # noqa: E402
import capability_lease_gate as gate  # noqa: E402
import switchboard as _swb  # noqa: E402 — live _TOOL_LEASE_PRIORITY source (finding 4)

MANIFEST_PATH = _REPO_ROOT / "config" / "first-party-tools.json"
DECISION_SCHEMA_PATH = _REPO_ROOT / "config" / "schemas" / "capability-lease-gate-decision.schema.json"


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


def prod_resolver():
    return PROD_KEY, False


def dev_resolver():
    return cl.DEV_SIGNING_KEY, True


def load_manifest_tools() -> dict:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {entry["tool"]: entry for entry in raw["tools"]}


MANIFEST_TOOLS = load_manifest_tools()
# Derived from the LIVE switchboard tool-priority table, not the manifest
# itself (finding 4) — otherwise the codex-2 equality tests below would be
# comparing the manifest against a copy of itself and could never catch
# real manifest<->bundle drift.
BUNDLE_TOOLS = set(_swb._TOOL_LEASE_PRIORITY.keys())


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


def make_candidate_lease(
    tool: str,
    key: bytes,
    *,
    writes=None,
    network=None,
    expires_delta=timedelta(hours=1),
    revocation_epoch=0,
    now=None,
) -> dict:
    moment = now or datetime.now(timezone.utc)
    lease = {
        "lease_id": f"candidate::{tool}::{moment.isoformat()}",
        "version": 1,
        "source": "capability-intake-shadow",
        "owner": "capability-intake-shadow",
        "issued_to": "candidate:test",
        "issued_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (moment + expires_delta).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "permissions": {
            "actions": [tool],
            "resources": (["write"] if writes else []) + (["network"] if network else []),
            "constraints": {"network": network, "writes": writes},
        },
        "input_schema": {},
        "output_schema": {},
        "trust_tier": 3,
        "zero_trust_behavior": "none",
        "cost_class": "shadow",
        "parent_lease_id": None,
        "revocation_epoch": revocation_epoch,
        "signature": "",
    }
    lease["signature"] = cl.sign(lease, key)
    return lease


# --------------------------------------------------------------------------
# 1. Flag-OFF parity (switchboard chokepoint, not just the pure gate)
# --------------------------------------------------------------------------


def test_flag_off_parity():
    import switchboard as swb

    assert swb.CAPABILITY_LEASE_ENFORCEMENT is False, "test env must start with flag OFF (default)"

    # Sabotage the gate so that if _admit_tool_call ever consulted it while
    # OFF, the test would fail loudly instead of silently passing.
    original_enforce = gate.enforce
    gate.enforce = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("gate must not be called when flag is OFF"))
    try:
        admitted, decision = swb._admit_tool_call("run_command", {"run_command", "read_file"})
        check("flag_off_parity_admits_bundle_tool", admitted is True and decision is None,
              f"admitted={admitted} decision={decision}")
        admitted2, decision2 = swb._admit_tool_call("not_in_bundle", {"run_command"})
        check("flag_off_parity_denies_non_bundle_tool", admitted2 is False and decision2 is None,
              f"admitted={admitted2} decision={decision2}")
    finally:
        gate.enforce = original_enforce


def test_flag_on_but_gate_import_broken_fails_closed_not_open():
    """A gate import/call failure under flag ON must deny, never silently
    fall back to the flag-OFF (allowed_names-only) behavior."""
    import switchboard as swb

    original_flag = swb.CAPABILITY_LEASE_ENFORCEMENT
    swb.CAPABILITY_LEASE_ENFORCEMENT = True
    original_enforce = gate.enforce
    gate.enforce = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        admitted, _ = swb._admit_tool_call("run_command", {"run_command"})
        check("gate_call_exception_fails_closed_via_switchboard", admitted is False, f"admitted={admitted}")
    finally:
        swb.CAPABILITY_LEASE_ENFORCEMENT = original_flag
        gate.enforce = original_enforce


# --------------------------------------------------------------------------
# 2. (B1) Per-call chokepoint gated: privileged bundle tool with no lease
#    dropped under flag ON, driven through the real switchboard admission
#    helper (not just _resolve_tool_lease).
# --------------------------------------------------------------------------


def test_b1_privileged_tool_dropped_without_lease_via_switchboard():
    import switchboard as swb

    reset_gate_state()
    original_flag = swb.CAPABILITY_LEASE_ENFORCEMENT
    swb.CAPABILITY_LEASE_ENFORCEMENT = True
    original_resolver = cl.resolve_key
    cl.resolve_key = prod_resolver  # bypass DEV-key degrade so deny-closed is exercised on its own
    original_ctx_fn = swb._capability_lease_request_ctx  # save to restore, never delete (finding 4)
    try:
        # No leases exist anywhere (manifest not pre-issued, no candidate
        # leases supplied) — run_command is in the bundle's allowed_names
        # but must still be dropped at the executor chokepoint.
        reset_gate_state()
        # Force manifest resolution to "no first-party leases issued yet" by
        # NOT calling issue_first_party_leases — enforce() will issue them
        # itself via the manifest, so to prove true "unleased" denial we
        # point bundle_tools construction away from matching (simulate the
        # tool not being coverable) — instead exercise via a request context
        # with an empty/broken manifest path.
        swb._capability_lease_request_ctx = lambda: {
            "zero_trust_behavior": "none",
            "candidate_leases": [],
            "bundle_tools": set(),  # forces manifest<->bundle mismatch -> fail closed
        }
        admitted, decision = swb._admit_tool_call("run_command", {"run_command", "read_file"})
        check("b1_run_command_dropped_when_unleased", admitted is False,
              f"admitted={admitted} decision={decision}")
    finally:
        swb.CAPABILITY_LEASE_ENFORCEMENT = original_flag
        cl.resolve_key = original_resolver
        swb._capability_lease_request_ctx = original_ctx_fn  # restore, not delete
        reset_gate_state()


def test_b1_normal_request_admits_run_command_via_first_party_lease():
    """The regression the C2-AMENDMENT gap would have caused: a normal
    flag-ON request with the real manifest/bundle wiring must ADMIT
    run_command via its first-party lease, not deny it."""
    reset_gate_state()
    admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
    check("run_command_admitted_via_first_party_lease", "run_command" in admitted,
          f"admitted={admitted} decisions={decisions}")
    reset_gate_state()


# --------------------------------------------------------------------------
# 3. Deny-closed: no / expired / tampered / epoch-stale lease -> dropped
# --------------------------------------------------------------------------


def test_deny_closed_no_lease():
    reset_gate_state()
    admitted, decisions = gate.enforce({"totally_unknown_tool"}, base_ctx(), 0, prod_resolver)
    check("deny_closed_unknown_tool", admitted == set(), f"admitted={admitted}")
    d = next(d for d in decisions if d["tool"] == "totally_unknown_tool")
    check("deny_closed_unknown_tool_reason", d["reason"] == "no-admitting-lease", d)


def test_deny_closed_expired_candidate_lease():
    reset_gate_state()
    lease = make_candidate_lease("custom_ext_tool", PROD_KEY, expires_delta=timedelta(hours=-1))
    admitted, decisions = gate.enforce(
        {"custom_ext_tool"}, base_ctx(candidate_leases=[lease]), 0, prod_resolver
    )
    check("deny_closed_expired_lease", admitted == set(), f"admitted={admitted}")


def test_deny_closed_tampered_candidate_lease():
    reset_gate_state()
    lease = make_candidate_lease("custom_ext_tool", PROD_KEY)
    tampered = copy.deepcopy(lease)
    # Widen post-signature to a tool that is NOT also independently
    # admissible via the first-party manifest (i.e. not "run_command"),
    # so an admit here can only be explained by the tampered signature
    # being wrongly accepted.
    tampered["permissions"]["actions"] = ["custom_ext_tool", "custom_ext_tool_2"]
    admitted, decisions = gate.enforce(
        {"custom_ext_tool", "custom_ext_tool_2"}, base_ctx(candidate_leases=[tampered]), 0, prod_resolver
    )
    check("deny_closed_tampered_signature", admitted == set(), f"admitted={admitted}")


def test_deny_closed_epoch_stale_candidate_lease():
    reset_gate_state()
    lease = make_candidate_lease("custom_ext_tool", PROD_KEY, revocation_epoch=0)
    admitted, decisions = gate.enforce(
        {"custom_ext_tool"}, base_ctx(candidate_leases=[lease]), 5, prod_resolver
    )
    check("deny_closed_epoch_stale", admitted == set(), f"admitted={admitted}")
    # Sanity: the same lease at epoch 0 DOES admit (proves the denial above
    # is really epoch-staleness, not some other defect).
    admitted_ok, _ = gate.enforce({"custom_ext_tool"}, base_ctx(candidate_leases=[lease]), 0, prod_resolver)
    check("epoch_stale_control_admits_at_matching_epoch", "custom_ext_tool" in admitted_ok, admitted_ok)


# --------------------------------------------------------------------------
# 4. (B2) DEV-key never admits — degrade to safe-read allowlist
# --------------------------------------------------------------------------


def test_b2_dev_key_degrades_never_admits_privileged():
    reset_gate_state()
    lease = make_candidate_lease("custom_ext_tool", cl.DEV_SIGNING_KEY)
    admitted, decisions = gate.enforce(
        {"custom_ext_tool", "run_command", "git_status"},
        base_ctx(candidate_leases=[lease]),
        0,
        dev_resolver,
    )
    check("dev_key_denies_privileged_candidate_even_if_valid", "custom_ext_tool" not in admitted, admitted)
    check("dev_key_denies_run_command", "run_command" not in admitted, admitted)
    check("dev_key_admits_safe_read", "git_status" in admitted, admitted)
    for d in decisions:
        check(f"dev_key_decision_degraded_{d['tool']}", d["degraded"] is True, d)


# --------------------------------------------------------------------------
# 5. Strip drops write/network/exec first-party tools; safe read survives
# --------------------------------------------------------------------------


def test_strip_drops_privileged_first_party_tools_keeps_safe_read():
    reset_gate_state()
    admitted, decisions = gate.enforce(
        {"run_command", "write_file", "git_status"},
        base_ctx(zero_trust_behavior="strip"),
        0,
        prod_resolver,
    )
    check("strip_drops_run_command", "run_command" not in admitted, admitted)
    check("strip_drops_write_file", "write_file" not in admitted, admitted)
    check("strip_keeps_git_status", "git_status" in admitted, admitted)
    rc_decision = next(d for d in decisions if d["tool"] == "run_command")
    check("strip_decision_marks_stripped", rc_decision["zero_trust_stripped"] is True, rc_decision)
    reset_gate_state()


def test_strip_candidate_lease_also_drops_privileged():
    reset_gate_state()
    lease = make_candidate_lease("custom_ext_writer", PROD_KEY, writes=True)
    admitted, decisions = gate.enforce(
        {"custom_ext_writer"}, base_ctx(zero_trust_behavior="strip", candidate_leases=[lease]), 0, prod_resolver
    )
    check("strip_drops_candidate_write_tool", "custom_ext_writer" not in admitted, admitted)


# --------------------------------------------------------------------------
# 5b. (BLOCKING FINDING 1) Zero-trust posture is monotonic: a caller CANNOT
#     weaken a SIGNED lease's own zero_trust_behavior:"strip" by passing
#     "none" / False / omitting the ctx key. Effective posture is always
#     (inherited ctx strip) OR (this lease's signed strip).
# --------------------------------------------------------------------------


def _signed_strip_writer_lease(key: bytes = PROD_KEY) -> dict:
    lease = make_candidate_lease("custom_ext_writer", key, writes=True)
    lease["zero_trust_behavior"] = "strip"
    lease["signature"] = cl.sign({**lease, "signature": ""}, key)
    return lease


def test_zt1_signed_strip_lease_denied_even_when_ctx_says_none():
    reset_gate_state()
    lease = _signed_strip_writer_lease()
    admitted, decisions = gate.enforce(
        {"custom_ext_writer"}, base_ctx(zero_trust_behavior="none", candidate_leases=[lease]), 0, prod_resolver
    )
    check("zt1_signed_strip_beats_ctx_none", "custom_ext_writer" not in admitted, admitted)
    d = next(d for d in decisions if d["tool"] == "custom_ext_writer")
    check("zt1_signed_strip_beats_ctx_none_marked_stripped", d["zero_trust_stripped"] is True, d)


def test_zt1_signed_strip_lease_denied_when_ctx_passes_boolean_false():
    reset_gate_state()
    lease = _signed_strip_writer_lease()
    admitted, decisions = gate.enforce(
        {"custom_ext_writer"}, base_ctx(zero_trust_behavior=False, candidate_leases=[lease]), 0, prod_resolver
    )
    check("zt1_signed_strip_beats_ctx_false", "custom_ext_writer" not in admitted, admitted)


def test_zt1_signed_strip_lease_denied_when_ctx_omits_key():
    reset_gate_state()
    lease = _signed_strip_writer_lease()
    ctx = base_ctx(candidate_leases=[lease])
    del ctx["zero_trust_behavior"]
    admitted, decisions = gate.enforce({"custom_ext_writer"}, ctx, 0, prod_resolver)
    check("zt1_signed_strip_beats_ctx_omitted", "custom_ext_writer" not in admitted, admitted)


def test_zt1_signed_strip_safe_tool_still_admitted():
    """A signed strip posture only drops PRIVILEGED tools — a safe
    (non-write/network/exec) tool under the same signed strip must still be
    admitted, proving the fix targets privilege, not blanket denial."""
    reset_gate_state()
    lease = make_candidate_lease("custom_ext_reader", PROD_KEY, writes=None, network=None)
    lease["zero_trust_behavior"] = "strip"
    lease["signature"] = cl.sign({**lease, "signature": ""}, PROD_KEY)
    admitted, decisions = gate.enforce(
        {"custom_ext_reader"}, base_ctx(zero_trust_behavior="none", candidate_leases=[lease]), 0, prod_resolver
    )
    check("zt1_signed_strip_safe_tool_admitted", "custom_ext_reader" in admitted, admitted)


def test_zt1_signed_strip_denied_through_switchboard_chokepoint():
    """Same finding, exercised THROUGH switchboard._admit_tool_call (flag
    ON) to prove the wiring end-to-end, not just enforce() in isolation."""
    import switchboard as swb

    reset_gate_state()
    original_flag = swb.CAPABILITY_LEASE_ENFORCEMENT
    swb.CAPABILITY_LEASE_ENFORCEMENT = True
    original_resolver = cl.resolve_key
    cl.resolve_key = prod_resolver
    original_ctx_fn = swb._capability_lease_request_ctx
    lease = _signed_strip_writer_lease()
    try:
        swb._capability_lease_request_ctx = lambda: {
            "zero_trust_behavior": "none",  # inherited ctx says none...
            "candidate_leases": [lease],  # ...but the lease is signed strip
            "bundle_tools": set(_swb._TOOL_LEASE_PRIORITY.keys()),
        }
        admitted, decision = swb._admit_tool_call("custom_ext_writer", {"custom_ext_writer"})
        check("zt1_switchboard_chokepoint_denies_signed_strip", admitted is False,
              f"admitted={admitted} decision={decision}")
        check("zt1_switchboard_chokepoint_marks_stripped",
              bool(decision and decision.get("zero_trust_stripped") is True), decision)
    finally:
        swb.CAPABILITY_LEASE_ENFORCEMENT = original_flag
        cl.resolve_key = original_resolver
        swb._capability_lease_request_ctx = original_ctx_fn
        reset_gate_state()


# --------------------------------------------------------------------------
# 6. (codex-1) Epoch bump revokes first-party leases; NOT auto-reissued
# --------------------------------------------------------------------------


def test_codex1_epoch_bump_revokes_and_does_not_auto_reissue():
    reset_gate_state()
    admitted0, decisions0 = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
    check("codex1_admitted_at_epoch_0", "run_command" in admitted0, admitted0)
    lease_id_epoch0 = next(d for d in decisions0 if d["tool"] == "run_command")["lease_id"]

    admitted1, decisions1 = gate.enforce({"run_command"}, base_ctx(), 1, prod_resolver)
    check("codex1_denied_after_epoch_bump", "run_command" not in admitted1, admitted1)

    # Call again at the bumped epoch WITHOUT resetting the cache — must
    # still be denied (no silent self-healing reissue).
    admitted2, decisions2 = gate.enforce({"run_command"}, base_ctx(), 1, prod_resolver)
    check("codex1_still_denied_second_call_no_auto_reissue", "run_command" not in admitted2, admitted2)
    d2 = next(d for d in decisions2 if d["tool"] == "run_command")
    check("codex1_same_stale_lease_id_not_reissued", d2["lease_id"] == lease_id_epoch0,
          f"{d2['lease_id']} != {lease_id_epoch0}")

    # Only an EXPLICIT reissue (deliberate operator act) restores admission.
    gate.reset_first_party_lease_cache()
    admitted3, decisions3 = gate.enforce({"run_command"}, base_ctx(), 1, prod_resolver)
    check("codex1_admitted_after_deliberate_reissue", "run_command" in admitted3, admitted3)
    reset_gate_state()


# --------------------------------------------------------------------------
# 7. (codex-2) Bidirectional manifest<->bundle equality
# --------------------------------------------------------------------------


def test_codex2_bundle_tool_missing_from_manifest_fails_closed():
    reset_gate_state()
    extra_bundle_tools = set(BUNDLE_TOOLS) | {"brand_new_bundle_tool_not_in_manifest"}
    admitted, decisions = gate.enforce(
        {"run_command", "git_status"}, base_ctx(bundle_tools=extra_bundle_tools), 0, prod_resolver
    )
    check("codex2_bundle_extra_tool_fails_closed_run_command", "run_command" not in admitted, admitted)
    check("codex2_bundle_extra_tool_fails_closed_git_status", "git_status" not in admitted, admitted)
    reset_gate_state()


def test_codex2_manifest_tool_absent_from_bundles_fails_closed():
    reset_gate_state()
    shrunk_bundle_tools = set(BUNDLE_TOOLS) - {"run_command"}
    admitted, decisions = gate.enforce(
        {"run_command", "git_status"}, base_ctx(bundle_tools=shrunk_bundle_tools), 0, prod_resolver
    )
    check("codex2_manifest_extra_tool_fails_closed_run_command", "run_command" not in admitted, admitted)
    check("codex2_manifest_extra_tool_fails_closed_git_status_too", "git_status" not in admitted, admitted)
    reset_gate_state()


def test_codex2_equality_check_function_directly():
    check("codex2_equal_sets_pass", gate.check_manifest_bundle_equality({"a", "b"}, {"a", "b"}) is True)
    check("codex2_missing_from_manifest_fails", gate.check_manifest_bundle_equality({"a"}, {"a", "b"}) is False)
    check("codex2_extra_in_manifest_fails", gate.check_manifest_bundle_equality({"a", "b"}, {"a"}) is False)


# --------------------------------------------------------------------------
# 8. (BLOCKING FINDING 2 / codex-3) Bound-metadata manifest<->signed-lease
#    mismatch — the manifest is a tamper/drift TRIPWIRE only: it may DENY on
#    divergence from the already-issued signed lease, it may never SUPPLY
#    the risk decision. Prior behavior (pre-fix) silently trusted the cached
#    signed lease and ignored manifest drift entirely — that is exactly the
#    vulnerability this test now asserts is closed: any divergence between
#    the currently-validated manifest entry and the lease's own signed
#    bound metadata must DENY, one independent case per named category in
#    the C2-AMENDMENT acceptance list (network/write/exec/secret/delegate)
#    plus the additional bound fields the reviewer flagged (trust_tier,
#    constraints, resources, zero_trust_behavior).
# --------------------------------------------------------------------------

_METADATA_TAMPER_CASES = [
    ("network_capable", "delegate_to_remote", lambda e: e.__setitem__("network_capable", not e["network_capable"])),
    ("write_capable", "write_file", lambda e: e.__setitem__("write_capable", not e["write_capable"])),
    ("exec_capable", "run_command", lambda e: e.__setitem__("exec_capable", not e["exec_capable"])),
    ("secret", "store_memory", lambda e: e.__setitem__("write_capable", not e["write_capable"])),
    ("delegate", "prsi_orchestrate", lambda e: e.__setitem__("write_capable", not e["write_capable"])),
    ("trust_tier", "read_file", lambda e: e.__setitem__("trust_tier", int(e["trust_tier"]) + 1)),
    ("constraints", "read_file", lambda e: e["constraints"].update({"tampered": True})),
    ("resources", "read_file", lambda e: e["resources"].append("tampered-resource")),
    ("zero_trust_behavior", "read_file", lambda e: e.__setitem__("zero_trust_behavior", "strip")),
]


def test_codex3_manifest_metadata_mismatch_denies_admission_per_category():
    for category, tool, mutate in _METADATA_TAMPER_CASES:
        reset_gate_state()
        # Issue first-party leases from the REAL (untampered) manifest first
        # — this is the "already issued, cached" state a running switchboard
        # would be in.
        gate.issue_first_party_leases(PROD_KEY, current_epoch=0)

        # Now mutate the ON-DISK manifest's bound-metadata field for this
        # tool and reload the manifest — but do NOT reissue leases (the
        # cache from before tampering stays authoritative, exactly like a
        # long-running process would). The cached SIGNED lease no longer
        # matches the currently-validated manifest entry -> must DENY.
        tampered_manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        for entry in tampered_manifest_data["tools"]:
            if entry["tool"] == tool:
                mutate(entry)
        tampered_path = Path(f"/tmp/claude-1000/-home-hyperd-Documents-NixOS-Dev-Quick-Deploy/950b6117-9357-4df4-bbed-8db89ba9d4cf/scratchpad/tampered-manifest-meta-{category}.json")
        tampered_path.parent.mkdir(parents=True, exist_ok=True)
        tampered_path.write_text(json.dumps(tampered_manifest_data), encoding="utf-8")
        # Force _load_manifest to see the tampered file at its DEFAULT path
        # by monkeypatching the default path for this call only.
        original_default = gate.DEFAULT_MANIFEST_PATH
        gate.DEFAULT_MANIFEST_PATH = tampered_path
        gate.reset_manifest_cache()  # manifest reloads (tampered); lease cache does NOT
        try:
            admitted, decisions = gate.enforce({tool}, base_ctx(), 0, prod_resolver)
            check(
                f"codex3_meta_mismatch_{category}_denied",
                tool not in admitted,
                f"tool={tool} admitted={tool in admitted}",
            )
            d = next(d for d in decisions if d["tool"] == tool)
            check(
                f"codex3_meta_mismatch_{category}_reason",
                d["reason"] == "bound-metadata-manifest-mismatch",
                d,
            )
        finally:
            gate.DEFAULT_MANIFEST_PATH = original_default
            gate.reset_manifest_cache()
            reset_gate_state()


def test_codex3_untampered_manifest_still_admits():
    """Control: with NO tampering, the same first-party tools admit
    normally — proves the mismatch tripwire above fires on real divergence,
    not on every call."""
    reset_gate_state()
    admitted, decisions = gate.enforce(
        {"delegate_to_remote", "write_file", "run_command", "store_memory", "prsi_orchestrate", "read_file"},
        base_ctx(),
        0,
        prod_resolver,
    )
    check(
        "codex3_untampered_all_admitted",
        admitted == {"delegate_to_remote", "write_file", "run_command", "store_memory", "prsi_orchestrate", "read_file"},
        admitted,
    )
    reset_gate_state()


def test_codex3_lease_manifest_lookup_mismatch_fails_closed():
    reset_gate_state()
    gate.issue_first_party_leases(PROD_KEY, current_epoch=0)
    # Corrupt the cached lease's bound actions so it no longer claims the
    # tool it's stored under (simulated corruption / key mismatch).
    corrupted = copy.deepcopy(gate._FIRST_PARTY_LEASE_CACHE)
    corrupted["run_command"]["permissions"]["actions"] = ["read_file"]
    gate._FIRST_PARTY_LEASE_CACHE = corrupted
    try:
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("codex3_lease_lookup_mismatch_fails_closed", "run_command" not in admitted, admitted)
        d = next(d for d in decisions if d["tool"] == "run_command")
        check("codex3_lease_lookup_mismatch_reason", d["reason"] == "lease-manifest-mismatch", d)
    finally:
        reset_gate_state()


# --------------------------------------------------------------------------
# 9. (codex-4) First-party DEV-key regression
# --------------------------------------------------------------------------


def test_codex4_first_party_dev_key_degrades():
    reset_gate_state()
    # A first-party lease genuinely, validly signed under the DEV key.
    gate.issue_first_party_leases(cl.DEV_SIGNING_KEY, current_epoch=0)
    dev_leases = gate._FIRST_PARTY_LEASE_CACHE
    assert dev_leases["run_command"]["signature"] == cl.sign(
        {**dev_leases["run_command"], "signature": ""}, cl.DEV_SIGNING_KEY
    ), "fixture sanity: lease must genuinely verify under the DEV key"
    admitted, decisions = gate.enforce({"run_command", "git_status"}, base_ctx(), 0, dev_resolver)
    check("codex4_dev_first_party_lease_not_admitted", "run_command" not in admitted, admitted)
    check("codex4_dev_degrade_still_admits_safe_read", "git_status" in admitted, admitted)
    for d in decisions:
        check(f"codex4_decision_degraded_{d['tool']}", d["degraded"] is True, d)
    reset_gate_state()


# --------------------------------------------------------------------------
# 10. (S-a) Unresolvable epoch source -> degrade
# --------------------------------------------------------------------------


def test_unresolvable_epoch_degrades():
    reset_gate_state()
    admitted, decisions = gate.enforce(
        {"run_command", "git_status"}, base_ctx(), "not-a-number-and-not-a-file", prod_resolver
    )
    check("unresolvable_epoch_denies_privileged", "run_command" not in admitted, admitted)
    check("unresolvable_epoch_admits_safe_read", "git_status" in admitted, admitted)
    for d in decisions:
        check(f"unresolvable_epoch_decision_degraded_{d['tool']}", d["degraded"] is True, d)


def test_resolve_current_epoch_helper():
    check("epoch_int_passthrough", gate.resolve_current_epoch(5) == 5)
    check("epoch_callable", gate.resolve_current_epoch(lambda: 7) == 7)
    check("epoch_bad_string_none", gate.resolve_current_epoch("garbage-not-int-not-file") is None)
    check("epoch_bool_rejected", gate.resolve_current_epoch(True) is None)


# --------------------------------------------------------------------------
# 11. (S-c) Gate-internal exception fails closed
# --------------------------------------------------------------------------


def test_gate_internal_exception_fails_closed():
    reset_gate_state()
    original = gate._load_manifest
    gate._load_manifest = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("simulated internal failure"))
    try:
        admitted, decisions = gate.enforce({"run_command", "git_status"}, base_ctx(), 0, prod_resolver)
        check("gate_exception_denies_everything", admitted == set(), admitted)
        for d in decisions:
            check(f"gate_exception_reason_{d['tool']}", d["reason"].startswith("gate-exception:"), d)
    finally:
        gate._load_manifest = original
        reset_gate_state()


# --------------------------------------------------------------------------
# 12. (finding 5) The decision schema is actually validated by the suite,
#     not just asserted to exist. Prefers `jsonschema`; falls back to a
#     minimal required-keys/enum check if it isn't importable.
# --------------------------------------------------------------------------


def _validate_decision_against_schema(decision: dict) -> tuple[bool, str]:
    try:
        import jsonschema  # type: ignore

        schema = json.loads(DECISION_SCHEMA_PATH.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=decision, schema=schema)
            return True, ""
        except jsonschema.ValidationError as exc:  # noqa: BLE001
            return False, str(exc)
    except ImportError:
        required = {"ts", "tool", "decision", "source", "reason", "degraded", "zero_trust_stripped", "lease_id"}
        missing = required - set(decision.keys())
        if missing:
            return False, f"missing keys: {missing}"
        if decision["decision"] not in ("admit", "deny"):
            return False, f"bad decision enum: {decision['decision']}"
        if decision["source"] not in ("candidate", "first-party", "degrade", None):
            return False, f"bad source enum: {decision['source']}"
        if not isinstance(decision["degraded"], bool) or not isinstance(decision["zero_trust_stripped"], bool):
            return False, "degraded/zero_trust_stripped must be bool"
        return True, ""


def test_decision_schema_validates_admit_deny_degrade():
    reset_gate_state()

    # ADMIT
    _, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
    admit_decision = next(d for d in decisions if d["tool"] == "run_command")
    check("decision_schema_admit_decision_field", admit_decision["decision"] == "admit", admit_decision)
    ok, detail = _validate_decision_against_schema(admit_decision)
    check("decision_schema_validates_admit", ok, detail)
    reset_gate_state()

    # DENY
    _, decisions = gate.enforce({"totally_unknown_tool"}, base_ctx(), 0, prod_resolver)
    deny_decision = next(d for d in decisions if d["tool"] == "totally_unknown_tool")
    check("decision_schema_deny_decision_field", deny_decision["decision"] == "deny", deny_decision)
    ok, detail = _validate_decision_against_schema(deny_decision)
    check("decision_schema_validates_deny", ok, detail)
    reset_gate_state()

    # DEGRADE
    lease = make_candidate_lease("custom_ext_tool", cl.DEV_SIGNING_KEY)
    _, decisions = gate.enforce({"custom_ext_tool"}, base_ctx(candidate_leases=[lease]), 0, dev_resolver)
    degrade_decision = next(d for d in decisions if d["tool"] == "custom_ext_tool")
    check("decision_schema_degrade_flag", degrade_decision["degraded"] is True, degrade_decision)
    ok, detail = _validate_decision_against_schema(degrade_decision)
    check("decision_schema_validates_degrade", ok, detail)
    reset_gate_state()


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

_TESTS = [
    test_flag_off_parity,
    test_flag_on_but_gate_import_broken_fails_closed_not_open,
    test_b1_privileged_tool_dropped_without_lease_via_switchboard,
    test_b1_normal_request_admits_run_command_via_first_party_lease,
    test_deny_closed_no_lease,
    test_deny_closed_expired_candidate_lease,
    test_deny_closed_tampered_candidate_lease,
    test_deny_closed_epoch_stale_candidate_lease,
    test_b2_dev_key_degrades_never_admits_privileged,
    test_strip_drops_privileged_first_party_tools_keeps_safe_read,
    test_strip_candidate_lease_also_drops_privileged,
    test_zt1_signed_strip_lease_denied_even_when_ctx_says_none,
    test_zt1_signed_strip_lease_denied_when_ctx_passes_boolean_false,
    test_zt1_signed_strip_lease_denied_when_ctx_omits_key,
    test_zt1_signed_strip_safe_tool_still_admitted,
    test_zt1_signed_strip_denied_through_switchboard_chokepoint,
    test_codex1_epoch_bump_revokes_and_does_not_auto_reissue,
    test_codex2_bundle_tool_missing_from_manifest_fails_closed,
    test_codex2_manifest_tool_absent_from_bundles_fails_closed,
    test_codex2_equality_check_function_directly,
    test_codex3_manifest_metadata_mismatch_denies_admission_per_category,
    test_codex3_untampered_manifest_still_admits,
    test_codex3_lease_manifest_lookup_mismatch_fails_closed,
    test_codex4_first_party_dev_key_degrades,
    test_unresolvable_epoch_degrades,
    test_resolve_current_epoch_helper,
    test_gate_internal_exception_fails_closed,
    test_decision_schema_validates_admit_deny_degrade,
]


def main() -> None:
    for test_fn in _TESTS:
        try:
            test_fn()
        except Exception as exc:  # noqa: BLE001 — surface as a failed check, not a crash
            check(test_fn.__name__, False, f"raised {type(exc).__name__}: {exc}")
        finally:
            reset_gate_state()
    _report_and_exit()


if __name__ == "__main__":
    main()
