#!/usr/bin/env python3
"""
Built-in AI Coordination Tools for Local Agents

Provides tools for local agents to interact with the AI stack:
- get_hint: Query hints engine
- delegate_to_remote: Send task to remote agent
- query_context: Query context memory
- store_memory: Store in context memory

Part of Phase 11 Batch 11.1: Tool Calling Infrastructure
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional

import httpx

from tool_registry import (
    SafetyPolicy,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
)

logger = logging.getLogger(__name__)


# Service endpoints
HYBRID_COORDINATOR_URL = "http://127.0.0.1:8003"
AIDB_URL = "http://127.0.0.1:8002"

MEMORY_TYPES = ("episodic", "semantic", "procedural", "working", "error_solutions", "interaction_history")
MEMORY_TYPE_ALIASES = {
    "note": "semantic",
    "observation": "episodic",
    "context": "episodic",
    "event": "episodic",
    "milestone": "episodic",
    "decision": "procedural",
    "procedure": "procedural",
    "error": "error_solutions",
    "error_solution": "error_solutions",
    "interaction": "interaction_history",
    # "working" is a conceptual scratch-pad alias for "semantic".
    # The coordinator has no separate working tier — scratch notes live in
    # semantic memory, distinguished by a "working_memory" tag on each entry.
    "working": "semantic",
}


def normalize_store_memory_type(context_type: str) -> str:
    """Map local-agent store_memory aliases onto coordinator memory tiers."""
    normalized = str(context_type or "").strip().lower()
    return MEMORY_TYPE_ALIASES.get(normalized, normalized or "semantic")


async def get_hint_handler(
    query: str,
    max_hints: int = 5,
) -> Dict:
    """
    Query the hints engine for relevant hints.

    Args:
        query: Query string
        max_hints: Maximum hints to return

    Returns:
        {
            "success": bool,
            "hints": [str],
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HYBRID_COORDINATOR_URL}/hints",
                params={"q": query, "max": max_hints},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "hints": data.get("hints", []),
                    "count": len(data.get("hints", [])),
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to query hints: {e}",
        }


async def delegate_to_remote_handler(
    task: str,
    agent_type: str = "codex",
    priority: str = "normal",
) -> Dict:
    """
    Delegate a task to a remote agent via the coordinator delegate lane.

    Args:
        task: Task description
        agent_type: Agent type (codex, claude, gemini)
        priority: Task priority (low, normal, high)

    Returns:
        {
            "success": bool,
            "response": str,
            "agent": str,
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{HYBRID_COORDINATOR_URL}/control/ai-coordinator/delegate",
                json={
                    "task": task,
                    "agent": agent_type,
                    "priority": priority,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", data.get("result", "")),
                    "task_id": data.get("task_id", ""),
                    "agent": agent_type,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to delegate task: {e}",
        }


async def query_context_handler(
    query: str,
    max_results: int = 10,
) -> Dict:
    """
    Query context memory for relevant information.

    Args:
        query: Query string
        max_results: Maximum results to return

    Returns:
        {
            "success": bool,
            "contexts": [{"content": str, "importance": float}],
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/memory/recall",
                json={
                    "query": query,
                    "memory_types": ["episodic", "semantic"],
                    "limit": max_results,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                return {
                    "success": True,
                    "contexts": [
                        {"content": r.get("content", ""), "importance": r.get("score", 0.5)}
                        for r in results
                    ],
                    "count": len(results),
                }
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def store_memory_handler(
    content: str,
    context_type: str = "semantic",
    importance: float = 0.5,
    tags: Optional[list] = None,
) -> Dict:
    """
    Store information in context memory.

    Args:
        content: Content to store
        context_type: Memory tier. Canonical values are episodic, semantic,
            procedural, working, error_solutions, interaction_history. Legacy
            aliases like note, decision, observation, and milestone are accepted.
        importance: Importance score (0.0-1.0)
        tags: Optional tags

    Returns:
        {
            "success": bool,
            "context_id": str,
            "error": str (if failed)
        }
    """
    try:
        memory_type = normalize_store_memory_type(context_type)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/memory/store",
                json={
                    "content": content,
                    "memory_type": memory_type,
                    "importance": importance,
                    "tags": tags or [],
                    "source": "local-agent",
                },
            )
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def execute_workflow_handler(
    yaml_file: str,
    inputs: Optional[Dict] = None,
    async_mode: bool = False,
) -> Dict:
    """Execute a YAML workflow via the coordinator's /yaml-workflow/execute endpoint."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/yaml-workflow/execute",
                json={
                    "workflow_file": yaml_file,
                    "inputs": inputs or {},
                    "async_mode": async_mode,
                },
            )
            if resp.status_code == 200:
                return {"success": True, **resp.json()}
            return {"success": False, "error": resp.text, "status_code": resp.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def discover_objectives_handler(
    context: str = "",
    limit: int = 5,
) -> Dict:
    """
    Research the codebase and propose ranked objectives for user approval.

    For each objective also populates:
      - context.relevant_files: file paths mentioned in the source data
      - context.recent_errors: matching error events from telemetry
      - context.prsi_items: pending PRSI actions related to the objective
      - constraints: inferred boundaries (validation gate, rebuild required, etc.)

    Returns a structured proposal. The agent MUST present it to the user and
    wait for approval — the terminal tool gate enforces this.
    """
    import json as _json
    import re as _re
    from pathlib import Path as _Path

    _FILE_RE = _re.compile(r'[\w./\-]+\.(?:py|nix|yaml|yml|json|sh|md|toml)\b')
    _REBUILD_KW = frozenset(["nix", "nixos", "apparmor", "switchboard", "service", "module", "rebuild"])
    _RESTART_KW = frozenset(["coordinator", "server", "handler", "daemon", "python"])
    _QA_KW = frozenset(["test", "qa", "health", "check", "validation"])

    def _infer_constraints(text: str) -> list:
        lo = text.lower()
        c = ["must pass scripts/governance/tier0-validation-gate.sh --pre-commit"]
        if any(k in lo for k in _REBUILD_KW):
            c.append("requires nixos-rebuild switch to activate")
        if any(k in lo for k in _RESTART_KW):
            c.append("requires service restart if Python-only change (no Nix)")
        if any(k in lo for k in _QA_KW):
            c.append("must pass aq-qa 0 after changes")
        if "apparmor" in lo:
            c.append("verify with: journalctl -u apparmor.service | grep -i error")
        return c

    def _extract_files(texts: list) -> list:
        seen: set = set()
        out: list = []
        for t in texts:
            for m in _FILE_RE.findall(str(t)):
                if m not in seen and len(m) > 4:
                    seen.add(m)
                    out.append(m)
        return out[:6]

    repo_root = _Path(os.environ.get("REPO_ROOT", "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy"))

    # ── Gather shared evidence upfront ────────────────────────────────────────

    # A. PRSI pending actions
    prsi_items: list = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/control/prsi/pending")
            if resp.status_code == 200:
                data = resp.json()
                actions = data if isinstance(data, list) else data.get("actions", [])
                for a in actions[:10]:
                    if a.get("approval", {}).get("at") is None:
                        prsi_items.append({
                            "id": a.get("id", "")[:16],
                            "action": a.get("action", ""),
                            "confidence": a.get("confidence"),
                            "reason": (a.get("raw_action") or {}).get("reason", "")[:80],
                        })
    except Exception:
        # Fall back to reading the queue file directly
        try:
            qf = _Path("/var/lib/nixos-ai-stack/prsi/action-queue.json")
            if qf.exists():
                data = _json.loads(qf.read_text())
                actions = data if isinstance(data, list) else data.get("actions", [])
                for a in actions[:10]:
                    if a.get("approval", {}).get("at") is None:
                        prsi_items.append({
                            "id": a.get("id", "")[:16],
                            "action": a.get("action", ""),
                            "confidence": a.get("confidence"),
                            "reason": (a.get("raw_action") or {}).get("reason", "")[:80],
                        })
        except Exception:
            pass

    # B. Recent error events from telemetry
    recent_errors: list = []
    try:
        _ERROR_KW = frozenset(["error", "fail", "stall", "eperm", "denied", "timeout", "exception"])
        telemetry_path = _Path(
            os.environ.get("HYBRID_TELEMETRY_PATH",
                           "/var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl")
        )
        if telemetry_path.exists():
            lines = telemetry_path.read_text().splitlines()[-200:]
            for ln in lines:
                try:
                    ev = _json.loads(ln)
                    ev_type = ev.get("event_type", "")
                    err = str(ev.get("error") or "")
                    if any(k in ev_type.lower() for k in _ERROR_KW) or any(k in err.lower() for k in _ERROR_KW):
                        recent_errors.append({
                            "ts": ev.get("timestamp", "")[:19],
                            "event": ev_type,
                            "detail": (err or ev.get("tool_name", ""))[:120],
                        })
                except Exception:
                    pass
            recent_errors = recent_errors[-10:]
    except Exception:
        pass

    # ── Build objectives ───────────────────────────────────────────────────────

    objectives: list = []

    # 1. RESUME.json — in-flight work (highest priority)
    try:
        resume_path = repo_root / ".agent" / "collaboration" / "RESUME.json"
        if resume_path.exists():
            resume = _json.loads(resume_path.read_text())
            current = resume.get("current_objective", "")
            pending = [t for t in resume.get("todo_snapshot", []) if not t.startswith("DONE")]
            uncommitted = resume.get("uncommitted_changes", [])
            if current or pending:
                combined_text = " ".join([current] + pending + uncommitted)
                objectives.append({
                    "rank": 1,
                    "source": "RESUME.json",
                    "title": f"Resume: {current}" if current else "Resume in-flight work",
                    "detail": pending[:3],
                    "reasoning": "Active work in progress — highest priority to maintain continuity.",
                    "priority": "critical",
                    "context": {
                        "relevant_files": _extract_files([combined_text]),
                        "recent_errors": [e for e in recent_errors[-3:]],
                        "prsi_items": prsi_items[:3],
                    },
                    "constraints": _infer_constraints(combined_text),
                })
    except Exception:
        pass

    # 2. issues-backlog.md — open/critical items
    try:
        backlog_path = repo_root / ".agent" / "memory" / "issues-backlog.md"
        if backlog_path.exists():
            lines = backlog_path.read_text().splitlines()
            open_items = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if any(tag in stripped for tag in ("[ ]", "OPEN", "CRITICAL", "TODO", "PENDING-REBUILD")):
                    open_items.append(stripped.lstrip("- ").lstrip("[ ] ").strip())
            for item in open_items[:3]:
                if any(o["title"][:60] == item[:60] for o in objectives):
                    continue
                priority = "high" if any(t in item for t in ("CRITICAL", "PENDING-REBUILD")) else "medium"
                # Filter errors relevant to this item's keywords
                item_lo = item.lower()
                item_errors = [e for e in recent_errors if any(w in e["detail"].lower() for w in item_lo.split()[:4])][:2]
                objectives.append({
                    "rank": len(objectives) + 1,
                    "source": "issues-backlog.md",
                    "title": item[:120],
                    "reasoning": "Tracked open issue requiring resolution.",
                    "priority": priority,
                    "context": {
                        "relevant_files": _extract_files([item]),
                        "recent_errors": item_errors,
                        "prsi_items": [p for p in prsi_items if any(w in p["action"] for w in item_lo.split()[:3])][:2],
                    },
                    "constraints": _infer_constraints(item),
                })
    except Exception:
        pass

    # 3. AIDB error-solutions — known patterns needing attention
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            query = context or "pending high priority fix error"
            resp = await client.post(f"{AIDB_URL}/vector/search", json={
                "query": query,
                "collection": "error-solutions",
                "limit": 3,
            })
            if resp.status_code == 200:
                for hit in resp.json().get("results", []):
                    payload = hit.get("payload", {})
                    title = (payload.get("title") or payload.get("problem", ""))[:100]
                    solution = payload.get("solution", "")[:200]
                    if not title:
                        continue
                    if any(o["title"][:60] == title[:60] for o in objectives):
                        continue
                    score = hit.get("score", 0)
                    combined = f"{title} {solution}"
                    objectives.append({
                        "rank": len(objectives) + 1,
                        "source": "aidb:error-solutions",
                        "title": title,
                        "reasoning": f"Known error pattern (relevance {score:.2f}). Suggested fix: {solution[:100]}",
                        "priority": "high" if score > 0.65 else "medium",
                        "score": round(score, 3),
                        "context": {
                            "relevant_files": _extract_files([combined]),
                            "recent_errors": [e for e in recent_errors if any(w in e["detail"].lower() for w in title.lower().split()[:4])][:2],
                            "prsi_items": [],
                        },
                        "constraints": _infer_constraints(combined),
                    })
    except Exception:
        pass

    # 4. PRSI-sourced objectives — unapproved high-confidence actions
    for p in prsi_items[:2]:
        title = f"PRSI: {p['action']} — {p['reason']}" if p["reason"] else f"PRSI: {p['action']}"
        if any(o["title"][:60] == title[:60] for o in objectives):
            continue
        objectives.append({
            "rank": len(objectives) + 1,
            "source": f"prsi:action-queue ({p['id']})",
            "title": title[:120],
            "reasoning": f"Pending PRSI action (confidence {p['confidence']}) awaiting approval.",
            "priority": "medium",
            "context": {
                "relevant_files": [],
                "recent_errors": [],
                "prsi_items": [p],
            },
            "constraints": _infer_constraints(p["action"]),
        })

    # ── Final assembly ─────────────────────────────────────────────────────────

    objectives = objectives[:limit]
    for i, obj in enumerate(objectives, 1):
        obj["rank"] = i

    # Last PULSE entry for session continuity
    last_pulse = ""
    try:
        pulse_path = repo_root / ".agent" / "collaboration" / "PULSE.log"
        if pulse_path.exists():
            recent = pulse_path.read_text().splitlines()
            last_pulse = next((ln for ln in reversed(recent) if ln.strip()), "")
    except Exception:
        pass

    return {
        "proposal_type": "objective_discovery",
        "instruction": (
            "STOP — do not call any more tools. Present the ranked objectives below "
            "to the user as a numbered list. For each include: title, source, priority, "
            "reasoning, context (relevant_files, recent_errors, prsi_items), and constraints. "
            "End with: 'Please reply with a number to select, or describe a different goal.' "
            "Wait for their approval before taking any action."
        ),
        "objectives": objectives,
        "last_pulse": last_pulse[-120:] if last_pulse else "",
        "prsi_pending_total": len(prsi_items),
        "recommendation": (
            objectives[0]["title"] if objectives
            else "No pending objectives found. Please describe what you'd like to work on."
        ),
    }


async def get_workflow_status_handler(workflow_id: str) -> Dict:
    """
    Get status of a running workflow.

    Args:
        workflow_id: Workflow ID

    Returns:
        {
            "success": bool,
            "status": str,
            "progress": float,
            "error": str (if failed)
        }
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{HYBRID_COORDINATOR_URL}/workflow/orchestrate/{workflow_id}",
                timeout=5.0,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "status": data.get("status", "unknown"),
                    "progress": data.get("progress", 0.0),
                    "workflow_id": workflow_id,
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get workflow status: {e}",
        }


async def run_opencode_handler(
    prompt: str,
    model: Optional[str] = None,
) -> Dict:
    """
    Invoke the opencode CLI coding agent with the given prompt.

    The model is resolved from the SWB_REMOTE_MODEL_ALIAS_OPENCODE env var
    when not explicitly provided, falling back to the configured remote-free
    alias so free capacity is used by default.

    Args:
        prompt: Coding task description passed to opencode
        model:  Override model id (OpenRouter format, e.g. qwen/qwen3-235b-a22b:free)

    Returns:
        {
            "success": bool,
            "output": str,
            "model": str,
            "error": str (if failed)
        }
    """
    import asyncio
    import shutil

    opencode_bin = shutil.which("opencode")
    if not opencode_bin:
        return {"success": False, "error": "opencode not found in PATH"}

    resolved_model = (
        model
        or os.getenv("SWB_REMOTE_MODEL_ALIAS_OPENCODE")
        or os.getenv("SWB_REMOTE_MODEL_ALIAS_FREE")
        or ""
    )

    cmd = [opencode_bin, "run", "--print", prompt]
    env = {**os.environ}
    if resolved_model:
        env["OPENCODE_MODEL"] = resolved_model

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
        if proc.returncode == 0:
            return {
                "success": True,
                "output": stdout.decode().strip(),
                "model": resolved_model,
            }
        return {
            "success": False,
            "error": stderr.decode().strip() or f"exit code {proc.returncode}",
            "model": resolved_model,
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": "opencode timed out after 120s", "model": resolved_model}
    except Exception as e:
        return {"success": False, "error": str(e), "model": resolved_model}


async def harness_health_handler(phase: str = "0") -> Dict:
    """Proxy for run_qa_check (harness_health)"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/qa/check", json={"phase": phase})
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_prsi_pending_handler() -> Dict:
    """Proxy for get_prsi_pending"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/control/prsi/pending")
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def prsi_orchestrate_handler(action: str, action_id: Optional[str] = None, note: Optional[str] = None) -> Dict:
    """Proxy for prsi_orchestrate"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"action": action, "action_id": action_id, "note": note}
            # Note: The coordinator might use different endpoints for different actions
            if action == "execute":
                resp = await client.post(f"{HYBRID_COORDINATOR_URL}/control/prsi/actions/execute", json=payload)
            else:
                resp = await client.get(f"{HYBRID_COORDINATOR_URL}/control/prsi/actions", params=payload)
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def recommend_agent_for_task_handler(query: str) -> Dict:
    """
    Recommend an agent role for the given task query.

    Uses GET /control/agents/roles for the role catalogue, then scores locally
    via keyword matching — no /federated/recommend route exists in coordinator.
    """
    _ROLE_KEYWORDS: dict = {
        "coordinator": ["orchestrate", "plan", "delegate", "coordinate", "workflow", "multi"],
        "coder": ["code", "implement", "write", "fix", "debug", "refactor", "patch", "function", "class"],
        "reviewer": ["review", "audit", "check", "evaluate", "assess", "verify", "feedback"],
        "researcher": ["research", "find", "search", "gather", "context", "information", "lookup"],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/control/agents/roles")
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
            roles = resp.json().get("roles", [])

        q_lower = query.lower()
        best_role = "agent"
        best_score = 0
        for role_entry in roles:
            role = role_entry.get("role", "")
            keywords = _ROLE_KEYWORDS.get(role, [])
            score = sum(1 for kw in keywords if kw in q_lower)
            if score > best_score:
                best_score = score
                best_role = role

        return {
            "success": True,
            "recommended_agent": best_role,
            "query": query,
            "available_roles": [r.get("role") for r in roles],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _query_qdrant_direct(query: str, collection: str, limit: int) -> Dict:
    """Embed query via llama-embed (8081) then search Qdrant directly (6333).
    Primary path for harness-seeded collections (error-solutions, skills-patterns, etc.).
    Normalises response to the shape expected by agent tool callers."""
    embed_url = os.environ.get("AI_STACK_EMBED_ENDPOINT", "http://127.0.0.1:8081")
    qdrant_url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
    # Port 6333 is Qdrant (seed target). Port 8002 is AIDB pgvector (separate store).
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            er = await client.post(f"{embed_url}/v1/embeddings",
                                   json={"model": "bge-m3", "input": query})
            if er.status_code != 200:
                return {"success": False, "error": f"embed failed {er.status_code}: {er.text[:200]}"}
            vector = er.json()["data"][0]["embedding"]
            sr = await client.post(
                f"{qdrant_url}/collections/{collection}/points/search",
                json={"vector": vector, "limit": limit, "with_payload": True},
            )
            if sr.status_code != 200:
                return {"success": False, "error": f"qdrant {sr.status_code}: {sr.text[:200]}"}
            hits = sr.json().get("result", [])
            # Deduplicate by title — same pattern seeded across multiple runs
            # produces identical Qdrant points. Keep highest-scored entry per title.
            seen_titles: set = set()
            deduped = []
            for h in hits:
                p = h.get("payload") or {}
                title = p.get("error_type") or p.get("title") or p.get("skill_name", "")
                if title and title in seen_titles:
                    continue
                seen_titles.add(title)
                deduped.append({
                    "title": title,
                    "content": p.get("solution") or p.get("description", ""),
                    "score": h.get("score", 0.0),
                    "source": f"qdrant:{collection}",
                    "payload": p,
                })
            return {
                "success": True,
                "results": deduped,
                "count": len(deduped),
                "fallback": "qdrant-direct",
            }
    except Exception as e:
        return {"success": False, "error": f"qdrant-direct: {e}"}


# Collections seeded directly to Qdrant (port 6333) by seed-rag-knowledge.py and training pipeline.
# These are separate from AIDB's pgvector store (port 8002) which holds document chunks.
# Phase 175: AIDB pgvector returns wrong content for these names (MCP registry entries, not
# harness patterns) — always go direct to Qdrant for harness pattern collections.
_QDRANT_COLLECTIONS: frozenset = frozenset({
    "error-solutions", "skills-patterns", "best-practices", "codebase-context",
    "knowledge", "interaction-history", "agent-memory-episodic", "agent-memory-semantic",
    "agent-memory-procedural", "learning-feedback", "trading-patterns", "mlops-patterns",
    "qa-patterns", "osint-intelligence",
})


async def query_aidb_handler(query: str, collection: str = "error-solutions", limit: int = 5) -> Dict:
    """Search harness pattern collections. Default 'error-solutions' has 66 seeded fix patterns.

    Routes to Qdrant-direct (embed via llama-embed:8081 + search Qdrant:6333) for all
    harness-seeded collections. AIDB pgvector (port 8002) is a separate document store
    with different content — not used for harness pattern queries.
    """
    if collection in _QDRANT_COLLECTIONS:
        return await _query_qdrant_direct(query, collection, limit)
    # Non-harness collections: try AIDB pgvector
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{AIDB_URL}/vector/search",
                json={"query": query, "collection": collection, "limit": limit},
            )
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_working_memory_handler() -> Dict:
    """Proxy for recall_agent_memory (get_working_memory)"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/memory/recall", json={"query": "working memory summary", "memory_types": ["semantic"]})
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def mesh_discovery_handler() -> Dict:
    """Get active agents, teams, and capabilities from the mesh."""
    try:
        from collective_memory import CollectiveMemory
        mem = CollectiveMemory()
        active_teams = mem.get_active_teams()
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{HYBRID_COORDINATOR_URL}/discovery/capabilities")
            capabilities = resp.json() if resp.status_code == 200 else {}
            
        return {
            "success": True,
            "active_teams": active_teams,
            "team_count": len(active_teams),
            "capabilities": capabilities.get("capabilities", []),
            "redis_connected": mem.is_redis_connected(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def collective_memory_search_handler(query: str, limit: int = 5) -> Dict:
    """Search historical collaboration records in the collective memory (Qdrant).

    Phase 175-A: was calling AIDB pgvector /vector/search with collection="knowledge"
    but "knowledge" is a Qdrant collection (_QDRANT_COLLECTIONS), not pgvector. Every
    call silently returned wrong content. Fixed to route through _query_qdrant_direct.
    """
    return await _query_qdrant_direct(query, "knowledge", limit)


async def post_review_finding_handler(
    board_key: str,
    component: str,
    severity: str,
    finding: str,
    file_line: str = "",
    agent_name: str = "agent",
) -> Dict:
    """Post a review finding to the collaborative review board in coordinator memory.

    Findings are stored as semantic memories tagged with board_key so that
    subsequent agents can read them via read_review_board before writing their own.
    """
    importance = 0.9 if severity == "P0" else 0.7 if severity == "P1" else 0.5
    content = (
        f"[review-board:{board_key}] {severity} {component} — {finding}"
        + (f" ({file_line})" if file_line else "")
        + f" [agent:{agent_name}]"
    )
    return await store_memory_handler(
        content=content,
        context_type="semantic",
        importance=importance,
        tags=["review-board", board_key, severity, component, agent_name],
    )


async def read_review_board_handler(board_key: str) -> Dict:
    """Read all findings posted to a collaborative review board.

    Queries coordinator semantic memory for entries tagged with the board_key.
    Returns findings from all agents that have posted to the board.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/memory/recall",
                json={
                    "query": f"review-board {board_key}",
                    "memory_types": ["semantic"],
                    "limit": 50,
                },
            )
            if resp.status_code != 200:
                return {"success": False, "error": resp.text}
            data = resp.json()
            memories = data.get("memories", []) if isinstance(data, dict) else []
            board_tag = f"review-board:{board_key}"
            board_entries = [
                m for m in memories
                if isinstance(m, dict) and board_tag in str(m.get("content", ""))
            ]
            return {
                "success": True,
                "board_key": board_key,
                "findings": board_entries,
                "count": len(board_entries),
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_unified_stack_health_handler() -> Dict:
    """Get a comprehensive health snapshot of the local AI stack."""
    try:
        api_key_path = "/run/secrets/hybrid_coordinator_api_key"
        api_key = ""
        if os.path.exists(api_key_path):
            with open(api_key_path, "r") as f:
                api_key = f.read().strip()

        headers = {"X-API-Key": api_key} if api_key else {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Parallel fetch for optimal performance
            status_task = client.get(f"{HYBRID_COORDINATOR_URL}/status", headers=headers)
            rate_limit_task = client.get(f"{HYBRID_COORDINATOR_URL}/admin/v1/policy/rate-limit-stats", headers=headers)
            hardware_task = client.get(f"{HYBRID_COORDINATOR_URL}/api/hardware/state", headers=headers)

            resps = await asyncio.gather(status_task, rate_limit_task, hardware_task, return_exceptions=True)

            results = []
            for r in resps:
                if isinstance(r, httpx.Response):
                    results.append(r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}"})
                else:
                    results.append({"error": str(r)})

            return {
                "success": True,
                "status": results[0],
                "rate_limiting": results[1],
                "hardware": results[2],
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def web_research_fetch_handler(
    urls: list,
    selectors: Optional[list] = None,
    max_text_chars: Optional[int] = None,
) -> Dict:
    """Fetch and extract text from one or more URLs via the coordinator web research engine."""
    try:
        payload: Dict = {"urls": urls}
        if selectors:
            payload["selectors"] = selectors
        if max_text_chars is not None:
            payload["max_text_chars"] = max_text_chars
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/research/web/fetch",
                json=payload,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def osint_research_ingest_handler(
    workflow: str,
    inputs: Optional[dict] = None,
    max_text_chars: Optional[int] = None,
    persist: bool = False,
) -> Dict:
    """Run a passive curated OSINT workflow and return osint-intelligence ledger records."""
    try:
        payload: Dict = {"workflow_slug": workflow}
        if inputs:
            payload["inputs"] = inputs
        if max_text_chars is not None:
            payload["max_text_chars"] = max_text_chars
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/research/workflows/curated-fetch",
                json=payload,
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            result = resp.json()
            ledger_records = []
            for item in result.get("results", []) or []:
                page = item.get("result") if isinstance(item.get("result"), dict) else {}
                excerpt = str(page.get("text_excerpt") or "").strip()
                if not excerpt:
                    continue
                requested_url = str(item.get("requested_url") or page.get("requested_url") or page.get("url") or "").strip()
                ledger_records.append(
                    {
                        "type": "observed-data",
                        "spec_version": "2.1",
                        "namespace": "osint-intelligence",
                        "schema_version": "stix-2.1-lite",
                        "workflow": str((result.get("workflow") or {}).get("slug") or workflow),
                        "source_name": str(item.get("source_name") or ""),
                        "selector": ",".join(str(sel).strip() for sel in (item.get("selectors") or []) if str(sel).strip()) or requested_url,
                        "source_url": requested_url,
                        "fact_type": "public_web_extract",
                        "status": str(item.get("status") or "ok"),
                        "confidence": 0.75 if item.get("status") == "ok" else 0.35,
                        "title": str(page.get("title") or ""),
                        "content": excerpt[:4000],
                        "links": page.get("links") if isinstance(page.get("links"), list) else [],
                    }
                )
            persisted = []
            if persist:
                for record in ledger_records:
                    stored = await store_memory_handler(
                        content=record["content"],
                        context_type="semantic",
                        importance=0.65,
                        tags=[
                            "osint-intelligence",
                            "stix-2.1-lite",
                            str(record.get("workflow") or workflow),
                            str(record.get("source_name") or "source"),
                        ],
                    )
                    persisted.append(stored)
            return {
                "success": True,
                "namespace": "osint-intelligence",
                "schema": "stix-2.1-lite",
                "ledger_count": len(ledger_records),
                "ledger_records": ledger_records,
                "persisted_count": len([item for item in persisted if isinstance(item, dict) and not item.get("error")]),
                "persisted": persisted,
                "research": result,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def osint_research_query_handler(
    query: str,
    max_results: int = 8,
    workflow: str = "",
) -> Dict:
    """Query shared memory for previously persisted osint-intelligence evidence."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{HYBRID_COORDINATOR_URL}/memory/recall",
                json={
                    "query": f"osint-intelligence {query}",
                    "memory_types": ["semantic", "episodic"],
                    "limit": max(1, min(int(max_results), 25)),
                },
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()
            evidence = []
            wanted_workflow = str(workflow or "").strip()
            for row in data.get("results", []) or []:
                metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                context = row.get("context") if isinstance(row.get("context"), dict) else {}
                payload = metadata or context
                record = payload.get("record") if isinstance(payload.get("record"), dict) else {}
                tags = {str(tag) for tag in row.get("tags", [])} if isinstance(row.get("tags"), list) else set()
                namespace = payload.get("namespace") or record.get("namespace")
                if namespace != "osint-intelligence" and "osint-intelligence" not in tags:
                    continue
                record_workflow = str(payload.get("workflow") or record.get("workflow") or "")
                if wanted_workflow and record_workflow != wanted_workflow:
                    continue
                evidence.append(
                    {
                        "score": row.get("score"),
                        "summary": row.get("summary") or str(row.get("content") or "")[:160],
                        "content": row.get("content") or record.get("content"),
                        "source_url": payload.get("source_url") or record.get("source_url"),
                        "source_name": payload.get("source_name") or record.get("source_name"),
                        "workflow": record_workflow,
                        "fact_type": payload.get("fact_type") or record.get("fact_type"),
                        "title": record.get("title"),
                        "record": record,
                    }
                )
            return {
                "success": True,
                "namespace": "osint-intelligence",
                "query": query,
                "count": len(evidence),
                "evidence": evidence,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def delegate_to_aider_handler(
    prompt: str,
    files: Optional[list] = None,
    workspace: Optional[str] = None,
) -> Dict:
    """Delegate a multi-file coding task to the aider coding assistant.
    Aider applies the change, returns the diff. Best for targeted edits
    requiring >4K tokens of context that exceed local model budget.
    """
    try:
        aider_url = os.environ.get("AIDER_WRAPPER_URL", "http://127.0.0.1:8090")
        aider_key_path = "/run/secrets/aider_wrapper_api_key"
        aider_key = ""
        if os.path.exists(aider_key_path):
            with open(aider_key_path) as f:
                aider_key = f.read().strip()
        headers = {"Authorization": f"Bearer {aider_key}"} if aider_key else {}
        payload: Dict = {"prompt": prompt}
        if files:
            payload["files"] = files
        if workspace:
            payload["workspace"] = workspace
        async with httpx.AsyncClient(timeout=300.0) as client:
            # submit task
            resp = await client.post(f"{aider_url}/tasks", json=payload, headers=headers)
            if resp.status_code not in (200, 201, 202):
                return {"success": False, "error": f"aider submit HTTP {resp.status_code}: {resp.text[:200]}"}
            task_data = resp.json()
            task_id = task_data.get("task_id") or task_data.get("id")
            if not task_id:
                return {"success": False, "error": "aider returned no task_id"}
            # poll for completion (max 270s)
            import asyncio as _asyncio
            for _ in range(54):
                await _asyncio.sleep(5)
                sr = await client.get(f"{aider_url}/tasks/{task_id}/status", headers=headers)
                if sr.status_code == 200:
                    status_data = sr.json()
                    st = status_data.get("status", "")
                    if st in ("completed", "done", "success"):
                        return {"success": True, "task_id": task_id, "result": status_data}
                    if st in ("failed", "error"):
                        return {"success": False, "task_id": task_id, "error": status_data.get("error", "aider task failed")}
            return {"success": False, "error": "aider task polling timed out (270s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


_HARNESS_CLI_WHITELIST = frozenset({
    "aq-qa", "aq-hints", "aq-report", "aq-session-start",
    "aq-commit-facts", "aq-lesson-promote", "aq-crystallize",
    "aqd",
})


async def run_harness_cli_handler(tool: str, args: Optional[list] = None) -> Dict:
    """
    Run an aq-* harness CLI tool with a fixed security whitelist.

    Args:
        tool: Harness tool name (must be in whitelist: aq-qa, aq-hints, aq-report, etc.)
        args: Optional list of string arguments to pass to the tool

    Returns:
        {"success": bool, "output": str, "tool": str, "error": str (if failed)}
    """
    if tool not in _HARNESS_CLI_WHITELIST:
        return {
            "success": False,
            "error": f"Tool '{tool}' not in harness whitelist. Allowed: {sorted(_HARNESS_CLI_WHITELIST)}",
        }
    cmd_args = [tool] + [str(a) for a in (args or [])]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "tool": tool, "error": "timed out after 60s"}
        output = stdout.decode("utf-8", errors="replace").strip()
        # Trim to 3000 chars to respect tool result cap
        if len(output) > 3000:
            output = output[:3000] + "\n[output truncated]"
        return {"success": proc.returncode == 0, "tool": tool, "output": output}
    except FileNotFoundError:
        return {"success": False, "tool": tool, "error": f"'{tool}' not found in PATH"}
    except Exception as e:
        return {"success": False, "tool": tool, "error": str(e)}


def register_ai_coordination_tools(registry: ToolRegistry):
    """Register all AI coordination tools in the registry"""

    # get_hint
    registry.register(ToolDefinition(
        name="get_hint",
        description="Query the hints engine for relevant hints and guidance",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query string",
                },
                "max_hints": {
                    "type": "integer",
                    "description": "Maximum hints to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_hint_handler,
    ))

    # delegate_to_remote
    registry.register(ToolDefinition(
        name="delegate_to_remote",
        description="Delegate a task to a remote agent (codex, claude, qwen)",
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task description",
                },
                "agent_type": {
                    "type": "string",
                    "description": "Agent type",
                    "enum": ["codex", "claude", "qwen", "opencode"],
                    "default": "codex",
                },
                "priority": {
                    "type": "string",
                    "description": "Task priority",
                    "enum": ["low", "normal", "high"],
                    "default": "normal",
                },
            },
            "required": ["task"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=delegate_to_remote_handler,
    ))

    # query_context
    registry.register(ToolDefinition(
        name="query_context",
        description="Query context memory for relevant information",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=query_context_handler,
    ))

    # store_memory
    registry.register(ToolDefinition(
        name="store_memory",
        description="Store information in agent memory using canonical memory tiers",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to store",
                },
                "context_type": {
                    "type": "string",
                    "description": (
                        "Memory tier. Use episodic for events/milestones, semantic for facts, "
                        "procedural for decisions/procedures, working for active scratch memory, "
                        "error_solutions for bug fixes, interaction_history for conversations."
                    ),
                    "enum": list(MEMORY_TYPES),
                    "default": "semantic",
                },
                "importance": {
                    "type": "number",
                    "description": "Importance score (0.0-1.0)",
                    "default": 0.5,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags",
                },
            },
            "required": ["content"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=store_memory_handler,
    ))

    # get_workflow_status
    registry.register(ToolDefinition(
        name="get_workflow_status",
        description="Get status of a running workflow",
        parameters={
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow ID",
                },
            },
            "required": ["workflow_id"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_workflow_status_handler,
    ))

    # execute_workflow
    registry.register(ToolDefinition(
        name="execute_workflow",
        description=(
            "Execute a YAML workflow from file through the harness coordinator. "
            "Dispatches each workflow node as a sub-agent task. "
            "Returns execution_id and status when complete."
        ),
        parameters={
            "type": "object",
            "properties": {
                "yaml_file": {
                    "type": "string",
                    "description": "Path to workflow YAML file (relative to repo root or absolute)",
                },
                "inputs": {
                    "type": "object",
                    "description": "Input parameters for the workflow (key-value dict)",
                },
                "async_mode": {
                    "type": "boolean",
                    "description": "Run in background (default false — wait for result)",
                },
            },
            "required": ["yaml_file"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        handler=execute_workflow_handler,
    ))

    # run_opencode
    registry.register(ToolDefinition(
        name="run_opencode",
        description=(
            "Invoke the opencode CLI coding agent for file-editing, refactoring, or "
            "code-generation tasks. Routes through the free remote model lane by default "
            "(SWB_REMOTE_MODEL_ALIAS_OPENCODE). Use for concrete implementation work to "
            "preserve paid-tier budget."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Coding task description",
                },
                "model": {
                    "type": "string",
                    "description": (
                        "Override model id in OpenRouter format "
                        "(e.g. qwen/qwen3-235b-a22b:free). "
                        "Defaults to SWB_REMOTE_MODEL_ALIAS_OPENCODE env var."
                    ),
                },
            },
            "required": ["prompt"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.WRITE_SAFE,
        sandbox_profile="execute-guarded",
        network_policy="loopback",
        timeout_seconds=120,
        handler=run_opencode_handler,
    ))

    # harness_health
    registry.register(ToolDefinition(
        name="harness_health",
        description="Run AI stack health checks (qa_check)",
        parameters={
            "type": "object",
            "properties": {
                "phase": {
                    "type": "string",
                    "description": "QA phase to run (0-10)",
                    "default": "0",
                },
            },
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=harness_health_handler,
    ))

    # get_prsi_pending
    registry.register(ToolDefinition(
        name="get_prsi_pending",
        description="Get list of pending PRSI optimization actions",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_prsi_pending_handler,
    ))

    # prsi_orchestrate
    registry.register(ToolDefinition(
        name="prsi_orchestrate",
        description="Approve, reject, or execute PRSI actions",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["approve", "reject", "sync", "execute"],
                },
                "action_id": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["action"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.SYSTEM_MODIFY,
        handler=prsi_orchestrate_handler,
    ))

    # recommend_agent_for_task
    registry.register(ToolDefinition(
        name="recommend_agent_for_task",
        description="Get recommendation for the best agent to handle a task (agent mesh)",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=recommend_agent_for_task_handler,
    ))

    # query_aidb
    registry.register(ToolDefinition(
        name="query_aidb",
        description="Search the AI stack knowledge base (hybrid_search)",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=query_aidb_handler,
    ))

    # get_working_memory
    registry.register(ToolDefinition(
        name="get_working_memory",
        description="Retrieve recent session facts and decisions",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_working_memory_handler,
    ))

    # mesh_discovery
    registry.register(ToolDefinition(
        name="mesh_discovery",
        description="Discover active agents, teams, and capabilities in the mesh",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=mesh_discovery_handler,
    ))

    # collective_memory_search
    registry.register(ToolDefinition(
        name="collective_memory_search",
        description="Search past agent collaborations and lessons learned",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=collective_memory_search_handler,
    ))

    # get_unified_stack_health
    registry.register(ToolDefinition(
        name="get_unified_stack_health",
        description="Get a comprehensive health snapshot of the local AI stack (status, rate-limits, hardware)",
        parameters={"type": "object", "properties": {}},
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=get_unified_stack_health_handler,
    ))

    # web_research_fetch
    registry.register(ToolDefinition(
        name="web_research_fetch",
        description=(
            "Fetch and extract readable text from one or more URLs. "
            "Handles robots.txt, redirect chains, and CSS selector extraction. "
            "Use for live web research, documentation lookups, and scraping."
        ),
        parameters={
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to fetch (max 5)",
                },
                "selectors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CSS selectors to extract specific page regions",
                },
                "max_text_chars": {
                    "type": "integer",
                    "description": "Max characters of extracted text per page (default 8000)",
                },
            },
            "required": ["urls"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=web_research_fetch_handler,
    ))

    registry.register(ToolDefinition(
        name="osint_research_ingest",
        description=(
            "Run a passive curated OSINT research workflow and return STIX-like ledger "
            "records for the osint-intelligence database. Use this for website/client "
            "research, public source aggregation, and multi-source design discovery. "
            "Does not perform active scanning."
        ),
        parameters={
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "string",
                    "description": "Curated research workflow slug",
                },
                "inputs": {
                    "type": "object",
                    "description": "Workflow input values such as topic, domain, organization, or query",
                },
                "max_text_chars": {
                    "type": "integer",
                    "description": "Maximum extracted characters per source",
                },
                "persist": {
                    "type": "boolean",
                    "description": "Persist bounded ledger records into shared harness memory",
                },
            },
            "required": ["workflow"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=osint_research_ingest_handler,
    ))

    registry.register(ToolDefinition(
        name="osint_research_query",
        description=(
            "Query persisted passive OSINT evidence from the osint-intelligence database. "
            "Use after osint_research_ingest with persist=true, or when answering from the shared research ledger."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Evidence query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum evidence records to return",
                },
                "workflow": {
                    "type": "string",
                    "description": "Optional workflow slug filter",
                },
            },
            "required": ["query"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=osint_research_query_handler,
    ))

    # discover_objectives
    registry.register(ToolDefinition(
        name="discover_objectives",
        description=(
            "Research the codebase and propose ranked objectives for user approval. "
            "Call when you need direction or no explicit task was given. "
            "Queries AIDB, issues-backlog.md, RESUME.json, and PULSE.log. "
            "AFTER CALLING: present results to user as a numbered list and STOP — "
            "do not call any other tools or take any action until the user confirms."
        ),
        parameters={
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Optional focus context to narrow the AIDB search (e.g. 'AppArmor', 'coordinator')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of objectives to propose (default 5)",
                    "default": 5,
                },
            },
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=discover_objectives_handler,
    ))

    # run_harness_cli
    registry.register(ToolDefinition(
        name="run_harness_cli",
        description=(
            "Run an aq-* harness CLI tool (aq-qa, aq-hints, aq-report, aq-session-start, "
            "aq-commit-facts, aq-lesson-promote, aq-crystallize, aqd). "
            "Use for health checks, hint queries, and harness reports. "
            "Returns the tool output as a string."
        ),
        parameters={
            "type": "object",
            "properties": {
                "tool": {
                    "type": "string",
                    "description": "Harness tool name (e.g. 'aq-qa', 'aq-hints', 'aq-report')",
                    "enum": sorted(_HARNESS_CLI_WHITELIST),
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional arguments (e.g. ['0'] for aq-qa phase 0)",
                },
            },
            "required": ["tool"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=run_harness_cli_handler,
    ))

    # delegate_to_aider
    registry.register(ToolDefinition(
        name="delegate_to_aider",
        description=(
            "Delegate a multi-file coding task to the aider AI coding assistant. "
            "Aider applies the edit and returns the diff. "
            "Use when a change requires reading >4K tokens of file context "
            "that exceeds the local model budget."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Natural-language instruction for the code change",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relative file paths aider should read/edit",
                },
                "workspace": {
                    "type": "string",
                    "description": "Absolute path to workspace root (defaults to repo root)",
                },
            },
            "required": ["prompt"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.SYSTEM_MODIFY,
        handler=delegate_to_aider_handler,
    ))

    # post_review_finding
    registry.register(ToolDefinition(
        name="post_review_finding",
        description=(
            "Post a finding to the collaborative review board in coordinator memory. "
            "Use during multi-agent reviews to share discoveries with other agents. "
            "Other agents read the board via read_review_board before writing their findings."
        ),
        parameters={
            "type": "object",
            "properties": {
                "board_key": {"type": "string", "description": "Review board identifier (e.g. 'phase175-review-board')"},
                "component": {"type": "string", "description": "Component affected (e.g. 'switchboard', 'coordinator', 'aq-chat')"},
                "severity": {"type": "string", "enum": ["P0", "P1", "P2"], "description": "Severity: P0=blocking, P1=degraded, P2=quality"},
                "finding": {"type": "string", "description": "Description of the finding"},
                "file_line": {"type": "string", "description": "File path and line number (e.g. 'switchboard.py:394')"},
                "agent_name": {"type": "string", "description": "Name of the agent posting the finding"},
            },
            "required": ["board_key", "component", "severity", "finding"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.SYSTEM_MODIFY,
        handler=post_review_finding_handler,
    ))

    # read_review_board
    registry.register(ToolDefinition(
        name="read_review_board",
        description=(
            "Read all findings posted to a collaborative review board. "
            "Call at the start of a review to see what other agents have already found. "
            "Prevents duplicate findings and enables cross-agent synthesis."
        ),
        parameters={
            "type": "object",
            "properties": {
                "board_key": {"type": "string", "description": "Review board identifier (e.g. 'phase175-review-board')"},
            },
            "required": ["board_key"],
        },
        category=ToolCategory.AI_COORD,
        safety_policy=SafetyPolicy.READ_ONLY,
        handler=read_review_board_handler,
    ))

    logger.info("Registered 22 AI coordination tools")
