"""
Helpers for the ai-coordinator control and delegation surfaces.

This layer turns declarative switchboard/OpenRouter configuration into concrete
runtime lanes the harness can list, schedule, and invoke without requiring
callers to hand-roll x-ai-profile usage.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from config import Config


def _runtime_record(
    runtime_id: str,
    *,
    name: str,
    profile: str,
    runtime_class: str,
    tags: List[str],
    status: str,
    note: str = "",
    model_alias: str = "",
    now: int,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "runtime_id": runtime_id,
        "name": name,
        "profile": profile,
        "status": status,
        "runtime_class": runtime_class,
        "transport": "openai-chat",
        "endpoint_env_var": "SWITCHBOARD_URL",
        "tags": tags,
        "updated_at": now,
        "created_at": now,
        "source": "ai-coordinator-default",
    }
    if note:
        record["status_notes"] = [{"ts": now, "text": note}]
    if model_alias:
        record["model_alias"] = model_alias
    return record


def runtime_defaults(now: int | None = None) -> List[Dict[str, Any]]:
    now_ts = int(now if now is not None else time.time())
    remote_configured = bool(Config.SWITCHBOARD_REMOTE_URL)
    local_tool_calling_status = "degraded"

    remote_free_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_FREE else (
        "degraded" if remote_configured else "offline"
    )
    remote_coding_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_CODING else (
        "degraded" if remote_configured else "offline"
    )
    remote_reasoning_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_REASONING else (
        "degraded" if remote_configured else "offline"
    )
    remote_tool_calling_status = "ready" if remote_configured and Config.SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING else (
        "degraded" if remote_configured else "offline"
    )

    return [
        _runtime_record(
            "local-hybrid",
            name="Local Hybrid Coordinator",
            profile="default",
            runtime_class="local-agent",
            tags=["local", "hybrid", "harness", "repo", "default"],
            status="ready",
            note="Built-in local-first harness lane.",
            now=now_ts,
        ),
        _runtime_record(
            "local-tool-calling",
            name="Local Tool-Calling Prep Lane",
            profile="local-tool-calling",
            runtime_class="local-agent",
            tags=["local", "tool-calling", "future-ready", "prep", "llama.cpp"],
            status=local_tool_calling_status,
            note=(
                "Preparatory local lane for future local model tool-calling support. "
                "Current local backends may reject or ignore tool payloads."
            ),
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-free",
            name="OpenRouter Free Agent Lane",
            profile="remote-free",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "free", "tool-calling", "planner"],
            status=remote_free_status,
            note="Uses the free remote lane for bounded delegation and planning.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_FREE,
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-coding",
            name="OpenRouter Coding Agent Lane",
            profile="remote-coding",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "coding", "tool-calling", "implementation"],
            status=remote_coding_status,
            note="Uses the coding-optimized remote lane for implementation-heavy delegation.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_CODING,
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-reasoning",
            name="OpenRouter Reasoning Agent Lane",
            profile="remote-reasoning",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "reasoning", "tool-calling", "review"],
            status=remote_reasoning_status,
            note="Uses the higher-judgment remote lane for architecture and review tasks.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_REASONING,
            now=now_ts,
        ),
        _runtime_record(
            "openrouter-tool-calling",
            name="OpenRouter Tool-Calling Agent Lane",
            profile="remote-tool-calling",
            runtime_class="remote-agent",
            tags=["remote", "openrouter", "tool-calling", "tools", "execution"],
            status=remote_tool_calling_status,
            note="Uses the tool-calling oriented remote lane for bounded tool-use delegation.",
            model_alias=Config.SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING,
            now=now_ts,
        ),
    ]


def merge_runtime_defaults(registry: Dict[str, Any], now: int | None = None) -> Dict[str, Any]:
    merged = {"runtimes": dict((registry or {}).get("runtimes", {}) or {})}
    for record in runtime_defaults(now=now):
        runtime_id = record["runtime_id"]
        existing = merged["runtimes"].get(runtime_id)
        if not isinstance(existing, dict):
            merged["runtimes"][runtime_id] = record
            continue
        # Refresh declarative defaults when the stored record was generated by
        # this module, but leave user-registered/custom runtimes untouched.
        if str(existing.get("source", "")).strip() == "ai-coordinator-default":
            refreshed = dict(record)
            if existing.get("created_at"):
                refreshed["created_at"] = existing["created_at"]
            merged["runtimes"][runtime_id] = refreshed
    return merged


def runtime_registry_retention_seconds() -> int:
    raw = str(getattr(Config, "AI_COORDINATOR_RUNTIME_RETENTION_SECONDS", "") or "").strip()
    if raw:
        try:
            return max(300, int(raw))
        except (TypeError, ValueError):
            pass
    return 12 * 60 * 60


def is_transient_runtime_record(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict):
        return False
    if bool(record.get("persistent")):
        return False
    source = str(record.get("source", "") or "").strip().lower()
    if source in {"ai-coordinator-default", "user-managed", "declarative"}:
        return False
    tags = {str(tag or "").strip().lower() for tag in record.get("tags", []) if str(tag or "").strip()}
    name = str(record.get("name", "") or "").strip().lower()
    runtime_id = str(record.get("runtime_id", "") or "").strip().lower()
    runtime_class = str(record.get("runtime_class", "") or "").strip().lower()
    if source in {"runtime-register", "smoke", "test", "smoke-test"}:
        return True
    if "smoke" in tags or "test" in tags:
        return True
    if name == "smoke-runtime":
        return True
    if runtime_class == "sandboxed":
        return True
    if runtime_id.startswith("smoke-"):
        return True
    return False


def prune_runtime_registry(registry: Dict[str, Any], now: int | None = None) -> Dict[str, Any]:
    current = int(now if now is not None else time.time())
    retention = runtime_registry_retention_seconds()
    merged = merge_runtime_defaults(registry, now=current)
    runtimes = dict((merged.get("runtimes", {}) or {}))
    kept: Dict[str, Dict[str, Any]] = {}
    pruned_ids: List[str] = []
    for runtime_id, record in runtimes.items():
        if not isinstance(record, dict):
            continue
        if not is_transient_runtime_record(record):
            kept[runtime_id] = record
            continue
        updated_at = int(record.get("updated_at") or record.get("created_at") or 0)
        age_s = max(0, current - updated_at) if updated_at > 0 else retention + 1
        if age_s > retention:
            pruned_ids.append(runtime_id)
            continue
        kept[runtime_id] = record
    return {
        "runtimes": kept,
        "meta": {
            "retention_seconds": retention,
            "last_pruned_at": current,
            "pruned_runtime_ids": pruned_ids,
        },
    }


def infer_profile(task: str, requested_profile: str = "") -> str:
    profile = str(requested_profile or "").strip().lower()
    if profile in {"default", "local", "local-hybrid", "continue-local"}:
        return "default"
    if profile == "local-tool-calling":
        return "local-tool-calling"
    if profile in {"remote-free", "remote-coding", "remote-reasoning", "remote-tool-calling"}:
        return profile

    lowered = str(task or "").lower()
    if any(token in lowered for token in ("local tool call", "local tool-call", "local tool use", "local function call")):
        return "local-tool-calling"
    if any(token in lowered for token in ("tool call", "tool-call", "tool use", "function call", "call tools", "tool routing")):
        return "remote-tool-calling"
    if any(token in lowered for token in ("architecture", "review", "risk", "tradeoff", "policy", "reasoning")):
        return "remote-reasoning"
    if any(token in lowered for token in ("code", "patch", "implement", "refactor", "fix", "debug")):
        return "remote-coding"
    return "remote-free"


def default_runtime_id_for_profile(profile: str) -> str:
    mapping = {
        "default": "local-hybrid",
        "local": "local-hybrid",
        "local-hybrid": "local-hybrid",
        "continue-local": "local-hybrid",
        "local-tool-calling": "local-tool-calling",
        "remote-free": "openrouter-free",
        "remote-coding": "openrouter-coding",
        "remote-reasoning": "openrouter-reasoning",
        "remote-tool-calling": "openrouter-tool-calling",
    }
    return mapping.get(str(profile or "").strip().lower(), "openrouter-free")


def coerce_orchestration_context(incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = incoming if isinstance(incoming, dict) else {}
    requested_by = str(
        payload.get("requesting_agent")
        or payload.get("requested_by")
        or payload.get("agent")
        or payload.get("agent_type")
        or "human"
    ).strip() or "human"
    requester_role = str(payload.get("requester_role") or payload.get("role") or "orchestrator").strip().lower()
    if requester_role not in {"orchestrator", "sub-agent"}:
        requester_role = "orchestrator"
    return {
        "requesting_agent": requested_by,
        "requested_by": requested_by,
        "requester_role": requester_role,
        "top_level_orchestrator": requester_role == "orchestrator",
        "subagents_may_spawn_subagents": False,
        "delegate_via_coordinator_only": True,
        "coordinator_delegate_path": "/control/ai-coordinator/delegate",
    }


def _delegation_system_prompt(profile: str) -> str:
    role = {
        "remote-coding": "implementation sub-agent",
        "remote-reasoning": "architecture/review sub-agent",
        "remote-tool-calling": "tool-calling sub-agent",
        "remote-free": "bounded research/planning sub-agent",
        "local-tool-calling": "local tool-calling prep sub-agent",
        "default": "local delegated sub-agent",
    }.get(str(profile or "").strip().lower(), "delegated sub-agent")
    return (
        f"You are a {role} inside the NixOS-Dev-Quick-Deploy harness.\n"
        "You are not the orchestrator.\n"
        "Do not spawn, invoke, or route additional sub-agents.\n"
        "If more delegation is needed, return a coordinator_handoff note for the orchestrator to submit through /control/ai-coordinator/delegate.\n"
        "Execute only the assigned slice.\n"
        "Respond concisely.\n"
        "Do not invent files, commands, or validation you did not actually derive from the provided task/context.\n"
        "Return evidence-first output with concrete paths, commands, and risks when available.\n"
        "If the task cannot be completed from the provided inputs, say what is missing instead of improvising."
    )


def _normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out
    text = str(value or "").strip()
    return [text] if text else []


def _profile_completion_rules(profile: str) -> List[str]:
    normalized = str(profile or "").strip().lower()
    if normalized == "remote-coding":
        return [
            "- keep the result tied to existing repo paths and current runtime behavior",
            "- prefer a minimal patch sketch, validation note, and concrete risk over broad redesign",
            "- do not propose extra files or tests unless the task/context justifies them",
        ]
    if normalized == "remote-reasoning":
        return [
            "- return a recommended direction first, then the top risks and tradeoffs",
            "- keep architecture/review notes concrete and bounded to the stated task",
            "- do not drift into patch design unless the task explicitly asks for it",
        ]
    if normalized == "remote-free":
        return [
            "- keep synthesis short: main finding, evidence, and one next step",
            "- avoid generic background paragraphs or repeated task restatement",
            "- prefer directly reusable findings over speculation",
        ]
    if normalized == "local-tool-calling":
        return [
            "- prepare an OpenAI-compatible tool contract and explicit fallback path",
            "- assume the local backend may reject tools and state that fallback clearly",
            "- keep the contract bounded to approved harness capabilities",
        ]
    if normalized == "remote-tool-calling":
        return [
            "- return a final artifact even if the provider starts with tool-call planning",
            "- keep tool arguments strict and bounded to the stated task",
            "- do not claim any tool was executed unless execution evidence is present in the prompt",
        ]
    return [
        "- keep the artifact bounded to the assigned slice",
        "- prefer concise result and evidence over narrative explanation",
    ]


def _task_shape_completion_rules(task: str, profile: str) -> List[str]:
    lowered = str(task or "").strip().lower()
    normalized = str(profile or "").strip().lower()
    rules: List[str] = []
    if any(token in lowered for token in ("deploy", "rollback", "switch", "nixos-rebuild", "service restart", "systemd")):
        rules.extend(
            [
                "- include the exact live verification signal and one rollback path",
                "- prefer declarative activation guidance over ad hoc restart loops when both are viable",
            ]
        )
    if any(token in lowered for token in ("fix", "bug", "regression", "debug", "failure")) and normalized in {"remote-coding", "remote-free", "default"}:
        rules.extend(
            [
                "- state the most likely root cause before proposing the smallest reversible fix",
                "- include one concrete validation step that would prove the bugfix actually worked",
            ]
        )
    if any(token in lowered for token in ("review", "risk", "tradeoff", "acceptance", "patch review")):
        rules.extend(
            [
                "- lead with the recommended direction or top finding before secondary commentary",
                "- call out the main residual risk instead of returning only a neutral summary",
            ]
        )
    if any(token in lowered for token in ("research", "scrape", "summarize", "source", "dataset", "retrieval")):
        rules.extend(
            [
                "- keep findings tied to explicit sources or bounded source packs when provided",
                "- separate extracted evidence from summary claims so the orchestrator can review quickly",
            ]
        )
    seen = set()
    deduped: List[str] = []
    for item in rules:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _delegation_contract_block(task: str, profile: str, context: Dict[str, Any] | None) -> str:
    ctx = context if isinstance(context, dict) else {}
    repo_paths = _normalize_list(ctx.get("repo_paths"))
    constraints = _normalize_list(ctx.get("constraints"))
    evidence = _normalize_list(ctx.get("evidence_requirements"))
    anti_goals = _normalize_list(ctx.get("anti_goals"))
    artifact = str(ctx.get("expected_artifact") or "").strip()
    output_format = str(ctx.get("output_format") or "").strip()

    default_artifact = {
        "remote-coding": "small patch plan or implementation sketch tied to existing repo paths",
        "remote-reasoning": "design/review notes with concrete risks and recommended direction",
        "remote-tool-calling": "bounded tool-calling plan or tool-use-ready task output with strict arguments",
        "local-tool-calling": "local tool-calling-ready task contract with explicit fallback if the backend lacks tool support",
        "remote-free": "bounded synthesis with actionable findings",
        "default": "bounded task result with evidence",
    }.get(str(profile or "").strip().lower(), "bounded task result with evidence")
    if not artifact:
        artifact = default_artifact

    lines = [
        f"Task: {task.strip()}",
        f"Expected artifact: {artifact}",
        "Required output sections:",
        "- result",
        "- evidence",
        "- risks",
        "- rollback_or_next_step",
        "- coordinator_handoff (only if more delegation is required)",
        "Completion rules:",
    ]
    lines.extend(_profile_completion_rules(profile))
    lines.extend(_task_shape_completion_rules(task, profile))
    if output_format:
        lines.append(f"Output format constraint: {output_format}")
    if repo_paths:
        lines.append("Allowed repo paths:")
        lines.extend(f"- {item}" for item in repo_paths[:8])
    if constraints:
        lines.append("Constraints:")
        lines.extend(f"- {item}" for item in constraints[:8])
    else:
        lines.append("Constraints:")
        lines.append("- stay within the assigned slice")
        lines.append("- do not invent repo paths or validation")
    if evidence:
        lines.append("Evidence requirements:")
        lines.extend(f"- {item}" for item in evidence[:8])
    else:
        lines.append("Evidence requirements:")
        lines.append("- cite concrete files, commands, or runtime facts when available")
    if anti_goals:
        lines.append("Anti-goals:")
        lines.extend(f"- {item}" for item in anti_goals[:8])
    if str(profile or "").strip().lower() == "remote-tool-calling":
        lines.append("Tool-calling completion rules:")
        lines.append("- tool-call-only output is insufficient")
        lines.append("- if you propose tool calls, still return a final artifact from the information currently available")
        lines.append("- if no tool execution occurred, summarize the proposed tool actions and the exact next step")
    return "\n".join(lines)


def build_tool_call_finalization_messages(
    task: str,
    tool_calls: List[Dict[str, Any]] | None,
    profile: str = "remote-tool-calling",
) -> List[Dict[str, str]]:
    compact_calls: List[str] = []
    for item in tool_calls or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip() or "unknown_tool"
        arguments = str(item.get("arguments") or "").strip()
        if arguments:
            compact_calls.append(f"- {name}: {arguments}")
        else:
            compact_calls.append(f"- {name}")
    if not compact_calls:
        compact_calls.append("- no tool call details available")
    return [
        {
            "role": "system",
            "content": _delegation_system_prompt(profile)
            + "\nYou are performing a bounded finalization pass after a tool-call-only reply."
            + "\nDo not invent tool execution results."
            + "\nReturn the final artifact now using only the task and proposed tool-call plan.",
        },
        {
            "role": "user",
            "content": "\n".join(
                [
                    f"Original task: {str(task or '').strip()}",
                    "The prior delegated reply proposed tool calls but returned no final assistant text.",
                    "Proposed tool-call plan:",
                    *compact_calls[:6],
                    "Required output sections:",
                    "- result",
                    "- evidence",
                    "- risks",
                    "- rollback_or_next_step",
                    "Constraints:",
                    "- do not claim any tool actually ran",
                    "- summarize only the proposed actions and what should happen next",
                    "- keep the artifact concise and concrete",
                ]
            ),
        },
    ]


def build_reasoning_finalization_messages(
    task: str,
    reasoning_excerpt: str,
    profile: str = "remote-reasoning",
) -> List[Dict[str, str]]:
    excerpt = str(reasoning_excerpt or "").strip()[:800] or "no reasoning excerpt available"
    return [
        {
            "role": "system",
            "content": _delegation_system_prompt(profile)
            + "\nYou are performing a bounded finalization pass after a reasoning-only reply."
            + "\nTurn the reasoning draft into a concrete final artifact."
            + "\nDo not emit hidden chain-of-thought or restate internal planning.",
        },
        {
            "role": "user",
            "content": "\n".join(
                [
                    f"Original task: {str(task or '').strip()}",
                    "The prior delegated reply returned reasoning notes but no final assistant content.",
                    "Recovered reasoning draft:",
                    excerpt,
                    "Required output sections:",
                    "- result",
                    "- evidence",
                    "- risks",
                    "- rollback_or_next_step",
                    "Constraints:",
                    "- convert the reasoning into a direct final artifact",
                    "- keep only the top recommendation, evidence, and tradeoff",
                    "- do not mention hidden reasoning or internal draft process",
                ]
            ),
        },
    ]


def build_messages(
    task: str,
    system_prompt: str = "",
    context: Dict[str, Any] | None = None,
    profile: str = "remote-free",
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    sys_prompt = system_prompt.strip() if system_prompt.strip() else _delegation_system_prompt(profile)
    messages.append({"role": "system", "content": sys_prompt})
    body = _delegation_contract_block(str(task or ""), profile, context)
    extra_context = context.get("extra_context") if isinstance(context, dict) else None
    if extra_context:
        body += "\n\nAdditional context:\n" + str(extra_context).strip()
    messages.append({"role": "user", "content": body.strip()})
    return messages
