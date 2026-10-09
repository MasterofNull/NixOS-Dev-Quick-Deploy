#!/usr/bin/env python3
"""AIDB Postgres<->Qdrant vector sync: stable ids, no-drop spool, drain retry, reconcile math.

Qdrant and the embed server are mocked. The real MCPServer methods are extracted from
server.py by AST (server.py itself needs sqlalchemy/pgvector/etc. at import time) and bound
to a stub, so the tests exercise the shipped code, not a copy.
"""
from __future__ import annotations

import ast
import asyncio
import logging
import subprocess
import sys
import tempfile
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AIDB = ROOT / "ai-stack" / "mcp-servers" / "aidb"
sys.path.insert(0, str(AIDB))
import vector_sync  # noqa: E402

METHODS = {
    "qdrant_vectorization_status", "schedule_qdrant_vectorization",
    "_vectorize_doc_to_qdrant", "drain_vectorize_spool_once",
}


def load_server_methods(max_queue: int = 2):
    tree = ast.parse((AIDB / "server.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MCPServer")
    fns = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in METHODS]
    assert {f.name for f in fns} == METHODS, {f.name for f in fns}
    ns = {
        "asyncio": asyncio, "vector_sync": vector_sync, "LOGGER": logging.getLogger("t"),
        "Any": typing.Any, "Dict": typing.Dict, "List": typing.List, "Optional": typing.Optional,
        "_QDRANT_VECTORIZE_MAX_CONCURRENCY": 2, "_QDRANT_VECTORIZE_MAX_QUEUE": max_queue,
        "_QDRANT_VECTORIZE_TIMEOUT_S": 5.0,
    }
    mod = ast.Module(body=fns, type_ignores=[])
    exec(compile(mod, "server.py[methods]", "exec"), ns)
    return {n: ns[n] for n in METHODS}


class FakeHTTP:
    def __init__(self, fail=False):
        self.fail, self.puts = fail, []

    async def put(self, url, json=None, timeout=None):
        self.puts.append((url, json))

        class R:
            status_code = 500 if self.fail else 200
        return R()


class Stub:
    def __init__(self, spool, http, embed_fail=False, max_queue=2):
        m = load_server_methods(max_queue)
        for name, fn in m.items():
            setattr(Stub, name, fn)
        self._vectorize_spool = spool
        self._external_http = http
        self._embed_fail = embed_fail
        self._qdrant_vectorize_pending = 0
        self._qdrant_vectorize_completed = self._qdrant_vectorize_failed = 0
        self._qdrant_vectorize_skipped = self._qdrant_vectorize_spooled = 0
        self._qdrant_vectorize_semaphore = asyncio.Semaphore(2)
        self.embed_calls = []

    async def embed_texts(self, texts):
        self.embed_calls.append(texts[0])
        if self._embed_fail:
            raise RuntimeError("embed down")
        return [[0.1] * 4]


def test_uuid5_stable_across_processes():
    code = "import sys;sys.path.insert(0,%r);import vector_sync as v;print(v.point_id('p','a/b.md'))" % str(AIDB)
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                           env={"PYTHONHASHSEED": str(s)}).stdout.strip() for s in (1, 2, 3)}
    assert outs == {vector_sync.point_id("p", "a/b.md")}, outs
    import uuid
    uuid.UUID(next(iter(outs)))  # valid Qdrant UUID point id


def test_distinct_projects_same_path_distinct_ids():
    assert vector_sync.point_id("a", "README.md") != vector_sync.point_id("b", "README.md")
    assert vector_sync.point_id("a", "x#chunk1") != vector_sync.point_id("a", "x#chunk2")
    ids = {vector_sync.point_id("p", f"d/{i}") for i in range(50000)}
    assert len(ids) == 50000  # md5[:8] would collide at this scale


def test_vectorize_upserts_by_uuid_and_keeps_payload(monkeypatch_env=None):
    import os
    os.environ["QDRANT_URL"] = "http://q"
    with tempfile.TemporaryDirectory() as d:
        http = FakeHTTP()
        s = Stub(vector_sync.PendingSpool(Path(d) / "sp.jsonl"), http)
        ok = asyncio.run(s._vectorize_doc_to_qdrant(
            title="T", content="c" * 5000, project="p", relative_path="r.md",
            source_trust_level="trusted", checksum="abc"))
        assert ok is True
        url, body = http.puts[0]
        pt = body["points"][0]
        assert pt["id"] == vector_sync.point_id("p", "r.md")
        for k in ("project", "title", "content", "relative_path", "source_trust_level", "imported_at"):
            assert k in pt["payload"], k
        assert pt["payload"]["checksum"] == "abc" and len(pt["payload"]["content"]) == 4000
        assert len(s.embed_calls[0]) == vector_sync.DEFAULT_EMBED_CHARS  # cap raised from 1200
        # Qdrant error -> False so the caller spools
        s2 = Stub(vector_sync.PendingSpool(Path(d) / "sp2.jsonl"), FakeHTTP(fail=True))
        assert asyncio.run(s2._vectorize_doc_to_qdrant(
            title="T", content="c", project="p", relative_path="r", source_trust_level="x")) is False


def test_embed_shrink_on_context_overflow():
    calls = []

    async def emb(texts):
        calls.append(len(texts[0]))
        if len(texts[0]) > 1000:
            raise RuntimeError("exceed_context_size_error")
        return [[1.0]]
    asyncio.run(vector_sync.embed_with_shrink(emb, "x" * 2400))
    assert calls == [2400, 1200, 600], calls


def test_queue_full_spools_not_drops():
    async def run():
        with tempfile.TemporaryDirectory() as d:
            sp = vector_sync.PendingSpool(Path(d) / "sp.jsonl")
            s = Stub(sp, FakeHTTP(), max_queue=1)
            s._qdrant_vectorize_pending = 1  # queue already full
            started = s.schedule_qdrant_vectorization(
                title="t", content="c", project="p", relative_path="a.md", source_trust_level="x")
            assert started is False and len(sp) == 1 and s._qdrant_vectorize_spooled == 1
            # durable: a new process-equivalent reload sees it
            assert len(vector_sync.PendingSpool(Path(d) / "sp.jsonl")) == 1
            # same doc spooled twice -> one entry (dedup by stable id)
            s.schedule_qdrant_vectorization(
                title="t", content="c2", project="p", relative_path="a.md", source_trust_level="x")
            assert len(sp) == 1
    asyncio.run(run())


def test_failed_vectorize_is_spooled():
    import os
    os.environ["QDRANT_URL"] = "http://q"

    async def run():
        with tempfile.TemporaryDirectory() as d:
            sp = vector_sync.PendingSpool(Path(d) / "sp.jsonl")
            s = Stub(sp, FakeHTTP(fail=True))
            assert s.schedule_qdrant_vectorization(
                title="t", content="c", project="p", relative_path="a.md", source_trust_level="x")
            for _ in range(20):
                await asyncio.sleep(0.01)
            assert len(sp) == 1 and s._qdrant_vectorize_failed == 1
    asyncio.run(run())


def test_drain_retries_then_clears():
    import os
    os.environ["QDRANT_URL"] = "http://q"

    async def run():
        with tempfile.TemporaryDirectory() as d:
            sp = vector_sync.PendingSpool(Path(d) / "sp.jsonl")
            pid = sp.add(title="t", content="c", project="p", relative_path="a.md", source_trust_level="x")
            http = FakeHTTP(fail=True)
            s = Stub(sp, http)
            assert await s.drain_vectorize_spool_once() == 0       # Qdrant down: stays queued
            assert len(sp) == 1 and sp._items[pid]["attempts"] == 1
            http.fail = False
            assert await s.drain_vectorize_spool_once() == 1       # recovered: retried and cleared
            assert len(sp) == 0
            assert len(vector_sync.PendingSpool(Path(d) / "sp.jsonl")) == 0
            assert http.puts[-1][1]["points"][0]["id"] == pid
    asyncio.run(run())


def test_spool_attempt_ceiling_and_compaction():
    with tempfile.TemporaryDirectory() as d:
        sp = vector_sync.PendingSpool(Path(d) / "sp.jsonl")
        pid = sp.add(title="t", content="c", project="p", relative_path="a", source_trust_level="x")
        for _ in range(vector_sync.MAX_SPOOL_ATTEMPTS):
            sp.bump_attempt(pid)
        assert sp.take(10) == [] and sp.exhausted() == 1 and len(sp) == 1  # kept, not retried forever
        for i in range(300):
            q = sp.add(title="t", content="c", project="p", relative_path=f"x{i}", source_trust_level="x")
            sp.mark_done(q)
        assert len(vector_sync.PendingSpool(Path(d) / "sp.jsonl")) == 1
        assert sum(1 for _ in open(Path(d) / "sp.jsonl")) < 250  # compacted


def test_reconcile_math():
    pg = [
        {"project": "a", "relative_path": "1", "checksum": "c1"},   # present, current
        {"project": "a", "relative_path": "2", "checksum": "c2"},   # present, stale
        {"project": "a", "relative_path": "3", "checksum": "c3"},   # missing
        {"project": "b", "relative_path": "1", "checksum": "d1"},   # same path other project: missing
        {"project": "b", "relative_path": "2", "checksum": "d2"},   # present, no stored checksum -> current
    ]
    pts = [
        (vector_sync.point_id("a", "1"), "c1"),
        (vector_sync.point_id("a", "2"), "OLD"),
        (vector_sync.point_id("b", "2"), None),
        (123456789, None),                                  # legacy 32-bit int id
        (vector_sync.point_id("gone", "x"), "z"),           # uuid orphan (doc deleted)
    ]
    r = vector_sync.reconcile(pg, pts)
    t = r["totals"]
    assert (t["postgres"], t["qdrant"], t["missing"], t["stale"], t["orphan"], t["legacy_orphan"]) == (5, 5, 2, 1, 2, 1), t
    assert r["per_project"]["a"] == {"postgres": 3, "missing": 1, "stale": 1}
    assert r["per_project"]["b"] == {"postgres": 2, "missing": 1, "stale": 0}
    assert r["legacy_ids"] == [123456789]
    assert {(m["project"], m["relative_path"]) for m in r["missing"]} == {("a", "3"), ("b", "1")}


def test_reconcile_cli_dry_run_and_prune_guard():
    """CLI main() with Postgres and Qdrant stubbed: dry-run reports, prune refuses while docs missing."""
    import importlib.machinery
    import importlib.util
    path = str(ROOT / "scripts" / "ai" / "aq-vector-reconcile")
    loader = importlib.machinery.SourceFileLoader("aqvr", path)
    spec = importlib.util.spec_from_loader("aqvr", loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    m.pg_rows = lambda project: [{"project": "a", "relative_path": "1", "checksum": "c"},
                                 {"project": "a", "relative_path": "2", "checksum": "c"}]
    m.qdrant_points = lambda q, c: iter([(vector_sync.point_id("a", "1"), "c"), (42, None)])
    deleted = []
    m._http = lambda method, url, body=None, headers=None, timeout=60: deleted.append((url, body)) or {}
    assert m.main([]) == 0 and not deleted                              # read-only default
    assert m.main(["--prune-legacy", "--apply-prune"]) == 2 and not deleted  # 1 doc missing: refuse
    assert m.main(["--prune-legacy", "--apply-prune", "--force"]) == 0
    assert deleted and deleted[0][1] == {"points": [42]}


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for name, fn in fns:
        fn()
        print(f"PASS {name}")
    print(f"PASS: {len(fns)} aidb vector sync tests")
