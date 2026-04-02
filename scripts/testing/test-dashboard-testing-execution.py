#!/usr/bin/env python3
"""Offline regression checks for dashboard runtime testing execution."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeProcess:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = None
        self._final_returncode = returncode
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    async def communicate(self):
        await asyncio.sleep(0)
        self.returncode = self._final_returncode
        return self._stdout, self._stderr

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        self.wait_calls += 1
        await asyncio.sleep(0)
        if self.returncode is None:
            self.returncode = self._final_returncode
        return self.returncode


def _wait_for_status(client: TestClient, execution_id: str, expected: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/testing/executions/{execution_id}")
        if response.status_code == 200:
            payload = response.json()
            if payload.get("status") == expected:
                return payload
        time.sleep(0.05)
    raise AssertionError(f"testing execution {execution_id} did not reach status {expected}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dashboard-testing-execution-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "dashboard-context.db")
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_MODE"] = "test"

        testing_module = importlib.import_module("api.routes.testing")
        testing_module = importlib.reload(testing_module)
        testing_module.testing_runs.clear()
        testing_module.testing_tasks.clear()
        testing_module.testing_processes.clear()

        async def fake_create_process(command: list[str]):
            return FakeProcess(stdout=f"executed {' '.join(command)}".encode("utf-8"))

        testing_module._create_process = fake_create_process

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)

        with TestClient(dashboard_main.app) as client:
            suites_response = client.get("/api/testing/suites")
            assert_true(suites_response.status_code == 200, "testing suites route should succeed")
            suites_payload = suites_response.json()
            assert_true(suites_payload.get("count") == 5, "testing suite catalog should expose bounded suites")
            assert_true(
                any(item.get("id") == "property_based" for item in suites_payload.get("suites") or []),
                "testing suite catalog should include property-based tests",
            )
            assert_true(
                any(item.get("id") == "comprehensive_validation" for item in suites_payload.get("suites") or []),
                "testing suite catalog should include comprehensive validation bundle",
            )

            denied = client.post(
                "/api/testing/execute",
                json={"suite_id": "chaos_smoke", "dry_run": False, "confirm": False, "user": "codex-test"},
            )
            assert_true(denied.status_code == 400, "live testing execution should require explicit confirmation")

            dry_run = client.post(
                "/api/testing/execute",
                json={"suite_id": "performance_benchmarks", "dry_run": True, "confirm": True, "user": "codex-test"},
            )
            assert_true(dry_run.status_code == 200, "dry-run testing execution should succeed")
            dry_payload = dry_run.json()
            assert_true(dry_payload.get("status") == "success", "dry-run execution should complete immediately")
            assert_true(dry_payload.get("returncode") == 0, "dry-run execution should report zero return code")

            live = client.post(
                "/api/testing/execute",
                json={"suite_id": "property_based", "dry_run": False, "confirm": True, "user": "codex-test"},
            )
            assert_true(live.status_code == 200, "confirmed live testing execution should start")
            live_payload = live.json()
            assert_true(live_payload.get("status") == "running", "confirmed live testing execution should be running")

            live_detail = _wait_for_status(client, live_payload["execution_id"], "success")
            assert_true(live_detail.get("returncode") == 0, "live testing execution should complete successfully")
            assert_true(
                "executed python3 ai-stack/testing/property_based_tests.py" in str(live_detail.get("output") or ""),
                "live testing execution should preserve bounded command output",
            )

            comprehensive = client.post(
                "/api/testing/execute",
                json={"suite_id": "comprehensive_validation", "dry_run": False, "confirm": True, "user": "codex-test"},
            )
            assert_true(comprehensive.status_code == 200, "comprehensive validation should start")
            comprehensive_payload = comprehensive.json()
            comprehensive_detail = _wait_for_status(client, comprehensive_payload["execution_id"], "success")
            assert_true(
                comprehensive_detail.get("returncode") == 0,
                "comprehensive validation should complete successfully when all bounded steps pass",
            )
            output = str(comprehensive_detail.get("output") or "")
            assert_true(
                "[step 1/4] python3 ai-stack/testing/property_based_tests.py" in output,
                "comprehensive validation should include property-based step output",
            )
            assert_true(
                "[step 4/4] bash scripts/automation/run-prsi-canary-suite.sh" in output,
                "comprehensive validation should include canary step output",
            )

            executions = client.get("/api/testing/executions")
            assert_true(executions.status_code == 200, "testing execution history route should succeed")
            executions_payload = executions.json()
            assert_true(executions_payload.get("count", 0) >= 2, "testing execution history should include recent runs")

        testing_module = importlib.reload(testing_module)
        testing_module.testing_runs.clear()
        testing_module.testing_tasks.clear()
        testing_module.testing_processes.clear()

        fake_process = FakeProcess()

        async def hanging_create_process(command: list[str]):
            return fake_process

        testing_module._create_process = hanging_create_process
        request = testing_module.TestingExecutionRequest(
            suite_id="property_based",
            dry_run=False,
            confirm=True,
            user="codex-test",
        )
        execution_id = "test-shutdown"
        testing_module.testing_runs[execution_id] = {
            "execution_id": execution_id,
            "suite_id": "property_based",
            "status": "running",
            "requested_at": "2026-03-01T00:00:00+00:00",
            "completed_at": None,
            "returncode": None,
            "output": "Execution queued",
        }
        task = asyncio.run(
            _exercise_shutdown(testing_module, execution_id, request)
        )
        assert_true(task is None, "shutdown exercise should complete")
        cancelled = testing_module.testing_runs[execution_id]
        assert_true(cancelled.get("status") == "cancelled", "shutdown should cancel in-flight testing execution")
        assert_true(fake_process.terminated or fake_process.killed, "shutdown should terminate in-flight process")

        print("PASS: dashboard testing execution regression")
    return 0


async def _exercise_shutdown(testing_module, execution_id: str, request) -> None:
    suite = testing_module.TEST_SUITES["property_based"]
    task = asyncio.create_task(testing_module._run_testing_suite(execution_id, suite, request))
    testing_module.testing_tasks[execution_id] = task
    await asyncio.sleep(0)
    await testing_module.shutdown_testing_runner()


if __name__ == "__main__":
    raise SystemExit(main())
