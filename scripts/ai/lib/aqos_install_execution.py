#!/usr/bin/env python3
"""Fail-closed, non-executing verification for AQ-OS installer authorization evidence."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

import aqos_install_resolver as resolver

MAX_RECEIPT_TTL_SECONDS = 3600
MAX_CLOCK_SKEW_SECONDS = 60
MIN_HMAC_KEY_BYTES = 32


class ExecutionVerificationError(ValueError):
    """Stable fail-closed error surfaced by the execution verifier."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _reject(reason: str, message: str) -> None:
    raise ExecutionVerificationError(reason, message)


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ExecutionVerificationError("receipt_timestamp_invalid", "receipt timestamps must be UTC seconds") from exc
    return parsed


def _validate_timing(receipt: Mapping[str, Any], now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        _reject("clock_invalid", "verification clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    issued = _timestamp(receipt["issued_at"])
    expires = _timestamp(receipt["expires_at"])
    if expires <= issued:
        _reject("receipt_window_invalid", "receipt expiry must follow issuance")
    if (expires - issued).total_seconds() > MAX_RECEIPT_TTL_SECONDS:
        _reject("receipt_ttl_exceeded", "receipt lifetime exceeds the P0 maximum")
    if (issued - now).total_seconds() > MAX_CLOCK_SKEW_SECONDS:
        _reject("receipt_not_yet_valid", "receipt issuance is too far in the future")
    if expires <= now:
        _reject("receipt_expired", "receipt has expired")


def _catalogs_bound(
    lock: Mapping[str, Any], module_bytes: bytes, ai_bytes: bytes, fieldset_bytes: bytes,
) -> dict[str, Any]:
    expected = lock["catalog_digests"]
    observed = {
        "module_catalog_sha256": resolver.sha256_bytes(module_bytes),
        "ai_fit_policy_catalog_sha256": resolver.sha256_bytes(ai_bytes),
        "mysystem_fieldset_sha256": resolver.sha256_bytes(fieldset_bytes),
    }
    if expected != observed:
        _reject("catalog_digest_mismatch", "current installer contracts do not match the resolved lock")
    module_catalog = resolver.parse_json_strict(module_bytes)
    fieldset = resolver.parse_json_strict(fieldset_bytes)
    if not isinstance(module_catalog, dict) or not isinstance(fieldset, dict):
        _reject("catalog_invalid", "installer catalogs must be JSON objects")
    if fieldset.get("activation") != "p0-inert":
        _reject("fieldset_activation_invalid", "P0 verifier requires the inert field-set contract")
    return module_catalog


def _schema_validate(artifact: Mapping[str, Any], schema: Mapping[str, Any], expected_type: str) -> None:
    if artifact.get("artifact_type") != expected_type:
        _reject("artifact_type_invalid", f"expected {expected_type}")
    try:
        resolver._validate_schema(artifact, schema)
    except resolver.ResolverError as exc:
        raise ExecutionVerificationError(exc.reason, str(exc)) from exc


def _verify_mac(receipt: Mapping[str, Any], key_provider: Callable[[str], bytes | None]) -> None:
    key_id = receipt["signing_key_id"]
    key = key_provider(key_id)
    if key is None:
        _reject("signing_key_unknown", "receipt signing key is unknown or revoked")
    if not isinstance(key, bytes) or len(key) < MIN_HMAC_KEY_BYTES:
        _reject("signing_key_invalid", "receipt signing key must contain at least 32 bytes")
    unsigned = dict(receipt)
    supplied = unsigned.pop("mac_hmac_sha256")
    expected = hmac.new(key, resolver.jcs_bytes(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        _reject("receipt_mac_invalid", "receipt integrity check failed")


def verify_execution_evidence(
    lock: Mapping[str, Any], projection: Mapping[str, Any], receipt: Mapping[str, Any],
    hardware: Mapping[str, Any], schema: Mapping[str, Any], module_bytes: bytes,
    ai_bytes: bytes, fieldset_bytes: bytes, repo_root: str,
    key_provider: Callable[[str], bytes | None], now: datetime,
    source_verifier: Callable[[Mapping[str, Any], str], None] | None = None,
) -> dict[str, Any]:
    """Verify P0 evidence and return proof that remains explicitly non-executable."""
    _schema_validate(lock, schema, "resolved_plan_lock")
    _schema_validate(receipt, schema, "execution_authorization_receipt")
    _validate_timing(receipt, now)
    _verify_mac(receipt, key_provider)
    module_catalog = _catalogs_bound(lock, module_bytes, ai_bytes, fieldset_bytes)

    expected_projection = resolver.compile_projection(lock, module_catalog, fieldset_bytes)
    if resolver.jcs_bytes(projection) != resolver.jcs_bytes(expected_projection):
        _reject("projection_mismatch", "supplied projection does not match the resolved lock")
    executor = expected_projection.get("executor") or {}
    if executor.get("executable") is not False or executor.get("env") != {}:
        _reject("projection_not_inert", "P0 projection must remain non-executable with an empty environment")

    verifier = source_verifier or resolver.verify_source_identity
    try:
        verifier(lock["source_identity"], repo_root)
    except resolver.ResolverError as exc:
        raise ExecutionVerificationError(exc.reason, str(exc)) from exc

    current_hardware = resolver.summarize_hardware(hardware)
    if current_hardware != lock["hardware_summary"]:
        _reject("hardware_identity_mismatch", "current hardware does not match the resolved lock")

    plan_digest = resolver.sha256_bytes(resolver.jcs_bytes(lock))
    source_digest = resolver.sha256_bytes(resolver.jcs_bytes(lock["source_identity"]))
    projection_digest = resolver.sha256_bytes(resolver.jcs_bytes(expected_projection))
    bound = {
        "resolved_plan_sha256": plan_digest,
        "source_identity_sha256": source_digest,
        "projection_sha256": projection_digest,
        "hardware_identity_sha256": current_hardware["hardware_identity_sha256"],
        "authorized_action": "build-only",
    }
    for field, value in bound.items():
        if receipt.get(field) != value:
            _reject("receipt_binding_mismatch", f"receipt does not bind the current {field}")
    return {
        "artifact_type": "execution_verification",
        "schema_version": "aqos-install-execution-verification/v1",
        "status": "activation_blocked",
        "verified": True,
        "resolved_plan_sha256": plan_digest,
        "projection_sha256": projection_digest,
        "hardware_identity_sha256": current_hardware["hardware_identity_sha256"],
        "authorized_action": "build-only",
        "blocked_reason": executor.get("blocked_reason"),
        "executable": False,
    }
