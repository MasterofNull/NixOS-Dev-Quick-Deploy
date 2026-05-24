"""
workflow/consensus_engine.py — Phase 70.1: Reputation-Weighted Consensus Engine.

Replaces simple majority voting with reputation-weighted voting for high-risk
workflow decisions. Agent reputation is derived from the agent_registry evaluation
data (runtime success rate × lesson count × average runtime score).

Routes registered by register_routes(app):
  POST /workflow/consensus/vote    — submit a vote for a session
  GET  /workflow/consensus/status/{session_id}  — current tally + outcome

Vote lifecycle:
  - Votes accumulate until quorum (≥2 non-abstain agents) or explicit resolve
  - Weighted score: reputation_weight × confidence
  - Winner: YES if weighted_yes > weighted_no; NO if weighted_no > weighted_yes
  - Tie-break: orchestrator veto → outcome = "no" (pessimistic-safe)
  - Abstain votes are recorded but do not count toward quorum or outcome

Session state is in-process memory only (keyed by session_id). Sessions expire
after CONSENSUS_SESSION_TTL_S (default 3600s).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

CONSENSUS_SESSION_TTL_S = 3600  # sessions expire after 1 hour
CONSENSUS_QUORUM = 2             # minimum non-abstain votes before outcome is final


# ---------------------------------------------------------------------------
# In-process session store
# ---------------------------------------------------------------------------

_sessions: Dict[str, Dict[str, Any]] = {}
_sessions_lock = asyncio.Lock()


def _now() -> float:
    return time.time()


async def _gc_sessions() -> None:
    """Remove sessions older than TTL."""
    cutoff = _now() - CONSENSUS_SESSION_TTL_S
    async with _sessions_lock:
        stale = [sid for sid, s in _sessions.items() if s["created_at"] < cutoff]
        for sid in stale:
            del _sessions[sid]


# ---------------------------------------------------------------------------
# Reputation scoring
# ---------------------------------------------------------------------------

async def _agent_reputation(agent_id: str) -> float:
    """Return [0.0, 1.0] reputation weight for agent_id.

    Derived from agent_registry evaluation row:
      base_score = successful_runtime_events / max(runtime_events, 1)
      promoted_lessons = count of 'promoted' lessons for this agent
      lesson_bonus = min(0.2, promoted_lessons * 0.02)
      score = base_score * (1 + lesson_bonus) * average_runtime_score_normalised

    Falls back to 0.5 (neutral weight) if registry unavailable.
    """
    try:
        from workflow.agent_registry import _load_agent_evaluations_registry  # type: ignore[import]
        evals = await _load_agent_evaluations_registry()
        agents = evals.get("agents", {})
        row = agents.get(agent_id) or agents.get(agent_id.lower(), {})

        runtime_events    = int(row.get("runtime_events", 0) or 0)
        successful_events = int(row.get("successful_runtime_events", 0) or 0)
        avg_score         = float(row.get("average_runtime_score", 0.5) or 0.5)

        base_score = successful_events / max(runtime_events, 1)

        # Lesson bonus: count promoted lessons attributed to this agent
        from workflow.agent_registry import _load_agent_lessons_registry  # type: ignore[import]
        lessons_reg = await _load_agent_lessons_registry()
        promoted = sum(
            1 for e in lessons_reg.get("entries", [])
            if str(e.get("agent", "")).lower() == agent_id.lower()
            and str(e.get("state", "")).lower() == "promoted"
        )
        lesson_bonus = min(0.20, promoted * 0.02)

        # Normalise avg_score (stored 0.0-1.0 or 0.0-10.0)
        if avg_score > 1.0:
            avg_score = min(avg_score / 10.0, 1.0)

        score = base_score * (1.0 + lesson_bonus) * max(avg_score, 0.1)
        return min(1.0, max(0.1, round(score, 4)))  # clamp [0.1, 1.0]

    except Exception as exc:
        logger.debug("consensus: reputation lookup failed for %s: %s — using 0.5", agent_id, exc)
        return 0.5


def _compute_outcome(votes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute weighted outcome from vote list.

    Returns:
        outcome: "yes" | "no" | "tie_veto" | "pending"
        weighted_yes, weighted_no, quorum_met, vote_count
    """
    non_abstain = [v for v in votes if v["vote"] != "abstain"]
    quorum_met  = len(non_abstain) >= CONSENSUS_QUORUM

    weighted_yes = sum(v["weight"] * v["confidence"] for v in non_abstain if v["vote"] == "yes")
    weighted_no  = sum(v["weight"] * v["confidence"] for v in non_abstain if v["vote"] == "no")

    if not quorum_met:
        outcome = "pending"
    elif weighted_yes > weighted_no:
        outcome = "yes"
    elif weighted_no > weighted_yes:
        outcome = "no"
    else:
        outcome = "tie_veto"  # tie-break = orchestrator veto (pessimistic-safe → reject)

    return {
        "outcome": outcome,
        "quorum_met": quorum_met,
        "weighted_yes": round(weighted_yes, 4),
        "weighted_no": round(weighted_no, 4),
        "vote_count": len(votes),
        "non_abstain_count": len(non_abstain),
    }


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def _handle_vote_post(request: web.Request) -> web.Response:
    """POST /workflow/consensus/vote

    Body (JSON):
        session_id  str   — identifies the decision being voted on
        agent_id    str   — voting agent identity
        vote        str   — "yes" | "no" | "abstain"
        confidence  float — [0.0, 1.0] agent's self-reported confidence (default 1.0)
        topic       str?  — optional human-readable decision label

    Response: current session tally + outcome.
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    session_id = str(body.get("session_id") or "").strip()
    agent_id   = str(body.get("agent_id") or "").strip()
    vote_val   = str(body.get("vote") or "").strip().lower()
    confidence = float(body.get("confidence", 1.0) or 1.0)
    topic      = str(body.get("topic") or "").strip()

    if not session_id:
        return web.json_response({"error": "session_id required"}, status=400)
    if not agent_id:
        return web.json_response({"error": "agent_id required"}, status=400)
    if vote_val not in ("yes", "no", "abstain"):
        return web.json_response({"error": "vote must be 'yes', 'no', or 'abstain'"}, status=400)
    confidence = max(0.0, min(1.0, confidence))

    # Look up reputation (non-blocking — default 0.5 on failure)
    reputation = await _agent_reputation(agent_id)

    vote_record = {
        "agent_id":   agent_id,
        "vote":       vote_val,
        "confidence": confidence,
        "weight":     reputation,
        "timestamp":  _now(),
    }

    await _gc_sessions()

    async with _sessions_lock:
        if session_id not in _sessions:
            _sessions[session_id] = {
                "session_id": session_id,
                "topic":      topic or session_id,
                "votes":      [],
                "created_at": _now(),
            }
        session = _sessions[session_id]
        # Replace existing vote from same agent
        session["votes"] = [v for v in session["votes"] if v["agent_id"] != agent_id]
        session["votes"].append(vote_record)
        if topic and not session.get("topic"):
            session["topic"] = topic
        tally = _compute_outcome(session["votes"])

    logger.info(
        "consensus: session=%s agent=%s vote=%s confidence=%.2f weight=%.4f → outcome=%s",
        session_id, agent_id, vote_val, confidence, reputation, tally["outcome"],
    )

    return web.json_response({
        "session_id": session_id,
        "topic":      session["topic"],
        "vote_recorded": vote_record,
        **tally,
    })


async def _handle_status_get(request: web.Request) -> web.Response:
    """GET /workflow/consensus/status/{session_id}"""
    session_id = request.match_info.get("session_id", "").strip()
    if not session_id:
        return web.json_response({"error": "session_id required"}, status=400)

    await _gc_sessions()

    async with _sessions_lock:
        session = _sessions.get(session_id)

    if session is None:
        return web.json_response({"error": "session not found", "session_id": session_id}, status=404)

    tally = _compute_outcome(session["votes"])
    return web.json_response({
        "session_id": session_id,
        "topic":      session["topic"],
        "votes": [
            {k: v for k, v in vote.items() if k != "timestamp"}
            for vote in session["votes"]
        ],
        **tally,
    })


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(app: web.Application) -> None:
    """Phase 70.1: Register consensus engine routes."""
    app.router.add_post("/workflow/consensus/vote", _handle_vote_post)
    app.router.add_get("/workflow/consensus/status/{session_id}", _handle_status_get)
    logger.info("consensus_engine: routes registered")
