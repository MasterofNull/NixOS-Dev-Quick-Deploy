#!/usr/bin/env python3
"""Pure B2-C1 workflow-shadow contract and decision oracle."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping


EVENT_LIMIT_BYTES = 2048
PENDING_RECEIPT_LIMIT = 64
PHASE_DOMAIN = "aq.workflow-shadow.phase.v1"
IDENTITY_DOMAIN = "aq.workflow-shadow.identity.v1"
DIGEST_DOMAIN = "aq.workflow-shadow.digest.v1"
SOURCE_SHA256 = "12ba465a5ede653579ac52752558ed9068fe0bbfd407dbc44cb2b80b70c72374"
EXPECTED_PHASE_TOKENS = (
    "sha256:a07e8aa35ef87d777d3f12ef637b0ad962f63a0ec374b67915b475d43e9b9d9f",
    "sha256:0bea302ecb71670082516b31e1a95c7b59e22402d7943252ce2a801589b1bd75",
    "sha256:7a43e0fdf66ba825f301959695d0168b166815aea295c26b5212be4267aea0ec",
    "sha256:3756c4e2a3ec79e06d021375f37457549247e7e150ebcb0a74a69c45b0c34248",
    "sha256:1a11cd07844c2be44f813b15da1e12a0a87e8ec7b9b408ba7b83c0f53c52a47b",
    "sha256:5e27f1f8de48447bdf39a55d64957e15b0be630dc05bb23cb09a23059c335846",
    "sha256:850460eae2d043439122798305f3d06a63ddcff12f3b3cd72a8d18aa1d4ad1fe",
    "sha256:dfd73cc0e0b0a7414f8cd4d65d02c9ef3352b15a632ea3e8be02f847679fa8b4",
    "sha256:25ff70e33e55caa5dfbb0ed52380912af4d80aeda1fb065e6da1df343a9f3fd0",
    "sha256:2d88612d72764e7b2a363ef6bf259d45490295faaf8e362726a42e53e1ac29c0",
    "sha256:8a5763d54c3d1b87f47e2fa3677039f8c0a3f62597392656bdb10670220ec45d",
    "sha256:d82f8f4d8df467b146d85f73025dae770b2bcd7d0c63a057e2939cdbc4fd264d",
    "sha256:43af273e2bcb6def794b7d5a2b62da36916614e1759c4bfc206ba6a326b1365b",
    "sha256:81003da22fab9aee69d7e30d8648203e2d5d479614d23f356aa39e2740a12aad",
)
VERSIONS = {
    "event": "aq.workflow-shadow-event.v1",
    "snapshot": "aq.workflow-shadow-snapshot.v1",
    "immutable_outbox": "aq.workflow-shadow-outbox.v1",
    "delivery_control": "aq.workflow-shadow-delivery-control.v1",
    "health": "aq.workflow-shadow-health.v1",
}
TRANSITIONS = {"run_start", "manual_phase_transition", "terminal_completion"}
STATUSES = {"started", "running", "completed", "failed", "cancelled"}
ACTIONS = {"start", "advance", "complete", "fail", "cancel"}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ERRORS = {
    "disabled", "deadline_exceeded", "database_unavailable", "schema_unready",
    "schema_invalid", "privacy_rejected", "cas_mismatch", "revision_gap",
    "event_collision", "terminal_conflict", "transaction_failed", "projection_gap",
    "integrity_failed", "disk_budget_exceeded", "parked",
}
RECEIPT_FIELDS = {
    "event_id", "outbox_id", "workflow_id", "expected_revision", "revision",
    "transition_kind", "status", "phase_id", "action", "terminal",
    "live_commit_digest", "occurred_at", "writer_identity", "writer_version",
}
STORED_FIELDS = {"revision", "event_id", "live_commit_digest", "terminal"}
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")


class ContractError(ValueError):
    """Privacy-safe contract rejection with a fixed low-cardinality reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _reject(reason: str) -> None:
    raise ContractError(reason)


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _reject("numeric_type_invalid")
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [_nfc(item) for item in value]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _reject("object_key_invalid")
            normalized = unicodedata.normalize("NFC", key)
            if normalized in result:
                _reject("normalized_key_collision")
            result[normalized] = _nfc(item)
        return result
    _reject("value_type_invalid")


def canonical_json_bytes(value: Any) -> bytes:
    """NFC UTF-8 JSON with sorted keys, integer-only numbers, and no padding."""
    try:
        return json.dumps(
            _nfc(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except ContractError:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractError("canonicalization_failed") from exc


def parse_json_strict(payload: str | bytes) -> Any:
    """Parse JSON while rejecting duplicate keys, floats, and non-finite constants."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                _reject("duplicate_json_key")
            result[key] = value
        return result

    def reject_float(_value: str) -> None:
        _reject("numeric_type_invalid")

    def reject_constant(_value: str) -> None:
        _reject("numeric_type_invalid")

    try:
        return json.loads(payload, object_pairs_hook=pairs, parse_float=reject_float, parse_constant=reject_constant)
    except ContractError:
        raise
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
        raise ContractError("json_invalid") from exc


def domain_digest(domain: str, value: Any) -> str:
    if not isinstance(domain, str) or not domain or len(domain) > 128:
        _reject("digest_domain_invalid")
    body = domain.encode("utf-8") + b"\x00" + canonical_json_bytes(value)
    return "sha256:" + hashlib.sha256(body).hexdigest()


def opaque_identity(kind: str, value: Any) -> str:
    if kind not in {"event", "outbox", "evidence"}:
        _reject("identity_domain_invalid")
    return domain_digest(f"{IDENTITY_DOMAIN}.{kind}", value)


def _integer(value: Any, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _closed(value: Any, fields: set[str], reason: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _reject(reason)
    return value


def _string(value: Any, minimum: int, maximum: int, pattern: re.Pattern[str] | None = None) -> bool:
    return (
        isinstance(value, str) and minimum <= len(value) <= maximum
        and (pattern is None or pattern.fullmatch(value) is not None)
    )


def validate_phase_registry(registry: Mapping[str, Any]) -> None:
    _closed(registry, {"$schema", "registry_version", "source", "domain", "entries"}, "phase_registry_shape")
    if registry["$schema"] != "https://json-schema.org/draft/2020-12/schema" or registry["registry_version"] != "aq.workflow-shadow-phase-tokens.v1":
        _reject("phase_registry_version")
    _closed(registry["source"], {"path", "sha256"}, "phase_registry_source")
    if registry["source"] != {"path": "config/workflow-blueprints.json", "sha256": SOURCE_SHA256}:
        _reject("phase_registry_source")
    if registry["domain"] != PHASE_DOMAIN or not isinstance(registry["entries"], list) or len(registry["entries"]) != 14:
        _reject("phase_registry_cardinality")
    seen_ids: set[str] = set()
    seen_tokens: set[str] = set()
    seen_indexes: set[int] = set()
    for position, entry in enumerate(registry["entries"]):
        _closed(entry, {"phase_id", "phase_index", "token"}, "phase_entry_shape")
        phase_id = entry["phase_id"]
        index = entry["phase_index"]
        token = entry["token"]
        if not _string(phase_id, 1, 64, re.compile(r"^[a-z][a-z0-9_]*$")) or not _integer(index, 0, 13) or not _DIGEST.fullmatch(token or ""):
            _reject("phase_entry_invalid")
        expected = "sha256:" + hashlib.sha256(PHASE_DOMAIN.encode() + b"\x00" + phase_id.encode()).hexdigest()
        if token != expected or token != EXPECTED_PHASE_TOKENS[index] or phase_id in seen_ids or index in seen_indexes or token in seen_tokens:
            _reject("phase_registry_collision")
        if index != position:
            _reject("phase_index_invalid")
        seen_ids.add(phase_id)
        seen_indexes.add(index)
        seen_tokens.add(token)
    if len(seen_ids) != 14 or seen_indexes != set(range(14)):
        _reject("phase_registry_incomplete")


def lookup_phase(registry: Mapping[str, Any], phase_id: str) -> dict[str, Any]:
    validate_phase_registry(registry)
    matches = [entry for entry in registry["entries"] if entry["phase_id"] == phase_id]
    if len(matches) != 1:
        _reject("phase_unknown")
    entry = matches[0]
    return {"phase_token": entry["token"], "phase_index": entry["phase_index"]}


def _validate_receipt(receipt: Mapping[str, Any]) -> None:
    _closed(receipt, RECEIPT_FIELDS, "receipt_fields_invalid")
    for field in ("event_id", "outbox_id", "workflow_id"):
        if not _string(receipt[field], 1, 128, _OPAQUE_ID):
            _reject("receipt_identifier_invalid")
    if not _integer(receipt["expected_revision"], 0, 99999) or not _integer(receipt["revision"], 1, 100000):
        _reject("receipt_revision_invalid")
    if receipt["revision"] != receipt["expected_revision"] + 1:
        _reject("receipt_revision_nonmonotonic")
    if receipt["transition_kind"] not in TRANSITIONS or receipt["status"] not in STATUSES or receipt["action"] not in ACTIONS:
        _reject("receipt_enum_invalid")
    if not _string(receipt["phase_id"], 1, 64, re.compile(r"^[a-z][a-z0-9_]*$")):
        _reject("phase_unknown")
    if not isinstance(receipt["terminal"], bool):
        _reject("receipt_terminal_invalid")
    terminal = receipt["status"] in TERMINAL_STATUSES
    if receipt["terminal"] != terminal:
        _reject("receipt_terminal_inconsistent")
    if (receipt["transition_kind"] == "terminal_completion") != terminal:
        _reject("receipt_transition_inconsistent")
    action_terminal = receipt["action"] in {"complete", "fail", "cancel"}
    if action_terminal != terminal:
        _reject("receipt_action_inconsistent")
    if not _DIGEST.fullmatch(receipt["live_commit_digest"] or ""):
        _reject("receipt_digest_invalid")
    if not _string(receipt["occurred_at"], 20, 35, _TIMESTAMP):
        _reject("receipt_timestamp_invalid")
    if not _string(receipt["writer_identity"], 1, 64, re.compile(r"^[A-Za-z0-9._:-]+$")):
        _reject("receipt_writer_invalid")
    if not _string(receipt["writer_version"], 1, 32, re.compile(r"^[A-Za-z0-9._-]+$")):
        _reject("receipt_writer_invalid")


def map_receipt(receipt: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Build all five variants from empty allowlists; never copy an input object."""
    _validate_receipt(receipt)
    phase = lookup_phase(registry, receipt["phase_id"])
    event: dict[str, Any] = {}
    event.update({
        "schema_version": VERSIONS["event"], "event_id": receipt["event_id"],
        "vertical_id": "workflow-run-task", "workflow_id": receipt["workflow_id"],
        "expected_revision": receipt["expected_revision"], "revision": receipt["revision"],
        "transition_kind": receipt["transition_kind"], "status": receipt["status"],
        "phase_token": phase["phase_token"], "phase_index": phase["phase_index"],
        "action": receipt["action"], "terminal": receipt["terminal"],
        "live_commit_digest": receipt["live_commit_digest"], "occurred_at": receipt["occurred_at"],
        "writer_identity": receipt["writer_identity"], "writer_version": receipt["writer_version"],
    })
    validate_contract(event)
    event_digest = domain_digest(f"{DIGEST_DOMAIN}.event", event)
    snapshot: dict[str, Any] = {}
    snapshot.update({
        "schema_version": VERSIONS["snapshot"], "workflow_id": receipt["workflow_id"],
        "revision": receipt["revision"], "last_event_id": receipt["event_id"],
        "status": receipt["status"], "phase_token": phase["phase_token"],
        "phase_index": phase["phase_index"], "action": receipt["action"],
        "terminal": receipt["terminal"], "live_commit_digest": receipt["live_commit_digest"],
        "created_at": receipt["occurred_at"], "updated_at": receipt["occurred_at"],
    })
    outbox: dict[str, Any] = {}
    outbox.update({
        "schema_version": VERSIONS["immutable_outbox"], "outbox_id": receipt["outbox_id"],
        "event_id": receipt["event_id"], "workflow_id": receipt["workflow_id"],
        "revision": receipt["revision"], "event_digest": event_digest,
        "transaction_at": receipt["occurred_at"],
    })
    delivery: dict[str, Any] = {}
    delivery.update({
        "schema_version": VERSIONS["delivery_control"], "event_id": receipt["event_id"],
        "lease_epoch": 0, "attempt_count": 0, "next_attempt_at": None,
        "disposition": "pending", "last_error": None,
        "created_at": receipt["occurred_at"], "updated_at": receipt["occurred_at"],
    })
    health: dict[str, Any] = {}
    health.update({
        "schema_version": VERSIONS["health"], "authority": "legacy_json_authoritative",
        "enabled_state": "disabled", "health_state": "ready",
        "last_successful_write_age_bucket": "not_measured", "lag_bucket": "not_measured",
        "counts": {"transitions": 0, "cas_conflicts": 0, "duplicates": 0, "gaps": 0, "terminal_conflicts": 0, "privacy_failures": 0},
        "parked_reason": None, "disk_budget_state": "not_measured",
        "evidence_freshness": "fixture_only",
        "coverage": {"aq_qa": "ready", "web_dashboard": "not_wired"},
    })
    result = {"event": event, "snapshot": snapshot, "immutable_outbox": outbox, "delivery_control": delivery, "health": health}
    for contract in result.values():
        validate_contract(contract)
    return result


def validate_contract(value: Mapping[str, Any]) -> str:
    if not isinstance(value, Mapping):
        _reject("contract_type_invalid")
    version = value.get("schema_version")
    matches = [kind for kind, expected in VERSIONS.items() if version == expected]
    if len(matches) != 1:
        _reject("contract_version_invalid")
    kind = matches[0]
    fields = {
        "event": {"schema_version", "event_id", "vertical_id", "workflow_id", "expected_revision", "revision", "transition_kind", "status", "phase_token", "phase_index", "action", "terminal", "live_commit_digest", "occurred_at", "writer_identity", "writer_version"},
        "snapshot": {"schema_version", "workflow_id", "revision", "last_event_id", "status", "phase_token", "phase_index", "action", "terminal", "live_commit_digest", "created_at", "updated_at"},
        "immutable_outbox": {"schema_version", "outbox_id", "event_id", "workflow_id", "revision", "event_digest", "transaction_at"},
        "delivery_control": {"schema_version", "event_id", "lease_epoch", "attempt_count", "next_attempt_at", "disposition", "last_error", "created_at", "updated_at"},
        "health": {"schema_version", "authority", "enabled_state", "health_state", "last_successful_write_age_bucket", "lag_bucket", "counts", "parked_reason", "disk_budget_state", "evidence_freshness", "coverage"},
    }[kind]
    _closed(value, fields, "contract_fields_invalid")
    canonical_json_bytes(value)
    id_fields = {
        "event": ("event_id", "workflow_id"),
        "snapshot": ("workflow_id", "last_event_id"),
        "immutable_outbox": ("outbox_id", "event_id", "workflow_id"),
        "delivery_control": ("event_id",),
        "health": (),
    }[kind]
    if any(not _string(value[field], 1, 128, _OPAQUE_ID) for field in id_fields):
        _reject("contract_identifier_invalid")
    if kind == "event":
        if not _integer(value["expected_revision"], 0, 99999) or not _integer(value["revision"], 1, 100000) or value["revision"] != value["expected_revision"] + 1:
            _reject("event_revision_invalid")
        if value["vertical_id"] != "workflow-run-task" or value["transition_kind"] not in TRANSITIONS or value["status"] not in STATUSES or value["action"] not in ACTIONS:
            _reject("event_enum_invalid")
        if not isinstance(value["terminal"], bool) or value["terminal"] != (value["status"] in TERMINAL_STATUSES):
            _reject("event_terminal_invalid")
        if (value["transition_kind"] == "terminal_completion") != value["terminal"] or (value["action"] in {"complete", "fail", "cancel"}) != value["terminal"]:
            _reject("event_terminal_invalid")
        if not _DIGEST.fullmatch(value["phase_token"] or "") or not _integer(value["phase_index"], 0, 13):
            _reject("event_phase_invalid")
        if not _DIGEST.fullmatch(value["live_commit_digest"] or "") or not _string(value["occurred_at"], 20, 35, _TIMESTAMP):
            _reject("event_integrity_invalid")
        if not _string(value["writer_identity"], 1, 64, re.compile(r"^[A-Za-z0-9._:-]+$")) or not _string(value["writer_version"], 1, 32, re.compile(r"^[A-Za-z0-9._-]+$")):
            _reject("event_writer_invalid")
        if len(canonical_json_bytes(value)) > EVENT_LIMIT_BYTES:
            _reject("event_size_exceeded")
    elif kind == "snapshot":
        if not _integer(value["revision"], 1, 100000) or value["status"] not in STATUSES or value["action"] not in ACTIONS:
            _reject("snapshot_state_invalid")
        if not isinstance(value["terminal"], bool) or value["terminal"] != (value["status"] in TERMINAL_STATUSES) or (value["action"] in {"complete", "fail", "cancel"}) != value["terminal"]:
            _reject("snapshot_terminal_invalid")
        if not _DIGEST.fullmatch(value["phase_token"] or "") or not _integer(value["phase_index"], 0, 13) or not _DIGEST.fullmatch(value["live_commit_digest"] or ""):
            _reject("snapshot_integrity_invalid")
        if not all(_string(value[field], 20, 35, _TIMESTAMP) for field in ("created_at", "updated_at")):
            _reject("snapshot_timestamp_invalid")
    elif kind == "immutable_outbox":
        if not _integer(value["revision"], 1, 100000) or not _DIGEST.fullmatch(value["event_digest"] or ""):
            _reject("outbox_integrity_invalid")
        if not _string(value["transaction_at"], 20, 35, _TIMESTAMP):
            _reject("outbox_timestamp_invalid")
    elif kind == "delivery_control":
        if not _integer(value["lease_epoch"], 0, 1000000) or not _integer(value["attempt_count"], 0, 1000):
            _reject("delivery_integer_invalid")
        if value["disposition"] not in {"pending", "delivering", "delivered", "parked"} or value["last_error"] not in ERRORS | {None}:
            _reject("delivery_enum_invalid")
        if value["next_attempt_at"] is not None and not _string(value["next_attempt_at"], 20, 35, _TIMESTAMP):
            _reject("delivery_timestamp_invalid")
        if not all(_string(value[field], 20, 35, _TIMESTAMP) for field in ("created_at", "updated_at")):
            _reject("delivery_timestamp_invalid")
    elif kind == "health":
        if value["authority"] != "legacy_json_authoritative" or value["coverage"] != {"aq_qa": "ready", "web_dashboard": "not_wired"}:
            _reject("health_authority_invalid")
        _closed(value["counts"], {"transitions", "cas_conflicts", "duplicates", "gaps", "terminal_conflicts", "privacy_failures"}, "health_counts_invalid")
        if any(not _integer(item, 0, 100000) for item in value["counts"].values()):
            _reject("health_counts_invalid")
        if value["enabled_state"] not in {"disabled", "observing", "parked"} or value["health_state"] not in {"ready", "invalid", "not_measured"}:
            _reject("health_state_invalid")
        if value["last_successful_write_age_bucket"] not in {"not_measured", "lt_5s", "5s_to_60s", "gt_60s"} or value["lag_bucket"] not in {"not_measured", "within_budget", "warning", "parked"}:
            _reject("health_bucket_invalid")
        if value["parked_reason"] not in {None, "revision_gap", "stale_conflict", "event_collision", "terminal_conflict", "privacy_rejected", "capacity_exceeded", "integrity_failed"}:
            _reject("health_reason_invalid")
        if value["disk_budget_state"] not in {"not_measured", "within_budget", "warning", "disabled"} or value["evidence_freshness"] not in {"fixture_only", "fresh", "stale", "unknown"}:
            _reject("health_evidence_invalid")
    return kind


def validate_event_size_bytes(event_bytes: bytes) -> int:
    if not isinstance(event_bytes, bytes):
        _reject("event_bytes_invalid")
    if len(event_bytes) > EVENT_LIMIT_BYTES:
        _reject("event_size_exceeded")
    return len(event_bytes)


def validate_pending_capacity(pending_receipts: Any) -> dict[str, Any]:
    if not _integer(pending_receipts, 0, 100000):
        _reject("pending_count_invalid")
    if pending_receipts > PENDING_RECEIPT_LIMIT:
        return {"disposition": "parked", "reason": "capacity_exceeded"}
    return {"disposition": "accepted", "reason": None}


def decide_receipt(receipt: Mapping[str, Any], stored: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return exactly one frozen replay/CAS decision without mutation or repair."""
    _validate_receipt(receipt)
    if stored is None:
        if receipt["expected_revision"] == 0 and receipt["revision"] == 1:
            return {"decision": "insert", "disposition": "accepted", "idempotent": False, "emit_event": True, "emit_delivery": True}
        return {"decision": "revision_gap", "disposition": "parked", "idempotent": False, "emit_event": False, "emit_delivery": False}
    _closed(stored, STORED_FIELDS, "stored_fields_invalid")
    if not _integer(stored["revision"], 1, 100000) or not isinstance(stored["terminal"], bool):
        _reject("stored_state_invalid")
    if not _string(stored["event_id"], 1, 128, _OPAQUE_ID) or not _DIGEST.fullmatch(stored["live_commit_digest"] or ""):
        _reject("stored_state_invalid")
    same = stored["event_id"] == receipt["event_id"] and stored["live_commit_digest"] == receipt["live_commit_digest"]
    if stored["revision"] == receipt["revision"] and same:
        return {"decision": "exact_replay", "disposition": "accepted", "idempotent": True, "emit_event": False, "emit_delivery": False}
    if stored["terminal"]:
        return {"decision": "terminal_conflict", "disposition": "parked", "idempotent": False, "emit_event": False, "emit_delivery": False}
    if stored["revision"] == receipt["revision"]:
        return {"decision": "event_collision", "disposition": "parked", "idempotent": False, "emit_event": False, "emit_delivery": False}
    if stored["revision"] == receipt["expected_revision"]:
        return {"decision": "advance", "disposition": "accepted", "idempotent": False, "emit_event": True, "emit_delivery": True}
    if stored["revision"] < receipt["expected_revision"]:
        return {"decision": "revision_gap", "disposition": "parked", "idempotent": False, "emit_event": False, "emit_delivery": False}
    return {"decision": "stale_conflict", "disposition": "parked", "idempotent": False, "emit_event": False, "emit_delivery": False}
