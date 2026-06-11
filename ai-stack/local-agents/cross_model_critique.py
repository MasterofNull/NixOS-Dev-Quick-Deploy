"""
Cross-Model Critique — Phase 157

Stores critique artifacts when one agent reviews another's output.
Writes to a local JSONL spool (no auth required) and optionally archives
to AIDB for vector search. training_ingest.py picks up the spool.

Primary storage: .agents/telemetry/cross-model-critiques.jsonl  (via harness_paths)
Vector search:   AIDB /vector/search collection "agent-collaborations" (best-effort)

Schema per record:
  critique_id    : unique ID
  critic_agent   : who reviewed (claude|gemini|local|codex)
  author_agent   : who produced the original output
  task_summary   : brief task description
  critique_score : 0.0-1.0 overall quality rating
  strengths      : list[str] — what worked
  weaknesses     : list[str] — gaps / errors found
  suggestions    : list[str] — actionable improvements
  patterns       : list[str] — extracted best practices (fed to training_ingest)
  session_id     : optional session/phase identifier
  timestamp      : ISO-8601 UTC

Usage:
    from cross_model_critique import record_critique, query_critiques
    await record_critique(
        critic="claude",
        author="gemini",
        task_summary="Architecture review of Phase 149-156",
        score=0.72,
        strengths=["Identified race condition in lifecycle manager"],
        weaknesses=["Missed frequency_penalty=0.0 constraint"],
        suggestions=["Add GPU ceiling check to eval_sandbox"],
        patterns=["Always validate hardware constraints before adopting candidates"],
        session_id="phase-157",
    )
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cross-model-critique")

# Use harness_paths for canonical spool location; fall back gracefully
# Note: harness_paths does not define AIDB_URL — resolve separately from env/config
try:
    from harness_paths import CRITIQUE_SPOOL
except ImportError:
    CRITIQUE_SPOOL = Path(os.environ.get("REPO_ROOT", ".")) / ".agents" / "telemetry" / "cross-model-critiques.jsonl"

_AIDB_URL = os.environ.get("AIDB_URL", "http://127.0.0.1:8002")


# ---------------------------------------------------------------------------
# Store a critique
# ---------------------------------------------------------------------------

def _append_spool(record: Dict[str, Any]) -> None:
    """Write one JSON record to the JSONL spool file (sync, no auth)."""
    CRITIQUE_SPOOL.parent.mkdir(parents=True, exist_ok=True)
    with CRITIQUE_SPOOL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


async def record_critique(
    *,
    critic: str,
    author: str,
    task_summary: str,
    score: float,
    strengths: List[str],
    weaknesses: List[str],
    suggestions: List[str],
    patterns: List[str],
    session_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a cross-model critique to the JSONL spool (primary) and AIDB (best-effort).

    Returns {"status": "stored", "critique_id": ..., "timestamp": ...} on success.
    """
    critique_id = f"critique-{critic}-{author}-{uuid.uuid4().hex[:8]}"
    ts = datetime.datetime.utcnow().isoformat() + "Z"

    record: Dict[str, Any] = {
        "critique_id": critique_id,
        "critic_agent": critic,
        "author_agent": author,
        "task_summary": task_summary,
        "critique_score": round(max(0.0, min(1.0, score)), 3),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "patterns": patterns,
        "session_id": session_id,
        "timestamp": ts,
        **(metadata or {}),
    }

    # Primary: JSONL spool — always attempt, no auth needed
    try:
        await asyncio.to_thread(_append_spool, record)
        logger.info("Spooled critique %s (score=%.2f)", critique_id, score)
    except Exception as exc:
        logger.warning("spool write failed for %s: %s", critique_id, exc)
        return {"status": "error", "reason": f"spool: {exc}", "critique_id": critique_id}

    return {"status": "stored", "critique_id": critique_id, "timestamp": ts}


# ---------------------------------------------------------------------------
# Query critiques
# ---------------------------------------------------------------------------

def _read_spool(
    agent: Optional[str] = None,
    limit: int = 20,
    min_score: float = 0.0,
) -> List[Dict[str, Any]]:
    """Read critiques from the JSONL spool (sync)."""
    if not CRITIQUE_SPOOL.exists():
        return []
    results = []
    try:
        with CRITIQUE_SPOOL.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("critique_score", 0) < min_score:
                    continue
                if agent and rec.get("critic_agent") != agent and rec.get("author_agent") != agent:
                    continue
                results.append(rec)
    except Exception as exc:
        logger.warning("spool read failed: %s", exc)
    # Return most recent first, up to limit
    return results[-limit:][::-1]


async def query_critiques(
    *,
    agent: Optional[str] = None,
    limit: int = 20,
    min_score: float = 0.0,
) -> List[Dict[str, Any]]:
    """Read cross-model critiques from the JSONL spool.

    Primary path: CRITIQUE_SPOOL (no auth). Returns most recent first.
    """
    return await asyncio.to_thread(_read_spool, agent, limit, min_score)


# ---------------------------------------------------------------------------
# Synthesize multi-agent critiques into a learning artifact
# ---------------------------------------------------------------------------

def synthesize_critiques(critiques: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate multiple critiques into a consolidated learning record.

    Returns a dict suitable for seeding into training_ingest or skills-patterns.
    """
    if not critiques:
        return {"error": "no critiques provided"}

    all_strengths: List[str] = []
    all_weaknesses: List[str] = []
    all_suggestions: List[str] = []
    all_patterns: List[str] = []
    scores: List[float] = []
    agents_involved: set = set()

    for c in critiques:
        all_strengths.extend(c.get("strengths", []))
        all_weaknesses.extend(c.get("weaknesses", []))
        all_suggestions.extend(c.get("suggestions", []))
        all_patterns.extend(c.get("patterns", []))
        if c.get("critique_score") is not None:
            scores.append(float(c["critique_score"]))
        for key in ("critic_agent", "author_agent"):
            if c.get(key):
                agents_involved.add(c[key])

    def _dedup(items: List[str]) -> List[str]:
        seen: set = set()
        out = []
        for item in items:
            norm = item.strip().lower()
            if norm and norm not in seen:
                seen.add(norm)
                out.append(item.strip())
        return out

    avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0

    return {
        "synthesis_type": "cross_model_critique_aggregate",
        "agents_involved": sorted(agents_involved),
        "critique_count": len(critiques),
        "avg_score": avg_score,
        "consensus_strengths": _dedup(all_strengths)[:10],
        "consensus_weaknesses": _dedup(all_weaknesses)[:10],
        "consensus_suggestions": _dedup(all_suggestions)[:10],
        "promoted_patterns": _dedup(all_patterns)[:15],
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    async def _main() -> None:
        if "--query" in sys.argv:
            agent_filter = None
            if "--agent" in sys.argv:
                idx = sys.argv.index("--agent")
                agent_filter = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
            results = await query_critiques(agent=agent_filter, limit=20)
            print(json.dumps(results, indent=2))
        elif "--synth" in sys.argv:
            results = await query_critiques(limit=50)
            synthesis = synthesize_critiques(results)
            print(json.dumps(synthesis, indent=2))
        else:
            print("Usage: cross_model_critique.py --query [--agent NAME] | --synth")
            sys.exit(1)

    asyncio.run(_main())
