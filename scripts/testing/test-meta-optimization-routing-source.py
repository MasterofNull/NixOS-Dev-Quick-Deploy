#!/usr/bin/env python3
"""Behavioral test: meta-optimization routing_source + alembic migration shape."""

import importlib
import json
import os
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MO = ROOT / "ai-stack" / "meta-optimization"
VERSIONS = ROOT / "ai-stack" / "migrations" / "versions"
sys.path.insert(0, str(MO))
import routing_source as rs  # noqa: E402

NOW = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def ev(model="m1", agent="a1", status="succeeded", dur=100.0, tok=10, src="delegate-to-local",
       age_h=1.0, etype="model_call", lane=None):
    return {
        "schema_version": "maeah.agent-run-event.v1", "event_type": etype,
        "agent_id": agent, "lane_id": lane, "model": model, "status": status,
        "duration_ms": dur, "tokens": {"total": tok}, "source": src,
        "route_profile": "local-direct", "timestamp": iso(NOW - timedelta(hours=age_h)),
    }


def write(path, rows, junk=()):
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
        for j in junk:
            fh.write(j + "\n")


def approx(a, b):
    return abs(a - b) < 1e-9


def test_aggregate(tmp):
    p = tmp / "events.jsonl"
    rows = [
        ev(dur=100, tok=10), ev(dur=300, tok=30),                       # m1/a1/succeeded x2
        ev(status="failed", dur=50, tok=None),                          # m1/a1/failed
        ev(model="m2", agent=None, lane="laneX", dur=200, tok=20),      # lane fallback
        ev(src="race-harness-fixture"),                                 # fixture source
        ev(model="fixture-model"),                                      # fixture model
        ev(etype="token_usage"),                                        # wrong type
        ev(age_h=24 * 8, dur=999),                                      # out of 7d window
        ev(status="running", dur=10000, tok=5),                         # progress row
    ]
    write(p, rows, junk=["not json", "{bad", '{"event_type": "model_call"}', '{"event_type":"model_call","timestamp":"zzz"}', ""])
    out = rs.aggregate_routing(7, path=str(p), now=NOW)
    by = {(r["model_used"], r["agent_type"], r["status"]): r for r in out}
    assert set(by) == {("m1", "a1", "succeeded"), ("m1", "a1", "failed"),
                       ("m2", "laneX", "succeeded"), ("m1", "a1", "running")}, set(by)
    s = by[("m1", "a1", "succeeded")]
    assert s["count"] == 2 and approx(s["avg_latency"], 200.0) and approx(s["avg_tokens"], 20.0), s
    f = by[("m1", "a1", "failed")]
    assert f["count"] == 1 and approx(f["avg_latency"], 50.0) and f["avg_tokens"] == 0.0, f
    assert out[0]["count"] == 2  # sorted by count desc
    # success rate: terminal = 2 succeeded + 1 failed + 1 m2 succeeded; running excluded
    assert approx(rs.success_rate(24, path=str(p), now=NOW), 3 / 4 * 100.0)
    # avg latency of successes: (100+300+200)/3
    assert approx(rs.avg_latency_ms(24, path=str(p), now=NOW), 200.0)
    # window narrower than all rows -> no data
    assert rs.success_rate(0.5, path=str(p), now=NOW) is None
    assert rs.avg_latency_ms(0.5, path=str(p), now=NOW) is None


def test_missing_and_env(tmp):
    missing = str(tmp / "nope.jsonl")
    assert rs.aggregate_routing(7, path=missing, now=NOW) == []
    assert rs.success_rate(24, path=missing, now=NOW) is None
    assert rs.avg_latency_ms(24, path=missing, now=NOW) is None
    import os
    p = tmp / "env.jsonl"
    write(p, [ev()])
    old = os.environ.get("AGENT_RUN_EVENTS_PATH")
    os.environ["AGENT_RUN_EVENTS_PATH"] = str(p)
    try:
        assert rs.events_path() == str(p)
        assert len(rs.aggregate_routing(7, now=NOW)) == 1
    finally:
        if old is None:
            del os.environ["AGENT_RUN_EVENTS_PATH"]
        else:
            os.environ["AGENT_RUN_EVENTS_PATH"] = old


def test_switchboard(tmp):
    d = tmp / ".agents" / "telemetry"
    d.mkdir(parents=True)
    lines = [
        {"ts": NOW.timestamp() - 3600, "local": True, "profile": "a"},
        {"ts": NOW.timestamp() - 7200, "local": False, "profile": "b"},
        {"ts": NOW.timestamp() - 86400 * 30, "local": True, "profile": "old"},
    ]
    (d / "routing-decisions.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\nbad\n")
    r = rs.switchboard_decisions(7, repo_root=str(tmp), now=NOW)
    assert r["total"] == 2 and r["local"] == 1 and r["by_profile"] == {"a": 1, "b": 1}, r
    assert rs.switchboard_decisions(7, repo_root=str(tmp / "none"), now=NOW)["total"] == 0


def test_migration():
    executed = []
    stub = types.ModuleType("alembic")
    stub.op = types.SimpleNamespace(execute=lambda sql: executed.append(str(sql)))
    saved = sys.modules.get("alembic")
    sys.modules["alembic"] = stub
    sys.path.insert(0, str(VERSIONS))
    try:
        mig = importlib.import_module("20261010_01_meta_optimization")
        assert mig.down_revision == "20260125_01" and mig.revision == "20261010_01"
        mig.upgrade()
        up = "\n".join(executed)
        executed.clear()
        mig.downgrade()
        down = "\n".join(executed)
    finally:
        sys.path.remove(str(VERSIONS))
        if saved is None:
            del sys.modules["alembic"]
        else:
            sys.modules["alembic"] = saved
    for t in ("harness_improvement_proposals", "harness_evolution_history", "harness_performance_baselines"):
        assert f"CREATE TABLE IF NOT EXISTS {t}" in up, t
        assert f"DROP TABLE IF EXISTS {t}" in down, t
    assert "CREATE TABLE " not in up.replace("CREATE TABLE IF NOT EXISTS", "")  # idempotent only
    assert "idx_improvement_proposals_status" in up


def test_cli_args(tmp):
    sys.modules.setdefault("asyncpg", types.ModuleType("asyncpg"))
    sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))
    import meta_optimizer as mo
    a = mo.parse_args(["--days", "3", "--output-dir", str(tmp / "o")])
    assert a.days == 3 and a.output_dir == str(tmp / "o")
    d = mo.parse_args([])
    assert d.days == 7 and d.output_dir is None
    prop = mo.ImprovementProposal(
        id="i", target=mo.OptimizationTarget.ROUTING_RULES, priority=mo.ProposalPriority.LOW,
        title="t", description="d", current_state="c", proposed_change="p", expected_impact="e",
        estimated_improvement_pct=1.0, confidence_score=0.5, evidence={}, implementation_steps=[],
        rollback_plan="r", created_at=NOW)
    path = mo.dump_proposals([prop], str(tmp / "o" / "nested"))
    data = json.loads(path.read_text())
    assert data[0]["id"] == "i" and data[0]["target"] == "routing_rules", data


def test_analyses_never_overlap():
    # Live failure 2026-10-10: gather() on one asyncpg connection -> "another operation is in progress".
    import asyncio
    import meta_optimizer as mo
    opt = mo.MetaOptimizer.__new__(mo.MetaOptimizer)
    state = {"active": 0, "max": 0, "order": []}

    def probe(name, result):
        async def run(days):
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
            await asyncio.sleep(0.01)
            state["active"] -= 1
            state["order"].append(name)
            if result == "boom":
                raise RuntimeError("boom")
            return result
        return run

    opt.analyze_routing_accuracy = probe("routing", "r")
    opt.analyze_hint_effectiveness = probe("hints", "boom")
    opt.analyze_lesson_library = probe("lessons", None)
    opt.analyze_tool_discovery = probe("tools", "t")
    got = asyncio.run(opt.generate_all_proposals(3))
    assert state["max"] == 1, state
    assert state["order"] == ["routing", "hints", "lessons", "tools"], state
    assert got == ["r", "t"], got  # a failing analysis is logged and skipped, others still run


def test_llm_failure_is_reported_not_hidden(tmp):
    # Live failure 2026-10-10: a 120s client timeout raised TimeoutError (empty str) and the
    # empty response was then logged as "no routing optimization opportunities".
    import asyncio
    import logging
    import meta_optimizer as mo
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    mo.logger.addHandler(handler)
    try:
        opt = mo.MetaOptimizer.__new__(mo.MetaOptimizer)
        opt.llama_url = "http://127.0.0.1:1"

        class TimingOut:
            def post(self, *a, **k):
                raise asyncio.TimeoutError()
        opt.http_client = TimingOut()
        assert asyncio.run(opt.call_local_llm("x")) == ""
        assert any("TimeoutError" in r.getMessage() for r in records), [r.getMessage() for r in records]

        events = tmp / "llm-events.jsonl"
        ts = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
        events.write_text(json.dumps({"event_type": "model_call", "model": "m", "agent_id": "a",
                                      "status": "succeeded", "duration_ms": 10, "timestamp": ts,
                                      "tokens": {"total": 5}, "source": "real"}) + "\n")
        os.environ["AGENT_RUN_EVENTS_PATH"] = str(events)

        async def empty(*a, **k):
            return ""
        opt.call_local_llm = empty
        records.clear()
        assert asyncio.run(opt.analyze_routing_accuracy(36500)) is None
        msgs = [r.getMessage() for r in records]
        assert any("skipped: local LLM returned nothing" in m for m in msgs), msgs
        assert not any("No routing optimization opportunities" in m for m in msgs), msgs
    finally:
        mo.logger.removeHandler(handler)
        os.environ.pop("AGENT_RUN_EVENTS_PATH", None)


def test_no_routing_log_reference():
    for f in sorted(MO.glob("*.py")):
        assert "routing_log" not in f.read_text(), f"routing_log still referenced in {f.name}"


def test_model_call_telemetry_agent_id(tmp):
    # Verify dispatch._write_progress emits agent_id and lane_id on model_call
    sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
    import dispatch
    events_path = tmp / "telemetry_events.jsonl"
    os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(events_path)
    try:
        progress_file = tmp / "test.progress.json"
        # 1. Default fallback with source="delegate-to-local"
        dispatch._write_progress(progress_file, 10, 100, 1.5, 6.7, None, "done", role="implementer")
        lines = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
        assert len(lines) >= 1
        ev = lines[-1]
        assert ev["event_type"] == "model_call"
        assert ev["agent_id"] == "local-qwen"
        assert ev["lane_id"] == "local"
        assert ev["role"] == "implementer"

        # 2. Explicit agent_id and lane_id
        dispatch._write_progress(progress_file, 20, 100, 2.0, 10.0, None, "done",
                                 agent_id="custom-agent", lane_id="custom-lane", role="reviewer")
        lines = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
        ev = lines[-1]
        assert ev["agent_id"] == "custom-agent"
        assert ev["lane_id"] == "custom-lane"
        assert ev["role"] == "reviewer"

        # 3. Environment variable override
        os.environ["AQ_AGENT_ID"] = "env-agent"
        os.environ["AQ_LANE_ID"] = "env-lane"
        dispatch._write_progress(progress_file, 30, 100, 3.0, 10.0, None, "done")
        lines = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
        ev = lines[-1]
        assert ev["agent_id"] == "env-agent"
        assert ev["lane_id"] == "env-lane"
    finally:
        os.environ.pop("AQ_AGENT_RUN_EVENTS_PATH", None)
        os.environ.pop("AQ_AGENT_ID", None)
        os.environ.pop("AQ_LANE_ID", None)


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_aggregate(tmp)
        test_missing_and_env(tmp)
        test_switchboard(tmp)
        test_cli_args(tmp)
        test_llm_failure_is_reported_not_hidden(tmp)
        test_model_call_telemetry_agent_id(tmp)
    test_analyses_never_overlap()
    test_migration()
    test_no_routing_log_reference()
    print("PASS")


if __name__ == "__main__":
    main()
