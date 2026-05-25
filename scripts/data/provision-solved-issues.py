#!/usr/bin/env python3
"""Provision the solved_issues table used by autonomous remediation."""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg


POSTGRES_PASSWORD_FILE = Path("/run/secrets/postgres_password")


async def main() -> int:
    if not POSTGRES_PASSWORD_FILE.exists():
        print(f"Error: {POSTGRES_PASSWORD_FILE} not found")
        return 1

    password = POSTGRES_PASSWORD_FILE.read_text(encoding="utf-8").strip()

    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="aidb",
            password=password,
            database="aidb",
        )
    except Exception as exc:
        print(f"Failed to connect to aidb database: {exc}")
        return 1

    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS solved_issues (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                solution TEXT NOT NULL,
                value_score FLOAT DEFAULT 0.0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_solved_issues_value_score
                ON solved_issues (value_score);
            CREATE INDEX IF NOT EXISTS idx_solved_issues_created_at
                ON solved_issues (created_at);
            """
        )
    finally:
        await conn.close()

    print("Table solved_issues ensured in aidb")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
