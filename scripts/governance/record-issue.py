#!/usr/bin/env python3
"""
CLI tool to record issues in the issue tracking database.

Usage:
    ./record-issue.py "Issue title" "Issue description" \
        --severity high \
        --category integration \
        --component p1-integration \
        --error "Error message" \
        --fix "Suggested fix 1" --fix "Suggested fix 2"
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

AIDB_MODULE_DIR = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "aidb"
sys.path.insert(0, str(AIDB_MODULE_DIR))

SEVERITY_CHOICES = ["critical", "high", "medium", "low", "info"]
CATEGORY_CHOICES = [
    "security",
    "performance",
    "reliability",
    "data_integrity",
    "configuration",
    "deployment",
    "integration",
    "validation",
    "monitoring",
    "other",
]

SCHEMA_SQL = """
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
""".strip()


def _read_secret(*candidates: str | None) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return ""


def _db_defaults() -> dict[str, object]:
    return {
        "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("AIDB_DB_NAME", os.getenv("POSTGRES_DB", "aidb")),
        "user": os.getenv("AIDB_DB_USER", os.getenv("POSTGRES_USER", "aidb")),
        "password": (
            os.getenv("POSTGRES_PASSWORD", "").strip()
            or _read_secret(
                os.getenv("AIDB_POSTGRES_PASSWORD_FILE"),
                os.getenv("POSTGRES_PASSWORD_FILE"),
                "/run/secrets/postgres_password",
            )
        ),
    }


def _build_parser() -> argparse.ArgumentParser:
    defaults = _db_defaults()
    parser = argparse.ArgumentParser(
        description="Record issues in the issue tracking database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("title", help="Issue title (short summary)")
    parser.add_argument("description", help="Issue description (detailed)")
    parser.add_argument("--severity", "-s", choices=SEVERITY_CHOICES, default="medium", help="Issue severity")
    parser.add_argument("--category", "-c", choices=CATEGORY_CHOICES, default="other", help="Issue category")
    parser.add_argument("--component", required=True, help="Component where issue occurred")
    parser.add_argument("--error", "-e", help="Error message")
    parser.add_argument("--error-type", help="Error type")
    parser.add_argument("--stack-trace", help="Stack trace")
    parser.add_argument("--fix", "-f", action="append", dest="fixes", help="Suggested fix")
    parser.add_argument("--change", action="append", dest="changes", help="System change needed")
    parser.add_argument("--tag", "-t", action="append", dest="tags", help="Tag for categorization")
    parser.add_argument("--context", help="Additional context as JSON string")
    parser.add_argument("--db-host", default=defaults["host"], help="Database host")
    parser.add_argument("--db-port", type=int, default=defaults["port"], help="Database port")
    parser.add_argument("--db-name", default=defaults["database"], help="Database name")
    parser.add_argument("--db-user", default=defaults["user"], help="Database user")
    parser.add_argument(
        "--db-password",
        default=defaults["password"],
        help="Database password. Prefer POSTGRES_PASSWORD or *_PASSWORD_FILE env vars.",
    )
    return parser


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _json_sql(value: object) -> str:
    return _sql_quote(json.dumps(value))


def _compute_error_hash(error_message: str, error_type: str, component: str) -> str:
    normalized = error_message.lower()
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", normalized)
    normalized = re.sub(r"\d{2}:\d{2}:\d{2}", "TIME", normalized)
    normalized = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "UUID", normalized)
    normalized = re.sub(r"\b\d+\b", "NUM", normalized)
    return hashlib.sha256(f"{error_type}:{component}:{normalized}".encode()).hexdigest()[:16]


def _psql(args: argparse.Namespace, sql: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if args.db_password:
        env["PGPASSWORD"] = str(args.db_password)
    return subprocess.run(
        [
            "psql",
            "-X",
            "-q",
            "-t",
            "-A",
            "-h",
            str(args.db_host),
            "-p",
            str(args.db_port),
            "-U",
            str(args.db_user),
            "-d",
            str(args.db_name),
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _ensure_schema_via_psql(args: argparse.Namespace) -> None:
    result = _psql(args, SCHEMA_SQL)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to initialize issues schema")


def _record_issue_via_psql(args: argparse.Namespace, context: dict[str, object]) -> dict[str, object]:
    _ensure_schema_via_psql(args)

    issue_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    error_hash = None
    if args.error and args.error_type:
        error_hash = _compute_error_hash(args.error, args.error_type, args.component)

    sql = f"""
INSERT INTO issues (
    id, title, description, severity, category, component, status,
    error_message, error_type, stack_trace, error_hash, context,
    affected_users, occurrence_count, first_seen, last_seen,
    resolution, resolved_at, resolved_by, related_issues, tags,
    suggested_fixes, system_changes_needed
) VALUES (
    {_sql_quote(issue_id)},
    {_sql_quote(args.title)},
    {_sql_quote(args.description)},
    {_sql_quote(args.severity)},
    {_sql_quote(args.category)},
    {_sql_quote(args.component)},
    'open',
    {"NULL" if not args.error else _sql_quote(args.error)},
    {"NULL" if not args.error_type else _sql_quote(args.error_type)},
    {"NULL" if not args.stack_trace else _sql_quote(args.stack_trace)},
    {"NULL" if not error_hash else _sql_quote(error_hash)},
    {_json_sql(context)}::jsonb,
    0,
    1,
    {_sql_quote(now)}::timestamptz,
    {_sql_quote(now)}::timestamptz,
    NULL,
    NULL,
    NULL,
    '[]'::jsonb,
    {_json_sql(args.tags or [])}::jsonb,
    {_json_sql(args.fixes or [])}::jsonb,
    {_json_sql(args.changes or [])}::jsonb
)
RETURNING json_build_object(
    'id', id,
    'title', title,
    'severity', severity,
    'category', category,
    'component', component,
    'suggested_fixes', COALESCE(suggested_fixes, '[]'::jsonb),
    'system_changes_needed', COALESCE(system_changes_needed, '[]'::jsonb)
);
""".strip()

    result = _psql(args, sql)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to record issue")

    line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not line:
        raise RuntimeError("issue insert returned no result")
    return json.loads(line)


async def _record_issue_via_asyncpg(args: argparse.Namespace, context: dict[str, object]) -> dict[str, object]:
    import asyncpg  # type: ignore
    from issue_tracker import IssueCategory, IssueSeverity, IssueTracker  # type: ignore

    db_pool = await asyncpg.create_pool(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        password=args.db_password,
        min_size=1,
        max_size=5,
    )
    try:
        tracker = IssueTracker(db_pool)
        await tracker.initialize_schema()
        issue = await tracker.record_issue(
            title=args.title,
            description=args.description,
            severity=IssueSeverity(args.severity),
            category=IssueCategory(args.category),
            component=args.component,
            error_message=args.error,
            error_type=args.error_type,
            stack_trace=args.stack_trace,
            context=context,
            tags=args.tags or [],
            suggested_fixes=args.fixes or [],
            system_changes_needed=args.changes or [],
        )
        return issue.model_dump(mode="json")
    finally:
        await db_pool.close()


async def record_issue_cli() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    context: dict[str, object] = {}
    if args.context:
        try:
            context = json.loads(args.context)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in --context: {args.context}", file=sys.stderr)
            return 1

    try:
        try:
            issue = await _record_issue_via_asyncpg(args, context)
        except ModuleNotFoundError as exc:
            if exc.name != "asyncpg":
                raise
            issue = _record_issue_via_psql(args, context)

        print("\nIssue recorded successfully.")
        print(f"   ID: {issue.get('id')}")
        print(f"   Title: {issue.get('title')}")
        print(f"   Severity: {issue.get('severity')}")
        print(f"   Category: {issue.get('category')}")
        print(f"   Component: {issue.get('component')}")

        suggested_fixes = issue.get("suggested_fixes") or []
        if suggested_fixes:
            print("\n   Suggested fixes:")
            for fix in list(suggested_fixes):
                print(f"   - {fix}")

        system_changes = issue.get("system_changes_needed") or []
        if system_changes:
            print("\n   System changes needed:")
            for change in list(system_changes):
                print(f"   - {change}")

        print("\n   View all issues: ./scripts/governance/list-issues.py")
        print("   Analyze patterns: ./scripts/governance/analyze-issues.py")
        return 0
    except Exception as exc:
        print(f"Error: Failed to record issue: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(record_issue_cli()))
