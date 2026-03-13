from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPO_PATH_RE = re.compile(r"(?:^|[\s`'\"])(/?[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+\.(?:nix|py|sh|md|js|ts|json|ya?ml))(?:$|[\s`'\",.:;])")
_COMMAND_RE = re.compile(r"(?:^|\n)(?:[$#]\s*)?((?:sudo|python3|python|bash|sh|nix(?:os-rebuild)?|systemctl|journalctl|curl|rg|git|node|npm|pnpm|./)[^\n]{0,160})")
_REFUSAL_TOKENS = (
    "i can't",
    "i cannot",
    "i'm sorry",
    "i am sorry",
    "unable to help",
    "cannot comply",
    "can't comply",
    "not able to",
    "policy",
    "refuse",
)
_GENERIC_LOW_SIGNAL_TOKENS = (
    "here's a summary",
    "here is a summary",
    "let me know if you'd like",
    "i can help",
    "would you like me to",
)


def delegation_feedback_log_path() -> Path:
    data_dir = Path(
        os.path.expanduser(
            os.getenv("DATA_DIR", "~/.local/share/nixos-ai-stack/hybrid")
        )
    )
    return data_dir / "telemetry" / "delegation-feedback.jsonl"


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def extract_delegated_text(body: Any) -> str:
    if isinstance(body, str):
        return body.strip()
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if isinstance(choices, list):
        parts: List[str] = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    parts.append(content.strip())
                elif isinstance(content, list):
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("text") or "").strip()
                        if text:
                            parts.append(text)
            text = str(choice.get("text") or "").strip()
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or "").strip()
    return str(body.get("message") or "").strip()


def extract_tool_call_summary(body: Any) -> List[Dict[str, str]]:
    if not isinstance(body, dict):
        return []
    choices = body.get("choices")
    if not isinstance(choices, list):
        return []
    tool_calls: List[Dict[str, str]] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        calls = message.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            function = call.get("function")
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "").strip()
            arguments = str(function.get("arguments") or "").strip()
            if not name:
                continue
            tool_calls.append(
                {
                    "name": name,
                    "arguments": arguments[:400],
                }
            )
    return tool_calls[:5]


def extract_reasoning_excerpt(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if not isinstance(choices, list):
        return ""
    parts: List[str] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if isinstance(message, dict):
            reasoning = str(message.get("reasoning") or "").strip()
            if reasoning:
                parts.append(reasoning)
            details = message.get("reasoning_details")
            if isinstance(details, list):
                for item in details:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text") or "").strip()
                    if text:
                        parts.append(text)
        reasoning_top = str(choice.get("reasoning") or "").strip()
        if reasoning_top:
            parts.append(reasoning_top)
    joined = "\n".join(part for part in parts if part).strip()
    return joined[:800]


def extract_repo_path_summary(text: str) -> Dict[str, Any]:
    observed: List[str] = []
    existing: List[str] = []
    missing: List[str] = []
    seen = set()
    for match in _REPO_PATH_RE.finditer(text or ""):
        candidate = str(match.group(1) or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        observed.append(candidate)
        resolved = Path(candidate)
        if not resolved.is_absolute():
            resolved = (_REPO_ROOT / candidate).resolve()
        try:
            within_repo = resolved == _REPO_ROOT or _REPO_ROOT in resolved.parents
        except Exception:
            within_repo = False
        if not within_repo:
            continue
        if resolved.exists():
            existing.append(str(resolved.relative_to(_REPO_ROOT)))
        else:
            missing.append(str(resolved.relative_to(_REPO_ROOT)))
    return {
        "observed": observed[:8],
        "existing": existing[:5],
        "missing": missing[:5],
    }


def extract_command_snippets(text: str) -> List[str]:
    commands: List[str] = []
    seen = set()
    for match in _COMMAND_RE.finditer(text or ""):
        command = str(match.group(1) or "").strip().strip("`")
        if not command or command in seen:
            continue
        seen.add(command)
        commands.append(command)
    return commands[:5]


def delegation_prompt_contract_signals(task: str, messages: List[Dict[str, Any]]) -> Dict[str, bool]:
    combined = [task]
    for message in messages:
        if isinstance(message, dict):
            combined.append(str(message.get("content") or ""))
    text = "\n".join(combined).lower()
    expects_json = "json" in text and any(token in text for token in ("only", "exact", "valid", "strict", "object", "array"))
    expects_short_exact = any(token in text for token in ("exactly", "and nothing else", "only this", "single word"))
    return {
        "expects_json": expects_json,
        "expects_short_exact": expects_short_exact,
    }


def classify_delegated_response(
    *,
    task: str,
    messages: List[Dict[str, Any]],
    status_code: int,
    body: Any,
    profile: str,
    runtime_id: str,
    stage: str,
    fallback_applied: bool,
) -> Dict[str, Any]:
    text = extract_delegated_text(body)
    text_lower = text.lower()
    handoff_requested = "coordinator_handoff" in text_lower
    tool_calls = extract_tool_call_summary(body)
    reasoning_excerpt = extract_reasoning_excerpt(body)
    path_summary = extract_repo_path_summary(text)
    commands = extract_command_snippets(text)
    contract = delegation_prompt_contract_signals(task, messages)
    failure_classes: List[str] = []

    if status_code == 429:
        failure_classes.append("rate_limited")
    elif status_code in {401, 403}:
        failure_classes.append("provider_auth_or_policy")
    elif status_code >= 500:
        failure_classes.append("provider_http_error")
    elif status_code >= 400:
        failure_classes.append("provider_request_error")

    if any(token in text_lower for token in _REFUSAL_TOKENS):
        failure_classes.append("policy_refusal")
    if status_code < 400 and not text and tool_calls:
        failure_classes.append("tool_call_without_final_text")
    elif status_code < 400 and not text:
        failure_classes.append("empty_content")
    if contract["expects_json"] and text:
        try:
            json.loads(text)
        except json.JSONDecodeError:
            failure_classes.append("json_contract_failed")
    if path_summary["missing"] and not path_summary["existing"] and len(path_summary["missing"]) >= 2:
        failure_classes.append("invented_repo_paths")
    if status_code < 400 and text:
        stripped = " ".join(text_lower.split())
        if (
            len(stripped) < 140
            and any(token in stripped for token in _GENERIC_LOW_SIGNAL_TOKENS)
            and not commands
            and not path_summary["existing"]
        ):
            failure_classes.append("low_signal_generic")

    seen = set()
    ordered_failure_classes: List[str] = []
    for item in failure_classes:
        if item not in seen:
            seen.add(item)
            ordered_failure_classes.append(item)

    improvement_actions: List[str] = []
    if "rate_limited" in ordered_failure_classes:
        improvement_actions.append("reduce delegated max_tokens and prefer smaller bounded asks before retry")
    if "json_contract_failed" in ordered_failure_classes:
        improvement_actions.append("tighten prompt contract to require strict JSON-only output and validate before acceptance")
    if "invented_repo_paths" in ordered_failure_classes:
        improvement_actions.append("bind delegated prompts to repo-grounded existing paths and reject invented file references")
    if "empty_content" in ordered_failure_classes:
        improvement_actions.append("require non-empty deliverable fields and treat blank completions as prompt failure")
    if "tool_call_without_final_text" in ordered_failure_classes:
        improvement_actions.append("either require a final post-tool deliverable or explicitly accept tool-call-only completions for this lane")
    if "low_signal_generic" in ordered_failure_classes:
        improvement_actions.append("ask for terse evidence-first output with concrete files, commands, or validation")
    if "policy_refusal" in ordered_failure_classes:
        improvement_actions.append("narrow the delegated task scope and remove ambiguous or policy-triggering phrasing")
    if "provider_request_error" in ordered_failure_classes or "provider_http_error" in ordered_failure_classes:
        improvement_actions.append("capture provider-specific failure details and simplify the payload before retry")

    salvage = {
        "text_excerpt": text[:400],
        "reasoning_excerpt": reasoning_excerpt[:400],
        "existing_paths": path_summary["existing"],
        "missing_paths": path_summary["missing"],
        "commands": commands,
        "tool_calls": tool_calls,
        "has_useful_data": bool(text[:120] or reasoning_excerpt[:120] or path_summary["existing"] or commands or tool_calls),
    }
    return {
        "is_failure": bool(ordered_failure_classes),
        "primary_failure_class": ordered_failure_classes[0] if ordered_failure_classes else "",
        "failure_classes": ordered_failure_classes,
        "improvement_actions": improvement_actions[:4],
        "salvage": salvage,
        "response_preview": (text[:400] or reasoning_excerpt[:400]),
        "profile": profile,
        "runtime_id": runtime_id,
        "stage": stage,
        "http_status": int(status_code),
        "fallback_applied": bool(fallback_applied),
        "handoff_requested": handoff_requested,
    }


def build_recovered_artifact(task: str, classification: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(classification, dict):
        return {"available": False}
    salvage = classification.get("salvage") if isinstance(classification.get("salvage"), dict) else {}
    tool_calls = salvage.get("tool_calls") if isinstance(salvage.get("tool_calls"), list) else []
    reasoning_excerpt = str(salvage.get("reasoning_excerpt") or "").strip()
    text_excerpt = str(salvage.get("text_excerpt") or "").strip()
    failure_classes = {str(item or "").strip() for item in classification.get("failure_classes") or []}
    if "tool_call_without_final_text" in failure_classes and tool_calls:
        tool_names = [str(item.get("name") or "").strip() for item in tool_calls if isinstance(item, dict)]
        compact_names = ", ".join(name for name in tool_names if name) or "unknown tool"
        return {
            "available": True,
            "recovery_class": "tool_call_plan_only",
            "result": f"Recovered a tool-call plan for {compact_names}, but the remote lane did not emit a final artifact.",
            "evidence": {
                "tool_calls": tool_calls[:3],
                "task_excerpt": str(task or "").strip()[:200],
            },
            "risks": [
                "tool calls were proposed but not executed inside the coordinator",
                "provider returned no final assistant content",
            ],
            "rollback_or_next_step": "Tighten the tool-calling prompt contract or run an explicit post-tool finalization pass before acceptance.",
        }
    if "empty_content" in failure_classes and reasoning_excerpt:
        return {
            "available": True,
            "recovery_class": "reasoning_only_draft",
            "result": "Recovered provider reasoning notes, but the remote lane did not emit a final deliverable.",
            "evidence": {
                "reasoning_excerpt": reasoning_excerpt[:400],
                "task_excerpt": str(task or "").strip()[:200],
            },
            "risks": [
                "reasoning text is not a validated final answer",
                "provider returned null assistant content",
            ],
            "rollback_or_next_step": "Use the recovered reasoning as prompt-tuning input, not as an accepted deliverable.",
        }
    if text_excerpt:
        return {
            "available": True,
            "recovery_class": "partial_text_excerpt",
            "result": "Recovered a partial delegated output excerpt.",
            "evidence": {"text_excerpt": text_excerpt[:400]},
            "risks": ["partial excerpt may not satisfy the delegated contract"],
            "rollback_or_next_step": "Tighten the delegated contract before accepting similar outputs.",
        }
    return {"available": False}


def record_delegation_feedback(
    *,
    task: str,
    requested_profile: str,
    selected_profile: str,
    selected_runtime_id: str,
    classification: Dict[str, Any],
    final_profile: str,
    final_runtime_id: str,
    requesting_agent: str = "human",
    requester_role: str = "orchestrator",
) -> None:
    if not classification.get("is_failure"):
        return
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "task_excerpt": task[:280],
        "requested_profile": requested_profile,
        "selected_profile": selected_profile,
        "selected_runtime_id": selected_runtime_id,
        "final_profile": final_profile,
        "final_runtime_id": final_runtime_id,
        "requesting_agent": str(requesting_agent or "human").strip() or "human",
        "requester_role": str(requester_role or "orchestrator").strip() or "orchestrator",
        "failure_stage": classification.get("stage"),
        "http_status": classification.get("http_status"),
        "failure_class": classification.get("primary_failure_class"),
        "failure_classes": classification.get("failure_classes") or [],
        "fallback_applied": bool(classification.get("fallback_applied")),
        "handoff_requested": bool(classification.get("handoff_requested")),
        "response_preview": classification.get("response_preview", ""),
        "salvage": classification.get("salvage") if isinstance(classification.get("salvage"), dict) else {},
        "improvement_actions": classification.get("improvement_actions") or [],
    }
    append_jsonl(delegation_feedback_log_path(), payload)
