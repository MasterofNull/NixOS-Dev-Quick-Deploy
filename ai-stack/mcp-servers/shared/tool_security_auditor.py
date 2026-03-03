"""First-use security auditor for tool metadata and invocation parameters.

This layer is intentionally conservative:
- Audit unknown tool/version fingerprints on first use.
- Sanitize known-dangerous metadata/parameter fields.
- Cache approval decisions locally to skip repeat audits.
"""

from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from shared.tool_audit import write_audit_entry

try:
    import structlog
    logger = structlog.get_logger(__name__)
except Exception:  # pragma: no cover - fallback for lightweight environments
    logger = logging.getLogger(__name__)


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return json.dumps({"repr": repr(value)}, sort_keys=True)


def _default_policy() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "blocked_tools": ["shell_exec", "remote_ssh_exec", "raw_system_command"],
        "blocked_endpoint_patterns": ["/control/*", "*/reload-model", "*/session/*/mode"],
        "blocked_reason_keywords": [
            "exec",
            "shell",
            "sudo",
            "delete",
            "truncate",
            "drop",
            "overwrite",
            "network egress",
        ],
        "strip_manifest_keys": ["exec", "command", "shell", "script", "sudo", "token", "api_key"],
        "blocked_parameter_keys": ["exec", "command", "shell", "script", "sudo", "api_key", "token"],
        "max_parameter_string_length": 4096,
    }


class ToolSecurityAuditor:
    def __init__(
        self,
        *,
        service_name: str,
        policy_path: Path,
        cache_path: Path,
        enabled: bool = True,
        enforce: bool = True,
        cache_ttl_hours: int = 168,
    ) -> None:
        self.service_name = service_name
        self.policy_path = Path(policy_path)
        self.cache_path = Path(cache_path)
        self.enabled = enabled
        self.enforce = enforce
        self.cache_ttl_seconds = max(3600, int(cache_ttl_hours) * 3600)
        self._lock = threading.Lock()

    def _load_policy(self) -> Dict[str, Any]:
        policy = _default_policy()
        if not self.policy_path.exists():
            return policy
        try:
            loaded = json.loads(self.policy_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                policy.update(loaded)
        except Exception as exc:
            logger.warning("tool_security_policy_load_failed", path=str(self.policy_path), error=str(exc))
        return policy

    def _load_cache(self) -> Dict[str, Any]:
        if not self.cache_path.exists():
            return {"entries": {}}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("entries"), dict):
                return payload
        except Exception:
            pass
        return {"entries": {}}

    def _save_cache(self, payload: Dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.cache_path)

    def _fingerprint(self, tool_name: str, metadata: Dict[str, Any], policy_hash: str) -> str:
        stable = {
            "tool_name": tool_name,
            "endpoint": metadata.get("endpoint"),
            "manifest": metadata.get("manifest", {}),
            "reason": metadata.get("reason", ""),
            "policy_hash": policy_hash,
        }
        return hashlib.sha256(_safe_json(stable).encode("utf-8")).hexdigest()

    def _sanitize(self, metadata: Dict[str, Any], policy: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        out = copy.deepcopy(metadata)
        changes: List[str] = []
        banned_manifest_keys = {str(k).strip().lower() for k in policy.get("strip_manifest_keys", [])}
        banned_param_keys = {str(k).strip().lower() for k in policy.get("blocked_parameter_keys", [])}
        max_param_len = int(policy.get("max_parameter_string_length", 4096))

        manifest = out.get("manifest")
        if isinstance(manifest, dict):
            for key in list(manifest.keys()):
                if str(key).strip().lower() in banned_manifest_keys:
                    manifest.pop(key, None)
                    changes.append(f"manifest_key_removed:{key}")

        params = out.get("parameters")
        if isinstance(params, dict):
            for key in list(params.keys()):
                lowered = str(key).strip().lower()
                if lowered in banned_param_keys:
                    params.pop(key, None)
                    changes.append(f"parameter_removed:{key}")
                    continue
                value = params.get(key)
                if isinstance(value, str) and len(value) > max_param_len:
                    params[key] = value[:max_param_len]
                    changes.append(f"parameter_truncated:{key}")
        return out, changes

    def _evaluate(self, tool_name: str, metadata: Dict[str, Any], policy: Dict[str, Any]) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        name = (tool_name or "").strip().lower()
        endpoint = str(metadata.get("endpoint", "")).strip().lower()
        reason_text = str(metadata.get("reason", "")).strip().lower()
        blob = _safe_json(metadata).lower()

        blocked_tools = {str(t).strip().lower() for t in policy.get("blocked_tools", [])}
        if name in blocked_tools:
            reasons.append("blocked_tool_name")

        for pattern in policy.get("blocked_endpoint_patterns", []):
            p = str(pattern).strip().lower()
            if p and endpoint and fnmatch.fnmatch(endpoint, p):
                reasons.append(f"blocked_endpoint_pattern:{p}")
                break

        for kw in policy.get("blocked_reason_keywords", []):
            keyword = str(kw).strip().lower()
            if not keyword:
                continue
            if keyword in reason_text or keyword in blob:
                reasons.append(f"blocked_keyword:{keyword}")
                break

        return (len(reasons) == 0), reasons

    def audit_tool(self, tool_name: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        normalized_name = (tool_name or "").strip()
        if not normalized_name:
            raise ValueError("tool_name is required")
        data = metadata if isinstance(metadata, dict) else {}
        policy = self._load_policy()
        policy_hash = hashlib.sha256(_safe_json(policy).encode("utf-8")).hexdigest()[:16]

        if not self.enabled:
            return {
                "tool_name": normalized_name,
                "approved": True,
                "safe": True,
                "cached": False,
                "first_seen": False,
                "policy_hash": policy_hash,
                "sanitized_metadata": data,
                "reasons": [],
                "changes": [],
            }

        with self._lock:
            cache = self._load_cache()
            entries = cache.setdefault("entries", {})
            fingerprint = self._fingerprint(normalized_name, data, policy_hash)
            key = f"{normalized_name}:{fingerprint[:20]}"
            now = int(time.time())
            record = entries.get(key, {})
            if record:
                age = now - int(record.get("updated_at_epoch", now))
                if age <= self.cache_ttl_seconds:
                    cached_safe = bool(record.get("safe", False))
                    return {
                        "tool_name": normalized_name,
                        "approved": cached_safe,
                        "safe": cached_safe,
                        "cached": True,
                        "first_seen": False,
                        "policy_hash": policy_hash,
                        "sanitized_metadata": record.get("sanitized_metadata", data),
                        "reasons": record.get("reasons", []),
                        "changes": record.get("changes", []),
                    }

            sanitized, changes = self._sanitize(data, policy)
            approved, reasons = self._evaluate(normalized_name, sanitized, policy)
            safe = bool(approved)

            entries[key] = {
                "tool_name": normalized_name,
                "fingerprint": fingerprint,
                "safe": safe,
                "approved": approved,
                "policy_hash": policy_hash,
                "changes": changes,
                "reasons": reasons,
                "sanitized_metadata": sanitized,
                "updated_at_epoch": now,
            }
            self._save_cache(cache)

        latency_ms = (time.time() - start) * 1000.0
        try:
            write_audit_entry(
                service=f"{self.service_name}-tool-security",
                tool_name=normalized_name,
                caller_identity=self.service_name,
                parameters={"reasons": reasons, "changes": changes, "enforce": self.enforce},
                risk_tier="medium",
                outcome="success" if safe else "error",
                error_message=None if safe else "; ".join(reasons),
                latency_ms=latency_ms,
            )
        except Exception:
            logger.debug("tool_security_audit_log_failed", tool_name=normalized_name)

        if not safe and self.enforce:
            raise PermissionError(
                f"tool '{normalized_name}' blocked by first-use security auditor: {', '.join(reasons)}"
            )
        return {
            "tool_name": normalized_name,
            "approved": safe,
            "safe": safe,
            "cached": False,
            "first_seen": True,
            "policy_hash": policy_hash,
            "sanitized_metadata": sanitized,
            "reasons": reasons,
            "changes": changes,
        }
