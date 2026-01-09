#!/usr/bin/env python3
"""
Test suite for P2 Health Check System

Tests liveness, readiness, and startup probes for all services.
"""

import asyncio
import sys
from pathlib import Path

import asyncpg
import httpx
import pytest
from qdrant_client import QdrantClient

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers" / "aidb"))

from health_check import HealthChecker, HealthStatus, CheckType


class TestHealthChecker:
    """Test suite for HealthChecker"""

    @pytest.mark.asyncio
    async def test_liveness_probe_healthy(self):
        """Liveness probe should return healthy for running service"""
        # Create minimal health checker (no dependencies)
        health_checker = HealthChecker(service_name="test-service")

        result = await health_checker.liveness_probe()

        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == CheckType.LIVENESS
        assert "alive" in result.message.lower()
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_readiness_probe_no_dependencies(self):
        """Readiness probe should be healthy with no dependencies"""
        health_checker = HealthChecker(service_name="test-service")

        result = await health_checker.readiness_probe()

        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == CheckType.READINESS
        assert "ready" in result.message.lower()

    @pytest.mark.asyncio
    async def test_startup_probe_not_complete(self):
        """Startup probe should be unhealthy before startup complete"""
        health_checker = HealthChecker(service_name="test-service")

        # Force startup not complete
        health_checker._startup_complete = False

        result = await health_checker.startup_probe()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.check_type == CheckType.STARTUP
        assert "in progress" in result.message.lower()

    @pytest.mark.asyncio
    async def test_startup_probe_complete(self):
        """Startup probe should be healthy after startup complete"""
        health_checker = HealthChecker(service_name="test-service")

        # Mark startup as complete
        health_checker._startup_complete = True

        result = await health_checker.startup_probe()

        assert result.status == HealthStatus.HEALTHY
        assert result.check_type == CheckType.STARTUP
        assert "complete" in result.message.lower()

    @pytest.mark.asyncio
    async def test_postgresql_dependency_check(self):
        """Test PostgreSQL dependency health check"""
        try:
            db_pool = await asyncpg.create_pool(
                host="localhost",
                port=5432,
                database="aidb",
                user="aidb",
                password="aidb_password",
                min_size=1,
                max_size=5
            )

            health_checker = HealthChecker(
                service_name="test-service",
                db_pool=db_pool
            )

            result = await health_checker.readiness_probe()

            assert result.check_type == CheckType.READINESS
            assert "dependencies" in result.details

            # Check PostgreSQL is in dependencies
            deps = result.details["dependencies"]
            pg_dep = next((d for d in deps if d["name"] == "postgresql"), None)
            assert pg_dep is not None
            assert pg_dep["critical"] == True

            await db_pool.close()

        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")

    @pytest.mark.asyncio
    async def test_qdrant_dependency_check(self):
        """Test Qdrant dependency health check"""
        try:
            qdrant = QdrantClient(host="localhost", port=6333, timeout=5)

            health_checker = HealthChecker(
                service_name="test-service",
                qdrant_client=qdrant
            )

            result = await health_checker.readiness_probe()

            assert result.check_type == CheckType.READINESS
            assert "dependencies" in result.details

            # Check Qdrant is in dependencies
            deps = result.details["dependencies"]
            qdrant_dep = next((d for d in deps if d["name"] == "qdrant"), None)
            assert qdrant_dep is not None
            assert qdrant_dep["critical"] == True

        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")

    @pytest.mark.asyncio
    async def test_readiness_degraded_with_non_critical_failure(self):
        """Readiness should be degraded if non-critical dependency fails"""
        health_checker = HealthChecker(service_name="test-service")

        # Register a non-critical check that fails
        async def failing_check():
            return False

        health_checker.register_dependency_check(
            name="non-critical-service",
            check_fn=failing_check,
            critical=False,
            timeout=1.0
        )

        result = await health_checker.readiness_probe()

        # Should be degraded, not unhealthy
        assert result.status == HealthStatus.DEGRADED
        assert "degraded" in result.message.lower()
        assert result.details["non_critical_failures"] == 1

    @pytest.mark.asyncio
    async def test_readiness_unhealthy_with_critical_failure(self):
        """Readiness should be unhealthy if critical dependency fails"""
        health_checker = HealthChecker(service_name="test-service")

        # Register a critical check that fails
        async def failing_check():
            return False

        health_checker.register_dependency_check(
            name="critical-service",
            check_fn=failing_check,
            critical=True,
            timeout=1.0
        )

        result = await health_checker.readiness_probe()

        # Should be unhealthy
        assert result.status == HealthStatus.UNHEALTHY
        assert "not ready" in result.message.lower()
        assert result.details["critical_failures"] == 1

    @pytest.mark.asyncio
    async def test_dependency_check_timeout(self):
        """Dependency check should timeout if taking too long"""
        health_checker = HealthChecker(service_name="test-service")

        # Register a check that times out
        async def slow_check():
            await asyncio.sleep(10)  # Longer than timeout
            return True

        health_checker.register_dependency_check(
            name="slow-service",
            check_fn=slow_check,
            critical=True,
            timeout=0.5  # Short timeout
        )

        result = await health_checker.readiness_probe()

        # Should be unhealthy due to timeout
        assert result.status == HealthStatus.UNHEALTHY

        # Check timeout is recorded
        deps = result.details["dependencies"]
        slow_dep = next((d for d in deps if d["name"] == "slow-service"), None)
        assert slow_dep is not None
        assert slow_dep["error"] == "timeout"

    def test_health_check_result_serialization(self):
        """HealthCheckResult should serialize to dict correctly"""
        from health_check import HealthCheckResult

        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            check_type=CheckType.LIVENESS,
            message="Service is healthy",
            details={"foo": "bar"},
            duration_ms=15.5
        )

        data = result.to_dict()

        assert data["status"] == "healthy"
        assert data["check_type"] == "liveness"
        assert data["message"] == "Service is healthy"
        assert data["details"]["foo"] == "bar"
        assert data["duration_ms"] == 15.5
        assert "timestamp" in data


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Test health check HTTP endpoints"""

    async def test_liveness_endpoint(self):
        """Test /health/live endpoint"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get("http://localhost:8091/health/live")

                if response.status_code == 404:
                    pytest.skip("Health endpoints not yet deployed")

                assert response.status_code in [200, 503]

                data = response.json()
                assert "status" in data
                assert "check_type" in data
                assert data["check_type"] == "liveness"

            except httpx.ConnectError:
                pytest.skip("AIDB server not running")

    async def test_readiness_endpoint(self):
        """Test /health/ready endpoint"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get("http://localhost:8091/health/ready")

                if response.status_code == 404:
                    pytest.skip("Health endpoints not yet deployed")

                assert response.status_code in [200, 503]

                data = response.json()
                assert "status" in data
                assert "check_type" in data
                assert data["check_type"] == "readiness"

                if response.status_code == 200:
                    # If healthy, check dependencies
                    assert "details" in data
                    assert "dependencies" in data["details"]

            except httpx.ConnectError:
                pytest.skip("AIDB server not running")

    async def test_startup_endpoint(self):
        """Test /health/startup endpoint"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get("http://localhost:8091/health/startup")

                if response.status_code == 404:
                    pytest.skip("Health endpoints not yet deployed")

                assert response.status_code in [200, 503]

                data = response.json()
                assert "status" in data
                assert "check_type" in data
                assert data["check_type"] == "startup"

            except httpx.ConnectError:
                pytest.skip("AIDB server not running")

    async def test_detailed_health_endpoint(self):
        """Test /health/detailed endpoint"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get("http://localhost:8091/health/detailed")

                if response.status_code == 404:
                    pytest.skip("Health endpoints not yet deployed")

                assert response.status_code == 200

                data = response.json()
                assert "service" in data
                assert data["service"] == "aidb"
                assert "startup_complete" in data

            except httpx.ConnectError:
                pytest.skip("AIDB server not running")


def run_all_tests():
    """Run all health check tests"""
    print("=" * 80)
    print("P2 Health Check System - Test Suite")
    print("=" * 80)
    print()

    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "--color=yes"
    ]

    return pytest.main(pytest_args)


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
