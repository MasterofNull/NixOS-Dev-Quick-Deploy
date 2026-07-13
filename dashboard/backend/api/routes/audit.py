#!/usr/bin/env python3
"""Operator audit trail routes."""

import calendar
import json
import time
from pathlib import Path

from fastapi import APIRouter

from api.services.runtime_controls import get_operator_audit_log

router = APIRouter()
audit_log = get_operator_audit_log()

# C0.3 read-only projection: the authorized Phase-0 integration
# (_check_state_authorities in scripts/testing/harness_qa/phases/phase0.py) atomically
# publishes the read-only bounded checker's validated {meta, findings} document here. This
# route projects last-check / age / blocker-count onto the EXISTING audit-integrity card. It
# adds no runtime authority, writer, store, or route. The projection is FAIL-CLOSED: only a
# document that satisfies every shape/type/identity invariant yields available=true; anything
# missing/incomplete/stale/malformed degrades to available=false with null blockers (never an
# invented zero). Rebuild source: run Phase-0 (`aq-qa 0`), which republishes the snapshot.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_STATE_AUTHORITY_SNAPSHOT = _REPO_ROOT / ".agents" / "governance" / "state-authorities-latest.json"
_SA_ALLOWED_CONDITIONS = {"SINGLE", "SPLIT_BRAIN", "UNKNOWN", "UNOWNED"}
_STATE_AUTHORITY_MAX_AGE_SECONDS = 3600


def _sa_nonneg_int(value: object) -> bool:
    """True only for a genuine nonnegative int (bool rejected — True/False are not counts)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _state_authorities_default() -> dict:
    return {
        "available": False,
        "last_check": None,
        "age_seconds": None,
        "blocker_count": None,
        "authorities_total": None,
        "condition_counts": None,
        "cycle1_authority": "NOT_AUTHORIZED",
        "source": ".agents/governance/state-authorities-latest.json",
        "rebuild": "aq-qa 0 (Phase-0 _check_state_authorities republishes the snapshot)",
    }


def _state_authorities_projection() -> dict:
    """Fail-closed read-only projection of the published checker snapshot for the audit card.

    Returns available=false with null blockers unless the snapshot exists AND is an exact
    {meta, findings} document whose meta carries the expected artifact/slice identity,
    registry_valid is True, cycle1_authority is exactly NOT_AUTHORIZED, run_at is a valid UTC
    timestamp, blocker_count and authorities_total are nonnegative integers, and
    condition_counts has exactly the four allowed keys, internally consistent counts, and the
    snapshot is no more than one hour old. A missing, stale, or
    malformed snapshot is never coerced into a healthy zero-blocker state.
    """
    default = _state_authorities_default()
    try:
        if not _STATE_AUTHORITY_SNAPSHOT.exists() or _STATE_AUTHORITY_SNAPSHOT.is_symlink():
            return default
        doc = json.loads(_STATE_AUTHORITY_SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return default

    if not isinstance(doc, dict) or set(doc.keys()) != {"meta", "findings"}:
        return default
    if not isinstance(doc["findings"], list):
        return default
    meta = doc["meta"]
    if not isinstance(meta, dict):
        return default
    if meta.get("slice") != "C0.3" or meta.get("artifact") != "system-state-authorities":
        return default
    if meta.get("registry_valid") is not True:
        return default
    if meta.get("cycle1_authority") != "NOT_AUTHORIZED":
        return default

    run_at = meta.get("run_at")
    if not isinstance(run_at, str):
        return default
    try:
        parsed = time.strptime(run_at, "%Y-%m-%dT%H:%M:%SZ")
        age = max(0, int(time.time() - calendar.timegm(parsed)))
    except (ValueError, OverflowError, TypeError):
        return default
    if age > _STATE_AUTHORITY_MAX_AGE_SECONDS:
        return default

    blocker_count = meta.get("blocker_count")
    authorities_total = meta.get("authorities_total")
    if not _sa_nonneg_int(blocker_count) or not _sa_nonneg_int(authorities_total):
        return default

    cond_counts = meta.get("condition_counts")
    if not isinstance(cond_counts, dict) or set(cond_counts) != _SA_ALLOWED_CONDITIONS:
        return default
    for val in cond_counts.values():
        if not _sa_nonneg_int(val):
            return default
    if sum(cond_counts.values()) != authorities_total:
        return default
    minimum_blockers = cond_counts["SPLIT_BRAIN"] + cond_counts["UNKNOWN"] + cond_counts["UNOWNED"]
    if blocker_count < minimum_blockers:
        return default

    return {
        "available": True,
        "last_check": run_at,
        "age_seconds": age,
        "blocker_count": blocker_count,
        "authorities_total": authorities_total,
        "condition_counts": cond_counts,
        "cycle1_authority": "NOT_AUTHORIZED",
        "registry_valid": True,
        "source": default["source"],
        "rebuild": default["rebuild"],
    }


@router.get("/audit/operator/summary")
async def get_operator_audit_summary(limit: int = 500):
    return audit_log.summary(limit=limit)


@router.get("/audit/operator/events")
async def get_operator_audit_events(
    limit: int = 100,
    path_prefix: str = "",
    method: str = "",
    status_code: int | None = None,
    category: str = "",
    contains: str = "",
):
    return {
        "path": str(audit_log.path()),
        "filters": {
            "path_prefix": path_prefix,
            "method": method,
            "status_code": status_code,
            "category": category,
            "contains": contains,
        },
        "events": audit_log.query_events(
            limit=limit,
            path_prefix=path_prefix,
            method=method,
            status_code=status_code,
            category=category,
            contains=contains,
        ),
    }


@router.get("/audit/operator/integrity")
async def get_operator_audit_integrity(limit: int = 500):
    status = audit_log.integrity_status(limit=limit)
    # C0.3: project the state-authority checker's last-check/age/blocker-count onto the
    # existing audit-integrity card (read-only; no new route or runtime authority).
    if isinstance(status, dict):
        status["state_authorities"] = _state_authorities_projection()
    return status
