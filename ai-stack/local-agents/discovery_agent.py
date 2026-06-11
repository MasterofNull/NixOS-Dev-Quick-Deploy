#!/usr/bin/env python3
"""
Discovery Agent - Proactive System & Codebase Analysis

Deterministically scans local harness signals and emits improvement candidates.
This agent does not execute fixes, fetch external content, or ask an LLM to
classify work; it prepares candidate artifacts for the existing review gates.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_executor import LocalAgentExecutor
from tool_registry import ToolRegistry, get_registry

logger = logging.getLogger(__name__)


_STATUS_RE = re.compile(r"^\[(OPEN|IN-FLIGHT|PENDING-REBUILD|DONE)\]\s+([^—]+)—\s*(.+?)\s+—")
_ACTIVE_STATUSES = {"OPEN", "IN-FLIGHT", "PENDING-REBUILD"}
_SEVERITY_RE = re.compile(r"^\s*Severity:\s*(critical|high|medium|low)\s*$", re.IGNORECASE)
_FILE_RE = re.compile(r"^\s*File:\s*(.+?)\s*$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _candidate_id(category: str, title: str) -> str:
    digest = hashlib.sha1(f"{category}:{title}".encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "candidate"
    return f"{category}-{slug}-{digest}"


def _priority_from_severity(severity: str) -> int:
    return {"critical": 1, "high": 2, "medium": 3, "low": 4}.get(severity.lower(), 3)


class DiscoveryAgent:
    def __init__(
        self,
        executor: Optional[LocalAgentExecutor] = None,
        tool_registry: Optional[ToolRegistry] = None,
        repo_root: Optional[Path] = None,
        output_path: Optional[Path] = None,
        delegation_feedback_path: Optional[Path] = None,
    ):
        self.executor = executor
        self.tool_registry = tool_registry or get_registry()
        self.repo_root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
        self.output_path = Path(output_path) if output_path else self.repo_root / ".agents" / "improvement" / "candidates.json"
        self.delegation_feedback_path = (
            Path(delegation_feedback_path)
            if delegation_feedback_path
            else Path(os.getenv("DELEGATION_FEEDBACK_LOG_PATH", "/var/lib/ai-stack/hybrid/telemetry/delegation-feedback.jsonl"))
        )

    async def discover_opportunities(self, persist: bool = True) -> Dict[str, Any]:
        logger.info("Scanning for system and code optimization opportunities.")
        return await asyncio.to_thread(self._discover_sync, persist)

    def _discover_sync(self, persist: bool) -> Dict[str, Any]:
        candidates: List[Dict[str, Any]] = []
        candidates.extend(self._scan_issue_backlog())
        candidates.extend(self._scan_health_spider_events())
        candidates.extend(self._scan_delegation_feedback())
        model_candidate = self._scan_model_profile_freshness()
        if model_candidate:
            candidates.append(model_candidate)

        candidates = self._dedupe_and_rank(candidates)
        # Phase 150 Slice 2: merge existing lifecycle state — new candidates get "proposed"
        # defaults; candidates already under review preserve their governance state.
        candidates = self._merge_lifecycle_state(candidates)
        generated_at = _utc_now().isoformat()
        payload = {
            "schema_version": "discovery-candidates.v1",
            "generated_at": generated_at,
            "source": "DiscoveryAgent",
            "total_candidates": len(candidates),
            "candidates": candidates,
        }
        if persist:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.output_path.with_suffix(f"{self.output_path.suffix}.tmp")
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(self.output_path)
        return payload

    _LIFECYCLE_FIELDS = frozenset({"state", "trust_score", "relevance", "governance", "eval_results", "lifecycle_log"})
    _LIFECYCLE_DEFAULTS: Dict[str, Any] = {
        "state": "proposed",
        "trust_score": 0.0,
        "relevance": 0.5,
        "governance": {"proposals": [], "reviews": [], "consensus_prd": None},
        "eval_results": {"sandbox_pass": None, "tokenomics_impact": "unknown", "hardware_compatible": None},
        "lifecycle_log": [],
    }

    def _merge_lifecycle_state(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge lifecycle fields from persisted candidates; add defaults for new ones."""
        existing: Dict[str, Dict[str, Any]] = {}
        if self.output_path.exists():
            try:
                data = json.loads(self.output_path.read_text(encoding="utf-8"))
                for c in data.get("candidates", []):
                    if c.get("id"):
                        existing[c["id"]] = c
            except (json.JSONDecodeError, OSError):
                pass

        result = []
        for candidate in candidates:
            cid = candidate.get("id", "")
            prev = existing.get(cid, {})
            for field, default in self._LIFECYCLE_DEFAULTS.items():
                if field in prev:
                    # preserve existing lifecycle state (e.g. evaluating, reviewed)
                    candidate[field] = prev[field]
                elif field not in candidate:
                    candidate[field] = (
                        list(default) if isinstance(default, list) else
                        dict(default) if isinstance(default, dict) else
                        default
                    )
            result.append(candidate)
        return result

    def _scan_issue_backlog(self) -> List[Dict[str, Any]]:
        path = self.repo_root / ".agent" / "memory" / "issues-backlog.md"
        if not path.exists():
            return []

        candidates: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _STATUS_RE.match(raw)
            if match:
                if current:
                    candidates.append(self._issue_candidate(current))
                status, scope, description = match.groups()
                if status not in _ACTIVE_STATUSES:
                    current = None
                    continue
                current = {
                    "status": status,
                    "scope": scope.strip(),
                    "description": description.strip(),
                    "severity": "medium",
                    "files": [],
                }
                continue
            if not current:
                continue
            severity = _SEVERITY_RE.match(raw)
            if severity:
                current["severity"] = severity.group(1).lower()
                continue
            files = _FILE_RE.match(raw)
            if files:
                current["files"] = [part.strip() for part in re.split(r";|,", files.group(1)) if part.strip()]
        if current:
            candidates.append(self._issue_candidate(current))
        return candidates

    def _issue_candidate(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        scope = str(issue.get("scope", "unknown")).strip()
        severity = str(issue.get("severity", "medium"))
        title = f"Resolve open issue: {scope}"
        return {
            "id": _candidate_id("issue", title),
            "title": title,
            "category": "system-fix",
            "priority": _priority_from_severity(severity),
            "estimated_impact": f"{severity} issue pressure",
            "effort": "medium",
            "related_files": issue.get("files", [])[:5],
            "evidence": [
                f"issues-backlog status={issue.get('status')}",
                str(issue.get("description", ""))[:240],
            ],
            "suggested_actions": [
                "Create a bounded implementation slice",
                "Add aq-qa and dashboard visibility before closing",
            ],
        }

    def _scan_health_spider_events(self) -> List[Dict[str, Any]]:
        path = self.repo_root / ".agents" / "telemetry" / "hybrid-events.jsonl"
        if not path.exists():
            return []
        counts: Counter[str] = Counter()
        examples: Dict[str, Dict[str, Any]] = {}
        for entry in self._read_jsonl_tail(path, limit=500):
            event_type = str(entry.get("event_type") or entry.get("event") or "")
            if not event_type.startswith("health_spider_") or event_type == "health_spider_cycle":
                continue
            key = f"{event_type}:{entry.get('zone', 'unknown')}"
            counts[key] += 1
            examples.setdefault(key, entry)
        candidates = []
        for key, count in counts.most_common(5):
            event_type, zone = key.split(":", 1)
            title = f"Investigate recurring health signal: {zone} {event_type.removeprefix('health_spider_')}"
            example = examples.get(key, {})
            candidates.append({
                "id": _candidate_id("health", title),
                "title": title,
                "category": "health-spider",
                "priority": 2 if count >= 3 else 3,
                "estimated_impact": f"{count} recent health-spider event(s)",
                "effort": "small",
                "related_files": ["scripts/ai/aq-health-spider"],
                "evidence": [json.dumps(example, sort_keys=True)[:320]],
                "suggested_actions": [
                    "Review recent health-spider telemetry and attention queue",
                    "Promote recurring event to a focused aq-qa or remediation check",
                ],
            })
        return candidates

    def _scan_delegation_feedback(self) -> List[Dict[str, Any]]:
        if not self.delegation_feedback_path.exists():
            return []
        counts: Counter[str] = Counter()
        examples: Dict[str, Dict[str, Any]] = {}
        for entry in self._read_jsonl_tail(self.delegation_feedback_path, limit=300):
            classes = entry.get("failure_classes")
            if not isinstance(classes, list):
                classes = [entry.get("failure_class")]
            for failure_class in classes:
                if not failure_class:
                    continue
                key = str(failure_class)
                counts[key] += 1
                examples.setdefault(key, entry)
        candidates = []
        for failure_class, count in counts.most_common(5):
            title = f"Reduce delegated prompt failure: {failure_class}"
            example = examples.get(failure_class, {})
            candidates.append({
                "id": _candidate_id("delegation", title),
                "title": title,
                "category": "delegation-quality",
                "priority": 2 if count >= 3 else 3,
                "estimated_impact": f"{count} delegation feedback event(s)",
                "effort": "medium",
                "related_files": [
                    "ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py",
                    "config/intent-routing-map.json",
                ],
                "evidence": [
                    f"failure_class={failure_class}",
                    str(example.get("task_excerpt", ""))[:180],
                ],
                "suggested_actions": [
                    "Inspect failure class examples before changing prompts",
                    "Add or update a focused regression gate for this failure class",
                ],
            })
        return candidates

    def _scan_model_profile_freshness(self) -> Optional[Dict[str, Any]]:
        path = self.repo_root / "config" / "model-profile.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        meta = payload.get("_meta") if isinstance(payload, dict) else {}
        probed_at = _parse_datetime(payload.get("probed_at"))
        last_updated = _parse_datetime(meta.get("last_updated") if isinstance(meta, dict) else None)
        timestamps = [item for item in (probed_at, last_updated) if item is not None]
        if not timestamps:
            age_days = None
        else:
            age_days = max((_utc_now() - item).days for item in timestamps)
        max_age_days = int(payload.get("freshness_max_age_days", 30) or 30)
        if age_days is not None and age_days <= max_age_days:
            return None
        title = "Refresh local model profile freshness metadata"
        return {
            "id": _candidate_id("model", title),
            "title": title,
            "category": "model-catalog",
            "priority": 2,
            "estimated_impact": f"profile_age_days={age_days if age_days is not None else 'unknown'}",
            "effort": "small",
            "related_files": ["config/model-profile.json", "ai-stack/mcp-servers/shared/model_catalog.py"],
            "evidence": [
                f"probed_at={payload.get('probed_at')}",
                f"_meta.last_updated={(meta or {}).get('last_updated') if isinstance(meta, dict) else None}",
            ],
            "suggested_actions": [
                "Refresh probe metadata or mark freshness policy explicitly",
                "Add aq-qa/dashboard freshness gates before activating new models",
            ],
        }

    def _read_jsonl_tail(self, path: Path, limit: int) -> List[Dict[str, Any]]:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        except OSError:
            return []
        entries: List[Dict[str, Any]] = []
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                entries.append(item)
        return entries

    def _dedupe_and_rank(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_id: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            cid = str(candidate.get("id") or _candidate_id(str(candidate.get("category", "unknown")), str(candidate.get("title", "candidate"))))
            candidate["id"] = cid
            by_id.setdefault(cid, candidate)
        ranked = sorted(
            by_id.values(),
            key=lambda item: (
                int(item.get("priority", 9) or 9),
                str(item.get("category", "")),
                str(item.get("title", "")),
            ),
        )
        return ranked[:25]
