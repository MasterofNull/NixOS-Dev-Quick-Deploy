"""
Autonomous tool auto-selection handlers.

Provides endpoints that any agent/model can call to automatically receive
the correct tools, skills, and execution sequences for any task — without
the user or agent needing to name specific tools explicitly.

The system analyzes task intent and proactively injects:
- Matched tools from the manifest
- Phase-ordered execution sequence
- Relevant skill recommendations
- AIDB project context

Routes:
  GET  /tools/auto-select?task=<description>  — auto-select tools for a task
  GET  /tools/catalog                          — full tool catalog for discovery
  POST /tools/enrich-plan                      — annotate a plan with tool sequences
  GET  /tools/for-phase?phase=<id>&plan=<path> — tools for a specific plan phase
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


_logger: Any = None
_config: Any = None


def init(logger: Any = None, config: Any = None) -> None:
    global _logger, _config
    _logger = logger
    _config = config


def register_routes(app: Any) -> None:
    app.router.add_get("/tools/auto-select", handle_auto_select)
    app.router.add_get("/tools/catalog", handle_tool_catalog)
    app.router.add_post("/tools/enrich-plan", handle_enrich_plan)
    app.router.add_get("/tools/for-phase", handle_tools_for_phase)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_auto_select(request: Any) -> Any:
    """
    Automatically select and sequence tools for any task description.

    Any agent can call this at the START of any task — no need to know
    tool names. The system infers intent and returns a ready-to-use
    tool manifest with execution order.

    Query params:
      task    — Free-text task description (required)
      agent   — Agent type hint: qwen|claude|gemini|local|any (default: any)
      phase   — Workflow phase: discover|plan|execute|validate|handoff (default: all)
      limit   — Max tools to return (default: 8)
    """
    from aiohttp import web

    task = request.rel_url.query.get("task", "").strip()
    agent = request.rel_url.query.get("agent", "any").strip().lower()
    phase = request.rel_url.query.get("phase", "all").strip().lower()
    limit = int(request.rel_url.query.get("limit", "8"))

    if not task:
        return web.Response(
            status=400, content_type="application/json",
            text=json.dumps({"error": "task parameter is required"}),
        )

    try:
        from tooling_manifest import workflow_tool_catalog, build_tooling_manifest

        tools = workflow_tool_catalog(task)
        if limit:
            tools = tools[:limit]

        manifest = build_tooling_manifest(
            query=task,
            tools=tools,
            runtime="python",
            max_tools=limit,
        )

        # Enrich with skill recommendations
        skills = _recommend_skills(task)
        aidb_projects = _recommend_aidb_projects(task)
        execution_order = _build_execution_order(tools, phase)

        payload = {
            "task": task,
            "agent": agent,
            "tools": manifest.get("tools", []),
            "phases": manifest.get("phases", []),
            "execution_order": execution_order,
            "recommended_skills": skills,
            "aidb_projects": aidb_projects,
            "coordinator_url": f"http://127.0.0.1:{os.getenv('HYBRID_COORDINATOR_PORT', '8003')}",
            "instructions": (
                "Call tools in execution_order sequence. "
                "Use recommended_skills for specialized tasks. "
                "Query aidb_projects for domain knowledge. "
                "No explicit tool naming required — this manifest is auto-generated."
            ),
            "status": "ok",
        }

        return web.Response(
            status=200, content_type="application/json",
            text=json.dumps(payload),
        )
    except Exception as exc:
        if _logger:
            _logger.error("auto_select error: %s", exc)
        return web.Response(
            status=500, content_type="application/json",
            text=json.dumps({"error": str(exc)}),
        )


async def handle_tool_catalog(request: Any) -> Any:
    """
    Return the full tool catalog — everything available in the system.
    Any agent can call this once at startup for complete capability discovery.

    Query params:
      domain  — Filter by domain: core|design|trading|orchestration|research (default: all)
      format  — Response format: full|compact|names-only (default: compact)
    """
    from aiohttp import web

    domain = request.rel_url.query.get("domain", "all").strip().lower()
    fmt = request.rel_url.query.get("format", "compact").strip().lower()

    catalog = _build_full_catalog()

    if domain != "all":
        catalog = {k: v for k, v in catalog.items() if v.get("domain") == domain}

    if fmt == "names-only":
        result = list(catalog.keys())
    elif fmt == "compact":
        result = {
            name: {
                "endpoint": t["endpoint"],
                "method": t["method"],
                "description": t["description"],
                "domain": t["domain"],
            }
            for name, t in catalog.items()
        }
    else:
        result = catalog

    return web.Response(
        status=200, content_type="application/json",
        text=json.dumps({"tools": result, "count": len(catalog), "status": "ok"}),
    )


async def handle_enrich_plan(request: Any) -> Any:
    """
    Auto-annotate a phase plan file with tool sequences for each task.
    The system reads the plan, analyzes each task, and injects tool guidance.

    POST body:
      plan_path  — Relative path to plan file (e.g. .agents/plans/phase-24-...)
      write_back — Boolean: write enriched plan back to file (default: false)
    """
    from aiohttp import web

    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, content_type="application/json",
                            text=json.dumps({"error": "invalid JSON body"}))

    plan_path_rel = body.get("plan_path", "").strip()
    write_back = bool(body.get("write_back", False))

    if not plan_path_rel:
        return web.Response(status=400, content_type="application/json",
                            text=json.dumps({"error": "plan_path required"}))

    repo_root = _find_repo_root()
    plan_path = os.path.join(repo_root, plan_path_rel)

    if not os.path.isfile(plan_path):
        return web.Response(status=404, content_type="application/json",
                            text=json.dumps({"error": f"plan not found: {plan_path_rel}"}))

    try:
        with open(plan_path) as f:
            content = f.read()

        enriched, annotations = _enrich_plan_content(content)

        if write_back:
            with open(plan_path, "w") as f:
                f.write(enriched)

        return web.Response(
            status=200, content_type="application/json",
            text=json.dumps({
                "plan_path": plan_path_rel,
                "annotations": annotations,
                "write_back": write_back,
                "status": "ok",
            }),
        )
    except Exception as exc:
        return web.Response(status=500, content_type="application/json",
                            text=json.dumps({"error": str(exc)}))


async def handle_tools_for_phase(request: Any) -> Any:
    """
    Return the tool sequence for a specific phase/task in a plan.

    Query params:
      phase  — Phase ID or task description (required)
      plan   — Plan file path (optional — for context)
    """
    from aiohttp import web

    phase = request.rel_url.query.get("phase", "").strip()
    if not phase:
        return web.Response(status=400, content_type="application/json",
                            text=json.dumps({"error": "phase parameter required"}))

    try:
        from tooling_manifest import workflow_tool_catalog
        tools = workflow_tool_catalog(phase)[:6]
        sequence = _build_execution_order(tools, "all")

        return web.Response(
            status=200, content_type="application/json",
            text=json.dumps({
                "phase": phase,
                "tools": tools,
                "execution_sequence": sequence,
                "skills": _recommend_skills(phase),
                "status": "ok",
            }),
        )
    except Exception as exc:
        return web.Response(status=500, content_type="application/json",
                            text=json.dumps({"error": str(exc)}))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _recommend_skills(task: str) -> List[str]:
    q = task.lower()
    skills = []
    if any(k in q for k in ("design", "ui", "ux", "frontend", "css", "impeccable", "typography", "color")):
        skills.append("impeccable")
    if any(k in q for k in ("trade", "trading", "stock", "ticker", "market analysis", "portfolio")):
        skills.append("tradingagents")
    if any(k in q for k in ("nix", "nixos", "module", "deploy", "service")):
        skills.append("nixos-deployment")
    if any(k in q for k in ("debug", "error", "fail", "broken", "fix")):
        skills.append("debug-workflow")
    if any(k in q for k in ("mcp", "server", "protocol", "tool", "bridge")):
        skills.append("mcp-builder")
    return skills


def _recommend_aidb_projects(task: str) -> List[Dict[str, str]]:
    q = task.lower()
    projects = []
    if any(k in q for k in ("design", "ui", "ux", "frontend", "css", "impeccable", "typography")):
        projects.append({"project": "impeccable-design", "reason": "Frontend design reference docs"})
    if any(k in q for k in ("trade", "trading", "stock", "ticker", "financial", "market analysis")):
        projects.append({"project": "trading-knowledge", "reason": "Trading analysis knowledge base"})
    # Default: always include ai-stack project
    projects.append({"project": "ai-stack", "reason": "Project codebase and architecture docs"})
    return projects


def _build_execution_order(tools: List[Dict], phase_filter: str) -> List[Dict]:
    phase_order = ["discover", "plan", "execute", "validate", "handoff"]
    tool_phases: Dict[str, str] = {
        "hints": "discover",
        "discovery": "discover",
        "shared_skill_registry": "discover",
        "trading_tools": "discover",
        "impeccable_audit": "discover",
        "workflow_plan": "plan",
        "route_search": "execute",
        "memory_recall": "execute",
        "web_research_fetch": "execute",
        "trading_analyze": "execute",
        "trading_forecast": "execute",
        "trading_debate": "execute",
        "impeccable_reference": "execute",
        "ai_coordinator_delegate": "execute",
        "loop_orchestrate": "execute",
        "qa_check": "validate",
        "harness_eval": "validate",
        "health": "validate",
        "loop_status": "validate",
        "feedback": "handoff",
        "learning_stats": "handoff",
    }

    ordered = []
    seen = set()

    for p in phase_order:
        if phase_filter != "all" and p != phase_filter:
            continue
        for tool in tools:
            name = tool.get("name", "")
            if name in seen:
                continue
            if tool_phases.get(name, "execute") == p:
                ordered.append({
                    "step": len(ordered) + 1,
                    "tool": name,
                    "phase": p,
                    "endpoint": tool.get("endpoint", ""),
                    "reason": tool.get("reason", ""),
                })
                seen.add(name)

    # Add remaining tools not in phase map
    for tool in tools:
        name = tool.get("name", "")
        if name not in seen:
            ordered.append({
                "step": len(ordered) + 1,
                "tool": name,
                "phase": "execute",
                "endpoint": tool.get("endpoint", ""),
                "reason": tool.get("reason", ""),
            })
    return ordered


def _enrich_plan_content(content: str) -> tuple:
    """
    Scan plan markdown for task lines and inject tool annotations.
    Returns (enriched_content, list_of_annotations).
    """
    from tooling_manifest import workflow_tool_catalog

    lines = content.split("\n")
    enriched = []
    annotations = []

    i = 0
    while i < len(lines):
        line = lines[i]
        enriched.append(line)

        # Match task lines like "1. **P24-001a** — Create ..."
        if re.match(r'^\d+\.\s+\*\*\w+\*\*', line) or re.match(r'^-\s+\*\*P\d', line):
            task_text = re.sub(r'\*\*[^*]+\*\*\s*—?\s*', '', line).strip()
            if task_text and len(task_text) > 20:
                tools = workflow_tool_catalog(task_text)[:4]
                if tools:
                    tool_names = [t["name"] for t in tools]
                    annotations.append({
                        "task": task_text[:80],
                        "tools": tool_names,
                    })
                    # Only inject annotation if not already annotated
                    next_line = lines[i + 1] if i + 1 < len(lines) else ""
                    if "<!-- tools:" not in next_line:
                        enriched.append(f"   <!-- tools: {', '.join(tool_names)} -->")
        i += 1

    return "\n".join(enriched), annotations


def _build_full_catalog() -> Dict[str, Any]:
    """Build the complete tool catalog from all registered domains."""
    coordinator_port = os.getenv("HYBRID_COORDINATOR_PORT", "8003")
    base = f"http://127.0.0.1:{coordinator_port}"

    return {
        # Core workflow
        "hints": {"endpoint": f"{base}/hints", "method": "GET", "domain": "core",
                  "description": "Ranked workflow hints for any task — always call first"},
        "discovery": {"endpoint": f"{base}/discovery/capabilities", "method": "GET", "domain": "core",
                      "description": "Stack capability flags and feature availability"},
        "route_search": {"endpoint": f"{base}/query", "method": "POST", "domain": "core",
                         "description": "Hybrid RAG retrieval + LLM synthesis"},
        "memory_recall": {"endpoint": f"{base}/memory/recall", "method": "POST", "domain": "core",
                          "description": "Semantic memory search across prior sessions"},
        "feedback": {"endpoint": f"{base}/feedback", "method": "POST", "domain": "core",
                     "description": "Capture outcome, corrections, and ratings"},
        "health": {"endpoint": f"{base}/health", "method": "GET", "domain": "core",
                   "description": "Stack health check"},
        # Skills
        "shared_skill_registry": {"endpoint": f"{base}/control/ai-coordinator/skills", "method": "GET",
                                   "domain": "orchestration", "description": "All registered agent skills"},
        "agent_lessons_registry": {"endpoint": f"{base}/control/ai-coordinator/lessons", "method": "GET",
                                    "domain": "orchestration", "description": "Persisted agent lessons"},
        # Orchestration
        "ai_coordinator_delegate": {"endpoint": f"{base}/control/ai-coordinator/delegate",
                                     "method": "POST", "domain": "orchestration",
                                     "description": "Delegate task to runtime lane"},
        "loop_orchestrate": {"endpoint": f"{base}/workflow/orchestrate", "method": "POST",
                              "domain": "orchestration", "description": "Long-running multi-agent work"},
        "workflow_plan": {"endpoint": f"{base}/workflow/plan", "method": "POST", "domain": "orchestration",
                          "description": "Structured task planning"},
        # Auto-selection
        "auto_select": {"endpoint": f"{base}/tools/auto-select", "method": "GET", "domain": "core",
                        "description": "Auto-select tools for any task without naming them explicitly"},
        "tool_catalog": {"endpoint": f"{base}/tools/catalog", "method": "GET", "domain": "core",
                         "description": "Full tool catalog — call once at agent startup"},
        "enrich_plan": {"endpoint": f"{base}/tools/enrich-plan", "method": "POST", "domain": "core",
                        "description": "Auto-annotate plan files with tool sequences"},
        # Design (impeccable)
        "impeccable_audit": {"endpoint": f"{base}/control/ai-coordinator/skills", "method": "GET",
                              "domain": "design",
                              "description": "Frontend design intelligence — audit, critique, polish, craft"},
        "impeccable_reference": {"endpoint": f"{base}/query", "method": "POST", "domain": "design",
                                  "description": "Design reference docs from AIDB (project: impeccable-design)"},
        # Trading
        "trading_analyze": {"endpoint": f"{base}/trading/analyze", "method": "GET", "domain": "trading",
                             "description": "Full 5-team trading analysis pipeline"},
        "trading_forecast": {"endpoint": f"{base}/trading/forecast", "method": "GET", "domain": "trading",
                              "description": "Quick market signal (no full pipeline)"},
        "trading_tools": {"endpoint": f"{base}/trading/tools", "method": "GET", "domain": "trading",
                          "description": "Financial data tool discovery"},
        "trading_debate": {"endpoint": f"{base}/trading/debate", "method": "POST", "domain": "trading",
                           "description": "Trigger researcher bull/bear debate round"},
        # Research
        "web_research_fetch": {"endpoint": f"{base}/research/web/fetch", "method": "POST",
                                "domain": "research", "description": "Bounded web fetch for public URLs"},
        "curated_research_fetch": {"endpoint": f"{base}/research/workflows/curated-fetch",
                                    "method": "POST", "domain": "research",
                                    "description": "Manifest-backed research workflow"},
        # Quality
        "qa_check": {"endpoint": "mcp://run_qa_check", "method": "-", "domain": "quality",
                     "description": "aq-qa phase checks"},
        "harness_eval": {"endpoint": f"{base}/harness/eval", "method": "POST", "domain": "quality",
                         "description": "Deterministic eval scorecard"},
        # World model / forecasting
        "world_forecast": {"endpoint": f"{base}/world/forecast", "method": "GET", "domain": "core",
                           "description": "Predict upcoming queries based on usage patterns"},
    }


def _find_repo_root() -> str:
    """Walk up from this file to find the repo root (contains CLAUDE.md)."""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isfile(os.path.join(current, "CLAUDE.md")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.getcwd()
