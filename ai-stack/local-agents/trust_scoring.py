#!/usr/bin/env python3
"""Phase 150 Slice 6: deterministic trust/relevance scoring for improvement candidates."""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Source trust baselines — higher = more trusted origin
_SOURCE_TRUST: dict[str, float] = {
    "issues-backlog": 0.90,    # human-logged, high signal
    "delegation-feedback": 0.80,  # live system telemetry
    "health-spider": 0.70,     # automated health signals
    "model-profile": 0.65,     # catalog freshness detection
    "DiscoveryAgent": 0.60,    # deterministic scanner default
    "external": 0.30,          # unverified external source
    "unknown": 0.20,
}

# Category relevance multipliers — how actionable is this category for the factory?
_CATEGORY_RELEVANCE: dict[str, float] = {
    "delegation-quality": 0.95,
    "health": 0.85,
    "health-spider": 0.85,
    "observability": 0.80,
    "security": 0.75,
    "system-fix": 0.75,
    "performance": 0.70,
    "tooling": 0.65,
    "documentation": 0.50,
    "research": 0.40,
}

# Priority → relevance modifier (priority 1 = critical, 4 = low)
_PRIORITY_RELEVANCE: dict[int, float] = {1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4}


_SCORE_REQUIRED_FIELDS: frozenset[str] = frozenset({"id", "category", "title", "source"})


def score_candidate(candidate: dict[str, Any]) -> tuple[float, float]:
    """Return (trust_score, relevance_score) in [0.0, 1.0] for a candidate.

    Deterministic: same inputs always produce same outputs.
    Raises ValueError if required fields (id, category, title, source) are missing.
    """
    missing = _SCORE_REQUIRED_FIELDS - set(candidate.keys())
    if missing:
        raise ValueError(f"score_candidate: missing required fields {missing} in candidate {candidate.get('id', '?')!r}")
    source = str(candidate.get("source") or candidate.get("category") or "unknown")
    category = str(candidate.get("category") or "unknown")
    priority = int(candidate.get("priority") or 3)

    # Trust: match source key prefix
    trust = _SOURCE_TRUST.get("unknown", 0.20)
    for key, val in _SOURCE_TRUST.items():
        if source.startswith(key) or key in source:
            trust = val
            break

    # Relevance: category weight × priority modifier
    cat_weight = _CATEGORY_RELEVANCE.get(category, 0.50)
    pri_mod = _PRIORITY_RELEVANCE.get(priority, 0.50)
    relevance = round(min(1.0, cat_weight * pri_mod * 1.2), 4)
    trust = round(min(1.0, trust), 4)

    return trust, relevance


def apply_scores(candidates: list[dict[str, Any]], *, overwrite: bool = False) -> list[dict[str, Any]]:
    """Apply trust/relevance scores to candidates that lack them (or all if overwrite=True).

    Returns the same list with scores updated in-place.
    """
    skipped = 0
    for candidate in candidates:
        missing_trust = "trust_score" not in candidate or candidate.get("trust_score") == 0.0
        missing_rel = "relevance" not in candidate or candidate.get("relevance") == 0.5
        if overwrite or (missing_trust and missing_rel):
            try:
                trust, relevance = score_candidate(candidate)
            except ValueError as exc:
                skipped += 1
                import logging as _logging
                _logging.getLogger(__name__).warning("apply_scores: skipped invalid candidate — %s", exc)
                continue
            candidate["trust_score"] = trust
            candidate["relevance"] = relevance
    if skipped:
        import logging as _logging
        _logging.getLogger(__name__).warning("apply_scores: %d candidate(s) skipped due to missing required fields", skipped)
    return candidates


def score_candidates_file(candidates_path: Path, *, overwrite: bool = False) -> int:
    """Score all candidates in a candidates.json file. Returns count updated."""
    import json
    if not candidates_path.exists():
        return 0
    data = json.loads(candidates_path.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    before = [(c.get("trust_score"), c.get("relevance")) for c in cands]
    apply_scores(cands, overwrite=overwrite)
    after = [(c.get("trust_score"), c.get("relevance")) for c in cands]
    updated = sum(1 for b, a in zip(before, after) if b != a)
    if updated:
        data["candidates"] = cands
        tmp = candidates_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(candidates_path)
    return updated


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".agents/improvement/candidates.json")
    n = score_candidates_file(path, overwrite="--overwrite" in sys.argv)
    print(f"Updated trust/relevance scores for {n} candidates in {path}")
