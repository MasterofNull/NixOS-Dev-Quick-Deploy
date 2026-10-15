#!/usr/bin/env python3
"""DEC-S0 regression: the live routing path must persist routing_decisions rows,
and write failures must be observable (counter + log), never silent.

Root cause being guarded: ModelCoordinator.classify_and_route never called any
recorder (inserts lived only in LLMRouter.execute_with_routing), and the router
DB path was cwd-relative (unwritable under systemd)."""

import logging
import os
import sqlite3
import sys
from pathlib import Path

import pytest

_HC = Path(__file__).resolve().parents[1]
for _p in (_HC, _HC / "extensions", _HC / "knowledge", _HC / "core"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import knowledge.llm_router as llm_router  # noqa: E402
LLMRouter = llm_router.LLMRouter


def _rows(db, table="routing_decisions"):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(f"SELECT * FROM {table}").fetchall()
    finally:
        conn.close()


def test_db_path_resolution(monkeypatch, tmp_path):
    monkeypatch.delenv("AQ_ROUTING_METRICS_DB_PATH", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    assert llm_router._resolve_metrics_db(None) == "routing_metrics.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert llm_router._resolve_metrics_db(None) == str(tmp_path / "routing_metrics.db")
    monkeypatch.setenv("AQ_ROUTING_METRICS_DB_PATH", str(tmp_path / "x.db"))
    assert llm_router._resolve_metrics_db(None) == str(tmp_path / "x.db")
    assert llm_router._resolve_metrics_db("/explicit.db") == "/explicit.db"


def test_record_route_decision_writes_row_and_migrates_legacy_db(tmp_path):
    db = str(tmp_path / "m.db")
    # legacy schema without the DEC-S0 columns
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE routing_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                 " timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, task_type TEXT, complexity TEXT,"
                 " tier TEXT, model TEXT, success BOOLEAN, escalated BOOLEAN DEFAULT 0,"
                 " escalated_from TEXT, response_time_ms INTEGER, cost_estimate REAL)")
    conn.commit()
    conn.close()
    r = LLMRouter(metrics_db=db)
    assert r.record_route_decision("coding", "medium", "local", "qwen-coder", lane="local",
                                   source="test", alternatives=["a", "b"], cost_estimate=0.0)
    assert r.flush()
    rows = _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert (row["task_type"], row["model"], row["lane"], row["source"]) == (
        "coding", "qwen-coder", "local", "test")
    assert row["success"] is None and row["timestamp"]
    assert row["alternatives"] == '["a", "b"]'
    ws = r.write_stats
    assert (ws["queued"], ws["written"], ws["failed"], ws["dropped"]) == (1, 1, 0, 0)
    assert sqlite3.connect(db).execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    r.close()


def test_write_failure_is_counted_and_logged(tmp_path, caplog):
    r = LLMRouter(metrics_db=str(tmp_path / "m.db"))
    r.metrics_db = str(tmp_path / "no-such-dir" / "m.db")  # unopenable
    with caplog.at_level(logging.ERROR):
        assert r.record_route_decision("coding", "low", "local", "m") is True  # queued
        assert r.flush()
    assert r.write_stats["failed"] == 1 and r.write_stats["written"] == 0
    assert "routing_metrics write failed" in caplog.text
    assert "unable to open" in (r.last_write_error or "")
    r.close()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_readonly_db_file_is_counted_failure_without_exception(tmp_path, monkeypatch):
    db = tmp_path / "m.db"
    r = LLMRouter(metrics_db=str(db))
    r.flush()
    r.close()
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(db) + suffix)
        if f.exists():
            f.chmod(0o444)
    r2 = LLMRouter(metrics_db=str(db))  # init must not raise
    assert r2.record_route_decision("coding", "low", "local", "m") is True
    assert r2.flush()
    assert r2.write_stats["failed"] + r2.write_stats["init_failed"] >= 1
    assert r2.write_stats["written"] == 0
    r2.close()


def test_full_queue_drops_with_counter_and_never_blocks(tmp_path, monkeypatch):
    r = LLMRouter(metrics_db=str(tmp_path / "m.db"))
    monkeypatch.setattr(r, "_wq", __import__("queue").Queue(maxsize=1))
    # keep the writer from draining: pretend it is alive
    class _Alive:
        def is_alive(self): return True
    r._writer = _Alive()
    assert r.record_route_decision("a", "l", "t", "m") is True
    assert r.record_route_decision("a", "l", "t", "m") is False
    assert r.write_stats["queued"] == 1 and r.write_stats["dropped"] == 1


def test_init_failure_does_not_raise(tmp_path):
    r = LLMRouter(metrics_db=str(tmp_path / "missing" / "m.db"))
    assert r.write_stats["init_failed"] == 1


def test_escalation_and_advisor_writes_counted(tmp_path):
    db = str(tmp_path / "m.db")
    r = LLMRouter(metrics_db=db)
    r._record_escalation("local", "free", "x" * 500, "coding")
    r._record_advisor_consultation("t1", "architecture", "local", "m", "adv", 10.0, 5,
                                   "q" * 500, "g" * 500)
    assert r.flush()
    assert len(_rows(db, "escalations")) == 1
    adv = _rows(db, "advisor_consultations")
    assert len(adv) == 1 and len(adv[0]["question"]) == 200
    assert len(_rows(db, "escalations")[0]["reason"]) == 200


def test_classify_and_route_persists_decision(monkeypatch, tmp_path):
    """End to end through the live path (ModelCoordinator), not just the recorder."""
    db = str(tmp_path / "live.db")
    monkeypatch.setattr(llm_router, "_router", LLMRouter(metrics_db=db))
    import extensions.model_coordinator as mc
    assert mc._LLM_ROUTER_AVAILABLE, "llm_router must import in the coordinator's own env"
    coord = mc.ModelCoordinator()
    decision = coord.classify_and_route("fix the failing unit test in parser.py", {})
    assert llm_router.get_router().flush()
    rows = _rows(db)
    assert len(rows) == 1, "classify_and_route did not persist a routing decision"
    assert rows[0]["model"] == decision.primary_model
    assert rows[0]["source"] == "model_coordinator"
    assert rows[0]["lane"] in ("local", "remote")
    # no task text persisted
    assert "parser.py" not in " ".join(str(v) for v in tuple(rows[0]))


def test_microbenchmark_recorder_overhead(monkeypatch, tmp_path, capsys):
    """classify_and_route per-call cost, recorder on vs off (in-process, n=1000)."""
    import statistics
    import time
    import extensions.model_coordinator as mc
    router = LLMRouter(metrics_db=str(tmp_path / "bench.db"))
    monkeypatch.setattr(llm_router, "_router", router)
    coord = mc.ModelCoordinator()
    task = "fix the failing unit test in parser.py"

    def run(n=1000):
        ts = []
        for _ in range(n):
            t = time.perf_counter()
            coord.classify_and_route(task, {})
            ts.append((time.perf_counter() - t) * 1000)
        ts.sort()
        return statistics.median(ts), ts[int(n * 0.99)], sum(ts) / n

    run(50)
    router.flush(30)
    monkeypatch.setattr(mc, "_LLM_ROUTER_AVAILABLE", False)
    off = run()
    monkeypatch.setattr(mc, "_LLM_ROUTER_AVAILABLE", True)
    on = run()
    router.flush(30)
    ws = dict(router.write_stats)
    print(f"BENCH n=1000 ms off p50={off[0]:.3f} p99={off[1]:.3f} mean={off[2]:.3f} | "
          f"on p50={on[0]:.3f} p99={on[1]:.3f} mean={on[2]:.3f} | stats={ws}")
    assert ws["queued"] + ws["dropped"] >= 1000
    assert on[0] - off[0] < 1.0  # enqueue must be sub-millisecond at the median
    router.close()


def test_live_db_not_group_writable_and_snapshot_published_on_close(tmp_path):
    db = tmp_path / "live.db"
    r = LLMRouter(metrics_db=str(db))
    assert (db.stat().st_mode & 0o777) == 0o640  # owner rw, group read only
    snap = Path(r.snapshot_db)
    assert snap.name == "live.snapshot.db"
    r.record_route_decision("coding", "low", "local", "qwen-coder", lane="local", source="t")
    assert r.flush()
    r.close()  # first write snapshots immediately; shutdown snapshots anything dirty
    assert snap.exists() and (snap.stat().st_mode & 0o777) == 0o644
    assert not Path(str(snap) + ".tmp").exists()
    # readable mode=ro with no WAL sidecar files needed
    ro = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
    try:
        assert ro.execute("SELECT COUNT(*) FROM routing_decisions").fetchone()[0] == 1
    finally:
        ro.close()
    assert not Path(str(snap) + "-wal").exists() and not Path(str(snap) + "-shm").exists()
    ws = r.write_stats
    assert ws["snapshots"] >= 1 and ws["snapshot_failed"] == 0 and ws["last_snapshot_ts"] > 0


def test_snapshot_is_atomic_for_concurrent_readers(tmp_path):
    import threading
    r = LLMRouter(metrics_db=str(tmp_path / "live.db"))
    for i in range(50):
        r.record_route_decision("coding", "low", "local", f"m{i}")
    assert r.flush()
    conn = sqlite3.connect(r.metrics_db)
    r._snapshot(conn)  # first publish so readers always have a file
    stop = threading.Event()
    errors, reads = [], [0]

    def reader():
        while not stop.is_set():
            try:
                c = sqlite3.connect(f"file:{r.snapshot_db}?mode=ro", uri=True)
                n = c.execute("SELECT COUNT(*) FROM routing_decisions").fetchone()[0]
                c.close()
                assert n == 50
                reads[0] += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

    t = threading.Thread(target=reader)
    t.start()
    for _ in range(40):
        r._snapshot(conn)
    stop.set()
    t.join()
    conn.close()
    assert not errors, errors[:3]
    assert reads[0] > 0 and r.write_stats["snapshots"] >= 41
    r.close()


def test_snapshot_failure_counted(tmp_path):
    r = LLMRouter(metrics_db=str(tmp_path / "live.db"))
    r.snapshot_db = str(tmp_path / "missing" / "s.db")
    conn = sqlite3.connect(r.metrics_db)
    r._snapshot(conn)
    conn.close()
    assert r.write_stats["snapshot_failed"] == 1 and r.write_stats["snapshots"] == 0


def test_bounded_shutdown_flushes_first_and_survives_hung_scheduler(tmp_path, monkeypatch):
    import asyncio
    import time
    r = LLMRouter(metrics_db=str(tmp_path / "live.db"))
    monkeypatch.setattr(llm_router, "_router", r)
    for i in range(20):
        r.record_route_decision("coding", "low", "local", f"m{i}")

    async def hung_stop():
        await asyncio.sleep(3600)

    t = time.monotonic()
    asyncio.run(llm_router.bounded_shutdown(hung_stop, stop_timeout=0.5))
    elapsed = time.monotonic() - t
    assert elapsed < 5, elapsed  # bounded by stop_timeout, not by the hung stop
    assert len(_rows(r.metrics_db)) == 20  # flushed before the scheduler stop
    ro = sqlite3.connect(f"file:{r.snapshot_db}?mode=ro", uri=True)
    try:
        assert ro.execute("SELECT COUNT(*) FROM routing_decisions").fetchone()[0] == 20
    finally:
        ro.close()
