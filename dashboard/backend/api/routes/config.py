"""Dashboard configuration and control-plane inventory endpoints."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import service_endpoints

router = APIRouter()
logger = logging.getLogger(__name__)

_CONFIG: Dict[str, Any] = {
    "rate_limit": 60,
    "checkpoint_interval": 100,
    "backpressure_threshold_mb": 100,
    "log_level": "INFO",
}


class ConfigPayload(BaseModel):
    rate_limit: int = 60
    checkpoint_interval: int = 100
    backpressure_threshold_mb: int = 100
    log_level: str = "INFO"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _workflow_blueprints_path() -> Path:
    return _repo_root() / "config" / "workflow-blueprints.json"


def _agent_discovery_manifest_path() -> Path:
    return _repo_root() / "config" / "ai-stack-agent-discovery.json"


def _harness_first_policy_path() -> Path:
    return _repo_root() / "config" / "harness-first-policy.json"


def _route_aliases_path() -> Path:
    return _repo_root() / "config" / "route-aliases.json"


def _harness_runbook_path() -> Path:
    return _repo_root() / "docs" / "harness-first" / "HARNESS-FIRST-RUNBOOK.md"


def _harness_evidence_template_path() -> Path:
    return _repo_root() / "docs" / "harness-first" / "HARNESS-FIRST-EVIDENCE-TEMPLATE.md"


def _repo_graph_surfaces() -> List[Dict[str, Any]]:
    return [
        {
            "id": "repo-structure",
            "label": "Relational File and Folder Graph",
            "endpoint": "/api/config/graphs/repo-structure",
            "description": "Bounded command-center graph of key repo folders, files, and operational ownership edges.",
        },
        {
            "id": "workflow-blueprints",
            "label": "System Workflow Diagram",
            "endpoint": "/api/config/graphs/workflow-blueprints",
            "description": "Blueprint-level workflow graph showing lanes, phases, and reviewer/escalation routing.",
        },
        {
            "id": "deployment-context",
            "label": "Deployment Relationship Graph",
            "endpoint": "/api/deployments/graph",
            "description": "Live deployment and causality graph for recent command-center events.",
        },
    ]


def _graph_stats(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    node_types: Dict[str, int] = {}
    relation_types: Dict[str, int] = {}
    for node in nodes:
        node_type = str(node.get("type") or "unknown")
        node_types[node_type] = node_types.get(node_type, 0) + 1
    for edge in edges:
        relation = str(edge.get("relation") or "related_to")
        relation_types[relation] = relation_types.get(relation, 0) + 1
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": node_types,
        "relation_types": relation_types,
    }


def _build_repo_structure_graph() -> Dict[str, Any]:
    repo_root = _repo_root()
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    def add_node(node_id: str, node_type: str, label: str, **extra: Any) -> None:
        nodes.append({"id": node_id, "type": node_type, "label": label, **extra})

    def add_edge(source: str, target: str, relation: str, **extra: Any) -> None:
        edges.append({"source": source, "target": target, "relation": relation, **extra})

    add_node("repo", "root", repo_root.name, path=str(repo_root), role="repository")
    add_node("file:AGENTS.md", "file", "AGENTS.md", path=str(repo_root / "AGENTS.md"), role="policy")
    add_node("file:README.md", "file", "README.md", path=str(repo_root / "README.md"), role="overview")
    add_edge("repo", "file:AGENTS.md", "governed_by")
    add_edge("repo", "file:README.md", "described_by")

    domain_nodes = [
        ("dir:config", "configuration", repo_root / "config"),
        ("dir:nix", "declarative-system", repo_root / "nix"),
        ("dir:scripts", "operations", repo_root / "scripts"),
        ("dir:ai-stack", "runtime", repo_root / "ai-stack"),
        ("dir:dashboard", "command-center", repo_root / "dashboard"),
        ("dir:docs", "documentation", repo_root / "docs"),
    ]
    for node_id, role, path in domain_nodes:
        add_node(node_id, "directory", Path(path).name, path=str(path), role=role)
        add_edge("repo", node_id, "contains")

    curated_children = [
        ("file:config/service-endpoints.sh", "file", "service-endpoints.sh", repo_root / "config" / "service-endpoints.sh", "endpoint-ssot", "dir:config"),
        ("file:config/workflow-blueprints.json", "file", "workflow-blueprints.json", repo_root / "config" / "workflow-blueprints.json", "workflow-contract", "dir:config"),
        ("file:config/route-aliases.json", "file", "route-aliases.json", repo_root / "config" / "route-aliases.json", "routing-contract", "dir:config"),
        ("file:config/ai-stack-agent-discovery.json", "file", "ai-stack-agent-discovery.json", repo_root / "config" / "ai-stack-agent-discovery.json", "agent-discovery", "dir:config"),
        ("dir:nix/modules", "directory", "modules", repo_root / "nix" / "modules", "system-modules", "dir:nix"),
        ("dir:nix/home", "directory", "home", repo_root / "nix" / "home", "editor-home", "dir:nix"),
        ("dir:scripts/ai", "directory", "ai", repo_root / "scripts" / "ai", "harness-cli", "dir:scripts"),
        ("dir:scripts/testing", "directory", "testing", repo_root / "scripts" / "testing", "validation", "dir:scripts"),
        ("dir:scripts/governance", "directory", "governance", repo_root / "scripts" / "governance", "quality-gates", "dir:scripts"),
        ("file:scripts/ai/aq-prime", "file", "aq-prime", repo_root / "scripts" / "ai" / "aq-prime", "bootstrap", "dir:scripts/ai"),
        ("file:scripts/ai/aq-hints", "file", "aq-hints", repo_root / "scripts" / "ai" / "aq-hints", "hinting", "dir:scripts/ai"),
        ("file:scripts/ai/aq-context-bootstrap", "file", "aq-context-bootstrap", repo_root / "scripts" / "ai" / "aq-context-bootstrap", "context-bootstrap", "dir:scripts/ai"),
        ("file:scripts/ai/aq-qa", "file", "aq-qa", repo_root / "scripts" / "ai" / "aq-qa", "runtime-verification", "dir:scripts/ai"),
        ("dir:ai-stack/mcp-servers", "directory", "mcp-servers", repo_root / "ai-stack" / "mcp-servers", "coordinator-runtime", "dir:ai-stack"),
        ("dir:ai-stack/workflows", "directory", "workflows", repo_root / "ai-stack" / "workflows", "workflow-engine", "dir:ai-stack"),
        ("file:ai-stack/mcp-servers/hybrid-coordinator/http_server.py", "file", "http_server.py", repo_root / "ai-stack" / "mcp-servers" / "hybrid-coordinator" / "http_server.py", "front-door-ingress", "dir:ai-stack/mcp-servers"),
        ("dir:dashboard/backend", "directory", "backend", repo_root / "dashboard" / "backend", "dashboard-api", "dir:dashboard"),
        ("file:dashboard/backend/api/routes/config.py", "file", "config.py", repo_root / "dashboard" / "backend" / "api" / "routes" / "config.py", "graph-api", "dir:dashboard/backend"),
        ("file:dashboard/backend/api/routes/aistack.py", "file", "aistack.py", repo_root / "dashboard" / "backend" / "api" / "routes" / "aistack.py", "runtime-observability", "dir:dashboard/backend"),
        ("file:dashboard.html", "file", "dashboard.html", repo_root / "dashboard.html", "operator-ui", "dir:dashboard"),
        ("dir:docs/operations", "directory", "operations", repo_root / "docs" / "operations", "runbooks", "dir:docs"),
        ("dir:docs/harness-first", "directory", "harness-first", repo_root / "docs" / "harness-first", "workflow-docs", "dir:docs"),
    ]
    for node_id, node_type, label, path, role, parent in curated_children:
        add_node(node_id, node_type, label, path=str(path), role=role)
        add_edge(parent, node_id, "contains")

    relational_edges = [
        ("file:AGENTS.md", "dir:nix", "governs"),
        ("file:AGENTS.md", "dir:scripts", "governs"),
        ("file:AGENTS.md", "dir:ai-stack", "governs"),
        ("file:AGENTS.md", "dir:dashboard", "governs"),
        ("file:config/service-endpoints.sh", "file:dashboard/backend/api/routes/config.py", "configures"),
        ("file:config/service-endpoints.sh", "file:dashboard/backend/api/routes/aistack.py", "configures"),
        ("file:config/workflow-blueprints.json", "dir:ai-stack/workflows", "defines"),
        ("file:config/workflow-blueprints.json", "file:dashboard/backend/api/routes/config.py", "published_by"),
        ("file:config/route-aliases.json", "file:dashboard/backend/api/routes/aistack.py", "feeds"),
        ("file:scripts/ai/aq-prime", "file:config/workflow-blueprints.json", "bootstraps_into"),
        ("file:scripts/ai/aq-hints", "file:config/workflow-blueprints.json", "guides"),
        ("file:scripts/ai/aq-context-bootstrap", "file:config/workflow-blueprints.json", "activates"),
        ("file:scripts/ai/aq-qa", "file:dashboard/backend/api/routes/aistack.py", "verifies"),
        ("file:ai-stack/mcp-servers/hybrid-coordinator/http_server.py", "file:config/route-aliases.json", "resolves"),
        ("file:dashboard/backend/api/routes/config.py", "file:dashboard.html", "renders_into"),
        ("file:dashboard/backend/api/routes/aistack.py", "file:dashboard.html", "streams_into"),
        ("dir:docs/operations", "file:dashboard.html", "documents"),
        ("dir:docs/harness-first", "file:scripts/ai/aq-prime", "documents"),
    ]
    for source, target, relation in relational_edges:
        add_edge(source, target, relation)

    return {
        "graph_id": "repo-structure",
        "title": "Relational File and Folder Graph",
        "nodes": nodes,
        "edges": edges,
        "focus_areas": ["nix", "scripts/ai", "ai-stack/mcp-servers", "dashboard/backend", "config"],
        "stats": _graph_stats(nodes, edges),
        "camera_presets": [
            {"id": "repo-core", "label": "Repo Core", "focus": ["repo", "dir:config", "dir:dashboard", "dir:ai-stack"]},
            {"id": "operator-loop", "label": "Operator Loop", "focus": ["file:scripts/ai/aq-prime", "file:config/workflow-blueprints.json", "file:dashboard.html"]},
        ],
    }


def _build_workflow_blueprint_graph() -> Dict[str, Any]:
    blueprints = _load_workflow_blueprints()
    raw_blueprints = []
    try:
        raw_blueprints = json.loads(_workflow_blueprints_path().read_text(encoding="utf-8")).get("blueprints") or []
    except (OSError, json.JSONDecodeError):
        raw_blueprints = []

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    lane_nodes: set[str] = set()
    tool_nodes: set[str] = set()
    surface_nodes: set[str] = set()
    policy_nodes: set[str] = set()

    def add_node(node_id: str, node_type: str, label: str, **extra: Any) -> None:
        nodes.append({"id": node_id, "type": node_type, "label": label, **extra})

    def add_edge(source: str, target: str, relation: str, **extra: Any) -> None:
        edges.append({"source": source, "target": target, "relation": relation, **extra})

    tool_surfaces: Dict[str, List[Dict[str, str]]] = {
        "hints": [
            {"id": "surface:aq-hints", "label": "aq-hints", "kind": "cli"},
            {"id": "surface:/hints", "label": "GET /hints", "kind": "http"},
        ],
        "workflow_plan": [
            {"id": "surface:/workflow/plan", "label": "POST /workflow/plan", "kind": "http"},
        ],
        "route_search": [
            {"id": "surface:hybrid-search", "label": "hybrid_search / grep-first", "kind": "tooling"},
        ],
        "memory_recall": [
            {"id": "surface:aq-memory", "label": "aq-memory search", "kind": "cli"},
        ],
        "feedback": [
            {"id": "surface:/review/acceptance", "label": "POST /review/acceptance", "kind": "http"},
        ],
        "health": [
            {"id": "surface:/health", "label": "GET /health", "kind": "http"},
            {"id": "surface:aq-qa0", "label": "aq-qa 0 --json", "kind": "cli"},
        ],
        "harness_eval": [
            {"id": "surface:aq-qa0", "label": "aq-qa 0 --json", "kind": "cli"},
        ],
        "qa_check": [
            {"id": "surface:aq-qa0", "label": "aq-qa 0 --json", "kind": "cli"},
        ],
        "shared_skill_registry": [
            {"id": "surface:skills", "label": "Skill Registry", "kind": "catalog"},
        ],
        "ai_coordinator_delegate": [
            {"id": "surface:coordinator-delegate", "label": "coordinator-delegate", "kind": "rpc"},
            {"id": "surface:remote-reasoning", "label": "remote-reasoning lane", "kind": "lane"},
        ],
        "check_boot_shutdown_integration": [
            {"id": "surface:boot-check", "label": "boot/shutdown integration checks", "kind": "verification"},
        ],
    }

    add_node("surface:aq-prime", "surface", "aq-prime", kind="cli", role="bootstrap")
    add_node("surface:aq-context-bootstrap", "surface", "aq-context-bootstrap", kind="cli", role="bootstrap")
    add_node("surface:/workflow/run/start", "surface", "POST /workflow/run/start", kind="http", role="persisted-run")
    add_node("surface:/api/aistack/routing/summary", "surface", "GET /api/aistack/routing/summary", kind="dashboard", role="monitoring")
    add_node("surface:/api/aistack/routing/decisions", "surface", "GET /api/aistack/routing/decisions", kind="dashboard", role="decision-log")
    surface_nodes.update(
        {
            "surface:aq-prime",
            "surface:aq-context-bootstrap",
            "surface:/workflow/run/start",
            "surface:/api/aistack/routing/summary",
            "surface:/api/aistack/routing/decisions",
        }
    )

    for blueprint in raw_blueprints:
        if not isinstance(blueprint, dict):
            continue
        blueprint_id = str(blueprint.get("id") or "")
        if not blueprint_id:
            continue
        title = str(blueprint.get("title") or blueprint_id)
        blueprint_node_id = f"blueprint:{blueprint_id}"
        add_node(
            blueprint_node_id,
            "blueprint",
            title,
            default_safety_mode=str(blueprint.get("default_safety_mode") or "unknown"),
            description=str(blueprint.get("description") or ""),
        )
        add_edge("surface:aq-prime", blueprint_node_id, "primes")
        add_edge("surface:aq-context-bootstrap", blueprint_node_id, "selects")
        add_edge(blueprint_node_id, "surface:/workflow/run/start", "starts")
        add_edge(blueprint_node_id, "surface:/api/aistack/routing/summary", "observed_by")
        add_edge(blueprint_node_id, "surface:/api/aistack/routing/decisions", "logged_by")

        policy = blueprint.get("orchestration_policy") or {}
        consensus_mode = str(policy.get("consensus_mode") or "").strip()
        if consensus_mode:
            consensus_id = f"policy:consensus:{consensus_mode}"
            if consensus_id not in policy_nodes:
                policy_nodes.add(consensus_id)
                add_node(consensus_id, "policy", consensus_mode, policy_kind="consensus_mode")
            add_edge(blueprint_node_id, consensus_id, "uses_consensus")

        selection_strategy = str(policy.get("selection_strategy") or "").strip()
        if selection_strategy:
            strategy_id = f"policy:selection:{selection_strategy}"
            if strategy_id not in policy_nodes:
                policy_nodes.add(strategy_id)
                add_node(strategy_id, "policy", selection_strategy, policy_kind="selection_strategy")
            add_edge(blueprint_node_id, strategy_id, "selects_via")

        for lane_key in ("primary_lane", "reviewer_lane", "escalation_lane"):
            lane = str(policy.get(lane_key) or "").strip()
            if not lane:
                continue
            lane_id = f"lane:{lane}"
            if lane_id not in lane_nodes:
                lane_nodes.add(lane_id)
                add_node(lane_id, "lane", lane, lane_kind=lane_key)
            add_edge(blueprint_node_id, lane_id, lane_key)

        previous_phase_id: Optional[str] = None
        for phase in blueprint.get("phases") or []:
            if not isinstance(phase, dict):
                continue
            phase_name = str(phase.get("id") or "phase")
            phase_id = f"phase:{blueprint_id}:{phase_name}"
            phase_tools = list(phase.get("tools") or [])
            add_node(
                phase_id,
                "phase",
                phase_name,
                requires_approval=bool(phase.get("requires_approval", False)),
                tools=phase_tools,
                exit_criteria=str(phase.get("exit_criteria") or ""),
            )
            add_edge(blueprint_node_id, phase_id, "has_phase")
            if previous_phase_id is not None:
                add_edge(previous_phase_id, phase_id, "precedes")
            previous_phase_id = phase_id

            if phase_tools:
                for tool_name in phase_tools:
                    tool_id = f"tool:{tool_name}"
                    if tool_id not in tool_nodes:
                        tool_nodes.add(tool_id)
                        add_node(tool_id, "tool", tool_name)
                    add_edge(phase_id, tool_id, "uses_tool")
                    for surface in tool_surfaces.get(tool_name, []):
                        surface_id = surface["id"]
                        if surface_id not in surface_nodes:
                            surface_nodes.add(surface_id)
                            add_node(surface_id, "surface", surface["label"], kind=surface["kind"])
                        add_edge(tool_id, surface_id, "invokes")

            if bool(phase.get("requires_approval", False)):
                add_edge(phase_id, "surface:/review/acceptance", "review_gate")

    return {
        "graph_id": "workflow-blueprints",
        "title": "System Workflow Diagram",
        "blueprints": blueprints,
        "nodes": nodes,
        "edges": edges,
        "focus_areas": [
            "bootstrap",
            "plan -> run/start",
            "review gate",
            "local vs remote lane selection",
            "monitoring and decision logs",
        ],
        "stats": _graph_stats(nodes, edges),
        "camera_presets": [
            {"id": "workflow-loop", "label": "Workflow Loop", "focus": ["surface:aq-prime", "surface:/workflow/run/start", "surface:/review/acceptance"]},
            {"id": "monitoring", "label": "Monitoring", "focus": ["surface:/api/aistack/routing/summary", "surface:/api/aistack/routing/decisions", "surface:aq-qa0"]},
        ],
    }


def _load_secret_from_file(env_var: str) -> str:
    secret_path = os.getenv(env_var, "").strip()
    if not secret_path:
        return ""
    try:
        return Path(secret_path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _hybrid_headers() -> Dict[str, str]:
    api_key = os.getenv("HYBRID_API_KEY", "").strip() or _load_secret_from_file("HYBRID_API_KEY_FILE")
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


async def _fetch_hybrid_health() -> Dict[str, Any]:
    url = f"{service_endpoints.HYBRID_URL}/health"
    timeout = aiohttp.ClientTimeout(total=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=_hybrid_headers()) as response:
                if response.status != 200:
                    logger.warning("Hybrid health probe returned %s for %s", response.status, url)
                    return {}
                return await response.json()
    except Exception as exc:
        logger.warning("Failed fetching hybrid health for dashboard config inventory: %s", exc)
        return {}


def _load_workflow_blueprints() -> List[Dict[str, Any]]:
    blueprint_path = _workflow_blueprints_path()
    try:
        payload = json.loads(blueprint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading workflow blueprints from %s: %s", blueprint_path, exc)
        return []

    blueprints = payload.get("blueprints")
    if not isinstance(blueprints, list):
        return []

    summarized: List[Dict[str, Any]] = []
    for entry in blueprints:
        if not isinstance(entry, dict):
            continue
        policy = entry.get("orchestration_policy") or {}
        summarized.append(
            {
                "workflow_id": str(entry.get("id") or ""),
                "name": str(entry.get("name") or entry.get("id") or "unnamed"),
                "runtime_editable": False,
                "redeploy_required": True,
                "orchestration_policy": {
                    "primary_lane": policy.get("primary_lane"),
                    "reviewer_lane": policy.get("reviewer_lane"),
                    "escalation_lane": policy.get("escalation_lane"),
                    "collaborator_lanes": list(policy.get("collaborator_lanes") or []),
                    "allow_parallel_subagents": bool(policy.get("allow_parallel_subagents", False)),
                    "max_parallel_subagents": int(policy.get("max_parallel_subagents", 1) or 1),
                },
            }
        )
    return summarized


def _load_agent_discovery_manifest() -> Dict[str, Any]:
    manifest_path = _agent_discovery_manifest_path()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading agent discovery manifest from %s: %s", manifest_path, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_harness_first_policy() -> Dict[str, Any]:
    policy_path = _harness_first_policy_path()
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading harness-first policy from %s: %s", policy_path, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_route_aliases_config() -> Dict[str, Any]:
    aliases_path = _route_aliases_path()
    try:
        payload = json.loads(aliases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed loading route aliases from %s: %s", aliases_path, exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_markdown_excerpt(path: Path, max_lines: int = 24) -> List[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Failed loading markdown excerpt from %s: %s", path, exc)
        return []
    excerpt = [line.rstrip() for line in lines[:max_lines]]
    return [line for line in excerpt if line.strip()]


def _bool_env(name: str, default: bool) -> bool:
    value = str(os.getenv(name, str(default).lower())).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _frontdoor_profile(name: str, fallback: str) -> str:
    return str(os.getenv(name, fallback) or fallback).strip()


def _build_frontdoor_routing_snapshot() -> Dict[str, Any]:
    route_aliases = _load_route_aliases_config()
    alias_map = route_aliases.get("aliases") if isinstance(route_aliases.get("aliases"), dict) else {}
    aliases = [{"route": str(route), "profile": str(profile)} for route, profile in alias_map.items()]
    env_overrides = [
        {"name": "AI_LOCAL_FRONTDOOR_DEFAULT_PROFILE", "value": _frontdoor_profile("AI_LOCAL_FRONTDOOR_DEFAULT_PROFILE", "default")},
        {"name": "AI_LOCAL_FRONTDOOR_EXPLORE_PROFILE", "value": _frontdoor_profile("AI_LOCAL_FRONTDOOR_EXPLORE_PROFILE", "default")},
        {"name": "AI_LOCAL_FRONTDOOR_PLAN_PROFILE", "value": _frontdoor_profile("AI_LOCAL_FRONTDOOR_PLAN_PROFILE", "default")},
        {
            "name": "AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE",
            "value": _frontdoor_profile("AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE", "local-tool-calling"),
        },
        {
            "name": "AI_LOCAL_FRONTDOOR_REASONING_PROFILE",
            "value": _frontdoor_profile("AI_LOCAL_FRONTDOOR_REASONING_PROFILE", "local-tool-calling"),
        },
        {
            "name": "AI_LOCAL_FRONTDOOR_TOOL_CALLING_PROFILE",
            "value": _frontdoor_profile("AI_LOCAL_FRONTDOOR_TOOL_CALLING_PROFILE", "local-tool-calling"),
        },
        {"name": "AI_LOCAL_FRONTDOOR_CONTINUATION_PROFILE", "value": _frontdoor_profile("AI_LOCAL_FRONTDOOR_CONTINUATION_PROFILE", "default")},
    ]
    return {
        "enabled": _bool_env("AI_LOCAL_FRONTDOOR_ROUTING_ENABLE", True),
        "runtime_editable": False,
        "redeploy_required": True,
        "source": str(_route_aliases_path()),
        "compatibility_overrides": {
            "source": "AI_LOCAL_FRONTDOOR_* env vars (local-orchestrator compatibility overrides)",
            "fields": env_overrides,
        },
        "aliases": aliases,
    }


async def _build_config_snapshot() -> Dict[str, Any]:
    hybrid_health = await _fetch_hybrid_health()
    harness_state = dict(hybrid_health.get("ai_harness") or {})
    workflow_blueprints = _load_workflow_blueprints()
    discovery_manifest = _load_agent_discovery_manifest()
    harness_policy = _load_harness_first_policy()
    primary_contact = dict(discovery_manifest.get("primary_contact") or {})
    frontdoor_routing = _build_frontdoor_routing_snapshot()
    workflow_loop = list(primary_contact.get("workflow_loop") or [])
    bootstrap_commands = list(primary_contact.get("bootstrap") or [])
    policy_required_commands = list(harness_policy.get("required_commands") or [])
    policy_required_sections = list(harness_policy.get("required_sections") or [])
    policy_required_evidence = list(harness_policy.get("required_evidence_sections") or [])

    docs_sources = [
        {
            "label": "Harness-First Runbook",
            "path": str(_harness_runbook_path()),
            "preview_lines": _load_markdown_excerpt(_harness_runbook_path()),
            "redeploy_required": False,
        },
        {
            "label": "Harness Evidence Template",
            "path": str(_harness_evidence_template_path()),
            "preview_lines": _load_markdown_excerpt(_harness_evidence_template_path()),
            "redeploy_required": False,
        },
        {
            "label": "Harness-First Policy",
            "path": str(_harness_first_policy_path()),
            "preview_lines": [],
            "redeploy_required": True,
        },
        {
            "label": "Agent Discovery Manifest",
            "path": str(_agent_discovery_manifest_path()),
            "preview_lines": [],
            "redeploy_required": True,
        },
        {
            "label": "Workflow Blueprints",
            "path": str(_workflow_blueprints_path()),
            "preview_lines": [],
            "redeploy_required": True,
        },
        {
            "label": "Front-Door Route Aliases",
            "path": str(_route_aliases_path()),
            "preview_lines": [],
            "redeploy_required": True,
        },
    ]

    return {
        "rate_limit": _CONFIG["rate_limit"],
        "checkpoint_interval": _CONFIG["checkpoint_interval"],
        "backpressure_threshold_mb": _CONFIG["backpressure_threshold_mb"],
        "log_level": _CONFIG["log_level"],
        "dashboard_runtime": dict(_CONFIG),
        "harness_runtime": {
            "source": f"{service_endpoints.HYBRID_URL}/health",
            "runtime_editable": False,
            "redeploy_required": False,
            "settings": harness_state,
        },
        "frontdoor_routing": frontdoor_routing,
        "primary_contact": {
            "human_frontdoor": primary_contact.get("human_frontdoor") or "local-orchestrator",
            "bootstrap": bootstrap_commands,
            "workflow_loop": workflow_loop,
            "routing_aliases": dict(primary_contact.get("routing_aliases") or {}),
            "source": str(_agent_discovery_manifest_path()),
        },
        "harness_workflow": {
            "workflow_loop": workflow_loop,
            "bootstrap_commands": bootstrap_commands,
            "required_commands": policy_required_commands,
            "required_sections": policy_required_sections,
            "required_evidence_sections": policy_required_evidence,
            "runbook": harness_policy.get("runbook") or str(_harness_runbook_path()),
            "evidence_template": harness_policy.get("evidence_template") or str(_harness_evidence_template_path()),
            "source": str(_harness_first_policy_path()),
        },
        "documentation_sources": docs_sources,
        "command_center_graphs": _repo_graph_surfaces(),
        "workflow_blueprints": workflow_blueprints,
        "control_plane_inventory": {
            "dashboard_runtime_controls": [
                {
                    "surface": "/api/config",
                    "scope": "dashboard-api only",
                    "runtime_editable": True,
                    "redeploy_required": False,
                    "fields": sorted(_CONFIG.keys()),
                }
            ],
            "live_runtime_sources": [
                {
                    "surface": "/health ai_harness",
                    "scope": "hybrid coordinator live runtime",
                    "runtime_editable": False,
                    "redeploy_required": False,
                },
                {
                    "surface": "config/route-aliases.json",
                    "scope": "coordinator front-door route alias contract",
                    "runtime_editable": False,
                    "redeploy_required": True,
                },
                {
                    "surface": "AI_LOCAL_FRONTDOOR_*",
                    "scope": "local-orchestrator compatibility overrides",
                    "runtime_editable": False,
                    "redeploy_required": True,
                },
                {
                    "surface": "config/harness-first-policy.json",
                    "scope": "canonical harness workflow contract and evidence requirements",
                    "runtime_editable": False,
                    "redeploy_required": True,
                }
            ],
            "redeploy_required_sources": [
                {
                    "surface": "config/workflow-blueprints.json",
                    "scope": "workflow orchestration policy",
                    "runtime_editable": False,
                    "redeploy_required": True,
                },
                {
                    "surface": "config/ai-stack-agent-discovery.json",
                    "scope": "primary human contact surface and agent bootstrap manifest",
                    "runtime_editable": False,
                    "redeploy_required": True,
                },
                {
                    "surface": "config/route-aliases.json",
                    "scope": "front-door alias routing for /v1/orchestrate",
                    "runtime_editable": False,
                    "redeploy_required": True,
                }
            ],
            "known_gaps": [
                {
                    "surface": "/api/config",
                    "status": "misleading",
                    "detail": "Legacy dashboard config writes only dashboard-local runtime values, not hybrid harness or Nix settings.",
                },
                {
                    "surface": "front-door routing visibility",
                    "status": "corrected-source",
                    "detail": "Dashboard now reports aliases from config/route-aliases.json; AI_LOCAL_FRONTDOOR_* remains a local-orchestrator compatibility overlay.",
                },
                {
                    "surface": "/api/actions",
                    "status": "separate-config",
                    "detail": "Action catalog is loaded from ~/.local/share/nixos-system-dashboard/config.json instead of the hybrid coordinator control plane.",
                },
                {
                    "surface": "/api/collaboration and /api/workflows",
                    "status": "miswired",
                    "detail": "These routes expose standalone libraries instead of the live hybrid coordinator workflow/session state.",
                },
                {
                    "surface": "dashboard front-door controls",
                    "status": "observe-only",
                    "detail": "The dashboard now shows local front-door routing and primary contact surfaces, but changing them still requires declarative config plus restart/redeploy.",
                },
            ],
        },
        "legacy_notice": (
            "Dashboard runtime controls are local to the dashboard API. "
            "AI harness flags and first-layer route aliases are read from the live hybrid coordinator or declarative env, "
            "and workflow blueprint or primary-contact changes require editing repo config followed by redeploy or restart."
        ),
    }


@router.get("")
async def get_runtime_config() -> Dict[str, Any]:
    """Return dashboard runtime config plus live harness control-plane inventory."""
    return await _build_config_snapshot()


@router.get("/graphs/repo-structure")
async def get_repo_structure_graph() -> Dict[str, Any]:
    """Return a bounded repo topology graph for command-center consumption."""
    return _build_repo_structure_graph()


@router.get("/graphs/workflow-blueprints")
async def get_workflow_blueprint_graph() -> Dict[str, Any]:
    """Return a blueprint-level workflow graph for command-center consumption."""
    return _build_workflow_blueprint_graph()


@router.post("")
async def update_runtime_config(payload: ConfigPayload) -> Dict[str, Any]:
    """Update dashboard-local runtime configuration only."""
    _CONFIG.update(payload.model_dump())
    snapshot = await _build_config_snapshot()
    snapshot.update(
        {
            "status": "ok",
            "scope": "dashboard-runtime-only",
            "restarted": [],
            "warning": (
                "This endpoint updates dashboard-local runtime settings only. "
                "AI harness and workflow blueprint settings are not changed here."
            ),
        }
    )
    return snapshot


@router.get("/{file_name}")
async def get_config(file_name: str) -> Dict[str, Any]:
    """Get a supported config file content preview."""
    try:
        supported_paths = {
            "workflow-blueprints.json": (_workflow_blueprints_path(), True),
            "ai-stack-agent-discovery.json": (_agent_discovery_manifest_path(), True),
            "harness-first-policy.json": (_harness_first_policy_path(), True),
            "HARNESS-FIRST-RUNBOOK.md": (_harness_runbook_path(), False),
            "HARNESS-FIRST-EVIDENCE-TEMPLATE.md": (_harness_evidence_template_path(), False),
        }
        if file_name not in supported_paths:
            raise HTTPException(status_code=404, detail="Unsupported config file")
        path, redeploy_required = supported_paths[file_name]
        return {
            "file_name": file_name,
            "path": str(path),
            "content": path.read_text(encoding="utf-8"),
            "redeploy_required": redeploy_required,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{file_name}")
async def update_config(file_name: str, content: str) -> Dict[str, Any]:
    """Reject unsupported dashboard file writes instead of pretending success."""
    raise HTTPException(
        status_code=501,
        detail=(
            f"Dashboard API does not support editing {file_name} yet. "
            "Use declarative repo changes for Nix or workflow blueprint updates."
        ),
    )
