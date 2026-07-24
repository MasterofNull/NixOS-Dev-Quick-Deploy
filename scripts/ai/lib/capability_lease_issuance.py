"""Shadow admission→issuance policy — Foundation C1 (SHADOW / LOG-ONLY).

Consumes the existing `aq-capability-intake` admission verdict
(`audit_candidate()` result) and the candidate registry entry as pure DATA
and computes the CapabilityLease that WOULD be issued (or the denial that
would apply) if a lease-issuing gate existed. This module changes NO
admission verdict, blocks nothing, calls nothing, and mutates neither of its
inputs — the pre-existing `aq-capability-intake` audit + keystone
`zero_trust` protections remain the sole authoritative gate. See
`.agents/plans/aqos-foundation-c/C1-IMPLEMENTATION-SPEC.md` (authoritative)
for the policy this file implements.

Builds on the Foundation C0 `capability_lease` primitive (sign/verify/
resolve_key) — this module never re-implements signing.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import capability_lease as cl  # noqa: E402


# --------------------------------------------------------------------------
# Constants — admission -> lease policy (spec table, C1 §"Admission -> lease
# policy")
# --------------------------------------------------------------------------

# admission -> (would_issue, trust_tier, zero_trust_behavior, deny_reason)
_ADMISSION_POLICY: dict[str, tuple[bool, Optional[int], Optional[str], Optional[str]]] = {
    "low-risk": (True, 3, "none", None),
    "accepted-with-mitigations": (True, 2, "none", None),
    "review-recommended": (True, 1, "strip", None),
    "needs-review": (False, None, None, "needs-review"),
    "blocked": (False, None, None, "blocked"),
}

# Conservative override: any of these risk flags force zero_trust_behavior
# to "strip" regardless of the tier the admission alone would grant.
_FORCE_STRIP_RISK_FLAGS = {"secret-or-token-required"}

# `permissions.writes` values that indicate report/output-only writes — NOT
# treated as write-capable for the purpose of the "write" resource grant.
_REPORT_ONLY_WRITE_VALUES = {"reports-only", "report-output-only", "knowledge-graph-output", False, "false", None}

SHADOW_SOURCE = "capability-intake-shadow"
SHADOW_LEASE_TTL = timedelta(hours=1)

_REPO_ROOT = Path(_LIB).resolve().parents[2]
DEFAULT_SHADOW_LOG_PATH = _REPO_ROOT / ".agent" / "collaboration" / "capability-lease-shadow.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_write_capable(writes: Any) -> bool:
    """True iff `permissions.writes` grants real (non-report-only) writes."""
    if not writes:
        return False
    if writes in _REPORT_ONLY_WRITE_VALUES:
        return False
    return True


def _build_permissions(candidate: dict[str, Any]) -> dict[str, Any]:
    tool_allowlist = candidate.get("tool_allowlist") or []
    permissions = candidate.get("permissions") or {}
    network = permissions.get("network")
    writes = permissions.get("writes")

    resources: list[str] = []
    if network:
        resources.append("network")
    if _is_write_capable(writes):
        resources.append("write")

    return {
        "actions": list(tool_allowlist),
        "resources": resources,
        "constraints": {"network": network, "writes": writes},
    }


def shadow_issue(
    audit_result: dict[str, Any],
    candidate: dict[str, Any],
    key: Optional[bytes] = None,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Pure policy: map an admission verdict to a shadow issuance record.

    Never mutates `audit_result` or `candidate`. Never raises on
    well-formed-looking inputs (unknown/missing admission values fail
    closed as a would-deny, matching the gate's own fail-closed posture —
    they never fall through to an issued lease).

    Returns `{ts, candidate_id, admission, would_issue, lease, deny_reason,
    risk_flags, dev_key}` — `lease` is a signed CapabilityLease dict when
    `would_issue` is True, else `None`. `dev_key` is True when the C0 DEV
    signing key was used (or would have been used) — resolved via
    `capability_lease.resolve_key()` when the caller passed no explicit
    `key`, or by direct comparison against `DEV_SIGNING_KEY` when the
    caller did. A DEV-signed shadow lease must never be mistaken for a
    trust-rooted one (see `capability_lease.DEV_KEY_BANNER`) — the CLI
    surfaces this field as a stderr banner.
    """
    admission = audit_result.get("admission")
    risk_flags = list(audit_result.get("risk_flags") or [])
    candidate_id = audit_result.get("id") or candidate.get("id")

    if key is not None:
        signing_key = key
        is_dev = key == cl.DEV_SIGNING_KEY
    else:
        signing_key, is_dev = cl.resolve_key()

    moment = now or _now()
    ts = _iso(moment)

    policy = _ADMISSION_POLICY.get(admission)
    if policy is None:
        # Unknown/malformed admission value — fail closed, never issue.
        record = {
            "ts": ts,
            "candidate_id": candidate_id,
            "admission": admission,
            "would_issue": False,
            "lease": None,
            "deny_reason": f"unknown-admission:{admission!r}",
            "risk_flags": risk_flags,
            "dev_key": is_dev,
        }
        return record

    would_issue, trust_tier, zero_trust_behavior, deny_reason = policy

    if not would_issue:
        return {
            "ts": ts,
            "candidate_id": candidate_id,
            "admission": admission,
            "would_issue": False,
            "lease": None,
            "deny_reason": deny_reason,
            "risk_flags": risk_flags,
            "dev_key": is_dev,
        }

    if _FORCE_STRIP_RISK_FLAGS & set(risk_flags):
        zero_trust_behavior = "strip"

    issued_at = moment
    expires_at = moment + SHADOW_LEASE_TTL

    lease_dict: dict[str, Any] = {
        "lease_id": f"shadow::{candidate_id}::{ts}",
        "version": 1,
        "source": SHADOW_SOURCE,
        "owner": SHADOW_SOURCE,
        "issued_to": f"candidate:{candidate_id}",
        "issued_at": _iso(issued_at),
        "expires_at": _iso(expires_at),
        "permissions": _build_permissions(candidate),
        "input_schema": {},
        "output_schema": {},
        "trust_tier": trust_tier,
        "zero_trust_behavior": zero_trust_behavior,
        "cost_class": "shadow",
        "parent_lease_id": None,
        "revocation_epoch": 0,
        "signature": "",
    }
    lease_dict["signature"] = cl.sign(lease_dict, signing_key)

    return {
        "ts": ts,
        "candidate_id": candidate_id,
        "admission": admission,
        "would_issue": True,
        "lease": lease_dict,
        "deny_reason": None,
        "risk_flags": risk_flags,
        "dev_key": is_dev,
    }


def append_shadow_log(record: dict[str, Any], path: Any) -> None:
    """Atomic-append one JSON line to a JSONL log at `path`.

    Fail-open: this is observability, not a gate — a bad/unwritable path
    (missing parent dir, read-only filesystem, permission error) must
    never raise into the caller. Uses a single O_APPEND write so
    concurrent appenders never interleave a partial line (standard POSIX
    append-mode atomicity for a single write() call).
    """
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        fd = os.open(str(target), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        # Fail-open by design — logging must never block or crash the
        # shadow pass. See module docstring / spec §CLI.
        pass
