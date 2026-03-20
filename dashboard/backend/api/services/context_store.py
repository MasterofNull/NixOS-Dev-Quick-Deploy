"""
Context-Aware Storage with SQLite + FTS5
Implements context-mode strategies for deployment tracking
"""

import os
import sqlite3
import json
import logging
import hashlib
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import asyncio
from contextlib import asynccontextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.config.service_endpoints import AIDB_URL

logger = logging.getLogger(__name__)

DEPLOYMENT_SEMANTIC_PROJECT = "dashboard-deployments"
DEPLOYMENT_SEMANTIC_COLLECTION = "telemetry_patterns"
DEFAULT_AIDB_KEY_FILE = "/run/secrets/aidb_api_key"
GRAPH_STOPWORDS = {
    "deployment", "deploy", "system", "build", "generation", "progress", "started",
    "success", "failed", "running", "rollback", "command", "nixos", "fast",
}
GRAPH_SERVICE_HINTS = {
    "hybrid-coordinator", "dashboard", "switchboard", "qdrant", "prometheus",
    "postgres", "redis", "embeddings", "llama", "nix", "nixos-rebuild",
    "command-center", "aidb", "ralph", "mindsdb", "grafana",
}


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
            db_path = self._resolve_db_path()

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.conn = None
        self._lock = threading.RLock()
        self._init_db()

    @staticmethod
    def _candidate_db_paths() -> List[str]:
        env_path = os.getenv("DASHBOARD_CONTEXT_DB_PATH", "").strip()
        repo_root = Path(__file__).resolve().parents[4]
        candidates = []
        if env_path:
            candidates.append(env_path)
        candidates.extend([
            "/var/lib/nixos-system-dashboard/telemetry/deployments-context.db",
            str(repo_root / "data" / "dashboard" / "context.db"),
            "/tmp/nixos-dashboard-context.db",
        ])
        return list(dict.fromkeys(candidates))

    @staticmethod
    def _can_open_writable_db(path: str) -> bool:
        try:
            db_file = Path(path)
            db_file.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE IF NOT EXISTS _context_store_probe (id INTEGER)")
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error:
            return False

    def _resolve_db_path(self) -> str:
        for candidate in self._candidate_db_paths():
            if self._can_open_writable_db(candidate):
                logger.info("Context store selected writable DB path: %s", candidate)
                return candidate
        repo_root = Path(__file__).resolve().parents[4]
        fallback = str(repo_root / "data" / "dashboard" / "context.db")
        logger.warning("Context store falling back to default DB path without writability confirmation: %s", fallback)
        return fallback

    def _reconnect_to_writable_db(self) -> None:
        replacement = self._resolve_db_path()
        if replacement == self.db_path and self.conn is not None:
            return
        if self.conn is not None:
            try:
                self.conn.close()
            except sqlite3.Error:
                logger.warning("Failed to close stale context DB connection cleanly", exc_info=True)
        self.db_path = replacement
        self._init_db()

    def _execute_write(self, operation: str, callback):
        try:
            return callback()
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "readonly" not in message and "unable to open database file" not in message:
                raise
            logger.warning("Context store write failed for %s on %s, retrying with writable fallback", operation, self.db_path)
            with self._lock:
                self._reconnect_to_writable_db()
                return callback()

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

            CREATE TABLE IF NOT EXISTS deployment_semantic_index (
                deployment_id TEXT PRIMARY KEY,
                document_id INTEGER,
                content_hash TEXT NOT NULL,
                indexed_at DATETIME,
                last_error TEXT
            );

            -- Create indexes for performance
            CREATE INDEX IF NOT EXISTS idx_deployment_events_id ON deployment_events(deployment_id);
            CREATE INDEX IF NOT EXISTS idx_deployment_events_timestamp ON deployment_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
            CREATE INDEX IF NOT EXISTS idx_deployments_started ON deployments(started_at);
            CREATE INDEX IF NOT EXISTS idx_deployment_semantic_document_id ON deployment_semantic_index(document_id);
        """)

        self.conn.commit()
        logger.info(f"Context store initialized: {self.db_path}")

    # ========================================================================
    # Deployment Tracking
    # ========================================================================

    @staticmethod
    def _timestamp() -> str:
        """Use microsecond timestamps so high-frequency events do not collide."""
        return datetime.utcnow().isoformat(timespec="microseconds")

    def start_deployment(self, deployment_id: str, command: str, user: str = "system") -> bool:
        """Start tracking a new deployment"""
        def write() -> bool:
            try:
                now = self._timestamp()
                self.conn.execute("""
                    INSERT INTO deployments (deployment_id, command, user, status, started_at)
                    VALUES (?, ?, ?, 'running', ?)
                """, (deployment_id, command, user, now))

                self.conn.execute("""
                    INSERT INTO deployment_events (deployment_id, event_type, timestamp, message, user, progress)
                    VALUES (?, 'started', ?, ?, ?, 0)
                """, (deployment_id, now, f"Deployment started: {command}", user))

                self.conn.commit()
                logger.info(f"Started tracking deployment: {deployment_id}")
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"Deployment already exists: {deployment_id}")
                return False

        return self._execute_write("start_deployment", write)

    def add_event(self, deployment_id: str, event_type: str, message: str,
                  progress: int = 0, metadata: dict = None) -> int:
        """Add an event to deployment history"""
        def write() -> int:
            metadata_json = json.dumps(metadata) if metadata else None
            now = self._timestamp()

            cursor = self.conn.execute("""
                INSERT INTO deployment_events
                (deployment_id, event_type, timestamp, message, progress, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (deployment_id, event_type, now, message, progress, metadata_json))

            self.conn.execute("""
                UPDATE deployments SET progress = ? WHERE deployment_id = ?
            """, (progress, deployment_id))

            self.conn.commit()
            return cursor.lastrowid

        return self._execute_write("add_event", write)

    def complete_deployment(self, deployment_id: str, success: bool = True,
                          exit_code: int = 0, message: str = None) -> bool:
        """Mark deployment as complete"""
        def write() -> bool:
            status = "success" if success else "failed"
            final_message = message or f"Deployment {status}"
            now = self._timestamp()

            self.conn.execute("""
                UPDATE deployments
                SET status = ?, completed_at = ?,
                    progress = ?, exit_code = ?
                WHERE deployment_id = ?
            """, (status, now, 100 if success else None, exit_code, deployment_id))

            self.conn.execute("""
                INSERT INTO deployment_events (deployment_id, event_type, timestamp, message, progress)
                VALUES (?, ?, ?, ?, ?)
            """, (deployment_id, status, now, final_message, 100 if success else 0))

            self.conn.commit()
            logger.info(f"Deployment {deployment_id} completed: {status}")
            return True

        return self._execute_write("complete_deployment", write)

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

    @staticmethod
    def _load_aidb_api_key() -> str:
        direct = os.getenv("AIDB_API_KEY", "").strip()
        if direct:
            return direct
        key_file = os.getenv("AIDB_API_KEY_FILE", "").strip() or DEFAULT_AIDB_KEY_FILE
        try:
            return Path(key_file).read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return ""
        except OSError as exc:
            logger.warning("Failed reading AIDB API key file %s: %s", key_file, exc)
            return ""

    def _aidb_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        api_key = self._load_aidb_api_key()
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    def _aidb_request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Any:
        url = f"{AIDB_URL.rstrip('/')}{path}"
        if query:
            encoded = urlencode({key: value for key, value in query.items() if value is not None})
            if encoded:
                url = f"{url}?{encoded}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, method=method.upper(), headers=self._aidb_headers())
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"AIDB {method} {path} failed: HTTP {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"AIDB {method} {path} failed: {exc.reason}") from exc

    @staticmethod
    def _deployment_relative_path(deployment_id: str) -> str:
        return f"deployments/{deployment_id}.md"

    def _build_deployment_semantic_content(self, deployment_id: str) -> Tuple[Optional[Dict[str, Any]], str]:
        summary = self.get_deployment_summary(deployment_id)
        if not summary:
            return None, ""
        timeline = self.get_deployment_timeline(deployment_id)
        lines = [
            f"# Deployment {deployment_id}",
            "",
            f"Command: {summary.get('command') or ''}",
            f"Status: {summary.get('status') or ''}",
            f"User: {summary.get('user') or ''}",
            f"Started: {summary.get('started_at') or ''}",
            f"Completed: {summary.get('completed_at') or ''}",
            f"Progress: {summary.get('progress')}",
            f"Exit Code: {summary.get('exit_code')}",
            f"Duration Seconds: {summary.get('duration_seconds')}",
            "",
            "## Event Counts",
        ]
        for event_type, count in sorted((summary.get("event_counts") or {}).items()):
            lines.append(f"- {event_type}: {count}")
        lines.extend(["", "## Timeline"])
        for event in timeline[-25:]:
            lines.append(
                f"- [{event.get('timestamp')}] {event.get('event_type')}: {event.get('message')} "
                f"(progress={event.get('progress')})"
            )
        return summary, "\n".join(lines).strip()

    def sync_deployment_to_semantic_index(self, deployment_id: str) -> Dict[str, Any]:
        with self._lock:
            summary, content = self._build_deployment_semantic_content(deployment_id)
            if not summary or not content:
                return {"status": "missing", "deployment_id": deployment_id}

            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            current = self.conn.execute(
                """
                SELECT document_id, content_hash, indexed_at
                FROM deployment_semantic_index
                WHERE deployment_id = ?
                """,
                (deployment_id,),
            ).fetchone()
            if current and current["content_hash"] == content_hash and current["document_id"]:
                return {
                    "status": "unchanged",
                    "deployment_id": deployment_id,
                    "document_id": current["document_id"],
                    "indexed_at": current["indexed_at"],
                }

            relative_path = self._deployment_relative_path(deployment_id)
            metadata = {
                "deployment_id": deployment_id,
                "command": summary.get("command"),
                "status": summary.get("status"),
                "started_at": summary.get("started_at"),
                "completed_at": summary.get("completed_at"),
                "semantic_type": "deployment-history",
            }
            try:
                self._aidb_request(
                    "/documents",
                    method="POST",
                    payload={
                        "project": DEPLOYMENT_SEMANTIC_PROJECT,
                        "relative_path": relative_path,
                        "title": f"Deployment {deployment_id}",
                        "content_type": "text/markdown",
                        "content": content,
                        "status": "approved",
                        "source_trust_level": "generated",
                    },
                )
                docs = self._aidb_request(
                    "/documents",
                    query={"project": DEPLOYMENT_SEMANTIC_PROJECT, "limit": 1000},
                )
                matches = [
                    item for item in (docs.get("documents") or [])
                    if item.get("relative_path") == relative_path
                ]
                if not matches:
                    raise RuntimeError(f"AIDB document not found after import for {deployment_id}")
                document_id = int(matches[0]["id"])
                self._aidb_request(
                    "/vector/index",
                    method="POST",
                    payload={
                        "items": [
                            {
                                "document_id": document_id,
                                "chunk_id": "summary",
                                "content": content,
                                "metadata": metadata,
                            }
                        ]
                    },
                )
                now = self._timestamp()
                self.conn.execute(
                    """
                    INSERT INTO deployment_semantic_index (deployment_id, document_id, content_hash, indexed_at, last_error)
                    VALUES (?, ?, ?, ?, NULL)
                    ON CONFLICT(deployment_id) DO UPDATE SET
                        document_id = excluded.document_id,
                        content_hash = excluded.content_hash,
                        indexed_at = excluded.indexed_at,
                        last_error = NULL
                    """,
                    (deployment_id, document_id, content_hash, now),
                )
                self.conn.commit()
                return {"status": "indexed", "deployment_id": deployment_id, "document_id": document_id, "indexed_at": now}
            except Exception as exc:
                self.conn.execute(
                    """
                    INSERT INTO deployment_semantic_index (deployment_id, document_id, content_hash, indexed_at, last_error)
                    VALUES (?, NULL, ?, NULL, ?)
                    ON CONFLICT(deployment_id) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        indexed_at = NULL,
                        last_error = excluded.last_error
                    """,
                    (deployment_id, content_hash, str(exc)),
                )
                self.conn.commit()
                logger.warning("Deployment semantic sync failed for %s: %s", deployment_id, exc)
                return {"status": "error", "deployment_id": deployment_id, "error": str(exc)}

    def sync_recent_deployments(self, limit: int = 10) -> Dict[str, Any]:
        deployments = self.get_recent_deployments(limit=limit)
        results = [self.sync_deployment_to_semantic_index(item["deployment_id"]) for item in deployments]
        return {
            "synced": sum(1 for item in results if item.get("status") in {"indexed", "unchanged"}),
            "failed": [item for item in results if item.get("status") == "error"],
            "results": results,
        }

    def search_deployments_semantic(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        try:
            data = self._aidb_request(
                "/vector/search",
                method="POST",
                payload={
                    "collection": DEPLOYMENT_SEMANTIC_COLLECTION,
                    "project": DEPLOYMENT_SEMANTIC_PROJECT,
                    "query": query,
                    "limit": max(limit + offset, limit),
                },
            )
        except Exception as exc:
            logger.warning("Semantic deployment search failed: %s", exc)
            return []

        results = []
        for item in (data.get("results") or [])[offset:offset + limit]:
            metadata = item.get("metadata") or {}
            deployment_id = metadata.get("deployment_id")
            if not deployment_id:
                relative_path = item.get("relative_path") or ""
                if relative_path.startswith("deployments/") and relative_path.endswith(".md"):
                    deployment_id = relative_path[len("deployments/"):-3]
            if not deployment_id:
                continue
            summary = self.get_deployment_summary(str(deployment_id)) or {}
            snippet = str(item.get("content") or "")
            if len(snippet) > 220:
                snippet = f"{snippet[:217]}..."
            results.append({
                "id": item.get("id"),
                "deployment_id": str(deployment_id),
                "event_type": "semantic",
                "message": summary.get("command") or item.get("title") or f"Deployment {deployment_id}",
                "timestamp": summary.get("started_at"),
                "progress": summary.get("progress"),
                "metadata": metadata,
                "relevance_score": item.get("score"),
                "distance": item.get("distance"),
                "snippet": snippet,
                "source": "semantic",
            })
        return results

    def search_deployments_hybrid(self, query: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        semantic = self.search_deployments_semantic(query, limit=limit, offset=offset)
        keyword = self.search_deployments(query, limit=limit, offset=offset)
        combined: List[Dict] = []
        seen: set[Tuple[str, str, str]] = set()
        for item in semantic + keyword:
            key = (
                str(item.get("deployment_id") or ""),
                str(item.get("event_type") or ""),
                str(item.get("message") or item.get("snippet") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            combined.append(item)
            if len(combined) >= limit:
                break
        return combined

    def get_deployment_search_status(self, recent_limit: int = 8) -> Dict[str, Any]:
        """Summarize deployment semantic indexing health for operators."""
        totals = self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                SUM(CASE WHEN indexed_at IS NOT NULL THEN 1 ELSE 0 END) AS indexed_rows,
                SUM(CASE WHEN last_error IS NOT NULL THEN 1 ELSE 0 END) AS error_rows
            FROM deployment_semantic_index
            """
        ).fetchone()
        recent = self.conn.execute(
            """
            SELECT
                d.deployment_id,
                d.command,
                d.status,
                d.started_at,
                d.progress,
                s.document_id,
                s.indexed_at,
                s.last_error
            FROM deployments d
            LEFT JOIN deployment_semantic_index s ON s.deployment_id = d.deployment_id
            ORDER BY d.started_at DESC
            LIMIT ?
            """,
            (recent_limit,),
        ).fetchall()

        items = []
        indexed_recent = 0
        error_recent = 0
        pending_recent = 0
        for row in recent:
            if row["last_error"]:
                semantic_state = "error"
                error_recent += 1
            elif row["indexed_at"]:
                semantic_state = "indexed"
                indexed_recent += 1
            else:
                semantic_state = "pending"
                pending_recent += 1
            items.append({
                "deployment_id": row["deployment_id"],
                "command": row["command"],
                "status": row["status"],
                "started_at": row["started_at"],
                "progress": row["progress"],
                "semantic_state": semantic_state,
                "document_id": row["document_id"],
                "indexed_at": row["indexed_at"],
                "last_error": row["last_error"],
            })

        latest_error = next((item for item in items if item["last_error"]), None)
        total_recent = len(items)
        return {
            "project": DEPLOYMENT_SEMANTIC_PROJECT,
            "collection": DEPLOYMENT_SEMANTIC_COLLECTION,
            "summary": {
                "tracked_deployments": self.count_deployments(),
                "indexed_total": int(totals["indexed_rows"] or 0),
                "error_total": int(totals["error_rows"] or 0),
                "pending_recent": pending_recent,
                "recent_coverage_pct": round((indexed_recent / total_recent) * 100, 1) if total_recent else 0.0,
            },
            "latest_error": latest_error,
            "recent": items,
        }

    @staticmethod
    def _extract_issue_tokens(text: str) -> List[str]:
        tokens = []
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", (text or "").lower()):
            if token in GRAPH_STOPWORDS:
                continue
            tokens.append(token)
        return list(dict.fromkeys(tokens))[:6]

    @staticmethod
    def _extract_service_tokens(command: str, messages: List[str]) -> List[str]:
        candidates: List[str] = []
        corpus = " ".join([command or ""] + [msg or "" for msg in messages]).lower()
        for token in re.findall(r"[a-z0-9][a-z0-9._-]{2,}", corpus):
            normalized = token.removesuffix(".service")
            if normalized in GRAPH_STOPWORDS:
                continue
            if normalized in GRAPH_SERVICE_HINTS or token.endswith(".service"):
                candidates.append(normalized)
        return list(dict.fromkeys(candidates))[:6]

    @staticmethod
    def _extract_config_paths(command: str, messages: List[str]) -> List[str]:
        corpus = "\n".join([command or ""] + [msg or "" for msg in messages])
        paths = re.findall(r"(?:[\w./-]+/)?[\w.-]+\.(?:nix|json|ya?ml|toml|service)", corpus)
        return list(dict.fromkeys(paths))[:6]

    @staticmethod
    def _match_focus(value: str, focus: Optional[str]) -> bool:
        if not focus:
            return True
        return focus.lower() in (value or "").lower()

    @staticmethod
    def _build_deployment_clusters(
        deployment_features: Dict[str, Dict[str, Any]],
        causality_edges: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        adjacency: Dict[str, set[str]] = {dep_id: set() for dep_id in deployment_features}
        for edge in causality_edges:
            if edge.get("relation") != "related_to":
                continue
            left = str(edge.get("source", "")).removeprefix("deployment:")
            right = str(edge.get("target", "")).removeprefix("deployment:")
            if left in adjacency and right in adjacency:
                adjacency[left].add(right)
                adjacency[right].add(left)

        clusters: List[Dict[str, Any]] = []
        visited: set[str] = set()
        for dep_id in sorted(adjacency):
            if dep_id in visited or not adjacency[dep_id]:
                continue
            stack = [dep_id]
            component: List[str] = []
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                stack.extend(sorted(adjacency[current] - visited))

            shared_services = set.intersection(*(deployment_features[item]["services"] for item in component))
            shared_configs = set.intersection(*(deployment_features[item]["configs"] for item in component))
            shared_issues = set.intersection(*(deployment_features[item]["issues"] for item in component))
            statuses = sorted({deployment_features[item]["status"] for item in component})
            root_score = (
                len(component) * 3
                + len(shared_issues) * 4
                + len(shared_services) * 2
                + len(shared_configs) * 2
                + (2 if "failed" in statuses else 0)
            )
            clusters.append({
                "cluster_id": f"cluster-{len(clusters) + 1}",
                "deployment_ids": sorted(component),
                "size": len(component),
                "shared_statuses": statuses,
                "shared_services": sorted(shared_services)[:4],
                "shared_configs": sorted(shared_configs)[:4],
                "shared_issues": sorted(shared_issues)[:4],
                "root_score": root_score,
            })

        return clusters

    @staticmethod
    def _build_similar_failures(
        deployment_features: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        families: Dict[Tuple[str, Tuple[str, ...]], List[str]] = {}
        for dep_id, features in deployment_features.items():
            issues = tuple(sorted(features["issues"]))[:4]
            status = str(features["status"])
            if status != "failed" and not issues:
                continue
            key = (status, issues)
            families.setdefault(key, []).append(dep_id)

        results: List[Dict[str, Any]] = []
        for index, ((status, issues), deployment_ids) in enumerate(
            sorted(families.items(), key=lambda item: (-len(item[1]), item[0][0], item[0][1]))
        ):
            if len(deployment_ids) < 2:
                continue
            results.append({
                "family_id": f"failure-family-{index + 1}",
                "status": status,
                "issue_signature": list(issues),
                "deployment_ids": sorted(deployment_ids),
                "count": len(deployment_ids),
            })
        return results

    def get_deployment_graph(
        self,
        recent_limit: int = 8,
        deployment_id: Optional[str] = None,
        view: str = "overview",
        focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a lightweight relationship graph from deployment summaries and events."""
        if deployment_id:
            summary = self.get_deployment_summary(deployment_id)
            deployments = [summary] if summary else []
        else:
            deployments = [self.get_deployment_summary(item["deployment_id"]) for item in self.get_recent_deployments(limit=recent_limit)]
            deployments = [item for item in deployments if item]

        normalized_view = (view or "overview").strip().lower()
        if normalized_view not in {"overview", "issues", "services", "configs", "causality"}:
            normalized_view = "overview"

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_nodes: set[str] = set()
        seen_edges: set[Tuple[str, str, str]] = set()
        relationship_counts: Dict[str, int] = {}
        focus_matches = 0
        deployment_features: Dict[str, Dict[str, Any]] = {}

        def add_node(node_id: str, node_type: str, label: str, **extra: Any) -> None:
            if node_id in seen_nodes:
                return
            seen_nodes.add(node_id)
            nodes.append({"id": node_id, "type": node_type, "label": label, **extra})

        def add_edge(source: str, target: str, relation: str, **extra: Any) -> None:
            nonlocal focus_matches
            key = (source, target, relation)
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append({"source": source, "target": target, "relation": relation, **extra})
            relationship_counts[relation] = relationship_counts.get(relation, 0) + 1
            if focus and (
                self._match_focus(source, focus)
                or self._match_focus(target, focus)
                or self._match_focus(relation, focus)
            ):
                focus_matches += 1

        for summary in deployments:
            dep_id = str(summary["deployment_id"])
            dep_node = f"deployment:{dep_id}"
            add_node(dep_node, "deployment", dep_id, status=summary.get("status"), progress=summary.get("progress"))

            command = str(summary.get("command") or "").strip()
            if command:
                cmd_node = f"command:{command}"
                add_node(cmd_node, "command", command)
                add_edge(dep_node, cmd_node, "executed")

            status = str(summary.get("status") or "unknown")
            status_node = f"status:{status}"
            add_node(status_node, "status", status)
            add_edge(dep_node, status_node, "resulted_in")

            timeline_rows = self.conn.execute(
                """
                SELECT event_type, message, timestamp, progress, metadata
                FROM deployment_events
                WHERE deployment_id = ?
                ORDER BY timestamp ASC
                """,
                (dep_id,),
            ).fetchall()
            timeline = [dict(row) for row in timeline_rows]
            messages = [str(event.get("message") or "") for event in timeline]
            issue_counts: Dict[str, int] = {}
            for event in timeline:
                event_type = str(event.get("event_type") or "event")
                event_node = f"event:{event_type}"
                add_node(event_node, "event", event_type)
                if normalized_view in {"overview", "issues"}:
                    add_edge(dep_node, event_node, "emitted")
                if event_type in {"failed", "rollback", "progress", "log"}:
                    for token in self._extract_issue_tokens(str(event.get("message") or "")):
                        issue_counts[token] = issue_counts.get(token, 0) + 1

            issue_tokens = set(sorted(issue_counts.keys()))
            for token, count in sorted(issue_counts.items(), key=lambda item: (-item[1], item[0]))[:4]:
                issue_node = f"issue:{token}"
                add_node(issue_node, "issue", token, occurrences=count)
                if normalized_view in {"overview", "issues"}:
                    add_edge(dep_node, issue_node, "signals")

            service_tokens = set(self._extract_service_tokens(command, messages))
            for service in service_tokens:
                service_node = f"service:{service}"
                add_node(service_node, "service", service)
                if normalized_view in {"overview", "services"}:
                    add_edge(dep_node, service_node, "touches_service")

            config_tokens = set(self._extract_config_paths(command, messages))
            for config_path in config_tokens:
                config_node = f"config:{config_path}"
                add_node(config_node, "config", config_path)
                if normalized_view in {"overview", "configs"}:
                    add_edge(dep_node, config_node, "references_config")

            deployment_features[dep_id] = {
                "status": status,
                "issues": issue_tokens,
                "services": service_tokens,
                "configs": config_tokens,
            }

        deployment_ids = sorted(deployment_features.keys())
        if len(deployment_ids) >= 2:
            for index, left_id in enumerate(deployment_ids):
                for right_id in deployment_ids[index + 1:]:
                    left = deployment_features[left_id]
                    right = deployment_features[right_id]
                    reasons: List[str] = []
                    shared_services = sorted(left["services"] & right["services"])
                    shared_configs = sorted(left["configs"] & right["configs"])
                    shared_issues = sorted(left["issues"] & right["issues"])
                    if left["status"] == right["status"] and left["status"] in {"failed", "success", "running"}:
                        reasons.append(f"shared_status:{left['status']}")
                    if shared_services:
                        reasons.append(f"shared_services:{','.join(shared_services[:3])}")
                    if shared_configs:
                        reasons.append(f"shared_configs:{','.join(shared_configs[:2])}")
                    if shared_issues:
                        reasons.append(f"shared_issues:{','.join(shared_issues[:3])}")
                    if not reasons:
                        continue
                    left_node = f"deployment:{left_id}"
                    right_node = f"deployment:{right_id}"
                    if normalized_view in {"overview", "causality"}:
                        add_edge(
                            left_node,
                            right_node,
                            "related_to",
                            weight=len(reasons),
                            reasons=reasons,
                        )

        causality_edges = [edge for edge in edges if edge.get("relation") == "related_to"]
        clusters = self._build_deployment_clusters(deployment_features, causality_edges)
        similar_failures = self._build_similar_failures(deployment_features)

        if focus:
            filtered_edges = [
                edge for edge in edges
                if self._match_focus(edge["source"], focus)
                or self._match_focus(edge["target"], focus)
                or self._match_focus(edge["relation"], focus)
            ]
            node_ids = {edge["source"] for edge in filtered_edges} | {edge["target"] for edge in filtered_edges}
            filtered_nodes = [node for node in nodes if node["id"] in node_ids]
        else:
            filtered_nodes = nodes
            filtered_edges = edges

        if focus:
            filtered_clusters = [
                cluster for cluster in clusters
                if any(self._match_focus(dep_id, focus) for dep_id in cluster["deployment_ids"])
                or any(self._match_focus(value, focus) for value in cluster["shared_services"])
                or any(self._match_focus(value, focus) for value in cluster["shared_configs"])
                or any(self._match_focus(value, focus) for value in cluster["shared_issues"])
                or any(self._match_focus(value, focus) for value in cluster["shared_statuses"])
            ]
        else:
            filtered_clusters = clusters

        if focus:
            filtered_failures = [
                item for item in similar_failures
                if any(self._match_focus(dep_id, focus) for dep_id in item["deployment_ids"])
                or any(self._match_focus(issue, focus) for issue in item["issue_signature"])
                or self._match_focus(item["status"], focus)
            ]
        else:
            filtered_failures = similar_failures

        root_cluster = None
        if filtered_clusters:
            root_cluster = max(
                filtered_clusters,
                key=lambda item: (
                    int(item.get("root_score", 0)),
                    int(item.get("size", 0)),
                    item.get("cluster_id", ""),
                ),
            )

        top_relationships = [
            {"relation": relation, "count": count}
            for relation, count in sorted(relationship_counts.items(), key=lambda item: (-item[1], item[0]))
        ][:6]

        return {
            "status": "ready" if filtered_nodes else "empty",
            "deployment_scope": deployment_id or "recent",
            "view": normalized_view,
            "focus": focus or "",
            "focus_matches": focus_matches if focus else len(filtered_edges),
            "node_count": len(filtered_nodes),
            "edge_count": len(filtered_edges),
            "top_relationships": top_relationships,
            "cluster_count": len(filtered_clusters),
            "clusters": filtered_clusters,
            "root_cluster": root_cluster,
            "similar_failures": filtered_failures[:6],
            "nodes": filtered_nodes,
            "edges": filtered_edges,
        }

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

        summary_row = cursor.fetchone()
        if not summary_row:
            return None

        # Get event counts by type (not full events)
        event_counts = {}
        cursor = self.conn.execute("""
            SELECT event_type, COUNT(*) as count
            FROM deployment_events
            WHERE deployment_id = ?
            GROUP BY event_type
        """, (deployment_id,))

        for event_row in cursor:
            event_counts[event_row["event_type"]] = event_row["count"]

        return {
            "deployment_id": summary_row["deployment_id"],
            "command": summary_row["command"],
            "user": summary_row["user"],
            "status": summary_row["status"],
            "started_at": summary_row["started_at"],
            "completed_at": summary_row["completed_at"],
            "progress": summary_row["progress"],
            "exit_code": summary_row["exit_code"],
            "duration_seconds": summary_row["duration_seconds"],
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

    def count_deployments(self, status: str = None) -> int:
        """Count tracked deployments, optionally filtered by status."""
        if status:
            cursor = self.conn.execute("""
                SELECT COUNT(*) AS total
                FROM deployments
                WHERE status = ?
            """, (status,))
        else:
            cursor = self.conn.execute("""
                SELECT COUNT(*) AS total
                FROM deployments
            """)

        row = cursor.fetchone()
        return int(row["total"]) if row and row["total"] is not None else 0

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
        def write() -> int:
            cursor = self.conn.execute("""
                INSERT INTO git_operations
                (deployment_id, operation, branch, commit_hash, files_changed)
                VALUES (?, ?, ?, ?, ?)
            """, (deployment_id, operation, branch, commit_hash,
                  json.dumps(files_changed) if files_changed else None))

            self.conn.commit()
            return cursor.lastrowid

        return self._execute_write("track_git_operation", write)

    def track_file_edit(self, deployment_id: str, file_path: str,
                       operation: str, size_before: int = None,
                       size_after: int = None) -> int:
        """Track file edit during deployment"""
        def write() -> int:
            cursor = self.conn.execute("""
                INSERT INTO file_edits
                (deployment_id, file_path, operation, size_before, size_after)
                VALUES (?, ?, ?, ?, ?)
            """, (deployment_id, file_path, operation, size_before, size_after))

            self.conn.commit()
            return cursor.lastrowid

        return self._execute_write("track_file_edit", write)

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
