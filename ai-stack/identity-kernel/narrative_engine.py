"""
Narrative Engine — Phase 16.1

Append-only JSONL journal for the identity kernel.  Records typed events and
can reconstruct a structured summary of capabilities, relationships, and
operational history for the GET /identity/self endpoint.

Journal path: IDENTITY_JOURNAL_PATH env var (default /var/lib/ai-stack/identity/journal.jsonl)
Event types  : boot, capability_registered, user_interaction, agent_collaboration,
               self_improvement, error_pattern, value_update
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("identity-kernel")

_EVENT_TYPES = {
    "boot",
    "capability_registered",
    "user_interaction",
    "agent_collaboration",
    "self_improvement",
    "error_pattern",
    "value_update",
}

_HISTORY_TAIL_SIZE = 20   # events kept in generate_summary history_tail
_SUMMARY_MAX_CAPS  = 50   # max capability names in summary


class NarrativeEngine:
    """
    Lightweight append-only journal.  All I/O is synchronous; callers that
    need async must offload to a thread or use asyncio.to_thread().
    """

    def __init__(self, journal_path: Optional[str] = None) -> None:
        raw = journal_path or os.environ.get(
            "IDENTITY_JOURNAL_PATH",
            "/var/lib/ai-stack/identity/journal.jsonl",
        )
        self.journal_path = Path(raw)
        self._ensure_dir()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        try:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("narrative_engine: cannot create journal dir: %s", exc)

    def _now(self) -> Dict[str, Any]:
        now = time.time()
        return {
            "timestamp": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "epoch": now,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> str:
        """
        Append one event to the journal.  Returns the event_id (hex UUID).
        Silently degrades (logs warning) if the journal file is not writable.
        """
        from uuid import uuid4

        if event_type not in _EVENT_TYPES:
            logger.warning("narrative_engine: unknown event_type=%s — allowed: %s",
                           event_type, sorted(_EVENT_TYPES))

        event_id = uuid4().hex
        entry = {
            "event_id": event_id,
            "event_type": event_type,
            **self._now(),
            "payload": payload,
        }
        line = json.dumps(entry, default=str) + "\n"
        try:
            with self.journal_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError as exc:
            logger.warning("narrative_engine: journal write failed: %s", exc)
        return event_id

    def replay_journal(self, since: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Read journal from disk and return ordered list of events.
        If *since* is a Unix epoch float, only events after that time are returned.
        """
        events: List[Dict[str, Any]] = []
        if not self.journal_path.exists():
            return events
        try:
            with self.journal_path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        entry = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
                    if since is not None and entry.get("epoch", 0) <= since:
                        continue
                    events.append(entry)
        except OSError as exc:
            logger.warning("narrative_engine: journal read failed: %s", exc)
        return events

    def generate_summary(self) -> Dict[str, Any]:
        """
        Replay journal and produce a structured identity summary dict.

        Keys returned:
          capabilities       — list of capability names registered so far
          relationships      — dict of {partner: count} from agent_collaboration
          history_tail       — last N events (type + timestamp)
          uptime_sessions    — number of boot events seen
          self_improvements  — count of self_improvement events
          error_patterns     — count of error_pattern events
          last_value_update  — ISO timestamp of most recent value_update, or None
        """
        events = self.replay_journal()

        capabilities: List[str] = []
        seen_caps: set = set()
        relationships: Dict[str, int] = {}
        uptime_sessions: int = 0
        self_improvements: int = 0
        error_patterns: int = 0
        last_value_update: Optional[str] = None

        for ev in events:
            et = ev.get("event_type", "")
            pl = ev.get("payload", {}) or {}

            if et == "boot":
                uptime_sessions += 1

            elif et == "capability_registered":
                cap = pl.get("name") or pl.get("capability", "")
                if cap and cap not in seen_caps and len(capabilities) < _SUMMARY_MAX_CAPS:
                    capabilities.append(cap)
                    seen_caps.add(cap)

            elif et == "agent_collaboration":
                partner = pl.get("partner") or pl.get("agent_id", "unknown")
                relationships[partner] = relationships.get(partner, 0) + 1

            elif et == "self_improvement":
                self_improvements += 1

            elif et == "error_pattern":
                error_patterns += 1

            elif et == "value_update":
                last_value_update = ev.get("timestamp")

        tail_events = events[-_HISTORY_TAIL_SIZE:] if events else []
        history_tail = [
            {"event_type": e.get("event_type"), "timestamp": e.get("timestamp")}
            for e in tail_events
        ]

        return {
            "capabilities": capabilities,
            "relationships": relationships,
            "history_tail": history_tail,
            "uptime_sessions": uptime_sessions,
            "self_improvements": self_improvements,
            "error_patterns": error_patterns,
            "last_value_update": last_value_update,
        }
