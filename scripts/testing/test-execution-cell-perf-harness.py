#!/usr/bin/env python3
"""Offline self-test -- Foundation C C3b R4 execution-cell-perf-harness.

Proves the HARNESS's OWN correctness (`scripts/testing/perf/
execution-cell-perf-harness.py`) per
`.agents/plans/aqos-foundation-c/C3B-R4-DESIGN-AND-AUTHORIZATION.md` §6/§7:
this is NOT the real N>=40 APU acceptance run (that is a separate,
committed-as-evidence operator step, §10) -- it is a FAST, hermetic,
tiny-N/tiny-fixture proof that the harness's own math, gating, and
verdict logic behave correctly, plus one small real
revocation-under-load exercise.

Covers (design §6/§7/§8):
  1. nearest-rank p95 math on known arrays (exact values, not interpolated).
  2. cache-validity gating: a cohort that cannot prove its residency bound
     is reported INVALID, not silently accepted.
  3. the zero-untyped-outcome gate: an unrecognized outcome/denial_code
     fails the gate; an all-known set passes.
  4. invalid-cohort rejection: `compute_verdict` never collapses an
     invalid cohort to PASS/FAIL -- it is always INVALID.
  5. verdict logic: a synthetic over-limit metric -> FAIL(metric,
     measured, limit); an all-within-limits set -> PASS.
  6. real (tiny) cache eviction/priming: `evict_cache`/`prime_cache`/
     `mincore_residency_pct` against a real on-disk fixture actually
     cross the cold (<=5%) / warm (>=95%) thresholds -- not mocked.
  7. a small, real revocation-under-load run (1-2 cells) asserting the
     four §5 properties, R6-deferred-skipped only if this host offers no
     delegated cgroup v2 subtree (never faked).
  8. a small real end-to-end protocol run (tiny N) through the actual R3
     runner over a real UDS, producing a PASS verdict with every
     available metric within budget.

Genuinely systemd-only surfaces this offline harness cannot exercise
(Delegate=true under the real deployed unit, real socket activation) are
R6-canary-deferred and SKIPPED with an explicit note -- never faked, same
precedent as `scripts/testing/test-execution-cell-runner.py`.

Run directly: `python3 scripts/testing/test-execution-cell-perf-harness.py`
Exits 0 iff every non-skipped check passes; prints "N/N passed" plus any
R6-canary-deferred skip count.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HARNESS_PATH = _REPO_ROOT / "scripts" / "testing" / "perf" / "execution-cell-perf-harness.py"


def _load_harness_module():
    """The harness file's name has hyphens (matches repo convention for
    perf-tooling scripts), so it cannot be `import`ed by module path --
    load it directly from its file location instead."""
    spec = importlib.util.spec_from_file_location("aq_c3b_r4_perf_harness", _HARNESS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["aq_c3b_r4_perf_harness"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_harness_module()

# --------------------------------------------------------------------------
# Test harness (no external deps -- matches test-execution-cell-runner.py)
# --------------------------------------------------------------------------

_RESULTS: "list[tuple[str, bool, str]]" = []
_SKIPPED: "list[tuple[str, str]]" = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), detail))


def skip(name: str, note: str) -> None:
    _SKIPPED.append((name, note))


def _report_and_exit() -> None:
    failed = [r for r in _RESULTS if not r[1]]
    for name, ok, detail in _RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    for name, note in _SKIPPED:
        print(f"[SKIP-R6-CANARY-DEFERRED] {name} — {note}")

    print(
        f"\n{len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed"
        f" ({len(_SKIPPED)} R6-canary-deferred skip(s))"
    )
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
        sys.exit(1)
    sys.exit(0)


# --------------------------------------------------------------------------
# 1. Nearest-rank p95 math -- exact values, no interpolation/averaging.
# --------------------------------------------------------------------------


def test_p95_nearest_rank_known_arrays():
    check("p95_empty_is_none", mod.p95_nearest_rank([]) is None)
    check("p95_single_value", mod.p95_nearest_rank([7.0]) == 7.0)

    # 1..100: ceil(0.95*100)=95 -> sorted[94] -> value 95 (1-indexed value
    # equals its own sorted position here since the array is 1..100).
    values = list(range(1, 101))
    check("p95_1_to_100_is_95", mod.p95_nearest_rank([float(v) for v in values]) == 95.0)

    # A frozen worked example from design §4's own formula,
    # sorted[ceil(0.95*N)-1], for N=40: ceil(38.0)=38 -> index 37 (0-based)
    # -> the 38th-smallest of 40 values.
    forty = [float(i) for i in range(1, 41)]
    check("p95_1_to_40_is_38", mod.p95_nearest_rank(forty) == 38.0,
          f"got {mod.p95_nearest_rank(forty)!r}")

    # Never averages: two values that would give a different (interpolated)
    # result under a linear-interpolation percentile must still yield the
    # frozen nearest-rank answer.
    two = [10.0, 20.0]
    check("p95_two_values_nearest_rank", mod.p95_nearest_rank(two) == 20.0,
          f"got {mod.p95_nearest_rank(two)!r} (ceil(0.95*2)=2 -> sorted[1]=20.0, "
          f"NOT a linear-interpolated ~19.5)")

    # Unsorted input must still be sorted internally.
    unsorted = [5.0, 1.0, 100.0, 2.0, 3.0, 4.0]
    check("p95_sorts_before_ranking", mod.p95_nearest_rank(unsorted) == mod.p95_nearest_rank(sorted(unsorted)))


# --------------------------------------------------------------------------
# 2. Cache-validity gating -- a cohort that cannot prove its residency
#    bound is reported INVALID, never silently accepted.
# --------------------------------------------------------------------------


def test_cache_validity_gating():
    # Pure decision function, synthetic percentages (design's own
    # "relaxed/mock limits" self-test posture).
    check("cold_at_0pct_valid", mod.cohort_cache_valid(mod.COHORT_COLD, 0.0) is True)
    check("cold_at_5pct_valid_boundary", mod.cohort_cache_valid(mod.COHORT_COLD, 5.0) is True)
    check("cold_at_5_01pct_invalid", mod.cohort_cache_valid(mod.COHORT_COLD, 5.01) is False)
    check("cold_at_100pct_invalid", mod.cohort_cache_valid(mod.COHORT_COLD, 100.0) is False)
    check("warm_at_100pct_valid", mod.cohort_cache_valid(mod.COHORT_WARM, 100.0) is True)
    check("warm_at_95pct_valid_boundary", mod.cohort_cache_valid(mod.COHORT_WARM, 95.0) is True)
    check("warm_at_94_99pct_invalid", mod.cohort_cache_valid(mod.COHORT_WARM, 94.99) is False)
    check("warm_at_0pct_invalid", mod.cohort_cache_valid(mod.COHORT_WARM, 0.0) is False)

    try:
        mod.cohort_cache_valid("not-a-real-cohort", 0.0)
        check("unknown_cohort_raises", False, "expected ValueError, got no exception")
    except ValueError:
        check("unknown_cohort_raises", True)

    # A cohort whose real residency check fails must surface as an
    # INVALID CohortResult from `run_cohort` -- forced deterministically by
    # patching `verify_cache_cohort` (the harness's own real-I/O function)
    # to report a failing residency for this ONE check, without touching
    # any R1/R2/R3 file.
    harness = mod.PerfHarness(n=2)
    try:
        config = harness._base_config()
        with mod._InstrumentedRunner():
            handle = mod.start_runner_server(config)
            try:
                original = mod.verify_cache_cohort
                mod.verify_cache_cohort = lambda path, cohort: (False, 42.0)
                try:
                    result = harness.run_cohort(handle, mod.COMMAND_NOOP, mod.COHORT_COLD)
                finally:
                    mod.verify_cache_cohort = original
            finally:
                handle.stop()
        check("forced_cache_failure_marks_cohort_invalid", result.valid is False, f"got valid={result.valid}")
        check(
            "forced_cache_failure_reason_mentions_residency",
            "residency" in (result.invalid_reason or "").lower(),
            repr(result.invalid_reason),
        )
    finally:
        mod.cleanup_temp_roots()


# --------------------------------------------------------------------------
# 3. Zero-untyped-outcome gate.
# --------------------------------------------------------------------------


def test_zero_untyped_outcome_gate():
    good_rows = [
        {"sample_index": 0, "outcome": mod.OUTCOME_GREEN, "denial_code": None},
        {"sample_index": 1, "outcome": mod.OUTCOME_DENIED, "denial_code": mod.runner.REASON_FLAG_OFF},
        {"sample_index": 2, "outcome": mod.OUTCOME_RED, "denial_code": mod.runner.REASON_COMMAND_FAILED},
        {"sample_index": 3, "outcome": mod.OUTCOME_QUARANTINED, "denial_code": mod.runner.REASON_TREE_NOT_PROVEN_ABSENT},
        {"sample_index": 4, "outcome": mod.OUTCOME_HARNESS_TRANSPORT, "denial_code": "harness-transport:timeout"},
    ]
    ok, offenders = mod.zero_untyped_outcome_gate(good_rows)
    check("all_known_outcomes_gate_passes", ok is True, repr(offenders))
    check("all_known_outcomes_no_offenders", offenders == [])

    bad_rows = list(good_rows) + [{"sample_index": 5, "outcome": "not-a-real-outcome", "denial_code": None}]
    ok2, offenders2 = mod.zero_untyped_outcome_gate(bad_rows)
    check("unrecognized_outcome_fails_gate", ok2 is False)
    check("unrecognized_outcome_is_reported", any("sample_index=5" in o for o in offenders2), repr(offenders2))

    bad_denial_rows = list(good_rows) + [
        {"sample_index": 6, "outcome": mod.OUTCOME_DENIED, "denial_code": "invented-code-nobody-wrote"}
    ]
    ok3, offenders3 = mod.zero_untyped_outcome_gate(bad_denial_rows)
    check("unrecognized_denial_code_fails_gate", ok3 is False, repr(offenders3))


# --------------------------------------------------------------------------
# 4. Invalid-cohort rejection: compute_verdict never collapses an invalid
#    cohort into PASS/FAIL.
# --------------------------------------------------------------------------


def test_invalid_cohort_never_passes():
    cohorts = [
        mod.CohortResult(command_class=mod.COMMAND_NOOP, cache_cohort=mod.COHORT_COLD, valid=True,
                          successful_samples=40, attempted_samples=40),
        mod.CohortResult(command_class=mod.COMMAND_NOOP, cache_cohort=mod.COHORT_WARM, valid=False,
                          invalid_reason="synthetic: residency check failed", successful_samples=3,
                          attempted_samples=3),
    ]
    verdict = mod.compute_verdict(cohorts, rows=[])
    check("invalid_cohort_status_is_invalid", verdict["status"] == mod.VERDICT_INVALID, verdict)
    check("invalid_cohort_status_is_not_pass", verdict["status"] != mod.VERDICT_PASS)
    check("invalid_cohort_status_is_not_fail", verdict["status"] != mod.VERDICT_FAIL)
    check("invalid_cohort_reported", len(verdict["invalid_cohorts"]) == 1, verdict["invalid_cohorts"])


# --------------------------------------------------------------------------
# 5. Verdict logic: over-limit metric -> FAIL(metric, measured, limit);
#    all-within-limits -> PASS. Budgets are HARD -- never let an over-limit
#    result collapse to PASS.
# --------------------------------------------------------------------------


def _synthetic_green_row(*, clone_latency_s: float, bwrap_latency_s: float, cgroup_peak_bytes, idle_baseline_bytes):
    start = 0.0
    clone_done = start + clone_latency_s * 1e9
    bwrap_started = clone_done + bwrap_latency_s * 1e9
    return {
        "schema_version": mod.SCHEMA_VERSION, "run_id": "synthetic", "host_fingerprint": {}, "kernel": "test",
        "build_revision": "test", "command_class": mod.COMMAND_NOOP, "cache_cohort": mod.COHORT_COLD,
        "cache_residency_pct": 1.0, "sample_index": 0, "monotonic_start_ns": start, "clone_done_ns": clone_done,
        "bwrap_started_ns": bwrap_started, "process_terminal_ns": bwrap_started, "tree_absent_ns": bwrap_started,
        "validation_done_ns": bwrap_started, "receipt_published_ns": bwrap_started,
        "cgroup_peak_bytes": cgroup_peak_bytes, "idle_baseline_bytes": idle_baseline_bytes,
        "mem_available_bytes": 16 * 1024 * 1024 * 1024, "swap_delta_bytes": 0,
        "outcome": mod.OUTCOME_GREEN, "denial_code": None,
    }


def test_verdict_pass_and_fail_logic():
    cohorts_valid = [
        mod.CohortResult(command_class=mod.COMMAND_NOOP, cache_cohort=mod.COHORT_COLD, valid=True,
                          successful_samples=3, attempted_samples=3),
    ]

    within_budget_rows = [
        _synthetic_green_row(clone_latency_s=0.5, bwrap_latency_s=0.010, cgroup_peak_bytes=100 * 1024 * 1024,
                              idle_baseline_bytes=0)
        for _ in range(5)
    ]
    verdict_pass = mod.compute_verdict(cohorts_valid, within_budget_rows,
                                        revocation_result={"teardown_latency_p95_s": 1.0, "all_assertions_passed": True})
    check("all_within_budget_is_pass", verdict_pass["status"] == mod.VERDICT_PASS, verdict_pass)
    check("all_within_budget_no_failures", verdict_pass["failures"] == [], verdict_pass["failures"])

    over_limit_clone_rows = [
        _synthetic_green_row(clone_latency_s=5.0, bwrap_latency_s=0.010, cgroup_peak_bytes=100 * 1024 * 1024,
                              idle_baseline_bytes=0)
        for _ in range(5)
    ]
    verdict_fail_clone = mod.compute_verdict(
        cohorts_valid, over_limit_clone_rows,
        revocation_result={"teardown_latency_p95_s": 1.0, "all_assertions_passed": True},
    )
    check("over_limit_clone_is_fail", verdict_fail_clone["status"] == mod.VERDICT_FAIL, verdict_fail_clone)
    check(
        "over_limit_clone_names_the_metric",
        any(f["metric"] == "clone_latency_p95_s" for f in verdict_fail_clone["failures"]),
        verdict_fail_clone["failures"],
    )
    for f in verdict_fail_clone["failures"]:
        if f["metric"] == "clone_latency_p95_s":
            check("over_limit_clone_measured_gt_limit", f["measured"] > f["limit"], f)

    over_limit_rss_rows = [
        _synthetic_green_row(clone_latency_s=0.5, bwrap_latency_s=0.010,
                              cgroup_peak_bytes=1024 * 1024 * 1024, idle_baseline_bytes=0)
        for _ in range(3)
    ]
    verdict_fail_rss = mod.compute_verdict(
        cohorts_valid, over_limit_rss_rows,
        revocation_result={"teardown_latency_p95_s": 1.0, "all_assertions_passed": True},
    )
    check("over_limit_rss_is_fail", verdict_fail_rss["status"] == mod.VERDICT_FAIL, verdict_fail_rss)
    check(
        "over_limit_rss_names_the_metric",
        any(f["metric"] == "peak_incremental_rss_bytes" for f in verdict_fail_rss["failures"]),
        verdict_fail_rss["failures"],
    )

    over_limit_teardown = mod.compute_verdict(
        cohorts_valid, within_budget_rows,
        revocation_result={"teardown_latency_p95_s": 9.0, "all_assertions_passed": True},
    )
    check("over_limit_teardown_is_fail", over_limit_teardown["status"] == mod.VERDICT_FAIL, over_limit_teardown)

    failed_revocation_assertions = mod.compute_verdict(
        cohorts_valid, within_budget_rows,
        revocation_result={"teardown_latency_p95_s": 1.0, "all_assertions_passed": False, "failures": ["synthetic"]},
    )
    check(
        "failed_revocation_assertions_is_fail",
        failed_revocation_assertions["status"] == mod.VERDICT_FAIL, failed_revocation_assertions,
    )

    untyped_rows = within_budget_rows + [{
        **within_budget_rows[0], "sample_index": 99, "outcome": "not-a-real-outcome", "denial_code": None,
    }]
    verdict_untyped = mod.compute_verdict(
        cohorts_valid, untyped_rows,
        revocation_result={"teardown_latency_p95_s": 1.0, "all_assertions_passed": True},
    )
    check("untyped_outcome_forces_fail", verdict_untyped["status"] == mod.VERDICT_FAIL, verdict_untyped)
    check(
        "untyped_outcome_names_the_metric",
        any(f["metric"] == "untyped_outcome_count" for f in verdict_untyped["failures"]),
        verdict_untyped["failures"],
    )

    verdict_no_revocation = mod.compute_verdict(cohorts_valid, within_budget_rows, revocation_result=None)
    check(
        "missing_revocation_result_is_unavailable_not_pass_fake",
        "teardown_latency_p95_s" in verdict_no_revocation["metrics_unavailable"],
        verdict_no_revocation,
    )
    check(
        "missing_revocation_result_still_passes_on_other_metrics",
        verdict_no_revocation["status"] == mod.VERDICT_PASS,
        verdict_no_revocation,
    )


# --------------------------------------------------------------------------
# 6. Real (tiny) cache eviction/priming against a real on-disk fixture --
#    not mocked. Proves `disk_backed_tmp_root` + `evict_cache` +
#    `mincore_residency_pct` + `prime_cache` actually cross the frozen
#    thresholds on THIS host.
# --------------------------------------------------------------------------


def test_real_cache_eviction_and_priming():
    fstype = mod._fs_type_of(mod.disk_backed_tmp_root())
    check("disk_backed_tmp_root_is_not_tmpfs_like", fstype not in mod._TMPFS_LIKE_FSTYPES, fstype)

    source_repo, head_oid = mod.build_source_repo()
    mirror = mod.build_bare_mirror(source_repo)
    try:
        pack_path = mod.find_trusted_object_source(mirror)
        check("trusted_object_source_exists", Path(pack_path).is_file(), pack_path)

        valid_cold, pct_cold = mod.verify_cache_cohort(pack_path, mod.COHORT_COLD)
        check("real_cold_eviction_valid", valid_cold is True, f"residency_pct={pct_cold}")
        check("real_cold_eviction_at_or_below_threshold", pct_cold <= mod.COLD_RESIDENCY_MAX_PCT, pct_cold)

        mod.prime_cache(pack_path)
        valid_warm, pct_warm = mod.verify_cache_cohort(pack_path, mod.COHORT_WARM)
        check("real_warm_priming_valid", valid_warm is True, f"residency_pct={pct_warm}")
        check("real_warm_priming_at_or_above_threshold", pct_warm >= mod.WARM_RESIDENCY_MIN_PCT, pct_warm)
    finally:
        mod.cleanup_temp_roots()


# --------------------------------------------------------------------------
# 7. Small, real revocation-under-load run (§5) -- R6-deferred-skipped only
#    if no delegated cgroup v2 subtree exists on this host.
# --------------------------------------------------------------------------


def test_revocation_under_load_small_real_run():
    harness = mod.PerfHarness(n=2)
    try:
        if harness.cgroup_parent is None:
            skip(
                "revocation_under_load_small_real_run",
                "no delegated cgroup v2 subtree available on this host — R6 canary",
            )
            return

        result = mod.run_revocation_under_load(harness, concurrency_cap=1, sleep_seconds=3.0)
        if result.get("skipped"):
            skip("revocation_under_load_small_real_run", "; ".join(result["skipped"]))
            return

        check(
            "revocation_all_assertions_passed", result["all_assertions_passed"] is True,
            result.get("failures"),
        )
        check(
            "revocation_teardown_within_budget",
            result["teardown_latency_p95_s"] is not None and result["teardown_latency_p95_s"] <= mod.REVOCATION_TEARDOWN_BUDGET_S,
            result.get("teardown_latency_p95_s"),
        )

        result2 = mod.run_revocation_under_load(harness, concurrency_cap=2, sleep_seconds=3.0)
        if not result2.get("skipped"):
            check(
                "revocation_cap2_all_assertions_passed", result2["all_assertions_passed"] is True,
                result2.get("failures"),
            )

        try:
            mod.run_revocation_under_load(harness, concurrency_cap=3, sleep_seconds=1.0)
            check("revocation_rejects_cap_over_review_ceiling", False, "expected ValueError for cap=3")
        except ValueError:
            check("revocation_rejects_cap_over_review_ceiling", True)
    finally:
        mod.cleanup_temp_roots()


# --------------------------------------------------------------------------
# 8. Small, real end-to-end protocol run through the actual R3 runner over
#    a real UDS (tiny N -- NOT the real N>=40 acceptance run).
# --------------------------------------------------------------------------


def test_small_real_end_to_end_run():
    harness = mod.PerfHarness(n=2)
    try:
        results = harness.run_all(command_classes=(mod.COMMAND_NOOP,), cache_cohorts=mod.CACHE_COHORTS)
        check("e2e_two_cohorts_ran", len(results) == 2, results)
        check("e2e_all_cohorts_valid", all(r.valid for r in results),
              [(r.command_class, r.cache_cohort, r.invalid_reason) for r in results])
        check("e2e_rows_recorded", len(harness.rows) >= 4, len(harness.rows))
        check(
            "e2e_all_rows_green",
            all(r["outcome"] == mod.OUTCOME_GREEN for r in harness.rows),
            [r["outcome"] for r in harness.rows],
        )

        verdict = mod.compute_verdict(harness.cohort_results, harness.rows, revocation_result=None)
        check("e2e_verdict_not_invalid", verdict["status"] != mod.VERDICT_INVALID, verdict)
        check(
            "e2e_verdict_pass_or_metric_named_fail",
            verdict["status"] in (mod.VERDICT_PASS, mod.VERDICT_FAIL),
            verdict,
        )

        untyped_ok, offenders = mod.zero_untyped_outcome_gate(harness.rows)
        check("e2e_zero_untyped_outcomes", untyped_ok is True, offenders)
    finally:
        mod.cleanup_temp_roots()


# --------------------------------------------------------------------------
# R6-canary-deferred: genuinely systemd-only surfaces (real socket
# activation, Delegate=true under the actual deployed unit) -- recorded as
# explicit skips, never faked. Same precedent as
# test-execution-cell-runner.py.
# --------------------------------------------------------------------------


def note_r6_canary_deferred_surfaces():
    skip(
        "systemd_delegated_cgroup_full_acceptance_run",
        "the REAL N>=40 APU acceptance run against a systemd Delegate=true "
        "cgroup is an operator step (design §10), not a CI unit — this "
        "self-test only proves the harness's own math/gating/verdict logic "
        "plus a small real exercise",
    )


def main() -> None:
    tests = [
        test_p95_nearest_rank_known_arrays,
        test_cache_validity_gating,
        test_zero_untyped_outcome_gate,
        test_invalid_cohort_never_passes,
        test_verdict_pass_and_fail_logic,
        test_real_cache_eviction_and_priming,
        test_revocation_under_load_small_real_run,
        test_small_real_end_to_end_run,
    ]
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 — a test crashing is itself a FAIL, not a harness crash
            check(test.__name__, False, f"test raised {type(exc).__name__}: {exc}")

    note_r6_canary_deferred_surfaces()
    mod.cleanup_temp_roots()

    _report_and_exit()


if __name__ == "__main__":
    main()
