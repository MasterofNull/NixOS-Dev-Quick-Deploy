#!/usr/bin/env python3
"""Runtime security and audit controls for the dashboard API."""

from __future__ import annotations

import json
import os
import threading
import time
import hashlib
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Tuple


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DashboardRateLimiter:
    """Simple in-memory per-client rate limiter for dashboard HTTP routes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[Tuple[str, str], Deque[float]] = {}

    def enabled(self) -> bool:
        return os.getenv("DASHBOARD_RATE_LIMIT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

    def _window_seconds(self) -> int:
        try:
            return max(1, int(os.getenv("DASHBOARD_RATE_LIMIT_WINDOW_SECONDS", "60")))
        except ValueError:
            return 60

    def _limit_for_category(self, category: str) -> int:
        env_map = {
            "operator_write": "DASHBOARD_RATE_LIMIT_OPERATOR_WRITE_RPM",
            "search": "DASHBOARD_RATE_LIMIT_SEARCH_RPM",
            "health": "DASHBOARD_RATE_LIMIT_HEALTH_RPM",
            "default": "DASHBOARD_RATE_LIMIT_DEFAULT_RPM",
        }
        env_name = env_map.get(category, "DASHBOARD_RATE_LIMIT_DEFAULT_RPM")
        try:
            return max(1, int(os.getenv(env_name, os.getenv("DASHBOARD_RATE_LIMIT_DEFAULT_RPM", "240"))))
        except ValueError:
            return 240

    def categorize(self, path: str, method: str) -> str:
        method = method.upper()
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            return "operator_write"
        if path.startswith("/api/deployments/search") or path.startswith("/api/deployments/graph"):
            return "search"
        if path.startswith("/api/health"):
            return "health"
        return "default"

    def check(self, client_id: str, path: str, method: str) -> Dict[str, Any]:
        category = self.categorize(path, method)
        limit = self._limit_for_category(category)
        window = self._window_seconds()
        key = (client_id, category)
        now = time.monotonic()

        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            allowed = len(bucket) < limit
            retry_after = 0
            if allowed:
                bucket.append(now)
            elif bucket:
                retry_after = max(1, int(window - (now - bucket[0])))
            remaining = max(0, limit - len(bucket))

        return {
            "allowed": allowed,
            "category": category,
            "limit": limit,
            "remaining": remaining,
            "retry_after": retry_after,
            "window_seconds": window,
        }


class OperatorAuditLog:
    """Append-only JSONL audit log for dashboard operator activity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def path(self) -> Path:
        configured = os.getenv("DASHBOARD_OPERATOR_AUDIT_LOG_PATH", "").strip()
        if configured:
            return Path(configured)
        data_dir = os.getenv("DASHBOARD_DATA_DIR", "")
        if data_dir:
            return Path(data_dir) / "telemetry" / "operator-audit.jsonl"
        context_db = os.getenv("DASHBOARD_CONTEXT_DB_PATH", "").strip()
        if context_db:
            return Path(context_db).resolve().parent / "operator-audit.jsonl"
        for telemetry_env in ("PRSI_ACTIONS_LOG_PATH", "PRSI_ACTION_QUEUE_PATH", "OPTIMIZER_ACTIONS_LOG"):
            candidate = os.getenv(telemetry_env, "").strip()
            if candidate:
                return Path(candidate).resolve().parent / "operator-audit.jsonl"
        return Path.home() / ".local" / "share" / "nixos-command-center" / "telemetry" / "operator-audit.jsonl"

    def _should_audit(self, path: str, method: str) -> bool:
        if not path.startswith("/api/"):
            return False
        if path.startswith("/api/metrics") or path.startswith("/api/health/services"):
            return False
        if path.startswith("/api/security/") or path.startswith("/api/audit/operator/"):
            return True
        if path == "/api/insights/security/compliance":
            return True
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            return True
        return path.startswith("/api/deployments/search") or path.startswith("/api/deployments/graph")

    def _seal_algorithm(self) -> str:
        return "sha256-chain-v1"

    def _canonical_json(self, payload: Dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _seal_hash(self, payload: Dict[str, Any]) -> str:
        material = {key: value for key, value in payload.items() if key != "hash"}
        return hashlib.sha256(self._canonical_json(material).encode("utf-8")).hexdigest()

    def _entry_digest(self, payload: Dict[str, Any]) -> str:
        existing_hash = str(payload.get("hash") or "").strip()
        if existing_hash:
            return existing_hash
        return self._seal_hash(payload)

    def _read_recent_unlocked(self, target: Path, limit: int = 100) -> List[Dict[str, Any]]:
        if not target.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for raw in target.read_text(encoding="utf-8").splitlines()[-max(1, limit):]:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows

    def append(
        self,
        *,
        path: str,
        method: str,
        status_code: int,
        client_ip: str,
        user_agent: str,
        query_keys: List[str],
        category: str,
    ) -> None:
        if not self._should_audit(path, method):
            return
        target = self.path()
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            previous = self._read_recent_unlocked(target, limit=1)
            previous_digest = self._entry_digest(previous[-1]) if previous else ""
            payload = {
                "ts": _utc_now_iso(),
                "path": path,
                "method": method.upper(),
                "status_code": int(status_code),
                "client_ip": client_ip,
                "user_agent": user_agent[:160],
                "query_keys": sorted({key for key in query_keys if key}),
                "category": category,
                "seal_alg": self._seal_algorithm(),
                "prev_hash": previous_digest,
            }
            payload["hash"] = self._seal_hash(payload)
            line = json.dumps(payload, sort_keys=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def read_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        target = self.path()
        return self._read_recent_unlocked(target, limit=limit)

    def query_events(
        self,
        *,
        limit: int = 100,
        path_prefix: str = "",
        method: str = "",
        status_code: int | None = None,
        category: str = "",
        contains: str = "",
    ) -> List[Dict[str, Any]]:
        rows = self.read_recent(limit=max(limit * 5, 200))
        filtered: List[Dict[str, Any]] = []
        method = method.strip().upper()
        path_prefix = path_prefix.strip()
        category = category.strip()
        contains = contains.strip().lower()
        for row in rows:
            row_path = str(row.get("path") or "")
            row_method = str(row.get("method") or "").upper()
            row_category = str(row.get("category") or "")
            if path_prefix and not row_path.startswith(path_prefix):
                continue
            if method and row_method != method:
                continue
            if status_code is not None and int(row.get("status_code") or 0) != int(status_code):
                continue
            if category and row_category != category:
                continue
            if contains:
                haystack = " ".join(
                    [
                        row_path,
                        row_method,
                        row_category,
                        str(row.get("client_ip") or ""),
                        str(row.get("user_agent") or ""),
                        " ".join(str(item) for item in (row.get("query_keys") or [])),
                    ]
                ).lower()
                if contains not in haystack:
                    continue
            filtered.append(row)
        return filtered[-max(1, limit):]

    def integrity_status(self, limit: int = 500) -> Dict[str, Any]:
        rows = self.read_recent(limit=limit)
        if not rows:
            return {
                "available": False,
                "path": str(self.path()),
                "valid": True,
                "seal_algorithm": self._seal_algorithm(),
                "checked_events": 0,
                "sealed_events": 0,
                "legacy_events": 0,
                "last_hash": "",
            }

        previous_digest = ""
        sealed_events = 0
        legacy_events = 0
        first_invalid_index = None
        invalid_reason = ""

        for index, row in enumerate(rows, start=1):
            current_hash = str(row.get("hash") or "").strip()
            if current_hash:
                sealed_events += 1
                expected_hash = self._seal_hash(row)
                if current_hash != expected_hash:
                    first_invalid_index = index
                    invalid_reason = "hash_mismatch"
                    break
                if str(row.get("prev_hash") or "") != previous_digest:
                    first_invalid_index = index
                    invalid_reason = "chain_mismatch"
                    break
                previous_digest = current_hash
                continue

            legacy_events += 1
            previous_digest = self._entry_digest(row)

        return {
            "available": True,
            "path": str(self.path()),
            "valid": first_invalid_index is None,
            "seal_algorithm": self._seal_algorithm(),
            "checked_events": len(rows),
            "sealed_events": sealed_events,
            "legacy_events": legacy_events,
            "fully_sealed": legacy_events == 0 and sealed_events == len(rows),
            "first_invalid_index": first_invalid_index,
            "invalid_reason": invalid_reason or None,
            "last_hash": previous_digest,
        }

    def summary(self, limit: int = 500) -> Dict[str, Any]:
        rows = self.read_recent(limit=limit)
        path_counts = Counter(str(row.get("path") or "") for row in rows)
        method_counts = Counter(str(row.get("method") or "") for row in rows)
        status_counts = Counter(str(row.get("status_code") or "") for row in rows)
        category_counts = Counter(str(row.get("category") or "") for row in rows)
        integrity = self.integrity_status(limit=limit)
        return {
            "available": bool(rows),
            "append_only": True,
            "tamper_evident": True,
            "path": str(self.path()),
            "total_events": len(rows),
            "last_event_at": rows[-1].get("ts") if rows else None,
            "top_paths": path_counts.most_common(5),
            "methods": method_counts,
            "statuses": status_counts,
            "categories": category_counts,
            "integrity": integrity,
        }


_RATE_LIMITER = DashboardRateLimiter()
_OPERATOR_AUDIT = OperatorAuditLog()


def get_dashboard_rate_limiter() -> DashboardRateLimiter:
    return _RATE_LIMITER


def get_operator_audit_log() -> OperatorAuditLog:
    return _OPERATOR_AUDIT
