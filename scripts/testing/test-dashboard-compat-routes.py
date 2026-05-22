#!/usr/bin/env python3
"""Static/API guard for dashboard compatibility proxy routes.

The command-center frontend and cached/legacy dashboard clients should not emit
404s for high-value visibility cards when route namespaces drift.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard/backend"))

from api.main import app  # noqa: E402

EXPECTED = {
    "/api/aistack/harness",
    "/api/aistack/hints/stats",
    "/api/aistack/hints/report",
    "/api/aistack/lesson-registry",
    "/api/aistack/agent-ops/status",
    "/api/aistack/memory/stats",
    "/api/traces/summary",
    "/api/hints/active",
    "/api/agent-ops/status",
    "/api/memory/stats",
    "/api/ports/registry",
    "/api/health/aggregate",
    "/api/traces/drift",
    "/api/memory/facts",
    "/api/memory/crystalline/status",
    "/api/memory/supersede/history",
    "/favicon.ico",
}

registered = {getattr(route, "path", "") for route in app.routes}
missing = sorted(EXPECTED - registered)
if missing:
    raise SystemExit("missing dashboard compatibility routes: " + ", ".join(missing))

source = (ROOT / "dashboard/backend/api/routes/aistack.py").read_text()
for needle in ("def _append_query", "def _hybrid_dual_auth_headers", "get_harness_legacy_alias"):
    if needle not in source:
        raise SystemExit(f"missing compatibility helper/function: {needle}")


FRONTEND = (ROOT / "dashboard.html").read_text() + "\n" + (ROOT / "assets/dashboard.js").read_text()
for needle in (
    "agentOpsDetails",
    "agentLessonsDetails",
    "memStatsDetails",
    "portsRegDetails",
    "healthAggDetails",
    "loadAgentOpsStatus",
    "loadAgentLessons",
    "loadMemStats",
    "loadPortsRegistry",
    "loadHealthAggregate",
):
    if needle not in FRONTEND:
        raise SystemExit(f"missing dashboard visibility surface: {needle}")

print(f"PASS: {len(EXPECTED)} dashboard compatibility routes registered")
