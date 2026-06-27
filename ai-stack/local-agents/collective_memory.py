"""
Collective Memory — Phase 18: Agent Mesh

Provides shared state for multi-agent teams via Redis pub/sub blackboard,
and archives completed collaboration records to AIDB for cross-session retrieval.

Blackboard: ephemeral Redis hash (TTL=3600s, key: agent-mesh:<team_id>)
Archive: permanent AIDB documents (project: agent-collaborations)

Usage:
    mem = CollectiveMemory()
    mem.blackboard_set(team_id, "planner_output", "phases: [...]")
    mem.blackboard_broadcast(team_id, json.dumps({"role": "planner", "status": "done"}))
    await mem.archive_collaboration(team_id, {
        "task_summary": "refactor auth",
        "roles": ["planner", "coder", "reviewer"],
        "outcome": "success",
        "duration_s": 42.0,
        "patterns": ["read existing tests first", "verify with py_compile"],
    })
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agent-mesh")

# ---------------------------------------------------------------------------
# Config from env (fallback chain: mesh-specific → generic)
# ---------------------------------------------------------------------------

def _redis_url() -> str:
    return (
        os.environ.get("AGENT_MESH_REDIS_URL")
        or os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
    )

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
    env_key = os.environ.get("AIDB_API_KEY", "")
    if env_key:
        return env_key
    # Fallback to SOPS secret path (readable by hyperd in dev sessions)
    try:
        return open("/run/secrets/aidb_api_key").read().strip()
    except OSError:
        return ""

_BLACKBOARD_TTL: int = int(os.environ.get("AGENT_MESH_BLACKBOARD_TTL", "3600"))


# ---------------------------------------------------------------------------
# CollectiveMemory
# ---------------------------------------------------------------------------

class CollectiveMemory:
    """Shared state for multi-agent teams.

    Redis blackboard is ephemeral (TTL-based).
    AIDB archive is permanent and searchable.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        aidb_url: Optional[str] = None,
        aidb_api_key: Optional[str] = None,
    ) -> None:
        self._redis_url = redis_url or _redis_url()
        self._aidb_url = aidb_url or _aidb_url()
        self._aidb_key = aidb_api_key or _aidb_key()
        self._redis: Optional[Any] = None

    # ── Redis helpers ──────────────────────────────────────────────────────

    def _get_redis(self) -> Any:
        if self._redis is None:
            import redis as _redis_lib  # lazy import
            self._redis = _redis_lib.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _mesh_key(self, team_id: str) -> str:
        return f"agent-mesh:{team_id}"

    # ── Blackboard operations ──────────────────────────────────────────────

    def blackboard_set(self, team_id: str, key: str, value: str) -> None:
        """Store a key-value pair in the team's ephemeral blackboard."""
        try:
            r = self._get_redis()
            r.hset(self._mesh_key(team_id), key, value)
            r.expire(self._mesh_key(team_id), _BLACKBOARD_TTL)
            logger.debug("blackboard_set team=%s key=%s", team_id, key)
        except Exception as exc:
            logger.warning("blackboard_set failed (non-fatal): %s", exc)

    def blackboard_get(self, team_id: str, key: str) -> Optional[str]:
        """Retrieve a value from the team's blackboard. Returns None if missing."""
        try:
            r = self._get_redis()
            return r.hget(self._mesh_key(team_id), key)
        except Exception as exc:
            logger.warning("blackboard_get failed (non-fatal): %s", exc)
            return None

    def blackboard_getall(self, team_id: str) -> Dict[str, str]:
        """Retrieve all key-value pairs from the team's blackboard."""
        try:
            r = self._get_redis()
            return r.hgetall(self._mesh_key(team_id)) or {}
        except Exception as exc:
            logger.warning("blackboard_getall failed (non-fatal): %s", exc)
            return {}

    def blackboard_broadcast(self, team_id: str, message: str) -> None:
        """Publish a message to the team's pub/sub channel."""
        try:
            r = self._get_redis()
            r.publish(self._mesh_key(team_id), message)
            logger.debug("blackboard_broadcast team=%s len=%d", team_id, len(message))
        except Exception as exc:
            logger.warning("blackboard_broadcast failed (non-fatal): %s", exc)

    # ── AIDB archive ───────────────────────────────────────────────────────

    async def archive_collaboration(
        self, team_id: str, metadata: Dict[str, Any]
    ) -> bool:
        """Write a completed collaboration record to AIDB.

        metadata must include:
          task_summary (str), roles (list[str]), outcome (str),
          duration_s (float), patterns (list[str])

        Returns True on success, False on failure (non-fatal).
        """
        required = {"task_summary", "roles", "outcome", "duration_s", "patterns"}
        missing = required - set(metadata.keys())
        if missing:
            logger.warning("archive_collaboration missing fields: %s", missing)

        roles_str = ", ".join(metadata.get("roles", []))
        patterns_str = " | ".join(metadata.get("patterns", []))
        content = (
            f"{metadata.get('task_summary', '')} | "
            f"roles: {roles_str} | "
            f"outcome: {metadata.get('outcome', '')} | "
            f"patterns: {patterns_str}"
        )

        payload = {
            "content": content,
            "project": "agent-collaborations",
            "title": f"collab-{team_id}",
            "relative_path": f"collaborations/{team_id}.json",
            "source_trust_level": "generated",
        }

        headers = {"Content-Type": "application/json"}
        if self._aidb_key:
            headers["X-API-Key"] = self._aidb_key

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._aidb_url}/documents",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code not in (200, 201):
                    logger.warning(
                        "archive_collaboration AIDB %d: %s",
                        resp.status_code, resp.text[:200],
                    )
                    return False
                doc_id = None
                try:
                    doc_id = resp.json().get("id") or resp.json().get("document_id")
                except Exception:
                    pass
                if doc_id:
                    # Vector-index the document so it's searchable via recall_agent_memory.
                    idx_resp = await client.post(
                        f"{self._aidb_url}/vector/index",
                        json={"items": [{"document_id": doc_id}], "collection": "skills-patterns"},
                        headers=headers,
                    )
                    if idx_resp.status_code not in (200, 201, 202):
                        logger.warning(
                            "archive_collaboration vector index %d: %s",
                            idx_resp.status_code, idx_resp.text[:200],
                        )
                logger.info("Archived collaboration team=%s to AIDB (doc_id=%s)", team_id, doc_id)
                return True
        except Exception as exc:
            logger.warning("archive_collaboration failed (non-fatal): %s", exc)
            return False

    # ── Active teams ───────────────────────────────────────────────────────

    def get_active_teams(self) -> List[str]:
        """Return list of team_ids with active blackboard keys in Redis."""
        try:
            r = self._get_redis()
            keys = r.keys("agent-mesh:*")
            return [k.replace("agent-mesh:", "") for k in keys]
        except Exception as exc:
            logger.warning("get_active_teams failed (non-fatal): %s", exc)
            return []

    def is_redis_connected(self) -> bool:
        """Probe Redis connectivity."""
        try:
            self._get_redis().ping()
            return True
        except Exception:
            return False
