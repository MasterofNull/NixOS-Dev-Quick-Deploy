"""Minimal async Postgres client used by the hybrid coordinator learning pipeline."""

from __future__ import annotations

import psycopg


class PostgresClient:
    """Simple async wrapper around psycopg.AsyncConnection for execute-only usage."""

    def __init__(self, host: str, port: int, database: str, user: str, password: str) -> None:
        self._dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self._conn: psycopg.AsyncConnection | None = None

    async def connect(self) -> None:
        if self._conn is None:
            self._conn = await psycopg.AsyncConnection.connect(self._dsn)

    async def execute(self, query: str, *params) -> None:
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        await self._conn.execute(query, params)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
