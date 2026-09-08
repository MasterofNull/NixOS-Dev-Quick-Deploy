#!/usr/bin/env python3
"""Frontier source catalog + source-quality metrics (FA-1b).

Loads the curated source catalog (sources.yaml) and scores each source by the
backlog it produced, so low-signal sources get pruned and high-signal ones
prioritized — the "assess and refine" tracker the owner asked for.

Coverage tells us if a parity pillar is under-watched; source_signal tells us which
sources actually surface techniques we adopt (adopt-rate), from the backlog's
source_ids links.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DEFAULT_CATALOG = ".agents/plans/frontier-evidence-intake/sources.yaml"
_TRUST = ("primary", "secondary")
_REQUIRED = ("id", "name", "kind", "url", "pillar", "trust_tier", "cadence", "why")


def load_catalog(path: str | os.PathLike = DEFAULT_CATALOG) -> dict[str, Any]:
    """Parse sources.yaml. Requires PyYAML (already used by aq-prompt-eval + gates)."""
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PyYAML required to read the source catalog") from exc
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("source catalog must be a mapping")
    return data


def validate(catalog: dict[str, Any]) -> list[str]:
    """Return a list of issues; empty means valid."""
    issues: list[str] = []
    pillars = set(catalog.get("pillars") or [])
    if not pillars:
        issues.append("catalog declares no pillars")
    sources = catalog.get("sources") or []
    seen: set[str] = set()
    for s in sources:
        if not isinstance(s, dict):
            issues.append("source entry is not a mapping")
            continue
        for k in _REQUIRED:
            if not s.get(k):
                issues.append(f"source {s.get('id', '?')} missing field: {k}")
        sid = s.get("id")
        if sid in seen:
            issues.append(f"duplicate source id: {sid}")
        seen.add(sid)
        if s.get("trust_tier") not in _TRUST:
            issues.append(f"source {sid}: trust_tier must be one of {_TRUST}")
        if pillars and s.get("pillar") not in pillars:
            issues.append(f"source {sid}: pillar '{s.get('pillar')}' not in declared pillars")
    return issues


def coverage(catalog: dict[str, Any]) -> dict[str, Any]:
    """Per-pillar / per-trust / per-cadence counts — is any pillar under-watched?"""
    sources = catalog.get("sources") or []
    by_pillar: dict[str, dict[str, int]] = {}
    by_trust: dict[str, int] = {}
    by_cadence: dict[str, int] = {}
    for s in sources:
        p = s.get("pillar", "?")
        row = by_pillar.setdefault(p, {"total": 0, "primary": 0})
        row["total"] += 1
        if s.get("trust_tier") == "primary":
            row["primary"] += 1
        by_trust[s.get("trust_tier", "?")] = by_trust.get(s.get("trust_tier", "?"), 0) + 1
        by_cadence[s.get("cadence", "?")] = by_cadence.get(s.get("cadence", "?"), 0) + 1
    # A pillar with zero primary sources is a coverage risk.
    at_risk = sorted(p for p, r in by_pillar.items() if r["primary"] == 0)
    return {"total": len(sources), "by_pillar": by_pillar, "by_trust": by_trust,
            "by_cadence": by_cadence, "pillars_without_primary": at_risk}


def source_signal(catalog: dict[str, Any], backlog_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-source adopt-rate from the backlog's source_ids links.

    surfaced = backlog candidates citing this source; adopted = those with verdict
    'adopt'. adopt_rate is the refinement signal: prune sources that surface noise,
    prioritize sources that surface techniques we keep."""
    sources = {s["id"]: s for s in (catalog.get("sources") or []) if s.get("id")}
    stats = {sid: {"source_id": sid, "pillar": s.get("pillar"), "trust_tier": s.get("trust_tier"),
                   "surfaced": 0, "adopted": 0} for sid, s in sources.items()}
    for item in backlog_items:
        for sid in item.get("source_ids") or []:
            if sid not in stats:
                continue
            stats[sid]["surfaced"] += 1
            if item.get("verdict") == "adopt":
                stats[sid]["adopted"] += 1
    out = []
    for row in stats.values():
        row["adopt_rate"] = round(row["adopted"] / row["surfaced"], 3) if row["surfaced"] else None
        out.append(row)
    # Highest signal first; unused sources (surfaced 0) sort last.
    return sorted(out, key=lambda r: (r["surfaced"] == 0, -(r["adopt_rate"] or 0), -r["surfaced"], r["source_id"]))
