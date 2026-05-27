#!/usr/bin/env python3
import logging, json, os
from pathlib import Path
from aiohttp import web

logger = logging.getLogger("health-spider-handlers")

async def handle_get_anomalies(request: web.Request) -> web.Response:
    remediation_dir = Path("/tmp/ai-hybrid-coordinator/.reports/remediation")
    logger.info(f"Spider scanning: {remediation_dir} exists={remediation_dir.exists()}")
    anomalies = []
    if remediation_dir.exists():
        for f in remediation_dir.glob("*.json"):
            try:
                data = json.load(f.open('r'))
                data["file"] = f.name
                anomalies.append(data)
                logger.info(f"Spider found anomaly: {data}")
            except Exception as e:
                logger.error(f"Spider handler error: {e}")
    return web.json_response({"anomalies": anomalies})
