#!/usr/bin/env python3
"""
Live validation for dashboard deployment tracking and rollback APIs.
"""

import asyncio
import os
import time
import uuid

import aiohttp


API_BASE_URL = os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8889").rstrip("/") + "/api"


class DeploymentDashboardTests:
    def __init__(self) -> None:
        self.session: aiohttp.ClientSession | None = None
        self.tests_passed = 0
        self.tests_failed = 0
        self.deployment_id = f"test-deploy-{int(time.time())}-{uuid.uuid4().hex[:8]}"

    async def initialize(self) -> None:
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    def log_test(self, name: str, passed: bool, details: str = "") -> None:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {name}")
        if details:
            print(f"  {details}")
        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1

    async def test_start(self) -> bool:
        async with self.session.post(
            f"{API_BASE_URL}/deployments/start",
            params={
                "deployment_id": self.deployment_id,
                "command": "deploy system --fast",
                "user": "codex-test",
            },
        ) as response:
            if response.status != 200:
                self.log_test("Start Deployment", False, f"HTTP {response.status}")
                return False
            data = await response.json()
            passed = data.get("deployment_id") == self.deployment_id and data.get("status") == "started"
            self.log_test("Start Deployment", passed, str(data))
            return passed

    async def test_progress(self) -> bool:
        payload = {
            "progress": 55,
            "message": "Building generation",
            "log": "nixos-rebuild switch in progress",
        }
        async with self.session.post(
            f"{API_BASE_URL}/deployments/{self.deployment_id}/progress",
            json=payload,
        ) as response:
            if response.status != 200:
                self.log_test("Progress Update", False, f"HTTP {response.status}")
                return False
            data = await response.json()
            passed = data.get("progress") == 55 and data.get("status") == "updated"
            self.log_test("Progress Update", passed, str(data))
            return passed

    async def test_history_and_detail(self) -> bool:
        async with self.session.get(
            f"{API_BASE_URL}/deployments/history",
            params={"limit": 10, "status": "running", "include_timeline_preview": "true"},
        ) as response:
            if response.status != 200:
                self.log_test("History Endpoint", False, f"HTTP {response.status}")
                return False
            history = await response.json()

        deployments = history.get("deployments") or []
        current = next((item for item in deployments if item.get("deployment_id") == self.deployment_id), None)
        if not current or not current.get("timeline_preview"):
            self.log_test("History Endpoint", False, "deployment missing timeline preview")
            return False

        async with self.session.get(f"{API_BASE_URL}/deployments/{self.deployment_id}") as response:
            if response.status != 200:
                self.log_test("Deployment Detail", False, f"HTTP {response.status}")
                return False
            detail = await response.json()

        passed = bool(detail.get("timeline")) and detail.get("rollback", {}).get("command") == "deploy system --rollback"
        self.log_test(
            "History And Detail",
            passed,
            f"history_total={history.get('total')}, timeline={len(detail.get('timeline') or [])}",
        )
        return passed

    async def test_search_and_logs(self) -> bool:
        async with self.session.get(f"{API_BASE_URL}/deployments/{self.deployment_id}/logs") as response:
            if response.status != 200:
                self.log_test("Deployment Logs", False, f"HTTP {response.status}")
                return False
            logs = await response.json()

        async with self.session.get(
            f"{API_BASE_URL}/deployments/search",
            params={"query": "building generation", "limit": 5, "mode": "keyword"},
        ) as response:
            if response.status != 200:
                self.log_test("Deployment Search", False, f"HTTP {response.status}")
                return False
            search = await response.json()

        async with self.session.get(
            f"{API_BASE_URL}/deployments/search/status",
            params={"recent_limit": 5},
        ) as response:
            if response.status != 200:
                self.log_test("Deployment Search Status", False, f"HTTP {response.status}")
                return False
            status = await response.json()

        async with self.session.get(
            f"{API_BASE_URL}/deployments/graph",
            params={"deployment_id": self.deployment_id, "view": "issues", "focus": "dashboard"},
        ) as response:
            if response.status != 200:
                self.log_test("Deployment Graph", False, f"HTTP {response.status}")
                return False
            graph = await response.json()

        async with self.session.get(
            f"{API_BASE_URL}/deployments/graph",
            params={"recent_limit": 6, "view": "causality", "focus": "deploy system --fast"},
        ) as response:
            if response.status != 200:
                self.log_test("Deployment Graph Causality", False, f"HTTP {response.status}")
                return False
            causality = await response.json()

        passed = (
            bool(logs.get("logs"))
            and isinstance(search.get("results"), list)
            and search.get("mode") == "keyword"
            and isinstance(status.get("recent"), list)
            and "summary" in status
            and isinstance(graph.get("nodes"), list)
            and isinstance(graph.get("edges"), list)
            and graph.get("view") == "issues"
            and graph.get("focus") == "dashboard"
            and isinstance(graph.get("top_relationships"), list)
            and causality.get("view") == "causality"
            and isinstance(causality.get("edges"), list)
            and isinstance(causality.get("clusters"), list)
            and causality.get("cluster_count", 0) >= 0
            and ("root_cluster" in causality)
            and isinstance(causality.get("similar_failures"), list)
            and isinstance(causality.get("cause_factors"), list)
            and isinstance(causality.get("cause_chain"), list)
        )
        self.log_test(
            "Search And Logs",
            passed,
            f"logs={len(logs.get('logs') or [])}, keyword={len(search.get('results') or [])}, graph_edges={len(graph.get('edges') or [])}, causality_edges={len(causality.get('edges') or [])}, clusters={len(causality.get('clusters') or [])}, similar_failures={len(causality.get('similar_failures') or [])}, cause_factors={len(causality.get('cause_factors') or [])}",
        )
        return passed

    async def test_complete_and_rollback_plan(self) -> bool:
        async with self.session.post(
            f"{API_BASE_URL}/deployments/{self.deployment_id}/complete",
            json={"success": True, "message": "Deployment test complete"},
        ) as response:
            if response.status != 200:
                self.log_test("Complete Deployment", False, f"HTTP {response.status}")
                return False
            complete = await response.json()

        async with self.session.post(
            f"{API_BASE_URL}/deployments/{self.deployment_id}/rollback",
            json={
                "confirm": True,
                "execute": False,
                "reason": "Dashboard dry-run rollback validation",
            },
        ) as response:
            if response.status != 200:
                self.log_test("Rollback Plan", False, f"HTTP {response.status}")
                return False
            rollback = await response.json()

        passed = (
            complete.get("status") == "success"
            and rollback.get("status") == "planned"
            and rollback.get("rollback_command") == "deploy system --rollback"
        )
        self.log_test("Complete And Rollback Plan", passed, f"{complete} / {rollback}")
        return passed

    async def run(self) -> int:
        await self.initialize()
        try:
            await self.test_start()
            await self.test_progress()
            await self.test_history_and_detail()
            await self.test_search_and_logs()
            await self.test_complete_and_rollback_plan()
        finally:
            await self.close()

        print()
        print(f"Tests passed: {self.tests_passed}")
        print(f"Tests failed: {self.tests_failed}")
        return 0 if self.tests_failed == 0 else 1


async def main() -> int:
    suite = DeploymentDashboardTests()
    return await suite.run()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
