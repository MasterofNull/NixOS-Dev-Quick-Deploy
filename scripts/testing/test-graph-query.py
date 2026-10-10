#!/usr/bin/env python3
"""Fixture tests: aq-graph-query (search/symbol/neighbors/impact/types), staleness, MCP bridge tool, dashboard route."""
import asyncio
import importlib.util
import json
import subprocess
import sys
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))
import understand_graph as ug  # noqa: E402

CLI = REPO / "scripts" / "ai" / "aq-graph-query"
GEN = "2026-07-01T00:00:00Z"
NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)  # 19 days after GEN

NODES = [
    {"id": "file:svc/switchboard.py", "type": "file", "name": "switchboard.py", "filePath": "svc/switchboard.py", "summary": "Routes chat requests", "tags": ["router"]},
    {"id": "function:svc/switchboard.py:route", "type": "function:", "name": "route", "filePath": "svc/switchboard.py", "summary": "pick a backend", "startLine": 10, "endLine": 20},
    {"id": "file:svc/client.py", "type": "code", "name": "client.py", "filePath": "svc/client.py", "summary": "calls the switchboard"},
    {"id": "function:svc/client.py:send", "type": "function", "name": "send", "filePath": "svc/client.py", "summary": "send"},
    {"id": "file:tests/test_sw.py", "type": "file", "name": "test_sw.py", "filePath": "tests/test_sw.py", "summary": "tests"},
    {"id": "doc:readme", "type": "docs", "label": "README", "path": "README.md", "summary": "overview of switchboard"},
    {"id": "job:ci", "type": "function:job", "name": "scan", "filePath": ".github/workflows/x.yml", "summary": "ci"},
]
EDGES = [
    {"source": "file:svc/switchboard.py", "target": "function:svc/switchboard.py:route", "type": "contains"},
    {"source": "file:svc/client.py", "target": "function:svc/client.py:send", "type": "contains"},
    {"source": "file:svc/client.py", "target": "file:svc/switchboard.py", "type": "imports"},
    {"source": "function:svc/client.py:send", "target": "function:svc/switchboard.py:route", "type": "calls"},
    {"source": "file:tests/test_sw.py", "target": "file:svc/switchboard.py", "type": "tests"},
]


def make_root(tmp: Path, generated=GEN, wiki=True, config=None) -> Path:
    ua = tmp / ".understand-anything"
    ua.mkdir(parents=True)
    (ua / "knowledge-graph.json").write_text(json.dumps(
        {"metadata": {"generated": generated}, "nodes": NODES, "edges": EDGES}))
    if wiki:
        (ua / "wiki").mkdir()
        (ua / "wiki" / ".wiki-meta.json").write_text(json.dumps(
            {"a": {"graph_generated": generated, "generated": "2026-07-02T00:00:00Z"}}))
    if config:
        (tmp / "config").mkdir()
        (tmp / "config" / "understand-anything.json").write_text(json.dumps(config))
    return tmp


def cli(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), "--root", str(root), "--json", *args],
                          capture_output=True, text=True, check=False)


def test_types(root):
    tc = ug.type_counts(ug.load_graph(root))
    assert tc["raw"]["function:"] == 1 and tc["raw"]["docs"] == 1
    n = tc["normalised"]
    assert n == {"function": 2, "file": 3, "document": 1, "ci-job": 1} or (
        n["function"] == 2 and n["file"] == 3 and n["document"] == 1 and n["ci-job"] == 1), n
    assert ug.normalize_type("docs:section") == "section" and ug.normalize_type("weird") == "other"
    assert ug.normalize_type(None) == "other"


def test_search_symbol_neighbors_impact(root):
    r = json.loads(cli(root, "search", "switchboard").stdout)
    assert r["results"][0]["name"] == "switchboard.py", r["results"][0]   # exact-prefix name beats summary hits
    assert {x["name"] for x in r["results"]} >= {"switchboard.py", "client.py", "README"}
    assert all(x["type"] in ug.TYPE_MAP.values() for x in r["results"])
    assert json.loads(cli(root, "search", "zzzz").stdout)["count"] == 0
    only_fn = json.loads(cli(root, "search", "route", "--type", "function").stdout)["results"]
    assert [x["name"] for x in only_fn] == ["route"]

    s = json.loads(cli(root, "symbol", "route").stdout)["matches"][0]
    assert s["type"] == "function" and s["called_by"] == ["send"] and s["file"] == "svc/switchboard.py"
    assert cli(root, "symbol", "nope").returncode == 1

    nb = json.loads(cli(root, "neighbors", "svc/switchboard.py").stdout)["neighbors"]
    assert {x["name"] for x in nb} == {"route", "client.py", "test_sw.py"} and all(x["depth"] == 1 for x in nb)
    nb2 = json.loads(cli(root, "neighbors", "svc/switchboard.py", "--depth", "2").stdout)["neighbors"]
    assert "send" in {x["name"] for x in nb2}
    assert cli(root, "neighbors", "no-such-node").returncode == 1

    im = json.loads(cli(root, "impact", "svc/switchboard.py").stdout)
    assert {x["name"] for x in im["nodes"]} == {"switchboard.py", "route"}
    deps = {d["name"]: d["via"] for d in im["dependents"]}
    assert deps == {"client.py": ["imports"], "send": ["calls"], "test_sw.py": ["tests"]}, deps
    assert cli(root, "impact", "missing/file.py").returncode == 1

    text = subprocess.run([sys.executable, str(CLI), "--root", str(root), "impact", "svc/switchboard.py"],
                          capture_output=True, text=True).stdout
    assert "3 dependent(s)" in text


def test_staleness():
    with tempfile.TemporaryDirectory() as d:
        root = make_root(Path(d), config={"staleness": {"max_age_days": 14, "max_commits": 300}})
        st = ug.staleness(root, now=NOW, commit_counter=lambda r, t: 5)
        assert st["stale"] and st["reasons"] == ["graph age 19d > max 14d"], st
        assert st["graph_age_days"] == 19.0 and st["wiki_vs_graph"] == "in-sync" and st["wiki_age_days"] == 18.0
        fresh = ug.staleness(root, now=NOW - timedelta(days=10), commit_counter=lambda r, t: 5)
        assert not fresh["stale"] and fresh["reasons"] == []
        many = ug.staleness(root, now=NOW - timedelta(days=10), commit_counter=lambda r, t: 301)
        assert many["stale"] and "301 commits" in many["reasons"][0]
        unknown = ug.staleness(root, now=NOW - timedelta(days=10), commit_counter=lambda r, t: None)
        assert not unknown["stale"] and unknown["commits_since_graph"] is None
    with tempfile.TemporaryDirectory() as d:  # limits come from config, wiki behind graph is reported
        root = make_root(Path(d), config={"staleness": {"max_age_days": 365, "max_commits": 1}})
        meta = root / ".understand-anything" / "wiki" / ".wiki-meta.json"
        meta.write_text(json.dumps({"a": {"graph_generated": "OLD", "generated": "2026-06-01T00:00:00Z"}}))
        st = ug.staleness(root, now=NOW, commit_counter=lambda r, t: 2)
        assert st["max_age_days"] == 365 and st["wiki_vs_graph"] == "behind"
        assert any("2 commits" in r for r in st["reasons"]) and "wiki older than graph" in st["reasons"]
    with tempfile.TemporaryDirectory() as d:
        st = ug.staleness(Path(d), now=NOW)
        assert st["stale"] and st["reasons"] == ["graph missing"]
        p = subprocess.run([sys.executable, str(CLI), "--root", d, "staleness", "--check"], capture_output=True, text=True)
        assert p.returncode == 1 and "graph missing" in p.stdout
    # --check exit codes via the CLI (real git absent in tmp dir -> commits unknown; age alone decides)
    with tempfile.TemporaryDirectory() as d:
        root = make_root(Path(d))
        assert cli(root, "staleness", "--check").returncode == 1          # fixture graph is >14d old
        assert cli(root, "staleness").returncode == 0                      # no --check: report only
        fresh_gen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory() as d:
        root = make_root(Path(d), generated=fresh_gen, wiki=False)
        assert cli(root, "staleness", "--check").returncode == 0


def test_dashboard_route(root):
    spec = importlib.util.spec_from_file_location("understand_route", REPO / "dashboard/backend/api/routes/understand.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._REPO_ROOT = root
    out = asyncio.run(mod.get_understand_summary())
    assert out["nodes"] == len(NODES) and out["edges"] == len(EDGES)
    assert out["node_types"]["function"] == 2 and out["edge_types"]["contains"] == 2
    assert out["stale"] is True and out["state"] == "partial"
    assert set(out["staleness"]) >= {"graph_age_days", "commits_since_graph", "wiki_age_days", "wiki_vs_graph", "reasons"}
    assert [r.path for r in mod.router.routes] == ["/understand/summary"] and mod.router.routes[0].methods == {"GET"}
    main_src = (REPO / "dashboard/backend/api/main.py").read_text()
    assert "understand_mod.router" in main_src


def test_bridge_tool():
    # The real graph is an untracked generated artifact (absent in CI): use a fixture build.
    tmp = tempfile.TemporaryDirectory()
    fixture_root = make_root(Path(tmp.name), config={"staleness": {"max_age_days": 14, "max_commits": 300}})
    os.environ["UA_GRAPH_PATH"] = str(ug.graph_path(fixture_root))
    spec = importlib.util.spec_from_file_location("bridge", REPO / "scripts/ai/mcp-bridge-hybrid.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert any(t["name"] == "graph_query" for t in mod.TOOLS)
    assert "error" in json.loads(mod._call_tool("graph_query", {"action": "bogus"}))
    assert "error" in json.loads(mod._call_tool("graph_query", {"action": "search"}))
    got = json.loads(mod._call_tool("graph_query", {"action": "staleness"}))
    assert "stale" in got and "max_age_days" in got
    argv_guard = json.loads(mod._call_tool("graph_query", {"action": "search", "target": "--root=/etc"}))
    assert argv_guard.get("query") == "--root=/etc"  # option-looking text is data, not a flag


def test_wiring():
    cfg = json.loads((REPO / "config/understand-anything.json").read_text())
    assert cfg["staleness"]["max_age_days"] == 14 and cfg["staleness"]["max_commits"] == 300
    assert len(cfg["pin"]["rev"]) == 40
    ua = (REPO / "scripts/ai/aq-understand-anything").read_text()
    assert "git pull" not in ua and "--depth 1 \"$REPO_URL\"" not in ua and "PINNED_REV" in ua
    assert "aq-graph-query" in (REPO / "ai-stack/local-agents/builtin_tools/shell_tools.py").read_text()
    for f, needle in (("scripts/testing/harness_qa/phases/phase0.py", "_check_understand_graph_freshness(ctx)"),
                      ("scripts/ai/_aq-qa-bash", "0.10.59")):
        assert needle in (REPO / f).read_text(), f


def main():
    with tempfile.TemporaryDirectory() as d:
        root = make_root(Path(d))
        test_types(root)
        test_search_symbol_neighbors_impact(root)
        test_dashboard_route(root)
    test_staleness()
    test_bridge_tool()
    test_wiring()
    print("PASS: graph query (search/symbol/neighbors/impact/types), staleness, bridge tool, dashboard route")


if __name__ == "__main__":
    main()
