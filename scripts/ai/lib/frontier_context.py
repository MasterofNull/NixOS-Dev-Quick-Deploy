#!/usr/bin/env python3
"""On-demand frontier context provider (FA-2, pull model).

Instead of a timer that scans on an arbitrary clock, agents PULL frontier context at
the moment they need it — creating a PRD, drafting a plan, reviewing a change,
authoring a slice. Given a topic, this returns: the relevant concepts, the verified
techniques we've already assessed (with OUR verdicts/corrections), what we already
have in the codebase (vector-DB matches), and a freshness signal — so if our
knowledge on that topic is stale or missing, the caller triggers a targeted refresh
NOW, only for that topic. Fresh at the point of use, never polled blindly.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import frontier_relevance as fr


def _parse_iso(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


def _is_stale(newest_iso: str | None, now: float, stale_days: int) -> bool:
    """No candidate at all -> stale (a gap); or the newest is older than the window."""
    ts = _parse_iso(newest_iso)
    if ts is None:
        return True
    return (now - ts) > stale_days * 86400


def context_for_topic(topic: str, concepts_catalog: dict[str, Any], backlog: list[dict[str, Any]], *,
                      stale_days: int = 30, now: float | None = None) -> dict[str, Any]:
    """Compose the frontier context an agent should fold into its PRD/plan/review."""
    now = time.time() if now is None else now
    score = fr.score_text(concepts_catalog, topic)
    by_id = {c["id"]: c for c in concepts_catalog.get("concepts") or []}

    per_concept: list[dict[str, Any]] = []
    for m in score["matched_concepts"]:
        cid = m["concept"]
        kws = by_id.get(cid, {}).get("keywords") or []
        cands = [b for b in backlog
                 if fr._hits(kws, f"{b.get('technique','')} {b.get('claim','')} {b.get('aqos_mapping','')}")]
        dates = [b.get("discovered_at") for b in cands if b.get("discovered_at")]
        newest = max(dates) if dates else None
        per_concept.append({
            "concept": cid, "tier": m["tier"],
            "candidates": [{"id": b.get("id"), "verdict": b.get("verdict"),
                            "status": b.get("status"), "claim": b.get("claim"),
                            "proposed_slice": b.get("proposed_slice")} for b in cands],
            "newest": newest, "stale": _is_stale(newest, now, stale_days),
        })

    stale = sorted({p["concept"] for p in per_concept if p["stale"]})
    return {
        "topic": topic,
        "relevance": score["relevance"],
        "core_matched": score["core_matched"],
        "relevant_concepts": [m["concept"] for m in score["matched_concepts"]],
        "per_concept": per_concept,
        "stale_concepts": stale,
        "refresh_recommended": bool(stale),
        # The lazy, need-driven refresh: a targeted scan for THIS topic only, routed
        # to a web-capable lane on demand — not a blanket timer.
        "refresh_cmd": (f"aq-frontier scan-topic {topic!r}" if stale else None),
    }


def render(ctx: dict[str, Any]) -> str:
    """Compact block a PRD/plan/review folds in verbatim."""
    lines = [f"Frontier context — topic: {ctx['topic']!r} (relevance={ctx['relevance']}, "
             f"core={'yes' if ctx['core_matched'] else 'no'})"]
    if not ctx["relevant_concepts"]:
        lines.append("  (no matched concepts — topic outside the tracked taxonomy)")
        return "\n".join(lines)
    for p in ctx["per_concept"]:
        flag = "  STALE/GAP" if p["stale"] else ""
        lines.append(f"  [{p['tier']}] {p['concept']}{flag}")
        for c in p["candidates"]:
            lines.append(f"     - {c['id']} ({c['verdict']}/{c['status']}): {c['claim']}")
        if not p["candidates"]:
            lines.append("     - (no assessed candidate yet)")
    if ctx["refresh_recommended"]:
        lines.append(f"  REFRESH: knowledge on {ctx['stale_concepts']} is stale/missing -> {ctx['refresh_cmd']}")
    return "\n".join(lines)
