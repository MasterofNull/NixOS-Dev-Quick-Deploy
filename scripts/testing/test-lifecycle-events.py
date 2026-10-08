#!/usr/bin/env python3
"""Contract tests for the typed lifecycle event adapter (ECC P0-C). Side-effect free."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("lifecycle_events", ROOT / "scripts/ai/lib/lifecycle_events.py")
LE = importlib.util.module_from_spec(spec)
sys.modules["lifecycle_events"] = LE
spec.loader.exec_module(LE)

PY = sys.executable


def ev(event="pre", **kw):
    base = {"source": "claude", "target": "tool-x", "event": event, "payload": {"k": "v"}}
    base.update(kw)
    return base


def py(code, name="h", events=("pre",), **kw):
    return LE.Handler(name, [PY, "-c", code], events, **kw)


def rejected(raw, **kw):
    try:
        LE.validate_event(raw, **kw)
    except LE.EventRejected as e:
        return e.args[0]
    return None


def test_validation():
    assert LE.validate_event(ev())["evidence_id"].startswith("lce-")
    assert rejected("x") == "not_object"
    assert rejected(ev(bogus=1)) == "unknown_field"
    assert rejected(ev(event="boot")) == "bad_event"
    assert rejected(ev(source="../etc")) == "bad_source"
    assert rejected(ev(payload_classification="secret")) == "bad_classification"
    assert rejected(ev(timeout_s=0)) == "bad_timeout"
    assert rejected(ev(timeout_s=True)) == "bad_timeout"
    assert rejected(ev(loop_budget=99)) == "bad_loop_budget"
    assert rejected(ev(fail_policy="maybe")) == "bad_fail_policy"
    assert rejected(ev(payload=[1])) == "bad_payload"
    assert rejected(ev(payload={"a": "x" * 70000})) == "payload_too_large"
    assert rejected(ev(capability_lease="a b")) == "bad_lease"
    assert rejected(ev(), require_lease=True) == "lease_required"
    assert rejected(ev(capability_lease="lease-1"), require_lease=True) is None
    r = LE.LifecycleRunner()
    assert r.emit({"event": "pre"}) == "rejected" and r.totals["rejected"] == 1


def test_ok_and_env_isolation():
    os.environ["LCE_FAKE_SECRET"] = "s3" + "cr3t-" + os.urandom(4).hex()
    r = LE.LifecycleRunner()
    code = ("import os,sys,json;e=json.load(sys.stdin);"
            "assert 'LCE_FAKE_SECRET' not in os.environ and 'HOME' not in os.environ;"
            "assert os.environ['EXTRA']=='1' and os.environ['LIFECYCLE_EVENT']=='pre';"
            "assert e['source']=='claude'")
    r.register(py(code, env={"EXTRA": "1"}))
    assert r.emit(ev()) == "queued"
    out = r.drain()
    assert out[0]["outcome"] == "ok" and out[0]["decision"] == "allow", out
    del os.environ["LCE_FAKE_SECRET"]


def test_missing_tool_timeout_crash_policies():
    r = LE.LifecycleRunner()
    r.register(LE.Handler("miss-closed", ["/nonexistent/tool-zz"], ["pre"], fail_policy="closed"))
    r.register(LE.Handler("miss-open", ["no-such-tool-zz"], ["failure"], fail_policy="open"))
    r.register(py("import time;time.sleep(5)", "slow-open", ["compact"], timeout_s=0.3, fail_policy="open"))
    r.register(py("import time;time.sleep(5)", "slow-closed", ["stop"], timeout_s=0.3, fail_policy="closed"))
    r.register(py("raise SystemExit(3)", "crash-open", ["post"], fail_policy="open"))
    r.register(py("import os;os.abort()", "crash-closed2", ["failure"], fail_policy="closed"))
    for e in ("pre", "failure", "compact", "stop", "post"):
        r.emit(ev(e))
    res = {x["event"]: x for x in r.drain()}
    assert res["pre"]["outcome"] == "missing_tool" and res["pre"]["decision"] == "deny"
    # failure event has miss-open (allow) and crash-closed2 (deny) -> overall deny
    assert res["failure"]["decision"] == "deny"
    assert {h["outcome"] for h in res["failure"]["handlers"]} == {"missing_tool", "handler_error"}
    assert res["compact"]["outcome"] == "timeout" and res["compact"]["decision"] == "allow"
    assert res["stop"]["outcome"] == "timeout" and res["stop"]["decision"] == "deny"
    assert res["post"]["outcome"] == "handler_error" and res["post"]["decision"] == "allow"
    t = r.telemetry()["handlers"]
    assert t["slow-open"]["timeouts"] == 1 and t["miss-closed"]["missing_tool"] == 1
    assert t["crash-open"]["failures"] == 1


def test_lease_policy():
    r = LE.LifecycleRunner()
    r.register(py("pass", "needs-lease", require_lease=True, fail_policy="closed"))
    r.emit(ev())
    assert r.drain()[0]["outcome"] == "lease_missing"
    r.emit(ev(capability_lease="lease-abc"))
    assert r.drain()[0]["outcome"] == "ok"


def test_recursion_and_budget():
    r = LE.LifecycleRunner()
    # handler on 'pre' re-emits 'pre' (suppressed) and emits 'post' (allowed)
    code = ("import json;"
            "print(json.dumps({'source':'h','target':'t','event':'pre'}));"
            "print(json.dumps({'source':'h','target':'t','event':'post'}))")
    r.register(py(code, "emitter", ["pre"]))
    r.register(py("pass", "sink", ["post"]))
    r.emit(ev(loop_budget=2))
    out = r.drain()
    assert [x["event"] for x in out] == ["pre", "post"], out
    assert r.totals["recursion_suppressed"] == 1
    # budget exhaustion: loop_budget=0 blocks follow-up events
    r2 = LE.LifecycleRunner()
    r2.register(py(code, "emitter", ["pre"]))
    r2.emit(ev(loop_budget=0))
    assert [x["event"] for x in r2.drain()] == ["pre"]
    assert r2.totals["budget_exhausted"] >= 1


def test_disabled_and_backpressure_and_cancel():
    r = LE.LifecycleRunner(max_queue=2)
    r.register(py("raise SystemExit(1)", "bad", fail_policy="closed"))
    r.disable("bad")
    assert [r.emit(ev()) for _ in range(3)] == ["queued", "queued", "backpressure"]
    out = r.drain()
    assert out[0]["handlers"][0]["outcome"] == "disabled" and out[0]["decision"] == "allow"
    assert r.telemetry()["disabled"] == ["bad"] and r.totals["backpressure_dropped"] == 1
    r.emit(ev())
    assert r.cancel() == 1 and r.totals["cancelled"] == 1 and not r.queue
    r.enable("bad")
    assert r.telemetry()["disabled"] == []


def test_suspend_resume_and_dashboard_projection():
    with tempfile.TemporaryDirectory() as d:
        state = Path(d) / "state.json"
        assert LE.health_summary(None)["status"] == "dormant"
        assert LE.health_summary(state)["status"] == "dormant"
        r = LE.LifecycleRunner()
        r.register(py("pass", "ok-h"))
        r.register(py("raise SystemExit(2)", "bad-h", ["post"], fail_policy="open"))
        r.emit(ev("post")), r.drain()
        r.emit(ev()), r.emit(ev(capability_lease="L1"))
        r.disable("bad-h")
        r.save_state(state)
        assert oct(state.stat().st_mode & 0o777) == "0o600"
        r2 = LE.LifecycleRunner()
        r2.register(py("pass", "ok-h"))
        r2.register(py("raise SystemExit(2)", "bad-h", ["post"], fail_policy="open"))
        assert r2.load_state(state) == 2
        assert r2.disabled == {"bad-h"} and r2.stats["bad-h"]["failures"] == 1
        assert [x["outcome"] for x in r2.drain()] == ["ok", "ok"]
        h = LE.health_summary(state)
        assert h["status"] == "degraded" and h["handlers_registered"] == 2
        assert h["failures"] == 1 and h["calls"] == 1 and h["disabled"] == ["bad-h"]
        assert h["queue_depth"] == 2 and "latency_avg_ms" in h and "latency_max_ms" in h
        # tampered snapshot: bad events dropped on restore, not trusted
        data = json.loads(state.read_text())
        data["snapshot"]["queue"].append({"event": "boot"})
        state.write_text(json.dumps(data))
        r3 = LE.LifecycleRunner()
        assert r3.load_state(state) == 2 and r3.totals["rejected"] == 1
        state.write_text("{not json")
        assert LE.health_summary(state)["status"] == "unverified"
        try:
            r3.restore({"version": 9})
        except LE.EventRejected as e:
            assert e.args[0] == "bad_snapshot"
        else:
            raise AssertionError("bad snapshot accepted")


def test_telemetry_latency():
    r = LE.LifecycleRunner()
    r.register(py("pass", "t"))
    r.emit(ev()), r.emit(ev())
    r.drain()
    t = r.telemetry()["handlers"]["t"]
    assert t["count"] == 2 and t["failures"] == 0 and t["latency_max_ms"] > 0


def main():
    smoke = "--smoke" in sys.argv
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    if smoke:
        tests = [test_validation, test_recursion_and_budget, test_suspend_resume_and_dashboard_projection]
    for t in tests:
        t()
    print("PASS: lifecycle event adapter" + (" (smoke)" if smoke else f" ({len(tests)} groups)"))


if __name__ == "__main__":
    main()
