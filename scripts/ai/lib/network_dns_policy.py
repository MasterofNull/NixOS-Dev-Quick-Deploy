#!/usr/bin/env python3
"""network_dns_policy — pure resolver contract, closed enums, and telemetry sanitizer.

N0 slice of Network Profile Interoperability (PRD: .agent/PROJECT-NETWORK-PROFILE-INTEROPERABILITY-PRD.md).
Implements Draft 2020-12 closed schemas for:
  - network.dns-policy-input.v1
  - network.dns-policy-eligibility.v1
  - network.dns-policy-decision.v1
  - network.dns-policy-health.v1

Pure and side-effect free:
  - ZERO imports of subprocess, socket, requests, urllib, dbus, or NetworkManager.
  - Deterministic eligibility resolution.
  - Deterministic transition resolution.
  - Strict telemetry sanitization (scrubbing UUIDs, MACs, IPs, domains, hex tokens, and secrets).
"""
from __future__ import annotations

import enum
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Fixed Protocol Constants (Draft 2020-12 schema constants)
RECEIPT_LEASE_DURATION_S: int = 55
MAX_EFFECT_CEILING_S: int = 90

SCHEMA_INPUT: str = "network.dns-policy-input.v1"
SCHEMA_ELIGIBILITY: str = "network.dns-policy-eligibility.v1"
SCHEMA_DECISION: str = "network.dns-policy-decision.v1"
SCHEMA_HEALTH: str = "network.dns-policy-health.v1"
SCHEMA_TRUST: str = "network.dns-policy-trust.v1"
SCHEMA_RECEIPT: str = "network.dns-policy-receipt.v1"


# ==============================================================================
# Closed Enums
# ==============================================================================

class ConnectionClass(str, enum.Enum):
    TRUSTED_FULL = "trusted_full"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


class Connectivity(str, enum.Enum):
    FULL = "full"
    PORTAL = "portal"
    LIMITED = "limited"
    SITE = "site"
    NONE = "none"
    UNKNOWN = "unknown"


class DnsTopology(str, enum.Enum):
    ORDINARY = "ordinary"
    SPLIT = "split"
    UNKNOWN = "unknown"


class EvidenceAgeBucket(str, enum.Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class LinkKind(str, enum.Enum):
    WIFI = "wifi"
    OTHER = "other"


class PriorEffect(str, enum.Enum):
    NONE = "none"
    PENDING_APPLY = "pending_apply"
    ACTIVE_OVERRIDE = "active_override"
    PENDING_REVERT = "pending_revert"
    UNKNOWN = "unknown"


class ReceiptState(str, enum.Enum):
    MISSING = "missing"
    PENDING_APPLY_FRESH = "pending_apply_fresh"
    ACTIVE_FRESH = "active_fresh"
    PENDING_REVERT_FRESH = "pending_revert_fresh"
    EXPIRED = "expired"
    INVALID = "invalid"


class Event(str, enum.Enum):
    ADMIT = "admit"
    REFRESH = "refresh"
    DOWNGRADE = "downgrade"
    LINK_DOWN = "link_down"
    WATCHDOG = "watchdog"
    RESTART = "restart"


class Mode(str, enum.Enum):
    LEGACY = "legacy"
    POLICY = "policy"


class Action(str, enum.Enum):
    PRESERVE_LINK_DNS = "preserve_link_dns"
    APPLY_PUBLIC_OVERRIDE = "apply_public_override"
    REFRESH_OVERRIDE = "refresh_override"
    REVERT_OVERRIDE = "revert_override"
    LEGACY_OVERRIDE = "legacy_override"


class Reason(str, enum.Enum):
    TRUSTED_FULL = "trusted_full"
    UNTRUSTED_PROFILE = "untrusted_profile"
    PORTAL = "portal"
    LIMITED_OR_SITE = "limited_or_site"
    SPLIT_DNS = "split_dns"
    STALE_EVIDENCE = "stale_evidence"
    UNKNOWN_STATE = "unknown_state"
    NON_WIFI = "non_wifi"
    LEGACY_MODE = "legacy_mode"


class PolicyState(str, enum.Enum):
    PRESERVING = "preserving"
    TRANSITIONING = "transitioning"
    OVERRIDING = "overriding"
    REVERTED = "reverted"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class LeaseState(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class LastTransitionAge(str, enum.Enum):
    LT_30S = "lt_30s"
    LT_2M = "lt_2m"
    LT_15M = "lt_15m"
    GTE_15M = "gte_15m"
    UNKNOWN = "unknown"


class TransitionCountBucket(str, enum.Enum):
    ZERO = "0"
    ONE = "1"
    TWO_FIVE = "2_5"
    SIX_PLUS = "6_plus"
    UNKNOWN = "unknown"


class AcquisitionError(str, enum.Enum):
    NONE = "none"
    UNSAFE_INTERFACE = "unsafe_interface"
    MISSING_COMMAND = "missing_command"
    TIMEOUT = "timeout"
    NONZERO = "nonzero"
    PERMISSION = "permission"
    TOO_LARGE = "too_large"
    MALFORMED = "malformed"


# Pre-computed value sets for fast O(1) closed validation
_CONNECTION_CLASSES: Set[str] = {e.value for e in ConnectionClass}
_CONNECTIVITIES: Set[str] = {e.value for e in Connectivity}
_DNS_TOPOLOGIES: Set[str] = {e.value for e in DnsTopology}
_EVIDENCE_AGE_BUCKETS: Set[str] = {e.value for e in EvidenceAgeBucket}
_LINK_KINDS: Set[str] = {e.value for e in LinkKind}
_PRIOR_EFFECTS: Set[str] = {e.value for e in PriorEffect}
_RECEIPT_STATES: Set[str] = {e.value for e in ReceiptState}
_EVENTS: Set[str] = {e.value for e in Event}
_MODES: Set[str] = {e.value for e in Mode}
_ACTIONS: Set[str] = {e.value for e in Action}
_REASONS: Set[str] = {e.value for e in Reason}
_POLICY_STATES: Set[str] = {e.value for e in PolicyState}
_LEASE_STATES: Set[str] = {e.value for e in LeaseState}
_LAST_TRANSITION_AGES: Set[str] = {e.value for e in LastTransitionAge}
_TRANSITION_COUNT_BUCKETS: Set[str] = {e.value for e in TransitionCountBucket}
_ACQUISITION_ERRORS: Set[str] = {e.value for e in AcquisitionError}


# ==============================================================================
# Closed Schema Validators (Pure Python, Zero Dependency)
# ==============================================================================

def validate_input(data: Any) -> Tuple[bool, str]:
    """Validate network.dns-policy-input.v1 payload."""
    if not isinstance(data, dict):
        return False, "Input must be a JSON object"
    required = {
        "connection_class",
        "connectivity",
        "dns_topology",
        "evidence_age_bucket",
        "link_kind",
    }
    actual = set(data.keys())
    if actual != required:
        extra = actual - required
        missing = required - actual
        if extra:
            return False, f"Unexpected extra keys: {sorted(extra)}"
        if missing:
            return False, f"Missing required keys: {sorted(missing)}"

    if data["connection_class"] not in _CONNECTION_CLASSES:
        return False, f"Invalid connection_class: {data['connection_class']}"
    if data["connectivity"] not in _CONNECTIVITIES:
        return False, f"Invalid connectivity: {data['connectivity']}"
    if data["dns_topology"] not in _DNS_TOPOLOGIES:
        return False, f"Invalid dns_topology: {data['dns_topology']}"
    if data["evidence_age_bucket"] not in _EVIDENCE_AGE_BUCKETS:
        return False, f"Invalid evidence_age_bucket: {data['evidence_age_bucket']}"
    if data["link_kind"] not in _LINK_KINDS:
        return False, f"Invalid link_kind: {data['link_kind']}"
    return True, ""


def validate_eligibility(data: Any) -> Tuple[bool, str]:
    """Validate network.dns-policy-eligibility.v1 payload."""
    if not isinstance(data, dict):
        return False, "Eligibility must be a JSON object"
    required = {"schema_version", "eligible", "reason", "lease_duration_s"}
    actual = set(data.keys())
    if actual != required:
        extra = actual - required
        missing = required - actual
        if extra:
            return False, f"Unexpected extra keys: {sorted(extra)}"
        if missing:
            return False, f"Missing required keys: {sorted(missing)}"

    if data["schema_version"] != SCHEMA_ELIGIBILITY:
        return False, f"Invalid schema_version: {data['schema_version']}"
    if not isinstance(data["eligible"], bool):
        return False, "eligible must be a boolean"
    if data["reason"] not in _REASONS:
        return False, f"Invalid reason: {data['reason']}"
    lease = data["lease_duration_s"]
    if not isinstance(lease, int) or isinstance(lease, bool):
        return False, "lease_duration_s must be an integer"
    if lease < 0 or lease > RECEIPT_LEASE_DURATION_S:
        return False, f"lease_duration_s out of range [0, {RECEIPT_LEASE_DURATION_S}]: {lease}"
    return True, ""


def validate_telemetry_state(data: Any) -> Tuple[bool, str]:
    """Validate telemetryState sub-object."""
    if not isinstance(data, dict):
        return False, "telemetry_state must be a JSON object"
    required = {"policy_state", "connectivity", "reason", "freshness", "lease"}
    actual = set(data.keys())
    if actual != required:
        extra = actual - required
        missing = required - actual
        if extra:
            return False, f"Unexpected extra keys in telemetry_state: {sorted(extra)}"
        if missing:
            return False, f"Missing required keys in telemetry_state: {sorted(missing)}"

    if data["policy_state"] not in _POLICY_STATES:
        return False, f"Invalid policy_state: {data['policy_state']}"
    if data["connectivity"] not in _CONNECTIVITIES:
        return False, f"Invalid connectivity: {data['connectivity']}"
    if data["reason"] not in _REASONS:
        return False, f"Invalid reason: {data['reason']}"
    if data["freshness"] not in _EVIDENCE_AGE_BUCKETS:
        return False, f"Invalid freshness: {data['freshness']}"
    if data["lease"] not in _LEASE_STATES:
        return False, f"Invalid lease: {data['lease']}"
    return True, ""


def validate_decision(data: Any) -> Tuple[bool, str]:
    """Validate network.dns-policy-decision.v1 payload."""
    if not isinstance(data, dict):
        return False, "Decision must be a JSON object"
    required = {
        "schema_version",
        "action",
        "reason",
        "lease_ttl_s",
        "rollback_required",
        "telemetry_state",
    }
    actual = set(data.keys())
    if actual != required:
        extra = actual - required
        missing = required - actual
        if extra:
            return False, f"Unexpected extra keys: {sorted(extra)}"
        if missing:
            return False, f"Missing required keys: {sorted(missing)}"

    if data["schema_version"] != SCHEMA_DECISION:
        return False, f"Invalid schema_version: {data['schema_version']}"
    if data["action"] not in _ACTIONS:
        return False, f"Invalid action: {data['action']}"
    if data["reason"] not in _REASONS:
        return False, f"Invalid reason: {data['reason']}"
    ttl = data["lease_ttl_s"]
    if not isinstance(ttl, int) or isinstance(ttl, bool):
        return False, "lease_ttl_s must be an integer"
    if ttl < 0 or ttl > MAX_EFFECT_CEILING_S:
        return False, f"lease_ttl_s out of range [0, {MAX_EFFECT_CEILING_S}]: {ttl}"
    if not isinstance(data["rollback_required"], bool):
        return False, "rollback_required must be a boolean"

    ok, msg = validate_telemetry_state(data["telemetry_state"])
    if not ok:
        return False, msg
    return True, ""


def validate_health(data: Any) -> Tuple[bool, str]:
    """Validate network.dns-policy-health.v1 payload."""
    if not isinstance(data, dict):
        return False, "Health must be a JSON object"
    required = {
        "schema_version",
        "policy_state",
        "connectivity",
        "reason",
        "freshness",
        "lease",
        "last_transition_age",
        "transition_count_bucket",
        "acquisition_error",
    }
    actual = set(data.keys())
    if actual != required:
        extra = actual - required
        missing = required - actual
        if extra:
            return False, f"Unexpected extra keys: {sorted(extra)}"
        if missing:
            return False, f"Missing required keys: {sorted(missing)}"

    if data["schema_version"] != SCHEMA_HEALTH:
        return False, f"Invalid schema_version: {data['schema_version']}"
    if data["policy_state"] not in _POLICY_STATES:
        return False, f"Invalid policy_state: {data['policy_state']}"
    if data["connectivity"] not in _CONNECTIVITIES:
        return False, f"Invalid connectivity: {data['connectivity']}"
    if data["reason"] not in _REASONS:
        return False, f"Invalid reason: {data['reason']}"
    if data["freshness"] not in _EVIDENCE_AGE_BUCKETS:
        return False, f"Invalid freshness: {data['freshness']}"
    if data["lease"] not in _LEASE_STATES:
        return False, f"Invalid lease: {data['lease']}"
    if data["last_transition_age"] not in _LAST_TRANSITION_AGES:
        return False, f"Invalid last_transition_age: {data['last_transition_age']}"
    if data["transition_count_bucket"] not in _TRANSITION_COUNT_BUCKETS:
        return False, f"Invalid transition_count_bucket: {data['transition_count_bucket']}"
    if data["acquisition_error"] not in _ACQUISITION_ERRORS:
        return False, f"Invalid acquisition_error: {data['acquisition_error']}"
    return True, ""


def validate_trust(data: Any) -> Tuple[bool, str]:
    """Validate network.dns-policy-trust.v1 payload."""
    if not isinstance(data, dict):
        return False, "Trust mapping must be a JSON object"
    required = {"schema_version", "trusted_profile_uuids"}
    actual = set(data.keys())
    if actual != required:
        extra = actual - required
        missing = required - actual
        if extra:
            return False, f"Unexpected extra keys: {sorted(extra)}"
        if missing:
            return False, f"Missing required keys: {sorted(missing)}"

    if data["schema_version"] != SCHEMA_TRUST:
        return False, f"Invalid schema_version: {data['schema_version']}"

    uuids = data["trusted_profile_uuids"]
    if not isinstance(uuids, list):
        return False, "trusted_profile_uuids must be an array"

    seen = set()
    for item in uuids:
        if not isinstance(item, str) or not _RE_UUID.match(item):
            return False, f"Invalid UUID entry: {item}"
        if item in seen:
            return False, f"Duplicate UUID entry: {item}"
        seen.add(item)

    return True, ""


_RECEIPT_DOC_STATES: Set[str] = {"pending_apply", "active", "pending_revert", "inactive"}


def validate_receipt(data: Any) -> Tuple[bool, str]:
    """Validate network.dns-policy-receipt.v1 payload."""
    if not isinstance(data, dict):
        return False, "Receipt must be a JSON object"
    required = {
        "schema_version",
        "receipt_state",
        "boot_id",
        "interface",
        "action",
        "reason",
        "lease_expiry_epoch_s",
        "updated_epoch_s",
        "revision",
    }
    actual = set(data.keys())
    if actual != required:
        extra = actual - required
        missing = required - actual
        if extra:
            return False, f"Unexpected extra keys: {sorted(extra)}"
        if missing:
            return False, f"Missing required keys: {sorted(missing)}"

    if data["schema_version"] != SCHEMA_RECEIPT:
        return False, f"Invalid schema_version: {data['schema_version']}"
    if data["receipt_state"] not in _RECEIPT_DOC_STATES:
        return False, f"Invalid receipt_state: {data['receipt_state']}"
    if not isinstance(data["boot_id"], str) or not data["boot_id"]:
        return False, "Invalid boot_id"
    if not is_valid_interface(data["interface"]):
        return False, f"Invalid interface token: {data['interface']}"
    if data["action"] not in _ACTIONS:
        return False, f"Invalid action: {data['action']}"
    if data["reason"] not in _REASONS:
        return False, f"Invalid reason: {data['reason']}"
    if not isinstance(data["lease_expiry_epoch_s"], int) or data["lease_expiry_epoch_s"] < 0:
        return False, "Invalid lease_expiry_epoch_s"
    if not isinstance(data["updated_epoch_s"], int) or data["updated_epoch_s"] < 0:
        return False, "Invalid updated_epoch_s"
    if not isinstance(data["revision"], int) or data["revision"] < 0:
        return False, "Invalid revision"

    return True, ""


# ==============================================================================
# Pure Eligibility Resolver
# ==============================================================================

def resolve_eligibility(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Pure, deterministic eligibility resolver.

    Accepts network.dns-policy-input.v1.
    Returns network.dns-policy-eligibility.v1.

    The sole permit tuple:
      link_kind == 'wifi' AND
      connection_class == 'trusted_full' AND
      connectivity == 'full' AND
      dns_topology == 'ordinary' AND
      evidence_age_bucket == 'fresh'
      -> eligible=True, reason='trusted_full', lease_duration_s=55

    All other combinations fail closed to eligible=False, lease_duration_s=0.
    """
    valid, _ = validate_input(input_data)
    if not valid:
        # Fails closed on any malformed or extra-keyed input
        return {
            "schema_version": SCHEMA_ELIGIBILITY,
            "eligible": False,
            "reason": Reason.UNKNOWN_STATE.value,
            "lease_duration_s": 0,
        }

    link_kind = input_data["link_kind"]
    conn_class = input_data["connection_class"]
    connectivity = input_data["connectivity"]
    dns_topo = input_data["dns_topology"]
    evidence_age = input_data["evidence_age_bucket"]

    # Permit check
    if (
        link_kind == LinkKind.WIFI.value
        and conn_class == ConnectionClass.TRUSTED_FULL.value
        and connectivity == Connectivity.FULL.value
        and dns_topo == DnsTopology.ORDINARY.value
        and evidence_age == EvidenceAgeBucket.FRESH.value
    ):
        return {
            "schema_version": SCHEMA_ELIGIBILITY,
            "eligible": True,
            "reason": Reason.TRUSTED_FULL.value,
            "lease_duration_s": RECEIPT_LEASE_DURATION_S,
        }

    # Deterministic deny reason classification
    if link_kind != LinkKind.WIFI.value:
        reason = Reason.NON_WIFI.value
    elif conn_class == ConnectionClass.UNTRUSTED.value:
        reason = Reason.UNTRUSTED_PROFILE.value
    elif conn_class == ConnectionClass.UNKNOWN.value:
        reason = Reason.UNKNOWN_STATE.value
    elif connectivity == Connectivity.PORTAL.value:
        reason = Reason.PORTAL.value
    elif connectivity in (Connectivity.LIMITED.value, Connectivity.SITE.value, Connectivity.NONE.value):
        reason = Reason.LIMITED_OR_SITE.value
    elif connectivity == Connectivity.UNKNOWN.value:
        reason = Reason.UNKNOWN_STATE.value
    elif dns_topo == DnsTopology.SPLIT.value:
        reason = Reason.SPLIT_DNS.value
    elif dns_topo == DnsTopology.UNKNOWN.value:
        reason = Reason.UNKNOWN_STATE.value
    elif evidence_age == EvidenceAgeBucket.STALE.value:
        reason = Reason.STALE_EVIDENCE.value
    else:
        reason = Reason.UNKNOWN_STATE.value

    return {
        "schema_version": SCHEMA_ELIGIBILITY,
        "eligible": False,
        "reason": reason,
        "lease_duration_s": 0,
    }


# ==============================================================================
# Pure Transition Resolver
# ==============================================================================

def resolve_transition(
    eligibility: Dict[str, Any],
    executor_state: Dict[str, Any],
    input_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pure, deterministic effect transition resolver.

    Accepts eligibility (network.dns-policy-eligibility.v1) and executor_state:
      - prior_effect: none, pending_apply, active_override, pending_revert, unknown
      - receipt_state: missing, pending_apply_fresh, active_fresh, pending_revert_fresh, expired, invalid
      - event: admit, refresh, downgrade, link_down, watchdog, restart
      - mode: legacy, policy

    Optionally accepts input_data for exact connectivity & freshness projection.
    Returns network.dns-policy-decision.v1.
    """
    # Validate eligibility format
    valid_elig, _ = validate_eligibility(eligibility)
    if not valid_elig:
        eligibility = {
            "schema_version": SCHEMA_ELIGIBILITY,
            "eligible": False,
            "reason": Reason.UNKNOWN_STATE.value,
            "lease_duration_s": 0,
        }

    # Validate executor_state format
    if not isinstance(executor_state, dict):
        return {
            "schema_version": SCHEMA_DECISION,
            "action": Action.REVERT_OVERRIDE.value,
            "reason": Reason.UNKNOWN_STATE.value,
            "lease_ttl_s": 0,
            "rollback_required": True,
            "telemetry_state": {
                "policy_state": PolicyState.DEGRADED.value,
                "connectivity": Connectivity.UNKNOWN.value,
                "reason": Reason.UNKNOWN_STATE.value,
                "freshness": EvidenceAgeBucket.UNKNOWN.value,
                "lease": LeaseState.UNKNOWN.value,
            },
        }

    prior_effect = executor_state.get("prior_effect")
    receipt_state = executor_state.get("receipt_state")
    event = executor_state.get("event")
    mode = executor_state.get("mode")

    if (
        prior_effect not in _PRIOR_EFFECTS
        or receipt_state not in _RECEIPT_STATES
        or event not in _EVENTS
        or mode not in _MODES
    ):
        return {
            "schema_version": SCHEMA_DECISION,
            "action": Action.REVERT_OVERRIDE.value,
            "reason": Reason.UNKNOWN_STATE.value,
            "lease_ttl_s": 0,
            "rollback_required": True,
            "telemetry_state": {
                "policy_state": PolicyState.DEGRADED.value,
                "connectivity": Connectivity.UNKNOWN.value,
                "reason": Reason.UNKNOWN_STATE.value,
                "freshness": EvidenceAgeBucket.UNKNOWN.value,
                "lease": LeaseState.UNKNOWN.value,
            },
        }

    # Determine connectivity and freshness for telemetry projection
    if isinstance(input_data, dict) and input_data.get("connectivity") in _CONNECTIVITIES:
        conn_val = input_data["connectivity"]
    elif eligibility["eligible"]:
        conn_val = Connectivity.FULL.value
    elif eligibility["reason"] == Reason.PORTAL.value:
        conn_val = Connectivity.PORTAL.value
    elif eligibility["reason"] == Reason.LIMITED_OR_SITE.value:
        conn_val = Connectivity.LIMITED.value
    else:
        conn_val = Connectivity.UNKNOWN.value

    if isinstance(input_data, dict) and input_data.get("evidence_age_bucket") in _EVIDENCE_AGE_BUCKETS:
        fresh_val = input_data["evidence_age_bucket"]
    elif eligibility["eligible"]:
        fresh_val = EvidenceAgeBucket.FRESH.value
    elif eligibility["reason"] == Reason.STALE_EVIDENCE.value:
        fresh_val = EvidenceAgeBucket.STALE.value
    else:
        fresh_val = EvidenceAgeBucket.UNKNOWN.value

    # 1. Mode = legacy: exact current behavior
    if mode == Mode.LEGACY.value:
        if event in (Event.ADMIT.value, Event.REFRESH.value):
            return {
                "schema_version": SCHEMA_DECISION,
                "action": Action.LEGACY_OVERRIDE.value,
                "reason": Reason.LEGACY_MODE.value,
                "lease_ttl_s": 0,
                "rollback_required": False,
                "telemetry_state": {
                    "policy_state": PolicyState.OVERRIDING.value,
                    "connectivity": conn_val,
                    "reason": Reason.LEGACY_MODE.value,
                    "freshness": EvidenceAgeBucket.UNKNOWN.value,
                    "lease": LeaseState.NOT_APPLICABLE.value,
                },
            }
        else:
            # Downgrade, link-down, watchdog in legacy
            if prior_effect == PriorEffect.NONE.value and receipt_state == ReceiptState.MISSING.value:
                action = Action.PRESERVE_LINK_DNS.value
                rollback = False
                pstate = PolicyState.PRESERVING.value
            else:
                action = Action.REVERT_OVERRIDE.value
                rollback = True
                pstate = PolicyState.REVERTED.value
            return {
                "schema_version": SCHEMA_DECISION,
                "action": action,
                "reason": Reason.LEGACY_MODE.value,
                "lease_ttl_s": 0,
                "rollback_required": rollback,
                "telemetry_state": {
                    "policy_state": pstate,
                    "connectivity": conn_val,
                    "reason": Reason.LEGACY_MODE.value,
                    "freshness": EvidenceAgeBucket.UNKNOWN.value,
                    "lease": LeaseState.NOT_APPLICABLE.value,
                },
            }

    # 2. Mode = policy: bounded, observable, reversible policy
    eligible = eligibility["eligible"]
    elig_reason = eligibility["reason"]

    # Condition: Invariant revert events (downgrade, link_down, watchdog)
    if event in (Event.DOWNGRADE.value, Event.LINK_DOWN.value, Event.WATCHDOG.value):
        if prior_effect == PriorEffect.NONE.value and receipt_state == ReceiptState.MISSING.value:
            return {
                "schema_version": SCHEMA_DECISION,
                "action": Action.PRESERVE_LINK_DNS.value,
                "reason": elig_reason,
                "lease_ttl_s": 0,
                "rollback_required": False,
                "telemetry_state": {
                    "policy_state": PolicyState.PRESERVING.value,
                    "connectivity": conn_val,
                    "reason": elig_reason,
                    "freshness": fresh_val,
                    "lease": LeaseState.NOT_APPLICABLE.value,
                },
            }
        else:
            lease_state_val = (
                LeaseState.EXPIRED.value
                if (event == Event.WATCHDOG.value or receipt_state == ReceiptState.EXPIRED.value)
                else LeaseState.UNKNOWN.value
            )
            return {
                "schema_version": SCHEMA_DECISION,
                "action": Action.REVERT_OVERRIDE.value,
                "reason": elig_reason,
                "lease_ttl_s": 0,
                "rollback_required": True,
                "telemetry_state": {
                    "policy_state": PolicyState.REVERTED.value,
                    "connectivity": conn_val,
                    "reason": elig_reason,
                    "freshness": fresh_val,
                    "lease": lease_state_val,
                },
            }

    # Condition: Restart event
    if event == Event.RESTART.value:
        if (
            eligible
            and prior_effect == PriorEffect.ACTIVE_OVERRIDE.value
            and receipt_state == ReceiptState.ACTIVE_FRESH.value
        ):
            # Valid same-boot receipt rehydration
            return {
                "schema_version": SCHEMA_DECISION,
                "action": Action.REFRESH_OVERRIDE.value,
                "reason": Reason.TRUSTED_FULL.value,
                "lease_ttl_s": RECEIPT_LEASE_DURATION_S,
                "rollback_required": False,
                "telemetry_state": {
                    "policy_state": PolicyState.OVERRIDING.value,
                    "connectivity": Connectivity.FULL.value,
                    "reason": Reason.TRUSTED_FULL.value,
                    "freshness": EvidenceAgeBucket.FRESH.value,
                    "lease": LeaseState.ACTIVE.value,
                },
            }
        else:
            # Missing, cross-boot, invalid, expired, or ambiguous receipts cause revert
            if prior_effect == PriorEffect.NONE.value and receipt_state == ReceiptState.MISSING.value:
                return {
                    "schema_version": SCHEMA_DECISION,
                    "action": Action.PRESERVE_LINK_DNS.value,
                    "reason": elig_reason,
                    "lease_ttl_s": 0,
                    "rollback_required": False,
                    "telemetry_state": {
                        "policy_state": PolicyState.PRESERVING.value,
                        "connectivity": conn_val,
                        "reason": elig_reason,
                        "freshness": fresh_val,
                        "lease": LeaseState.NOT_APPLICABLE.value,
                    },
                }
            else:
                return {
                    "schema_version": SCHEMA_DECISION,
                    "action": Action.REVERT_OVERRIDE.value,
                    "reason": elig_reason,
                    "lease_ttl_s": 0,
                    "rollback_required": True,
                    "telemetry_state": {
                        "policy_state": PolicyState.REVERTED.value,
                        "connectivity": conn_val,
                        "reason": elig_reason,
                        "freshness": fresh_val,
                        "lease": LeaseState.EXPIRED.value if receipt_state == ReceiptState.EXPIRED.value else LeaseState.UNKNOWN.value,
                    },
                }

    # Condition: Admit or Refresh events
    if event in (Event.ADMIT.value, Event.REFRESH.value):
        if eligible:
            # Clean prior state -> apply public override
            if prior_effect == PriorEffect.NONE.value and receipt_state == ReceiptState.MISSING.value:
                return {
                    "schema_version": SCHEMA_DECISION,
                    "action": Action.APPLY_PUBLIC_OVERRIDE.value,
                    "reason": Reason.TRUSTED_FULL.value,
                    "lease_ttl_s": RECEIPT_LEASE_DURATION_S,
                    "rollback_required": True,
                    "telemetry_state": {
                        "policy_state": PolicyState.OVERRIDING.value,
                        "connectivity": Connectivity.FULL.value,
                        "reason": Reason.TRUSTED_FULL.value,
                        "freshness": EvidenceAgeBucket.FRESH.value,
                        "lease": LeaseState.ACTIVE.value,
                    },
                }
            # Active fresh receipt -> idempotent refresh
            elif (
                prior_effect == PriorEffect.ACTIVE_OVERRIDE.value
                and receipt_state == ReceiptState.ACTIVE_FRESH.value
            ):
                return {
                    "schema_version": SCHEMA_DECISION,
                    "action": Action.REFRESH_OVERRIDE.value,
                    "reason": Reason.TRUSTED_FULL.value,
                    "lease_ttl_s": RECEIPT_LEASE_DURATION_S,
                    "rollback_required": False,
                    "telemetry_state": {
                        "policy_state": PolicyState.OVERRIDING.value,
                        "connectivity": Connectivity.FULL.value,
                        "reason": Reason.TRUSTED_FULL.value,
                        "freshness": EvidenceAgeBucket.FRESH.value,
                        "lease": LeaseState.ACTIVE.value,
                    },
                }
            # Any unclean / uncertain / expired / pending state -> revert first
            else:
                return {
                    "schema_version": SCHEMA_DECISION,
                    "action": Action.REVERT_OVERRIDE.value,
                    "reason": Reason.UNKNOWN_STATE.value if receipt_state != ReceiptState.EXPIRED.value else Reason.STALE_EVIDENCE.value,
                    "lease_ttl_s": 0,
                    "rollback_required": True,
                    "telemetry_state": {
                        "policy_state": PolicyState.REVERTED.value,
                        "connectivity": conn_val,
                        "reason": Reason.UNKNOWN_STATE.value if receipt_state != ReceiptState.EXPIRED.value else Reason.STALE_EVIDENCE.value,
                        "freshness": fresh_val,
                        "lease": LeaseState.EXPIRED.value if receipt_state == ReceiptState.EXPIRED.value else LeaseState.UNKNOWN.value,
                    },
                }
        else:
            # Non-eligible input
            if prior_effect == PriorEffect.NONE.value and receipt_state == ReceiptState.MISSING.value:
                return {
                    "schema_version": SCHEMA_DECISION,
                    "action": Action.PRESERVE_LINK_DNS.value,
                    "reason": elig_reason,
                    "lease_ttl_s": 0,
                    "rollback_required": False,
                    "telemetry_state": {
                        "policy_state": PolicyState.PRESERVING.value,
                        "connectivity": conn_val,
                        "reason": elig_reason,
                        "freshness": fresh_val,
                        "lease": LeaseState.NOT_APPLICABLE.value,
                    },
                }
            else:
                return {
                    "schema_version": SCHEMA_DECISION,
                    "action": Action.REVERT_OVERRIDE.value,
                    "reason": elig_reason,
                    "lease_ttl_s": 0,
                    "rollback_required": True,
                    "telemetry_state": {
                        "policy_state": PolicyState.REVERTED.value,
                        "connectivity": conn_val,
                        "reason": elig_reason,
                        "freshness": fresh_val,
                        "lease": LeaseState.EXPIRED.value if receipt_state == ReceiptState.EXPIRED.value else LeaseState.UNKNOWN.value,
                    },
                }

    # Catch-all safe fallback
    return {
        "schema_version": SCHEMA_DECISION,
        "action": Action.PRESERVE_LINK_DNS.value,
        "reason": Reason.UNKNOWN_STATE.value,
        "lease_ttl_s": 0,
        "rollback_required": False,
        "telemetry_state": {
            "policy_state": PolicyState.DEGRADED.value,
            "connectivity": Connectivity.UNKNOWN.value,
            "reason": Reason.UNKNOWN_STATE.value,
            "freshness": EvidenceAgeBucket.UNKNOWN.value,
            "lease": LeaseState.UNKNOWN.value,
        },
    }


# ==============================================================================
# Strict Telemetry Sanitizer
# ==============================================================================

# Regex patterns for sensitive tokens and network identifiers
_RE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_RE_MAC = re.compile(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b")
_RE_IPV4 = re.compile(
    r"\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b"
)
_RE_IPV6 = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b::(?:ffff:)?(?:\d{1,3}\.){3}\d{1,3}\b|\b(?:[0-9a-fA-F]{1,4}:){1,7}:[0-9a-fA-F]{1,4}\b"
)
_RE_HEX_SECRET = re.compile(r"\b[0-9a-fA-F]{16,64}\b")
_RE_DOMAIN = re.compile(
    r"\b(?!(?:network\.dns-policy-[a-z0-9-]+\.v1\b))(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|edu|gov|io|local|lan|internal|home|corp|arpa|[a-z]{2,})\b",
    re.IGNORECASE,
)

_SENSITIVE_KEY_EXACT: Set[str] = {
    "ssid",
    "bssid",
    "uuid",
    "con_uuid",
    "password",
    "secret",
    "psk",
    "token",
    "credential",
    "key",
    "passphrase",
    "auth",
    "profile_name",
    "private",
}

_SENSITIVE_KEY_SUBSTRINGS: Tuple[str, ...] = (
    "ssid",
    "bssid",
    "password",
    "secret",
    "psk",
    "token",
    "credential",
    "passphrase",
    "con_uuid",
    "api_key",
    "secret_key",
    "private_key",
    "auth_token",
)


def _sanitize_string(val: str) -> str:
    """Scrub identifiers, IPs, domains, and tokens from a string."""
    if not val:
        return val

    # Preserve schema constants verbatim
    if val in (SCHEMA_INPUT, SCHEMA_ELIGIBILITY, SCHEMA_DECISION, SCHEMA_HEALTH, SCHEMA_TRUST, SCHEMA_RECEIPT):
        return val

    # Scrub UUID
    res = _RE_UUID.sub("[REDACTED_UUID]", val)
    # Scrub MAC
    res = _RE_MAC.sub("[REDACTED_MAC]", res)
    # Scrub IPv4
    res = _RE_IPV4.sub("[REDACTED_IP]", res)
    # Scrub IPv6
    res = _RE_IPV6.sub("[REDACTED_IP]", res)
    # Scrub hex secrets / hashes
    res = _RE_HEX_SECRET.sub("[REDACTED_HEX]", res)
    # Scrub domains (while preserving schema constants)
    res = _RE_DOMAIN.sub("[REDACTED_DOMAIN]", res)
    return res


def sanitize_telemetry(payload: Any) -> Any:
    """Recursively scrub any sensitive identifiers, SSIDs, UUIDs, MACs, IPs, domains,

    and secret key values from arbitrary telemetry objects or projections.
    Pure and non-destructive to caller data.
    """
    if isinstance(payload, dict):
        sanitized_dict: Dict[str, Any] = {}
        for k, v in payload.items():
            k_str = str(k)
            k_lower = k_str.lower()
            # If the dictionary key itself suggests sensitive data, redact value entirely
            if k_lower in _SENSITIVE_KEY_EXACT or any(sub in k_lower for sub in _SENSITIVE_KEY_SUBSTRINGS):
                sanitized_dict[_sanitize_string(k_str)] = "[REDACTED]"
            else:
                sanitized_dict[_sanitize_string(k_str)] = sanitize_telemetry(v)
        return sanitized_dict
    elif isinstance(payload, list):
        return [sanitize_telemetry(item) for item in payload]
    elif isinstance(payload, tuple):
        return tuple(sanitize_telemetry(item) for item in payload)
    elif isinstance(payload, str):
        return _sanitize_string(payload)
    else:
        # Numbers, booleans, None
        return payload


# ==============================================================================
# N1 Bounded Acquisition Adapter & Durable Health Projection
# ==============================================================================

RE_IFACE_TOKEN: re.Pattern = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
MAX_COMMAND_OUTPUT_BYTES: int = 16 * 1024  # 16 KiB ceiling
COMMAND_TIMEOUT_S: float = 2.0

HEALTH_FILE_DEFAULT: Path = Path("/run/aq-network-policy/health.json")
HEALTH_LOCK_DEFAULT: Path = Path("/run/lock/aq-network-policy/health.lock")
TRUSTED_PROFILES_DEFAULT: Path = Path("/var/lib/aq-network-policy/private/trusted-profiles.json")
TRUSTED_PROFILES_LOCK_DEFAULT: Path = Path("/run/lock/aq-network-policy/trusted-profiles.lock")
OVERRIDE_LEASE_DEFAULT: Path = Path("/run/aq-network-policy/private/override-lease.json")
OVERRIDE_LEASE_LOCK_DEFAULT: Path = Path("/run/lock/aq-network-policy/override-lease.lock")
EFFECT_LOCK_DEFAULT: Path = Path("/run/lock/aq-network-policy/effect-operation.lock")

MAX_TRUST_FILE_BYTES: int = 64 * 1024  # 64 KiB ceiling
EFFECT_LOCK_TIMEOUT_S: float = 2.0
MUTATION_DEADLINE_S: float = 5.0
TOTAL_TRANSACTION_DEADLINE_S: float = 15.0
WATCHDOG_INTERVAL_S: float = 10.0
WATCHDOG_JITTER_S: float = 1.0
WATCHDOG_RETRY_INTERVAL_S: float = 0.25
WATCHDOG_MAX_RETRY_S: float = 5.0


def is_valid_interface(iface: Any) -> bool:
    """Validate interface token matching ^[A-Za-z0-9_.:-]{1,32}$."""
    if not isinstance(iface, str):
        return False
    return bool(RE_IFACE_TOKEN.match(iface))


def is_wifi_interface(iface: str, sysfs_base: Optional[Path] = None) -> bool:
    """Prove interface is Wi-Fi through local sysfs."""
    if not is_valid_interface(iface):
        return False
    base = sysfs_base or Path("/sys/class/net")
    iface_dir = base / iface
    return (iface_dir / "wireless").is_dir() or (iface_dir / "phy80211").is_dir()


def _run_bounded_command(
    argv: List[str],
    env: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[str], AcquisitionError]:
    """Execute fixed allowlisted argv with 2s timeout and 16KiB output ceiling.

    Zero shell, zero stderr/raw output exposure, closed errors.
    """
    import subprocess

    clean_env = env or {
        "LC_ALL": "C",
        "LANG": "C",
        "PATH": "/run/current-system/sw/bin:/usr/bin:/bin",
    }
    try:
        proc = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_S,
            env=clean_env,
            check=False,
        )
    except FileNotFoundError:
        return None, AcquisitionError.MISSING_COMMAND
    except PermissionError:
        return None, AcquisitionError.PERMISSION
    except subprocess.TimeoutExpired:
        return None, AcquisitionError.TIMEOUT
    except Exception:
        return None, AcquisitionError.MALFORMED

    combined_len = len(proc.stdout) + len(proc.stderr)
    if combined_len > MAX_COMMAND_OUTPUT_BYTES:
        return None, AcquisitionError.TOO_LARGE

    if proc.returncode != 0:
        return None, AcquisitionError.NONZERO

    try:
        out_str = proc.stdout.decode("utf-8", errors="replace").strip()
        return out_str, AcquisitionError.NONE
    except Exception:
        return None, AcquisitionError.MALFORMED


def acquire_facts(
    iface: str,
    sysfs_base: Optional[Path] = None,
    cmd_runner: Optional[Any] = None,
    trusted_profiles_path: Optional[Path] = None,
) -> Tuple[Dict[str, Any], AcquisitionError]:
    """Acquire N0 input facts using bounded inspection allowlist only.

    Command allowlist:
      ["nmcli", "--terse", "--fields", "CONNECTIVITY", "general"]
      ["nmcli", "--get-values", "GENERAL.CON-UUID", "device", "show", IFACE]
      ["resolvectl", "domain", IFACE]
    """
    runner = cmd_runner or _run_bounded_command

    if not is_valid_interface(iface):
        fallback = {
            "connection_class": ConnectionClass.UNKNOWN.value,
            "connectivity": Connectivity.UNKNOWN.value,
            "dns_topology": DnsTopology.UNKNOWN.value,
            "evidence_age_bucket": EvidenceAgeBucket.UNKNOWN.value,
            "link_kind": LinkKind.OTHER.value,
        }
        return fallback, AcquisitionError.UNSAFE_INTERFACE

    # 1. Sysfs Wi-Fi verification
    is_wifi = is_wifi_interface(iface, sysfs_base)
    link_kind = LinkKind.WIFI.value if is_wifi else LinkKind.OTHER.value

    # 2. NetworkManager connectivity
    out_conn, err_conn = runner(["nmcli", "--terse", "--fields", "CONNECTIVITY", "general"])
    acq_err = AcquisitionError.NONE
    if err_conn != AcquisitionError.NONE:
        connectivity = Connectivity.UNKNOWN.value
        acq_err = err_conn
    else:
        norm_conn = (out_conn or "").lower().strip()
        if norm_conn in _CONNECTIVITIES:
            connectivity = norm_conn
        else:
            connectivity = Connectivity.UNKNOWN.value
            acq_err = AcquisitionError.MALFORMED

    # 3. Connection Class (trust lookup) — UUID is consumed purely in-memory
    con_uuid_out, _ = runner(["nmcli", "--get-values", "GENERAL.CON-UUID", "device", "show", iface])
    connection_class = ConnectionClass.UNTRUSTED.value
    tpath = trusted_profiles_path or TRUSTED_PROFILES_DEFAULT
    if con_uuid_out and tpath.exists() and tpath.is_file():
        try:
            with open(tpath, "r", encoding="utf-8") as f:
                tdata = json.load(f)
            allowed_uuids = set(tdata.get("trusted_profile_uuids", []))
            if con_uuid_out.strip() in allowed_uuids:
                connection_class = ConnectionClass.TRUSTED_FULL.value
        except Exception:
            connection_class = ConnectionClass.UNKNOWN.value

    # 4. DNS Topology (read-only query)
    out_dom, err_dom = runner(["resolvectl", "domain", iface])
    if err_dom != AcquisitionError.NONE:
        dns_topology = DnsTopology.UNKNOWN.value
        if acq_err == AcquisitionError.NONE:
            acq_err = err_dom
    else:
        dom_text = out_dom or ""
        if "~" in dom_text:
            dns_topology = DnsTopology.SPLIT.value
        else:
            dns_topology = DnsTopology.ORDINARY.value

    facts = {
        "connection_class": connection_class,
        "connectivity": connectivity,
        "dns_topology": dns_topology,
        "evidence_age_bucket": EvidenceAgeBucket.FRESH.value,
        "link_kind": link_kind,
    }

    ok, _ = validate_input(facts)
    if not ok:
        fallback = {
            "connection_class": ConnectionClass.UNKNOWN.value,
            "connectivity": Connectivity.UNKNOWN.value,
            "dns_topology": DnsTopology.UNKNOWN.value,
            "evidence_age_bucket": EvidenceAgeBucket.UNKNOWN.value,
            "link_kind": LinkKind.OTHER.value,
        }
        return fallback, AcquisitionError.MALFORMED

    return facts, acq_err


def derive_health_record(
    facts: Dict[str, Any],
    acq_error: AcquisitionError = AcquisitionError.NONE,
) -> Dict[str, Any]:
    """Derive versioned network.dns-policy-health.v1 projection from input facts."""
    if acq_error in (AcquisitionError.UNSAFE_INTERFACE, AcquisitionError.MISSING_COMMAND):
        policy_state = PolicyState.UNAVAILABLE.value
    elif acq_error != AcquisitionError.NONE:
        policy_state = PolicyState.DEGRADED.value
    elif facts.get("connectivity") == Connectivity.UNKNOWN.value:
        policy_state = PolicyState.UNAVAILABLE.value
    else:
        # In passive N1 observation, DHCP/link DNS is preserved
        policy_state = PolicyState.PRESERVING.value

    elig_res = resolve_eligibility(facts)
    reason = elig_res.get("reason", Reason.UNKNOWN_STATE.value)

    record = {
        "schema_version": SCHEMA_HEALTH,
        "policy_state": policy_state,
        "connectivity": facts.get("connectivity", Connectivity.UNKNOWN.value),
        "reason": reason,
        "freshness": facts.get("evidence_age_bucket", EvidenceAgeBucket.FRESH.value),
        "lease": LeaseState.NOT_APPLICABLE.value,
        "last_transition_age": LastTransitionAge.LT_30S.value,
        "transition_count_bucket": TransitionCountBucket.ONE.value,
        "acquisition_error": acq_error.value,
    }
    return record


def fallback_unavailable_health(acq_err: AcquisitionError = AcquisitionError.NONE) -> Dict[str, Any]:
    """Return closed schema-conforming unavailable health object."""
    return {
        "schema_version": SCHEMA_HEALTH,
        "policy_state": PolicyState.UNAVAILABLE.value,
        "connectivity": Connectivity.UNKNOWN.value,
        "reason": Reason.UNKNOWN_STATE.value,
        "freshness": EvidenceAgeBucket.UNKNOWN.value,
        "lease": LeaseState.UNKNOWN.value,
        "last_transition_age": LastTransitionAge.UNKNOWN.value,
        "transition_count_bucket": TransitionCountBucket.UNKNOWN.value,
        "acquisition_error": acq_err.value,
    }


def publish_health(
    health_data: Dict[str, Any],
    health_path: Optional[Path] = None,
    lock_path: Optional[Path] = None,
) -> bool:
    """Durable atomic health projection writer.

    Adheres to PRD Section 4.5/5 contract:
      - Closed schema validation before write
      - Stable lock (0600)
      - Root-owned 0700 dir (if privileged)
      - Temporary regular file in same directory (0600)
      - File fsync, atomic rename, and directory fsync
    """
    import fcntl
    import os

    ok, _ = validate_health(health_data)
    if not ok:
        return False

    target_health = health_path or HEALTH_FILE_DEFAULT
    target_lock = lock_path or HEALTH_LOCK_DEFAULT

    try:
        target_health.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target_lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        return False

    lock_fd = -1
    temp_path = None
    temp_fd = -1
    try:
        lock_fd = os.open(str(target_lock), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        temp_path = target_health.parent / f"{target_health.name}.tmp.{os.getpid()}"
        temp_fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        payload = json.dumps(health_data, indent=2, sort_keys=True) + "\n"
        os.write(temp_fd, payload.encode("utf-8"))
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = -1

        os.replace(str(temp_path), str(target_health))
        temp_path = None

        try:
            dir_fd = os.open(str(target_health.parent), os.O_RDONLY)
            os.fsync(dir_fd)
            os.close(dir_fd)
        except OSError:
            pass

        return True
    except Exception:
        return False
    finally:
        if temp_fd != -1:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        if lock_fd != -1:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def read_health(health_path: Optional[Path] = None) -> Dict[str, Any]:
    """Read and validate the sole health projection at /run/aq-network-policy/health.json.

    Readers never independently query NM or resolved.
    Missing, invalid, or unreadable files fail safe as 'unavailable'.
    """
    target = health_path or HEALTH_FILE_DEFAULT
    if not target.exists() or not target.is_file():
        return fallback_unavailable_health(AcquisitionError.NONE)

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        ok, _ = validate_health(data)
        if not ok:
            return fallback_unavailable_health(AcquisitionError.MALFORMED)
        return sanitize_telemetry(data)
    except Exception:
        return fallback_unavailable_health(AcquisitionError.MALFORMED)


def acquire_and_publish_health(
    iface: Optional[str] = None,
    health_path: Optional[Path] = None,
    lock_path: Optional[Path] = None,
    sysfs_base: Optional[Path] = None,
    cmd_runner: Optional[Any] = None,
    trusted_profiles_path: Optional[Path] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Bounded observation transaction: inspects facts, derives health, publishes projection."""
    chosen_iface = iface
    if not chosen_iface:
        base = sysfs_base or Path("/sys/class/net")
        if base.exists():
            for p in sorted(base.iterdir()):
                if (p / "wireless").is_dir() or (p / "phy80211").is_dir():
                    chosen_iface = p.name
                    break
    if not chosen_iface:
        chosen_iface = "wlan0"

    facts, acq_err = acquire_facts(
        chosen_iface,
        sysfs_base=sysfs_base,
        cmd_runner=cmd_runner,
        trusted_profiles_path=trusted_profiles_path,
    )
    record = derive_health_record(facts, acq_err)
    pub_ok = publish_health(record, health_path=health_path, lock_path=lock_path)
    return pub_ok, record


# ==============================================================================
# N2 Narrow Policy Executor, Watchdog, and Trust Map Interface
# ==============================================================================

class TrustReplaceResult(str, enum.Enum):
    UPDATED = "updated"
    INVALID_INPUT = "invalid_input"
    UNSAFE_METADATA = "unsafe_metadata"
    LOCK_TIMEOUT = "lock_timeout"
    DURABLE_WRITE_FAILED = "durable_write_failed"


def get_current_boot_id(boot_id_file: Optional[Path] = None) -> str:
    """Read current host boot_id or return zero UUID fallback."""
    path = boot_id_file or Path("/proc/sys/kernel/random/boot_id")
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "00000000-0000-0000-0000-000000000000"


def replace_trust_map(
    input_path: Union[str, Path],
    target_path: Optional[Path] = None,
    lock_path: Optional[Path] = None,
    check_privileges: bool = True,
    timeout_s: float = 2.0,
) -> Tuple[TrustReplaceResult, int]:
    """Atomically validate and replace private trusted-profiles.json map.

    Exit codes:
      0: updated
      2: invalid_input
      3: unsafe_metadata
      4: lock_timeout
      5: durable_write_failed
    """
    import fcntl
    import os
    import stat
    import time

    target = target_path or TRUSTED_PROFILES_DEFAULT
    lock_file = lock_path or TRUSTED_PROFILES_LOCK_DEFAULT

    if check_privileges:
        if os.geteuid() != 0:
            return TrustReplaceResult.UNSAFE_METADATA, 3

    p = Path(input_path)
    if not p.exists():
        return TrustReplaceResult.INVALID_INPUT, 2
    if p.is_symlink():
        return TrustReplaceResult.UNSAFE_METADATA, 3
    if not p.is_file():
        return TrustReplaceResult.UNSAFE_METADATA, 3

    try:
        st = p.stat()
        if check_privileges and st.st_uid != 0:
            return TrustReplaceResult.UNSAFE_METADATA, 3
        if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return TrustReplaceResult.UNSAFE_METADATA, 3
        if st.st_size > MAX_TRUST_FILE_BYTES:
            return TrustReplaceResult.INVALID_INPUT, 2
    except OSError:
        return TrustReplaceResult.UNSAFE_METADATA, 3

    try:
        content = p.read_text(encoding="utf-8")
        if len(content.encode("utf-8")) > MAX_TRUST_FILE_BYTES:
            return TrustReplaceResult.INVALID_INPUT, 2
        data = json.loads(content)
    except Exception:
        return TrustReplaceResult.INVALID_INPUT, 2

    ok, _ = validate_trust(data)
    if not ok:
        return TrustReplaceResult.INVALID_INPUT, 2

    try:
        lock_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        return TrustReplaceResult.DURABLE_WRITE_FAILED, 5

    lock_fd = -1
    temp_path = None
    temp_fd = -1
    try:
        lock_fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o600)
        start = time.monotonic()
        locked = False
        while time.monotonic() - start < timeout_s:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except (BlockingIOError, OSError):
                time.sleep(0.05)
        if not locked:
            return TrustReplaceResult.LOCK_TIMEOUT, 4

        temp_path = target.parent / f"{target.name}.tmp.{os.getpid()}"
        temp_fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
        os.write(temp_fd, payload.encode("utf-8"))
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = -1

        # Back up existing target file to .bak before replacing
        if target.exists():
            try:
                bak_path = target.with_suffix(".bak")
                bak_path.write_bytes(target.read_bytes())
                bak_path.chmod(0o600)
            except OSError:
                pass

        os.replace(str(temp_path), str(target))
        temp_path = None

        try:
            dir_fd = os.open(str(target.parent), os.O_RDONLY)
            os.fsync(dir_fd)
            os.close(dir_fd)
        except OSError:
            pass

        return TrustReplaceResult.UPDATED, 0
    except Exception:
        return TrustReplaceResult.DURABLE_WRITE_FAILED, 5
    finally:
        if temp_fd != -1:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        if lock_fd != -1:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def publish_receipt(
    receipt_data: Dict[str, Any],
    receipt_path: Optional[Path] = None,
    lock_path: Optional[Path] = None,
) -> bool:
    """Atomic durable writer for override-lease.json receipt."""
    import fcntl
    import os

    ok, _ = validate_receipt(receipt_data)
    if not ok:
        return False

    target_receipt = receipt_path or OVERRIDE_LEASE_DEFAULT
    target_lock = lock_path or OVERRIDE_LEASE_LOCK_DEFAULT

    try:
        target_receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target_lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        return False

    lock_fd = -1
    temp_path = None
    temp_fd = -1
    try:
        lock_fd = os.open(str(target_lock), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        temp_path = target_receipt.parent / f"{target_receipt.name}.tmp.{os.getpid()}"
        temp_fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        payload = json.dumps(receipt_data, indent=2, sort_keys=True) + "\n"
        os.write(temp_fd, payload.encode("utf-8"))
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = -1

        os.replace(str(temp_path), str(target_receipt))
        temp_path = None

        try:
            dir_fd = os.open(str(target_receipt.parent), os.O_RDONLY)
            os.fsync(dir_fd)
            os.close(dir_fd)
        except OSError:
            pass

        return True
    except Exception:
        return False
    finally:
        if temp_fd != -1:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        if lock_fd != -1:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def read_receipt(receipt_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Read and validate the sole lease receipt at /run/aq-network-policy/private/override-lease.json."""
    target = receipt_path or OVERRIDE_LEASE_DEFAULT
    if not target.exists() or not target.is_file():
        return None

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        ok, _ = validate_receipt(data)
        if not ok:
            return None
        return data
    except Exception:
        return None


def execute_policy_transaction(
    iface: str,
    event: str = "admit",
    mode: str = "legacy",
    now_epoch_s: Optional[int] = None,
    boot_id: Optional[str] = None,
    cmd_runner: Optional[Any] = None,
    sysfs_base: Optional[Path] = None,
    effect_lock_path: Optional[Path] = None,
    receipt_path: Optional[Path] = None,
    receipt_lock_path: Optional[Path] = None,
    health_path: Optional[Path] = None,
    health_lock_path: Optional[Path] = None,
    trusted_profiles_path: Optional[Path] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Execute bounded policy or legacy transaction under exclusive effect-operation lock.

    Lock order: effect-operation -> mapping -> receipt -> health.
    """
    import fcntl
    import os
    import time

    runner = cmd_runner or _run_bounded_command
    cur_time = int(now_epoch_s if now_epoch_s is not None else time.time())
    cur_boot = boot_id or get_current_boot_id()

    # Legacy branch — preserves exact pre-N2 behavior
    if mode == "legacy":
        if not is_valid_interface(iface):
            return False, {"error": "unsafe_interface"}
        is_wifi = is_wifi_interface(iface, sysfs_base)
        if is_wifi and event in ("admit", "up", "dhcp4-change"):
            runner(["resolvectl", "dns", iface, "1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4"])
            runner(["resolvectl", "domain", iface, "~."])
            return True, {"action": "legacy_override", "iface": iface}
        return True, {"action": "preserve_link_dns", "iface": iface}

    # Policy branch — bounded effect lock
    target_effect_lock = effect_lock_path or EFFECT_LOCK_DEFAULT
    try:
        target_effect_lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        return False, {"error": "cannot_create_lock_dir"}

    lock_fd = -1
    try:
        lock_fd = os.open(str(target_effect_lock), os.O_RDWR | os.O_CREAT, 0o600)
        start_lock = time.monotonic()
        locked = False
        while time.monotonic() - start_lock < EFFECT_LOCK_TIMEOUT_S:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except (BlockingIOError, OSError):
                time.sleep(0.05)
        if not locked:
            return False, {"error": "lock_timeout"}

        # In-lock fact acquisition and receipt read
        facts, acq_err = acquire_facts(
            iface,
            sysfs_base=sysfs_base,
            cmd_runner=runner,
            trusted_profiles_path=trusted_profiles_path,
        )

        prior_rec = read_receipt(receipt_path)
        prior_effect = PriorEffect.NONE.value
        receipt_state = ReceiptState.MISSING.value
        rev = 0
        if prior_rec:
            rev = prior_rec.get("revision", 0)
            st = prior_rec.get("receipt_state")
            rec_boot = prior_rec.get("boot_id", "")
            if rec_boot and rec_boot != cur_boot:
                prior_effect = PriorEffect.NONE.value
                receipt_state = ReceiptState.EXPIRED.value
            elif st == "active":
                # Check expiry
                if cur_time >= prior_rec.get("lease_expiry_epoch_s", 0):
                    prior_effect = PriorEffect.NONE.value
                    receipt_state = ReceiptState.EXPIRED.value
                else:
                    prior_effect = PriorEffect.ACTIVE_OVERRIDE.value
                    receipt_state = ReceiptState.ACTIVE_FRESH.value
            elif st == "pending_apply":
                prior_effect = PriorEffect.PENDING_APPLY.value
                receipt_state = ReceiptState.PENDING_APPLY_FRESH.value
            elif st == "pending_revert":
                prior_effect = PriorEffect.PENDING_REVERT.value
                receipt_state = ReceiptState.PENDING_REVERT_FRESH.value
            else:
                receipt_state = ReceiptState.INVALID.value

        # Pure decision
        eligibility = resolve_eligibility(facts)
        executor_state = {
            "prior_effect": prior_effect,
            "receipt_state": receipt_state,
            "event": event,
            "mode": mode,
        }
        decision = resolve_transition(eligibility, executor_state, input_data=facts)
        act = decision["action"]
        reason_val = decision["reason"]

        if act in (Action.APPLY_PUBLIC_OVERRIDE.value, Action.REFRESH_OVERRIDE.value):
            # Durable pending receipt before mutation
            pending_receipt = {
                "schema_version": SCHEMA_RECEIPT,
                "receipt_state": "pending_apply",
                "boot_id": cur_boot,
                "interface": iface,
                "action": act,
                "reason": reason_val,
                "lease_expiry_epoch_s": cur_time + RECEIPT_LEASE_DURATION_S,
                "updated_epoch_s": cur_time,
                "revision": rev + 1,
            }
            publish_receipt(pending_receipt, receipt_path, receipt_lock_path)

            # Mutate per-link DNS
            out_dns, err_dns = runner(["resolvectl", "dns", iface, "1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4"])
            out_dom, err_dom = runner(["resolvectl", "domain", iface, "~."])

            if err_dns == AcquisitionError.NONE and err_dom == AcquisitionError.NONE:
                active_receipt = dict(pending_receipt)
                active_receipt["receipt_state"] = "active"
                active_receipt["revision"] = rev + 2
                publish_receipt(active_receipt, receipt_path, receipt_lock_path)

                health_rec = derive_health_record(facts, acq_err)
                health_rec["policy_state"] = PolicyState.OVERRIDING.value
                health_rec["lease"] = LeaseState.ACTIVE.value
                publish_health(health_rec, health_path, health_lock_path)
                return True, decision
            else:
                # Mutation failed -> immediate same-lock revert
                runner(["resolvectl", "revert", iface])
                inactive_receipt = dict(pending_receipt)
                inactive_receipt["receipt_state"] = "inactive"
                inactive_receipt["revision"] = rev + 2
                publish_receipt(inactive_receipt, receipt_path, receipt_lock_path)

                health_rec = derive_health_record(facts, acq_err)
                health_rec["policy_state"] = PolicyState.DEGRADED.value
                health_rec["lease"] = LeaseState.NOT_APPLICABLE.value
                publish_health(health_rec, health_path, health_lock_path)
                return False, {"error": "mutation_failed", "action": act}

        elif act == Action.REVERT_OVERRIDE.value:
            pending_receipt = {
                "schema_version": SCHEMA_RECEIPT,
                "receipt_state": "pending_revert",
                "boot_id": cur_boot,
                "interface": iface,
                "action": act,
                "reason": reason_val,
                "lease_expiry_epoch_s": cur_time,
                "updated_epoch_s": cur_time,
                "revision": rev + 1,
            }
            publish_receipt(pending_receipt, receipt_path, receipt_lock_path)

            runner(["resolvectl", "revert", iface])

            inactive_receipt = dict(pending_receipt)
            inactive_receipt["receipt_state"] = "inactive"
            inactive_receipt["revision"] = rev + 2
            publish_receipt(inactive_receipt, receipt_path, receipt_lock_path)

            health_rec = derive_health_record(facts, acq_err)
            health_rec["policy_state"] = PolicyState.REVERTED.value
            health_rec["lease"] = LeaseState.EXPIRED.value
            publish_health(health_rec, health_path, health_lock_path)
            return True, decision

        else:  # PRESERVE_LINK_DNS
            if prior_effect in (PriorEffect.ACTIVE_OVERRIDE.value, PriorEffect.PENDING_APPLY.value):
                runner(["resolvectl", "revert", iface])
                inactive_receipt = {
                    "schema_version": SCHEMA_RECEIPT,
                    "receipt_state": "inactive",
                    "boot_id": cur_boot,
                    "interface": iface,
                    "action": act,
                    "reason": reason_val,
                    "lease_expiry_epoch_s": cur_time,
                    "updated_epoch_s": cur_time,
                    "revision": rev + 1,
                }
                publish_receipt(inactive_receipt, receipt_path, receipt_lock_path)

            health_rec = derive_health_record(facts, acq_err)
            health_rec["policy_state"] = PolicyState.PRESERVING.value
            health_rec["lease"] = LeaseState.NOT_APPLICABLE.value
            publish_health(health_rec, health_path, health_lock_path)
            return True, decision

    finally:
        if lock_fd != -1:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def run_watchdog_or_recovery(
    mode: str = "policy",
    now_epoch_s: Optional[int] = None,
    boot_id: Optional[str] = None,
    cmd_runner: Optional[Any] = None,
    sysfs_base: Optional[Path] = None,
    effect_lock_path: Optional[Path] = None,
    receipt_path: Optional[Path] = None,
    receipt_lock_path: Optional[Path] = None,
    health_path: Optional[Path] = None,
    health_lock_path: Optional[Path] = None,
) -> bool:
    """Watchdog and boot-recovery transaction.

    In legacy mode: immediate no-op.
    In policy mode: inspects boot_id and lease_expiry_epoch_s; reverts expired or invalid state.
    """
    import fcntl
    import os
    import time

    if mode == "legacy":
        return True

    runner = cmd_runner or _run_bounded_command
    cur_time = int(now_epoch_s if now_epoch_s is not None else time.time())
    cur_boot = boot_id or get_current_boot_id()

    target_effect_lock = effect_lock_path or EFFECT_LOCK_DEFAULT
    try:
        target_effect_lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        return False

    lock_fd = -1
    try:
        lock_fd = os.open(str(target_effect_lock), os.O_RDWR | os.O_CREAT, 0o600)
        # Watchdog retries every 250ms for up to 5s
        start_lock = time.monotonic()
        locked = False
        while time.monotonic() - start_lock < WATCHDOG_MAX_RETRY_S:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except (BlockingIOError, OSError):
                time.sleep(WATCHDOG_RETRY_INTERVAL_S)
        if not locked:
            return False

        rec = read_receipt(receipt_path)
        if not rec:
            _revert_wifi_links(runner, sysfs_base)
            return True

        iface = rec.get("interface", "")
        rec_boot = rec.get("boot_id", "")
        rec_state = rec.get("receipt_state", "")
        expiry = rec.get("lease_expiry_epoch_s", 0)
        rev = rec.get("revision", 0)

        needs_revert = False
        if rec_boot != cur_boot or rec_state in ("pending_apply", "pending_revert"):
            needs_revert = True
        elif rec_state == "active" and cur_time >= expiry:
            needs_revert = True

        if needs_revert:
            if iface and is_valid_interface(iface):
                runner(["resolvectl", "revert", iface])
            else:
                _revert_wifi_links(runner, sysfs_base)

            inactive_rec = dict(rec)
            inactive_rec["receipt_state"] = "inactive"
            inactive_rec["updated_epoch_s"] = cur_time
            inactive_rec["revision"] = rev + 1
            publish_receipt(inactive_rec, receipt_path, receipt_lock_path)

            h = fallback_unavailable_health()
            h["policy_state"] = PolicyState.REVERTED.value
            h["lease"] = LeaseState.EXPIRED.value
            publish_health(h, health_path, health_lock_path)

        return True
    finally:
        if lock_fd != -1:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except OSError:
                pass


def _revert_wifi_links(runner: Any, sysfs_base: Optional[Path] = None) -> None:
    """Enumerate and revert only local sysfs-proven Wi-Fi interfaces."""
    base = sysfs_base or Path("/sys/class/net")
    if base.exists():
        for p in sorted(base.iterdir()):
            if (p / "wireless").is_dir() or (p / "phy80211").is_dir():
                if is_valid_interface(p.name):
                    runner(["resolvectl", "revert", p.name])


def run_emergency_revert(
    cmd_runner: Optional[Any] = None,
    sysfs_base: Optional[Path] = None,
    receipt_path: Optional[Path] = None,
    receipt_lock_path: Optional[Path] = None,
    health_path: Optional[Path] = None,
    health_lock_path: Optional[Path] = None,
) -> bool:
    """Emergency fallback revert: immediately reverts Wi-Fi interfaces and marks degraded."""
    runner = cmd_runner or _run_bounded_command
    _revert_wifi_links(runner, sysfs_base)

    rec = read_receipt(receipt_path)
    rev = (rec.get("revision", 0) + 1) if rec else 1
    inactive_receipt = {
        "schema_version": SCHEMA_RECEIPT,
        "receipt_state": "inactive",
        "boot_id": get_current_boot_id(),
        "interface": "wlan0",
        "action": Action.REVERT_OVERRIDE.value,
        "reason": Reason.UNKNOWN_STATE.value,
        "lease_expiry_epoch_s": 0,
        "updated_epoch_s": 0,
        "revision": rev,
    }
    publish_receipt(inactive_receipt, receipt_path, receipt_lock_path)

    h = fallback_unavailable_health(AcquisitionError.NONE)
    h["policy_state"] = PolicyState.DEGRADED.value
    publish_health(h, health_path, health_lock_path)
    return True
