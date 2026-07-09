#!/usr/bin/env python3
"""Static guard: dashboard QA surfaces must share one aq-qa subprocess service."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEALTH = (ROOT / "dashboard/backend/api/routes/health.py").read_text()
AISTACK = (ROOT / "dashboard/backend/api/routes/aistack.py").read_text()
RUNNER = (ROOT / "dashboard/backend/api/services/qa_runner.py").read_text()
HELPERS = (ROOT / "scripts/testing/harness_qa/core/helpers.py").read_text()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


require("from api.services.qa_runner import run_phase_json" in HEALTH, "health route must use shared qa runner")
require("from ..services.qa_runner import run_phase_json" in AISTACK, "aistack route must use shared qa runner")
require("_RUNNING_TASKS" in RUNNER and "_TASKS_LOCK" in RUNNER, "qa runner must keep single-flight state")
require("run_phase_json(\"0\"" in HEALTH, "layered health must delegate phase 0 to shared runner")
require("qa_result = await run_phase_json(" in AISTACK, "phase runner must delegate to shared runner")
require(
    "normalize_dashboard_confined=True" in HEALTH
    and "dashboard_confined_normalized" in RUNNER
    and "_DASHBOARD_HOST_ONLY_PHASE0_IDS" in RUNNER,
    "layered health should normalize dashboard-confined host-only aq-qa failures instead of showing false OSI failures",
)
require(
    '"0.10.26"' in RUNNER and "context compaction sandwich imports full switchboard deps" in RUNNER,
    "dashboard OSI health should normalize context sandwich import failures when run under dashboard Python confinement",
)
require(
    'env.setdefault("AQ_QA_DASHBOARD_SAFE", "1")' in RUNNER,
    "dashboard phase-0 QA should request dashboard-safe harness mode before host-only probes run",
)
require(
    '"TMPDIR", "TEMP", "TMP"' in RUNNER
    and "PYTHONPYCACHEPREFIX" in RUNNER
    and "CARGO_TARGET_DIR" in RUNNER
    and "DASHBOARD_DATA_DIR" in RUNNER,
    "dashboard QA subprocesses must redirect temp/cache writes into the dashboard writable state dir",
)
require(
    "dashboard_safe = os.environ.get(\"AQ_QA_DASHBOARD_SAFE\"" in HELPERS
    and "if dashboard_safe:" in HELPERS
    and "subprocess.run(" in HELPERS,
    "dashboard-safe port probes must avoid ss fallback that AppArmor denies under command-center-dashboard-api",
)
print("PASS: dashboard QA surfaces share one single-flight runner")
