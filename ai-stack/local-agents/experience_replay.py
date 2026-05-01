"""
Experience Replay — Phase 18: Agent Mesh

Retrieves past collaboration records from AIDB so new agent teams can
bootstrap from prior experience rather than starting from zero.

Only returns semantically close matches (distance < 0.5) so noise from
unrelated collaborations is filtered out.

Usage:
    replay = ExperienceReplay()
    records = await replay.retrieve("refactor authentication system")
    context_str = replay.format_as_context(records)
    # Prepend context_str to team briefing prompt
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agent-mesh")

# ---------------------------------------------------------------------------
# Config from env (fallback chain: mesh-specific → generic)
# ---------------------------------------------------------------------------

def _aidb_url() -> str:
    return (
        os.environ.get("AGENT_MESH_AIDB_URL")
        or os.environ.get("AIDB_URL", "http://127.0.0.1:8002")
    )

def _aidb_key() -> str:
    key_file = (
        os.environ.get("AGENT_MESH_AIDB_KEY_FILE")
        or os.environ.get("AIDB_API_KEY_FILE", "")
    )
    if key_file:
        try:
            return open(key_file).read().strip()
        except OSError:
            pass
    return os.environ.get("AIDB_API_KEY", "")

_DISTANCE_THRESHOLD: float = float(os.environ.get("AGENT_MESH_DISTANCE_THRESHOLD", "0.5"))


# ---------------------------------------------------------------------------
# ExperienceReplay
# ---------------------------------------------------------------------------

class ExperienceReplay:
    """Retrieves semantically relevant past collaboration records from AIDB.

    Uses /vector/search with project=agent-collaborations. Only records with
    distance < threshold are returned (default 0.5 — close semantic match).
    """

    def __init__(
        self,
        aidb_url: Optional[str] = None,
        aidb_api_key: Optional[str] = None,
        distance_threshold: Optional[float] = None,
    ) -> None:
        self._aidb_url = aidb_url or _aidb_url()
        self._aidb_key = aidb_api_key or _aidb_key()
        self._threshold = distance_threshold if distance_threshold is not None else _DISTANCE_THRESHOLD

    async def retrieve(
        self, task_description: str, top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Search AIDB for past collaborations similar to task_description.

        Returns list of {content, metadata, distance} dicts with distance < threshold.
        Returns empty list on any error (graceful degradation).
        """
        if not task_description.strip():
            return []

        headers = {"Content-Type": "application/json"}
        if self._aidb_key:
            headers["X-API-Key"] = self._aidb_key

        payload = {
            "query": task_description,
            "limit": top_k,
            "project": "agent-collaborations",
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self._aidb_url}/vector/search",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.debug(
                        "experience_replay AIDB %d: %s",
                        resp.status_code, resp.text[:200],
                    )
                    return []

                data = resp.json()
                results = data.get("results", data) if isinstance(data, dict) else data
                if not isinstance(results, list):
                    return []

                filtered = [
                    r for r in results
                    if isinstance(r, dict) and r.get("distance", 1.0) < self._threshold
                ]
                logger.debug(
                    "experience_replay: %d/%d results within threshold %.2f",
                    len(filtered), len(results), self._threshold,
                )
                return filtered

        except Exception as exc:
            logger.debug("experience_replay retrieve failed (non-fatal): %s", exc)
            return []

    def format_as_context(self, records: List[Dict[str, Any]]) -> str:
        """Format retrieved collaboration records as a context string for team prompts.

        Returns empty string if no records (graceful degradation — safe to prepend).
        """
        if not records:
            return ""

        lines = ["=== Past Collaboration Context ==="]
        for i, rec in enumerate(records, 1):
            content = rec.get("content", "")
            # Parse the pipe-delimited content written by CollectiveMemory.archive_collaboration
            parts: Dict[str, str] = {}
            for part in content.split(" | "):
                if ": " in part:
                    k, _, v = part.partition(": ")
                    parts[k.strip()] = v.strip()

            task_summary = parts.get("task_summary", content[:80])
            roles = parts.get("roles", "unknown")
            outcome = parts.get("outcome", "unknown")
            patterns = parts.get("patterns", "")

            lines.append(f"[{i}] Task: {task_summary} | Roles: {roles} | Outcome: {outcome}")
            if patterns:
                lines.append(f"    Patterns that worked: {patterns}")

        lines.append("")  # trailing newline separator
        return "\n".join(lines)
