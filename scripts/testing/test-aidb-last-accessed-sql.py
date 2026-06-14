#!/usr/bin/env python3
"""Guard AIDB last_accessed_at update SQL against PostgreSQL unknown-parameter regressions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "ai-stack" / "mcp-servers" / "aidb" / "server.py"
src = SERVER.read_text()

required = [
    "jsonb_build_object('last_accessed_at', CAST(:ts AS text))",
    "WHERE id = ANY(CAST(:ids AS integer[]))",
    "COALESCE(metadata, '{}'::jsonb)",
]

missing = [item for item in required if item not in src]
if missing:
    raise SystemExit(f"FAIL: AIDB last_accessed_at SQL missing explicit casts: {missing}")

print("PASS: AIDB last_accessed_at SQL casts parameters explicitly")
