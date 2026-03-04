#!/usr/bin/env python3
"""
sync-hint-feedback-db.py

Persist hint feedback JSONL into Postgres and build semantic aggregate profiles
used by hint ranking and PRSI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import psycopg  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]


DEFAULT_HINT_FEEDBACK_PATH = Path("/var/log/nixos-ai-stack/hint-feedback.jsonl")
DEFAULT_SUMMARY_OUT = Path("/var/lib/ai-stack/hybrid/telemetry/hint-feedback-sync-latest.json")


def _read_secret(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def pg_dsn() -> str:
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "aidb")
    user = os.getenv("POSTGRES_USER", "aidb")
    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password:
        pw_file = Path(os.getenv("POSTGRES_PASSWORD_FILE", "/run/secrets/postgres_password"))
        password = _read_secret(pw_file)
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def parse_ts(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _norm_list(values: Any, cap: int = 16) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    seen = set()
    for item in values:
        text = str(item or "").strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text[:64])
        if len(out) >= cap:
            break
    return out


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"))


def _event_id(payload: Dict[str, Any]) -> str:
    basis = _json_dumps(
        {
            "timestamp": payload.get("timestamp", ""),
            "hint_id": payload.get("hint_id", ""),
            "agent": payload.get("agent", ""),
            "task_id": payload.get("task_id", ""),
            "score": payload.get("score"),
            "helpful": payload.get("helpful"),
            "comment": payload.get("comment", ""),
        }
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def semantic_tags(comment: str, score: Optional[float], helpful: Optional[bool]) -> List[str]:
    text = (comment or "").lower()
    tags: List[str] = []

    lex = {
        "tool_error": ("error", "failed", "timeout", "exception", "traceback", "denied"),
        "missing_context": ("missing", "unclear", "context", "insufficient", "unknown"),
        "too_verbose": ("too long", "verbose", "wordy", "token", "huge"),
        "stale_signal": ("stale", "old", "outdated", "not current"),
        "actionable": ("run ", "scripts/", "fix", "check", "verify", "retry"),
        "relevance_high": ("relevant", "exact", "helpful", "worked"),
        "relevance_low": ("irrelevant", "off topic", "not useful", "waste"),
    }
    for tag, words in lex.items():
        if any(w in text for w in words):
            tags.append(tag)

    if score is not None:
        if score >= 0.5:
            tags.append("score_positive")
        elif score <= -0.5:
            tags.append("score_negative")
    if helpful is True:
        tags.append("helpful_true")
    elif helpful is False:
        tags.append("helpful_false")

    if not tags:
        tags.append("neutral")
    return sorted(set(tags))


@dataclass
class Event:
    event_id: str
    ts: datetime
    hint_id: str
    agent: str
    task_id: str
    helpful: Optional[bool]
    score: Optional[float]
    comment: str
    preferred_tools: List[str]
    preferred_data_sources: List[str]
    preferred_hint_types: List[str]
    preferred_tags: List[str]
    semantic_tags: List[str]
    raw: Dict[str, Any]


def parse_feedback_rows(path: Path) -> Iterable[Event]:
    if not path.exists():
        return []
    rows: List[Event] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        hint_id = str(obj.get("hint_id", "") or "").strip()
        if not hint_id:
            continue
        ts = parse_ts(str(obj.get("timestamp", "")))
        if ts is None:
            ts = datetime.now(tz=timezone.utc)
        helpful_raw = obj.get("helpful")
        helpful: Optional[bool]
        if isinstance(helpful_raw, bool):
            helpful = helpful_raw
        else:
            helpful = None
        score_raw = obj.get("score")
        score: Optional[float] = None
        if score_raw is not None:
            try:
                score = max(-1.0, min(1.0, float(score_raw)))
            except (TypeError, ValueError):
                score = None
        comment = str(obj.get("comment", "") or "").strip()[:512]
        prefs = obj.get("agent_preferences", {})
        if not isinstance(prefs, dict):
            prefs = {}
        payload = {
            "timestamp": ts.isoformat(),
            "hint_id": hint_id,
            "agent": str(obj.get("agent", "") or "").strip()[:64] or "unknown",
            "task_id": str(obj.get("task_id", "") or "").strip()[:128],
            "helpful": helpful,
            "score": score,
            "comment": comment,
            "preferred_tools": _norm_list(prefs.get("preferred_tools")),
            "preferred_data_sources": _norm_list(prefs.get("preferred_data_sources")),
            "preferred_hint_types": _norm_list(prefs.get("preferred_hint_types")),
            "preferred_tags": _norm_list(prefs.get("preferred_tags")),
            "raw_payload": obj,
        }
        rows.append(
            Event(
                event_id=_event_id(payload),
                ts=ts,
                hint_id=payload["hint_id"],
                agent=payload["agent"],
                task_id=payload["task_id"],
                helpful=payload["helpful"],
                score=payload["score"],
                comment=payload["comment"],
                preferred_tools=payload["preferred_tools"],
                preferred_data_sources=payload["preferred_data_sources"],
                preferred_hint_types=payload["preferred_hint_types"],
                preferred_tags=payload["preferred_tags"],
                semantic_tags=semantic_tags(payload["comment"], payload["score"], payload["helpful"]),
                raw=obj,
            )
        )
    return rows


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS hint_feedback_events (
  event_id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_ts TIMESTAMPTZ NOT NULL,
  hint_id TEXT NOT NULL,
  agent TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  helpful BOOLEAN NULL,
  score DOUBLE PRECISION NULL,
  comment TEXT NOT NULL DEFAULT '',
  preferred_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
  preferred_data_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  preferred_hint_types JSONB NOT NULL DEFAULT '[]'::jsonb,
  preferred_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  semantic_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_hint_feedback_events_hint_id ON hint_feedback_events (hint_id);
CREATE INDEX IF NOT EXISTS idx_hint_feedback_events_event_ts ON hint_feedback_events (event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_hint_feedback_events_agent ON hint_feedback_events (agent);

CREATE TABLE IF NOT EXISTS hint_feedback_profiles (
  hint_id TEXT PRIMARY KEY,
  window_days INTEGER NOT NULL,
  event_count INTEGER NOT NULL DEFAULT 0,
  helpful_count INTEGER NOT NULL DEFAULT 0,
  unhelpful_count INTEGER NOT NULL DEFAULT 0,
  helpful_rate DOUBLE PRECISION NULL,
  mean_score DOUBLE PRECISION NULL,
  confidence DOUBLE PRECISION NULL,
  dominant_semantic_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  preferred_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
  preferred_data_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  preferred_hint_types JSONB NOT NULL DEFAULT '[]'::jsonb,
  preferred_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ensure_schema(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.commit()


def insert_events(conn: Any, rows: Iterable[Event]) -> Tuple[int, int]:
    inserted = 0
    skipped = 0
    sql = """
    INSERT INTO hint_feedback_events (
      event_id, event_ts, hint_id, agent, task_id, helpful, score, comment,
      preferred_tools, preferred_data_sources, preferred_hint_types, preferred_tags,
      semantic_tags, raw_payload
    ) VALUES (
      %(event_id)s, %(event_ts)s, %(hint_id)s, %(agent)s, %(task_id)s, %(helpful)s, %(score)s, %(comment)s,
      %(preferred_tools)s::jsonb, %(preferred_data_sources)s::jsonb, %(preferred_hint_types)s::jsonb, %(preferred_tags)s::jsonb,
      %(semantic_tags)s::jsonb, %(raw_payload)s::jsonb
    )
    ON CONFLICT (event_id) DO NOTHING;
    """
    with conn.cursor() as cur:
        for e in rows:
            payload = {
                "event_id": e.event_id,
                "event_ts": e.ts,
                "hint_id": e.hint_id,
                "agent": e.agent,
                "task_id": e.task_id,
                "helpful": e.helpful,
                "score": e.score,
                "comment": e.comment,
                "preferred_tools": _json_dumps(e.preferred_tools),
                "preferred_data_sources": _json_dumps(e.preferred_data_sources),
                "preferred_hint_types": _json_dumps(e.preferred_hint_types),
                "preferred_tags": _json_dumps(e.preferred_tags),
                "semantic_tags": _json_dumps(e.semantic_tags),
                "raw_payload": _json_dumps(e.raw),
            }
            cur.execute(sql, payload)
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
    conn.commit()
    return inserted, skipped


def _top_values(counter: Counter, limit: int = 8) -> List[str]:
    return [k for k, _ in counter.most_common(limit)]


def rebuild_profiles(conn: Any, window_days: int) -> int:
    since = datetime.now(tz=timezone.utc) - timedelta(days=window_days)
    query = """
    SELECT hint_id, helpful, score, semantic_tags,
           preferred_tools, preferred_data_sources, preferred_hint_types, preferred_tags
    FROM hint_feedback_events
    WHERE event_ts >= %s
    """
    grouped: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "event_count": 0,
            "helpful_count": 0,
            "unhelpful_count": 0,
            "scores": [],
            "semantic_tags": Counter(),
            "preferred_tools": Counter(),
            "preferred_data_sources": Counter(),
            "preferred_hint_types": Counter(),
            "preferred_tags": Counter(),
        }
    )

    with conn.cursor() as cur:
        cur.execute(query, (since,))
        for row in cur.fetchall():
            hint_id = str(row[0])
            helpful = row[1]
            score = row[2]
            semantic = row[3] or []
            pref_tools = row[4] or []
            pref_sources = row[5] or []
            pref_types = row[6] or []
            pref_tags = row[7] or []
            g = grouped[hint_id]
            g["event_count"] += 1
            if helpful is True:
                g["helpful_count"] += 1
            elif helpful is False:
                g["unhelpful_count"] += 1
            if score is not None:
                g["scores"].append(float(score))
            for item in semantic:
                g["semantic_tags"][str(item)] += 1
            for item in pref_tools:
                g["preferred_tools"][str(item)] += 1
            for item in pref_sources:
                g["preferred_data_sources"][str(item)] += 1
            for item in pref_types:
                g["preferred_hint_types"][str(item)] += 1
            for item in pref_tags:
                g["preferred_tags"][str(item)] += 1

    upsert = """
    INSERT INTO hint_feedback_profiles (
      hint_id, window_days, event_count, helpful_count, unhelpful_count, helpful_rate, mean_score, confidence,
      dominant_semantic_tags, preferred_tools, preferred_data_sources, preferred_hint_types, preferred_tags, updated_at
    ) VALUES (
      %(hint_id)s, %(window_days)s, %(event_count)s, %(helpful_count)s, %(unhelpful_count)s, %(helpful_rate)s, %(mean_score)s, %(confidence)s,
      %(dominant_semantic_tags)s::jsonb, %(preferred_tools)s::jsonb, %(preferred_data_sources)s::jsonb, %(preferred_hint_types)s::jsonb, %(preferred_tags)s::jsonb, now()
    )
    ON CONFLICT (hint_id) DO UPDATE SET
      window_days = EXCLUDED.window_days,
      event_count = EXCLUDED.event_count,
      helpful_count = EXCLUDED.helpful_count,
      unhelpful_count = EXCLUDED.unhelpful_count,
      helpful_rate = EXCLUDED.helpful_rate,
      mean_score = EXCLUDED.mean_score,
      confidence = EXCLUDED.confidence,
      dominant_semantic_tags = EXCLUDED.dominant_semantic_tags,
      preferred_tools = EXCLUDED.preferred_tools,
      preferred_data_sources = EXCLUDED.preferred_data_sources,
      preferred_hint_types = EXCLUDED.preferred_hint_types,
      preferred_tags = EXCLUDED.preferred_tags,
      updated_at = now();
    """

    updated = 0
    with conn.cursor() as cur:
        for hint_id, g in grouped.items():
            event_count = int(g["event_count"])
            if event_count <= 0:
                continue
            helpful_count = int(g["helpful_count"])
            unhelpful_count = int(g["unhelpful_count"])
            helpful_rate = float(helpful_count / event_count)
            mean_score = float(sum(g["scores"]) / len(g["scores"])) if g["scores"] else None
            confidence = float(min(1.0, event_count / 20.0))
            cur.execute(
                upsert,
                {
                    "hint_id": hint_id,
                    "window_days": window_days,
                    "event_count": event_count,
                    "helpful_count": helpful_count,
                    "unhelpful_count": unhelpful_count,
                    "helpful_rate": helpful_rate,
                    "mean_score": mean_score,
                    "confidence": confidence,
                    "dominant_semantic_tags": _json_dumps(_top_values(g["semantic_tags"])),
                    "preferred_tools": _json_dumps(_top_values(g["preferred_tools"])),
                    "preferred_data_sources": _json_dumps(_top_values(g["preferred_data_sources"])),
                    "preferred_hint_types": _json_dumps(_top_values(g["preferred_hint_types"])),
                    "preferred_tags": _json_dumps(_top_values(g["preferred_tags"])),
                },
            )
            updated += 1
    conn.commit()
    return updated


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync hint feedback JSONL into Postgres semantic profiles.")
    p.add_argument("--feedback-log", default=str(DEFAULT_HINT_FEEDBACK_PATH))
    p.add_argument("--window-days", type=int, default=30)
    p.add_argument("--summary-out", default=str(DEFAULT_SUMMARY_OUT))
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if psycopg is None:
        raise SystemExit("psycopg is required (run with the system ai-stack python env)")
    feedback_path = Path(args.feedback_log).expanduser()
    summary_out = Path(args.summary_out).expanduser()

    events = list(parse_feedback_rows(feedback_path))
    dsn = pg_dsn()
    conn = psycopg.connect(dsn, connect_timeout=5)
    ensure_schema(conn)
    inserted, skipped = insert_events(conn, events)
    profiles = rebuild_profiles(conn, window_days=max(1, int(args.window_days)))
    conn.close()

    summary = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "feedback_log": str(feedback_path),
        "events_seen": len(events),
        "events_inserted": inserted,
        "events_skipped": skipped,
        "profiles_updated": profiles,
    }
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
