#!/usr/bin/env python3
"""
Comprehensive Health Check System

Implements Kubernetes-style readiness and liveness probes for all services
and their dependencies. Helps detect and prevent issues proactively.

Features:
- Readiness probes (ready to accept traffic)
- Liveness probes (still alive, not deadlocked)
- Dependency health checks (DB, Qdrant, Redis, etc.)
- Prometheus metrics integration
- Detailed health status reporting
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

import asyncpg
import httpx
from prometheus_client import Counter, Gauge, Histogram
from qdrant_client import QdrantClient
from redis import asyncio as redis_asyncio


# Prometheus metrics
HEALTH_CHECK_TOTAL = Counter(
    'health_check_total',
    'Total health checks performed',
    ['service', 'check_type', 'status']
)

HEALTH_CHECK_DURATION = Histogram(
    'health_check_duration_seconds',
    'Health check duration',
    ['service', 'check_type']
)

SERVICE_HEALTH_STATUS = Gauge(
    'service_health_status',
    'Service health status (1=healthy, 0=unhealthy)',
    ['service', 'check_type']
)

DEPENDENCY_HEALTH_STATUS = Gauge(
    'dependency_health_status',
    'Dependency health status (1=healthy, 0=unhealthy)',
    ['dependency', 'check_type']
)


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """Health check types"""
    LIVENESS = "liveness"      # Is the service alive? (not deadlocked)
    READINESS = "readiness"    # Is the service ready to accept traffic?
    STARTUP = "startup"        # Has the service finished starting up?


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    status: HealthStatus
    check_type: CheckType
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "check_type": self.check_type.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms
        }


@dataclass
class DependencyHealthCheck:
    """Health check for a dependency"""
    name: str
    check_fn: Callable
    critical: bool = True  # If True, failure makes service unhealthy
    timeout: float = 5.0


class HealthChecker:
    """Comprehensive health check system"""

    def __init__(
        self,
        service_name: str,
        db_pool: Optional[asyncpg.Pool] = None,
        qdrant_client: Optional[QdrantClient] = None,
        redis_client: Optional[redis_asyncio.Redis] = None,
    ):
        self.service_name = service_name
        self.db_pool = db_pool
        self.qdrant_client = qdrant_client
        self.redis_client = redis_client

        self._startup_complete = False
        self._last_liveness_check: Optional[HealthCheckResult] = None
        self._last_readiness_check: Optional[HealthCheckResult] = None
        self._dependency_checks: List[DependencyHealthCheck] = []

        # Register default dependency checks
        self._register_default_checks()

    def _register_default_checks(self):
        """Register default dependency health checks"""
        if self.db_pool:
            self.register_dependency_check(
                name="postgresql",
                check_fn=self._check_postgresql,
                critical=True,
                timeout=5.0
            )

        if self.qdrant_client:
            self.register_dependency_check(
                name="qdrant",
                check_fn=self._check_qdrant,
                critical=True,
                timeout=5.0
            )

        if self.redis_client:
            self.register_dependency_check(
                name="redis",
                check_fn=self._check_redis,
                critical=False,  # Redis is often used for caching, not critical
                timeout=3.0
            )

    def register_dependency_check(
        self,
        name: str,
        check_fn: Callable,
        critical: bool = True,
        timeout: float = 5.0
    ):
        """Register a custom dependency health check"""
        self._dependency_checks.append(
            DependencyHealthCheck(
                name=name,
                check_fn=check_fn,
                critical=critical,
                timeout=timeout
            )
        )

    async def liveness_probe(self) -> HealthCheckResult:
        """
        Liveness probe - checks if service is alive (not deadlocked)

        Used by Kubernetes to determine if container should be restarted.
        Should be fast and simple - just checks if the service can respond.
        """
        start_time = time.time()

        try:
            # Simple check - can we execute Python code?
            _ = 1 + 1

            # Check if we're not in a deadlock state
            # (this will timeout if deadlocked)
            await asyncio.wait_for(
                asyncio.sleep(0.001),
                timeout=1.0
            )

            duration_ms = (time.time() - start_time) * 1000

            result = HealthCheckResult(
                status=HealthStatus.HEALTHY,
                check_type=CheckType.LIVENESS,
                message=f"{self.service_name} is alive",
                details={"service": self.service_name},
                duration_ms=duration_ms
            )

            self._last_liveness_check = result
            self._update_metrics(result, success=True)
            return result

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.LIVENESS,
                message=f"{self.service_name} appears to be deadlocked",
                details={"error": "timeout", "service": self.service_name},
                duration_ms=duration_ms
            )
            self._update_metrics(result, success=False)
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.LIVENESS,
                message=f"{self.service_name} liveness check failed: {str(e)}",
                details={"error": str(e), "service": self.service_name},
                duration_ms=duration_ms
            )
            self._update_metrics(result, success=False)
            return result

    async def readiness_probe(self) -> HealthCheckResult:
        """
        Readiness probe - checks if service is ready to accept traffic

        Used by Kubernetes to determine if pod should receive traffic.
        Checks all critical dependencies are healthy.
        """
        start_time = time.time()

        try:
            # Check all dependencies
            dependency_results = await self._check_all_dependencies()

            # Count failures
            critical_failures = [
                r for r in dependency_results
                if r["critical"] and r["status"] != HealthStatus.HEALTHY
            ]

            non_critical_failures = [
                r for r in dependency_results
                if not r["critical"] and r["status"] != HealthStatus.HEALTHY
            ]

            duration_ms = (time.time() - start_time) * 1000

            # Determine overall status
            if critical_failures:
                status = HealthStatus.UNHEALTHY
                message = f"{self.service_name} is not ready: {len(critical_failures)} critical dependencies unhealthy"
            elif non_critical_failures:
                status = HealthStatus.DEGRADED
                message = f"{self.service_name} is degraded: {len(non_critical_failures)} non-critical dependencies unhealthy"
            else:
                status = HealthStatus.HEALTHY
                message = f"{self.service_name} is ready"

            result = HealthCheckResult(
                status=status,
                check_type=CheckType.READINESS,
                message=message,
                details={
                    "service": self.service_name,
                    "dependencies": dependency_results,
                    "critical_failures": len(critical_failures),
                    "non_critical_failures": len(non_critical_failures)
                },
                duration_ms=duration_ms
            )

            self._last_readiness_check = result
            self._update_metrics(result, success=(status != HealthStatus.UNHEALTHY))
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.READINESS,
                message=f"{self.service_name} readiness check failed: {str(e)}",
                details={"error": str(e), "service": self.service_name},
                duration_ms=duration_ms
            )
            self._update_metrics(result, success=False)
            return result

    async def startup_probe(self) -> HealthCheckResult:
        """
        Startup probe - checks if service has finished starting up

        Used by Kubernetes to know when to start liveness/readiness probes.
        More lenient timeout for slow-starting services.
        """
        start_time = time.time()

        try:
            # Check if all initialization is complete
            if not self._startup_complete:
                # Perform startup checks
                await self._verify_startup_complete()

            duration_ms = (time.time() - start_time) * 1000

            result = HealthCheckResult(
                status=HealthStatus.HEALTHY if self._startup_complete else HealthStatus.UNHEALTHY,
                check_type=CheckType.STARTUP,
                message=f"{self.service_name} startup {'complete' if self._startup_complete else 'in progress'}",
                details={"service": self.service_name, "startup_complete": self._startup_complete},
                duration_ms=duration_ms
            )

            self._update_metrics(result, success=self._startup_complete)
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.STARTUP,
                message=f"{self.service_name} startup check failed: {str(e)}",
                details={"error": str(e), "service": self.service_name},
                duration_ms=duration_ms
            )
            self._update_metrics(result, success=False)
            return result

    async def _verify_startup_complete(self):
        """Verify all startup tasks are complete"""
        # Check database schema is initialized
        if self.db_pool:
            async with self.db_pool.acquire() as conn:
                # Try a simple query
                await conn.fetchval("SELECT 1")

        # Check Qdrant collections exist
        if self.qdrant_client:
            try:
                collections = self.qdrant_client.get_collections()
                # Expect at least one collection
                if not collections.collections:
                    raise ValueError("No Qdrant collections found")
            except Exception as e:
                raise ValueError(f"Qdrant not ready: {e}")

        # Mark startup as complete
        self._startup_complete = True

    async def _check_all_dependencies(self) -> List[Dict[str, Any]]:
        """Check all registered dependencies"""
        results = []

        for dep_check in self._dependency_checks:
            try:
                # Run check with timeout
                is_healthy = await asyncio.wait_for(
                    dep_check.check_fn(),
                    timeout=dep_check.timeout
                )

                status = HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY
                message = f"{dep_check.name} is {'healthy' if is_healthy else 'unhealthy'}"

                results.append({
                    "name": dep_check.name,
                    "status": status,
                    "critical": dep_check.critical,
                    "message": message,
                    "error": None
                })

                # Update dependency metrics
                DEPENDENCY_HEALTH_STATUS.labels(
                    dependency=dep_check.name,
                    check_type="readiness"
                ).set(1 if is_healthy else 0)

            except asyncio.TimeoutError:
                results.append({
                    "name": dep_check.name,
                    "status": HealthStatus.UNHEALTHY,
                    "critical": dep_check.critical,
                    "message": f"{dep_check.name} check timed out",
                    "error": "timeout"
                })

                DEPENDENCY_HEALTH_STATUS.labels(
                    dependency=dep_check.name,
                    check_type="readiness"
                ).set(0)

            except Exception as e:
                results.append({
                    "name": dep_check.name,
                    "status": HealthStatus.UNHEALTHY,
                    "critical": dep_check.critical,
                    "message": f"{dep_check.name} check failed: {str(e)}",
                    "error": str(e)
                })

                DEPENDENCY_HEALTH_STATUS.labels(
                    dependency=dep_check.name,
                    check_type="readiness"
                ).set(0)

        return results

    async def _check_postgresql(self) -> bool:
        """Check PostgreSQL health"""
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception:
            return False

    async def _check_qdrant(self) -> bool:
        """Check Qdrant health"""
        try:
            # Try to get collections (lightweight operation)
            collections = self.qdrant_client.get_collections()
            return True
        except Exception:
            return False

    async def _check_redis(self) -> bool:
        """Check Redis health"""
        try:
            pong = await self.redis_client.ping()
            return pong == True
        except Exception:
            return False

    def _update_metrics(self, result: HealthCheckResult, success: bool):
        """Update Prometheus metrics"""
        HEALTH_CHECK_TOTAL.labels(
            service=self.service_name,
            check_type=result.check_type.value,
            status=result.status.value
        ).inc()

        HEALTH_CHECK_DURATION.labels(
            service=self.service_name,
            check_type=result.check_type.value
        ).observe(result.duration_ms / 1000)

        SERVICE_HEALTH_STATUS.labels(
            service=self.service_name,
            check_type=result.check_type.value
        ).set(1 if success else 0)

    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all health checks"""
        return {
            "service": self.service_name,
            "startup_complete": self._startup_complete,
            "liveness": self._last_liveness_check.to_dict() if self._last_liveness_check else None,
            "readiness": self._last_readiness_check.to_dict() if self._last_readiness_check else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Example integration with FastAPI
def create_health_endpoints(app, health_checker: HealthChecker):
    """Create health check endpoints for FastAPI"""

    @app.get("/health/live")
    async def liveness():
        """Liveness probe endpoint"""
        result = await health_checker.liveness_probe()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return result.to_dict(), status_code

    @app.get("/health/ready")
    async def readiness():
        """Readiness probe endpoint"""
        result = await health_checker.readiness_probe()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return result.to_dict(), status_code

    @app.get("/health/startup")
    async def startup():
        """Startup probe endpoint"""
        result = await health_checker.startup_probe()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return result.to_dict(), status_code

    @app.get("/health")
    async def health_summary():
        """Comprehensive health summary"""
        return health_checker.get_status_summary()


async def main():
    """Example usage"""
    # Create DB pool
    db_pool = await asyncpg.create_pool(
        host="localhost",
        database="aidb",
        user="aidb",
        password="aidb_password"
    )

    # Create Qdrant client
    qdrant = QdrantClient(host="localhost", port=6333)

    # Create health checker
    health_checker = HealthChecker(
        service_name="aidb",
        db_pool=db_pool,
        qdrant_client=qdrant
    )

    # Run health checks
    print("Running liveness probe...")
    liveness = await health_checker.liveness_probe()
    print(f"  Status: {liveness.status.value}")
    print(f"  Message: {liveness.message}")
    print()

    print("Running readiness probe...")
    readiness = await health_checker.readiness_probe()
    print(f"  Status: {readiness.status.value}")
    print(f"  Message: {readiness.message}")
    print(f"  Details: {readiness.details}")
    print()

    print("Health Summary:")
    import json
    print(json.dumps(health_checker.get_status_summary(), indent=2))

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
