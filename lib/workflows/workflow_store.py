#!/usr/bin/env python3
"""
Workflow Store - Persistence layer for workflows and telemetry.

This module provides storage and retrieval for workflows, templates,
execution history, and telemetry data.
"""

import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class WorkflowStore:
    """Stores and retrieves workflows."""

    def __init__(self, db_path: str = "/tmp/workflow-store.db"):
        """
        Initialize workflow store.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path) if db_path != ":memory:" else db_path
        if self.db_path != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Cache connection for in-memory databases
        self._cached_conn = None
        if db_path == ":memory:":
            self._cached_conn = sqlite3.connect(":memory:")
            self._cached_conn.row_factory = sqlite3.Row

        self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Workflows table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    goal TEXT,
                    created_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)

            # Workflow executions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    execution_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    total_duration INTEGER,
                    success INTEGER,
                    data TEXT NOT NULL,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                )
            """)

            # Task executions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_executions (
                    execution_id TEXT PRIMARY KEY,
                    workflow_execution_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    duration INTEGER,
                    retry_count INTEGER,
                    agent_id TEXT,
                    error_message TEXT,
                    data TEXT NOT NULL,
                    FOREIGN KEY (workflow_execution_id) REFERENCES workflow_executions(execution_id)
                )
            """)

            # Telemetry table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    workflow_id TEXT,
                    execution_id TEXT,
                    task_id TEXT,
                    timestamp TEXT NOT NULL,
                    data TEXT
                )
            """)

            # Task logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    workflow_execution_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context TEXT,
                    FOREIGN KEY (execution_id) REFERENCES task_executions(execution_id)
                )
            """)

            # Create indices
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_executions_workflow_id
                ON workflow_executions(workflow_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_executions_status
                ON workflow_executions(status)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_executions_workflow
                ON task_executions(workflow_execution_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_workflow
                ON telemetry(workflow_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_execution
                ON telemetry(execution_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_logs_execution
                ON task_logs(execution_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_logs_workflow
                ON task_logs(workflow_execution_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_logs_timestamp
                ON task_logs(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_logs_level
                ON task_logs(level)
            """)

            conn.commit()

        logger.info(f"Initialized workflow store at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        # Use cached connection for in-memory databases
        if self._cached_conn is not None:
            yield self._cached_conn
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def save_workflow(self, workflow: Any):
        """
        Save a workflow.

        Args:
            workflow: Workflow object
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO workflows (id, name, description, goal, created_at, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                workflow.id,
                workflow.name,
                workflow.description,
                workflow.goal,
                workflow.created_at,
                json.dumps(workflow.to_dict()),
            ))

            conn.commit()

        logger.info(f"Saved workflow {workflow.id}")

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a workflow by ID.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow data or None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM workflows WHERE id = ?
            """, (workflow_id,))

            row = cursor.fetchone()

            if row:
                return json.loads(row["data"])

        return None

    def list_workflows(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List workflows.

        Args:
            limit: Maximum number of workflows
            offset: Offset for pagination

        Returns:
            List of workflow data
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM workflows
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            return [json.loads(row["data"]) for row in cursor.fetchall()]

    def search_workflows(self, query: str) -> List[Dict[str, Any]]:
        """
        Search workflows by query.

        Args:
            query: Search query

        Returns:
            List of matching workflows
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM workflows
                WHERE name LIKE ? OR description LIKE ? OR goal LIKE ?
                ORDER BY created_at DESC
            """, (f"%{query}%", f"%{query}%", f"%{query}%"))

            return [json.loads(row["data"]) for row in cursor.fetchall()]

    def delete_workflow(self, workflow_id: str):
        """Delete a workflow."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            conn.commit()

        logger.info(f"Deleted workflow {workflow_id}")

    def save_execution(self, workflow_execution: Any):
        """
        Save a workflow execution.

        Args:
            workflow_execution: WorkflowExecution object
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Save workflow execution
            success = 1 if workflow_execution.status.value == "success" else 0

            cursor.execute("""
                INSERT OR REPLACE INTO workflow_executions
                (execution_id, workflow_id, status, start_time, end_time,
                 total_duration, success, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workflow_execution.execution_id,
                workflow_execution.workflow_id,
                workflow_execution.status.value,
                workflow_execution.start_time,
                workflow_execution.end_time,
                workflow_execution.total_duration,
                success,
                json.dumps(workflow_execution.to_dict()),
            ))

            # Save task executions
            for task_execution in workflow_execution.task_executions.values():
                cursor.execute("""
                    INSERT OR REPLACE INTO task_executions
                    (execution_id, workflow_execution_id, task_id, status,
                     start_time, end_time, duration, retry_count, agent_id,
                     error_message, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_execution.execution_id,
                    task_execution.workflow_execution_id,
                    task_execution.task_id,
                    task_execution.status.value,
                    task_execution.start_time,
                    task_execution.end_time,
                    task_execution.duration,
                    task_execution.retry_count,
                    task_execution.agent_id,
                    task_execution.error_message,
                    json.dumps(task_execution.to_dict()),
                ))

            conn.commit()

        logger.info(f"Saved workflow execution {workflow_execution.execution_id}")

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get a workflow execution by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM workflow_executions WHERE execution_id = ?
            """, (execution_id,))

            row = cursor.fetchone()

            if row:
                return json.loads(row["data"])

        return None

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List workflow executions.

        Args:
            workflow_id: Filter by workflow ID
            status: Filter by status
            limit: Maximum number of executions
            offset: Offset for pagination

        Returns:
            List of execution data
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT data FROM workflow_executions WHERE 1=1"
            params = []

            if workflow_id:
                query += " AND workflow_id = ?"
                params.append(workflow_id)

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)

            return [json.loads(row["data"]) for row in cursor.fetchall()]

    def get_workflow_history(
        self,
        workflow_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get execution history for a workflow.

        Args:
            workflow_id: Workflow ID
            days: Number of days to look back

        Returns:
            List of executions
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM workflow_executions
                WHERE workflow_id = ? AND start_time >= ?
                ORDER BY start_time DESC
            """, (workflow_id, cutoff))

            return [json.loads(row["data"]) for row in cursor.fetchall()]

    def save_telemetry(self, telemetry_events: List[Dict[str, Any]]):
        """Save telemetry events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for event in telemetry_events:
                cursor.execute("""
                    INSERT INTO telemetry
                    (event, workflow_id, execution_id, task_id, timestamp, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event.get("event"),
                    event.get("workflow_id"),
                    event.get("execution_id"),
                    event.get("task_id"),
                    event.get("timestamp"),
                    json.dumps(event),
                ))

            conn.commit()

        logger.debug(f"Saved {len(telemetry_events)} telemetry events")

    def get_telemetry(
        self,
        workflow_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        event_type: Optional[str] = None,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get telemetry events.

        Args:
            workflow_id: Filter by workflow ID
            execution_id: Filter by execution ID
            event_type: Filter by event type
            days: Number of days to look back

        Returns:
            List of telemetry events
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT data FROM telemetry WHERE timestamp >= ?"
            params = [cutoff]

            if workflow_id:
                query += " AND workflow_id = ?"
                params.append(workflow_id)

            if execution_id:
                query += " AND execution_id = ?"
                params.append(execution_id)

            if event_type:
                query += " AND event = ?"
                params.append(event_type)

            query += " ORDER BY timestamp DESC"

            cursor.execute(query, params)

            return [json.loads(row["data"]) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total workflows
            cursor.execute("SELECT COUNT(*) as count FROM workflows")
            total_workflows = cursor.fetchone()["count"]

            # Total executions
            cursor.execute("SELECT COUNT(*) as count FROM workflow_executions")
            total_executions = cursor.fetchone()["count"]

            # Success rate
            cursor.execute("""
                SELECT
                    SUM(success) as successes,
                    COUNT(*) as total
                FROM workflow_executions
            """)
            row = cursor.fetchone()
            success_rate = row["successes"] / row["total"] if row["total"] > 0 else 0

            # Average duration
            cursor.execute("""
                SELECT AVG(total_duration) as avg_duration
                FROM workflow_executions
                WHERE total_duration > 0
            """)
            avg_duration = cursor.fetchone()["avg_duration"] or 0

            # Recent activity (last 24 hours)
            cutoff = (datetime.utcnow() - timedelta(days=1)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) as count FROM workflow_executions
                WHERE start_time >= ?
            """, (cutoff,))
            recent_executions = cursor.fetchone()["count"]

            return {
                "total_workflows": total_workflows,
                "total_executions": total_executions,
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "recent_executions_24h": recent_executions,
            }

    def cleanup_old_data(self, days: int = 90):
        """
        Clean up old data.

        Args:
            days: Delete data older than this many days
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete old executions
            cursor.execute("""
                DELETE FROM workflow_executions
                WHERE start_time < ?
            """, (cutoff,))

            executions_deleted = cursor.rowcount

            # Delete old task executions
            cursor.execute("""
                DELETE FROM task_executions
                WHERE start_time < ?
            """, (cutoff,))

            task_executions_deleted = cursor.rowcount

            # Delete old telemetry
            cursor.execute("""
                DELETE FROM telemetry
                WHERE timestamp < ?
            """, (cutoff,))

            telemetry_deleted = cursor.rowcount

            conn.commit()

        logger.info(
            f"Cleaned up old data: {executions_deleted} executions, "
            f"{task_executions_deleted} task executions, "
            f"{telemetry_deleted} telemetry events"
        )

    def save_log(
        self,
        execution_id: str,
        task_id: str,
        workflow_execution_id: str,
        level: str,
        message: str,
        timestamp: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Save a task log entry.

        Args:
            execution_id: Task execution ID
            task_id: Task ID
            workflow_execution_id: Parent workflow execution ID
            level: Log level (DEBUG, INFO, WARN, ERROR)
            message: Log message
            timestamp: ISO format timestamp
            context: Optional context metadata
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_logs
                (execution_id, task_id, workflow_execution_id, timestamp, level, message, context)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                execution_id,
                task_id,
                workflow_execution_id,
                timestamp,
                level,
                message,
                json.dumps(context) if context else None,
            ))
            conn.commit()

        logger.debug(f"Saved log for {execution_id}: {level} {message}")

    def get_task_logs(
        self,
        execution_id: str,
        task_id: Optional[str] = None,
        level: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get task logs with filtering and pagination.

        Args:
            execution_id: Task execution ID (or workflow execution ID)
            task_id: Optional task ID filter
            level: Optional log level filter
            search: Optional search query
            limit: Maximum number of logs
            offset: Offset for pagination

        Returns:
            List of log dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Support querying by either task execution_id or workflow execution_id
            query = "SELECT * FROM task_logs WHERE (execution_id = ? OR workflow_execution_id = ?)"
            params = [execution_id, execution_id]

            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)

            if level:
                query += " AND level = ?"
                params.append(level)

            if search:
                query += " AND message LIKE ?"
                params.append(f"%{search}%")

            query += " ORDER BY timestamp ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)

            logs = []
            for row in cursor.fetchall():
                log = dict(row)
                if log.get("context"):
                    log["context"] = json.loads(log["context"])
                logs.append(log)

            return logs

    def count_task_logs(
        self,
        execution_id: str,
        task_id: Optional[str] = None,
        level: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        """
        Count task logs with filtering.

        Args:
            execution_id: Task execution ID (or workflow execution ID)
            task_id: Optional task ID filter
            level: Optional log level filter
            search: Optional search query

        Returns:
            Count of matching logs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT COUNT(*) FROM task_logs WHERE (execution_id = ? OR workflow_execution_id = ?)"
            params = [execution_id, execution_id]

            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)

            if level:
                query += " AND level = ?"
                params.append(level)

            if search:
                query += " AND message LIKE ?"
                params.append(f"%{search}%")

            cursor.execute(query, params)
            return cursor.fetchone()[0]


def main():
    """Test workflow store."""
    logging.basicConfig(level=logging.INFO)

    store = WorkflowStore()
    stats = store.get_statistics()

    print("Workflow Store Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
