"""Structured tool call audit logging for MCP servers.

Phase 12.3.2: writes via the audit-sidecar Unix socket when available so that
MCP service processes never hold a direct writable file descriptor to the log.
Falls back to direct file write only when the socket is absent (dev/test mode).
"""

import hashlib
import json
import os
import socket as _socket_module
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import structlog

_audit_log_path = Path(os.getenv('TOOL_AUDIT_LOG_PATH', '/var/log/nixos-ai-stack/tool-audit.jsonl'))
_audit_socket_path = os.getenv('AUDIT_SOCKET_PATH', '/run/ai-audit-sidecar.sock')

logger = structlog.get_logger(__name__)


def _send_via_socket(entry_json: str) -> bool:
    """Attempt to deliver the entry to the audit sidecar via Unix socket.

    Returns True on success, False if the socket is unavailable.
    The 0.5 s timeout prevents audit I/O from blocking tool calls.
    """
    try:
        with _socket_module.socket(_socket_module.AF_UNIX, _socket_module.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect(_audit_socket_path)
            s.sendall((entry_json + '\n').encode('utf-8'))
        return True
    except OSError:
        return False


def write_audit_entry(
    service: str,
    tool_name: str,
    caller_identity: str,
    parameters: dict,
    risk_tier: str,
    outcome: str,
    error_message: Optional[str],
    latency_ms: float,
) -> None:
    """Write a structured audit log entry for a tool call.

    Args:
        service: The service name (e.g., 'aidb', 'hybrid-coordinator')
        tool_name: Name of the tool that was called
        caller_identity: API key or 'anonymous'
        parameters: Tool call parameters dict
        risk_tier: Risk tier string (e.g., 'low', 'medium', 'high')
        outcome: Outcome string ('success' or 'error')
        error_message: Error message if outcome is 'error', None otherwise
        latency_ms: Execution latency in milliseconds
    """
    try:
        parameters_hash = hashlib.sha256(
            json.dumps(parameters, sort_keys=True).encode()
        ).hexdigest()[:16]
        caller_hash = hashlib.sha256(caller_identity.encode()).hexdigest()[:16]

        entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'service': service,
            'tool_name': tool_name,
            'caller_hash': caller_hash,
            'parameters_hash': parameters_hash,
            'risk_tier': risk_tier,
            'outcome': outcome,
            'error_message': error_message,
            'latency_ms': latency_ms,
        }

        entry_json = json.dumps(entry)

        # Phase 12.3.2 — prefer sidecar socket so the service process never holds
        # a writable fd to the audit log file directly.
        if _send_via_socket(entry_json):
            return

        # Fallback: direct write (dev mode or sidecar not running).
        parent_dir = _audit_log_path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, mode=0o755, exist_ok=True)
        with open(_audit_log_path, 'a', encoding='utf-8') as f:
            f.write(entry_json + '\n')

    except Exception:  # noqa: BLE001 - audit failure must NEVER crash the service
        logger.warning('audit_write_failed', service=service, tool_name=tool_name)
