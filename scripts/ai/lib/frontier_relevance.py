#!/usr/bin/env python3
"""Frontier relevance scoring + concept coverage (FA-1c).

Answers "how do we find the highest-value, most-relevant research for OUR system,
and how do we cover all relevant subjects without losing focus on the core?"

Two mechanisms, hybrid by design (mirrors our hybrid_search: semantic + keyword):
  - KEYWORD (this module, deterministic + offline): score a paper/tool's text
    against the concept taxonomy (concepts.yaml). Core concepts weigh more, so
    highest-value-to-us research ranks first — focus on the core.
  - SEMANTIC (optional, at scan time): the taxonomy's `subsystems` anchor a vector-DB
    corpus (Qdrant/AIDB via the hybrid-coordinator); `semantic_score` calls
    hybrid_search to blend embedding similarity to what we actually build. Fail-safe:
    if the coordinator is down, keyword scoring still works.

COVERAGE turns the SAME taxonomy into a breadth guarantee: every concept is a subject
we must track; a concept with no source and no candidate is a blind spot.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_CONCEPTS = ".agents/plans/frontier-evidence-intake/concepts.yaml"


def load_concepts(path: str | os.PathLike = DEFAULT_CONCEPTS) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML required to read the concept taxonomy") from exc
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("concept taxonomy must be a mapping")
    return data


def validate(catalog: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    weights = catalog.get("weights") or {}
    seen: set[str] = set()
    for c in catalog.get("concepts") or []:
        cid = c.get("id")
        if not cid:
            issues.append("concept missing id")
        if cid in seen:
            issues.append(f"duplicate concept id: {cid}")
        seen.add(cid)
        if c.get("tier") not in weights:
            issues.append(f"concept {cid}: tier '{c.get('tier')}' has no weight")
        if not c.get("keywords"):
            issues.append(f"concept {cid}: no keywords")
    return issues


def _weight(catalog: dict[str, Any], tier: str) -> int:
    return int((catalog.get("weights") or {}).get(tier, 0))


def _norm(s: str) -> str:
    """Lowercase + treat hyphen/whitespace runs as one space, so 'kv-cache' and
    'long-context' (how papers write them) match 'kv cache' / 'long context' keywords."""
    return re.sub(r"[\s\-]+", " ", s.lower()).strip()


def _hits(keywords: list[str], text_lower: str) -> int:
    """Distinct keywords matched as whole words/phrases (avoids nix->nixon)."""
    tl = _norm(text_lower)
    n = 0
    for kw in keywords:
        if re.search(r"\b" + re.escape(_norm(str(kw))) + r"\b", tl):
            n += 1
    return n


def score_text(catalog: dict[str, Any], text: str) -> dict[str, Any]:
    """Keyword relevance of a paper/tool text against the concept taxonomy."""
    tl = (text or "").lower()
    matched = []
    for c in catalog.get("concepts") or []:
        h = _hits(c.get("keywords") or [], tl)
        if h:
            w = _weight(catalog, c.get("tier", ""))
            matched.append({"concept": c["id"], "tier": c.get("tier"), "hits": h, "weighted": h * w})
    matched.sort(key=lambda m: (-m["weighted"], -m["hits"], m["concept"]))
    relevance = sum(m["weighted"] for m in matched)
    core_matched = any(m["tier"] == "core" for m in matched)
    return {"relevance": relevance, "core_matched": core_matched,
            "matched_concepts": matched, "top_concept": matched[0]["concept"] if matched else None}


def _concept_text(concept: dict[str, Any]) -> str:
    return " ".join(str(concept.get(k, "")) for k in ("id", "why")).lower()


def concept_coverage(catalog: dict[str, Any], sources: list[dict[str, Any]],
                     backlog: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-concept breadth: how many sources track it + candidates found. Gaps = a
    core/supporting concept with no source or no candidate (a subject we're blind to)."""
    rows = []
    gaps = []
    for c in catalog.get("concepts") or []:
        kws = c.get("keywords") or []
        src_hits = sum(1 for s in sources
                       if _hits(kws, f"{s.get('name','')} {s.get('why','')} {s.get('pillar','')}".lower()))
        cand_hits = sum(1 for b in backlog
                        if _hits(kws, f"{b.get('technique','')} {b.get('claim','')} {b.get('aqos_mapping','')}".lower()))
        tier = c.get("tier")
        is_gap = tier in ("core", "supporting") and (src_hits == 0 or cand_hits == 0)
        row = {"concept": c["id"], "tier": tier, "sources_tracking": src_hits, "candidates_found": cand_hits, "gap": is_gap}
        rows.append(row)
        if is_gap:
            gaps.append(c["id"])
    rows.sort(key=lambda r: ({"core": 0, "supporting": 1, "peripheral": 2}.get(r["tier"], 3), r["concept"]))
    return {"concepts": rows, "gaps": gaps, "gap_count": len(gaps)}


def _hybrid_key() -> str:
    """Read the coordinator API key from HYBRID_API_KEY_FILE (a path) or HYBRID_API_KEY."""
    path = os.environ.get("HYBRID_API_KEY_FILE")
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return os.environ.get("HYBRID_API_KEY", "").strip()


def semantic_score(text: str, *, coordinator_url: str | None = None, limit: int = 5) -> dict[str, Any] | None:
    """Optional vector-DB enrichment via the hybrid-coordinator (Qdrant/AIDB).

    POSTs to the coordinator's /query hybrid (semantic + keyword) search and returns
    the top corpus matches — what in OUR system this text is most similar to — so the
    scan can blend embedding similarity to what we actually build. Fail-safe: any
    error (coordinator down, no key) returns None; keyword scoring never depends on it.
    Contract matches ai-stack/local-orchestrator/mcp_client.py (POST /query, X-API-Key)."""
    base = coordinator_url or os.environ.get("HYBRID_COORDINATOR_URL", "http://127.0.0.1:8003")
    headers = {"Content-Type": "application/json"}
    key = _hybrid_key()
    if key:
        headers["X-API-Key"] = key
    payload = {"query": text, "mode": "auto", "prefer_local": True, "limit": limit,
               "generate_response": False}
    try:
        req = urllib.request.Request(
            f"{base.rstrip('/')}/query", data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Response shape (ai-stack coordinator): results is a dict with
        # combined_results (hybrid-ranked) + semantic_results + keyword_results.
        res = data.get("results", {}) if isinstance(data, dict) else {}
        combined = (res.get("combined_results")
                    or (res.get("semantic_results") or []) + (res.get("keyword_results") or []))
        matches = [{"source": (x.get("payload") or {}).get("title") or x.get("collection") or x.get("source"),
                    "score": x.get("score")} for x in combined[:limit]]
        return {"matches": matches, "count": len(combined), "route": data.get("route")}
    except Exception:
        return None
