"""
Pattern Index — Phase 20: World Model Predictive Warming

Records query sequences in PostgreSQL and predicts likely follow-on queries
based on recency + co-occurrence + time-of-day heuristics.

Table: query_sequence_patterns (created by V20__world_model_query_patterns.sql)
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

logger = logging.getLogger("world-model")

_RETENTION_DAYS: int = int(os.environ.get("WORLD_MODEL_PATTERN_RETENTION_DAYS", "7"))


def _pg_dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "aidb")
    user = os.environ.get("POSTGRES_USER", "aidb")
    pw_file = os.environ.get("POSTGRES_PASSWORD_FILE", "")
    pw = ""
    if pw_file:
        try:
            pw = open(pw_file).read().strip()
        except OSError:
            pass
    pw = pw or os.environ.get("POSTGRES_PASSWORD", "")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


def _query_hash(text: str) -> str:
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]


class PatternIndex:
    """Lightweight query-sequence pattern recorder and predictor."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or _pg_dsn()

    def _connect(self):
        import psycopg  # type: ignore
        return psycopg.connect(self._dsn)

    def record(self, query_text: str, previous_hash: Optional[str] = None) -> str:
        """Upsert query into pattern index. Returns the hash for this query."""
        now = datetime.now(timezone.utc)
        qhash = _query_hash(query_text)
        summary = query_text[:120]
        hour = now.hour
        dow = now.weekday()

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    # Upsert by hash + hour
                    cur.execute(
                        """
                        INSERT INTO query_sequence_patterns
                          (query_hash, query_summary, hour_of_day, day_of_week,
                           follow_on_hashes, occurrence_count, last_seen)
                        VALUES (%s, %s, %s, %s, %s, 1, NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        (qhash, summary, hour, dow, []),
                    )
                    # Increment occurrence and update last_seen
                    cur.execute(
                        """
                        UPDATE query_sequence_patterns
                        SET occurrence_count = occurrence_count + 1,
                            last_seen = NOW()
                        WHERE query_hash = %s AND hour_of_day = %s
                        """,
                        (qhash, hour),
                    )
                    # Link to previous query in follow_on_hashes
                    if previous_hash:
                        cur.execute(
                            """
                            UPDATE query_sequence_patterns
                            SET follow_on_hashes = array_append(
                                COALESCE(follow_on_hashes, '{}'), %s
                            )
                            WHERE query_hash = %s AND hour_of_day = %s
                              AND NOT (%s = ANY(COALESCE(follow_on_hashes, '{}')))
                            """,
                            (qhash, previous_hash, hour, qhash),
                        )
                conn.commit()
        except Exception as exc:
            logger.debug("pattern_index.record failed (non-fatal): %s", exc)

        return qhash

    def predict_next(
        self, current_hash: str, top_k: int = 3
    ) -> List[Tuple[str, float]]:
        """Predict likely next queries. Returns list of (query_summary, probability)."""
        now = datetime.now(timezone.utc)
        hour = now.hour

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    # Find records where current_hash appears in follow_on_hashes
                    cur.execute(
                        """
                        SELECT q2.query_summary, q2.occurrence_count
                        FROM query_sequence_patterns q1
                        JOIN query_sequence_patterns q2
                          ON q2.query_hash = ANY(q1.follow_on_hashes)
                         AND q2.hour_of_day = %s
                        WHERE q1.query_hash = %s
                        ORDER BY q2.occurrence_count DESC
                        LIMIT %s
                        """,
                        (hour, current_hash, top_k),
                    )
                    rows = cur.fetchall()

                    if not rows:
                        # Fallback: most frequent queries at this hour
                        cur.execute(
                            """
                            SELECT query_summary, occurrence_count
                            FROM query_sequence_patterns
                            WHERE hour_of_day = %s
                            ORDER BY occurrence_count DESC
                            LIMIT %s
                            """,
                            (hour, top_k),
                        )
                        rows = cur.fetchall()

                    if not rows:
                        return []

                    total = sum(r[1] for r in rows)
                    return [(r[0], round(r[1] / total, 3)) for r in rows]

        except Exception as exc:
            logger.debug("pattern_index.predict_next failed (non-fatal): %s", exc)
            return []

    def prune_old(self, days: int = _RETENTION_DAYS) -> int:
        """Delete rows older than `days` days. Returns row count deleted."""
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM query_sequence_patterns "
                        "WHERE last_seen < NOW() - INTERVAL '%s days'",
                        (days,),
                    )
                    deleted = cur.rowcount
                conn.commit()
                return deleted
        except Exception as exc:
            logger.debug("pattern_index.prune_old failed (non-fatal): %s", exc)
            return 0
