"""
Capability discovery module for the hybrid-coordinator.

Queries AIDB for applicable tools, skills, MCP servers, and datasets
based on query intent. Uses an in-memory TTL cache (DISCOVERY_CACHE).

Extracted from server.py (Phase 6.1 decomposition).

Usage in server.py:
    import capability_discovery
    capability_discovery.init(aidb_client=aidb_client, stats=HYBRID_STATS)
    result = await capability_discovery.discover(query)
"""

import asyncio
import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from metrics import AUTONOMY_BUDGET_EXCEEDED, DISCOVERY_DECISIONS, DISCOVERY_LATENCY

logger = logging.getLogger("hybrid-coordinator")

# In-memory TTL cache
DISCOVERY_CACHE: Dict[str, Dict[str, Any]] = {}
DISCOVERY_CACHE_LOCK = asyncio.Lock()

# Injected from server.py during startup
_aidb_client: Optional[Any] = None
_stats: Optional[Dict[str, Any]] = None  # reference to HYBRID_STATS["capability_discovery"]


def init(*, aidb_client: Any, stats: Dict[str, Any]) -> None:
    """Inject runtime dependencies.  Call once from server.py initialize_server()."""
    global _aidb_client, _stats
    _aidb_client = aidb_client
    _stats = stats


DISCOVERY_DOMAIN_KEYWORDS = {
    "tool", "tools", "mcp", "server", "servers", "skill", "skills",
    "dataset", "datasets", "document", "documents", "catalog", "library",
    "rag", "embedding", "embeddings", "vector", "workflow", "prompt",
    "prompts", "agent", "agents", "extension", "extensions", "vscodium",
}

DISCOVERY_ACTION_KEYWORDS = {
    "find", "discover", "list", "lookup", "search", "select", "choose",
    "recommend", "use", "apply", "install", "configure", "integrate",
    "wire", "map", "route", "optimize", "ingest",
}


# ============================================================================
# Public entry point
# ============================================================================

async def discover(query: str) -> Dict[str, Any]:
    """Discover applicable resources for *query*. Returns a dict with tools/skills/servers/datasets."""
    return await _discover_applicable_resources(query)


# ============================================================================
# Internal helpers
# ============================================================================

def _normalize_tokens(query: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9_\-]{2,}", query.lower())
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "http", "https",
        "you", "your", "are", "was", "were", "can", "could", "should", "would",
    }
    return [t for t in tokens if t not in stopwords]


def _update_stats(decision: str, reason: str) -> None:
    DISCOVERY_DECISIONS.labels(decision=decision, reason=reason).inc()
    if _stats is None:
        return
    _stats["last_decision"] = decision
    _stats["last_reason"] = reason
    if decision == "invoked":
        _stats["invoked"] += 1
    elif decision == "cache_hit":
        _stats["cache_hits"] += 1
    elif decision == "skipped":
        _stats["skipped"] += 1
    elif decision == "error":
        _stats["errors"] += 1


def _build_cache_key(query: str, intent_tags: List[str]) -> str:
    normalized_query = " ".join(_normalize_tokens(query))[:512]
    normalized_tags = ",".join(sorted(intent_tags))
    digest = hashlib.sha256(f"{normalized_query}|{normalized_tags}".encode("utf-8")).hexdigest()
    return digest


def _should_run(query: str) -> Tuple[bool, str, List[str]]:
    if not Config.AI_CAPABILITY_DISCOVERY_ENABLED:
        return False, "disabled", []
    if len(query.strip()) < Config.AI_CAPABILITY_DISCOVERY_MIN_QUERY_CHARS:
        return False, "query-too-short", []

    tokens = _normalize_tokens(query)
    if not tokens:
        return False, "no-meaningful-tokens", []

    token_set = set(tokens)
    domain_hits = sorted(t for t in token_set if t in DISCOVERY_DOMAIN_KEYWORDS)
    action_hits = sorted(t for t in token_set if t in DISCOVERY_ACTION_KEYWORDS)

    direct_triggers = {"mcp", "tools", "skills", "dataset", "datasets", "rag", "workflow"}
    if token_set.intersection(direct_triggers):
        return True, "explicit-discovery-intent", domain_hits or ["discovery"]

    if domain_hits and action_hits:
        return True, "domain-plus-action", domain_hits

    return False, "no-discovery-intent", []


def _rank_items_for_query(
    items: List[Dict[str, Any]],
    query: str,
    *,
    fields: List[str],
    limit: int,
) -> List[Dict[str, Any]]:
    tokens = _normalize_tokens(query)
    if not items:
        return []
    if not tokens:
        return items[:limit]

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for item in items:
        text_parts: List[str] = []
        for f in fields:
            value = item.get(f)
            if isinstance(value, str):
                text_parts.append(value.lower())
            elif isinstance(value, list):
                text_parts.extend(str(v).lower() for v in value if isinstance(v, (str, int)))
        corpus = " ".join(text_parts)
        score = sum(2 if token == corpus else 1 for token in tokens if token in corpus)
        if score > 0:
            scored.append((score, item))
    if not scored:
        return items[:limit]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]


def format_context(discovery: Dict[str, Any]) -> str:
    """Format discovery result as a markdown context block."""
    decision = discovery.get("decision", "unknown")
    if decision in {"skipped", "error"}:
        return ""

    lines: List[str] = ["\n## Applicable Tools, Skills, MCP Servers, and Datasets\n"]
    tools = discovery.get("tools") or []
    skills = discovery.get("skills") or []
    servers = discovery.get("servers") or []
    datasets = discovery.get("datasets") or []

    if tools:
        lines.append("- Tools:\n")
        for item in tools:
            lines.append(f"  - {item.get('name', 'unknown')}: {item.get('description', 'No description')}\n")
    if skills:
        lines.append("- Skills:\n")
        for item in skills:
            lines.append(f"  - {item.get('name', item.get('slug', 'unknown'))}: {item.get('description', 'No description')}\n")
    if servers:
        lines.append("- MCP Servers:\n")
        for item in servers:
            lines.append(f"  - {item.get('name', 'unknown')}: {item.get('description', item.get('source_url', 'No description'))}\n")
    if datasets:
        lines.append("- Datasets/Documents:\n")
        for item in datasets:
            lines.append(f"  - {item.get('title', item.get('relative_path', 'unknown'))} ({item.get('project', 'default')})\n")

    if len(lines) == 1:
        return ""
    return "".join(lines)


async def _discover_applicable_resources(query: str) -> Dict[str, Any]:
    decision, reason, intent_tags = _should_run(query)
    if not decision:
        _update_stats("skipped", reason)
        return {
            "decision": "skipped", "reason": reason, "intent_tags": intent_tags,
            "cache_hit": False, "tools": [], "skills": [], "servers": [], "datasets": [],
        }

    if _aidb_client is None or not Config.AIDB_URL:
        _update_stats("skipped", "aidb-unavailable")
        return {
            "decision": "skipped", "reason": "aidb-unavailable", "intent_tags": intent_tags,
            "cache_hit": False, "tools": [], "skills": [], "servers": [], "datasets": [],
        }

    cache_key = _build_cache_key(query, intent_tags)
    now = time.time()
    ttl = max(60, Config.AI_CAPABILITY_DISCOVERY_TTL_SECONDS)
    async with DISCOVERY_CACHE_LOCK:
        cached = DISCOVERY_CACHE.get(cache_key)
        if cached and float(cached.get("expires_at", 0)) > now:
            _update_stats("cache_hit", "ttl-hit")
            return {
                **cached["payload"],
                "cache_hit": True,
                "decision": "cache_hit",
                "reason": "ttl-hit",
                "intent_tags": intent_tags,
            }

    start = time.time()

    async def _fetch(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        attempts = max(1, Config.AI_AUTONOMY_MAX_RETRIES + 1)
        last_error: Optional[Exception] = None
        for _ in range(attempts):
            try:
                response = await _aidb_client.get(path, params=params, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                await asyncio.sleep(0.1)
        AUTONOMY_BUDGET_EXCEEDED.labels(budget="external_retries").inc()
        raise last_error or RuntimeError("external_fetch_failed")

    try:
        fetch_plan = [
            ("tools", "/tools", {"mode": "minimal"}),
            ("skills", "/skills", {"include_pending": "false"}),
            ("documents", "/documents", {"limit": 120, "include_content": "false", "include_pending": "false"}),
            ("servers", "/api/v1/federation/servers", None),
        ]
        max_calls = max(1, Config.AI_AUTONOMY_MAX_EXTERNAL_CALLS)
        if max_calls < len(fetch_plan):
            AUTONOMY_BUDGET_EXCEEDED.labels(budget="external_calls").inc()
        selected_plan = fetch_plan[:max_calls]
        responses = await asyncio.gather(
            *[_fetch(path, params) for _, path, params in selected_plan]
        )
        payload_map = {name: data for (name, _, _), data in zip(selected_plan, responses)}
        tools_payload = payload_map.get("tools", {"tools": []})
        skills_payload = payload_map.get("skills", [])
        docs_payload = payload_map.get("documents", {"documents": []})
        servers_payload = payload_map.get("servers", {"servers": []})

        max_items = max(1, Config.AI_CAPABILITY_DISCOVERY_MAX_RESULTS)
        tools = _rank_items_for_query(
            tools_payload.get("tools", []), query, fields=["name", "description"], limit=max_items,
        )
        skills = _rank_items_for_query(
            skills_payload if isinstance(skills_payload, list) else [],
            query, fields=["name", "description", "tags"], limit=max_items,
        )
        servers = _rank_items_for_query(
            servers_payload.get("servers", []), query,
            fields=["name", "description", "server_type", "source_url"], limit=max_items,
        )
        datasets = _rank_items_for_query(
            docs_payload.get("documents", []), query,
            fields=["title", "relative_path", "project", "content_type"], limit=max_items,
        )

        payload = {
            "decision": "invoked",
            "reason": "live-discovery",
            "intent_tags": intent_tags,
            "cache_hit": False,
            "tools": tools,
            "skills": skills,
            "servers": servers,
            "datasets": datasets,
            "latency_ms": int((time.time() - start) * 1000),
        }
        async with DISCOVERY_CACHE_LOCK:
            DISCOVERY_CACHE[cache_key] = {"expires_at": now + ttl, "payload": payload}
        DISCOVERY_LATENCY.observe(time.time() - start)
        _update_stats("invoked", "live-discovery")
        return payload

    except Exception as exc:  # noqa: BLE001
        logger.warning("capability_discovery_failed error=%s", exc)
        _update_stats("error", "request-failed")
        return {
            "decision": "error",
            "reason": "request-failed",
            "intent_tags": intent_tags,
            "cache_hit": False,
            "tools": [], "skills": [], "servers": [], "datasets": [],
            "error": str(exc),
        }
