#!/usr/bin/env python3
"""
Dashboard Backend API Server
Aggregates health and metrics from all services for the dashboard.
Port: 8889
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from aiohttp import web, ClientSession, ClientTimeout
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service endpoints
SERVICES = {
    "ralph": "http://localhost:8098",
    "hybrid": "http://localhost:8092",
    "aidb": "http://localhost:8091",
    "qdrant": "http://localhost:6333",
    "postgresql": "http://localhost:5432",
    "prometheus": "http://localhost:9090",
}

# Timeouts for all external requests
REQUEST_TIMEOUT = ClientTimeout(total=5)


class DashboardAPI:
    def __init__(self):
        self.session: Optional[ClientSession] = None

    async def setup(self):
        """Initialize aiohttp client session"""
        self.session = ClientSession(timeout=REQUEST_TIMEOUT)
        logger.info("Dashboard API initialized")

    async def cleanup(self):
        """Cleanup aiohttp client session"""
        if self.session:
            await self.session.close()

    async def fetch_with_fallback(self, url: str, fallback: Any = None) -> Any:
        """Fetch URL with error handling and fallback"""
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"Non-200 status from {url}: {resp.status}")
                    return fallback
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {url}")
            return fallback
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
            return fallback

    async def get_service_health(self, service_name: str, base_url: str) -> Dict[str, Any]:
        """Get health status for a single service"""
        health_data = {
            "name": service_name,
            "status": "unknown",
            "url": base_url,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Try /health endpoint
        health = await self.fetch_with_fallback(f"{base_url}/health")
        if health:
            health_data["status"] = health.get("status", "healthy")
            health_data["details"] = health
        else:
            health_data["status"] = "unhealthy"

        return health_data

    async def handle_services(self, request: web.Request) -> web.Response:
        """GET /api/services - List all services with health status"""
        services_health = []

        for service_name, base_url in SERVICES.items():
            if service_name in ["prometheus", "postgresql"]:
                # These don't have standard /health endpoints
                continue
            health = await self.get_service_health(service_name, base_url)
            services_health.append(health)

        return web.json_response({
            "services": services_health,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def handle_system_metrics(self, request: web.Request) -> web.Response:
        """GET /api/metrics/system - System resource usage"""
        # Query Prometheus for container metrics
        prom_queries = {
            "cpu_usage": 'sum(rate(container_cpu_usage_seconds_total[5m])) by (name)',
            "memory_usage": 'sum(container_memory_usage_bytes) by (name)',
            "memory_limit": 'sum(container_spec_memory_limit_bytes) by (name)',
        }

        metrics = {}
        prom_base = SERVICES["prometheus"]

        for metric_name, query in prom_queries.items():
            url = f"{prom_base}/api/v1/query?query={query}"
            result = await self.fetch_with_fallback(url, {})
            metrics[metric_name] = result.get("data", {}).get("result", [])

        return web.json_response({
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def handle_learning_stats(self, request: web.Request) -> web.Response:
        """GET /api/stats/learning - Continuous learning statistics"""
        # Fetch from hybrid coordinator
        hybrid_base = SERVICES["hybrid"]
        stats = await self.fetch_with_fallback(
            f"{hybrid_base}/learning/stats",
            {
                "checkpoints": {"total": 0, "last_checkpoint": None},
                "backpressure": {"unprocessed_mb": 0, "paused": False},
                "deduplication": {"total_patterns": 0, "duplicates_found": 0, "unique_patterns": 0}
            }
        )

        return web.json_response(stats)

    async def handle_circuit_breakers(self, request: web.Request) -> web.Response:
        """GET /api/stats/circuit-breakers - Circuit breaker states"""
        # Fetch from hybrid coordinator health endpoint
        hybrid_base = SERVICES["hybrid"]
        health = await self.fetch_with_fallback(f"{hybrid_base}/health", {})

        circuit_breakers = health.get("circuit_breakers", {})

        return web.json_response({
            "circuit_breakers": circuit_breakers,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def handle_health_aggregate(self, request: web.Request) -> web.Response:
        """GET /api/health/aggregate - Combined health from all services"""
        health_checks = {}

        # Ralph Wiggum
        ralph_health = await self.fetch_with_fallback(f"{SERVICES['ralph']}/health")
        health_checks["ralph"] = {
            "status": ralph_health.get("status", "unknown") if ralph_health else "unhealthy",
            "details": ralph_health or {}
        }

        # Hybrid Coordinator
        hybrid_health = await self.fetch_with_fallback(f"{SERVICES['hybrid']}/health")
        health_checks["hybrid"] = {
            "status": hybrid_health.get("status", "unknown") if hybrid_health else "unhealthy",
            "details": hybrid_health or {}
        }

        # AIDB
        aidb_health = await self.fetch_with_fallback(f"{SERVICES['aidb']}/health")
        health_checks["aidb"] = {
            "status": aidb_health.get("status", "unknown") if aidb_health else "unhealthy",
            "details": aidb_health or {}
        }

        # Qdrant
        qdrant_health = await self.fetch_with_fallback(f"{SERVICES['qdrant']}/health")
        health_checks["qdrant"] = {
            "status": "healthy" if qdrant_health else "unhealthy",
            "details": qdrant_health or {}
        }

        # Overall status
        all_healthy = all(
            check["status"] == "healthy"
            for check in health_checks.values()
        )

        return web.json_response({
            "overall_status": "healthy" if all_healthy else "degraded",
            "services": health_checks,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def handle_ralph_stats(self, request: web.Request) -> web.Response:
        """GET /api/ralph/stats - Ralph Wiggum task statistics"""
        ralph_base = SERVICES["ralph"]

        # Get Ralph stats
        stats = await self.fetch_with_fallback(
            f"{ralph_base}/stats",
            {
                "active_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "total_iterations": 0
            }
        )

        return web.json_response(stats)

    async def handle_ralph_tasks(self, request: web.Request) -> web.Response:
        """GET /api/ralph/tasks - List Ralph tasks"""
        ralph_base = SERVICES["ralph"]

        # Get active tasks
        tasks = await self.fetch_with_fallback(f"{ralph_base}/tasks", [])

        return web.json_response({
            "tasks": tasks,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def handle_prometheus_proxy(self, request: web.Request) -> web.Response:
        """GET /api/prometheus/* - Proxy to Prometheus"""
        # Extract the path after /api/prometheus/
        prom_path = request.match_info.get('path', '')
        query_string = request.query_string

        prom_url = f"{SERVICES['prometheus']}/{prom_path}"
        if query_string:
            prom_url += f"?{query_string}"

        result = await self.fetch_with_fallback(prom_url, {})
        return web.json_response(result)

    async def handle_config_get(self, request: web.Request) -> web.Response:
        """GET /api/config - Get current configuration"""
        config_file = Path.home() / '.local/share/nixos-ai-stack/config/config.yaml'

        if config_file.exists():
            try:
                import yaml
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                return web.json_response(config or {})
            except Exception as e:
                logger.error(f"Error reading config: {e}")
                return web.json_response({"error": str(e)}, status=500)
        else:
            # Return defaults
            return web.json_response({
                "rate_limit": 150,
                "checkpoint_interval": 100,
                "backpressure_threshold_mb": 100,
                "log_level": "INFO"
            })

    async def handle_config_post(self, request: web.Request) -> web.Response:
        """POST /api/config - Update configuration"""
        try:
            new_config = await request.json()
            config_file = Path.home() / '.local/share/nixos-ai-stack/config/config.yaml'
            config_file.parent.mkdir(parents=True, exist_ok=True)

            import yaml
            with open(config_file, 'w') as f:
                yaml.dump(new_config, f)

            return web.json_response({
                "status": "success",
                "message": "Configuration updated",
                "config": new_config
            })
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return web.json_response({"error": str(e)}, status=500)


async def create_app() -> web.Application:
    """Create and configure the aiohttp application"""
    api = DashboardAPI()

    app = web.Application()

    # Setup/cleanup
    app.on_startup.append(lambda app: api.setup())
    app.on_cleanup.append(lambda app: api.cleanup())

    # Routes
    app.router.add_get('/api/services', api.handle_services)
    app.router.add_get('/api/metrics/system', api.handle_system_metrics)
    app.router.add_get('/api/stats/learning', api.handle_learning_stats)
    app.router.add_get('/api/stats/circuit-breakers', api.handle_circuit_breakers)
    app.router.add_get('/api/health/aggregate', api.handle_health_aggregate)
    app.router.add_get('/api/ralph/stats', api.handle_ralph_stats)
    app.router.add_get('/api/ralph/tasks', api.handle_ralph_tasks)
    app.router.add_get('/api/config', api.handle_config_get)
    app.router.add_post('/api/config', api.handle_config_post)
    app.router.add_get('/api/prometheus/{path:.*}', api.handle_prometheus_proxy)

    # CORS middleware
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
        return middleware_handler

    app.middlewares.append(cors_middleware)

    return app


def main():
    """Main entry point"""
    logger.info("Starting Dashboard API Server on port 8889")
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=8889)


if __name__ == '__main__':
    main()
