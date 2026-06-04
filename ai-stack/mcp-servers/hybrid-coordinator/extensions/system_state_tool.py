"""
context_system_state MCP tool — Phase 115.4

Returns compressed system intelligence artifact data for agent context injection.
File I/O is fully async (asyncio.to_thread) — never blocks the coordinator event loop.
If artifact is missing or older than max_age_s: returns last valid + _stale=True.
Never blocks to generate a fresh snapshot (timer handles refresh asynchronously).
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

logger = logging.getLogger("hybrid-coordinator")

# Per-domain freshness thresholds (seconds).
_FRESHNESS_S: Dict[str, int] = {
    "services": 60,
    "errors": 300,
    "git": 900,
    "validation": 1800,
    "data": 300,
    "agent": 60,
    "performance": 900,
    "attention": 120,
}

_VALID_DOMAINS: Set[str] = set(_FRESHNESS_S) | {"summary"}

_ARTIFACT_PATH = Path(
    os.environ.get(
        "SYSTEM_STATE_ARTIFACT_PATH",
        "/var/lib/ai-stack/hybrid/telemetry/latest-system-state.json",
    )
)


def _read_artifact_sync() -> Optional[Dict[str, Any]]:
    """Read artifact JSON from disk. Invoked via asyncio.to_thread only."""
    if not _ARTIFACT_PATH.exists():
        return None
    try:
        return json.loads(_ARTIFACT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("context_system_state: artifact read failed: %s", exc)
        return None


def _build_summary(snap: Dict[str, Any]) -> str:
    """Compact ≤200-token summary text from snapshot dict."""
    parts = []

    svcs = snap.get("services") or []
    if svcs:
        active = sum(1 for s in svcs if s.get("status") == "active")
        failed = [s["name"] for s in svcs if s.get("status") in ("failed", "inactive") and s.get("sub_state") != "dead"]
        parts.append("Services {}/{} active{}".format(
            active, len(svcs),
            ", failed: {}".format(",".join(failed[:3])) if failed else "",
        ))

    git = snap.get("git") or {}
    if git:
        parts.append("Git branch={} uncommitted={}".format(
            git.get("branch", "?"),
            len(git.get("uncommitted_files") or []),
        ))

    val = snap.get("validation") or {}
    qa = val.get("aq_qa") or {}
    if qa.get("available"):
        parts.append("QA {}/{} pass".format(qa.get("passed", 0), qa.get("total", 0)))

    errors = snap.get("errors") or []
    if errors:
        top = errors[0]
        parts.append("Errors(1h): {} types top={}/{}x{}".format(
            len(errors), top.get("service", "?"), top.get("type", "?"), top.get("count", 0),
        ))

    agent = snap.get("agent") or {}
    if agent.get("current_objective"):
        obj = str(agent["current_objective"])[:60]
        parts.append("Phase={} tasks={} obj={}".format(
            agent.get("phase", "?"),
            len(agent.get("open_tasks") or []),
            obj,
        ))

    attn = snap.get("attention") or {}
    pending_gate = attn.get("pending_human_gate", 0)
    if pending_gate:
        parts.append("ATTENTION: {} items pending human gate".format(pending_gate))

    ts = snap.get("generated_at", "?")[:19].replace("T", " ")
    partial_tag = " [partial]" if snap.get("partial") else ""
    header = "[SYSTEM STATE {} UTC{}]".format(ts, partial_tag)
    return "{} {}".format(header, " | ".join(parts)) if parts else header


async def context_system_state(domain: str = "summary", max_age_s: int = 900) -> Dict[str, Any]:
    """
    Return system intelligence context for agent consumption.

    domain="summary" (default): ≤200-token text summary of all domains.
    domain=<name>: filtered dict for services|git|errors|validation|data|
                   agent|performance|attention.

    Returns _stale=True if artifact is older than max_age_s or the
    per-domain freshness threshold — never blocks to regenerate.
    """
    if domain not in _VALID_DOMAINS:
        return {
            "error": "unknown domain '{}' — valid: {}".format(domain, sorted(_VALID_DOMAINS)),
            "summary": "Unknown domain requested: {}".format(domain),
        }

    snap = await asyncio.to_thread(_read_artifact_sync)

    if snap is None:
        return {
            "_stale": True,
            "_source_status": "unavailable",
            "_error": "artifact not found at {}".format(_ARTIFACT_PATH),
            "summary": (
                "System state artifact not yet generated. "
                "Run: aq-system-state  (or wait for ai-system-state.timer)"
            ),
            "domain": domain,
        }

    generated_at_str = snap.get("generated_at", "")
    freshness_s = 0
    is_stale = False
    try:
        gen_ts = datetime.fromisoformat(generated_at_str.replace("Z", "+00:00"))
        freshness_s = int((datetime.now(timezone.utc) - gen_ts).total_seconds())
        threshold = min(max_age_s, _FRESHNESS_S.get(domain, max_age_s))
        is_stale = freshness_s > threshold
    except Exception:
        pass

    summary_text = _build_summary(snap)

    if domain == "summary":
        return {
            "summary": summary_text,
            "generated_at": generated_at_str,
            "freshness_seconds": freshness_s,
            "partial": snap.get("partial", False),
            "_stale": is_stale,
        }

    domain_data = snap.get(domain)
    if domain_data is None:
        domain_data = {
            "_source_status": "unavailable",
            "_error": "domain '{}' not present in artifact".format(domain),
        }

    return {
        "domain": domain,
        "data": domain_data,
        "generated_at": generated_at_str,
        "freshness_seconds": freshness_s,
        "stale": is_stale,
        "summary": summary_text,
    }
