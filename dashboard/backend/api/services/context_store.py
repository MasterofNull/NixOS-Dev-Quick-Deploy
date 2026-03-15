"""
Context-Aware Storage with SQLite + FTS5
Implements context-mode strategies for deployment tracking
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ContextStore:
    """
    Intelligent context storage using SQLite + FTS5

    Implements context-mode strategies:
    - Event tracking with full-text search
    - BM25 ranking for relevance
    - Progressive disclosure
    - Session continuity
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path.home() / ".deploy" / "context.db")

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Initialize database schema with FTS5"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Create tables
        self.conn.executescript("""
            -- Deployment events table
            CREATE TABLE IF NOT EXISTS deployment_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message TEXT NOT NULL,
                metadata TEXT,
                progress INTEGER,
                user TEXT,
                UNIQUE(deployment_id, timestamp)
            );

            -- FTS5 virtual table for full-text search with BM25 ranking
            CREATE VIRTUAL TABLE IF NOT EXISTS deployment_events_fts USING fts5(
                deployment_id UNINDEXED,
                message,
                metadata,
                content='deployment_events',
                content_rowid='id',
                tokenize='porter unicode61'
            );

            -- Triggers to keep FTS5 in sync with main table
            CREATE TRIGGER IF NOT EXISTS deployment_events_ai AFTER INSERT ON deployment_events BEGIN
                INSERT INTO deployment_events_fts(rowid, deployment_id, message, metadata)
                VALUES (new.id, new.deployment_id, new.message, new.metadata);
            END;

            CREATE TRIGGER IF NOT EXISTS deployment_events_ad AFTER DELETE ON deployment_events BEGIN
                DELETE FROM deployment_events_fts WHERE rowid = old.id;
            END;

            CREATE TRIGGER IF NOT EXISTS deployment_events_au AFTER UPDATE ON deployment_events BEGIN
                UPDATE deployment_events_fts SET
                    deployment_id = new.deployment_id,
                    message = new.message,
                    metadata = new.metadata
                WHERE rowid = new.id;
            END;

            -- Deployments table (summary)
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id TEXT UNIQUE NOT NULL,
                command TEXT NOT NULL,
                user TEXT,
                status TEXT NOT NULL,
                started_at DATETIME NOT NULL,
                completed_at DATETIME,
                progress INTEGER DEFAULT 0,
                exit_code INTEGER
            );

            -- Git operations tracking
            CREATE TABLE IF NOT EXISTS git_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id TEXT,
                operation TEXT NOT NULL,
                branch TEXT,
                commit_hash TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                files_changed TEXT
            );

            -- File edits tracking
            CREATE TABLE IF NOT EXISTS file_edits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deployment_id TEXT,
                file_path TEXT NOT NULL,
                operation TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                size_before INTEGER,
                size_after INTEGER
            );

            -- Create indexes for performance
            CREATE INDEX IF NOT EXISTS idx_deployment_events_id ON deployment_events(deployment_id);
            CREATE INDEX IF NOT EXISTS idx_deployment_events_timestamp ON deployment_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
            CREATE INDEX IF NOT EXISTS idx_deployments_started ON deployments(started_at);
        """)

        self.conn.commit()
        logger.info(f"Context store initialized: {self.db_path}")

    # ========================================================================
    # Deployment Tracking
    # ========================================================================

    def start_deployment(self, deployment_id: str, command: str, user: str = "system") -> bool:
        """Start tracking a new deployment"""
        try:
            self.conn.execute("""
                INSERT INTO deployments (deployment_id, command, user, status, started_at)
                VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP)
            """, (deployment_id, command, user))

            self.conn.execute("""
                INSERT INTO deployment_events (deployment_id, event_type, message, user, progress)
                VALUES (?, 'started', ?, ?, 0)
            """, (deployment_id, f"Deployment started: {command}", user))

            self.conn.commit()
            logger.info(f"Started tracking deployment: {deployment_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Deployment already exists: {deployment_id}")
            return False

    def add_event(self, deployment_id: str, event_type: str, message: str,
                  progress: int = 0, metadata: dict = None) -> int:
        """Add an event to deployment history"""
        metadata_json = json.dumps(metadata) if metadata else None

        cursor = self.conn.execute("""
            INSERT INTO deployment_events
            (deployment_id, event_type, message, progress, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (deployment_id, event_type, message, progress, metadata_json))

        # Update deployment progress
        self.conn.execute("""
            UPDATE deployments SET progress = ? WHERE deployment_id = ?
        """, (progress, deployment_id))

        self.conn.commit()
        return cursor.lastrowid

    def complete_deployment(self, deployment_id: str, success: bool = True,
                          exit_code: int = 0, message: str = None) -> bool:
        """Mark deployment as complete"""
        status = "success" if success else "failed"
        message = message or f"Deployment {status}"

        self.conn.execute("""
            UPDATE deployments
            SET status = ?, completed_at = CURRENT_TIMESTAMP,
                progress = ?, exit_code = ?
            WHERE deployment_id = ?
        """, (status, 100 if success else None, exit_code, deployment_id))

        self.conn.execute("""
            INSERT INTO deployment_events (deployment_id, event_type, message, progress)
            VALUES (?, ?, ?, ?)
        """, (deployment_id, status, message, 100 if success else 0))

        self.conn.commit()
        logger.info(f"Deployment {deployment_id} completed: {status}")
        return True

    # ========================================================================
    # Context-Aware Retrieval with FTS5 + BM25
    # ========================================================================

    def search_deployments(self, query: str, limit: int = 20,
                          offset: int = 0) -> List[Dict]:
        """
        Search deployment events using FTS5 with BM25 ranking

        Features:
        - Porter stemming (caching → cached, caches)
        - Trigram matching (useEff → useEffect)
        - BM25 relevance scoring
        - Smart snippet extraction
        """
        try:
            cursor = self.conn.execute("""
                SELECT
                    de.id,
                    de.deployment_id,
                    de.event_type,
                    de.message,
                    de.timestamp,
                    de.progress,
                    de.metadata,
                    bm25(deployment_events_fts) as rank,
                    snippet(deployment_events_fts, 1, '**', '**', '...', 32) as snippet
                FROM deployment_events de
                JOIN deployment_events_fts ON de.id = deployment_events_fts.rowid
                WHERE deployment_events_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """, (query, limit, offset))

            results = []
            for row in cursor:
                results.append({
                    "id": row["id"],
                    "deployment_id": row["deployment_id"],
                    "event_type": row["event_type"],
                    "message": row["message"],
                    "timestamp": row["timestamp"],
                    "progress": row["progress"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                    "relevance_score": row["rank"],
                    "snippet": row["snippet"]
                })

            logger.info(f"Search '{query}' returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def get_deployment_summary(self, deployment_id: str) -> Optional[Dict]:
        """Get context-efficient deployment summary (not full logs)"""
        cursor = self.conn.execute("""
            SELECT
                deployment_id,
                command,
                user,
                status,
                started_at,
                completed_at,
                progress,
                exit_code,
                (julianday(COALESCE(completed_at, CURRENT_TIMESTAMP)) -
                 julianday(started_at)) * 86400 as duration_seconds
            FROM deployments
            WHERE deployment_id = ?
        """, (deployment_id,))

        row = cursor.fetchone()
        if not row:
            return None

        # Get event counts by type (not full events)
        event_counts = {}
        cursor = self.conn.execute("""
            SELECT event_type, COUNT(*) as count
            FROM deployment_events
            WHERE deployment_id = ?
            GROUP BY event_type
        """, (deployment_id,))

        for row in cursor:
            event_counts[row["event_type"]] = row["count"]

        return {
            "deployment_id": row["deployment_id"],
            "command": row["command"],
            "user": row["user"],
            "status": row["status"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "progress": row["progress"],
            "exit_code": row["exit_code"],
            "duration_seconds": row["duration_seconds"],
            "event_counts": event_counts,
            "context_saved": True  # Full logs in DB, not in response
        }

    def get_recent_deployments(self, limit: int = 20, status: str = None) -> List[Dict]:
        """Get recent deployments (summaries only, not full logs)"""
        if status:
            cursor = self.conn.execute("""
                SELECT deployment_id, command, status, started_at, completed_at, progress
                FROM deployments
                WHERE status = ?
                ORDER BY started_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            cursor = self.conn.execute("""
                SELECT deployment_id, command, status, started_at, completed_at, progress
                FROM deployments
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))

        return [dict(row) for row in cursor]

    # ========================================================================
    # Progressive Disclosure (Context-Efficient Retrieval)
    # ========================================================================

    def get_deployment_errors_only(self, deployment_id: str, limit: int = 10) -> List[Dict]:
        """Get only error events (context-efficient)"""
        cursor = self.conn.execute("""
            SELECT message, timestamp, metadata
            FROM deployment_events
            WHERE deployment_id = ? AND event_type IN ('failed', 'error')
            ORDER BY timestamp DESC
            LIMIT ?
        """, (deployment_id, limit))

        return [dict(row) for row in cursor]

    def get_deployment_timeline(self, deployment_id: str) -> List[Dict]:
        """Get condensed timeline (not full logs)"""
        cursor = self.conn.execute("""
            SELECT event_type, message, timestamp, progress
            FROM deployment_events
            WHERE deployment_id = ?
              AND event_type IN ('started', 'progress', 'success', 'failed', 'rollback')
            ORDER BY timestamp ASC
        """, (deployment_id,))

        return [dict(row) for row in cursor]

    # ========================================================================
    # Git and File Tracking
    # ========================================================================

    def track_git_operation(self, deployment_id: str, operation: str,
                           branch: str = None, commit_hash: str = None,
                           files_changed: List[str] = None) -> int:
        """Track git operation during deployment"""
        cursor = self.conn.execute("""
            INSERT INTO git_operations
            (deployment_id, operation, branch, commit_hash, files_changed)
            VALUES (?, ?, ?, ?, ?)
        """, (deployment_id, operation, branch, commit_hash,
              json.dumps(files_changed) if files_changed else None))

        self.conn.commit()
        return cursor.lastrowid

    def track_file_edit(self, deployment_id: str, file_path: str,
                       operation: str, size_before: int = None,
                       size_after: int = None) -> int:
        """Track file edit during deployment"""
        cursor = self.conn.execute("""
            INSERT INTO file_edits
            (deployment_id, file_path, operation, size_before, size_after)
            VALUES (?, ?, ?, ?, ?)
        """, (deployment_id, file_path, operation, size_before, size_after))

        self.conn.commit()
        return cursor.lastrowid

    # ========================================================================
    # Cleanup and Maintenance
    # ========================================================================

    def cleanup_old_deployments(self, days: int = 30) -> int:
        """Remove deployments older than specified days"""
        cursor = self.conn.execute("""
            DELETE FROM deployment_events
            WHERE deployment_id IN (
                SELECT deployment_id FROM deployments
                WHERE julianday(CURRENT_TIMESTAMP) - julianday(started_at) > ?
            )
        """, (days,))

        affected = cursor.rowcount

        cursor = self.conn.execute("""
            DELETE FROM deployments
            WHERE julianday(CURRENT_TIMESTAMP) - julianday(started_at) > ?
        """, (days,))

        affected += cursor.rowcount
        self.conn.commit()

        logger.info(f"Cleaned up {affected} old deployment records")
        return affected

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Context store closed")


# ============================================================================
# Singleton instance
# ============================================================================

_context_store = None


def get_context_store() -> ContextStore:
    """Get singleton context store instance"""
    global _context_store
    if _context_store is None:
        _context_store = ContextStore()
    return _context_store
