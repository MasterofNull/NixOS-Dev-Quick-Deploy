"""
OpenAI-compat and A2A HTTP handlers for the hybrid-coordinator server.

Extracted from http_server.py during Phase 11.4 decomposition. This module
owns the OpenAI-compatible proxy surface, A2A-style JSON-RPC task handling,
and .well-known descriptors while relying on injected workflow/session helpers.
"""

import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx
from aiohttp import web

logger = logging.getLogger("hybrid-coordinator")

_error_payload: Optional[Callable[[str, Exception], Dict[str, Any]]] = None
_workflow_tool_catalog: Optional[Callable[..., List[Dict[str, Any]]]] = None
_load_lesson_refs: Optional[Callable[..., Any]] = None
_workflow_sessions_lock: Optional[Any] = None
_load_workflow_sessions: Optional[Callable[[], Any]] = None
_save_workflow_sessions: Optional[Callable[[Dict[str, Any]], Any]] = None
_ensure_session_runtime_fields: Optional[Callable[[Dict[str, Any]], None]] = None
_load_and_validate_workflow_blueprints: Optional[Callable[[], Dict[str, Any]]] = None
_coerce_orchestration_context: Optional[Callable[[Any], Dict[str, Any]]] = None
_build_workflow_run_session: Optional[Callable[..., Dict[str, Any]]] = None
_ai_coordinator_route_openai_chat_payload: Optional[Callable[..., Dict[str, Any]]] = None
_ai_coordinator_extract_task_from_openai_messages: Optional[Callable[[Any], str]] = None
_ai_coordinator_route_by_complexity: Optional[Callable[..., Dict[str, Any]]] = None
_switchboard_url: str = ""
_service_version: str = "1.0.0"
_a2a_signing_key_path: Optional[Path] = None


class A2ARequestError(Exception):
    def __init__(self, code: int, message: str, *, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def init(
    *,
    error_payload_fn: Callable[[str, Exception], Dict[str, Any]],
    workflow_tool_catalog_fn: Callable[..., List[Dict[str, Any]]],
    load_lesson_refs_fn: Callable[..., Any],
    workflow_sessions_lock: Any,
    load_workflow_sessions_fn: Callable[[], Any],
    save_workflow_sessions_fn: Callable[[Dict[str, Any]], Any],
    ensure_session_runtime_fields_fn: Callable[[Dict[str, Any]], None],
    load_and_validate_workflow_blueprints_fn: Callable[[], Dict[str, Any]],
    coerce_orchestration_context_fn: Callable[[Any], Dict[str, Any]],
    build_workflow_run_session_fn: Callable[..., Dict[str, Any]],
    ai_coordinator_route_openai_chat_payload_fn: Callable[..., Dict[str, Any]],
    ai_coordinator_extract_task_from_openai_messages_fn: Callable[[Any], str],
    ai_coordinator_route_by_complexity_fn: Callable[..., Dict[str, Any]],
    switchboard_url: str,
    service_version: str,
) -> None:
    global _error_payload, _workflow_tool_catalog, _load_lesson_refs
    global _workflow_sessions_lock, _load_workflow_sessions, _save_workflow_sessions
    global _ensure_session_runtime_fields, _load_and_validate_workflow_blueprints
    global _coerce_orchestration_context, _build_workflow_run_session
    global _ai_coordinator_route_openai_chat_payload
    global _ai_coordinator_extract_task_from_openai_messages
    global _ai_coordinator_route_by_complexity, _switchboard_url, _service_version

    _error_payload = error_payload_fn
    _workflow_tool_catalog = workflow_tool_catalog_fn
    _load_lesson_refs = load_lesson_refs_fn
    _workflow_sessions_lock = workflow_sessions_lock
    _load_workflow_sessions = load_workflow_sessions_fn
    _save_workflow_sessions = save_workflow_sessions_fn
    _ensure_session_runtime_fields = ensure_session_runtime_fields_fn
    _load_and_validate_workflow_blueprints = load_and_validate_workflow_blueprints_fn
    _coerce_orchestration_context = coerce_orchestration_context_fn
    _build_workflow_run_session = build_workflow_run_session_fn
    _ai_coordinator_route_openai_chat_payload = ai_coordinator_route_openai_chat_payload_fn
    _ai_coordinator_extract_task_from_openai_messages = ai_coordinator_extract_task_from_openai_messages_fn
    _ai_coordinator_route_by_complexity = ai_coordinator_route_by_complexity_fn
    _switchboard_url = switchboard_url
    _service_version = service_version
    _ensure_a2a_signing_key()


async def _active_lesson_refs(limit: int = 2) -> List[Dict[str, Any]]:
    refs = await _load_lesson_refs(limit=limit)
    return refs if isinstance(refs, list) else []


def _internal_error(exc: Exception) -> web.Response:
    return web.json_response(_error_payload("internal_error", exc), status=500)


def _coordinator_requested_profile(request: web.Request, payload: Dict[str, Any] | None = None) -> str:
    profile = str(request.headers.get("X-AI-Profile") or "").strip().lower()
    if profile:
        return profile
    profile = str(request.rel_url.query.get("ai_profile") or "").strip().lower()
    if profile:
        return profile
    if isinstance(payload, dict):
        profile = str(payload.get("ai_profile") or payload.get("profile") or "").strip().lower()
        if profile:
            return profile
    return ""


def _coordinator_prefer_local(request: web.Request, payload: Dict[str, Any] | None = None) -> bool:
    raw = str(request.headers.get("X-AI-Prefer-Local") or "").strip().lower()
    if raw in {"0", "false", "no", "remote"}:
        return False
    if raw in {"1", "true", "yes", "local"}:
        return True
    raw = str(request.rel_url.query.get("prefer_local") or "").strip().lower()
    if raw in {"0", "false", "no", "remote"}:
        return False
    if raw in {"1", "true", "yes", "local"}:
        return True
    if isinstance(payload, dict) and "prefer_local" in payload:
        return bool(payload.get("prefer_local"))
    return True


async def _proxy_openai_request_via_coordinator(
    request: web.Request,
    payload: Dict[str, Any],
    *,
    path: str,
) -> web.Response:
    requested_profile = _coordinator_requested_profile(request, payload)
    prefer_local = _coordinator_prefer_local(request, payload)

    if path == "chat/completions":
        routing = _ai_coordinator_route_openai_chat_payload(
            payload,
            requested_profile=requested_profile,
            prefer_local=prefer_local,
        )
    else:
        task = str(payload.get("prompt") or "").strip() or _ai_coordinator_extract_task_from_openai_messages(payload.get("messages"))
        routing = _ai_coordinator_route_by_complexity(
            task or "continue completion request",
            requested_profile=requested_profile,
            prefer_local=prefer_local,
        )
        routing["task"] = task

    selected_profile = str(routing.get("recommended_profile") or "default").strip() or "default"
    outbound_headers = {
        "Content-Type": "application/json",
        "X-AI-Profile": "continue-local" if selected_profile == "default" else selected_profile,
        "X-AI-Route": "local" if selected_profile in {"default", "local-tool-calling"} else "remote",
    }
    if "Authorization" in request.headers:
        outbound_headers["Authorization"] = request.headers["Authorization"]

    timeout_s = float(payload.get("timeout_s") or 120.0)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        upstream = await client.post(
            f"{_switchboard_url.rstrip('/')}/v1/{path}",
            headers=outbound_headers,
            json=payload,
        )

    content_type = upstream.headers.get("content-type", "application/json")
    response = web.Response(
        status=upstream.status_code,
        body=upstream.content,
        content_type=content_type.split(";", 1)[0] if content_type else None,
    )
    response.headers["X-AI-Profile"] = selected_profile
    response.headers["X-Coordinator-Task-Archetype"] = str(routing.get("task_archetype") or "")
    response.headers["X-Coordinator-Model-Class"] = str(routing.get("model_class") or "")
    response.headers["X-Coordinator-Complexity"] = str(routing.get("complexity") or "")
    return response


def _isoformat_epoch(value: Any) -> str:
    try:
        ts = float(value or 0)
    except (TypeError, ValueError):
        ts = 0.0
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _a2a_text_parts(text: str) -> List[Dict[str, Any]]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    return [{"type": "text", "text": normalized}]


def _a2a_role(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_")
    if text in {"ROLE_USER", "USER"}:
        return "ROLE_USER"
    if text in {"ROLE_AGENT", "AGENT", "ASSISTANT"}:
        return "ROLE_AGENT"
    return "ROLE_AGENT"


def _a2a_message_payload(role: str, text: str, *, message_id: str = "", task_id: str = "") -> Dict[str, Any]:
    message: Dict[str, Any] = {
        "role": _a2a_role(role),
        "parts": _a2a_text_parts(text),
    }
    if message_id:
        message["messageId"] = message_id
    if task_id:
        message["taskId"] = task_id
    return message


def _extract_a2a_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    direct = str(message.get("text", "") or "").strip()
    if direct:
        return direct
    parts = message.get("parts")
    if not isinstance(parts, list):
        return ""
    texts: List[str] = []
    for item in parts:
        if not isinstance(item, dict):
            continue
        part_type = str(item.get("type", "")).strip().lower()
        text = str(item.get("text", "") or "").strip()
        if not text and not part_type and isinstance(item.get("data"), dict):
            text = json.dumps(item.get("data"), sort_keys=True)
        if not text and not part_type and item.get("url"):
            text = str(item.get("url", "")).strip()
        if text:
            texts.append(text)
    return "\n".join(texts).strip()


def _a2a_latest_detail(session: Dict[str, Any]) -> str:
    trajectory = session.get("trajectory", []) if isinstance(session, dict) else []
    if not isinstance(trajectory, list):
        return ""
    for event in reversed(trajectory):
        if not isinstance(event, dict):
            continue
        detail = str(event.get("detail", "") or "").strip()
        if detail:
            return detail
    return ""


def _a2a_task_state(session: Dict[str, Any]) -> str:
    status = str(session.get("status", "") or "").strip().lower()
    if status == "completed":
        return "TASK_STATE_COMPLETED"
    if status in {"error", "failed"}:
        return "TASK_STATE_FAILED"
    if status == "canceled":
        return "TASK_STATE_CANCELED"
    if status in {"pending", "queued"}:
        return "TASK_STATE_SUBMITTED"
    return "TASK_STATE_WORKING"


def _normalize_a2a_method(value: Any) -> str:
    text = str(value or "").strip()
    method_aliases = {
        "SendMessage": "message/send",
        "tasks/send": "message/send",
        "GetTask": "tasks/get",
        "ListTasks": "tasks/list",
        "CancelTask": "tasks/cancel",
        "SubscribeToTask": "tasks/resubscribe",
        "GetExtendedAgentCard": "agent/getAuthenticatedExtendedCard",
    }
    return method_aliases.get(text, text)


def _coerce_a2a_request_id(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float)):
        return value
    return None


def _normalize_a2a_status_filter(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_")
    if not text:
        return ""
    if text.startswith("TASK_STATE_"):
        return text
    mapping = {
        "SUBMITTED": "TASK_STATE_SUBMITTED",
        "WORKING": "TASK_STATE_WORKING",
        "INPUT_REQUIRED": "TASK_STATE_INPUT_REQUIRED",
        "COMPLETED": "TASK_STATE_COMPLETED",
        "CANCELED": "TASK_STATE_CANCELED",
        "FAILED": "TASK_STATE_FAILED",
    }
    return mapping.get(text, "")


def _session_to_a2a_artifacts(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    session_id = str(session.get("session_id", "") or "").strip()
    objective = str(session.get("objective", "") or "").strip()
    latest_detail = _a2a_latest_detail(session)
    artifacts: List[Dict[str, Any]] = []

    summary_lines = [line for line in [objective, latest_detail] if line]
    if summary_lines:
        artifacts.append(
            {
                "artifactId": f"{session_id}:summary",
                "name": "Workflow Summary",
                "description": "Current workflow objective and latest recorded detail.",
                "parts": _a2a_text_parts("\n\n".join(summary_lines)),
                "metadata": {
                    "workflow_session_id": session_id,
                    "artifact_kind": "summary",
                },
            }
        )

    gate = session.get("reviewer_gate", {})
    if isinstance(gate, dict):
        last_review = gate.get("last_review", {})
        if isinstance(last_review, dict) and last_review:
            review_text = (
                f"Reviewer gate status: {str(gate.get('status', 'pending_review') or 'pending_review').strip()}\n"
                f"Reviewer: {str(last_review.get('reviewer', 'unknown') or 'unknown').strip()}\n"
                f"Review type: {str(last_review.get('review_type', 'acceptance') or 'acceptance').strip()}\n"
                f"Artifact kind: {str(last_review.get('artifact_kind', 'response') or 'response').strip()}\n"
                f"Score: {last_review.get('score', 0)}"
            )
            artifacts.append(
                {
                    "artifactId": f"{session_id}:reviewer-gate",
                    "name": "Reviewer Gate",
                    "description": "Latest reviewer-gate decision for this workflow task.",
                    "parts": _a2a_text_parts(review_text),
                    "metadata": {
                        "workflow_session_id": session_id,
                        "artifact_kind": "reviewer_gate",
                        "review_status": str(gate.get("status", "") or "").strip(),
                    },
                }
            )

    consensus = session.get("consensus", {})
    if isinstance(consensus, dict) and consensus:
        candidate_count = len(consensus.get("candidates", []) or [])
        arbiter = consensus.get("arbiter") if isinstance(consensus.get("arbiter"), dict) else {}
        consensus_text = (
            f"Consensus status: {str(consensus.get('status', 'pending') or 'pending').strip()}\n"
            f"Consensus mode: {str(consensus.get('consensus_mode', 'reviewer-gate') or 'reviewer-gate').strip()}\n"
            f"Selection strategy: {str(consensus.get('selection_strategy', 'orchestrator-first') or 'orchestrator-first').strip()}\n"
            f"Selected candidate: {str(consensus.get('selected_candidate_id', '') or 'none').strip()}\n"
            f"Selected lane: {str(consensus.get('selected_lane', '') or 'unknown').strip()}\n"
            f"Candidate count: {candidate_count}\n"
            f"Arbiter status: {str(arbiter.get('status', 'not-required') or 'not-required').strip()}"
        )
        artifacts.append(
            {
                "artifactId": f"{session_id}:consensus",
                "name": "Consensus Snapshot",
                "description": "Current candidate evaluation and consensus state for this workflow task.",
                "parts": _a2a_text_parts(consensus_text),
                "metadata": {
                    "workflow_session_id": session_id,
                    "artifact_kind": "consensus",
                    "consensus_status": str(consensus.get("status", "") or "").strip(),
                    "selected_candidate_id": str(consensus.get("selected_candidate_id", "") or "").strip(),
                },
            }
        )
        last_arbiter = arbiter.get("last_decision") if isinstance(arbiter.get("last_decision"), dict) else {}
        if last_arbiter:
            arbiter_text = (
                f"Arbiter: {str(last_arbiter.get('arbiter', 'unknown') or 'unknown').strip()}\n"
                f"Verdict: {str(last_arbiter.get('verdict', 'unknown') or 'unknown').strip()}\n"
                f"Selected candidate: {str(last_arbiter.get('selected_candidate_id', 'none') or 'none').strip()}\n"
                f"Selected lane: {str(last_arbiter.get('selected_lane', 'unknown') or 'unknown').strip()}\n"
                f"Rationale: {str(last_arbiter.get('rationale', '') or '').strip()}"
            )
            artifacts.append(
                {
                    "artifactId": f"{session_id}:arbiter",
                    "name": "Arbiter Decision",
                    "description": "Latest arbiter decision for this workflow task.",
                    "parts": _a2a_text_parts(arbiter_text),
                    "metadata": {
                        "workflow_session_id": session_id,
                        "artifact_kind": "arbiter",
                        "arbiter_status": str(arbiter.get("status", "") or "").strip(),
                        "selected_candidate_id": str(last_arbiter.get("selected_candidate_id", "") or "").strip(),
                    },
                }
            )

    team = session.get("team", {})
    if isinstance(team, dict) and (team.get("members") or []):
        team_lines = [
            f"Formation mode: {str(team.get('formation_mode', 'dynamic-role-assignment') or 'dynamic-role-assignment').strip()}",
            f"Selection strategy: {str(team.get('selection_strategy', 'orchestrator-first') or 'orchestrator-first').strip()}",
            f"Active slots: {', '.join(str(slot or '').strip() for slot in (team.get('active_slots') or []) if str(slot or '').strip()) or 'none'}",
        ]
        for member in team.get("members") or []:
            if not isinstance(member, dict):
                continue
            team_lines.append(
                f"{str(member.get('slot', 'member') or 'member').strip()}: "
                f"{str(member.get('agent', 'unknown') or 'unknown').strip()} "
                f"[{str(member.get('lane', 'unknown') or 'unknown').strip()}]"
            )
        artifacts.append(
            {
                "artifactId": f"{session_id}:team",
                "name": "Orchestration Team",
                "description": "Current dynamically formed role assignment for this workflow task.",
                "parts": _a2a_text_parts("\n".join(team_lines)),
                "metadata": {
                    "workflow_session_id": session_id,
                    "artifact_kind": "team",
                    "formation_mode": str(team.get("formation_mode", "") or "").strip(),
                },
            }
        )

    return artifacts


def _session_history_to_a2a_messages(session: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    session_id = str(session.get("session_id", "") or "").strip()
    trajectory = session.get("trajectory", [])
    if not isinstance(trajectory, list):
        return []
    messages: List[Dict[str, Any]] = []
    start = max(0, len(trajectory) - max(1, limit))
    for idx, event in enumerate(trajectory[start:], start=start):
        if not isinstance(event, dict):
            continue
        detail = str(event.get("detail", "") or "").strip()
        if not detail:
            continue
        messages.append(
            _a2a_message_payload(
                "agent",
                detail,
                message_id=f"{session_id}:history:{idx}",
                task_id=session_id,
            )
        )
    return messages


def _history_subset(session: Dict[str, Any], history_length: Optional[int]) -> List[Dict[str, Any]]:
    trajectory = session.get("trajectory", []) if isinstance(session, dict) else []
    if not isinstance(trajectory, list):
        return []
    if history_length is None:
        return trajectory
    return trajectory[: max(0, min(len(trajectory), int(history_length)))]


def _session_to_a2a_status_event(
    session: Dict[str, Any],
    base_url: str,
    *,
    detail: str = "",
    timestamp: Any = None,
    final: Optional[bool] = None,
) -> Dict[str, Any]:
    task = _session_to_a2a_task(session, base_url)
    session_id = str(task.get("id", "") or "").strip()
    state = str(task.get("status", {}).get("state", "working") or "working").strip() or "working"
    status_timestamp = _isoformat_epoch(timestamp if timestamp is not None else session.get("updated_at") or session.get("created_at"))
    message_text = str(detail or _a2a_latest_detail(session) or f"Task is {state}.").strip()
    if final is None:
        final = state in {"completed", "failed", "canceled"}
    return {
        "kind": "status-update",
        "taskId": session_id,
        "contextId": session_id,
        "status": {
            "state": state,
            "timestamp": status_timestamp,
            "message": _a2a_message_payload(
                "ROLE_AGENT",
                message_text,
                message_id=f"{session_id}:status:{state}",
                task_id=session_id,
            ),
        },
        "final": bool(final),
        "metadata": task.get("metadata", {}),
    }


def _artifact_to_a2a_update(task: Dict[str, Any], artifact: Dict[str, Any], *, last_chunk: bool = True) -> Dict[str, Any]:
    session_id = str(task.get("id", "") or "").strip()
    return {
        "kind": "artifact-update",
        "taskId": session_id,
        "contextId": session_id,
        "artifact": artifact,
        "lastChunk": bool(last_chunk),
    }


def _session_to_a2a_task(
    session: Dict[str, Any],
    base_url: str,
    *,
    history_length: Optional[int] = None,
    include_artifacts: bool = True,
) -> Dict[str, Any]:
    session_id = str(session.get("session_id", "") or "").strip()
    objective = str(session.get("objective", "") or "").strip()
    state = _a2a_task_state(session)
    updated_at = session.get("updated_at") or session.get("created_at")
    latest_detail = _a2a_latest_detail(session)
    artifacts = _session_to_a2a_artifacts(session) if include_artifacts else []
    history_items = _history_subset(session, history_length)
    task: Dict[str, Any] = {
        "id": session_id,
        "kind": "task",
        "contextId": str(session.get("context_id", "") or session_id).strip() or session_id,
        "status": {
            "state": state,
            "timestamp": _isoformat_epoch(updated_at),
            "message": _a2a_message_payload(
                "agent",
                latest_detail or objective or f"Task is {state}.",
                message_id=f"{session_id}:status",
                task_id=session_id,
            ),
        },
        "metadata": {
            "objective": objective,
            "safety_mode": str(session.get("safety_mode", "") or "").strip(),
            "phase_count": len(session.get("phase_state", []) or []),
            "current_phase_index": int(session.get("current_phase_index", 0) or 0),
            "reviewer_gate": session.get("reviewer_gate", {}),
            "a2a_stream_url": f"{base_url.rstrip('/')}/a2a/tasks/{session_id}/events",
            "workflow_run_url": f"{base_url.rstrip('/')}/workflow/run/{session_id}",
        },
        "historyLength": len(history_items),
    }
    if objective:
        task["message"] = _a2a_message_payload(
            "ROLE_AGENT",
            objective,
            message_id=f"{session_id}:summary",
            task_id=session_id,
        )
    history = _session_history_to_a2a_messages({"session_id": session_id, "trajectory": history_items}, limit=max(1, len(history_items)))
    if history_length is not None:
        task["history"] = history
    elif history:
        task["history"] = history
    if artifacts:
        task["artifacts"] = artifacts
    return task


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _canonical_agent_card_payload(card: Dict[str, Any]) -> bytes:
    unsigned = {k: v for k, v in card.items() if k != "proof"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _a2a_default_signing_key_path() -> Path:
    configured = os.getenv("A2A_SIGNING_KEY_PATH", "").strip()
    if configured:
        return Path(configured)
    run_secret = Path("/run/secrets/a2a_signing_key")
    if run_secret.exists() or os.access(str(run_secret.parent), os.W_OK):
        return run_secret
    return Path("/var/lib/ai-stack/hybrid/a2a_signing.key")


def _run_signing_command(args: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    if not any(key in kwargs for key in ("stdout", "stderr", "capture_output")):
        kwargs["capture_output"] = True
    return subprocess.run(args, check=True, **kwargs)


def _generate_openssl_ed25519_key(path: Path) -> bool:
    if not shutil.which("openssl"):
        return False
    _run_signing_command(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(path)])
    return True


def _generate_pynacl_ed25519_key(path: Path) -> bool:
    try:
        from nacl.signing import SigningKey
    except Exception:
        return False
    signing_key = SigningKey.generate()
    path.write_bytes(signing_key.encode())
    return True


def _generate_cryptography_ed25519_key(path: Path) -> bool:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except Exception:
        return False
    private_key = Ed25519PrivateKey.generate()
    path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return True


def _generate_ssh_ed25519_key(path: Path) -> bool:
    if not shutil.which("ssh-keygen"):
        return False
    _run_signing_command(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)])
    return True


def _ensure_a2a_signing_key() -> Optional[Path]:
    global _a2a_signing_key_path
    path = _a2a_default_signing_key_path()
    if path.exists():
        _a2a_signing_key_path = path
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not (
            _generate_pynacl_ed25519_key(path)
            or _generate_cryptography_ed25519_key(path)
            or _generate_openssl_ed25519_key(path)
            or _generate_ssh_ed25519_key(path)
        ):
            logger.warning("A2A signing key unavailable: install PyNaCl, cryptography, openssl, or ssh-keygen")
            return None
        path.chmod(0o600)
        _a2a_signing_key_path = path
        logger.info("A2A signing key initialized at %s", path)
        return path
    except Exception as exc:
        logger.warning("A2A signing key initialization failed at %s: %s", path, exc)
        return None


def _openssl_public_key_b64url(path: Path) -> str:
    proc = _run_signing_command(
        ["openssl", "pkey", "-in", str(path), "-pubout", "-outform", "DER"]
    )
    der = proc.stdout
    raw = der[-32:] if len(der) >= 32 else der
    return _b64url(raw)


def _pynacl_public_key_b64url(path: Path) -> Optional[str]:
    try:
        from nacl.signing import SigningKey
    except Exception:
        return None
    seed = path.read_bytes()
    if len(seed) != 32:
        return None
    return _b64url(SigningKey(seed).verify_key.encode())


def _cryptography_public_key_b64url(path: Path) -> Optional[str]:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except Exception:
        return None
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except Exception:
        return None
    if not isinstance(key, Ed25519PrivateKey):
        return None
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64url(public_key)


def _ssh_public_key_b64url(path: Path) -> str:
    pub_path = path.with_name(path.name + ".pub")
    if not pub_path.exists():
        with pub_path.open("wb") as fh:
            _run_signing_command(["ssh-keygen", "-y", "-f", str(path)], stdout=fh)
    return _b64url(pub_path.read_bytes())


def _sign_with_pynacl(path: Path, payload: bytes) -> Optional[bytes]:
    try:
        from nacl.signing import SigningKey
    except Exception:
        return None
    try:
        seed = path.read_bytes()
        if len(seed) != 32:
            return None
        return SigningKey(seed).sign(payload).signature
    except Exception as exc:
        logger.debug("A2A PyNaCl signing unavailable for %s: %s", path, exc)
        return None


def _sign_with_cryptography(path: Path, payload: bytes) -> Optional[bytes]:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except Exception:
        return None
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            return None
        return key.sign(payload)
    except Exception as exc:
        logger.debug("A2A cryptography signing unavailable for %s: %s", path, exc)
        return None


def _sign_with_openssl(path: Path, payload: bytes) -> Optional[bytes]:
    if not shutil.which("openssl"):
        return None
    try:
        proc = _run_signing_command(
            ["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(path)],
            input=payload,
        )
        return proc.stdout
    except Exception as exc:
        logger.debug("A2A openssl signing unavailable for %s: %s", path, exc)
        return None


def _sign_with_ssh_keygen(path: Path, payload: bytes) -> Optional[bytes]:
    if not shutil.which("ssh-keygen"):
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="a2a-sign-") as tmpdir:
            payload_path = Path(tmpdir) / "agent-card.canon"
            payload_path.write_bytes(payload)
            _run_signing_command(
                ["ssh-keygen", "-Y", "sign", "-q", "-n", "a2a-agent-card", "-f", str(path), str(payload_path)]
            )
            sig_path = payload_path.with_name(payload_path.name + ".sig")
            return sig_path.read_bytes()
    except Exception as exc:
        logger.debug("A2A ssh-keygen signing unavailable for %s: %s", path, exc)
        return None


def _a2a_verification_method(path: Path) -> str:
    try:
        public_key = _pynacl_public_key_b64url(path) or _cryptography_public_key_b64url(path)
        if public_key:
            return f"did:web:hybrid-coordinator#ed25519-{public_key}"
        if path.with_name(path.name + ".pub").exists() or str(path.read_text(errors="ignore")).startswith("-----BEGIN OPENSSH"):
            return f"did:web:hybrid-coordinator#ssh-ed25519-{_ssh_public_key_b64url(path)}"
        if shutil.which("openssl"):
            return f"did:web:hybrid-coordinator#ed25519-{_openssl_public_key_b64url(path)}"
    except Exception as exc:
        logger.debug("A2A verification method derivation failed for %s: %s", path, exc)
    return "did:web:hybrid-coordinator#ed25519"


def _add_a2a_agent_card_proof(card: Dict[str, Any]) -> Dict[str, Any]:
    key_path = _ensure_a2a_signing_key()
    if not key_path:
        return card
    payload = _canonical_agent_card_payload(card)
    signature = (
        _sign_with_pynacl(key_path, payload)
        or _sign_with_cryptography(key_path, payload)
        or _sign_with_openssl(key_path, payload)
        or _sign_with_ssh_keygen(key_path, payload)
    )
    if not signature:
        logger.warning("A2A agent card proof omitted: no Ed25519 signing backend succeeded")
        return card
    signed = dict(card)
    signed["proof"] = {
        "type": "Ed25519Signature2020",
        "verificationMethod": _a2a_verification_method(key_path),
        "signature": _b64url(signature),
    }
    return signed


def _build_a2a_agent_card(base_url: str) -> Dict[str, Any]:
    parsed = urlsplit(base_url.rstrip("/"))
    hostname = parsed.hostname or ""
    if hostname in {"127.0.0.1", "::1"}:
        host = "localhost"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        origin = urlunsplit((parsed.scheme or "http", host, "", "", "")).rstrip("/")
    else:
        origin = base_url.rstrip("/")
    card = {
        "protocolVersion": "0.3.0",
        "name": "NixOS Dev Quick Deploy Hybrid Coordinator",
        "description": (
            "A2A compatibility surface for the hybrid coordinator. "
            "It exposes guarded workflow planning and task execution over JSON-RPC."
        ),
        "endpoint": f"{origin}/",
        "preferredTransport": "JSONRPC",
        "version": _service_version,
        "provider": {
            "organization": "NixOS-Dev-Quick-Deploy",
        },
        "documentationUrl": f"{origin}/.well-known/agent-card.json",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "supportedInterfaces": [
            {
                "transport": "JSONRPC",
                "url": f"{origin}/",
                "features": {
                    "streaming": True,
                    "pushNotifications": False,
                },
            }
        ],
        "skills": [
            {
                "id": "workflow-orchestration",
                "name": "Workflow Orchestration",
                "description": "Starts guarded workflow runs with intent contracts and replayable trajectory history.",
                "tags": ["workflow", "orchestration", "guardrails"],
                "examples": ["Resume the previous deployment integration slice and report evidence."],
            },
            {
                "id": "runtime-review-gate",
                "name": "Reviewer Gate",
                "description": "Tracks reviewer-gate state and safety-mode transitions for coding-agent tasks.",
                "tags": ["review", "safety", "runtime"],
                "examples": ["Create a bounded fix plan and do not exit until the review gate is satisfied."],
            },
        ],
        "endpoints": {
            "rpc": f"{origin}/",
            "taskEvents": f"{origin}/a2a/tasks/{{taskId}}/events",
            "taskSend": f"{origin}/a2a/tasks/send",
        },
    }
    return _add_a2a_agent_card_proof(card)


def _jsonrpc_success(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if isinstance(data, dict) and data:
        payload["error"]["data"] = data
    return payload


async def handle_well_known_mcp(_request: web.Request) -> web.Response:
    try:
        tool_list = _workflow_tool_catalog("")
        tool_count = len(tool_list) if isinstance(tool_list, list) else 0
        tool_summary = [
            {"name": t.get("name", ""), "description": (t.get("description", "") or "")[:100]}
            for t in (tool_list if isinstance(tool_list, list) else [])[:10]
        ]
    except Exception:
        tool_count = 0
        tool_summary = []

    payload = {
        "mcp_version": "2026.1",
        "server": {
            "name": "hybrid-coordinator",
            "version": "1.1.0",
            "description": "AI workflow orchestration and RAG coordination server",
        },
        "capabilities": {
            "augment_query": True,
            "route_search": True,
            "tree_search": True,
            "memory_store": True,
            "memory_recall": True,
            "hints": True,
            "workflow_orchestration": True,
            "multi_turn_context": True,
            "web_research": True,
            "browser_research": True,
            "delegation": True,
            "autoresearch": True,
        },
        "protocols": {
            "http": True,
            "mcp_stdio": True,
            "jsonrpc": True,
        },
        "tools": {
            "count": tool_count,
            "summary": tool_summary,
        },
        "endpoints": {
            "health": "/health",
            "health_detailed": "/health/detailed",
            "status": "/status",
            "hints": "/hints",
            "workflow_plan": "/workflow/plan",
            "delegate": "/control/ai-coordinator/delegate",
        },
        "rate_limiting": {
            "enabled": True,
            "default_rpm": 60,
        },
        "links": {
            "documentation": "https://github.com/yourusername/NixOS-Dev-Quick-Deploy",
            "health": "/health",
        },
    }
    return web.json_response(payload)


async def handle_well_known_a2a(request: web.Request) -> web.Response:
    base_url = f"{request.scheme}://{request.host}"
    return web.json_response(_build_a2a_agent_card(base_url))


async def handle_a2a_task_events(request: web.Request) -> web.StreamResponse:
    session_id = request.match_info.get("session_id", "")
    try:
        since = max(0, int(request.rel_url.query.get("since", "0") or 0))
    except ValueError:
        since = 0
    async with _workflow_sessions_lock:
        sessions = await _load_workflow_sessions()
        session = sessions.get(session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)
    _ensure_session_runtime_fields(session)
    base_url = f"{request.scheme}://{request.host}"
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await response.prepare(request)
    snapshot = _session_to_a2a_task(session, base_url)
    await response.write(f"event: task\ndata: {json.dumps(snapshot, separators=(',', ':'))}\n\n".encode("utf-8"))
    await response.write(
        (
            f"event: status-update\ndata: "
            f"{json.dumps(_session_to_a2a_status_event(session, base_url, final=False), separators=(',', ':'))}\n\n"
        ).encode("utf-8")
    )
    for artifact in snapshot.get("artifacts", []) or []:
        if not isinstance(artifact, dict):
            continue
        await response.write(
            (
                f"event: artifact-update\ndata: "
                f"{json.dumps(_artifact_to_a2a_update(snapshot, artifact), separators=(',', ':'))}\n\n"
            ).encode("utf-8")
        )
    trajectory = list(session.get("trajectory", []) or [])
    for idx, event in enumerate(trajectory[since:], start=since):
        payload = _session_to_a2a_status_event(
            session,
            base_url,
            detail=str(event.get("detail", "") or str(event.get("event_type", "") or "workflow event")).strip(),
            timestamp=event.get("ts"),
            final=False,
        )
        payload["metadata"] = {
            **(payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}),
            "index": idx,
            "eventType": str(event.get("event_type", "")).strip(),
            "phaseId": str(event.get("phase_id", "")).strip(),
            "riskClass": str(event.get("risk_class", "")).strip(),
        }
        await response.write(
            f"event: status-update\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n".encode("utf-8")
        )
    await response.write(
        (
            f"event: status-update\ndata: "
            f"{json.dumps(_session_to_a2a_status_event(session, base_url), separators=(',', ':'))}\n\n"
        ).encode("utf-8")
    )
    await response.write_eof()
    return response


async def _send_a2a_message(params: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    message = params.get("message")
    text = _extract_a2a_text(message)
    if not text:
        text = str(params.get("text", "") or "").strip()
    if not text:
        raise A2ARequestError(-32602, "message text required")

    task_id = str(
        params.get("taskId")
        or params.get("id")
        or (message.get("taskId") if isinstance(message, dict) else "")
        or ""
    ).strip()
    context_id = str(
        params.get("contextId")
        or (message.get("contextId") if isinstance(message, dict) else "")
        or ""
    ).strip()
    lesson_refs = await _active_lesson_refs(limit=2)
    if task_id:
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            session = sessions.get(task_id)
            if not session:
                raise A2ARequestError(-32001, "task not found", http_status=404)
            _ensure_session_runtime_fields(session)
            now = time.time()
            session["updated_at"] = now
            session["status"] = "working"
            session["trajectory"].append(
                {
                    "ts": now,
                    "event_type": "message_send",
                    "phase_id": f"phase-{int(session.get('current_phase_index', 0) or 0)}",
                    "detail": text,
                    "risk_class": "safe",
                }
            )
            if context_id:
                session["context_id"] = context_id
            sessions[task_id] = session
            await _save_workflow_sessions(sessions)
    else:
        blueprints_data = _load_and_validate_workflow_blueprints()
        blueprint_id = str(params.get("blueprint_id", "") or "").strip()
        selected_blueprint = (
            blueprints_data.get("blueprint_by_id", {}).get(blueprint_id)
            if blueprint_id
            else None
        )
        start_data = {
            "query": text,
            "prompt": text,
            "blueprint_id": blueprint_id,
            "safety_mode": str(params.get("safetyMode") or params.get("safety_mode") or "plan-readonly"),
            "token_limit": params.get("tokenLimit"),
            "tool_call_limit": params.get("toolCallLimit"),
            "intent_contract": params.get("intent_contract"),
            "isolation_profile": params.get("isolationProfile"),
            "workspace_root": params.get("workspaceRoot"),
            "network_policy": params.get("networkPolicy"),
            "agent": "a2a",
            "role": "orchestrator",
        }
        orchestration = _coerce_orchestration_context(start_data)
        session = _build_workflow_run_session(
            query=text,
            data=start_data,
            selected_blueprint=selected_blueprint,
            orchestration=orchestration,
            lesson_refs=lesson_refs,
        )
        if context_id:
            session["context_id"] = context_id
        task_id = session["session_id"]
        async with _workflow_sessions_lock:
            sessions = await _load_workflow_sessions()
            sessions[task_id] = session
            await _save_workflow_sessions(sessions)

    task = _session_to_a2a_task(session, base_url)
    result = {
        "task": task,
        "message": {
            "role": "ROLE_AGENT",
            "parts": _a2a_text_parts(
                f"Accepted task '{session.get('objective', '')}'. Track status via tasks/get or the task event stream."
            ),
            "messageId": f"{task_id}:accepted",
            "taskId": task_id,
        },
        "stream": {
            "url": f"{base_url.rstrip('/')}/a2a/tasks/{task_id}/events",
        },
    }
    if lesson_refs:
        result["active_lesson_refs"] = lesson_refs
    return result


async def handle_a2a_rpc(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response(_jsonrpc_error(None, -32700, "parse error"))
    if not isinstance(payload, dict):
        return web.json_response(_jsonrpc_error(None, -32600, "invalid request"))

    request_id = _coerce_a2a_request_id(payload.get("id"))
    if payload.get("id") is not None and request_id is None:
        return web.json_response(_jsonrpc_error(None, -32600, "invalid request"))
    if str(payload.get("jsonrpc", "") or "") != "2.0":
        return web.json_response(_jsonrpc_error(request_id, -32600, "invalid request"))
    raw_method = payload.get("method")
    if not isinstance(raw_method, str) or not raw_method.strip():
        return web.json_response(_jsonrpc_error(request_id, -32600, "invalid request"))
    method = _normalize_a2a_method(raw_method)
    params = payload.get("params")
    if not isinstance(params, dict):
        return web.json_response(_jsonrpc_error(request_id, -32602, "invalid params"))
    base_url = f"{request.scheme}://{request.host}"

    try:
        if method == "agent/getCard":
            return web.json_response(_jsonrpc_success(request_id, _build_a2a_agent_card(base_url)))

        if method == "agent/getAuthenticatedExtendedCard":
            return web.json_response(_jsonrpc_error(request_id, -32007, "authentication required"))

        if method == "tasks/resubscribe":
            return web.json_response(_jsonrpc_error(request_id, -32003, "push notification not supported"))

        if method == "tasks/get":
            task_id = str(params.get("id") or params.get("taskId") or "").strip()
            if not task_id:
                return web.json_response(_jsonrpc_error(request_id, -32602, "task id required"))
            history_length = params.get("historyLength")
            if history_length is not None:
                try:
                    history_length = int(history_length)
                except (TypeError, ValueError):
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
                if history_length < 0:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(task_id)
            if not session:
                return web.json_response(_jsonrpc_error(request_id, -32001, "task not found"))
            _ensure_session_runtime_fields(session)
            return web.json_response(
                _jsonrpc_success(
                    request_id,
                    _session_to_a2a_task(session, base_url, history_length=history_length),
                )
            )

        if method == "tasks/list":
            context_id = str(params.get("contextId") or "").strip()
            status_filter = _normalize_a2a_status_filter(params.get("status"))
            if params.get("status") is not None and not status_filter:
                return web.json_response(_jsonrpc_error(request_id, -32602, "invalid status"))
            explicit_page_size = "pageSize" in params
            page_size_raw = params.get("pageSize", params.get("limit", 50))
            try:
                page_size = int(page_size_raw if page_size_raw is not None else 50)
            except (TypeError, ValueError):
                return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageSize"))
            if page_size < 0 or page_size > 100 or (explicit_page_size and page_size == 0):
                return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageSize"))
            history_length = params.get("historyLength")
            if history_length is not None:
                try:
                    history_length = int(history_length)
                except (TypeError, ValueError):
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
                if history_length < 0:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid historyLength"))
            include_artifacts = bool(params.get("includeArtifacts", False))
            status_timestamp_after = str(params.get("statusTimestampAfter") or "").strip()
            cutoff_iso = ""
            if status_timestamp_after:
                try:
                    cutoff_iso = datetime.fromisoformat(status_timestamp_after.replace("Z", "+00:00")).isoformat()
                except ValueError:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid statusTimestampAfter"))
            page_token = str(params.get("pageToken") or "").strip()
            start = 0
            if page_token:
                try:
                    start = int(page_token)
                except ValueError:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageToken"))
                if start < 0:
                    return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageToken"))
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                items = list(sessions.values())
            items.sort(key=lambda item: float(item.get("updated_at", 0) or 0), reverse=True)
            filtered: List[Dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                _ensure_session_runtime_fields(item)
                task = _session_to_a2a_task(
                    item,
                    base_url,
                    history_length=history_length,
                    include_artifacts=include_artifacts,
                )
                if context_id and str(task.get("contextId", "") or "").strip() != context_id:
                    continue
                if status_filter and str(task.get("status", {}).get("state", "") or "").strip() != status_filter:
                    continue
                if cutoff_iso and str(task.get("status", {}).get("timestamp", "") or "") <= cutoff_iso:
                    continue
                filtered.append(task)
            total_size = len(filtered)
            if start > total_size:
                return web.json_response(_jsonrpc_error(request_id, -32602, "invalid pageToken"))
            tasks = filtered[start : start + page_size] if page_size > 0 else []
            next_page_token = ""
            if start + len(tasks) < total_size:
                next_page_token = str(start + len(tasks))
            return web.json_response(
                _jsonrpc_success(
                    request_id,
                    {
                        "tasks": tasks,
                        "totalSize": total_size,
                        "pageSize": len(tasks),
                        "nextPageToken": next_page_token,
                    },
                )
            )

        if method == "tasks/cancel":
            task_id = str(params.get("id") or params.get("taskId") or "").strip()
            if not task_id:
                return web.json_response(_jsonrpc_error(request_id, -32602, "task id required"))
            async with _workflow_sessions_lock:
                sessions = await _load_workflow_sessions()
                session = sessions.get(task_id)
                if not session:
                    return web.json_response(_jsonrpc_error(request_id, -32001, "task not found"))
                _ensure_session_runtime_fields(session)
                now = time.time()
                session["status"] = "canceled"
                session["updated_at"] = now
                session["trajectory"].append(
                    {
                        "ts": now,
                        "event_type": "task_canceled",
                        "phase_id": f"phase-{int(session.get('current_phase_index', 0) or 0)}",
                        "detail": str(params.get("reason", "") or "canceled via A2A RPC").strip(),
                    }
                )
                sessions[task_id] = session
                await _save_workflow_sessions(sessions)
            return web.json_response(_jsonrpc_success(request_id, _session_to_a2a_task(session, base_url)))

        if method in {"message/send", "message/stream"}:
            try:
                result = await _send_a2a_message(params, base_url)
            except A2ARequestError as exc:
                return web.json_response(_jsonrpc_error(request_id, exc.code, exc.message))
            task = result["task"]
            if method == "message/stream":
                stream_response = web.StreamResponse(
                    status=200,
                    headers={
                        "Content-Type": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                    },
                )
                await stream_response.prepare(request)
                await stream_response.write(
                    (
                        f"event: task\ndata: "
                        f"{json.dumps(_jsonrpc_success(request_id, task), separators=(',', ':'))}\n\n"
                    ).encode("utf-8")
                )
                await stream_response.write(
                    (
                        f"event: status-update\ndata: "
                        f"{json.dumps(_jsonrpc_success(request_id, _session_to_a2a_status_event(session, base_url, final=False)), separators=(',', ':'))}\n\n"
                    ).encode("utf-8")
                )
                for artifact in task.get("artifacts", []) or []:
                    if not isinstance(artifact, dict):
                        continue
                    await stream_response.write(
                        (
                            f"event: artifact-update\ndata: "
                            f"{json.dumps(_jsonrpc_success(request_id, _artifact_to_a2a_update(task, artifact)), separators=(',', ':'))}\n\n"
                        ).encode("utf-8")
                    )
                await stream_response.write(
                    (
                        f"event: message\ndata: "
                        f"{json.dumps(_jsonrpc_success(request_id, result.get('message', {})), separators=(',', ':'))}\n\n"
                    ).encode("utf-8")
                )
                await stream_response.write_eof()
                return stream_response
            return web.json_response(_jsonrpc_success(request_id, result))

        return web.json_response(_jsonrpc_error(request_id, -32601, "method not found"))
    except Exception as exc:
        logger.error("handle_a2a_rpc error=%s", exc)
        return web.json_response(
            _jsonrpc_error(request_id, -32603, "internal error", {"detail": str(exc)[:240]}),
        )


async def handle_a2a_tasks_send(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"error": "parse error"}, status=400)
    if not isinstance(payload, dict):
        return web.json_response({"error": "json object body required"}, status=400)

    task_id = payload.get("id")
    if task_id is not None and not isinstance(task_id, str):
        return web.json_response({"error": "id must be a string"}, status=400)
    message = payload.get("message")
    if not isinstance(message, dict):
        return web.json_response({"error": "message object required"}, status=400)

    role = str(message.get("role") or "").strip().lower()
    if role and role != "user":
        return web.json_response({"error": "message.role must be user"}, status=400)
    if not _extract_a2a_text(message):
        return web.json_response({"error": "message.parts[0].text required"}, status=400)

    params = dict(payload)
    if task_id:
        params["taskId"] = task_id
    base_url = f"{request.scheme}://{request.host}"
    try:
        result = await _send_a2a_message(params, base_url)
    except A2ARequestError as exc:
        return web.json_response({"error": exc.message}, status=exc.http_status)
    except Exception as exc:
        logger.error("handle_a2a_tasks_send error=%s", exc)
        return web.json_response({"error": "internal error", "detail": str(exc)[:240]}, status=500)

    task = result.get("task", {})
    return web.json_response(
        {
            "id": str(task.get("id") or task_id or ""),
            "status": task.get("status", {"state": "TASK_STATE_WORKING"}),
            "artifacts": task.get("artifacts", []),
        }
    )


async def handle_openai_models(_request: web.Request) -> web.Response:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{_switchboard_url.rstrip('/')}/v1/models")
        content_type = response.headers.get("content-type", "application/json")
        return web.Response(
            status=response.status_code,
            body=response.content,
            content_type=content_type.split(";", 1)[0] if content_type else None,
        )
    except Exception as exc:
        return _internal_error(exc)


async def handle_openai_chat_completions(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        if not isinstance(data, dict):
            return web.json_response({"error": "json object body required"}, status=400)
        return await _proxy_openai_request_via_coordinator(request, data, path="chat/completions")
    except Exception as exc:
        return _internal_error(exc)


async def handle_openai_completions(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        if not isinstance(data, dict):
            return web.json_response({"error": "json object body required"}, status=400)
        return await _proxy_openai_request_via_coordinator(request, data, path="completions")
    except Exception as exc:
        return _internal_error(exc)


async def handle_openai_responses(request: web.Request) -> web.Response:
    """Minimal OpenAI Responses API compatibility shim.

    The switchboard currently exposes chat/completions. Accept the Responses
    API's common `input` shape and route it through chat/completions while
    preserving the coordinator's profile routing headers. This is intentionally
    a compatibility subset, not a claim of full Responses API parity.
    """
    try:
        data = await request.json()
        if not isinstance(data, dict):
            return web.json_response({"error": "json object body required"}, status=400)
        input_value = data.get("input", data.get("messages"))
        messages: List[Dict[str, Any]] = []
        if isinstance(input_value, str):
            messages = [{"role": "user", "content": input_value}]
        elif isinstance(input_value, list):
            for item in input_value:
                if isinstance(item, dict):
                    role = str(item.get("role") or "user")
                    content = item.get("content")
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict):
                                text_parts.append(str(part.get("text") or part.get("input_text") or ""))
                            else:
                                text_parts.append(str(part))
                        content = "\n".join(p for p in text_parts if p)
                    messages.append({"role": role, "content": str(content or "")})
                else:
                    messages.append({"role": "user", "content": str(item)})
        elif input_value is not None:
            messages = [{"role": "user", "content": str(input_value)}]
        if not messages:
            return web.json_response({"error": "input or messages required"}, status=400)

        chat_payload = dict(data)
        chat_payload.pop("input", None)
        chat_payload["messages"] = messages
        upstream = await _proxy_openai_request_via_coordinator(request, chat_payload, path="chat/completions")

        # If upstream failed, preserve it exactly.
        if upstream.status >= 400:
            return upstream

        # The switchboard may force streaming for local profiles (N-2 contract).
        # If we get SSE back, accumulate chunks into a synthetic non-streaming response.
        upstream_ct = upstream.content_type or ""
        if "text/event-stream" in upstream_ct or "event-stream" in upstream_ct:
            raw = upstream.body.decode("utf-8", errors="replace")
            content_parts: List[str] = []
            first_chunk: Dict[str, Any] = {}
            for line in raw.splitlines():
                if not line.startswith("data: "):
                    continue
                chunk_str = line[6:].strip()
                if chunk_str in ("[DONE]", ""):
                    continue
                try:
                    chunk = json.loads(chunk_str)
                    if not first_chunk:
                        first_chunk = chunk
                    delta = ((chunk.get("choices") or [{}])[0] or {}).get("delta", {})
                    if delta.get("content"):
                        content_parts.append(delta["content"])
                except Exception:
                    continue
            upstream_data: Dict[str, Any] = {
                "id": first_chunk.get("id", f"chatcmpl-{int(time.time() * 1000)}"),
                "object": "chat.completion",
                "created": first_chunk.get("created", int(time.time())),
                "model": first_chunk.get("model"),
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": "".join(content_parts)},
                    "finish_reason": "stop",
                }],
                "usage": None,
            }
        else:
            try:
                upstream_data = json.loads(upstream.body.decode("utf-8"))
            except Exception:
                return upstream
        choice = ((upstream_data.get("choices") or [{}])[0] or {}) if isinstance(upstream_data, dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        text = str(message.get("content") or choice.get("text") or "")
        response_payload = {
            "id": upstream_data.get("id", f"resp_{int(time.time() * 1000)}"),
            "object": "response",
            "created_at": upstream_data.get("created", int(time.time())),
            "model": upstream_data.get("model") or data.get("model"),
            "status": "completed",
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }],
            "output_text": text,
            "usage": upstream_data.get("usage"),
        }
        response = web.json_response(response_payload)
        for header in ("X-AI-Profile", "X-Coordinator-Task-Archetype", "X-Coordinator-Model-Class", "X-Coordinator-Complexity"):
            if header in upstream.headers:
                response.headers[header] = upstream.headers[header]
        response.headers["X-OpenAI-Responses-Compat"] = "chat-completions-shim"
        return response
    except Exception as exc:
        return _internal_error(exc)


def register_routes(http_app: web.Application) -> None:
    http_app.router.add_get("/.well-known/mcp.json", handle_well_known_mcp)
    http_app.router.add_get("/.well-known/agent.json", handle_well_known_a2a)
    http_app.router.add_get("/.well-known/agent-card.json", handle_well_known_a2a)
    http_app.router.add_get("/v1/models", handle_openai_models)
    http_app.router.add_post("/v1/chat/completions", handle_openai_chat_completions)
    http_app.router.add_post("/v1/completions", handle_openai_completions)
    http_app.router.add_post("/v1/responses", handle_openai_responses)
    http_app.router.add_post("/", handle_a2a_rpc)
    http_app.router.add_post("/a2a", handle_a2a_rpc)
    http_app.router.add_post("/a2a/tasks/send", handle_a2a_tasks_send)
    http_app.router.add_get("/a2a/tasks/{session_id}/events", handle_a2a_task_events)
