"""
Context Memory Manager - Intelligent context lifecycle and importance scoring.

Prevents "remembers everything, remembers nothing" by managing context with:
- Importance-based retention
- Decay modeling
- Proactive compaction triggering
- Long-term memory preservation

Part of Context Rot and Recall system.
"""

import asyncio
import hashlib
import json
import logging
import math
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import httpx

logger = logging.getLogger(__name__)


class LifecycleState(Enum):
    """Context lifecycle states with aging transitions."""
    FRESH = "fresh"        # 0-1h: High relevance, full detail
    ACTIVE = "active"      # 1-8h: Medium relevance, detail preserved
    AGING = "aging"        # 8-24h: Declining relevance, summarization candidate
    STALE = "stale"        # 1-7d: Low relevance, compact or archive
    ARCHIVED = "archived"  # 7d+: Long-term storage, recall on demand


class ContextType(Enum):
    """Types of context for categorization."""
    CONVERSATION = "conversation"
    FILE_READ = "file_read"
    CODE_CHANGE = "code_change"
    ERROR = "error"
    DECISION = "decision"
    TASK = "task"
    LEARNING = "learning"


@dataclass
class Context:
    """
    Context memory unit with metadata and importance tracking.

    Attributes:
        id: Unique context identifier
        created_at: Creation timestamp
        last_accessed: Last access timestamp
        lifecycle_state: Current lifecycle state
        importance_score: Calculated importance (0.0-1.0)
        reference_count: Number of times referenced
        context_type: Type of context
        content: Full context content
        summary: Generated summary (for compaction)
        session_id: Associated session
        task_id: Associated task
        tags: Categorization tags
        related_files: Associated file paths
        related_commits: Associated commit hashes
        related_context_ids: Related context IDs
        is_pinned: Never auto-prune flag
        is_archived: Archived flag
        is_error_resolution: Error resolution flag
        token_count: Estimated token count
    """
    id: str
    created_at: datetime
    last_accessed: datetime
    lifecycle_state: LifecycleState
    importance_score: float
    reference_count: int
    context_type: ContextType
    content: str
    summary: Optional[str] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    related_commits: List[str] = field(default_factory=list)
    related_context_ids: List[str] = field(default_factory=list)
    is_pinned: bool = False
    is_archived: bool = False
    is_error_resolution: bool = False
    token_count: int = 0

    def to_dict(self) -> dict:
        """Convert context to dictionary for storage."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "lifecycle_state": self.lifecycle_state.value,
            "importance_score": self.importance_score,
            "reference_count": self.reference_count,
            "context_type": self.context_type.value,
            "content": self.content,
            "summary": self.summary,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "tags": json.dumps(self.tags),
            "related_files": json.dumps(self.related_files),
            "related_commits": json.dumps(self.related_commits),
            "related_context_ids": json.dumps(self.related_context_ids),
            "is_pinned": self.is_pinned,
            "is_archived": self.is_archived,
            "is_error_resolution": self.is_error_resolution,
            "token_count": self.token_count,
        }


class ContextMemoryManager:
    """
    Context memory lifecycle and importance management system.

    Implements intelligent context retention, decay modeling, and
    proactive compaction triggering.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        window_limit: int = 200000,
        decay_constant: float = 0.1,
    ):
        """
        Initialize context memory manager.

        Args:
            db_path: Path to SQLite database
            window_limit: Maximum token window size
            decay_constant: Decay rate for recency scoring
        """
        if db_path is None:
            data_dir = Path(os.path.expanduser(os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack")))
            db_path = data_dir / "context_memory.db"

        self.db_path = db_path
        self.window_limit = window_limit
        self.decay_constant = decay_constant

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"ContextMemoryManager initialized: db={db_path}, window={window_limit}")

    def _init_database(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_memory (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL,
                    last_accessed TIMESTAMP NOT NULL,
                    lifecycle_state TEXT NOT NULL,
                    importance_score REAL NOT NULL,
                    reference_count INTEGER DEFAULT 0,

                    context_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,

                    session_id TEXT,
                    task_id TEXT,
                    tags TEXT,

                    related_files TEXT,
                    related_commits TEXT,
                    related_context_ids TEXT,

                    is_pinned BOOLEAN DEFAULT FALSE,
                    is_archived BOOLEAN DEFAULT FALSE,
                    is_error_resolution BOOLEAN DEFAULT FALSE,
                    token_count INTEGER DEFAULT 0
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_lifecycle ON context_memory(lifecycle_state)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_importance ON context_memory(importance_score DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_created ON context_memory(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_session ON context_memory(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_task ON context_memory(task_id)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS context_references (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id TEXT NOT NULL,
                    referenced_at TIMESTAMP NOT NULL,
                    reference_type TEXT NOT NULL,
                    session_id TEXT,
                    FOREIGN KEY (context_id) REFERENCES context_memory(id)
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_ref_context ON context_references(context_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ref_time ON context_references(referenced_at DESC)")

            conn.commit()

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough estimate: ~4 characters per token
        return len(text) // 4

    def _calculate_importance_score(self, context: Context) -> float:
        """
        Calculate importance score (0.0-1.0) for context.

        Factors:
        - Recency (0.25): Exponential decay
        - Reference count (0.20): Normalized usage
        - Code changes (0.25): Binary indicator
        - User interaction (0.15): Explicit engagement
        - Semantic centrality (0.10): Connection to other context
        - Error resolution (0.05): Problem-solving value
        """
        now = datetime.utcnow()
        age_hours = (now - context.created_at).total_seconds() / 3600

        # Recency score with exponential decay
        recency_score = math.exp(-self.decay_constant * age_hours)

        # Reference count score (normalized to 10 references)
        reference_score = min(1.0, context.reference_count / 10.0)

        # Code changes indicator
        code_score = 1.0 if (
            context.context_type == ContextType.CODE_CHANGE or
            len(context.related_commits) > 0
        ) else 0.0

        # User interaction score (based on context type)
        user_interaction_scores = {
            ContextType.DECISION: 1.0,
            ContextType.ERROR: 0.9,
            ContextType.CODE_CHANGE: 0.8,
            ContextType.TASK: 0.7,
            ContextType.LEARNING: 0.6,
            ContextType.CONVERSATION: 0.5,
            ContextType.FILE_READ: 0.3,
        }
        user_interaction_score = user_interaction_scores.get(context.context_type, 0.5)

        # Semantic centrality (number of related contexts)
        semantic_centrality = min(1.0, len(context.related_context_ids) / 5.0)

        # Error resolution indicator
        error_resolution_score = 1.0 if context.is_error_resolution else 0.0

        # Weighted combination
        importance_score = (
            0.25 * recency_score +
            0.20 * reference_score +
            0.25 * code_score +
            0.15 * user_interaction_score +
            0.10 * semantic_centrality +
            0.05 * error_resolution_score
        )

        return min(1.0, max(0.0, importance_score))

    def _update_lifecycle_state(self, context: Context) -> LifecycleState:
        """
        Update lifecycle state based on age.

        0-1h: FRESH
        1-8h: ACTIVE
        8-24h: AGING
        1-7d: STALE
        7d+: ARCHIVED
        """
        now = datetime.utcnow()
        age = now - context.created_at

        if age < timedelta(hours=1):
            return LifecycleState.FRESH
        elif age < timedelta(hours=8):
            return LifecycleState.ACTIVE
        elif age < timedelta(hours=24):
            return LifecycleState.AGING
        elif age < timedelta(days=7):
            return LifecycleState.STALE
        else:
            return LifecycleState.ARCHIVED

    async def store_context(
        self,
        content: str,
        context_type: ContextType,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        related_files: Optional[List[str]] = None,
        related_commits: Optional[List[str]] = None,
        is_pinned: bool = False,
        is_error_resolution: bool = False,
    ) -> Context:
        """
        Store new context with metadata.

        Args:
            content: Context content
            context_type: Type of context
            session_id: Associated session ID
            task_id: Associated task ID
            tags: Categorization tags
            related_files: Associated file paths
            related_commits: Associated commit hashes
            is_pinned: Pin context (never auto-prune)
            is_error_resolution: Mark as error resolution

        Returns:
            Created Context object
        """
        now = datetime.utcnow()

        # Generate context ID
        context_id = hashlib.sha256(f"{content}{now.isoformat()}".encode()).hexdigest()[:16]

        # Create context object
        context = Context(
            id=context_id,
            created_at=now,
            last_accessed=now,
            lifecycle_state=LifecycleState.FRESH,
            importance_score=0.0,  # Will be calculated
            reference_count=0,
            context_type=context_type,
            content=content,
            session_id=session_id,
            task_id=task_id,
            tags=tags or [],
            related_files=related_files or [],
            related_commits=related_commits or [],
            is_pinned=is_pinned,
            is_error_resolution=is_error_resolution,
            token_count=self._estimate_tokens(content),
        )

        # Calculate initial importance score
        context.importance_score = self._calculate_importance_score(context)

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO context_memory VALUES (
                    :id, :created_at, :last_accessed, :lifecycle_state, :importance_score,
                    :reference_count, :context_type, :content, :summary, :session_id,
                    :task_id, :tags, :related_files, :related_commits, :related_context_ids,
                    :is_pinned, :is_archived, :is_error_resolution, :token_count
                )
            """, context.to_dict())
            conn.commit()

        logger.debug(f"Stored context {context_id}: type={context_type.value}, importance={context.importance_score:.2f}")

        return context

    def get_total_token_count(self) -> int:
        """Get total token count of all non-archived contexts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT SUM(token_count)
                FROM context_memory
                WHERE is_archived = FALSE
            """)
            result = cursor.fetchone()[0]
            return result if result is not None else 0

    def get_stale_context_ratio(self) -> float:
        """Get ratio of stale contexts to total contexts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE lifecycle_state IN ('stale', 'aging')) as stale_count,
                    COUNT(*) as total_count
                FROM context_memory
                WHERE is_archived = FALSE
            """)
            row = cursor.fetchone()
            if row and row[1] > 0:
                return row[0] / row[1]
            return 0.0

    def should_trigger_compaction(self) -> Tuple[bool, str]:
        """
        Check if proactive compaction should be triggered.

        Returns:
            Tuple of (should_trigger, reason)
        """
        current_tokens = self.get_total_token_count()

        # Trigger at 75% threshold
        if current_tokens > (self.window_limit * 0.75):
            return True, f"Context at {current_tokens/1000:.1f}k tokens (75% threshold)"

        # Trigger if stale context ratio high
        stale_ratio = self.get_stale_context_ratio()
        if stale_ratio > 0.40:
            return True, f"Stale context ratio {stale_ratio:.1%} (>40%)"

        return False, "No compaction trigger met"

    async def update_all_lifecycle_states(self) -> int:
        """
        Update lifecycle states for all contexts based on age.

        Returns:
            Number of contexts updated
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get all non-archived contexts
            cursor = conn.execute("""
                SELECT id, created_at, lifecycle_state
                FROM context_memory
                WHERE is_archived = FALSE
            """)

            updated = 0
            for row in cursor.fetchall():
                context_id, created_at_str, current_state = row
                created_at = datetime.fromisoformat(created_at_str)

                # Create minimal context for state calculation
                temp_context = Context(
                    id=context_id,
                    created_at=created_at,
                    last_accessed=datetime.utcnow(),
                    lifecycle_state=LifecycleState(current_state),
                    importance_score=0.0,
                    reference_count=0,
                    context_type=ContextType.CONVERSATION,
                    content="",
                )

                new_state = self._update_lifecycle_state(temp_context)

                if new_state != temp_context.lifecycle_state:
                    conn.execute("""
                        UPDATE context_memory
                        SET lifecycle_state = ?
                        WHERE id = ?
                    """, (new_state.value, context_id))
                    updated += 1

            conn.commit()

        logger.info(f"Updated lifecycle states for {updated} contexts")
        return updated

    def get_compaction_plan(self) -> Dict[str, List[Dict]]:
        """
        Generate compaction plan with contexts to keep, summarize, or archive.

        Returns:
            Dict with keys: keep_full, summarize, archive
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT *
                FROM context_memory
                WHERE is_archived = FALSE
                ORDER BY importance_score DESC
            """)

            rows = cursor.fetchall()

        target_tokens = self.window_limit * 0.70  # 70% headroom
        budget_remaining = target_tokens

        keep_full = []
        summarize = []
        archive = []

        for row in rows:
            ctx_dict = dict(row)
            importance = ctx_dict["importance_score"]
            lifecycle = ctx_dict["lifecycle_state"]
            is_pinned = ctx_dict["is_pinned"]
            token_count = ctx_dict["token_count"]

            # Always keep pinned
            if is_pinned:
                keep_full.append(ctx_dict)
                budget_remaining -= token_count
                continue

            # Keep high-importance fresh/active
            if importance >= 0.8 and lifecycle in ("fresh", "active"):
                keep_full.append(ctx_dict)
                budget_remaining -= token_count
                continue

            # Summarize medium-importance aging
            if importance >= 0.5 and lifecycle == "aging":
                summarize.append(ctx_dict)
                budget_remaining -= (token_count * 0.2)  # 80% reduction
                continue

            # Archive low-importance or stale
            if importance < 0.5 or lifecycle == "stale":
                archive.append(ctx_dict)
                continue

            # If budget exhausted, archive remaining
            if budget_remaining <= 0:
                archive.append(ctx_dict)

        return {
            "keep_full": keep_full,
            "summarize": summarize,
            "archive": archive,
            "stats": {
                "keep_full_count": len(keep_full),
                "summarize_count": len(summarize),
                "archive_count": len(archive),
                "budget_remaining": budget_remaining,
            }
        }

    def get_stats(self) -> dict:
        """Get context memory statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Total counts
            cursor = conn.execute("SELECT COUNT(*) FROM context_memory")
            total_count = cursor.fetchone()[0]

            # Lifecycle distribution
            cursor = conn.execute("""
                SELECT lifecycle_state, COUNT(*) as count
                FROM context_memory
                GROUP BY lifecycle_state
            """)
            lifecycle_dist = {row["lifecycle_state"]: row["count"] for row in cursor.fetchall()}

            # Average importance by lifecycle
            cursor = conn.execute("""
                SELECT lifecycle_state, AVG(importance_score) as avg_importance
                FROM context_memory
                GROUP BY lifecycle_state
            """)
            avg_importance = {row["lifecycle_state"]: row["avg_importance"] for row in cursor.fetchall()}

            # Total tokens
            total_tokens = self.get_total_token_count()

            # Stale ratio
            stale_ratio = self.get_stale_context_ratio()

        return {
            "total_contexts": total_count,
            "total_tokens": total_tokens,
            "window_limit": self.window_limit,
            "window_usage_percent": (total_tokens / self.window_limit) * 100,
            "stale_ratio": stale_ratio,
            "lifecycle_distribution": lifecycle_dist,
            "average_importance_by_lifecycle": avg_importance,
        }
