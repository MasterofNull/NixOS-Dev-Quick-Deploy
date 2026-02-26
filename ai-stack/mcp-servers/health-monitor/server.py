#!/usr/bin/env python3
"""
Health Monitoring MCP Server
Provides continuous health monitoring for the NixOS Hybrid AI Learning Stack

This MCP server exposes tools for:
- Real-time service health checks
- Dashboard data collection
- Metric aggregation
- Alert generation
- Trend analysis

Version: 1.0.0
Created: 2025-12-21
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("health-monitor")

# Environment configuration
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", os.getcwd()))
DASHBOARD_DATA_DIR = Path.home() / ".local/share/nixos-system-dashboard"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Service configuration
SERVICES = {
    "qdrant": {"url": os.getenv("QDRANT_HEALTH_URL", f"{os.getenv('QDRANT_URL', 'http://127.0.0.1:6333')}/healthz"), "name": "Qdrant Vector DB"},
    "llama_cpp": {"url": os.getenv("LLAMA_CPP_HEALTH_URL", f"{os.getenv('LLAMA_CPP_BASE_URL', 'http://127.0.0.1:8080')}/health"), "name": "llama.cpp"},
    "open_webui": {"url": os.getenv("OPEN_WEBUI_HEALTH_URL", "http://127.0.0.1:3000"), "name": "Open WebUI"},
    "aidb": {"url": os.getenv("AIDB_HEALTH_URL", f"{os.getenv('AIDB_URL', 'http://127.0.0.1:8002')}/health"), "name": "AIDB MCP Server"},
    "hybrid_coordinator": {"url": os.getenv("HYBRID_HEALTH_URL", f"{os.getenv('HYBRID_COORDINATOR_URL', 'http://127.0.0.1:8003')}/health"), "name": "Hybrid Coordinator"},
    "mindsdb": {"url": os.getenv("MINDSDB_HEALTH_URL", "http://127.0.0.1:47334"), "name": "MindsDB"},
}

# Create MCP server instance
app = Server("health-monitor")


class HealthMonitor:
    """Core health monitoring functionality"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=5.0)
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 30  # seconds

    async def check_service(self, service_id: str) -> Dict[str, Any]:
        """Check health of a single service"""
        if service_id not in SERVICES:
            return {"error": f"Unknown service: {service_id}"}

        service = SERVICES[service_id]
        result = {
            "service": service_id,
            "name": service["name"],
            "url": service["url"],
            "status": "offline",
            "response_time_ms": None,
            "checked_at": datetime.now().isoformat(),
        }

        try:
            start = time.time()
            response = await self.client.get(service["url"])
            elapsed = (time.time() - start) * 1000  # convert to ms

            result["status"] = "online" if response.status_code == 200 else "degraded"
            result["response_time_ms"] = round(elapsed, 2)
            result["status_code"] = response.status_code

        except Exception as e:
            result["error"] = str(e)
            logger.debug(f"Service {service_id} check failed: {e}")

        return result

    async def check_all_services(self) -> List[Dict[str, Any]]:
        """Check health of all services"""
        tasks = [self.check_service(sid) for sid in SERVICES.keys()]
        results = await asyncio.gather(*tasks)
        return list(results)

    def read_dashboard_file(self, filename: str) -> Dict[str, Any]:
        """Read a dashboard JSON file"""
        file_path = DASHBOARD_DATA_DIR / filename

        if not file_path.exists():
            return {"error": f"File not found: {filename}"}

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            return {"error": f"Failed to read {filename}: {str(e)}"}

    def regenerate_dashboard_data(self) -> Dict[str, Any]:
        """Legacy dashboard collector is deprecated in declarative mode."""
        return {
            "success": False,
            "deprecated": True,
            "error": "Legacy dashboard regeneration script is deprecated",
            "next_steps": [
                "Use declarative monitoring services (Prometheus/Node Exporter)",
                "Check dashboard status with systemctl status command-center-dashboard.service"
            ],
            "timestamp": datetime.now().isoformat()
        }

    def calculate_health_score(self, services: List[Dict[str, Any]]) -> float:
        """Calculate overall health score (0-100)"""
        if not services:
            return 0.0

        online_count = sum(1 for s in services if s.get("status") == "online")
        return round((online_count / len(services)) * 100, 1)

    def get_critical_issues(self) -> List[str]:
        """Identify critical issues requiring attention"""
        issues = []

        # Check if dashboard data is stale
        system_file = DASHBOARD_DATA_DIR / "system.json"
        if system_file.exists():
            data = self.read_dashboard_file("system.json")
            if "timestamp" in data:
                timestamp = datetime.fromisoformat(data["timestamp"])
                age_minutes = (datetime.now() - timestamp).total_seconds() / 60
                if age_minutes > 15:
                    issues.append(f"Dashboard data is stale ({age_minutes:.1f} minutes old)")

        # Check RAG collections
        rag_data = self.read_dashboard_file("rag-collections.json")
        if "collections" in rag_data:
            empty_collections = [
                c["name"] for c in rag_data["collections"]
                if c.get("points", 0) == 0
            ]
            if empty_collections:
                issues.append(f"Empty RAG collections: {', '.join(empty_collections)}")

        return issues


# Initialize monitor
monitor = HealthMonitor()


# MCP Tool Definitions

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available health monitoring tools"""
    return [
        Tool(
            name="check_service_health",
            description="Check health status of a specific AI stack service",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "Service ID to check",
                        "enum": list(SERVICES.keys())
                    }
                },
                "required": ["service_id"]
            }
        ),
        Tool(
            name="check_all_services",
            description="Check health status of all AI stack services",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_dashboard_metrics",
            description="Get metrics from a specific dashboard data file",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Dashboard JSON filename",
                        "enum": [
                            "system.json", "llm.json", "rag-collections.json",
                            "learning-metrics.json", "token-savings.json",
                            "hybrid-coordinator.json", "network.json",
                            "security.json", "database.json", "persistence.json",
                            "telemetry.json", "feedback.json", "proof.json",
                            "config.json", "links.json"
                        ]
                    }
                },
                "required": ["filename"]
            }
        ),
        Tool(
            name="regenerate_dashboard",
            description="Regenerate all dashboard data files",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_health_summary",
            description="Get comprehensive health summary with scores and recommendations",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_critical_issues",
            description="Get list of critical issues requiring immediate attention",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls"""

    try:
        if name == "check_service_health":
            service_id = arguments["service_id"]
            result = await monitor.check_service(service_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "check_all_services":
            results = await monitor.check_all_services()
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        elif name == "get_dashboard_metrics":
            filename = arguments["filename"]
            data = monitor.read_dashboard_file(filename)
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "regenerate_dashboard":
            result = monitor.regenerate_dashboard_data()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_health_summary":
            # Get all service health
            services = await monitor.check_all_services()
            health_score = monitor.calculate_health_score(services)

            # Get RAG collection stats
            rag_data = monitor.read_dashboard_file("rag-collections.json")

            # Get learning metrics
            learning_data = monitor.read_dashboard_file("learning-metrics.json")

            # Get token savings
            token_data = monitor.read_dashboard_file("token-savings.json")

            summary = {
                "timestamp": datetime.now().isoformat(),
                "health_score": health_score,
                "services": {
                    "total": len(services),
                    "online": sum(1 for s in services if s.get("status") == "online"),
                    "offline": sum(1 for s in services if s.get("status") == "offline"),
                    "degraded": sum(1 for s in services if s.get("status") == "degraded"),
                },
                "rag_collections": {
                    "total": rag_data.get("total_collections", 0),
                    "total_points": rag_data.get("total_points", 0),
                },
                "learning": {
                    "total_interactions": learning_data.get("interactions", {}).get("total", 0),
                    "learning_rate": learning_data.get("patterns", {}).get("learning_rate", 0),
                },
                "token_savings": {
                    "local_percent": token_data.get("routing", {}).get("local_percent", 0),
                    "estimated_savings_usd": token_data.get("cost", {}).get("estimated_savings_usd", 0),
                },
                "critical_issues": monitor.get_critical_issues()
            }

            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        elif name == "get_critical_issues":
            issues = monitor.get_critical_issues()
            return [TextContent(type="text", text=json.dumps({"issues": issues}, indent=2))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    except Exception as e:
        logger.error(f"Tool execution error: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    """Run the MCP server"""
    logger.info("Starting Health Monitoring MCP Server")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"Dashboard data: {DASHBOARD_DATA_DIR}")
    logger.info(f"Monitoring {len(SERVICES)} services")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
