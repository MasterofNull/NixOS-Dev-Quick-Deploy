#!/usr/bin/env python3
"""
Test script for AI Insights Dashboard API
Validates all insights endpoints and data integrity.
"""

import asyncio
import sys
import json
from typing import Dict, Any
import aiohttp

# Dashboard API configuration
API_BASE_URL = "http://localhost:8889/api"
INSIGHTS_BASE = f"{API_BASE_URL}/insights"

class AIInsightsTests:
    """Test suite for AI insights API."""

    def __init__(self):
        self.session: aiohttp.ClientSession = None
        self.tests_passed = 0
        self.tests_failed = 0

    async def initialize(self):
        """Initialize async resources."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

    async def close(self):
        """Close async resources."""
        if self.session:
            await self.session.close()

    def log_test(self, name: str, passed: bool, details: str = ""):
        """Log test result."""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if details:
            print(f"  {details}")

        if passed:
            self.tests_passed += 1
        else:
            self.tests_failed += 1

    async def test_system_health_overview(self) -> bool:
        """Test GET /api/insights/system/health endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/system/health") as response:
                if response.status != 200:
                    self.log_test("System Health Overview", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "status", "issues", "recommendations"]
                if not all(key in data for key in required_keys):
                    self.log_test("System Health Overview", False, "Missing required keys")
                    return False

                status = data["status"]
                issue_count = len(data["issues"])
                rec_count = len(data["recommendations"])

                details = f"status={status}, issues={issue_count}, recommendations={rec_count}"
                self.log_test("System Health Overview", True, details)
                return True

        except Exception as e:
            self.log_test("System Health Overview", False, str(e))
            return False

    async def test_tool_performance(self) -> bool:
        """Test GET /api/insights/tools/performance endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/tools/performance") as response:
                if response.status != 200:
                    self.log_test("Tool Performance Summary", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "summary", "top_tools"]
                if not all(key in data for key in required_keys):
                    self.log_test("Tool Performance Summary", False, "Missing required keys")
                    return False

                summary = data["summary"]
                total_tools = summary.get("total_tools", 0)
                total_calls = summary.get("total_calls", 0)
                error_rate = summary.get("error_rate_pct", 0)

                details = f"{total_tools} tools, {total_calls} calls, {error_rate:.2f}% errors"
                self.log_test("Tool Performance Summary", True, details)
                return True

        except Exception as e:
            self.log_test("Tool Performance Summary", False, str(e))
            return False

    async def test_routing_analytics(self) -> bool:
        """Test GET /api/insights/routing/analytics endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/routing/analytics") as response:
                if response.status != 200:
                    self.log_test("Routing Analytics", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "current", "recent", "windows"]
                if not all(key in data for key in required_keys):
                    self.log_test("Routing Analytics", False, "Missing required keys")
                    return False

                current = data["current"]
                local_pct = current.get("local_pct", 0)
                available = current.get("available", False)

                details = f"available={available}, local={local_pct}%"
                self.log_test("Routing Analytics", True, details)
                return True

        except Exception as e:
            self.log_test("Routing Analytics", False, str(e))
            return False

    async def test_hint_effectiveness(self) -> bool:
        """Test GET /api/insights/hints/effectiveness endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/hints/effectiveness") as response:
                if response.status != 200:
                    self.log_test("Hint Effectiveness", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "adoption", "diversity"]
                if not all(key in data for key in required_keys):
                    self.log_test("Hint Effectiveness", False, "Missing required keys")
                    return False

                adoption = data["adoption"]
                adoption_pct = adoption.get("adoption_pct", 0)
                unique_hints = adoption.get("unique_hints", 0)

                details = f"adoption={adoption_pct}%, unique_hints={unique_hints}"
                self.log_test("Hint Effectiveness", True, details)
                return True

        except Exception as e:
            self.log_test("Hint Effectiveness", False, str(e))
            return False

    async def test_workflow_compliance(self) -> bool:
        """Test GET /api/insights/workflows/compliance endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/workflows/compliance") as response:
                if response.status != 200:
                    self.log_test("Workflow Compliance", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "intent_contract", "task_tooling"]
                if not all(key in data for key in required_keys):
                    self.log_test("Workflow Compliance", False, "Missing required keys")
                    return False

                intent = data["intent_contract"]
                total_runs = intent.get("total_runs", 0)
                coverage_pct = intent.get("contract_coverage_pct", 0)

                details = f"total_runs={total_runs}, coverage={coverage_pct}%"
                self.log_test("Workflow Compliance", True, details)
                return True

        except Exception as e:
            self.log_test("Workflow Compliance", False, str(e))
            return False

    async def test_a2a_readiness(self) -> bool:
        """Test GET /api/insights/workflows/a2a-readiness endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/workflows/a2a-readiness") as response:
                if response.status != 200:
                    self.log_test("A2A Readiness", False, f"HTTP {response.status}")
                    return False

                data = await response.json()
                required_keys = [
                    "available",
                    "status",
                    "protocol_version",
                    "streaming",
                    "push_notifications",
                    "features",
                    "methods",
                ]
                if not all(key in data for key in required_keys):
                    self.log_test("A2A Readiness", False, "Missing required keys")
                    return False

                implemented = (data.get("methods") or {}).get("implemented") or []
                if "message/stream" not in implemented or "tasks/list" not in implemented or "tasks/cancel" not in implemented:
                    self.log_test("A2A Readiness", False, "Missing required A2A methods")
                    return False
                features = data.get("features") or {}
                if not features.get("message_stream") or not features.get("task_artifacts"):
                    self.log_test("A2A Readiness", False, "Missing required A2A feature flags")
                    return False

                details = (
                    f"status={data.get('status')}, protocol={data.get('protocol_version')}, "
                    f"streaming={data.get('streaming')}, message_stream={features.get('message_stream')}, "
                    f"task_artifacts={features.get('task_artifacts')}, push_notifications={data.get('push_notifications')}"
                )
                self.log_test("A2A Readiness", True, details)
                return True

        except Exception as e:
            self.log_test("A2A Readiness", False, str(e))
            return False

    async def test_query_complexity(self) -> bool:
        """Test GET /api/insights/queries/complexity endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/queries/complexity") as response:
                if response.status != 200:
                    self.log_test("Query Complexity Analysis", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "latency_breakdown", "query_gaps"]
                if not all(key in data for key in required_keys):
                    self.log_test("Query Complexity Analysis", False, "Missing required keys")
                    return False

                latency = data["latency_breakdown"]
                total_calls = latency.get("total_calls", 0)
                p95_ms = latency.get("overall_p95_ms", 0)
                gap_count = len(data["query_gaps"])

                details = f"calls={total_calls}, p95={p95_ms:.0f}ms, gaps={gap_count}"
                self.log_test("Query Complexity Analysis", True, details)
                return True

        except Exception as e:
            self.log_test("Query Complexity Analysis", False, str(e))
            return False

    async def test_cache_analytics(self) -> bool:
        """Test GET /api/insights/cache/analytics endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/cache/analytics") as response:
                if response.status != 200:
                    self.log_test("Cache Analytics", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "cache"]
                if not all(key in data for key in required_keys):
                    self.log_test("Cache Analytics", False, "Missing required keys")
                    return False

                cache = data["cache"]
                hit_pct = cache.get("hit_pct", 0)
                available = cache.get("available", False)

                details = f"available={available}, hit_pct={hit_pct}%"
                self.log_test("Cache Analytics", True, details)
                return True

        except Exception as e:
            self.log_test("Cache Analytics", False, str(e))
            return False

    async def test_agent_lessons(self) -> bool:
        """Test GET /api/insights/agents/lessons endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/agents/lessons") as response:
                if response.status != 200:
                    self.log_test("Agent Lessons", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "window", "lessons"]
                if not all(key in data for key in required_keys):
                    self.log_test("Agent Lessons", False, "Missing required keys")
                    return False

                lessons = data["lessons"]
                available = lessons.get("available", False)

                details = f"available={available}"
                self.log_test("Agent Lessons", True, details)
                return True

        except Exception as e:
            self.log_test("Agent Lessons", False, str(e))
            return False

    async def test_structured_actions(self) -> bool:
        """Test GET /api/insights/actions/recommendations endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/actions/recommendations") as response:
                if response.status != 200:
                    self.log_test("Structured Actions", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                if "actions" not in data or "count" not in data:
                    self.log_test("Structured Actions", False, "Missing required keys")
                    return False

                count = data["count"]

                details = f"{count} actionable recommendations"
                self.log_test("Structured Actions", True, details)
                return True

        except Exception as e:
            self.log_test("Structured Actions", False, str(e))
            return False

    async def test_full_report(self) -> bool:
        """Test GET /api/insights/report/full endpoint."""
        try:
            async with self.session.get(f"{INSIGHTS_BASE}/report/full") as response:
                if response.status != 200:
                    self.log_test("Full Insights Report", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["generated_at", "window", "tool_performance", "routing"]
                if not all(key in data for key in required_keys):
                    self.log_test("Full Insights Report", False, "Missing required keys")
                    return False

                tool_count = len(data.get("tool_performance", {}))

                details = f"{tool_count} tools tracked"
                self.log_test("Full Insights Report", True, details)
                return True

        except Exception as e:
            self.log_test("Full Insights Report", False, str(e))
            return False

    async def run_all_tests(self):
        """Run all AI insights tests."""
        print("=" * 70)
        print("AI Insights Dashboard Test Suite")
        print("=" * 70)
        print()

        await self.initialize()

        try:
            # Run all tests
            await self.test_system_health_overview()
            await self.test_tool_performance()
            await self.test_routing_analytics()
            await self.test_hint_effectiveness()
            await self.test_workflow_compliance()
            await self.test_a2a_readiness()
            await self.test_query_complexity()
            await self.test_cache_analytics()
            await self.test_agent_lessons()
            await self.test_structured_actions()
            await self.test_full_report()

        finally:
            await self.close()

        # Print summary
        print()
        print("=" * 70)
        print("Test Summary")
        print("=" * 70)
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Total:  {self.tests_passed + self.tests_failed}")
        print()

        if self.tests_failed == 0:
            print("✓ All tests PASSED")
            return 0
        else:
            print(f"✗ {self.tests_failed} test(s) FAILED")
            return 1


async def main():
    """Main entry point."""
    tests = AIInsightsTests()
    exit_code = await tests.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
