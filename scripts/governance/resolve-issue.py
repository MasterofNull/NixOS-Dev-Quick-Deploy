#!/usr/bin/env python3
"""
Resolve an issue in the local issue tracking database.

Usage:
    ./resolve-issue.py <issue_id> "Resolution description"
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
    parser = argparse.ArgumentParser(description="Resolve an issue in the issue tracking database")
    parser.add_argument("issue_id", help="Issue ID to resolve")
    parser.add_argument("resolution", help="Resolution summary")
    parser.add_argument("--resolved-by", default=os.getenv("USER", "system"), help="Resolver identity")
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


def _resolve_issue_via_psql(args: argparse.Namespace) -> dict[str, object]:
    sql = f"""
UPDATE issues
SET status = 'resolved',
    resolution = {_sql_quote(args.resolution)},
    resolved_at = NOW(),
    resolved_by = {_sql_quote(args.resolved_by)},
    updated_at = NOW()
WHERE id = {_sql_quote(args.issue_id)}
RETURNING json_build_object(
    'id', id,
    'title', title,
    'status', status,
    'resolution', resolution,
    'resolved_by', resolved_by
);
""".strip()
    result = _psql(args, sql)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to resolve issue")
    line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not line:
        raise RuntimeError(f"issue not found: {args.issue_id}")
    return json.loads(line)


async def _resolve_issue_via_asyncpg(args: argparse.Namespace) -> dict[str, object]:
    import asyncpg  # type: ignore
    from issue_tracker import IssueTracker  # type: ignore

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
        await tracker.resolve_issue(args.issue_id, args.resolution, resolved_by=args.resolved_by)
        issue = await tracker.get_issue(args.issue_id)
        if issue is None:
            raise RuntimeError(f"issue not found: {args.issue_id}")
        return issue.model_dump(mode="json")
    finally:
        await db_pool.close()


async def resolve_issue_cli() -> int:
    args = _build_parser().parse_args()
    try:
        try:
            issue = await _resolve_issue_via_asyncpg(args)
        except ModuleNotFoundError as exc:
            if exc.name != "asyncpg":
                raise
            issue = _resolve_issue_via_psql(args)
        print("\nIssue resolved successfully.")
        print(f"   ID: {issue.get('id')}")
        print(f"   Title: {issue.get('title')}")
        print(f"   Status: {issue.get('status')}")
        print(f"   Resolved by: {issue.get('resolved_by')}")
        print(f"   Resolution: {issue.get('resolution')}")
        return 0
    except Exception as exc:
        print(f"Error: Failed to resolve issue: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(resolve_issue_cli()))
