#!/usr/bin/env python3
"""
List issues from the issue tracking database.

Usage:
    ./list-issues.py                     # List all open issues
    ./list-issues.py --all              # List all issues
    ./list-issues.py --severity critical # List critical issues only
    ./list-issues.py --category security # List security issues only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

AIDB_MODULE_DIR = Path(__file__).resolve().parents[2] / "ai-stack" / "mcp-servers" / "aidb"
sys.path.insert(0, str(AIDB_MODULE_DIR))

STATUS_CHOICES = ["open", "investigating", "in_progress", "resolved", "wont_fix", "duplicate"]
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
    parser = argparse.ArgumentParser(description="List issues from the issue tracking database")
    parser.add_argument("--all", "-a", action="store_true", help="List all issues (including resolved)")
    parser.add_argument("--status", choices=STATUS_CHOICES, help="Filter by status")
    parser.add_argument("--severity", choices=SEVERITY_CHOICES, help="Filter by severity")
    parser.add_argument("--category", choices=CATEGORY_CHOICES, help="Filter by category")
    parser.add_argument("--component", help="Filter by component")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Limit number of results (default: 50)")
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


def _print_issues(issues: list[dict[str, object]]) -> None:
    if not issues:
        print("No issues found matching the criteria.")
        return

    severity_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🔵",
        "info": "⚪",
    }
    status_emoji = {
        "open": "📭",
        "investigating": "🔍",
        "in_progress": "⚙️",
        "resolved": "✅",
        "wont_fix": "❌",
        "duplicate": "♻️",
    }

    print(f"\n{'=' * 100}")
    print(f"Found {len(issues)} issue(s)")
    print(f"{'=' * 100}\n")

    for issue in issues:
        severity = str(issue.get("severity", "info"))
        status = str(issue.get("status", "unknown"))
        title = str(issue.get("title", "<untitled>"))
        print(f"{severity_emoji.get(severity, '❓')} {status_emoji.get(status, '❓')} [{severity.upper()}] {title}")
        print(f"   ID: {issue.get('id')}")
        print(f"   Component: {issue.get('component')}")
        print(f"   Category: {issue.get('category')}")
        print(f"   Status: {status}")
        print(f"   First seen: {issue.get('first_seen')}")
        print(f"   Last seen: {issue.get('last_seen')}")
        print(f"   Occurrences: {issue.get('occurrence_count')}")

        error_message = issue.get("error_message")
        if error_message:
            text = str(error_message)
            suffix = "..." if len(text) > 100 else ""
            print(f"   Error: {text[:100]}{suffix}")

        suggested_fixes = issue.get("suggested_fixes") or []
        if suggested_fixes:
            print("   Suggested fixes:")
            for fix in list(suggested_fixes)[:3]:
                print(f"     - {fix}")

        system_changes = issue.get("system_changes_needed") or []
        if system_changes:
            print("   System changes needed:")
            for change in list(system_changes)[:3]:
                print(f"     - {change}")

        print()

    print(f"{'=' * 100}")
    print('\nTo resolve an issue: ./scripts/resolve-issue.py <issue_id> "Resolution description"')
    print("To analyze patterns: ./scripts/governance/analyze-issues.py")


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _load_issues_via_psql(args: argparse.Namespace) -> list[dict[str, object]]:
    filters: list[str] = []
    status_filter = None if args.all else (args.status or "open")
    if status_filter:
        filters.append(f"status = {_sql_quote(status_filter)}")
    if args.severity:
        filters.append(f"severity = {_sql_quote(args.severity)}")
    if args.category:
        filters.append(f"category = {_sql_quote(args.category)}")
    if args.component:
        filters.append(f"component = {_sql_quote(args.component)}")

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    sql = f"""
SELECT json_build_object(
    'id', id,
    'title', title,
    'description', description,
    'severity', severity,
    'category', category,
    'component', component,
    'status', status,
    'error_message', error_message,
    'first_seen', to_char(first_seen AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
    'last_seen', to_char(last_seen AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
    'occurrence_count', occurrence_count,
    'suggested_fixes', COALESCE(suggested_fixes, '[]'::jsonb),
    'system_changes_needed', COALESCE(system_changes_needed, '[]'::jsonb)
)
FROM issues
{where_sql}
ORDER BY first_seen DESC
LIMIT {int(args.limit)};
""".strip()

    env = os.environ.copy()
    if args.db_password:
        env["PGPASSWORD"] = str(args.db_password)

    result = subprocess.run(
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
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "psql query failed")

    issues = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        issues.append(json.loads(line))
    return issues


async def _load_issues_via_asyncpg(args: argparse.Namespace) -> list[dict[str, object]]:
    import asyncpg  # type: ignore
    from issue_tracker import IssueCategory, IssueSeverity, IssueStatus, IssueTracker  # type: ignore

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
        status_filter = None if args.all else IssueStatus(args.status) if args.status else IssueStatus.OPEN
        severity_filter = IssueSeverity(args.severity) if args.severity else None
        category_filter = IssueCategory(args.category) if args.category else None

        issues = await tracker.list_issues(
            status=status_filter,
            severity=severity_filter,
            category=category_filter,
            component=args.component,
            limit=args.limit,
        )
        return [issue.model_dump(mode="json") for issue in issues]
    finally:
        await db_pool.close()


async def list_issues_cli() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        try:
            issues = await _load_issues_via_asyncpg(args)
        except ModuleNotFoundError as exc:
            if exc.name != "asyncpg":
                raise
            issues = _load_issues_via_psql(args)
        _print_issues(issues)
        return 0
    except Exception as exc:
        message = str(exc)
        if 'relation "issues" does not exist' in message:
            print("No issues found: issue tracker schema is not initialized yet.")
            print('Initialize it by recording the first issue with `./scripts/governance/record-issue.py ...`.')
            return 0
        print(f"Error: Failed to list issues: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(list_issues_cli()))
