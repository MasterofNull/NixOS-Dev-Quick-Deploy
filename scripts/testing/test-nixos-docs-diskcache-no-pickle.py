#!/usr/bin/env python3
"""Regression: nixos-docs cache is a stdlib sqlite3 TEXT TTL cache, no diskcache/pickle."""

from __future__ import annotations

import ast
import os
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "ai-stack/mcp-servers/nixos-docs/server.py"


def load_class():
    src = SERVER.read_text(encoding="utf-8")
    node = next(
        n for n in ast.parse(src).body
        if isinstance(n, ast.ClassDef) and n.name == "TextTTLCache"
    )
    ns = {"logger": __import__("logging").getLogger("t"), "os": os, "time": time, "sqlite3": sqlite3, "threading": threading,
          "Optional": Optional}
    exec(compile(ast.Module([node], []), str(SERVER), "exec"), ns)
    return src, ns["TextTTLCache"]


def main() -> int:
    f: list[str] = []
    src, C = load_class()
    if "diskcache" in src.lower().replace("diskcache (unmaintained", ""):
        f.append("server.py still references diskcache")
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in n.names] + [getattr(n, "module", "") or ""]
            if any(x.split(".")[0] in ("diskcache", "pickle") for x in names):
                f.append("server.py imports diskcache/pickle")

    with tempfile.TemporaryDirectory() as td:
        c = C(td)
        c.set("a", "hello", expire=60)
        big = "x" * 100000
        c.set("big", big)
        if c.get("a") != "hello" or c.get("big") != big:
            f.append("round-trip failed")
        if c.get("missing") is not None:
            f.append("missing key not a miss")
        for bad in ({"a": 1}, b"x", 1, None):
            try:
                c.set("b", bad)
                f.append(f"set({type(bad).__name__}) did not raise TypeError")
            except TypeError:
                pass
        c.set("short", "v", expire=0.2)
        if c.get("short") != "v":
            f.append("short-lived key missing early")
        time.sleep(0.3)
        if c.get("short") is not None:
            f.append("expired key returned")
        if c._db.execute("SELECT COUNT(*) FROM cache WHERE key='short'").fetchone()[0]:
            f.append("expired row not deleted")
        if len(c) != 2:
            f.append(f"len expected 2, got {len(c)}")
        c.close()

        c = C(td)  # persistence
        if c.get("a") != "hello":
            f.append("not persisted across reopen")

        errs: list[str] = []

        def work(i: int) -> None:
            try:
                for j in range(50):
                    k = f"t{i}-{j}"
                    c.set(k, k, expire=60)
                    if c.get(k) != k:
                        errs.append(k)
            except Exception as e:  # noqa: BLE001
                errs.append(repr(e))

        ts = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        if errs:
            f.append(f"thread errors: {errs[:3]}")
        c.clear()
        if len(c) != 0:
            f.append("clear failed")
        c.close()

    # legacy diskcache-shaped cache.db present -> works via text-cache.db
    with tempfile.TemporaryDirectory() as td:
        legacy = sqlite3.connect(os.path.join(td, "cache.db"))
        legacy.execute(
            "CREATE TABLE Cache (rowid INTEGER PRIMARY KEY, key BLOB, raw INTEGER, "
            "store_time REAL, expire_time REAL, access_time REAL, access_count INTEGER, "
            "tag BLOB, size INTEGER, mode INTEGER, filename TEXT, value BLOB)"
        )
        legacy.commit()
        legacy.close()
        c = C(td)
        c.set("k", "v", expire=60)
        if c.get("k") != "v":
            f.append("cache broken with legacy cache.db present")
        c.close()
        if not os.path.exists(os.path.join(td, "text-cache.db")):
            f.append("text-cache.db not created")

    # schema mismatch on text-cache.db -> constructor raises (server falls back to tmp dir)
    with tempfile.TemporaryDirectory() as td:
        bad = sqlite3.connect(os.path.join(td, "text-cache.db"))
        bad.execute("CREATE TABLE cache (key TEXT PRIMARY KEY, other BLOB)")
        bad.commit()
        bad.close()
        try:
            C(td)
            f.append("schema mismatch did not raise")
        except RuntimeError:
            pass
        if "except Exception as _cache_exc" not in src or "_fallback" not in src:
            f.append("server.py lost temp-dir fallback")

    # get() never raises on sqlite errors
    with tempfile.TemporaryDirectory() as td:
        c = C(td)
        c._db.execute("DROP TABLE cache")
        if c.get("x", "MISS") != "MISS":
            f.append("get on broken db did not miss")
        c.close()

    if f:
        print("FAIL:")
        for x in f:
            print(" -", x)
        return 1
    print("PASS test-nixos-docs-diskcache-no-pickle (stdlib sqlite3 TextTTLCache)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
