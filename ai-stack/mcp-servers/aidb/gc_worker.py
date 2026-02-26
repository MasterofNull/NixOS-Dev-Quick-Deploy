"""AIDB stale-vector garbage-collection worker (Phase 6.2.3)."""

import sqlalchemy as sa
from datetime import datetime, timezone
from typing import Any, Dict
import logging

LOGGER = logging.getLogger(__name__)


def run_gc_pass_sync(engine: Any, stale_days: int, dry_run: bool = False) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc).isoformat()
    # Build the cutoff timestamp string for comparison inside JSON.
    # We use a SQL expression that casts metadata JSON fields to text
    # and compares them, since the values are stored as ISO 8601 strings.
    sql_candidates = sa.text(
        """
        SELECT id
        FROM document_embeddings
        WHERE
            (metadata->>'ingested_at') IS NOT NULL
            AND (metadata->>'last_accessed_at') IS NOT NULL
            AND (metadata->>'last_accessed_at') = (metadata->>'ingested_at')
            AND (metadata->>'feedback_linked') IS DISTINCT FROM 'true'
            AND (metadata->>'ingested_at')::timestamptz < NOW() - INTERVAL ':stale_days days'
        """
    )
    # NOTE: interval interpolation via bindparams is dialect-specific;
    # use plain string formatting for the integer day count (safe — it
    # comes from an env var validated as int at module load time).
    sql_candidates_safe = sa.text(
        f"""
        SELECT id
        FROM document_embeddings
        WHERE
            (metadata->>'ingested_at') IS NOT NULL
            AND (metadata->>'last_accessed_at') IS NOT NULL
            AND (metadata->>'last_accessed_at') = (metadata->>'ingested_at')
            AND (metadata->>'feedback_linked') IS DISTINCT FROM 'true'
            AND (metadata->>'ingested_at')::timestamptz < NOW() - INTERVAL '{stale_days} days'
        """
    )
    sql_delete = sa.text(
        f"""
        DELETE FROM document_embeddings
        WHERE id = ANY(:ids)
        """
    )

    summary: Dict[str, Any] = {"dry_run": dry_run, "collections": {}}
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql_candidates_safe).fetchall()
            candidate_ids = [row[0] for row in rows]
            count = len(candidate_ids)
            summary["collections"]["document_embeddings"] = count
            summary["total_candidates"] = count

            if dry_run:
                LOGGER.info(
                    "GC dry-run: %d stale vector(s) found (older than %d days, never accessed)",
                    count,
                    stale_days,
                )
                return summary

            if candidate_ids:
                conn.execute(sql_delete, {"ids": candidate_ids})
                conn.commit()
                LOGGER.info(
                    "GC pass: deleted %d stale vector(s) from document_embeddings",
                    count,
                )
            else:
                LOGGER.info("GC pass: no stale vectors found, nothing deleted")

            summary["total_deleted"] = count
            return summary
    except Exception:  # noqa: BLE001
        LOGGER.exception("GC pass failed")
        raise
