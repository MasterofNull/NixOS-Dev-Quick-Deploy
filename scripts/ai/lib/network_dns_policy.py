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
    if val in (SCHEMA_INPUT, SCHEMA_ELIGIBILITY, SCHEMA_DECISION, SCHEMA_HEALTH):
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
