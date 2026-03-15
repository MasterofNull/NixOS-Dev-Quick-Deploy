"""
AI Service Health Monitoring
Provides real-time health checks and metrics for all AI stack services.
"""

import asyncio
import logging
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiohttp
import psutil

logger = logging.getLogger(__name__)

# Service definitions with health check endpoints
AI_SERVICES = {
    "ai-aidb": {
        "name": "AIDB Service",
        "health_url": "http://127.0.0.1:8002/health",
        "metrics_url": "http://127.0.0.1:8002/metrics",
        "category": "ai-core",
    },
    "ai-hybrid-coordinator": {
        "name": "Hybrid Coordinator",
        "health_url": "http://127.0.0.1:8003/health",
        "metrics_url": "http://127.0.0.1:8003/stats",
        "category": "ai-core",
    },
    "ai-ralph-wiggum": {
        "name": "Ralph Wiggum",
        "health_url": "http://127.0.0.1:8004/health",
        "category": "ai-core",
    },
    "ai-switchboard": {
        "name": "AI Switchboard",
        "health_url": "http://127.0.0.1:8085/health",
        "category": "ai-core",
    },
    "qdrant": {
        "name": "Qdrant Vector DB",
        "health_url": "http://127.0.0.1:6333/",
        "category": "storage",
    },
    "llama-cpp": {
        "name": "Llama.cpp (Chat)",
        "health_url": "http://127.0.0.1:8080/health",
        "category": "llm",
    },
    "llama-cpp-embed": {
        "name": "Llama.cpp (Embeddings)",
        "health_url": "http://127.0.0.1:8081/health",
        "category": "llm",
    },
    "redis-mcp": {
        "name": "Redis MCP",
        "port": 6379,
        "category": "storage",
    },
    "postgresql": {
        "name": "PostgreSQL",
        "port": 5432,
        "category": "storage",
    },
    "prometheus": {
        "name": "Prometheus",
        "health_url": "http://127.0.0.1:9090/-/ready",
        "category": "observability",
    },
    "prometheus-node-exporter": {
        "name": "Node Exporter",
        "health_url": "http://127.0.0.1:9100/metrics",
        "category": "observability",
    },
    "ai-otel-collector": {
        "name": "OpenTelemetry Collector",
        "health_url": "http://127.0.0.1:13133/",
        "category": "observability",
    },
}


class AIServiceHealthMonitor:
    """Monitor health and metrics for all AI stack services."""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._service_pids: Dict[str, int] = {}

    async def initialize(self):
        """Initialize async resources."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            )

    async def close(self):
        """Close async resources."""
        if self._session:
            await self._session.close()
            self._session = None

    async def check_all_services(self) -> Dict[str, Any]:
        """Check health of all AI services."""
        await self.initialize()

        tasks = {
            service_id: self._check_service_health(service_id, config)
            for service_id, config in AI_SERVICES.items()
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        service_health = {}
        for service_id, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Health check failed for {service_id}: {result}")
                service_health[service_id] = {
                    "status": "error",
                    "error": str(result),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            else:
                service_health[service_id] = result

        # Calculate aggregate health
        healthy_count = sum(1 for s in service_health.values() if s["status"] == "healthy")
        total_count = len(service_health)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "services": service_health,
            "aggregate": {
                "healthy": healthy_count,
                "total": total_count,
                "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0,
                "status": "healthy" if healthy_count == total_count else "degraded" if healthy_count > 0 else "unhealthy",
            },
        }

    async def _check_service_health(self, service_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check health of a single service."""
        # Get systemd status
        systemd_status = await self._get_systemd_status(service_id)

        # Get HTTP health if available
        http_health = None
        if "health_url" in config:
            http_health = await self._check_http_health(config["health_url"])

        # Get process metrics
        process_metrics = await self._get_process_metrics(service_id)

        # Determine overall status
        is_healthy = (
            systemd_status["active"]
            and (http_health is None or http_health["healthy"])
        )

        return {
            "name": config["name"],
            "status": "healthy" if is_healthy else "unhealthy",
            "category": config["category"],
            "systemd": systemd_status,
            "http_health": http_health,
            "metrics": process_metrics,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _get_systemd_status(self, service_id: str) -> Dict[str, Any]:
        """Get systemd status for a service."""
        unit = service_id if service_id.endswith(".service") else f"{service_id}.service"

        try:
            # Check if service is active
            is_active = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                check=False,
            )

            # Get detailed status
            status_output = subprocess.run(
                ["systemctl", "status", unit, "--no-pager", "-l"],
                capture_output=True,
                text=True,
                check=False,
            )

            # Get main PID
            show_output = subprocess.run(
                ["systemctl", "show", unit, "--property=MainPID", "--value"],
                capture_output=True,
                text=True,
                check=False,
            )

            main_pid = 0
            try:
                main_pid = int(show_output.stdout.strip())
                self._service_pids[service_id] = main_pid
            except (ValueError, AttributeError):
                pass

            return {
                "active": is_active.returncode == 0,
                "status": is_active.stdout.strip(),
                "main_pid": main_pid if main_pid > 0 else None,
            }

        except Exception as e:
            logger.error(f"Failed to get systemd status for {service_id}: {e}")
            return {
                "active": False,
                "status": "unknown",
                "error": str(e),
            }

    async def _check_http_health(self, url: str) -> Dict[str, Any]:
        """Check HTTP health endpoint."""
        if not self._session:
            await self.initialize()

        try:
            async with self._session.get(url) as response:
                return {
                    "healthy": response.status in (200, 204),
                    "status_code": response.status,
                    "response_time_ms": int(response.headers.get("X-Response-Time", 0)),
                }
        except asyncio.TimeoutError:
            return {
                "healthy": False,
                "error": "timeout",
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }

    async def _get_process_metrics(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get CPU and memory metrics for a service."""
        pid = self._service_pids.get(service_id)
        if not pid or pid <= 0:
            return None

        try:
            process = psutil.Process(pid)

            # Get CPU percent (non-blocking)
            cpu_percent = process.cpu_percent(interval=0.1)

            # Get memory info
            memory_info = process.memory_info()

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_info.rss / 1024 / 1024, 2),
                "memory_percent": round(process.memory_percent(), 2),
                "num_threads": process.num_threads(),
                "status": process.status(),
            }

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.debug(f"Could not get process metrics for {service_id}: {e}")
            return None

    async def get_service_metrics(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed metrics for a specific service."""
        if service_id not in AI_SERVICES:
            return None

        config = AI_SERVICES[service_id]
        return await self._check_service_health(service_id, config)

    async def get_category_health(self, category: str) -> Dict[str, Any]:
        """Get aggregated health for services in a category."""
        services_in_category = {
            sid: config
            for sid, config in AI_SERVICES.items()
            if config["category"] == category
        }

        if not services_in_category:
            return {"error": "Category not found"}

        health_results = await asyncio.gather(
            *[
                self._check_service_health(sid, config)
                for sid, config in services_in_category.items()
            ],
            return_exceptions=True,
        )

        healthy_count = sum(
            1 for result in health_results
            if not isinstance(result, Exception) and result["status"] == "healthy"
        )

        return {
            "category": category,
            "total_services": len(services_in_category),
            "healthy_services": healthy_count,
            "health_percentage": (healthy_count / len(services_in_category) * 100),
            "status": "healthy" if healthy_count == len(services_in_category) else "degraded",
            "services": {
                sid: result if not isinstance(result, Exception) else {"status": "error", "error": str(result)}
                for sid, result in zip(services_in_category.keys(), health_results)
            },
        }


# Singleton instance
_health_monitor: Optional[AIServiceHealthMonitor] = None


async def get_health_monitor() -> AIServiceHealthMonitor:
    """Get singleton health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = AIServiceHealthMonitor()
        await _health_monitor.initialize()
    return _health_monitor
