#!/usr/bin/env python3
"""
telemetry/health_spider_handlers.py — Integration between HealthSpider and Dashboard.
"""

import logging
import json
from pathlib import Path
from aiohttp import web

logger = logging.getLogger("health-spider-handlers")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

async def handle_get_anomalies(request: web.Request) -> web.Response:
    """Returns the most recent remediation records."""
    remediation_dir = REPO_ROOT / ".reports" / "remediation"
    anomalies = []
    
    if remediation_dir.exists():
        for f in remediation_dir.glob("*.json"):
            try:
                with open(f, "r") as report:
                    data = json.load(report)
                    data["file"] = f.name
                    anomalies.append(data)
            except Exception:
                continue
    
    return web.json_response({"anomalies": sorted(anomalies, key=lambda x: x.get("timestamp", 0), reverse=True)})
