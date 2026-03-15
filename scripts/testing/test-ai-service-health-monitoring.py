#!/usr/bin/env python3
"""
Test script for AI Service Health Monitoring API
Validates all health monitoring endpoints and WebSocket functionality.
"""

import asyncio
import sys
import json
import time
from typing import Dict, Any
import aiohttp

# Dashboard API configuration
API_BASE_URL = "http://localhost:8889/api"
HEALTH_BASE = f"{API_BASE_URL}/health"

class HealthMonitoringTests:
    """Test suite for health monitoring API."""

    def __init__(self):
        self.session: aiohttp.ClientSession = None
        self.tests_passed = 0
        self.tests_failed = 0

    async def initialize(self):
        """Initialize async resources."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

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

    async def test_all_services_health(self) -> bool:
        """Test GET /api/health/services/all endpoint."""
        try:
            async with self.session.get(f"{HEALTH_BASE}/services/all") as response:
                if response.status != 200:
                    self.log_test("All Services Health", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Validate response structure
                required_keys = ["timestamp", "services", "aggregate"]
                if not all(key in data for key in required_keys):
                    self.log_test("All Services Health", False, "Missing required keys")
                    return False

                # Validate aggregate data
                aggregate = data["aggregate"]
                if "healthy" not in aggregate or "total" not in aggregate:
                    self.log_test("All Services Health", False, "Invalid aggregate structure")
                    return False

                # Validate at least some services are healthy
                healthy_count = aggregate["healthy"]
                total_count = aggregate["total"]

                if total_count == 0:
                    self.log_test("All Services Health", False, "No services found")
                    return False

                health_pct = aggregate.get("health_percentage", 0)
                details = f"{healthy_count}/{total_count} services healthy ({health_pct:.1f}%)"
                self.log_test("All Services Health", True, details)
                return True

        except Exception as e:
            self.log_test("All Services Health", False, str(e))
            return False

    async def test_specific_service_health(self) -> bool:
        """Test GET /api/health/services/{id} endpoint."""
        test_services = ["ai-hybrid-coordinator", "llama-cpp", "qdrant"]

        for service_id in test_services:
            try:
                async with self.session.get(f"{HEALTH_BASE}/services/{service_id}") as response:
                    if response.status != 200:
                        self.log_test(f"Service Health: {service_id}", False, f"HTTP {response.status}")
                        continue

                    data = await response.json()

                    # Validate response structure
                    required_keys = ["name", "status", "category", "systemd", "timestamp"]
                    if not all(key in data for key in required_keys):
                        self.log_test(f"Service Health: {service_id}", False, "Missing required keys")
                        continue

                    # Check if metrics are present (should be for running services)
                    has_metrics = data.get("metrics") is not None
                    has_http = data.get("http_health") is not None

                    status = data["status"]
                    details = f"status={status}, metrics={has_metrics}, http={has_http}"
                    self.log_test(f"Service Health: {service_id}", True, details)

            except Exception as e:
                self.log_test(f"Service Health: {service_id}", False, str(e))

        return True

    async def test_category_health(self) -> bool:
        """Test GET /api/health/categories/{category} endpoint."""
        test_categories = ["ai-core", "storage", "llm"]

        for category in test_categories:
            try:
                async with self.session.get(f"{HEALTH_BASE}/categories/{category}") as response:
                    if response.status != 200:
                        self.log_test(f"Category Health: {category}", False, f"HTTP {response.status}")
                        continue

                    data = await response.json()

                    # Validate response structure
                    required_keys = ["category", "total_services", "healthy_services", "health_percentage", "services"]
                    if not all(key in data for key in required_keys):
                        self.log_test(f"Category Health: {category}", False, "Missing required keys")
                        continue

                    healthy = data["healthy_services"]
                    total = data["total_services"]
                    health_pct = data["health_percentage"]

                    details = f"{healthy}/{total} healthy ({health_pct:.1f}%)"
                    self.log_test(f"Category Health: {category}", True, details)

            except Exception as e:
                self.log_test(f"Category Health: {category}", False, str(e))

        return True

    async def test_list_categories(self) -> bool:
        """Test GET /api/health/categories endpoint."""
        try:
            async with self.session.get(f"{HEALTH_BASE}/categories") as response:
                if response.status != 200:
                    self.log_test("List Categories", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                if "categories" not in data or "count" not in data:
                    self.log_test("List Categories", False, "Missing required keys")
                    return False

                categories = data["categories"]
                count = data["count"]

                if count == 0 or len(categories) == 0:
                    self.log_test("List Categories", False, "No categories found")
                    return False

                details = f"{count} categories: {', '.join(categories)}"
                self.log_test("List Categories", True, details)
                return True

        except Exception as e:
            self.log_test("List Categories", False, str(e))
            return False

    async def test_aggregate_health(self) -> bool:
        """Test GET /api/health/aggregate endpoint."""
        try:
            async with self.session.get(f"{HEALTH_BASE}/aggregate") as response:
                if response.status != 200:
                    self.log_test("Aggregate Health", False, f"HTTP {response.status}")
                    return False

                data = await response.json()

                # Check for either new format or existing format
                if "healthy" in data and "total" in data:
                    # New format
                    status = data.get("status", "unknown")
                    health_pct = data.get("health_percentage", 0)
                    details = f"status={status}, health={health_pct:.1f}%"
                    self.log_test("Aggregate Health", True, details)
                    return True
                elif "summary" in data and "overall_status" in data:
                    # Existing format
                    summary = data["summary"]
                    status = data["overall_status"]
                    healthy = summary.get("healthy", 0)
                    total = summary.get("total", 0)
                    health_pct = (healthy / total * 100) if total > 0 else 0
                    details = f"status={status}, {healthy}/{total} healthy ({health_pct:.1f}%)"
                    self.log_test("Aggregate Health", True, details)
                    return True
                else:
                    self.log_test("Aggregate Health", False, f"Unexpected format: {list(data.keys())}")
                    return False

        except Exception as e:
            self.log_test("Aggregate Health", False, str(e))
            return False

    async def test_websocket_connection(self) -> bool:
        """Test WebSocket /api/health/ws endpoint."""
        try:
            async with self.session.ws_connect(f"ws://localhost:8889/api/health/ws") as ws:
                # Send ping
                await ws.send_str("ping")

                # Wait for pong (with timeout)
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "pong":
                            self.log_test("WebSocket Ping/Pong", True, "Ping/pong successful")
                        else:
                            self.log_test("WebSocket Ping/Pong", False, f"Unexpected response: {data.get('type')}")
                    else:
                        self.log_test("WebSocket Ping/Pong", False, f"Unexpected message type: {msg.type}")
                except asyncio.TimeoutError:
                    self.log_test("WebSocket Ping/Pong", False, "Timeout waiting for pong")

                # Request health update
                await ws.send_str("get_health")

                # Wait for health update
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "health_update" and "data" in data:
                            self.log_test("WebSocket Health Update", True, "Received health update")
                        else:
                            self.log_test("WebSocket Health Update", False, f"Unexpected response: {data.get('type')}")
                    else:
                        self.log_test("WebSocket Health Update", False, f"Unexpected message type: {msg.type}")
                except asyncio.TimeoutError:
                    self.log_test("WebSocket Health Update", False, "Timeout waiting for health update")

                return True

        except Exception as e:
            self.log_test("WebSocket Connection", False, str(e))
            return False

    async def test_service_metrics(self) -> bool:
        """Test that service metrics include CPU and memory data."""
        try:
            async with self.session.get(f"{HEALTH_BASE}/services/all") as response:
                if response.status != 200:
                    self.log_test("Service Metrics", False, f"HTTP {response.status}")
                    return False

                data = await response.json()
                services = data.get("services", {})

                # Find a service with metrics
                service_with_metrics = None
                for service_id, service_data in services.items():
                    if service_data.get("metrics"):
                        service_with_metrics = service_id
                        metrics = service_data["metrics"]

                        # Validate metrics structure
                        required_metrics = ["cpu_percent", "memory_mb", "memory_percent", "num_threads"]
                        if all(key in metrics for key in required_metrics):
                            cpu = metrics["cpu_percent"]
                            mem = metrics["memory_mb"]
                            threads = metrics["num_threads"]
                            details = f"{service_id}: CPU={cpu}%, MEM={mem}MB, threads={threads}"
                            self.log_test("Service Metrics", True, details)
                            return True

                if not service_with_metrics:
                    self.log_test("Service Metrics", False, "No services with metrics found")
                    return False

        except Exception as e:
            self.log_test("Service Metrics", False, str(e))
            return False

    async def run_all_tests(self):
        """Run all health monitoring tests."""
        print("=" * 70)
        print("AI Service Health Monitoring Test Suite")
        print("=" * 70)
        print()

        await self.initialize()

        try:
            # Run all tests
            await self.test_all_services_health()
            await self.test_specific_service_health()
            await self.test_category_health()
            await self.test_list_categories()
            await self.test_aggregate_health()
            await self.test_service_metrics()
            await self.test_websocket_connection()

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
    tests = HealthMonitoringTests()
    exit_code = await tests.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
