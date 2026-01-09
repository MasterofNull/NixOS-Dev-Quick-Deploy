#!/usr/bin/env python3
"""
Issue Tracking System for Production Errors

Tracks errors, patterns, and system issues to inform improvements
and prevent recurrence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import traceback
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

import asyncpg
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram

# Prometheus metrics
ISSUES_CREATED = Counter(
    'aidb_issues_created_total',
    'Total issues created',
    ['severity', 'category', 'component']
)

ISSUES_RESOLVED = Counter(
    'aidb_issues_resolved_total',
    'Total issues resolved',
    ['severity', 'category']
)

ISSUE_RESOLUTION_TIME = Histogram(
    'aidb_issue_resolution_seconds',
    'Time to resolve issues',
    ['severity', 'category']
)

ACTIVE_ISSUES = Gauge(
    'aidb_active_issues',
    'Number of active issues',
    ['severity', 'category']
)


class IssueSeverity(str, Enum):
    """Issue severity levels"""
    CRITICAL = "critical"      # System down, data loss
    HIGH = "high"              # Major functionality broken
    MEDIUM = "medium"          # Minor functionality broken
    LOW = "low"                # Cosmetic, documentation
    INFO = "info"              # Informational, no action needed


class IssueCategory(str, Enum):
    """Issue categories"""
    SECURITY = "security"           # Security vulnerabilities
    PERFORMANCE = "performance"     # Performance degradation
    RELIABILITY = "reliability"     # Crashes, timeouts, errors
    DATA_INTEGRITY = "data_integrity"  # Data corruption, inconsistency
    CONFIGURATION = "configuration"  # Configuration errors
    DEPLOYMENT = "deployment"       # Deployment failures
    INTEGRATION = "integration"     # Integration failures
    VALIDATION = "validation"       # Input validation failures
    MONITORING = "monitoring"       # Monitoring/alerting issues
    OTHER = "other"                 # Uncategorized


class IssueStatus(str, Enum):
    """Issue status"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"
    DUPLICATE = "duplicate"


class Issue(BaseModel):
    """Issue model"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    severity: IssueSeverity
    category: IssueCategory
    component: str = Field(..., min_length=1, max_length=100)
    status: IssueStatus = IssueStatus.OPEN

    # Error details
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    error_hash: Optional[str] = None  # Hash for deduplication

    # Context
    context: Dict[str, Any] = Field(default_factory=dict)
    affected_users: int = 0
    occurrence_count: int = 1
    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Resolution
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    # Related
    related_issues: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # System improvement suggestions
    suggested_fixes: List[str] = Field(default_factory=list)
    system_changes_needed: List[str] = Field(default_factory=list)


class IssueTracker:
    """Track and manage production issues"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self._issue_cache: Dict[str, Issue] = {}
        self._error_hash_to_issue: Dict[str, str] = {}  # error_hash -> issue_id
        self._pattern_analysis: Dict[str, List[str]] = defaultdict(list)

    async def initialize_schema(self):
        """Create issues table if not exists"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS issues (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    component TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    error_type TEXT,
                    stack_trace TEXT,
                    error_hash TEXT,
                    context JSONB,
                    affected_users INTEGER DEFAULT 0,
                    occurrence_count INTEGER DEFAULT 1,
                    first_seen TIMESTAMPTZ NOT NULL,
                    last_seen TIMESTAMPTZ NOT NULL,
                    resolution TEXT,
                    resolved_at TIMESTAMPTZ,
                    resolved_by TEXT,
                    related_issues JSONB,
                    tags JSONB,
                    suggested_fixes JSONB,
                    system_changes_needed JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
                CREATE INDEX IF NOT EXISTS idx_issues_category ON issues(category);
                CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
                CREATE INDEX IF NOT EXISTS idx_issues_error_hash ON issues(error_hash);
                CREATE INDEX IF NOT EXISTS idx_issues_first_seen ON issues(first_seen);
                CREATE INDEX IF NOT EXISTS idx_issues_component ON issues(component);
            """)

    def _compute_error_hash(self, error_message: str, error_type: str, component: str) -> str:
        """Compute hash for error deduplication"""
        # Normalize error message (remove timestamps, IDs, etc.)
        normalized = error_message.lower()
        # Remove common variable parts
        import re
        normalized = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', normalized)
        normalized = re.sub(r'\d{2}:\d{2}:\d{2}', 'TIME', normalized)
        normalized = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'UUID', normalized)
        normalized = re.sub(r'\b\d+\b', 'NUM', normalized)

        hash_input = f"{error_type}:{component}:{normalized}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    async def record_issue(
        self,
        title: str,
        description: str,
        severity: IssueSeverity,
        category: IssueCategory,
        component: str,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        stack_trace: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        suggested_fixes: Optional[List[str]] = None,
        system_changes_needed: Optional[List[str]] = None
    ) -> Issue:
        """
        Record a new issue or update existing if duplicate

        Returns the created or updated issue
        """
        # Compute error hash for deduplication
        error_hash = None
        if error_message and error_type:
            error_hash = self._compute_error_hash(error_message, error_type, component)

            # Check if we've seen this error before
            if error_hash in self._error_hash_to_issue:
                existing_issue_id = self._error_hash_to_issue[error_hash]
                return await self._update_duplicate_issue(existing_issue_id)

        # Create new issue
        issue = Issue(
            title=title,
            description=description,
            severity=severity,
            category=category,
            component=component,
            error_message=error_message,
            error_type=error_type,
            stack_trace=stack_trace,
            error_hash=error_hash,
            context=context or {},
            tags=tags or [],
            suggested_fixes=suggested_fixes or [],
            system_changes_needed=system_changes_needed or []
        )

        # Save to database
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO issues (
                    id, title, description, severity, category, component,
                    status, error_message, error_type, stack_trace, error_hash,
                    context, affected_users, occurrence_count, first_seen, last_seen,
                    related_issues, tags, suggested_fixes, system_changes_needed
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
                )
            """,
                issue.id, issue.title, issue.description, issue.severity.value,
                issue.category.value, issue.component, issue.status.value,
                issue.error_message, issue.error_type, issue.stack_trace, issue.error_hash,
                json.dumps(issue.context), issue.affected_users, issue.occurrence_count,
                issue.first_seen, issue.last_seen,
                json.dumps(issue.related_issues), json.dumps(issue.tags),
                json.dumps(issue.suggested_fixes), json.dumps(issue.system_changes_needed)
            )

        # Update caches
        self._issue_cache[issue.id] = issue
        if error_hash:
            self._error_hash_to_issue[error_hash] = issue.id

        # Update metrics
        ISSUES_CREATED.labels(
            severity=severity.value,
            category=category.value,
            component=component
        ).inc()

        ACTIVE_ISSUES.labels(
            severity=severity.value,
            category=category.value
        ).inc()

        return issue

    async def _update_duplicate_issue(self, issue_id: str) -> Issue:
        """Update occurrence count for duplicate issue"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE issues
                SET occurrence_count = occurrence_count + 1,
                    last_seen = NOW(),
                    updated_at = NOW()
                WHERE id = $1
            """, issue_id)

            # Fetch updated issue
            row = await conn.fetchrow("SELECT * FROM issues WHERE id = $1", issue_id)
            issue = self._row_to_issue(row)
            self._issue_cache[issue_id] = issue
            return issue

    async def record_exception(
        self,
        exc: Exception,
        component: str,
        severity: IssueSeverity = IssueSeverity.HIGH,
        category: IssueCategory = IssueCategory.RELIABILITY,
        context: Optional[Dict[str, Any]] = None,
        suggested_fixes: Optional[List[str]] = None
    ) -> Issue:
        """Convenience method to record an exception as an issue"""
        error_type = type(exc).__name__
        error_message = str(exc)
        stack_trace = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        title = f"{error_type} in {component}"
        description = f"Exception occurred in {component}: {error_message}"

        return await self.record_issue(
            title=title,
            description=description,
            severity=severity,
            category=category,
            component=component,
            error_message=error_message,
            error_type=error_type,
            stack_trace=stack_trace,
            context=context,
            suggested_fixes=suggested_fixes
        )

    async def resolve_issue(
        self,
        issue_id: str,
        resolution: str,
        resolved_by: str = "system"
    ):
        """Mark issue as resolved"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE issues
                SET status = $1,
                    resolution = $2,
                    resolved_at = NOW(),
                    resolved_by = $3,
                    updated_at = NOW()
                WHERE id = $4
                RETURNING *
            """, IssueStatus.RESOLVED.value, resolution, resolved_by, issue_id)

            if row:
                issue = self._row_to_issue(row)

                # Update metrics
                ISSUES_RESOLVED.labels(
                    severity=issue.severity.value,
                    category=issue.category.value
                ).inc()

                ACTIVE_ISSUES.labels(
                    severity=issue.severity.value,
                    category=issue.category.value
                ).dec()

                # Calculate resolution time
                resolution_time = (issue.resolved_at - issue.first_seen).total_seconds()
                ISSUE_RESOLUTION_TIME.labels(
                    severity=issue.severity.value,
                    category=issue.category.value
                ).observe(resolution_time)

    async def get_issue(self, issue_id: str) -> Optional[Issue]:
        """Get issue by ID"""
        if issue_id in self._issue_cache:
            return self._issue_cache[issue_id]

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM issues WHERE id = $1", issue_id)
            if row:
                issue = self._row_to_issue(row)
                self._issue_cache[issue_id] = issue
                return issue
        return None

    async def list_issues(
        self,
        status: Optional[IssueStatus] = None,
        severity: Optional[IssueSeverity] = None,
        category: Optional[IssueCategory] = None,
        component: Optional[str] = None,
        limit: int = 100
    ) -> List[Issue]:
        """List issues with optional filters"""
        query = "SELECT * FROM issues WHERE 1=1"
        params = []
        param_idx = 1

        if status:
            query += f" AND status = ${param_idx}"
            params.append(status.value)
            param_idx += 1

        if severity:
            query += f" AND severity = ${param_idx}"
            params.append(severity.value)
            param_idx += 1

        if category:
            query += f" AND category = ${param_idx}"
            params.append(category.value)
            param_idx += 1

        if component:
            query += f" AND component = ${param_idx}"
            params.append(component)
            param_idx += 1

        query += f" ORDER BY first_seen DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_issue(row) for row in rows]

    async def analyze_patterns(self) -> Dict[str, Any]:
        """Analyze issue patterns to identify systemic problems"""
        async with self.db_pool.acquire() as conn:
            # Get statistics
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_issues,
                    COUNT(*) FILTER (WHERE status = 'open') as open_issues,
                    COUNT(*) FILTER (WHERE severity = 'critical') as critical_issues,
                    COUNT(*) FILTER (WHERE severity = 'high') as high_issues,
                    SUM(occurrence_count) as total_occurrences
                FROM issues
                WHERE first_seen > NOW() - INTERVAL '7 days'
            """)

            # Most common errors
            common_errors = await conn.fetch("""
                SELECT error_type, component, COUNT(*) as count, SUM(occurrence_count) as occurrences
                FROM issues
                WHERE error_type IS NOT NULL
                    AND first_seen > NOW() - INTERVAL '7 days'
                GROUP BY error_type, component
                ORDER BY occurrences DESC
                LIMIT 10
            """)

            # Most affected components
            affected_components = await conn.fetch("""
                SELECT component, COUNT(*) as issue_count, SUM(occurrence_count) as occurrences
                FROM issues
                WHERE first_seen > NOW() - INTERVAL '7 days'
                GROUP BY component
                ORDER BY occurrences DESC
                LIMIT 10
            """)

            # Category breakdown
            category_breakdown = await conn.fetch("""
                SELECT category, COUNT(*) as count, SUM(occurrence_count) as occurrences
                FROM issues
                WHERE first_seen > NOW() - INTERVAL '7 days'
                GROUP BY category
                ORDER BY occurrences DESC
            """)

        return {
            "statistics": dict(stats),
            "common_errors": [dict(row) for row in common_errors],
            "affected_components": [dict(row) for row in affected_components],
            "category_breakdown": [dict(row) for row in category_breakdown]
        }

    async def suggest_system_improvements(self) -> List[Dict[str, Any]]:
        """Analyze issues and suggest system improvements"""
        pattern_analysis = await self.analyze_patterns()
        suggestions = []

        # Check for high occurrence patterns
        for error in pattern_analysis["common_errors"]:
            if error["occurrences"] > 10:
                suggestions.append({
                    "priority": "high",
                    "type": "error_handling",
                    "description": f"High frequency of {error['error_type']} in {error['component']}",
                    "suggestion": f"Add specific error handling for {error['error_type']} in {error['component']}",
                    "occurrences": error["occurrences"]
                })

        # Check for component issues
        for component in pattern_analysis["affected_components"]:
            if component["issue_count"] > 5:
                suggestions.append({
                    "priority": "medium",
                    "type": "component_reliability",
                    "description": f"Component {component['component']} has {component['issue_count']} different issues",
                    "suggestion": f"Review {component['component']} for reliability improvements",
                    "issue_count": component["issue_count"]
                })

        # Check category trends
        for category in pattern_analysis["category_breakdown"]:
            if category["occurrences"] > 20:
                suggestions.append({
                    "priority": "medium",
                    "type": "category_trend",
                    "description": f"High number of {category['category']} issues",
                    "suggestion": f"Implement systematic improvements for {category['category']}",
                    "occurrences": category["occurrences"]
                })

        return suggestions

    def _row_to_issue(self, row: asyncpg.Record) -> Issue:
        """Convert database row to Issue model"""
        return Issue(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            severity=IssueSeverity(row["severity"]),
            category=IssueCategory(row["category"]),
            component=row["component"],
            status=IssueStatus(row["status"]),
            error_message=row["error_message"],
            error_type=row["error_type"],
            stack_trace=row["stack_trace"],
            error_hash=row["error_hash"],
            context=json.loads(row["context"]) if row["context"] else {},
            affected_users=row["affected_users"],
            occurrence_count=row["occurrence_count"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            resolution=row["resolution"],
            resolved_at=row["resolved_at"],
            resolved_by=row["resolved_by"],
            related_issues=json.loads(row["related_issues"]) if row["related_issues"] else [],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            suggested_fixes=json.loads(row["suggested_fixes"]) if row["suggested_fixes"] else [],
            system_changes_needed=json.loads(row["system_changes_needed"]) if row["system_changes_needed"] else []
        )


async def main():
    """Example usage"""
    # Create DB pool
    db_pool = await asyncpg.create_pool(
        host="localhost",
        database="aidb",
        user="aidb",
        password="aidb_password"
    )

    tracker = IssueTracker(db_pool)
    await tracker.initialize_schema()

    # Example: Record an issue
    issue = await tracker.record_issue(
        title="P1 Integration Test Failures",
        description="Integration tests failed during P1 deployment",
        severity=IssueSeverity.HIGH,
        category=IssueCategory.INTEGRATION,
        component="p1-integration",
        error_message="Multiple integration tests failed",
        error_type="TestFailure",
        context={"deployment": "p1", "phase": "integration"},
        suggested_fixes=[
            "Review test environment configuration",
            "Check database connectivity",
            "Verify service dependencies"
        ],
        system_changes_needed=[
            "Add pre-deployment validation",
            "Improve test environment setup",
            "Add integration test monitoring"
        ]
    )

    print(f"Created issue: {issue.id}")
    print(f"Title: {issue.title}")
    print(f"Severity: {issue.severity}")

    # Analyze patterns
    patterns = await tracker.analyze_patterns()
    print("\nPattern Analysis:")
    print(json.dumps(patterns, indent=2, default=str))

    # Get suggestions
    suggestions = await tracker.suggest_system_improvements()
    print("\nSystem Improvement Suggestions:")
    for suggestion in suggestions:
        print(f"- [{suggestion['priority']}] {suggestion['description']}")
        print(f"  Suggestion: {suggestion['suggestion']}")

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
