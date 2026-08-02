"""Pure L3-P0 provenance-shadow kernel; intentionally no I/O or runtime hooks."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Mapping, Sequence

SCHEMA_ID = "aq.local-inference-trusted-fact-envelope/1.0"
PRODUCER_SET_SCHEMA_ID = "aq.local-inference-producer-revision-set/1.0"
REQUEST_SCHEMA_ID = "aq.local-inference-shadow-request-projection/1.0"
PLAN_SCHEMA_ID = "aq.local-inference-resolved-shadow-plan/1.0"
METADATA_SCHEMA_ID = "aq.local-inference-shadow-observation-metadata/1.0"
UNAVAILABLE_SCHEMA_ID = "aq.local-inference-trusted-fact-unavailable/1.0"
OBSERVATION_SCHEMA_ID = "aq.local-inference-shadow-observation/1.0"
REQUIRED_FACT_TYPES = (
    "authenticated_principal", "role", "approval_or_lease", "profile",
    "eligibility", "budget", "path", "clock",
)
FACT_STATUSES = ("available", "unavailable")
UNAVAILABLE_CATEGORIES = ("missing", "producer_unavailable")
HEX_DIGEST_LENGTH = 64


class ProvenanceError(ValueError):
    """Closed-contract input is malformed or not admissible."""


def _normalize_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise ProvenanceError("floating point is not canonical")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list) or isinstance(value, tuple):
        return [_normalize_json(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProvenanceError("JSON object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ProvenanceError("duplicate normalized key")
            normalized[normalized_key] = _normalize_json(item)
        return normalized
    raise ProvenanceError("non-JSON value")


def canonical_json_bytes(value: Any) -> bytes:
    """UTF-8 NFC JSON with recursive key sorting and shortest separators."""
    normalized = _normalize_json(value)
    try:
        text = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ProvenanceError("non-canonical JSON") from exc
    return text.encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def parse_json_strict(text: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            normalized = unicodedata.normalize("NFC", key)
            if normalized in result:
                raise ProvenanceError("duplicate JSON key")
            result[normalized] = value
        return result
    try:
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_constant=lambda value: (_ for _ in ()).throw(
                               ProvenanceError("non-finite JSON number: " + value)))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ProvenanceError("invalid JSON") from exc
    return _normalize_json(value)


def _closed(value: Mapping[str, Any], required: set[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != required:
        raise ProvenanceError("closed object mismatch")


def _bounded_string(value: Any, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ProvenanceError("invalid " + name)
    if value != unicodedata.normalize("NFC", value):
        raise ProvenanceError("non-NFC " + name)
    return value


def _digest(value: Any, name: str) -> str:
    text = _bounded_string(value, name, HEX_DIGEST_LENGTH)
    if len(text) != HEX_DIGEST_LENGTH or any(char not in "0123456789abcdef" for char in text):
        raise ProvenanceError("invalid " + name)
    return text


def validate_trusted_fact(fact: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_id", "fact_type", "category", "value_digest", "producer",
                "producer_revision", "evidence_ref", "status"}
    _closed(fact, required)
    if fact.get("schema_id") != SCHEMA_ID or fact.get("fact_type") not in REQUIRED_FACT_TYPES:
        raise ProvenanceError("invalid trusted fact envelope")
    if fact.get("status") not in FACT_STATUSES:
        raise ProvenanceError("invalid fact status")
    for name in ("fact_type", "category", "producer", "producer_revision", "evidence_ref"):
        _bounded_string(fact[name], name)
    _digest(fact["value_digest"], "value_digest")
    return dict(fact)


def validate_producer_revision_set(value: Mapping[str, Any]) -> dict[str, Any]:
    _closed(value, {"schema_id", "producers"})
    if value.get("schema_id") != PRODUCER_SET_SCHEMA_ID or not isinstance(value.get("producers"), list):
        raise ProvenanceError("invalid producer revision set")
    producers: list[dict[str, str]] = []
    for raw in value["producers"]:
        _closed(raw, {"producer", "revision"})
        producer = _bounded_string(raw["producer"], "producer")
        revision = _bounded_string(raw["revision"], "revision")
        producers.append({"producer": producer, "revision": revision})
    canonical = sorted(producers, key=lambda item: (item["producer"], item["revision"]))
    if producers != canonical or len({(p["producer"], p["revision"]) for p in producers}) != len(producers):
        raise ProvenanceError("producer revision set must be unique and sorted")
    return {"schema_id": PRODUCER_SET_SCHEMA_ID, "producers": producers}


def validate_request_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    _closed(value, {"schema_id", "request_ref", "trace_ref", "legacy_plan_digest"})
    if value.get("schema_id") != REQUEST_SCHEMA_ID:
        raise ProvenanceError("invalid request projection")
    _bounded_string(value["request_ref"], "request_ref")
    _bounded_string(value["trace_ref"], "trace_ref")
    _digest(value["legacy_plan_digest"], "legacy_plan_digest")
    return dict(value)


def _provenance_ref(raw: Mapping[str, Any]) -> dict[str, Any]:
    required = {"fact_type", "producer", "producer_revision", "evidence_ref", "value_digest"}
    _closed(raw, required)
    if raw.get("fact_type") not in REQUIRED_FACT_TYPES:
        raise ProvenanceError("invalid provenance fact type")
    for name in ("fact_type", "producer", "producer_revision", "evidence_ref"):
        _bounded_string(raw[name], name)
    _digest(raw["value_digest"], "value_digest")
    return dict(raw)


def validate_resolved_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_id", "request_projection_digest", "producer_revision_set_digest",
                "provenance_vector_digest", "compatibility_adapter", "decision",
                "divergence_findings", "provenance_refs", "shadow",
                "non_authoritative", "no_live_cutover"}
    _closed(plan, required)
    if plan.get("schema_id") != PLAN_SCHEMA_ID or plan.get("compatibility_adapter") != "none":
        raise ProvenanceError("invalid resolved plan")
    if plan.get("decision") != "shadow_only" or plan.get("divergence_findings") != []:
        raise ProvenanceError("invalid shadow decision")
    if (plan.get("shadow"), plan.get("non_authoritative"), plan.get("no_live_cutover")) != (True, True, True):
        raise ProvenanceError("authority flags changed")
    for name in ("request_projection_digest", "producer_revision_set_digest", "provenance_vector_digest"):
        _digest(plan[name], name)
    if not isinstance(plan.get("provenance_refs"), list) or len(plan["provenance_refs"]) != len(REQUIRED_FACT_TYPES):
        raise ProvenanceError("incomplete provenance refs")
    refs = [_provenance_ref(item) for item in plan["provenance_refs"]]
    if [item["fact_type"] for item in refs] != list(REQUIRED_FACT_TYPES):
        raise ProvenanceError("unordered provenance refs")
    if canonical_digest(refs) != plan["provenance_vector_digest"]:
        raise ProvenanceError("provenance digest mismatch")
    return dict(plan)


def _trusted_fact_unavailable(fact_type: str, category: str, evidence_ref: str) -> dict[str, Any]:
    if fact_type not in REQUIRED_FACT_TYPES or category not in UNAVAILABLE_CATEGORIES:
        raise ProvenanceError("invalid unavailable classification")
    _bounded_string(evidence_ref, "evidence_ref")
    return {"schema_id": UNAVAILABLE_SCHEMA_ID, "typed_error": "trusted_fact_unavailable",
            "failing_fact_type": fact_type, "category": category,
            "evidence_ref": evidence_ref, "shadow": True,
            "non_authoritative": True, "no_live_cutover": True}


def resolve_shadow_plan(facts: Sequence[Mapping[str, Any]], request_projection: Mapping[str, Any],
                        producer_revision_set: Mapping[str, Any]) -> dict[str, Any]:
    request = validate_request_projection(request_projection)
    revisions = validate_producer_revision_set(producer_revision_set)
    by_type: dict[str, dict[str, Any]] = {}
    for raw in facts:
        item = validate_trusted_fact(raw)
        if item["fact_type"] in by_type:
            raise ProvenanceError("duplicate fact type")
        by_type[item["fact_type"]] = item
    for fact_type in REQUIRED_FACT_TYPES:
        item = by_type.get(fact_type)
        if item is None:
            return _trusted_fact_unavailable(fact_type, "missing", "fact:" + fact_type)
        if item["status"] == "unavailable":
            return _trusted_fact_unavailable(fact_type, "producer_unavailable", item["evidence_ref"])
    expected = [(item["producer"], item["producer_revision"]) for item in by_type.values()]
    actual = [(item["producer"], item["revision"]) for item in revisions["producers"]]
    if len(expected) != len(set(expected)) or sorted(expected) != actual:
        raise ProvenanceError("producer revision set does not exactly bind facts")
    refs = [{"fact_type": name, "producer": by_type[name]["producer"],
             "producer_revision": by_type[name]["producer_revision"],
             "evidence_ref": by_type[name]["evidence_ref"],
             "value_digest": by_type[name]["value_digest"]} for name in REQUIRED_FACT_TYPES]
    plan = {"schema_id": PLAN_SCHEMA_ID,
            "request_projection_digest": canonical_digest(request),
            "producer_revision_set_digest": canonical_digest(revisions),
            "provenance_vector_digest": canonical_digest(refs),
            "compatibility_adapter": "none", "decision": "shadow_only",
            "divergence_findings": [], "provenance_refs": refs,
            "shadow": True, "non_authoritative": True, "no_live_cutover": True}
    return validate_resolved_plan(plan)


def validate_observation_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_id", "observation_id", "request_ref", "trace_ref",
                "shadow_sequence", "observed_at"}
    _closed(metadata, required)
    if metadata.get("schema_id") != METADATA_SCHEMA_ID:
        raise ProvenanceError("invalid observation metadata")
    for name in ("observation_id", "request_ref", "trace_ref", "observed_at"):
        _bounded_string(metadata[name], name)
    if not isinstance(metadata["shadow_sequence"], int) or isinstance(metadata["shadow_sequence"], bool) or metadata["shadow_sequence"] < 0:
        raise ProvenanceError("invalid shadow sequence")
    return dict(metadata)


def build_shadow_observation(metadata: Mapping[str, Any], plan: Mapping[str, Any],
                             legacy_observation_digest: str) -> dict[str, Any]:
    meta = validate_observation_metadata(metadata)
    resolved = validate_resolved_plan(plan)
    legacy_digest = _digest(legacy_observation_digest, "legacy_observation_digest")
    body = {"schema_id": OBSERVATION_SCHEMA_ID,
            "observation_id": meta["observation_id"],
            "request_ref": meta["request_ref"], "trace_ref": meta["trace_ref"],
            "shadow_sequence": meta["shadow_sequence"], "observed_at": meta["observed_at"],
            "producer": "l3-p0-kernel", "producer_revision": "1",
            "resolved_plan_digest": canonical_digest(resolved),
            "legacy_observation_digest": legacy_digest,
            "compatibility_adapter": resolved["compatibility_adapter"],
            "decision": resolved["decision"], "typed_error": None,
            "divergence_findings": resolved["divergence_findings"],
            "provenance_refs": resolved["provenance_refs"],
            "shadow": True, "non_authoritative": True, "no_live_cutover": True}
    return {**body, "observation_digest": canonical_digest(body)}
