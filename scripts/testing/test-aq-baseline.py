#!/usr/bin/env python3
"""Hermetic tests for aq-baseline (experience-capture S-M1): AT-1..AT-5, J0 reproducibility, rollback.

Every producer is a fixture in a temp dir; nothing reads the live repo producers or network.
"""
from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB))
import aq_baseline as ab  # noqa: E402

CLI = ROOT / "scripts" / "ai" / "aq-baseline"
PM_TRACKER = ROOT / "scripts" / "ai" / "aq-pm-tracker"
EFFECTIVE = "2026-10-27T12:00:00Z"
PRE_NOW = "2026-10-27T00:00:00Z"
POST_NOW = "2026-11-28T00:00:00Z"
POST_AS_OF = "2026-11-27T00:00:00Z"
ARGS = dict(subject="feat-x", cohort="all", definition_version="v1", horizon_days=30, min_effect=0.1)


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


class Fixture:
    """A temp root with every producer present; override pieces per test."""

    def __init__(self, tmp: Path, *, pre_rounds: int = 1, post_rounds: int = 0, per_arm: int = 25,
                 dup_pr: bool = False) -> None:
        self.root = tmp
        self.extra: dict[str, str] = {}  # per-test env overrides applied on top of the defaults
        self.deleg = tmp / "deleg"
        self.report = tmp / "latest-aq-report.json"
        self.leanctx = tmp / "leanctx.json"
        self.write_all(pre_rounds, post_rounds, per_arm, dup_pr)

    def write_all(self, pre_rounds: int, post_rounds: int, per_arm: int, dup_pr: bool) -> None:
        receipts: list[dict[str, Any]] = []
        registry: list[dict[str, Any]] = []
        for arm, (day0, rounds, ok_every) in {"pre": ("2026-10-", pre_rounds, 5), "post": ("2026-11-", post_rounds, 1)}.items():
            for i in range(per_arm):
                day = 2 + i if arm == "pre" else 2 + i
                # pre arm lives in 2026-10-02..10-26 (before effective start); post arm in 2026-11-02..11-26
                stamp = f"{day0}{day:02d}T10:00:00Z"
                receipts.append({"pr": (100 if arm == "pre" else 200) + i, "recorded_at": stamp,
                                 "request_changes_rounds": rounds, "head_sha": "a" * 40})
                if dup_pr and i == 0:
                    for k in range(3):  # repeated landing records for one PR must count once
                        receipts.append({"pr": 100 if arm == "pre" else 200, "recorded_at": f"{day0}{day:02d}T1{k}:30:00Z",
                                         "request_changes_rounds": rounds, "head_sha": "a" * 40})
                ok = (i % ok_every == 0) if arm == "pre" else True
                row = {"id": f"d-{arm}-{i}", "agent": "codex", "status": "done" if ok else "failed", "created": stamp,
                       "outcome": "unknown", "model_effective": "m1" if i % 2 else "unknown"}
                registry.append(row)
                if dup_pr and i == 0:
                    registry.extend([dict(row), dict(row)])  # duplicate events for one dispatch
        _jsonl(self.deleg / "registry.jsonl", registry)
        _jsonl(self.deleg / "outcome-receipts.jsonl", receipts)
        _jsonl(self.deleg / "training-loop-results.jsonl", [
            {"run_id": f"loop-{n}", "timestamp": f"2026-10-{10 + n:02d}T00:00:00Z", "cases_total": 12, "pass_count": 7,
             "ingest": {"samples_added": 0}} for n in range(3)])
        (self.root / ".agent" / "collaboration").mkdir(parents=True, exist_ok=True)
        # the tracked seed is a decoy (1 incident); the live runtime ledger (4 incidents) must win
        (self.root / ".agent" / "collaboration" / "rsi-incidents.json").write_text(json.dumps({"version": 1, "incidents": {
            "seed0": {"first_seen": "2026-10-05T00:00:00Z", "producer": "seed"}}}))
        (self.root / "rsi-state").mkdir(exist_ok=True)
        (self.root / "rsi-state" / "rsi-incidents.json").write_text(json.dumps({"version": 1, "incidents": {
            f"inc{n}": {"first_seen": f"2026-10-{5 + n:02d}T00:00:00Z", "producer": "aq-qa:phase0"} for n in range(4)}}))
        self.report.write_text(json.dumps({
            "generated_at": "2026-11-26T00:00:00Z", "hint_adoption": {"total": 10, "accepted": 10},
            "effectiveness_scorecard": {"completion_reliability": {"delegation_total": 10, "delegation_failures": 4,
                                                                   "delegation_window_s": 86400}},
            "useful_tokens": {"status": "no_data", "useful_ratio": None}}))
        self.leanctx.write_text(json.dumps([
            {"tool": "ctx_read", "baseline_tokens": 1000, "saved_tokens": 900, "calls": 5},
            {"tool": "ctx_shell", "baseline_tokens": 100, "saved_tokens": 50, "calls": 2}]))

    def failures(self, rows: list[dict[str, Any]] | None) -> Path:
        p = self.deleg / "outputs" / "aq-land" / "failure-events.jsonl"
        if rows is None:
            if p.exists():
                p.unlink()
        else:
            _jsonl(p, rows)
        return p

    def env(self, now: str) -> dict[str, str]:
        return {"AQ_BASELINE_ROOT": str(self.root), "AQ_DELEGATION_DIR": str(self.deleg),
                "AQ_REPORT_LATEST_JSON": str(self.report), "AQ_BASELINE_LEANCTX_JSON": str(self.leanctx),
                "AQ_BASELINE_NOW": now, "TELEMETRY_DIR": str(self.root / "telemetry"),
                "RSI_STATE_DIR": str(self.root / "rsi-state"), **self.extra}


@contextlib.contextmanager
def env(vals: dict[str, str]) -> Iterator[None]:
    old = {k: os.environ.get(k) for k in vals}
    os.environ.update(vals)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def snap(fx: Fixture, now: str, as_of: str | None = None, window_days: int = 30, **over: Any) -> str:
    kw = {**ARGS, **over}
    with env(fx.env(now)):
        sid, _ = ab.take_snapshot(fx.root, as_of=as_of, window_days=window_days, **kw)
    return sid


def compare(fx: Fixture, pre: str, post: str, subject: str = "feat-x", effective: str = EFFECTIVE) -> dict[str, Any]:
    with env(fx.env(POST_NOW)):
        return ab.compare_snapshots(fx.root, subject, effective, pre, post)


def rejected(fx: Fixture, pre: str, post: str, reason: str, **kw: Any) -> None:
    try:
        compare(fx, pre, post, **kw)
    except ab.BaselineError as exc:
        assert reason in str(exc), f"expected {reason}, got {exc}"
        return
    raise AssertionError(f"compare accepted a pair that must be rejected with {reason}")


def rows_of(fx: Fixture, sid: str) -> dict[str, dict[str, Any]]:
    return {r["metric_id"]: r for r in ab.snapshot_rows(ab.telemetry_dir(fx.root), sid)}


def run_cli(fx: Fixture, now: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True,
                          env={**os.environ, **fx.env(now)})


def test_j0_snapshot_verify_reproducible_and_private() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        sid = snap(fx, PRE_NOW)
        with env(fx.env(PRE_NOW)):
            ok, detail = ab.verify_snapshot(fx.root, sid)
        assert ok, detail
        tdir = ab.telemetry_dir(fx.root)
        assert oct((tdir / ab.SNAPSHOT_FILE).stat().st_mode & 0o777) == "0o600"
        copies = list((tdir / ab.INPUT_DIR).iterdir())
        assert copies and all(oct(c.stat().st_mode & 0o777) == "0o600" for c in copies)
        # live producers change AFTER capture: verify still passes (recomputed from retained copies only)
        _jsonl(fx.deleg / "registry.jsonl", [{"id": "x", "agent": "codex", "status": "failed", "created": "2026-10-10T00:00:00Z"}])
        fx.leanctx.unlink()
        with env(fx.env(PRE_NOW)):
            ok, detail = ab.verify_snapshot(fx.root, sid)
        assert ok, detail
        # a fresh snapshot of the changed producers differs (not a replay of the retained one)
        sid2 = snap(fx, "2026-10-27T00:00:01Z")
        assert rows_of(fx, sid2)["delegation_success_raw"]["n"] != rows_of(fx, sid)["delegation_success_raw"]["n"]
        # tampering with a stored row or a retained input fails verify
        path = tdir / ab.SNAPSHOT_FILE
        path.write_text(path.read_text().replace('"concentration_threshold":0.3', '"concentration_threshold":0.9', 1))
        with env(fx.env(PRE_NOW)):
            assert not ab.verify_snapshot(fx.root, sid)[0]
        sid3 = snap(fx, "2026-10-27T00:00:02Z")
        first_input = ab.snapshot_rows(tdir, sid3)[0]["inputs"][0]["sha256"]
        (tdir / ab.INPUT_DIR / first_input).write_bytes(b"tampered")
        with env(fx.env(PRE_NOW)):
            assert not ab.verify_snapshot(fx.root, sid3)[0]


def test_cli_snapshot_verify_compare() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        a = ["--subject", "feat-x", "--cohort", "all", "--definition-version", "v1", "--horizon-days", "30", "--min-effect", "0.1"]
        pre = run_cli(fx, PRE_NOW, "snapshot", *a)
        assert pre.returncode == 0, pre.stderr
        pre_id = pre.stdout.split()[1]
        post = run_cli(fx, POST_NOW, "snapshot", *a, "--as-of", POST_AS_OF)
        post_id = post.stdout.split()[1]
        v = run_cli(fx, POST_NOW, "verify", pre_id)
        assert v.returncode == 0 and v.stdout.startswith("PASS"), v.stdout
        c = run_cli(fx, POST_NOW, "compare", "--subject", "feat-x", "--effective-start", EFFECTIVE, pre_id, post_id)
        assert c.returncode == 0 and "rework_rounds_per_pr" in c.stdout and "improved" in c.stdout, c.stdout + c.stderr
        bad = run_cli(fx, POST_NOW, "compare", "--subject", "other", "--effective-start", EFFECTIVE, pre_id, post_id)
        assert bad.returncode == 1 and "subject_mismatch" in bad.stderr


def test_at1_compare_binding() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        pre = snap(fx, PRE_NOW)
        post = snap(fx, POST_NOW, as_of=POST_AS_OF)
        res = compare(fx, pre, post)
        assert res["metrics"]["rework_rounds_per_pr"]["verdict"] == "improved"  # decreasing-is-better metric
        assert res["metrics"]["delegation_success_raw"]["verdict"] == "improved"
        # (a) retrospective capture: pre window ends before activation but it was captured after it
        retro = snap(fx, "2026-10-27T18:00:00Z", as_of=PRE_NOW)
        rejected(fx, retro, post, "retrospective_capture")
        # (b) a snapshot of a different subject
        other = snap(fx, PRE_NOW, subject="feat-y")
        rejected(fx, other, post, "subject_mismatch")
        rejected(fx, pre, post, "subject_mismatch", subject="feat-y")
        # (c) changed min_effect
        rejected(fx, pre, snap(fx, POST_NOW, as_of=POST_AS_OF, min_effect=0.3), "min_effect_mismatch")
        # definition / cohort / horizon changes
        rejected(fx, pre, snap(fx, POST_NOW, as_of=POST_AS_OF, definition_version="v2"), "definition_mismatch")
        rejected(fx, pre, snap(fx, POST_NOW, as_of=POST_AS_OF, cohort="lane=codex"), "cohort_mismatch")
        rejected(fx, pre, snap(fx, POST_NOW, as_of=POST_AS_OF, horizon_days=60), "horizon_mismatch")
        # window cases
        rejected(fx, pre, snap(fx, POST_NOW, as_of=POST_AS_OF, window_days=20), "windows_unequal")
        rejected(fx, pre, snap(fx, "2026-11-10T00:00:00Z", as_of="2026-11-10T00:00:00Z"), "post_window_starts_before_effective_start")
        rejected(fx, pre, snap(fx, "2026-10-26T00:00:00Z", as_of="2026-10-26T00:00:00Z"), "post_window_ends_before_effective_start")
        # a pre window that ends after the effective start, or windows that overlap (crafted: unreachable via capture order)
        p_row = ab.snapshot_rows(ab.telemetry_dir(fx.root), pre)[0]
        q_row = ab.snapshot_rows(ab.telemetry_dir(fx.root), post)[0]
        late_pre = {**p_row, "input_window": {"start": "2026-10-01T00:00:00Z", "end": "2026-10-28T00:00:00Z"}}
        assert ab.bind_check(late_pre, q_row, "feat-x", ab.parse_ts(EFFECTIVE)) == "pre_window_ends_after_effective_start"
        # every parameter participates in the snapshot id
        base = dict(subject="s", cohort="all", definition_version="v1", horizon_days=30, min_effect=0.1,
                    captured_at="2026-10-27T00:00:00Z", window={"start": "a", "end": "b"}, input_digests=["d"], metric_ids=["m"])
        ids = {ab.compute_snapshot_id(**base)}
        for k, v in (("subject", "s2"), ("cohort", "lane=x"), ("definition_version", "v2"), ("horizon_days", 31),
                     ("min_effect", 0.2), ("captured_at", "2026-10-27T00:00:01Z"), ("window", {"start": "a", "end": "c"}),
                     ("input_digests", ["e"]), ("metric_ids", ["n"])):
            ids.add(ab.compute_snapshot_id(**{**base, k: v}))
        assert len(ids) == 10
        # effective-start unresolvable
        try:
            with env(fx.env(POST_NOW)):
                ab.compare_snapshots(fx.root, "feat-x", "not-a-ref", pre, post)
        except ab.BaselineError:
            pass
        else:
            raise AssertionError("unresolvable effective start accepted")


def test_at2_units_time_coverage_and_independent_resampling() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        sid = snap(fx, PRE_NOW)
        rows = rows_of(fx, sid)
        for r in rows.values():
            assert r["unit_label"] in ("pr", "dispatch", "aggregate") and r["time_coverage"] in ("windowed", "current-only")
            if r["time_coverage"] == "windowed":
                assert r["window"]["start"] and r["window"]["end"]
        training, rsi, lean = rows["training_loop_pass_rate"], rows["rsi_incident_count"], rows["leanctx_token_savings"]
        for r in (training, rsi, lean):
            assert r["unit_label"] == "aggregate" and r["observation_membership"]["digest"]
        # membership counts equal the producer records inside the window
        assert training["observation_membership"]["count"] == 3 and training["n"] == 3
        assert rsi["observation_membership"]["count"] == 4
        assert lean["observation_membership"]["count"] == 2 and lean["time_coverage"] == "current-only"
        assert lean["concentrated"] is True and lean["value_ex_top"] is not None and lean["top_share"] > 0.3
        # <20 memberships prints insufficient; current-only aggregates never get a verdict
        assert training["display"] == rsi["display"] == lean["display"] == "insufficient"
        post = snap(fx, POST_NOW, as_of=POST_AS_OF)
        res = compare(fx, sid, post)["metrics"]
        assert res["leanctx_token_savings"]["verdict"] in ("insufficient", "descriptive")
        assert res["delegation_success_report"]["verdict"] == "descriptive"  # current-only, never improved
        assert "improved" not in {res[m]["verdict"] for m in res if rows[m]["unit_label"] == "aggregate"}
        # 20 independent units reach the floor: a populated aggregate becomes descriptive, still no verdict
        # duplicate events on one PR / one dispatch leave the observations and the bootstrap interval unchanged
        with tempfile.TemporaryDirectory() as t2:
            dup = Fixture(Path(t2), dup_pr=True)
            dsid, dpost = snap(dup, PRE_NOW), snap(dup, POST_NOW, as_of=POST_AS_OF)
            plain = compare(fx, sid, post)["metrics"]
            duped = compare(dup, dsid, dpost)["metrics"]
            for m in ("rework_rounds_per_pr", "delegation_success_raw"):
                assert plain[m] == duped[m], (m, plain[m], duped[m])
            assert rows_of(dup, dsid)["rework_rounds_per_pr"]["n"] == 25


def test_at2_small_n_prints_counts_without_verdict_and_worse_is_not_improved() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t), per_arm=10)
        pre, post = snap(fx, PRE_NOW), snap(fx, POST_NOW, as_of=POST_AS_OF)
        v = compare(fx, pre, post)["metrics"]["rework_rounds_per_pr"]
        assert v["verdict"] == "insufficient" and v["n_pre"] == 10 and v["n_post"] == 10
        assert rows_of(fx, pre)["rework_rounds_per_pr"]["display"] == "counts_only"
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t), pre_rounds=0, post_rounds=2)  # more rework is worse for a decreasing metric
        pre, post = snap(fx, PRE_NOW), snap(fx, POST_NOW, as_of=POST_AS_OF)
        assert compare(fx, pre, post)["metrics"]["rework_rounds_per_pr"]["verdict"] == "no demonstrated change"
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t), pre_rounds=1, post_rounds=1)  # change below zero effect
        pre, post = snap(fx, PRE_NOW), snap(fx, POST_NOW, as_of=POST_AS_OF)
        assert compare(fx, pre, post)["metrics"]["rework_rounds_per_pr"]["verdict"] == "no demonstrated change"


def test_unknown_and_in_flight_are_reported_not_merged() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t), per_arm=2)
        _jsonl(fx.deleg / "registry.jsonl", [
            {"id": "a", "agent": "codex", "status": "done", "created": "2026-10-10T00:00:00Z", "outcome": "unknown"},
            {"id": "b", "agent": "codex", "status": "running", "created": "2026-10-11T00:00:00Z"},
            {"id": "c", "agent": "codex", "status": "cancelled", "created": "2026-10-11T00:00:00Z"},
            {"id": "d", "agent": "codex", "status": "orphaned", "created": "2026-10-11T00:00:00Z"},
            {"id": "e", "agent": "codex", "status": "timeout", "created": "2026-10-11T00:00:00Z"},
            {"id": "f", "agent": "codex", "status": "done", "created": "2026-10-11T00:00:00Z", "outcome": "refused"},
            {"id": "g", "agent": "codex", "status": "done"}])  # undated: excluded and counted
        _jsonl(fx.deleg / "outcome-receipts.jsonl", [
            {"pr": 1, "recorded_at": "2026-10-10T00:00:00Z", "request_changes_rounds": 0},
            {"pr": 2, "recorded_at": "2026-10-10T00:00:00Z"}])  # zero is a value; missing is unknown
        r = rows_of(fx, snap(fx, PRE_NOW))
        d = r["delegation_success_raw"]
        assert (d["numerator"], d["denominator"], d["in_flight_n"], d["skipped_n"], d["unknown_n"], d["infra_n"],
                d["blocked_n"], d["undated_n"]) == (1, 2, 1, 1, 1, 1, 1, 1)
        w = r["rework_rounds_per_pr"]
        assert w["unknown_n"] == 1 and w["n"] == 1 and w["value"] == 0


def test_at3_mint_failure_no_producer_never_zero() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        fx.failures(None)
        r = rows_of(fx, snap(fx, PRE_NOW))
        assert r["receipt_mint_failures"]["value"] is None and r["receipt_mint_failures"]["gap"] == "no_producer"
        assert r["wasted_reviews"]["value"] is None and r["wasted_reviews"]["gap"] == "no_producer"
        # the producer exists but never emitted a mint kind: a quiet window must not read as zero
        fx.failures([{"at": "2026-10-10T00:00:00Z", "kind": "review_exhausted", "stage": "review", "head_sha": "h"}])
        r = rows_of(fx, snap(fx, "2026-10-27T00:00:01Z"))
        assert r["receipt_mint_failures"]["value"] is None and r["receipt_mint_failures"]["gap"] == "no_producer"
        assert r["wasted_reviews"]["gap"] == "no_producer"
        assert r["aq_land_structured_failures"]["value"] == 1
        keys_before = set(r["receipt_mint_failures"])
        # a later durable producer flips the row to a count, same schema
        fx.failures([{"at": "2026-10-10T00:00:00Z", "kind": "review_exhausted", "stage": "review", "head_sha": "h"},
                     {"at": "2026-10-12T00:00:00Z", "kind": "mint_failed", "stage": "mint", "head_sha": "h2"}])
        r = rows_of(fx, snap(fx, "2026-10-27T00:00:02Z"))
        m = r["receipt_mint_failures"]
        assert m["value"] == 1 and m["gap"] is None and set(m) == keys_before
        assert m["observation_membership"]["count"] == 1


def test_at4_qa_check_report_line_and_pm_tracker_modes() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        sid = snap(fx, PRE_NOW)
        # age + verify status: fresh
        with env(fx.env("2026-10-30T00:00:00Z")):
            st = ab.snapshot_status()
            assert st["verify"] == "pass" and st["status"] == "ok" and 2.9 < st["age_days"] < 3.1
            assert "verify pass" in ab.status_line(st) and "age 3.0d" in ab.status_line(st)
            qa = _qa_check()
            assert qa.status.value == "PASS" and "age 3.0d" in qa.description and "verify pass" in qa.description
            report = _load_report_module()
            line = report._baseline_status_line(report.baseline_snapshot_status())
            assert "age 3.0d" in line and "verify pass" in line
            doc = json.loads(report.format_json(*_format_json_stub(report), baseline_status=report.baseline_snapshot_status()))
            assert doc["baseline_snapshot"]["verify"] == "pass" and doc["baseline_snapshot"]["age_days"] > 2.9
        # stale after 35 days
        with env(fx.env("2026-12-05T00:00:00Z")):
            assert ab.snapshot_status()["status"] == "stale"
            qa = _qa_check()
            assert qa.status.value == "FAIL" and "stale" in qa.reason
        # verify failure surfaces in the check and the line
        tdir = ab.telemetry_dir(fx.root)
        digest = ab.snapshot_rows(tdir, sid)[0]["inputs"][0]["sha256"]
        (tdir / ab.INPUT_DIR / digest).write_bytes(b"x")
        with env(fx.env("2026-10-30T00:00:00Z")):
            assert _qa_check().status.value == "FAIL"
            assert "verify fail" in ab.status_line(ab.snapshot_status())
    with tempfile.TemporaryDirectory() as t:
        with env({"AQ_BASELINE_ROOT": t}):
            qa = _qa_check()
            assert qa.status.value == "SKIP" and "not yet baselined" in qa.reason  # fresh install must not false-alarm
            assert ab.snapshot_status()["status"] == "no_snapshot"
    # dashboard path: the scorecard route forwards the aq-report artifact's snapshot status
    src = (ROOT / "dashboard" / "backend" / "api" / "routes" / "aistack.py").read_text()
    assert '"baseline_snapshot": report.get("baseline_snapshot")' in src
    # decision 2 on the SAME missing-baseline input: commit WARN, maintenance failure
    with tempfile.TemporaryDirectory() as t:
        plan = Path(t) / "p1"
        plan.mkdir()
        (plan / "tracker.json").write_text(json.dumps({
            "plan": {"id": "p1", "title": "t", "measurement_required": True},
            "phases": [{"id": "P1", "name": "x", "goal": "g", "order": 1}],
            "items": [{"id": "A", "name": "a", "phase": "P1", "goal": "g", "validation_goal": "v", "kind": "slice",
                       "acceptance": {"status": "accepted", "by": "hyperd"},
                       "detection": {"command": "python3", "wired_caller": {"file": "scripts/ai/aq-baseline", "pattern": "aq_baseline"},
                                     "tests": ["scripts/testing/test-aq-baseline.py"]}}]}))
        commit = subprocess.run([sys.executable, str(PM_TRACKER), "--check-no-baseline", "--plans-root", t], capture_output=True, text=True)
        maint = subprocess.run([sys.executable, str(PM_TRACKER), "--check-no-baseline", "--maintenance", "--plans-root", t],
                               capture_output=True, text=True)
        assert commit.returncode == 0 and "WARN: no_baseline" in commit.stdout, commit.stdout + commit.stderr
        assert maint.returncode == 1 and "FAIL: no_baseline" in maint.stdout, maint.stdout + maint.stderr
        # populated measurement object clears it in both modes
        doc = json.loads((plan / "tracker.json").read_text())
        doc["items"][0]["measurement"] = {"baseline": {"snapshot_id": "abc"}}
        (plan / "tracker.json").write_text(json.dumps(doc))
        ok = subprocess.run([sys.executable, str(PM_TRACKER), "--check-no-baseline", "--maintenance", "--plans-root", t],
                            capture_output=True, text=True)
        assert ok.returncode == 0 and "0 required" in ok.stdout, ok.stdout


def test_rollback_disables_schedule_first_then_archives() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        a = ["--subject", "feat-x", "--definition-version", "v1", "--horizon-days", "30", "--min-effect", "0.1", "--scheduled"]
        assert run_cli(fx, PRE_NOW, "snapshot", *a).returncode == 0
        tdir = ab.telemetry_dir(fx.root)
        assert (tdir / ab.SNAPSHOT_FILE).exists()
        rb = run_cli(fx, PRE_NOW, "rollback")
        assert rb.returncode == 0, rb.stderr
        archived = list((fx.root / ".agent" / "archive").glob("*-aq-baseline"))
        assert archived and (archived[0] / ab.SNAPSHOT_FILE).exists() and (archived[0] / ab.INPUT_DIR).is_dir()
        assert not (tdir / ab.SNAPSHOT_FILE).exists()
        # the next scheduled tick writes nothing
        tick = run_cli(fx, "2026-10-28T00:00:00Z", "snapshot", *a)
        assert tick.returncode == 3 and not (tdir / ab.SNAPSHOT_FILE).exists()
        assert not (tdir / ab.INPUT_DIR).exists()


def test_cohort_validation_and_future_as_of_rejected() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        for bad in ("lane=", "everything"):
            try:
                snap(fx, PRE_NOW, cohort=bad)
            except ab.BaselineError:
                continue
            raise AssertionError(f"cohort {bad!r} accepted")
        try:
            snap(fx, PRE_NOW, as_of="2027-01-01T00:00:00Z")
        except ab.BaselineError:
            pass
        else:
            raise AssertionError("future --as-of accepted")
        lane = rows_of(fx, snap(fx, PRE_NOW, cohort="lane=other"))
        assert lane["delegation_success_raw"]["n"] == 0


def test_live_stores_preferred_over_seed_and_fallback() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        # RSI: runtime ledger (4) beats the tracked seed (1); an explicit dir without a ledger is no_producer (seed fallback: see the RSI read test)
        assert rows_of(fx, snap(fx, PRE_NOW))["rsi_incident_count"]["value"] == 4
        (fx.root / "rsi-state" / "rsi-incidents.json").unlink()
        gone = rows_of(fx, snap(fx, "2026-10-27T00:00:01Z"))["rsi_incident_count"]
        assert gone["value"] is None and gone["gap"] == "no_producer"  # explicit RSI_STATE_DIR: never the seed
        # training loop: TELEMETRY_DIR primary store (5 runs) beats the delegation-dir fallback (3 runs)
        tel = fx.root / "telemetry"
        _jsonl(tel / "training-loop-results.jsonl", [
            {"run_id": f"live-{n}", "timestamp": f"2026-10-{10 + n:02d}T00:00:00Z", "cases_total": 12, "pass_count": 9,
             "ingest": {"samples_added": 1}} for n in range(5)])
        r = rows_of(fx, snap(fx, "2026-10-27T00:00:02Z"))["training_loop_pass_rate"]
        assert r["n"] == 5 and r["samples_added"] == 5 and r["numerator"] == 45
        origins = [i["path"] for i in ab.snapshot_rows(ab.telemetry_dir(fx.root), ab_sid_last(fx))[0]["inputs"]]
        assert str(tel / "training-loop-results.jsonl") in origins


def ab_sid_last(fx: Fixture) -> str:
    return max(ab.load_rows(ab.telemetry_dir(fx.root)), key=lambda r: r["captured_at"])["snapshot_id"]


def test_duplicate_snapshot_idempotent_conflict_refused_and_concurrent_writers() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        tdir = ab.telemetry_dir(fx.root)
        sid = snap(fx, PRE_NOW)
        n_lines = len((tdir / ab.SNAPSHOT_FILE).read_text().splitlines())
        assert snap(fx, PRE_NOW) == sid  # same second, same inputs: identical rows, no-op
        assert len((tdir / ab.SNAPSHOT_FILE).read_text().splitlines()) == n_lines
        with env(fx.env(PRE_NOW)):
            assert ab.verify_snapshot(fx.root, sid)[0] and ab.snapshot_status(now=ab.parse_ts(PRE_NOW))["verify"] == "pass"
        # a legacy store that already holds an identical duplicate still verifies (identical rows collapse)
        path = tdir / ab.SNAPSHOT_FILE
        path.write_text(path.read_text() * 2)
        with env(fx.env(PRE_NOW)):
            assert ab.verify_snapshot(fx.root, sid)[0]
        # same id but different row content: refuse with a clear error, store unchanged
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:n_lines]) + "\n")
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        rows[0]["value"] = 12345
        path.write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows))
        before = path.read_text()
        try:
            snap(fx, PRE_NOW)
        except ab.BaselineError as exc:
            assert "different rows" in str(exc)
        else:
            raise AssertionError("conflicting same-id snapshot accepted")
        assert path.read_text() == before
        with env(fx.env(PRE_NOW)):
            assert not ab.verify_snapshot(fx.root, sid)[0]
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        a = ["--subject", "feat-x", "--definition-version", "v1", "--horizon-days", "30", "--min-effect", "0.1"]
        procs = [subprocess.Popen([sys.executable, str(CLI), "snapshot", *a, *(["--as-of", PRE_NOW] if i % 2 else [])],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  env={**os.environ, **fx.env(PRE_NOW)}) for i in range(8)]
        outs = [p.communicate() for p in procs]
        assert all(p.returncode == 0 for p in procs), outs
        tdir = ab.telemetry_dir(fx.root)
        ids = {o[0].split()[1] for o in outs}
        assert len(ids) == 1  # identical inputs and second: one snapshot id, written once
        sid = ids.pop()
        lines = (tdir / ab.SNAPSHOT_FILE).read_text().splitlines()
        assert all(json.loads(x) for x in lines) and len(lines) == len(ab.snapshot_rows(tdir, sid))
        with env(fx.env(PRE_NOW)):
            assert ab.verify_snapshot(fx.root, sid)[0]
        assert not [p for p in (tdir / ab.INPUT_DIR).iterdir() if p.name.endswith(".tmp")]


def test_post_display_gates_aggregate_verdict_and_input_validation() -> None:
    pre = ab.new_row("m", improves_when="up", unit_label="aggregate", time_coverage="windowed", producer="p",
                     eligibility_filter="f", value=1.0, display="descriptive")
    post = {**pre, "display": "insufficient"}
    assert ab.metric_verdict(pre, post, 0.1, "s")["verdict"] == "insufficient"
    assert ab.metric_verdict(post, pre, 0.1, "s")["verdict"] == "insufficient"
    assert ab.metric_verdict(pre, {**pre}, 0.1, "s")["verdict"] == "descriptive"
    # a unit row paired with a current-only post row never gets a verdict
    unit = {**pre, "unit_label": "pr", "time_coverage": "windowed", "observations": [{"u": str(i), "v": 1} for i in range(30)]}
    assert ab.metric_verdict(unit, {**unit, "time_coverage": "current-only"}, 0.1, "s")["verdict"] in ("descriptive", "insufficient")
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        for bad in (float("nan"), float("inf"), -0.1):
            try:
                snap(fx, PRE_NOW, min_effect=bad)
            except ab.BaselineError:
                continue
            raise AssertionError(f"min_effect {bad} accepted")
        # a tampered snapshot line cannot point verify outside baseline-inputs/
        sid = snap(fx, PRE_NOW)
        path = ab.telemetry_dir(fx.root) / ab.SNAPSHOT_FILE
        path.write_text(path.read_text().replace(ab.snapshot_rows(ab.telemetry_dir(fx.root), sid)[0]["inputs"][0]["sha256"], "../../../etc/passwd"))
        with env(fx.env(PRE_NOW)):
            ok, detail = ab.verify_snapshot(fx.root, sid)
        assert not ok and ("invalid" in detail or "differ" in detail)


def test_rollback_twice_same_second_never_overwrites() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        snap(fx, PRE_NOW)
        assert run_cli(fx, PRE_NOW, "rollback").returncode == 0
        snap(fx, PRE_NOW, as_of="2026-10-26T00:00:00Z")
        first = {p.name: p.stat().st_size for p in (fx.root / ".agent" / "archive").glob("*-aq-baseline/*")}
        assert run_cli(fx, PRE_NOW, "rollback").returncode == 0
        dirs = sorted((fx.root / ".agent" / "archive").glob("*-aq-baseline*"))
        assert len(dirs) == 2 and re.match(r"\d{8}T\d{6}Z-aq-baseline", dirs[0].name)
        assert all((d / ab.SNAPSHOT_FILE).exists() and (d / ab.INPUT_DIR).is_dir() for d in dirs)
        assert first[ab.SNAPSHOT_FILE] == (dirs[0] / ab.SNAPSHOT_FILE).stat().st_size


def test_per_lane_rows_keep_each_lane_when_two_lanes_share_a_pr() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        _jsonl(fx.deleg / "registry.jsonl", [
            {"id": "a1", "agent": "codex", "status": "done", "created": "2026-10-10T00:00:00Z", "pr": 7},
            {"id": "a2", "agent": "codex", "status": "failed", "created": "2026-10-11T00:00:00Z", "pr": 7},  # retry, same lane
            {"id": "g1", "agent": "gemini", "status": "done", "created": "2026-10-12T00:00:00Z", "pr": 7},  # reviewer lane, same PR
            {"id": "x1", "agent": "codex", "status": "done", "created": "2026-10-13T00:00:00Z"}])
        r = rows_of(fx, snap(fx, PRE_NOW))
        assert r["delegation_success_raw.lane.gemini"]["n"] == 1  # not dropped for the later/earlier lane
        codex = r["delegation_success_raw.lane.codex"]
        assert codex["n"] == 2 and codex["numerator"] == 1  # retry clusters inside the lane: final attempt (failed) + x1
        assert r["delegation_success_raw"]["n"] == 2  # across lanes the PR is one unit (final attempt overall)


def test_runtime_artifacts_are_gitignored() -> None:
    for rel in (".agents/telemetry/.baseline.lock", ".agents/telemetry/baseline-snapshots.jsonl",
                ".agents/telemetry/baseline-inputs/" + "a" * 64, ".agents/telemetry/baseline-schedule.disabled",
                ".agent/archive/20261126T000000Z-aq-baseline/baseline-snapshots.jsonl",
                ".agent/archive/20261126T000000Z-aq-baseline-2/baseline-inputs/" + "a" * 64):
        r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel], capture_output=True)
        assert r.returncode == 0, f"not gitignored: {rel}"
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t) / "fx")
        repo = Path(t) / "repo"
        repo.mkdir()
        (repo / ".gitignore").write_text((ROOT / ".gitignore").read_text())
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", ".gitignore"], check=True)
        subprocess.run([*git, "commit", "-qm", "init"], check=True)
        e = {**os.environ, **fx.env(PRE_NOW), "AQ_BASELINE_ROOT": str(repo)}
        a = ["--subject", "feat-x", "--definition-version", "v1", "--horizon-days", "30", "--min-effect", "0.1"]
        assert subprocess.run([sys.executable, str(CLI), "snapshot", *a], env=e, capture_output=True).returncode == 0
        assert subprocess.run([sys.executable, str(CLI), "rollback"], env=e, capture_output=True).returncode == 0
        status = subprocess.run([*git, "status", "--porcelain"], capture_output=True, text=True).stdout
        assert status == "", status


def test_rsi_read_access_without_write_and_explicit_override_never_falls_back() -> None:
    import rsi_paths
    keep = {k: os.environ.pop(k, None) for k in ("PRSI_INCIDENTS_FILE", "RSI_RUNTIME_DIR", "RSI_STATE_DIR")}
    default = rsi_paths.DEFAULT_STATE_DIR
    try:
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(Path(t))  # tracked seed in root/.agent has 1 incident
            state = Path(t) / "ro-state"
            state.mkdir()
            (state / "rsi-incidents.json").write_text((fx.root / "rsi-state" / "rsi-incidents.json").read_text())
            state.chmod(0o555)  # readable, not writable
            try:
                # read-only explicit state dir with a ledger: read it (4), not the seed (1)
                fx.extra = {"RSI_STATE_DIR": str(state)}
                assert rows_of(fx, snap(fx, PRE_NOW))["rsi_incident_count"]["value"] == 4
                # explicit override pointing at nothing: no_producer, never the seed
                for i, (var, val) in enumerate((("RSI_STATE_DIR", str(Path(t) / "absent")),
                                                ("RSI_RUNTIME_DIR", str(Path(t) / "absent")),
                                                ("PRSI_INCIDENTS_FILE", str(Path(t) / "absent.json")))):
                    fx.extra = {"RSI_STATE_DIR": "", "RSI_RUNTIME_DIR": "", "PRSI_INCIDENTS_FILE": "", var: val}
                    row = rows_of(fx, snap(fx, f"2026-10-27T00:00:0{1 + i}Z"))["rsi_incident_count"]
                    assert row["value"] is None and row["gap"] == "no_producer", (var, row["value"])
                # no override: readable default state ledger (read-only) wins, then the seed when there is none
                fx.extra = {"RSI_STATE_DIR": "", "RSI_RUNTIME_DIR": "", "PRSI_INCIDENTS_FILE": ""}
                rsi_paths.DEFAULT_STATE_DIR = str(state)
                assert rows_of(fx, snap(fx, "2026-10-27T00:00:09Z"))["rsi_incident_count"]["value"] == 4
                rsi_paths.DEFAULT_STATE_DIR = str(Path(t) / "no-default")
                assert rows_of(fx, snap(fx, "2026-10-27T00:00:10Z"))["rsi_incident_count"]["value"] == 1
            finally:
                state.chmod(0o755)
    finally:
        rsi_paths.DEFAULT_STATE_DIR = default
        for k, v in keep.items():
            if v is not None:
                os.environ[k] = v


def test_rollback_between_compute_and_append_leaves_no_dangling_rows() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        snap(fx, PRE_NOW)  # something for rollback to move
        real = ab.compute_rows

        def rollback_mid_flight(*args: Any, **kw: Any) -> Any:
            out = real(*args, **kw)
            ab.rollback(fx.root)  # lands after the inputs were read, before the append
            return out
        ab.compute_rows = rollback_mid_flight
        try:
            # a scheduled tick that loses the race writes nothing
            try:
                with env(fx.env("2026-10-27T00:00:05Z")):
                    ab.take_snapshot(fx.root, scheduled=True, as_of=None, window_days=30, **ARGS)
            except ab.ScheduleDisabled:
                pass
            else:
                raise AssertionError("scheduled tick wrote after rollback")
            tdir = ab.telemetry_dir(fx.root)
            assert not (tdir / ab.SNAPSHOT_FILE).exists() and not (tdir / ab.INPUT_DIR).exists()
            # a manual snapshot that loses the race still retains its inputs inside the lock: nothing dangles
            with env(fx.env("2026-10-27T00:00:06Z")):
                sid, _ = ab.take_snapshot(fx.root, scheduled=False, as_of=None, window_days=30, **ARGS)
        finally:
            ab.compute_rows = real
        with env(fx.env(PRE_NOW)):
            assert ab.verify_snapshot(fx.root, sid)[0]
        a = ["--subject", "feat-x", "--definition-version", "v1", "--horizon-days", "30", "--min-effect", "0.1", "--scheduled"]
        assert run_cli(fx, "2026-10-27T00:00:07Z", "snapshot", *a).returncode == 3


def test_latest_attempt_is_chronological_across_mixed_offsets() -> None:
    with tempfile.TemporaryDirectory() as t:
        fx = Fixture(Path(t))
        # a2 is the LATER instant (10-11T04:00Z) but its string sorts before a1 ("...T00:00:00+00:00" < "...T00:00:00Z"? no:
        # "2026-10-10T20:00:00-08:00" < "2026-10-11T00:00:00Z" lexically while being later in time)
        _jsonl(fx.deleg / "registry.jsonl", [
            {"id": "a1", "agent": "codex", "status": "done", "created": "2026-10-11T00:00:00Z", "pr": 9},
            {"id": "a2", "agent": "codex", "status": "failed", "created": "2026-10-10T20:00:00-08:00", "pr": 9},
            {"id": "b1", "agent": "codex", "status": "done", "created": "2026-10-12T00:00:00+00:00", "pr": 10},
            {"id": "b2", "agent": "codex", "status": "failed", "created": "2026-10-12T00:00:00.500000Z", "pr": 10}])
        _jsonl(fx.deleg / "outcome-receipts.jsonl", [
            {"pr": 5, "recorded_at": "2026-10-11T00:00:00Z", "request_changes_rounds": 1},
            {"pr": 5, "recorded_at": "2026-10-10T20:00:00-08:00", "request_changes_rounds": 3}])
        r = rows_of(fx, snap(fx, PRE_NOW))
        d = r["delegation_success_raw"]
        assert d["n"] == 2 and d["numerator"] == 0  # final attempt of both PRs is the failed one
        assert r["rework_rounds_per_pr"]["numerator"] == 3  # the -08:00 record is the later instant


def test_at5_plan_naming_and_freeze_record() -> None:
    plan = ROOT / ".agents" / "plans" / "experience-capture-20261119"
    tracker = (plan / "tracker.json").read_text()
    design = (plan / "DESIGN.md").read_text()
    assert "rev5" in tracker and "1869c40c3" in tracker and "rev5" in design and "1869c40c3" in design
    assert not re.search(r"\brev[24]\b", tracker), "stale rev2/rev4 name in tracker.json"
    history = re.compile(r"Revision response|findings that moved|each rev4 finding|\(rev[24]\)|rev2 `|Codex review of rev4|rev2/rev4")
    stale = [ln for ln in design.splitlines() if re.search(r"\brev[24]\b", ln) and not history.search(ln)]
    assert not stale, stale
    ec0 = next(i for i in json.loads(tracker)["items"] if i["id"] == "EC-0")
    assert ec0["detection"]["freeze_record"].endswith("DESIGN.md")


def _qa_check() -> Any:
    sys.path.insert(0, str(ROOT / "scripts" / "testing"))
    from harness_qa.core.context import RunContext
    from harness_qa.phases import phase0
    results = phase0._check_baseline_snapshot(RunContext(repo_root=ROOT))
    assert len(results) == 1 and results[0].id == "0.10.71"
    return results[0]


def _load_report_module() -> Any:
    loader = importlib.machinery.SourceFileLoader("aq_report_under_test", str(ROOT / "scripts" / "ai" / "aq-report"))
    spec = importlib.util.spec_from_loader("aq_report_under_test", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _format_json_stub(report: Any) -> tuple[Any, ...]:
    import inspect
    params = [p for p in inspect.signature(report.format_json).parameters.values() if p.default is inspect.Parameter.empty]
    return tuple("" if p.name == "since_label" else ([] if p.name in ("leaderboard", "top_prompts", "gaps", "recs") else {})
                 for p in params)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print(f"ok {fn.__name__}")
    print("PASS: test-aq-baseline")
