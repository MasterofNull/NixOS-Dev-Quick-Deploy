"""CapabilityLease enforcement gate — Foundation C2 (flag-gated, deny-closed).

Pure, standalone module: no import of `switchboard.py` (it is imported BY
switchboard, lazily, only when `CAPABILITY_LEASE_ENFORCEMENT` is on — see
`.agents/plans/aqos-foundation-c/C2-DESIGN-AND-AUTHORIZATION.md` +
`C2-AMENDMENT-BUILTIN-TOOLS.md`, the frozen spec this file implements).

`enforce()` is the single entry point. It decides, for a set of requested
tool names, which are admitted for execution this call. A tool is admitted
iff EITHER:
  1. a valid **candidate** lease (external capability, C1 shadow-issuance
     shape) verifies and lists the tool in `permissions.actions`, OR
  2. the tool is in the first-party manifest (`config/first-party-tools.json`,
     sourced from `_TOOL_BUNDLES`) AND a verified **first-party** lease
     (issued from that manifest by this module) admits it.

Both paths go through the same `capability_lease.verify()` — first-party is
a lease SOURCE, never a bypass. Deny-closed: a tool in neither path is
dropped, never executed.

Fail-safe posture (see module docstring sections below for each):
  - DEV-key (`is_dev=True` from `key_resolver()`) => authority-unavailable
    S4 degrade: admit only `SAFE_READ_ALLOWLIST`, verify nothing under the
    DEV key (not even a first-party lease genuinely signed with it).
  - Unresolvable/unparseable epoch source => the same S4 degrade (never
    `current_epoch=None` skip of the staleness check).
  - `zero_trust_behavior: "strip"` on the request context drops any
    admitting tool whose bound risk classification (read from the VERIFIED
    lease, never the on-disk manifest) is write/network/exec-capable.
  - Zero-trust posture is MONOTONIC: the effective strip decision for a
    given admitting lease is (inherited request-context strip) OR (that
    lease's OWN signed `zero_trust_behavior`). A caller can never weaken a
    signed "strip" by passing "none"/`False`/omitting the key on the
    request context — only a genuinely-signed "none" lease under a "none"
    request contributes "none". Malformed/unknown `zero_trust_behavior`
    values (anything not exactly the string "none") fail safe toward
    "strip"; `None`/`False`/missing = no inherited policy ("none"
    contribution, never an override of a signed strip).
  - First-party admission additionally cross-checks the verified lease's
    OWN signed bound security metadata (actions/resources/constraints/risk
    flags/trust_tier/zero_trust_behavior) against the CURRENTLY validated
    manifest entry for that tool. The manifest is a tamper/drift tripwire
    only — it can DENY on divergence, it never supplies or overrides the
    risk decision, which always comes from the signed lease.
  - First-party leases are issued ONCE per process and cached
    (`issue_first_party_leases`) — an epoch bump makes them go stale
    (dropped) but this module NEVER reissues them automatically; only an
    explicit `reset_first_party_lease_cache()` call (a deliberate operator
    act, e.g. at startup) allows the next `issue_first_party_leases` call to
    mint fresh ones. Auto-reissue-on-bump would defeat revocation
    (C2-AMENDMENT codex-1) and is forbidden.
  - The first-party manifest must be in EXACT set equality with the caller-
    supplied live bundle tool set (`request_ctx["bundle_tools"]`) or the
    entire first-party path is treated as unusable this call (candidate
    leases are unaffected) — codex-2.
  - ANY exception anywhere in `enforce()` is caught at the outer boundary
    and turned into a total deny for the requested tools — this module must
    never raise into the switchboard tool-calling loop.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.abspath(os.path.join(_HERE, "..", "..", "scripts", "ai", "lib"))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import capability_lease as cl  # noqa: E402


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

_REPO_ROOT = Path(_HERE).resolve().parents[1]
DEFAULT_MANIFEST_PATH = _REPO_ROOT / "config" / "first-party-tools.json"
DEFAULT_EPOCH_PATH = _REPO_ROOT / "config" / "capability-lease-epoch"
ENV_EPOCH = "AQ_LEASE_POLICY_EPOCH"

FIRST_PARTY_SOURCE = "first-party-manifest"
FIRST_PARTY_LEASE_TTL = timedelta(hours=24)

DECISION_ADMIT = "admit"
DECISION_DENY = "deny"

# Fixed, hardcoded safe-read allowlist for the S4 authority-unavailable
# degrade (DEV-key or unresolvable-epoch). Deliberately independent of the
# on-disk manifest/lease risk classification — in a degrade posture we do
# not trust either as an admission input, only this fixed set of tools that
# are read-only by construction (non-write, non-network, non-exec).
SAFE_READ_ALLOWLIST: frozenset[str] = frozenset({
    "lease_tools",
    "git_status",
    "git_diff",
    "search_files",
    "read_file",
    "list_files",
    "check_service",
    "get_system_info",
    "get_hint",
    "query_context",
    "harness_health",
    "get_working_memory",
    "get_prsi_pending",
    "query_aidb",
    "mesh_discovery",
    "recommend_agent_for_task",
    "collective_memory_search",
    "get_screen_size",
    "screenshot",
})

_REQUIRED_MANIFEST_ENTRY_FIELDS = (
    "tool",
    "actions",
    "resources",
    "constraints",
    "trust_tier",
    "zero_trust_behavior",
    "write_capable",
    "network_capable",
    "exec_capable",
)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _decision(
    tool: str,
    decision: str,
    *,
    source: Optional[str] = None,
    reason: str = "",
    degraded: bool = False,
    stripped: bool = False,
    lease_id: Optional[str] = None,
    ts: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "ts": ts or _iso(datetime.now(timezone.utc)),
        "tool": tool,
        "decision": decision,
        "source": source,
        "reason": reason,
        "degraded": bool(degraded),
        "zero_trust_stripped": bool(stripped),
        "lease_id": lease_id,
    }


# --------------------------------------------------------------------------
# Epoch resolution (S-a) — never returns a value that would let the caller
# skip the staleness check; returns None on ANY unresolvable/malformed input
# so `enforce()` degrades instead of treating epoch as absent.
# --------------------------------------------------------------------------


def resolve_current_epoch(epoch_source: Any = None) -> Optional[int]:
    """Resolve the current policy epoch. Returns None iff unresolvable.

    `epoch_source` may be: None (resolve from `AQ_LEASE_POLICY_EPOCH` env,
    else the default epoch file, else 0), an int (used directly), a
    zero-arg callable returning an int, or a path (str/Path) to a
    single-int file. Never raises.
    """
    try:
        if epoch_source is None:
            env_val = os.environ.get(ENV_EPOCH)
            if env_val is not None:
                stripped = env_val.strip()
                return int(stripped) if stripped else None
            if DEFAULT_EPOCH_PATH.is_file():
                text = DEFAULT_EPOCH_PATH.read_text(encoding="utf-8").strip()
                return int(text) if text else None
            return 0
        if isinstance(epoch_source, bool):
            return None
        if isinstance(epoch_source, int):
            return epoch_source
        if callable(epoch_source):
            value = epoch_source()
            if isinstance(value, bool):
                return None
            if isinstance(value, int):
                return value
            return int(str(value).strip())
        if isinstance(epoch_source, (str, Path)):
            candidate = Path(epoch_source)
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8").strip()
                return int(text) if text else None
            text = str(epoch_source).strip()
            return int(text) if text else None
        return None
    except (ValueError, TypeError, OSError):
        return None


# --------------------------------------------------------------------------
# First-party manifest loading + bundle-equality check (codex-2)
# --------------------------------------------------------------------------

_MANIFEST_CACHE: Optional[dict[str, dict]] = None
_MANIFEST_CACHE_PATH: Optional[str] = None


def _validate_manifest_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    if any(field not in entry for field in _REQUIRED_MANIFEST_ENTRY_FIELDS):
        return False
    tool = entry.get("tool")
    if not isinstance(tool, str) or not tool:
        return False
    if not isinstance(entry.get("actions"), list):
        return False
    if not isinstance(entry.get("resources"), list):
        return False
    if not isinstance(entry.get("constraints"), dict):
        return False
    for flag in ("write_capable", "network_capable", "exec_capable"):
        if not isinstance(entry.get(flag), bool):
            return False
    if not isinstance(entry.get("trust_tier"), int) or isinstance(entry.get("trust_tier"), bool):
        return False
    return True


def _load_manifest(path: Any = None) -> Optional[dict[str, dict]]:
    """Load + schema-validate the first-party manifest. None on ANY failure
    (missing file, bad JSON, malformed entries) — fail-closed for the whole
    first-party path, never a partial/best-effort load."""
    global _MANIFEST_CACHE, _MANIFEST_CACHE_PATH
    target = Path(path) if path is not None else DEFAULT_MANIFEST_PATH
    cache_key = str(target)
    if path is None and _MANIFEST_CACHE is not None and _MANIFEST_CACHE_PATH == cache_key:
        return _MANIFEST_CACHE
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        entries = raw.get("tools") if isinstance(raw, dict) else None
        if not isinstance(entries, list) or not entries:
            return None
        out: dict[str, dict] = {}
        for entry in entries:
            if not _validate_manifest_entry(entry):
                return None
            tool = entry["tool"]
            if tool in out:
                return None  # duplicate manifest entry — malformed, fail closed
            out[tool] = entry
    except Exception:
        return None
    if path is None:
        _MANIFEST_CACHE = out
        _MANIFEST_CACHE_PATH = cache_key
    return out


def reset_manifest_cache() -> None:
    """Test/operator hook: force the next `_load_manifest()` to re-read disk."""
    global _MANIFEST_CACHE, _MANIFEST_CACHE_PATH
    _MANIFEST_CACHE = None
    _MANIFEST_CACHE_PATH = None


def check_manifest_bundle_equality(manifest_tools: Any, bundle_tools: Any) -> bool:
    """Bidirectional set equality (codex-2). A bundle tool missing from the
    manifest, OR a manifest tool absent from the bundles, both fail this
    check — the caller treats a False result as "first-party path unusable
    this call", never a partial admit."""
    try:
        return set(manifest_tools) == set(bundle_tools)
    except TypeError:
        return False


# --------------------------------------------------------------------------
# First-party lease issuance — deliberate, cached, NEVER auto-reissued
# (codex-1: an epoch bump must genuinely revoke, not self-heal).
# --------------------------------------------------------------------------

_FIRST_PARTY_LEASE_CACHE: Optional[dict[str, dict]] = None


def reset_first_party_lease_cache() -> None:
    """The ONLY way first-party leases are reissued: a deliberate act
    (process startup calls this implicitly by never having populated the
    cache yet; an operator/owner reissue-after-clearing-a-bump calls this
    explicitly). `enforce()` and `issue_first_party_leases()` never call
    this themselves — that is exactly the auto-reissue-on-bump fail-open
    codex-1 forbids."""
    global _FIRST_PARTY_LEASE_CACHE
    _FIRST_PARTY_LEASE_CACHE = None


def issue_first_party_leases(
    key: bytes,
    current_epoch: int = 0,
    manifest: Optional[dict[str, dict]] = None,
    now: Optional[datetime] = None,
) -> dict[str, dict]:
    """Issue (or return the cached) first-party leases, one per manifest
    entry. Signed with `key` (the resolver's current production key — this
    is never called while `is_dev=True`, see `enforce()`). Each lease binds
    its tool's risk classification (write/network/exec-capable, trust_tier)
    INSIDE the signed payload (`permissions.constraints.risk`) so admission
    later reads it from the verified lease, never the mutable on-disk
    manifest (codex-3)."""
    global _FIRST_PARTY_LEASE_CACHE
    if _FIRST_PARTY_LEASE_CACHE is not None:
        return _FIRST_PARTY_LEASE_CACHE
    manifest = manifest if manifest is not None else _load_manifest()
    if not manifest:
        _FIRST_PARTY_LEASE_CACHE = {}
        return _FIRST_PARTY_LEASE_CACHE

    moment = now or datetime.now(timezone.utc)
    issued_at = _iso(moment)
    expires_at = _iso(moment + FIRST_PARTY_LEASE_TTL)
    leases: dict[str, dict] = {}
    for tool, entry in manifest.items():
        actions = list(entry.get("actions") or [tool])
        lease_dict: dict[str, Any] = {
            "lease_id": f"first-party::{tool}::{issued_at}",
            "version": 1,
            "source": FIRST_PARTY_SOURCE,
            "owner": FIRST_PARTY_SOURCE,
            "issued_to": "switchboard-local-tool-executor",
            "issued_at": issued_at,
            "expires_at": expires_at,
            "permissions": {
                "actions": actions,
                "resources": list(entry.get("resources") or []),
                "constraints": {
                    **{k: v for k, v in (entry.get("constraints") or {}).items()},
                    "risk": {
                        "write_capable": bool(entry.get("write_capable", False)),
                        "network_capable": bool(entry.get("network_capable", False)),
                        "exec_capable": bool(entry.get("exec_capable", False)),
                        "trust_tier": int(entry.get("trust_tier", 0)),
                    },
                },
            },
            "input_schema": {},
            "output_schema": {},
            "trust_tier": int(entry.get("trust_tier", 0)),
            "zero_trust_behavior": str(entry.get("zero_trust_behavior", "none")),
            "cost_class": "first-party",
            "parent_lease_id": None,
            "revocation_epoch": int(current_epoch),
            "signature": "",
        }
        lease_dict["signature"] = cl.sign(lease_dict, key)
        leases[tool] = lease_dict
    _FIRST_PARTY_LEASE_CACHE = leases
    return _FIRST_PARTY_LEASE_CACHE


# --------------------------------------------------------------------------
# Risk classification — ALWAYS read from the verified lease, never the
# manifest, at admission time (codex-3).
# --------------------------------------------------------------------------


def _lease_risk(lease: dict) -> dict[str, bool]:
    constraints = ((lease.get("permissions") or {}).get("constraints")) or {}
    risk = constraints.get("risk")
    if isinstance(risk, dict):
        return {
            "write_capable": bool(risk.get("write_capable", True)),
            "network_capable": bool(risk.get("network_capable", True)),
            "exec_capable": bool(risk.get("exec_capable", True)),
        }
    # Legacy/external candidate-lease shape (C1 shadow_issue): infer from
    # its constraints.network / constraints.writes + resources grant. No
    # bound "risk" block => treat conservatively (fail closed under strip).
    resources = set((lease.get("permissions") or {}).get("resources") or [])
    return {
        "write_capable": bool(constraints.get("writes")) or "write" in resources,
        "network_capable": bool(constraints.get("network")) or "network" in resources,
        "exec_capable": bool(constraints.get("exec", False)),
    }


def _is_privileged(risk: dict[str, bool]) -> bool:
    return bool(risk.get("write_capable") or risk.get("network_capable") or risk.get("exec_capable"))


def _normalize_zero_trust(value: Any) -> str:
    """Normalize any `zero_trust_behavior` input to exactly "none" or
    "strip" — the only two valid values. `None`/`False` mean "no policy
    contribution from this source" and normalize to "none" (but per the
    monotonic-posture rule in `enforce()`, a "none" contribution from one
    source NEVER overrides a "strip" contribution from another source).
    Any other value that is not literally the string "none" (malformed,
    unknown, truthy-but-not-"strip", etc.) fails safe toward "strip" —
    an unrecognized posture must never silently collapse to the weaker
    "none"."""
    if value is None or value is False:
        return "none"
    if value == "none":
        return "none"
    return "strip"


# --------------------------------------------------------------------------
# First-party bound-metadata tamper/drift tripwire (codex-3 completion) —
# the manifest may DETECT a divergence from the signed lease and DENY, but
# never supplies the risk decision itself (that always comes from the
# verified lease's own signed payload).
# --------------------------------------------------------------------------


def _lease_bound_security_projection(lease: dict) -> dict:
    perms = lease.get("permissions") or {}
    constraints = dict(perms.get("constraints") or {})
    risk = constraints.pop("risk", None)
    risk = risk if isinstance(risk, dict) else {}
    return {
        "actions": sorted(str(a) for a in (perms.get("actions") or [])),
        "resources": sorted(str(r) for r in (perms.get("resources") or [])),
        "constraints": constraints,
        "write_capable": bool(risk.get("write_capable", False)),
        "network_capable": bool(risk.get("network_capable", False)),
        "exec_capable": bool(risk.get("exec_capable", False)),
        "trust_tier": lease.get("trust_tier"),
        "zero_trust_behavior": lease.get("zero_trust_behavior"),
    }


def _manifest_bound_security_projection(entry: dict) -> dict:
    return {
        "actions": sorted(str(a) for a in (entry.get("actions") or [])),
        "resources": sorted(str(r) for r in (entry.get("resources") or [])),
        "constraints": dict(entry.get("constraints") or {}),
        "write_capable": bool(entry.get("write_capable", False)),
        "network_capable": bool(entry.get("network_capable", False)),
        "exec_capable": bool(entry.get("exec_capable", False)),
        "trust_tier": entry.get("trust_tier"),
        "zero_trust_behavior": entry.get("zero_trust_behavior"),
    }


# --------------------------------------------------------------------------
# Degrade path (DEV-key / unresolvable-epoch authority-unavailable, S4)
# --------------------------------------------------------------------------


def _degrade(tool_names: set[str], reason: str) -> tuple[set[str], list[dict]]:
    admitted = {tool for tool in tool_names if tool in SAFE_READ_ALLOWLIST}
    decisions = [
        _decision(
            tool,
            DECISION_ADMIT if tool in admitted else DECISION_DENY,
            source="degrade",
            reason=reason,
            degraded=True,
        )
        for tool in sorted(tool_names)
    ]
    return admitted, decisions


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


def enforce(
    tool_names: set,
    request_ctx: Optional[dict] = None,
    epoch_source: Any = None,
    key_resolver: Any = None,
) -> tuple[set, list]:
    """Decide which of `tool_names` are admitted for execution this call.

    `request_ctx` (optional dict):
      - `candidate_leases`: list of raw signed CapabilityLease dicts
        (external capabilities, C1 shape) relevant to this request.
      - `zero_trust_behavior`: "none" | "strip" — the resolved, task-scoped
        request directive (upstream-resolved; this gate treats it as
        authoritative input, it does not compute it). This is the
        INHERITED contribution only: the effective per-tool posture is
        this value OR'd with the admitting lease's own signed
        `zero_trust_behavior` (monotonic — a caller can never weaken a
        signed "strip" by passing "none"/`False`/omitting this key).
      - `bundle_tools`: optional iterable of the live first-party tool
        names (e.g. the switchboard's own `_TOOL_LEASE_PRIORITY` keys) used
        for the codex-2 manifest<->bundle equality check. If omitted, the
        equality check is skipped (manifest trusted as-is) — callers that
        care about drift detection MUST pass it.

    Returns `(admitted: set[str], decisions: list[dict])`. NEVER raises —
    any internal exception is caught and turned into a total deny for
    every requested tool (S-c fail-closed wrapper).
    """
    try:
        names = {str(t) for t in (tool_names or set())}

        resolver = key_resolver if key_resolver is not None else cl.resolve_key
        try:
            key, is_dev = resolver()
        except Exception:
            key, is_dev = cl.DEV_SIGNING_KEY, True

        if is_dev:
            return _degrade(names, "dev-key-authority-unavailable")

        current_epoch = resolve_current_epoch(epoch_source)
        if current_epoch is None:
            return _degrade(names, "epoch-source-unresolvable")

        ctx = dict(request_ctx or {})
        # Inherited (request-context) contribution only — NOT the effective
        # posture. The effective per-tool posture also OR's in the
        # admitting lease's own signed zero_trust_behavior below; see the
        # monotonic-posture note in the module docstring.
        inherited_strip = _normalize_zero_trust(ctx.get("zero_trust_behavior")) == "strip"
        candidate_leases = ctx.get("candidate_leases") or []
        bundle_tools = ctx.get("bundle_tools")

        manifest = _load_manifest()
        manifest_ok = manifest is not None
        if manifest_ok and bundle_tools is not None:
            manifest_ok = check_manifest_bundle_equality(set(manifest.keys()), set(bundle_tools))

        fp_leases: dict[str, dict] = {}
        if manifest_ok and manifest is not None:
            fp_leases = issue_first_party_leases(key, current_epoch=current_epoch, manifest=manifest)

        # S-b: tool -> admitting candidate lease map, one pass over the
        # candidate leases for this request.
        candidate_admits: dict[str, dict] = {}
        for lease in candidate_leases:
            if not isinstance(lease, dict):
                continue
            try:
                verdict = cl.verify(lease, key, current_epoch=current_epoch)
            except Exception:
                continue
            if verdict != cl.VERIFY_OK:
                continue
            actions = ((lease.get("permissions") or {}).get("actions")) or []
            for action in actions:
                if action in names and action not in candidate_admits:
                    candidate_admits[action] = lease

        admitted: set[str] = set()
        decisions: list[dict] = []

        for tool in sorted(names):
            if tool in candidate_admits:
                lease = candidate_admits[tool]
                risk = _lease_risk(lease)
                lease_strip = _normalize_zero_trust(lease.get("zero_trust_behavior")) == "strip"
                effective_strip = inherited_strip or lease_strip
                if effective_strip and _is_privileged(risk):
                    decisions.append(_decision(
                        tool, DECISION_DENY, source="candidate",
                        reason="zero-trust-strip", stripped=True,
                        lease_id=lease.get("lease_id"),
                    ))
                    continue
                admitted.add(tool)
                decisions.append(_decision(
                    tool, DECISION_ADMIT, source="candidate",
                    reason="candidate-lease-verified", lease_id=lease.get("lease_id"),
                ))
                continue

            if manifest_ok and tool in fp_leases:
                lease = fp_leases[tool]
                bound_actions = ((lease.get("permissions") or {}).get("actions")) or []
                if tool not in bound_actions:
                    # Lease<->lookup-key mismatch — fail closed rather than
                    # trust a lease that doesn't actually claim this tool.
                    decisions.append(_decision(
                        tool, DECISION_DENY, source="first-party",
                        reason="lease-manifest-mismatch", lease_id=lease.get("lease_id"),
                    ))
                    continue
                try:
                    verdict = cl.verify(lease, key, current_epoch=current_epoch)
                except Exception:
                    verdict = cl.VERIFY_MALFORMED
                if verdict != cl.VERIFY_OK:
                    decisions.append(_decision(
                        tool, DECISION_DENY, source="first-party",
                        reason=f"first-party-lease-{verdict}", lease_id=lease.get("lease_id"),
                    ))
                    continue
                # codex-3 tamper/drift tripwire: the SIGNED lease's own
                # bound security metadata must still match the CURRENTLY
                # validated manifest entry. This can only DENY — the risk
                # decision itself always comes from the signed lease
                # (`_lease_risk` below), never from this comparison.
                manifest_entry = manifest.get(tool) if manifest else None
                if (
                    manifest_entry is None
                    or _lease_bound_security_projection(lease) != _manifest_bound_security_projection(manifest_entry)
                ):
                    decisions.append(_decision(
                        tool, DECISION_DENY, source="first-party",
                        reason="bound-metadata-manifest-mismatch", lease_id=lease.get("lease_id"),
                    ))
                    continue
                risk = _lease_risk(lease)
                lease_strip = _normalize_zero_trust(lease.get("zero_trust_behavior")) == "strip"
                effective_strip = inherited_strip or lease_strip
                if effective_strip and _is_privileged(risk):
                    decisions.append(_decision(
                        tool, DECISION_DENY, source="first-party",
                        reason="zero-trust-strip", stripped=True,
                        lease_id=lease.get("lease_id"),
                    ))
                    continue
                admitted.add(tool)
                decisions.append(_decision(
                    tool, DECISION_ADMIT, source="first-party",
                    reason="first-party-lease-verified", lease_id=lease.get("lease_id"),
                ))
                continue

            reason = "no-admitting-lease" if manifest_ok else "first-party-manifest-bundle-mismatch"
            decisions.append(_decision(tool, DECISION_DENY, source=None, reason=reason))

        return admitted, decisions
    except Exception as exc:  # noqa: BLE001 — S-c: total fail-closed, never raise
        try:
            names_for_report = {str(t) for t in (tool_names or set())}
        except Exception:
            names_for_report = set()
        return set(), [
            _decision(tool, DECISION_DENY, reason=f"gate-exception:{type(exc).__name__}")
            for tool in sorted(names_for_report)
        ]
