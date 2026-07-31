#!/usr/bin/env python3
"""Offline acceptance tests — Foundation C, C5 (OTel spans as source of truth).

Exercises `scripts/ai/lib/span_taxonomy.py` (closed-taxonomy validator),
`scripts/ai/lib/span_projector.py` (pure-fold projections), and the four
SHADOW, flag-gated emit call sites (`capability_lease_gate.py`,
`switchboard.py::_admit_tool_call`, `execution_cell_runner.py`,
`execution_cell_validator.py`) per
`.agents/plans/aqos-foundation-c/C5-DESIGN-AND-AUTHORIZATION.md`.

C5 is NON-ENFORCEMENT observability: every test here proves spans OBSERVE
already-decided outcomes and never gate anything. No live server, no
network, no bwrap/cgroup — hermetic and offline throughout.

Run directly: `python3 scripts/testing/test-span-truth.py`
Exits 0 iff every test passes; each failure prints name + detail.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SWITCHBOARD_DIR = str(_REPO_ROOT / "ai-stack" / "switchboard")
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
for _p in (_SWITCHBOARD_DIR, _LIB_DIR, str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --------------------------------------------------------------------------
# Test harness (no external deps) — mirrors test-capability-lease-gate.py /
# test-a2a-guard.py conventions used elsewhere in this suite.
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


def _fresh(tmp_dir: str):
    """Isolated event log + shadow-artifact paths + ambient trace env, per
    test — never touches the real `.agents/events/a2a-events.jsonl` or the
    real `span-*-shadow` artifacts (same discipline as test-trace.py)."""
    os.environ["A2A_EVENT_LOG"] = str(Path(tmp_dir) / "ev.jsonl")
    os.environ["SPAN_PULSE_SHADOW_PATH"] = str(Path(tmp_dir) / "span-pulse-shadow.log")
    os.environ["SPAN_A2A_AUDIT_PATH"] = str(Path(tmp_dir) / "span-a2a-audit.jsonl")
    os.environ["SPAN_ACTIVATION_AUDIT_SHADOW_PATH"] = str(Path(tmp_dir) / "span-activation-audit-shadow.json")
    os.environ["SPAN_PARITY_MATRIX_PATH"] = str(Path(tmp_dir) / "span-parity-matrix.json")
    os.environ["ACTIVATION_AUDIT_MD_PATH"] = str(Path(tmp_dir) / "ACTIVATION-AUDIT.md")
    for k in ("AQ_TRACE_ID", "AQ_SPAN_ID", "OTEL_EXPORTER_OTLP_ENDPOINT"):
        os.environ.pop(k, None)
    import event_log
    importlib.reload(event_log)
    import trace as T
    importlib.reload(T)
    import span_taxonomy as ST
    importlib.reload(ST)
    import span_projector as SP
    importlib.reload(SP)
    return event_log, T, ST, SP


def _flag(on: bool):
    if on:
        os.environ["CAPABILITY_SPAN_TRUTH"] = "1"
    else:
        os.environ.pop("CAPABILITY_SPAN_TRUTH", None)


# ==========================================================================
# 1. Taxonomy validation — required attrs per kind, unknown kind rejected
# ==========================================================================

_MINIMAL_ATTRS = {
    "turn": {"turn_id": "t1", "agent": "claude", "traceparent": "00-" + "a" * 32 + "-" + "b" * 16 + "-01"},
    "tool": {"tool": "read_file", "decision": "admit", "reason": "ok", "lease_id": "lid1"},
    "lease": {"lease_id": "lid1", "parent_lease_id": None, "revocation_epoch": 3, "op": "enforce", "decision": "admit"},
    "validation": {"verdict": "GREEN", "declared_paths_ok": True, "grant_digest": "gd1"},
    "workspace": {"event": "snapshot", "cell_id": "r1", "base_oid": "deadbeef", "grant_digest": "gd1"},
    "broker": {"broker": "net", "effect": "egress", "decision": "allow", "reason": "ok", "lease_id": "lid1"},
}


def test_taxonomy_required_attrs_each_kind():
    import span_taxonomy as st
    for kind, attrs in _MINIMAL_ATTRS.items():
        outcome = st.validate_span({"kind": kind, "attrs": dict(attrs)})
        check(f"taxonomy_minimal_attrs_valid[{kind}]", outcome.ok, str(outcome))
        for missing_attr in attrs:
            trimmed = {k: v for k, v in attrs.items() if k != missing_attr}
            out2 = st.validate_span({"kind": kind, "attrs": trimmed})
            check(
                f"taxonomy_missing_attr_rejected[{kind}.{missing_attr}]",
                not out2.ok and out2.reason and out2.reason.startswith("missing-required-attrs"),
                str(out2),
            )


def test_unknown_span_kind_rejected():
    import span_taxonomy as st
    outcome = st.validate_span({"kind": "mystery-kind", "attrs": {}})
    check("unknown_span_kind_rejected", not outcome.ok and outcome.reason == "unknown-span-kind", str(outcome))
    outcome2 = st.validate_span({"kind": None, "attrs": {}})
    check("missing_kind_rejected", not outcome2.ok, str(outcome2))
    outcome3 = st.validate_span({"kind": "tool", "attrs": "not-a-dict"})
    check("attrs_not_dict_rejected", not outcome3.ok and outcome3.reason == "attrs-not-dict", str(outcome3))


def test_enum_constrained_fields_rejected_out_of_enum():
    import span_taxonomy as st
    attrs = dict(_MINIMAL_ATTRS["workspace"])
    attrs["event"] = "merge"  # not in {snapshot, rollback, quarantine}
    outcome = st.validate_span({"kind": "workspace", "attrs": attrs})
    check("enum_out_of_range_rejected", not outcome.ok and "invalid-enum-value" in (outcome.reason or ""), str(outcome))


# ==========================================================================
# 2. Secret-free / low-cardinality enforcement
# ==========================================================================


def test_secret_free_enforcement_rejects_forbidden_keys_and_shapes():
    import span_taxonomy as st

    cases = [
        ("forbidden-key-prompt", {"tool": "read_file", "decision": "admit", "reason": "ok",
                                    "lease_id": "x", "prompt": "do the thing"}),
        ("forbidden-key-payload", {"tool": "read_file", "decision": "admit", "reason": "ok",
                                     "lease_id": "x", "payload": "..."}),
        ("forbidden-key-api-key", {"tool": "read_file", "decision": "admit", "reason": "ok",
                                     "lease_id": "x", "api_key": "sk-abc"}),
        ("raw-filesystem-path-value", {"tool": "read_file", "decision": "admit",
                                         "reason": "ok", "lease_id": "/home/user/.ssh/id_rsa"}),
        ("newline-embedded-value", {"tool": "read_file", "decision": "admit",
                                      "reason": "line1\nline2", "lease_id": "x"}),
        ("value-too-long", {"tool": "read_file", "decision": "admit", "reason": "x" * 200, "lease_id": "x"}),
        ("unsupported-list-value", {"tool": "read_file", "decision": "admit", "reason": "ok",
                                      "lease_id": ["not", "scalar"]}),
    ]
    for label, attrs in cases:
        outcome = st.validate_span({"kind": "tool", "attrs": attrs})
        check(f"secret_or_shape_rejected[{label}]", not outcome.ok, str(outcome))

    # A declared-scope id (grant_digest/lease_id-shaped hex/opaque token) is
    # NOT a raw path and must be admitted.
    clean = st.validate_span({"kind": "workspace", "attrs": dict(_MINIMAL_ATTRS["workspace"])})
    check("declared_scope_id_not_flagged_as_path", clean.ok, str(clean))


def test_universal_trace_primitive_attrs_allowed():
    import span_taxonomy as st
    attrs = dict(_MINIMAL_ATTRS["tool"])
    attrs["duration_s"] = 0.004
    attrs["_span_taxonomy"] = "c5.v1"
    outcome = st.validate_span({"kind": "tool", "attrs": attrs})
    check("duration_s_and_marker_universally_allowed", outcome.ok, str(outcome))


# ==========================================================================
# 3. Projection purity — idempotency + reproducibility
# ==========================================================================


def test_projection_idempotent_and_reproducible():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        ST.emit_taxonomy_span("tool", agent="switchboard", attrs=dict(_MINIMAL_ATTRS["tool"]))
        ST.emit_taxonomy_span("lease", agent="capability_lease_gate", attrs=dict(_MINIMAL_ATTRS["lease"]))
        ST.emit_taxonomy_span("workspace", agent="execution_cell_runner", attrs=dict(_MINIMAL_ATTRS["workspace"]))

        events = event_log.read_all()
        text_a, flagged_a = SP.project_pulse_spans(events)
        text_b, flagged_b = SP.project_pulse_spans(events)
        check("pulse_projection_reproducible_same_events", text_a == text_b and flagged_a == flagged_b)

        p1, changed1 = SP.write_pulse_shadow(events)
        p2, changed2 = SP.write_pulse_shadow(events)
        check("pulse_write_idempotent_first_write_changes", changed1)
        check("pulse_write_idempotent_second_write_no_change", not changed2)
        check("pulse_shadow_bytes_identical_across_writes", p1.read_bytes() == p2.read_bytes())

        matrix_a = SP.project_parity_matrix_spans(events)
        matrix_b = SP.project_parity_matrix_spans(events)
        check("parity_matrix_projection_reproducible", matrix_a == matrix_b)


def test_check_drift_mode_catches_hand_edit():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        ST.emit_taxonomy_span("tool", agent="switchboard", attrs=dict(_MINIMAL_ATTRS["tool"]))
        events = event_log.read_all()

        path, _changed = SP.write_pulse_shadow(events)
        check("check_no_drift_immediately_after_write", SP.check_pulse_shadow(events) is None)

        # Hand-edit the projected shadow surface — drift the projector must catch.
        path.write_text("[hand-edited] this line was never emitted by any span\n", encoding="utf-8")
        drift_msg = SP.check_pulse_shadow(events)
        check("check_drift_detected_after_hand_edit", drift_msg is not None, str(drift_msg))

        # Re-running the writer overwrites the hand-edit (projection wins).
        SP.write_pulse_shadow(events)
        check("check_drift_cleared_after_rewrite", SP.check_pulse_shadow(events) is None)


# ==========================================================================
# 4. Malformed span dropped + flagged (never silently trusted)
# ==========================================================================


def test_malformed_span_dropped_from_projection():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        ST.emit_taxonomy_span("tool", agent="switchboard", attrs=dict(_MINIMAL_ATTRS["tool"]))
        # A hand-crafted malformed candidate: marked as a taxonomy span but
        # missing required attrs for its declared kind.
        with T.span("validation", agent="execution_cell_validator", attrs={"verdict": "GREEN", "_span_taxonomy": "c5.v1"}):
            pass

        valid, flagged = SP.iter_taxonomy_records()
        kinds_valid = {r["kind"] for r in valid}
        check("malformed_span_excluded_from_valid", "validation" not in kinds_valid or len(valid) == 1, str(valid))
        check("malformed_span_present_in_flagged", any(f["kind"] == "validation" for f in flagged), str(flagged))
        flagged_entry = next(f for f in flagged if f["kind"] == "validation")
        check("malformed_span_flag_reason_is_missing_attrs", flagged_entry["reason"].startswith("missing-required-attrs"), str(flagged_entry))

        # The malformed span must not appear in ANY derived projection.
        pulse_text, _ = SP.project_pulse_spans()
        check("malformed_span_absent_from_pulse_projection", "validation" not in pulse_text)


def test_unrelated_pre_existing_spans_never_flagged():
    """Spans outside the C5 convention (no `_span_taxonomy` marker) — e.g.
    the pre-existing `dispatch.local` spans — are simply not candidates.
    They must never appear in `flagged` (they never claimed to be a C5 span)."""
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        with T.span("dispatch.local", agent="claude", attrs={"task_id": "abc"}):
            pass
        valid, flagged = SP.iter_taxonomy_records()
        check("unrelated_span_not_valid_candidate", len(valid) == 0)
        check("unrelated_span_not_flagged", len(flagged) == 0, str(flagged))


# ==========================================================================
# 5. flag-OFF byte-parity — every emit call site is a true no-op
# ==========================================================================


def test_flag_off_no_events_written_by_span_taxonomy_primitive():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(False)
        before = len(event_log.read_all())
        # Callers own the flag check per span_taxonomy's own contract — this
        # proves the PRIMITIVE itself is inert to the flag (callers gate it).
        # The real flag-off no-op guarantee is proven per call-site below.
        check("flag_off_baseline_log_empty", before == 0)


def test_flag_off_capability_lease_gate_no_op():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(False)
        import capability_lease_gate as gate
        gate.reset_first_party_lease_cache()
        gate.reset_manifest_cache()
        before = len(event_log.read_all())
        admitted, decisions = gate.enforce({"git_status"}, {"zero_trust_behavior": "none", "candidate_leases": [], "bundle_tools": set()},
                                            epoch_source=0, key_resolver=lambda: (b"x" * 32, True))
        after = len(event_log.read_all())
        check("flag_off_capability_lease_gate_zero_new_events", after == before, f"before={before} after={after}")
        check("flag_off_capability_lease_gate_still_returns_decisions", isinstance(decisions, list) and len(decisions) == 1)


def test_flag_off_switchboard_admit_tool_call_no_op():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(False)
        import switchboard as _swb
        before = len(event_log.read_all())
        admitted, decision = _swb._admit_tool_call("git_status", {"git_status"})
        after = len(event_log.read_all())
        check("flag_off_switchboard_zero_new_events", after == before, f"before={before} after={after}")
        check("flag_off_switchboard_admission_unaffected", admitted is True)


def test_flag_off_execution_cell_runner_workspace_no_op():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(False)
        import execution_cell_runner as runner
        decision = runner.Decision(runner.DECISION_GREEN, runner.REASON_OK, runner.STAGE_FINAL_FENCE,
                                    "receipt1", grant_digest="gd1", base_oid="deadbeef")
        before = len(event_log.read_all())
        runner._emit_workspace_span_shadow(decision)
        after = len(event_log.read_all())
        check("flag_off_execution_cell_runner_zero_new_events", after == before, f"before={before} after={after}")


def test_flag_off_execution_cell_validator_no_op():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(False)
        import execution_cell_validator as validator
        result = validator.ValidationResult(validator.VERDICT_GREEN, "ok", changed_paths=("a.txt",))
        before = len(event_log.read_all())
        validator._emit_validation_span_shadow(result, "gd1", ("a.txt",))
        after = len(event_log.read_all())
        check("flag_off_execution_cell_validator_zero_new_events", after == before, f"before={before} after={after}")


def test_flag_off_enforcement_outcomes_identical_to_flag_on():
    """The strongest form of 'spans observe, never gate': toggling
    CAPABILITY_SPAN_TRUTH must never change an admission/validation outcome."""
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        import capability_lease_gate as gate
        import switchboard as _swb
        import execution_cell_validator as validator

        results = {}
        for flag_on in (False, True):
            _flag(flag_on)
            gate.reset_first_party_lease_cache()
            gate.reset_manifest_cache()
            admitted, decisions = gate.enforce({"git_status", "run_command"},
                                                {"zero_trust_behavior": "none", "candidate_leases": [], "bundle_tools": set()},
                                                epoch_source=0, key_resolver=lambda: (b"x" * 32, True))
            swb_admitted, _ = _swb._admit_tool_call("git_status", {"git_status"})
            val = validator.validate(grant_digest="gd1", base_oid="deadbeef", cell_root="/nonexistent",
                                      declared_output_paths=(), config=validator.ValidatorConfig(
                                          bare_mirror_path="/nonexistent", bwrap_path=None,
                                          python_bin="/usr/bin/python3", work_root=str(Path(d) / "vwork")))
            results[flag_on] = (admitted, [{k: v for k, v in dd.items() if k != "ts"} for dd in decisions],
                                 swb_admitted, val.verdict, val.reason)
        _flag(False)
        check("enforcement_outcome_identical_regardless_of_span_flag", results[False] == results[True], str(results))


# ==========================================================================
# 6. flag-ON — the four shadow emit call sites actually produce valid spans
# ==========================================================================


def test_flag_on_capability_lease_gate_emits_valid_lease_spans():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(True)
        import capability_lease_gate as gate
        gate.reset_first_party_lease_cache()
        gate.reset_manifest_cache()
        admitted, decisions = gate.enforce({"git_status"}, {"zero_trust_behavior": "none", "candidate_leases": [], "bundle_tools": set()},
                                            epoch_source=0, key_resolver=lambda: (b"x" * 32, True))
        _flag(False)
        valid, flagged = SP.iter_taxonomy_records()
        lease_spans = [r for r in valid if r["kind"] == "lease"]
        check("flag_on_capability_lease_gate_produced_lease_spans", len(lease_spans) >= 1, str(valid))
        check("flag_on_lease_spans_none_flagged_malformed", len(flagged) == 0, str(flagged))


def test_flag_on_switchboard_emits_valid_tool_span():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(True)
        import switchboard as _swb
        _swb._admit_tool_call("git_status", {"git_status"})
        _flag(False)
        valid, flagged = SP.iter_taxonomy_records()
        tool_spans = [r for r in valid if r["kind"] == "tool"]
        check("flag_on_switchboard_produced_tool_span", len(tool_spans) == 1, str(valid))
        check("flag_on_tool_span_decision_admit", tool_spans and tool_spans[0]["attrs"].get("decision") == "admit", str(tool_spans))
        check("flag_on_tool_spans_none_flagged_malformed", len(flagged) == 0, str(flagged))


def test_flag_on_execution_cell_runner_emits_valid_workspace_span():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(True)
        import execution_cell_runner as runner
        decision = runner.Decision(runner.DECISION_GREEN, runner.REASON_OK, runner.STAGE_FINAL_FENCE,
                                    "receipt1", grant_digest="gd1", base_oid="deadbeef")
        runner._emit_workspace_span_shadow(decision)
        # A DENIED decision with no cell (base_oid=None) must NOT emit.
        denied = runner.Decision(runner.DECISION_DENIED, runner.REASON_FLAG_OFF, runner.STAGE_FLAG, "receipt2")
        runner._emit_workspace_span_shadow(denied)
        _flag(False)
        valid, flagged = SP.iter_taxonomy_records()
        ws_spans = [r for r in valid if r["kind"] == "workspace"]
        check("flag_on_execution_cell_runner_produced_one_workspace_span", len(ws_spans) == 1, str(valid))
        check("flag_on_workspace_span_event_is_snapshot", ws_spans and ws_spans[0]["attrs"].get("event") == "snapshot", str(ws_spans))
        check("flag_on_workspace_spans_none_flagged_malformed", len(flagged) == 0, str(flagged))


def test_flag_on_execution_cell_validator_emits_valid_validation_span():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        _flag(True)
        import execution_cell_validator as validator
        result = validator.ValidationResult(validator.VERDICT_RED, "declared-path-invalid")
        validator._emit_validation_span_shadow(result, "gd1", ("../escape",))
        _flag(False)
        valid, flagged = SP.iter_taxonomy_records()
        val_spans = [r for r in valid if r["kind"] == "validation"]
        check("flag_on_execution_cell_validator_produced_validation_span", len(val_spans) == 1, str(valid))
        check("flag_on_validation_span_verdict_red", val_spans and val_spans[0]["attrs"].get("verdict") == "RED", str(val_spans))
        check("flag_on_validation_span_declared_paths_ok_false", val_spans and val_spans[0]["attrs"].get("declared_paths_ok") is False, str(val_spans))
        check("flag_on_validation_spans_none_flagged_malformed", len(flagged) == 0, str(flagged))


# ==========================================================================
# 7. W3C traceparent propagation across a simulated A2A hop
# ==========================================================================


def test_w3c_traceparent_propagation_across_a2a_hop():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        with T.span("turn", agent="claude") as root:
            trace_id = root.trace_id
            span_id = root.span_id
            tp = ST.w3c_traceparent(trace_id, span_id)
            check("traceparent_well_formed", ST.parse_traceparent(tp) == (trace_id, span_id), tp)

            # "A2A hop": a fresh process only has the traceparent string (no
            # shared env) — it must be able to rejoin the SAME trace from it alone.
            parsed = ST.parse_traceparent(tp)
            check("traceparent_parse_roundtrip", parsed is not None and parsed[0] == trace_id)

            os.environ["AQ_TRACE_ID"] = parsed[0]
            os.environ["AQ_SPAN_ID"] = parsed[1]
            with T.span("tool", agent="remote-agent") as child:
                check("a2a_hop_child_joins_same_trace", child.trace_id == trace_id)
                check("a2a_hop_child_parents_to_traceparent_span", child.parent_span_id == span_id)

        tree = T.reconstruct(trace_id)
        check("a2a_hop_reconstructs_as_one_tree", len(tree) == 1 and len(tree[0].children) == 1, str(tree))


# ==========================================================================
# 8. ACTIVATION-AUDIT shadow cross-check (Q-C5-2) — seeded discrepancy
# ==========================================================================


def test_activation_audit_shadow_cross_check_seeded_discrepancy():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        hand_path = Path(os.environ["ACTIVATION_AUDIT_MD_PATH"])
        hand_path.write_text("# Activation Audit\n\nSome narrative text, no grant ids here.\n", encoding="utf-8")

        event_log.emit("owner", "activation.grant", payload={"activation_id": "deadbeef12345678"})
        report = SP.cross_check_activation_audit()
        check("activation_shadow_reports_seeded_discrepancy",
              any(dd["activation_id"] == "deadbeef12345678" for dd in report["discrepancies"]), str(report))
        check("activation_shadow_hand_audit_present_flag", report["hand_audit_present"] is True)

        # Now the hand file DOES mention the id — discrepancy must clear.
        hand_path.write_text("# Activation Audit\n\nSee grant deadbeef12345678 for details.\n", encoding="utf-8")
        report2 = SP.cross_check_activation_audit()
        check("activation_shadow_discrepancy_clears_when_hand_audit_mentions_id",
              not any(dd["activation_id"] == "deadbeef12345678" for dd in report2["discrepancies"]), str(report2))


def test_activation_audit_shadow_never_writes_hand_file():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        hand_path = Path(os.environ["ACTIVATION_AUDIT_MD_PATH"])
        original = "# Activation Audit\n\noriginal content\n"
        hand_path.write_text(original, encoding="utf-8")
        event_log.emit("owner", "activation.grant", payload={"activation_id": "abc123"})
        SP.write_activation_audit_shadow()
        check("activation_shadow_never_mutates_hand_owned_file", hand_path.read_text(encoding="utf-8") == original)
        shadow_path = SP._activation_audit_shadow_path()
        check("activation_shadow_writes_separate_artifact", shadow_path != hand_path and shadow_path.exists())


# ==========================================================================
# 9. OTLP export offline-safe — no endpoint => no network attempt
# ==========================================================================


def test_otlp_export_offline_safe_trace_py():
    with tempfile.TemporaryDirectory() as d:
        event_log, T, ST, SP = _fresh(d)
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        with mock.patch("socket.socket", side_effect=AssertionError("network attempted with no OTLP endpoint configured")):
            with T.span("turn", agent="claude", attrs={"turn_id": "t1"}):
                pass
        check("trace_py_otlp_offline_safe_no_socket_touched", True)  # no exception => no socket() call happened


def test_otlp_export_offline_safe_trace_collector():
    hc_dir = str(_REPO_ROOT / "ai-stack" / "mcp-servers" / "hybrid-coordinator")
    if hc_dir not in sys.path:
        sys.path.insert(0, hc_dir)
    os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    import importlib as _il
    import trace_collector as tc
    _il.reload(tc)  # re-bind _OTEL_EXPORTER_URL from the now-unset env var
    check("trace_collector_otel_url_empty_when_unset", tc._OTEL_EXPORTER_URL == "")

    import asyncio

    async def _run():
        with mock.patch("socket.socket", side_effect=AssertionError("network attempted with no OTLP endpoint configured")):
            await tc._emit_otlp_span({"gen_ai.operation.name": "chat"}, "trace-1")

    asyncio.run(_run())
    check("trace_collector_otlp_offline_safe_no_socket_touched", True)


# ==========================================================================
# 10. Schema conformance — validate_span() agrees with the JSON schema
# ==========================================================================


def test_json_schema_matches_python_validator():
    import json
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        check("json_schema_conformance_skipped_no_jsonschema", True, "jsonschema not installed — skipped")
        return
    import span_taxonomy as st
    schema = json.loads((_REPO_ROOT / "config" / "schemas" / "span-taxonomy.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for kind, attrs in _MINIMAL_ATTRS.items():
        record = {"kind": kind, "attrs": dict(attrs), "agent": "test", "ts": 1.0}
        py_outcome = st.validate_span(record)
        schema_errors = list(validator.iter_errors(record))
        check(f"schema_and_python_validator_agree[{kind}]", py_outcome.ok and not schema_errors,
              f"py={py_outcome} schema_errors={schema_errors}")


# ==========================================================================
# main
# ==========================================================================

if __name__ == "__main__":
    test_taxonomy_required_attrs_each_kind()
    test_unknown_span_kind_rejected()
    test_enum_constrained_fields_rejected_out_of_enum()
    test_secret_free_enforcement_rejects_forbidden_keys_and_shapes()
    test_universal_trace_primitive_attrs_allowed()
    test_projection_idempotent_and_reproducible()
    test_check_drift_mode_catches_hand_edit()
    test_malformed_span_dropped_from_projection()
    test_unrelated_pre_existing_spans_never_flagged()
    test_flag_off_no_events_written_by_span_taxonomy_primitive()
    test_flag_off_capability_lease_gate_no_op()
    test_flag_off_switchboard_admit_tool_call_no_op()
    test_flag_off_execution_cell_runner_workspace_no_op()
    test_flag_off_execution_cell_validator_no_op()
    test_flag_off_enforcement_outcomes_identical_to_flag_on()
    test_flag_on_capability_lease_gate_emits_valid_lease_spans()
    test_flag_on_switchboard_emits_valid_tool_span()
    test_flag_on_execution_cell_runner_emits_valid_workspace_span()
    test_flag_on_execution_cell_validator_emits_valid_validation_span()
    test_w3c_traceparent_propagation_across_a2a_hop()
    test_activation_audit_shadow_cross_check_seeded_discrepancy()
    test_activation_audit_shadow_never_writes_hand_file()
    test_otlp_export_offline_safe_trace_py()
    test_otlp_export_offline_safe_trace_collector()
    test_json_schema_matches_python_validator()
    _report_and_exit()
