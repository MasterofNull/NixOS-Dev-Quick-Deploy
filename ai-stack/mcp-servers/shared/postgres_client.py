"""Minimal async Postgres client used by the hybrid coordinator learning pipeline."""

from __future__ import annotations

import socket
from urllib.parse import urlencode

import psycopg
from psycopg.rows import dict_row


class PostgresClient:
    """Simple async wrapper around psycopg.AsyncConnection for execute-only usage."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        sslmode: str | None = None,
        sslrootcert: str | None = None,
        sslcert: str | None = None,
        sslkey: str | None = None,
    ) -> None:
        if not host:
            host = "127.0.0.1"
        else:
            # Be defensive in service startup: fall back to loopback when a hostname
            # from external config is not resolvable in this runtime.
            try:
                socket.getaddrinfo(host, port)
            except OSError:
                host = "127.0.0.1"

        base_dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        params = {}
        if sslmode:
            params["sslmode"] = sslmode
        if sslrootcert:
            params["sslrootcert"] = sslrootcert
        if sslcert:
            params["sslcert"] = sslcert
        if sslkey:
            params["sslkey"] = sslkey
        if params:
            self._dsn = f"{base_dsn}?{urlencode(params)}"
        else:
            self._dsn = base_dsn
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

    async def fetch_all(self, query: str, *params) -> list[dict]:
        if self._conn is None:
            await self.connect()
        assert self._conn is not None
        async with self._conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
        return list(rows)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
