"""
System topology and logic-error search endpoints.

GET  /api/topology        — live service graph (nodes + edges + health)
GET  /api/topology/flow   — request routing flowchart (Mermaid-compatible)
POST /api/logic/search    — semantic search for logic patterns in AIDB
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import service_endpoints

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _aidb_api_key() -> str:
    key_file = os.environ.get("AIDB_API_KEY_FILE", "/run/secrets/aidb_api_key")
    try:
        return open(key_file).read().strip()
    except OSError:
        return os.environ.get("AIDB_API_KEY", "")


async def _check_service(session: aiohttp.ClientSession, url: str) -> str:
    """Return 'up', 'down', or 'degraded' for a service health check."""
    try:
        async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=2)) as r:
            if r.status == 200:
                return "up"
            return "degraded"
    except Exception:
        return "down"


# ---------------------------------------------------------------------------
# Static topology definition — edges and roles never change at runtime
# ---------------------------------------------------------------------------

_SERVICES = [
    {"id": "llama-cpp",            "port": service_endpoints.LLAMA_CPP_PORT,          "role": "inference",    "label": "LLaMA.cpp (Qwen3)"},
    {"id": "llama-embed",          "port": service_endpoints.LLAMA_EMBED_PORT if hasattr(service_endpoints, "LLAMA_EMBED_PORT") else 8081, "role": "embeddings", "label": "LLaMA Embed"},
    {"id": "aidb",                 "port": service_endpoints.AIDB_PORT,               "role": "vector-db",    "label": "AIDB"},
    {"id": "hybrid-coordinator",   "port": service_endpoints.HYBRID_COORDINATOR_PORT, "role": "coordinator",  "label": "Hybrid Coordinator"},
    {"id": "ralph-wiggum",         "port": service_endpoints.RALPH_PORT,              "role": "rag",          "label": "Ralph Wiggum"},
    {"id": "switchboard",          "port": service_endpoints.SWITCHBOARD_PORT,        "role": "gateway",      "label": "Switchboard"},
    {"id": "dashboard",            "port": int(os.environ.get("DASHBOARD_PORT", "8889")), "role": "ui",       "label": "Dashboard"},
]

_EDGES = [
    {"from": "switchboard",        "to": "hybrid-coordinator", "label": "route"},
    {"from": "hybrid-coordinator", "to": "llama-cpp",          "label": "query"},
    {"from": "hybrid-coordinator", "to": "aidb",               "label": "vector search"},
    {"from": "hybrid-coordinator", "to": "ralph-wiggum",       "label": "rag"},
    {"from": "ralph-wiggum",       "to": "aidb",               "label": "retrieve"},
    {"from": "hybrid-coordinator", "to": "llama-embed",        "label": "embed"},
    {"from": "dashboard",          "to": "hybrid-coordinator", "label": "api"},
    {"from": "dashboard",          "to": "aidb",               "label": "api"},
]

_SERVICE_URL_MAP = {
    "llama-cpp":          service_endpoints.LLAMA_URL,
    "llama-embed":        getattr(service_endpoints, "LLAMA_EMBED_URL", f"http://127.0.0.1:8081"),
    "aidb":               service_endpoints.AIDB_URL,
    "hybrid-coordinator": service_endpoints.HYBRID_URL,
    "ralph-wiggum":       service_endpoints.RALPH_URL,
    "switchboard":        service_endpoints.SWITCHBOARD_URL,
    "dashboard":          f"http://127.0.0.1:{os.environ.get('DASHBOARD_PORT', '8889')}",
}


# ---------------------------------------------------------------------------
# GET /api/topology
# ---------------------------------------------------------------------------

@router.get("/topology")
async def get_topology() -> Dict[str, Any]:
    """Return live service topology with health status."""
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        nodes = []
        for svc in _SERVICES:
            url = _SERVICE_URL_MAP.get(svc["id"], "")
            status = await _check_service(session, url) if url else "unknown"
            nodes.append({
                "id":     svc["id"],
                "port":   svc["port"],
                "role":   svc["role"],
                "label":  svc["label"],
                "status": status,
                "url":    url,
            })

    return {
        "nodes":        nodes,
        "edges":        _EDGES,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# GET /api/topology/flow
# ---------------------------------------------------------------------------

_FLOWCHART = """flowchart LR
    User([User / Agent]) --> SWB[Switchboard :8085]
    SWB -->|default profile| HC[Hybrid Coordinator :8003]
    SWB -->|continue-local| HC
    HC -->|prefer_local=true| LLAMA[LLaMA.cpp :8080]
    HC -->|vector search| AIDB[(AIDB :8002)]
    HC -->|rag task| RALPH[Ralph Wiggum :8004]
    HC -->|embed request| EMBED[LLaMA Embed :8081]
    RALPH --> AIDB
    DASHBOARD[Dashboard :8889] -->|/api/*| HC
    DASHBOARD -->|/api/logic/search| AIDB
"""


@router.get("/topology/flow")
async def get_topology_flow() -> Dict[str, Any]:
    """Return Mermaid-compatible request routing flowchart."""
    return {
        "format":   "mermaid",
        "flowchart": _FLOWCHART.strip(),
        "version":  "1.0",
    }


# ---------------------------------------------------------------------------
# POST /api/logic/search
# ---------------------------------------------------------------------------

class LogicSearchRequest(BaseModel):
    query: str = Field(..., description="Natural-language description of the logic pattern")
    top_k: int = Field(5, ge=1, le=20)


@router.post("/logic/search")
async def search_logic_patterns(body: LogicSearchRequest) -> Dict[str, Any]:
    """Semantic search for logic patterns indexed in AIDB (project: logic-patterns)."""
    api_key = _aidb_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="AIDB API key not available")

    payload = {
        "query":   body.query,
        "project": "logic-patterns",
        "limit":   body.top_k,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{service_endpoints.AIDB_URL}/vector/search",
                json=payload,
                headers={"X-API-Key": api_key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 404:
                    return {"results": [], "note": "logic-patterns project not yet indexed — run aq-index-logic-patterns"}
                if resp.status != 200:
                    body_text = await resp.text()
                    raise HTTPException(status_code=resp.status, detail=body_text)
                data = await resp.json()
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=503, detail=f"AIDB unreachable: {exc}") from exc

    results = []
    for hit in data.get("results", []):
        doc = hit.get("document", {})
        results.append({
            "file":         doc.get("relative_path", ""),
            "title":        doc.get("title", ""),
            "pattern_type": doc.get("metadata", {}).get("pattern_type", ""),
            "distance":     hit.get("distance"),
            "excerpt":      doc.get("content", "")[:300],
        })

    return {"query": body.query, "top_k": body.top_k, "results": results}
