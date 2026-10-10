"""Read-only helpers over the Understand-Anything knowledge graph (stdlib only).

Single implementation shared by aq-graph-query, aq-wiki --status,
aq-understand-anything status, the phase-0 staleness check, and the dashboard
route GET /api/understand/summary. Nothing here writes or calls an LLM.

Refresh limits and the upstream pin live in config/understand-anything.json
(the one declared place); DEFAULT_* below only apply if that file is absent.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

DEFAULT_MAX_AGE_DAYS = 14
DEFAULT_MAX_COMMITS = 300

# Upstream emits ~28 spellings; collapse to a closed vocabulary.
TYPE_MAP: Dict[str, str] = {
    "file": "file", "code": "file", "markup-file": "file", "infra-file": "file",
    "script": "script", "script-file": "script",
    "config": "config", "config-file": "config",
    "document": "document", "doc": "document", "docs": "document",
    "documentation": "document", "doc-file": "document",
    "section": "section", "docs:section": "section", "docs-section": "section",
    "function": "function", "function:": "function",
    "function:job": "ci-job",
    "class": "class", "class:": "class",
    "infra": "infra", "infra:build-stage": "infra",
    "workflow-step": "workflow-step", "step": "workflow-step",
    "table": "table", "view": "view", "resource": "resource", "schema": "schema",
    "service": "service", "data": "data",
}

# edge types that mean "source depends on / refers to target"
DEPENDENCY_EDGES = {"imports", "calls", "extends", "tests", "tested_by", "configures", "documents"}


def normalize_type(raw: Optional[str]) -> str:
    key = str(raw or "").strip().lower()
    return TYPE_MAP.get(key, "other")


# ── config / paths ──────────────────────────────────────────────────────────

def repo_root() -> Path:
    env = os.environ.get("UA_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


def load_config(root: Path) -> dict:
    cfg = {
        "staleness": {"max_age_days": DEFAULT_MAX_AGE_DAYS, "max_commits": DEFAULT_MAX_COMMITS},
        "pin": {},
    }
    path = Path(root) / "config" / "understand-anything.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if isinstance(data.get("staleness"), dict):
        cfg["staleness"].update({k: v for k, v in data["staleness"].items() if isinstance(v, (int, float))})
    if isinstance(data.get("pin"), dict):
        cfg["pin"] = data["pin"]
    return cfg


def graph_path(root: Path) -> Path:
    # The graph is a generated, untracked artifact; UA_GRAPH_PATH lets tests and
    # tooling point consumers at another build without touching the repo copy.
    override = os.environ.get("UA_GRAPH_PATH")
    if override:
        return Path(override)
    return Path(root) / ".understand-anything" / "knowledge-graph.json"


_CACHE: dict = {}


def load_graph(root: Path) -> dict:
    """Parse the graph; cached on (path, mtime, size) so dashboard polling is cheap."""
    path = graph_path(root)
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    hit = _CACHE.get("graph")
    if hit and hit[0] == key:
        return hit[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    _CACHE["graph"] = (key, data)
    _CACHE.pop("index", None)
    return data


# ── staleness ────────────────────────────────────────────────────────────────

def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def git_commits_since(root: Path, since: datetime) -> Optional[int]:
    env = dict(os.environ)
    # the dashboard's bare PATH lacks git
    env["PATH"] = "/run/current-system/sw/bin:/run/wrappers/bin:" + env.get("PATH", "")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--count", f"--since={since.isoformat()}", "HEAD"],
            capture_output=True, text=True, timeout=20, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def wiki_info(root: Path, graph_generated: Optional[str]) -> dict:
    meta_path = Path(root) / ".understand-anything" / "wiki" / ".wiki-meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"present": False, "sections": 0, "oldest_generated": None, "behind_graph": None}
    # only per-section records count; aq-wiki also stores a "body_sha256" hash map in this file
    recs = [r for r in meta.values() if isinstance(r, dict) and "graph_generated" in r]
    gens = [r.get("generated") for r in recs if r.get("generated")]
    oldest = min(gens) if gens else None
    behind = any(r.get("graph_generated") != graph_generated for r in recs)
    return {"present": True, "sections": len(recs), "oldest_generated": oldest, "behind_graph": behind}


def staleness(root: Path, now: Optional[datetime] = None,
              commit_counter: Callable[[Path, datetime], Optional[int]] = git_commits_since) -> dict:
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    cfg = load_config(root)["staleness"]
    max_age = cfg.get("max_age_days", DEFAULT_MAX_AGE_DAYS)
    max_commits = cfg.get("max_commits", DEFAULT_MAX_COMMITS)
    out: dict = {
        "graph_present": False, "graph_generated": None, "graph_age_days": None,
        "commits_since_graph": None, "max_age_days": max_age, "max_commits": max_commits,
        "wiki": {"present": False}, "wiki_age_days": None, "wiki_vs_graph": None,
        "stale": True, "reasons": [],
    }
    path = graph_path(root)
    if not path.is_file():
        out["reasons"].append("graph missing")
        return out
    out["graph_present"] = True
    try:
        generated = load_graph(root).get("metadata", {}).get("generated")
    except (OSError, ValueError):
        out["reasons"].append("graph unreadable")
        return out
    gen_dt = _parse_ts(generated)
    if gen_dt is None:
        gen_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        generated = gen_dt.isoformat()
    out["graph_generated"] = generated
    age = (now - gen_dt).total_seconds() / 86400.0
    out["graph_age_days"] = round(age, 1)
    out["commits_since_graph"] = commit_counter(root, gen_dt)

    wiki = wiki_info(root, out["graph_generated"])
    out["wiki"] = wiki
    wiki_dt = _parse_ts(wiki.get("oldest_generated"))
    if wiki_dt:
        out["wiki_age_days"] = round((now - wiki_dt).total_seconds() / 86400.0, 1)
    if wiki["present"]:
        out["wiki_vs_graph"] = "behind" if (wiki["behind_graph"] or (wiki_dt and wiki_dt < gen_dt)) else "in-sync"

    if age > max_age:
        out["reasons"].append(f"graph age {age:.0f}d > max {max_age}d")
    n = out["commits_since_graph"]
    if n is not None and n > max_commits:
        out["reasons"].append(f"{n} commits since graph > max {max_commits}")
    if out["wiki_vs_graph"] == "behind":
        out["reasons"].append("wiki older than graph")
    out["stale"] = bool(out["reasons"])
    return out


def format_staleness(s: dict) -> List[str]:
    lines = [
        f"  graph_generated: {s['graph_generated'] or 'missing'}",
        f"  graph_age_days: {s['graph_age_days']} (max {s['max_age_days']})",
        f"  commits_since_graph: {s['commits_since_graph'] if s['commits_since_graph'] is not None else 'unknown'} (max {s['max_commits']})",
        f"  wiki_age_days: {s['wiki_age_days'] if s['wiki_age_days'] is not None else 'n/a'} vs graph: {s['wiki_vs_graph'] or 'n/a'}",
    ]
    verdict = "STALE: " + "; ".join(s["reasons"]) if s["stale"] else "FRESH"
    lines.append(f"  verdict: {verdict}")
    return lines


# ── summary (dashboard) ──────────────────────────────────────────────────────

def type_counts(graph: dict) -> dict:
    raw = Counter(str(n.get("type")) for n in graph.get("nodes", []))
    norm = Counter(normalize_type(n.get("type")) for n in graph.get("nodes", []))
    return {"raw": dict(raw.most_common()), "normalised": dict(norm.most_common())}


def summary(root: Path, **kw) -> dict:
    s = staleness(root, **kw)
    out = {"staleness": s, "stale": s["stale"], "nodes": 0, "edges": 0,
           "node_types": {}, "edge_types": {}, "state": "partial",
           "note": "graph regeneration pending" if s["stale"] else "current"}
    if s["graph_present"]:
        g = load_graph(root)
        out["nodes"] = len(g.get("nodes", []))
        out["edges"] = len(g.get("edges", []))
        out["node_types"] = type_counts(g)["normalised"]
        out["edge_types"] = dict(Counter(str(e.get("type")) for e in g.get("edges", [])).most_common())
    return out


# ── query ────────────────────────────────────────────────────────────────────

def _fp(n: dict) -> str:
    return str(n.get("filePath") or n.get("path") or "")


def _nm(n: dict) -> str:
    return str(n.get("name") or n.get("label") or n.get("id") or "")


def brief(n: dict) -> dict:
    d = {"id": n.get("id"), "type": normalize_type(n.get("type")), "name": _nm(n), "file": _fp(n),
         "summary": str(n.get("summary") or "")[:200]}
    if n.get("startLine") is not None:
        d["lines"] = [n.get("startLine"), n.get("endLine")]
    return d


class Index:
    def __init__(self, graph: dict):
        self.nodes = {n["id"]: n for n in graph.get("nodes", []) if "id" in n}
        self.out = defaultdict(list)
        self.inc = defaultdict(list)
        for e in graph.get("edges", []):
            self.out[e.get("source")].append(e)
            self.inc[e.get("target")].append(e)
        self.by_file = defaultdict(list)
        self.by_name = defaultdict(list)
        for n in self.nodes.values():
            if _fp(n):
                self.by_file[_fp(n)].append(n["id"])
            self.by_name[_nm(n)].append(n["id"])


def get_index(root: Path) -> Index:
    g = load_graph(root)
    hit = _CACHE.get("index")
    if hit and hit[0] is g:
        return hit[1]
    idx = Index(g)
    _CACHE["index"] = (g, idx)
    return idx


_TYPE_RANK = {"file": 0, "function": 1, "class": 2, "config": 3, "script": 4}


def search(idx: Index, text: str, limit: int = 20, ntype: Optional[str] = None) -> List[dict]:
    terms = [t for t in re.split(r"\s+", text.lower().strip()) if t]
    if not terms:
        return []
    scored = []
    for n in idx.nodes.values():
        if ntype and normalize_type(n.get("type")) != ntype:
            continue
        name = _nm(n).lower()
        nid = str(n["id"]).lower()
        summ = str(n.get("summary") or "").lower()
        tags = " ".join(str(t) for t in n.get("tags") or []).lower()
        score = 0
        for t in terms:
            s = 0
            if name == t:
                s = 100
            elif name.startswith(t):
                s = 60
            elif t in name:
                s = 40
            elif t in nid:
                s = 20
            if t in summ:
                s += 10
            if t in tags:
                s += 8
            score += s
        if score:
            scored.append((score, _TYPE_RANK.get(normalize_type(n.get("type")), 9), _nm(n), n))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    out = []
    for score, _, _, n in scored[:limit]:
        d = brief(n)
        d["score"] = score
        out.append(d)
    return out


def resolve(idx: Index, ref: str) -> Optional[str]:
    if ref in idx.nodes:
        return ref
    if ref in idx.by_file:
        files = [i for i in idx.by_file[ref] if normalize_type(idx.nodes[i].get("type")) in ("file", "config", "script", "document")]
        if files:
            return files[0]
    names = idx.by_name.get(ref, [])
    if len(names) == 1:
        return names[0]
    return None


def symbol(idx: Index, name: str) -> List[dict]:
    ids = idx.by_name.get(name) or [i for nm, v in idx.by_name.items() if nm.lower() == name.lower() for i in v]
    res = []
    for i in ids:
        n = idx.nodes[i]
        d = brief(n)
        d["calls"] = sorted({idx.nodes[e["target"]].get("name", e["target"]) if e["target"] in idx.nodes else e["target"]
                             for e in idx.out[i] if e.get("type") == "calls"})
        d["called_by"] = sorted({_nm(idx.nodes[e["source"]]) if e["source"] in idx.nodes else e["source"]
                                 for e in idx.inc[i] if e.get("type") == "calls"})
        res.append(d)
    res.sort(key=lambda d: (_TYPE_RANK.get(d["type"], 9), d["file"]))
    return res


def neighbors(idx: Index, start: str, depth: int = 1, limit: int = 200) -> List[dict]:
    depth = max(1, min(int(depth), 4))
    seen = {start: 0}
    q = deque([start])
    found: List[dict] = []
    while q and len(found) < limit:
        cur = q.popleft()
        d = seen[cur]
        if d >= depth:
            continue
        for e, other, direction in (
            [(e, e["target"], "out") for e in idx.out[cur]] + [(e, e["source"], "in") for e in idx.inc[cur]]
        ):
            if other in seen or other not in idx.nodes:
                continue
            seen[other] = d + 1
            q.append(other)
            item = brief(idx.nodes[other])
            item.update({"depth": d + 1, "via": e.get("type"), "direction": direction})
            found.append(item)
            if len(found) >= limit:
                break
    return found


def impact(idx: Index, path: str) -> dict:
    own = set(idx.by_file.get(path, []))
    for i in list(own):  # include nodes contained by this file's nodes
        for e in idx.out[i]:
            if e.get("type") == "contains":
                own.add(e["target"])
    dependents: Dict[str, dict] = {}
    for i in own:
        for e in idx.inc[i]:
            et = e.get("type")
            src = e.get("source")
            if et == "contains" or src in own or src not in idx.nodes:
                continue
            d = dependents.setdefault(src, {**brief(idx.nodes[src]), "via": set()})
            d["via"].add(et)
    deps = []
    for d in dependents.values():
        d["via"] = sorted(d["via"])
        deps.append(d)
    deps.sort(key=lambda d: (d["file"], d["name"]))
    return {"path": path, "nodes": [brief(idx.nodes[i]) for i in sorted(own)], "dependents": deps}
