#!/usr/bin/env python3
"""
Enhanced Health Check System for AI Stack Services

Implements Kubernetes-style readiness and liveness probes for all services
and their dependencies. Includes comprehensive dependency health checks,
performance metrics, and detailed health status reporting.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
import socket
import subprocess
from pathlib import Path

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

# Custom metrics for AI stack
AI_SERVICE_RESPONSE_TIME = Histogram(
    'ai_service_response_time_seconds',
    'Response time for AI services',
    ['service']
)

AI_SERVICE_ERROR_RATE = Counter(
    'ai_service_error_total',
    'Total errors from AI services',
    ['service']
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
    DEPENDENCY = "dependency"  # Are dependencies healthy?
    PERFORMANCE = "performance"  # Performance metrics


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
    weight: float = 1.0  # Weight for composite health score


class HealthChecker:
    """Comprehensive health check system"""

    def __init__(
        self,
        service_name: str,
        db_pool: Optional[asyncpg.Pool] = None,
        qdrant_client: Optional[QdrantClient] = None,
        redis_client: Optional[redis_asyncio.Redis] = None,
        external_services: Optional[Dict[str, str]] = None,  # {name: url}
    ):
        self.service_name = service_name
        self.db_pool = db_pool
        self.qdrant_client = qdrant_client
        self.redis_client = redis_client
        self.external_services = external_services or {}

        self._startup_complete = False
        self._last_liveness_check: Optional[HealthCheckResult] = None
        self._last_readiness_check: Optional[HealthCheckResult] = None
        self._last_dependency_check: Optional[HealthCheckResult] = None
        self._last_performance_check: Optional[HealthCheckResult] = None
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
                timeout=5.0,
                weight=1.0
            )

        if self.qdrant_client:
            self.register_dependency_check(
                name="qdrant",
                check_fn=self._check_qdrant,
                critical=True,
                timeout=5.0,
                weight=1.0
            )

        if self.redis_client:
            self.register_dependency_check(
                name="redis",
                check_fn=self._check_redis,
                critical=False,  # Redis is often used for caching, not critical
                timeout=3.0,
                weight=0.5
            )

        # Add external services
        for name, url in self.external_services.items():
            self.register_dependency_check(
                name=name,
                check_fn=lambda u=url: self._check_external_service(u),
                critical=False,
                timeout=10.0,
                weight=0.8
            )

    def register_dependency_check(
        self,
        name: str,
        check_fn: Callable,
        critical: bool = True,
        timeout: float = 5.0,
        weight: float = 1.0
    ):
        """Register a custom dependency health check"""
        self._dependency_checks.append(
            DependencyHealthCheck(
                name=name,
                check_fn=check_fn,
                critical=critical,
                timeout=timeout,
                weight=weight
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

            # Check if event loop is responsive
            loop_start = time.time()
            await asyncio.sleep(0.001)
            loop_time = (time.time() - loop_start) * 1000
            
            duration_ms = (time.time() - start_time) * 1000

            result = HealthCheckResult(
                status=HealthStatus.HEALTHY,
                check_type=CheckType.LIVENESS,
                message=f"{self.service_name} is alive",
                details={
                    "service": self.service_name,
                    "event_loop_response_ms": round(loop_time, 2)
                },
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
                    "non_critical_failures": len(non_critical_failures),
                    "composite_health_score": self._calculate_composite_health(dependency_results)
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

    async def dependency_probe(self) -> HealthCheckResult:
        """
        Dependency probe - checks health of all dependencies
        """
        start_time = time.time()

        try:
            dependency_results = await self._check_all_dependencies()
            
            unhealthy_deps = [r for r in dependency_results if r["status"] != HealthStatus.HEALTHY]
            
            duration_ms = (time.time() - start_time) * 1000

            if unhealthy_deps:
                status = HealthStatus.UNHEALTHY
                message = f"{len(unhealthy_deps)} dependencies unhealthy"
            else:
                status = HealthStatus.HEALTHY
                message = f"All {len(dependency_results)} dependencies healthy"

            result = HealthCheckResult(
                status=status,
                check_type=CheckType.DEPENDENCY,
                message=message,
                details={
                    "service": self.service_name,
                    "dependencies": dependency_results,
                    "unhealthy_count": len(unhealthy_deps),
                    "composite_health_score": self._calculate_composite_health(dependency_results)
                },
                duration_ms=duration_ms
            )

            self._last_dependency_check = result
            self._update_metrics(result, success=(status == HealthStatus.HEALTHY))
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.DEPENDENCY,
                message=f"Dependency check failed: {str(e)}",
                details={"error": str(e), "service": self.service_name},
                duration_ms=duration_ms
            )
            self._update_metrics(result, success=False)
            return result

    async def performance_probe(self) -> HealthCheckResult:
        """
        Performance probe - checks performance metrics
        """
        start_time = time.time()

        try:
            # Check system resources
            cpu_usage = await self._get_cpu_usage()
            memory_usage = await self._get_memory_usage()
            disk_usage = await self._get_disk_usage()
            
            # Check service-specific metrics
            service_metrics = await self._get_service_metrics()
            
            duration_ms = (time.time() - start_time) * 1000

            # Determine status based on thresholds
            issues = []
            if cpu_usage > 80.0:
                issues.append(f"High CPU usage: {cpu_usage}%")
            if memory_usage > 85.0:
                issues.append(f"High memory usage: {memory_usage}%")
            if disk_usage > 90.0:
                issues.append(f"High disk usage: {disk_usage}%")
                
            if issues:
                status = HealthStatus.DEGRADED
                message = f"Performance issues: {', '.join(issues)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Performance within acceptable ranges"

            result = HealthCheckResult(
                status=status,
                check_type=CheckType.PERFORMANCE,
                message=message,
                details={
                    "service": self.service_name,
                    "cpu_usage_percent": cpu_usage,
                    "memory_usage_percent": memory_usage,
                    "disk_usage_percent": disk_usage,
                    "service_metrics": service_metrics
                },
                duration_ms=duration_ms
            )

            self._last_performance_check = result
            self._update_metrics(result, success=(status == HealthStatus.HEALTHY))
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                check_type=CheckType.PERFORMANCE,
                message=f"Performance check failed: {str(e)}",
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
                    "weight": dep_check.weight,
                    "message": message,
                    "error": None
                })

                # Update dependency metrics
                DEPENDENCY_HEALTH_STATUS.labels(
                    dependency=dep_check.name,
                    check_type="dependency"
                ).set(1 if is_healthy else 0)

            except asyncio.TimeoutError:
                results.append({
                    "name": dep_check.name,
                    "status": HealthStatus.UNHEALTHY,
                    "critical": dep_check.critical,
                    "weight": dep_check.weight,
                    "message": f"{dep_check.name} check timed out",
                    "error": "timeout"
                })

                DEPENDENCY_HEALTH_STATUS.labels(
                    dependency=dep_check.name,
                    check_type="dependency"
                ).set(0)

            except Exception as e:
                results.append({
                    "name": dep_check.name,
                    "status": HealthStatus.UNHEALTHY,
                    "critical": dep_check.critical,
                    "weight": dep_check.weight,
                    "message": f"{dep_check.name} check failed: {str(e)}",
                    "error": str(e)
                })

                DEPENDENCY_HEALTH_STATUS.labels(
                    dependency=dep_check.name,
                    check_type="dependency"
                ).set(0)

        return results

    def _calculate_composite_health(self, dependency_results: List[Dict[str, Any]]) -> float:
        """Calculate a composite health score based on weighted dependencies"""
        total_weight = 0.0
        healthy_weight = 0.0
        
        for dep in dependency_results:
            weight = dep.get("weight", 1.0)
            total_weight += weight
            if dep["status"] == HealthStatus.HEALTHY:
                healthy_weight += weight
                
        if total_weight == 0:
            return 100.0  # No dependencies = perfect health
            
        return (healthy_weight / total_weight) * 100.0

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

    async def _check_external_service(self, url: str) -> bool:
        """Check external service health"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                return response.status_code < 400
        except Exception:
            return False

    async def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            # Use psutil if available, otherwise parse /proc/stat
            import psutil
            return psutil.cpu_percent(interval=1)
        except ImportError:
            # Fallback: parse /proc/stat
            try:
                with open('/proc/stat', 'r') as f:
                    line = f.readline().split()
                    idle = int(line[4])
                    total = sum(int(i) for i in line[1:5])
                    
                    # Calculate CPU usage
                    usage = 100.0 - (idle * 100.0 / total)
                    return usage
            except:
                return 0.0

    async def _get_memory_usage(self) -> float:
        """Get current memory usage percentage"""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            # Fallback: parse /proc/meminfo
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = {}
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            key = parts[0].rstrip(':')
                            value = int(parts[1])
                            meminfo[key] = value
                    
                    mem_total = meminfo['MemTotal']
                    mem_free = meminfo['MemFree']
                    mem_available = meminfo['MemAvailable']
                    
                    usage = (mem_total - mem_available) * 100.0 / mem_total
                    return usage
            except:
                return 0.0

    async def _get_disk_usage(self) -> float:
        """Get current disk usage percentage"""
        try:
            import psutil
            return psutil.disk_usage('/').percent
        except ImportError:
            # Fallback: use df command
            try:
                result = subprocess.run(['df', '/'], capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    usage_str = parts[4].rstrip('%')
                    return float(usage_str)
            except:
                return 0.0

    async def _get_service_metrics(self) -> Dict[str, Any]:
        """Get service-specific metrics"""
        # This would be customized per service
        # For now, return generic metrics
        return {
            "requests_per_second": 0.0,
            "average_response_time_ms": 0.0,
            "error_rate": 0.0
        }

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
        """Get comprehensive health status summary"""
        return {
            "service": self.service_name,
            "startup_complete": self._startup_complete,
            "liveness": self._last_liveness_check.to_dict() if self._last_liveness_check else None,
            "readiness": self._last_readiness_check.to_dict() if self._last_readiness_check else None,
            "dependency": self._last_dependency_check.to_dict() if self._last_dependency_check else None,
            "performance": self._last_performance_check.to_dict() if self._last_performance_check else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependency_summary": {
                "total": len(self._dependency_checks),
                "healthy": len([dc for dc in self._dependency_checks if dc.name in [r["name"] for r in (self._last_dependency_check.details.get("dependencies", []) if self._last_dependency_check else [])] and r["status"] == HealthStatus.HEALTHY]),
                "unhealthy": len([dc for dc in self._dependency_checks if dc.name in [r["name"] for r in (self._last_dependency_check.details.get("dependencies", []) if self._last_dependency_check else [])] and r["status"] != HealthStatus.HEALTHY])
            }
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

    @app.get("/health/dependency")
    async def dependency():
        """Dependency health check endpoint"""
        result = await health_checker.dependency_probe()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return result.to_dict(), status_code

    @app.get("/health/performance")
    async def performance():
        """Performance health check endpoint"""
        result = await health_checker.performance_probe()
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

    print("Running dependency probe...")
    dependency = await health_checker.dependency_probe()
    print(f"  Status: {dependency.status.value}")
    print(f"  Message: {dependency.message}")
    print()

    print("Running performance probe...")
    performance = await health_checker.performance_probe()
    print(f"  Status: {performance.status.value}")
    print(f"  Message: {performance.message}")
    print()

    print("Health Summary:")
    import json
    print(json.dumps(health_checker.get_status_summary(), indent=2))

    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())