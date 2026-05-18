#!/usr/bin/env python3
"""Static guard: dashboard QA surfaces must share one aq-qa subprocess service."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEALTH = (ROOT / "dashboard/backend/api/routes/health.py").read_text()
AISTACK = (ROOT / "dashboard/backend/api/routes/aistack.py").read_text()
RUNNER = (ROOT / "dashboard/backend/api/services/qa_runner.py").read_text()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


require("from api.services.qa_runner import run_phase_json" in HEALTH, "health route must use shared qa runner")
require("from ..services.qa_runner import run_phase_json" in AISTACK, "aistack route must use shared qa runner")
require("_RUNNING_TASKS" in RUNNER and "_TASKS_LOCK" in RUNNER, "qa runner must keep single-flight state")
require("run_phase_json(\"0\"" in HEALTH, "layered health must delegate phase 0 to shared runner")
require("qa_result = await run_phase_json(" in AISTACK, "phase runner must delegate to shared runner")
print("PASS: dashboard QA surfaces share one single-flight runner")
