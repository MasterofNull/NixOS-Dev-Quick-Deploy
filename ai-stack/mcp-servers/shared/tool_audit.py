"""Structured tool call audit logging for MCP servers."""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import structlog

_audit_log_path = Path(os.getenv('TOOL_AUDIT_LOG_PATH', '/var/log/nixos-ai-stack/tool-audit.jsonl'))

logger = structlog.get_logger(__name__)


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
        
        parent_dir = _audit_log_path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, mode=0o755, exist_ok=True)
        
        with open(_audit_log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:  # noqa: BLE001 - audit failure must NEVER crash the service
        logger.warning('audit_write_failed', service=service, tool_name=tool_name)
