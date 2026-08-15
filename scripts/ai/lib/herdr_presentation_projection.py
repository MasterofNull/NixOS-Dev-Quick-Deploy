"""Pure, hermetic projection for ``aq.herdr.presentation.v1``.

This module deliberately accepts already-normalized values only.  It performs
no I/O, clock, environment, process, HERDR, adapter, or mutation operation.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA_VERSION = "aq.herdr.presentation.v1"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_REF = re.compile(r"^aqref:v1:[A-Za-z0-9._-]+:[A-Za-z0-9._-]{22,128}$")
_CREDENTIAL = re.compile(r"^(?:AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|Bearer[ ._-]|(?:api[_-]?key|token|secret)[=:])", re.IGNORECASE)
_COUNT_NAMES = ("managed", "unmanaged", "orphaned", "dark", "stale", "drifted", "unknown")
_COVERAGE_KNOWN = frozenset({
    "healthy", "known", "fresh", "enabled", "disabled", "degraded", "compatible",
    "incompatible", "match", "mismatch", "pending", "succeeded", "failed", "stale",
    "conflict", "reachable", "unreachable", "present", "absent", "expected",
    "unexpected", "ok", "denied", "attached", "detached",
})


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    """Return the single canonical JSON representation used for replay hashes."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")


def projection_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _unknown_count() -> dict[str, Any]:
    return {"state": "unknown", "value": None}


def _default(envelope: Mapping[str, Any]) -> dict[str, Any]:
    revision = envelope.get("observation_revision", "unknown")
    generated_at = envelope.get("generated_at", "unknown")
    expected = envelope.get("static_expected", {})
    if not isinstance(expected, Mapping) or set(expected) - {"version", "protocol", "layout_revision", "layout_digest", "session_count"}:
        raise ValueError("static_expected_invalid")
    return {
        "schema_version": SCHEMA_VERSION,
        "observation_revision": _token(revision),
        "generated_at": _token(generated_at),
        "freshness": {"state": "unknown", "observation_age": "unknown", "reconciliation_age": "unknown"},
        "source_health": [{"observer": "herdr-observer", "authorization": "unauthorized", "state": "unavailable", "reason": "no_authorized_observer"}],
        "source_digests": [],
        "configured": {"state": "unknown", "reason": "no_authorized_observer"},
        "runtime": {"state": "unknown", "reason": "no_authorized_observer", "evidence_ref": None},
        "socket": {"state": "unknown", "presence": "unknown", "type": "unknown", "permission": "unknown", "peer": "unknown", "evidence_ref": None},
        "session": {"expected_count": _count(expected.get("session_count", {"state":"unknown","value":None})), "observed_count": _unknown_count(), "refs": []},
        "version": {"expected": _optional_token(expected.get("version")), "observed": None, "compatibility": "unknown"},
        "protocol": {"expected": _optional_token(expected.get("protocol")), "observed": None, "compatibility": "unknown"},
        "panes": [],
        "layout": {"expected_revision": _optional_token(expected.get("layout_revision")), "expected_digest": _optional_digest(expected.get("layout_digest")), "observed_revision": None, "observed_digest": None, "observation_delta": "unknown", "reason": "no_authorized_observer", "evidence_ref": None},
        "counts": {name: _unknown_count() for name in _COUNT_NAMES},
        "reconciliation": {"state": "unknown", "last_revision": None, "last_digest": None, "age": "unknown", "evidence_ref": None},
        "coverage": {"known": 0, "unknown": 1, "unavailable": 1, "overflow": 0},
        "policy": {"schema_revision": "v1", "observer_policy_revision": "v1", "redaction_revision": "v1", "bounds_revision": "v1", "age_policy_revision": "v1", "serializer_revision": "v1", "digest_algorithm": "sha256"},
    }


def _token(value: Any) -> str:
    if not isinstance(value, str) or not _TOKEN.fullmatch(value) or _CREDENTIAL.search(value):
        raise ValueError("token_invalid")
    return value


def _optional_token(value: Any) -> str | None:
    return None if value is None else _token(value)


def _optional_digest(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError("digest_invalid")
    return value


def _ref(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _REF.fullmatch(value):
        raise ValueError("reference_invalid")
    return value


def _count(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"state", "value"}:
        raise ValueError("count_invalid")
    state = value["state"]
    number = value["value"]
    if state not in {"known", "unknown", "unavailable"}:
        raise ValueError("count_state_invalid")
    if state == "known" and (not isinstance(number, int) or isinstance(number, bool) or number < 0 or number > 4096):
        raise ValueError("count_value_invalid")
    if state != "known" and number is not None:
        raise ValueError("count_unknown_value_invalid")
    return {"state": state, "value": number}


def _coverage_states(result: Mapping[str, Any]) -> list[str]:
    """Return every coverage-relevant state emitted by the closed profile.

    The profile includes identifiers and evidence leaves that intentionally have no
    health truth.  Every emitted state-bearing observer, socket, session, pane,
    layout, reconciliation, and count leaf is included exactly once here.
    """
    states = [
        item["state"] for item in result["source_health"]
    ] + [
        result["configured"]["state"], result["runtime"]["state"],
        result["freshness"]["state"], result["reconciliation"]["state"],
        result["version"]["compatibility"], result["protocol"]["compatibility"],
        result["layout"]["observation_delta"],
        result["session"]["expected_count"]["state"],
        result["session"]["observed_count"]["state"],
        result["socket"]["state"], result["socket"]["presence"],
        result["socket"]["type"], result["socket"]["permission"],
        result["socket"]["peer"],
    ]
    states += [item["health"] for item in result["session"]["refs"]]
    states += [item["detach_state"] for item in result["session"]["refs"]]
    states += [item["health"] for item in result["panes"]]
    states += [item["freshness"] for item in result["panes"]]
    states += [item["observation_delta"] for item in result["panes"]]
    states += [item["state"] for item in result["counts"].values()]
    return states


def _finalize(result: dict[str, Any]) -> dict[str, Any]:
    """Apply the sole pure coverage reducer immediately before every return."""
    states = _coverage_states(result)
    result["coverage"] = {
        "known": sum(state in _COVERAGE_KNOWN for state in states),
        "unknown": sum(state == "unknown" for state in states),
        "unavailable": sum(state == "unavailable" for state in states),
        "overflow": 0,
    }
    return result


def _validated_observation(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a complete output-shaped observation without accepting raw content."""
    allowed = {"freshness", "configured", "runtime", "socket", "session", "version", "protocol", "panes", "layout", "counts", "reconciliation", "coverage"}
    if not isinstance(value, Mapping) or set(value) - allowed:
        raise ValueError("observation_shape_invalid")
    result: dict[str, Any] = {}
    if "freshness" in value:
        x = value["freshness"]
        if not isinstance(x, Mapping) or set(x) != {"state", "observation_age", "reconciliation_age"} or x["state"] not in {"fresh", "stale", "unknown", "unavailable"}:
            raise ValueError("freshness_invalid")
        result["freshness"] = {"state": x["state"], "observation_age": _token(x["observation_age"]), "reconciliation_age": _token(x["reconciliation_age"])}
    if "configured" in value:
        x = value["configured"]
        if not isinstance(x, Mapping) or set(x) != {"state", "reason"} or x["state"] not in {"enabled", "disabled", "unknown", "unavailable", "degraded"}:
            raise ValueError("configured_invalid")
        result["configured"] = {"state": x["state"], "reason": _token(x["reason"])}
    for name, states in (("runtime", {"healthy", "degraded", "unavailable", "unknown"}),):
        if name in value:
            x = value[name]
            if not isinstance(x, Mapping) or set(x) != {"state", "reason", "evidence_ref"} or x["state"] not in states:
                raise ValueError("runtime_invalid")
            result[name] = {"state": x["state"], "reason": _token(x["reason"]), "evidence_ref": _ref(x["evidence_ref"])}
    if "counts" in value:
        x = value["counts"]
        if not isinstance(x, Mapping) or set(x) != set(_COUNT_NAMES):
            raise ValueError("counts_invalid")
        result["counts"] = {name: _count(x[name]) for name in _COUNT_NAMES}
    if "coverage" in value:
        raise ValueError("coverage_is_pure_derived")
    if "socket" in value:
        x=value["socket"]
        if not isinstance(x,Mapping) or set(x)!={"state","presence","type","permission","peer","evidence_ref"} or x["state"] not in {"known","unknown","unavailable","stale","conflict"} or x["presence"] not in {"present","absent","unknown","unavailable"} or x["type"] not in {"expected","unexpected","unknown"} or x["permission"] not in {"ok","denied","unknown"} or x["peer"] not in {"reachable","unreachable","unknown"}: raise ValueError("socket_invalid")
        result["socket"]={**x,"evidence_ref":_ref(x["evidence_ref"])}
    if "session" in value:
        x=value["session"]
        if not isinstance(x,Mapping) or set(x)!={"observed_count","refs"} or not isinstance(x["refs"],list) or len(x["refs"])>64: raise ValueError("session_invalid")
        refs=[]
        for item in x["refs"]:
            if not isinstance(item,Mapping) or set(item)!={"session_ref","health","detach_state"} or _ref(item["session_ref"]) is None or item["health"] not in {"healthy","degraded","unknown","unavailable"} or item["detach_state"] not in {"attached","detached","unknown"}: raise ValueError("session_ref_invalid")
            refs.append(dict(item))
        if len({item["session_ref"] for item in refs}) != len(refs):
            raise ValueError("duplicate_session_ref")
        result["session"]={"expected_count":_unknown_count(),"observed_count":_count(x["observed_count"]),"refs":refs}
    for name in ("version","protocol"):
        if name in value:
            x=value[name]
            if not isinstance(x,Mapping) or set(x)!={"observed","compatibility"} or x["compatibility"] not in {"compatible","incompatible","unknown","unavailable"}: raise ValueError(name+"_invalid")
            result[name]={"expected":None,"observed":_optional_token(x["observed"]),"compatibility":x["compatibility"]}
    if "panes" in value:
        x=value["panes"]
        if not isinstance(x,list) or len(x)>64: raise ValueError("panes_invalid")
        panes=[]
        for item in x:
            if not isinstance(item,Mapping) or set(item)!={"pane_ref","role","work_ref","health","freshness","observed_state","observation_delta"} or _ref(item["pane_ref"]) is None or item["health"] not in {"healthy","degraded","unknown","unavailable"} or item["freshness"] not in {"fresh","stale","unknown","unavailable"} or item["observation_delta"] not in {"match","mismatch","unknown"}: raise ValueError("pane_invalid")
            panes.append({**item,"role":_token(item["role"]),"work_ref":_ref(item["work_ref"]),"observed_state":_optional_token(item["observed_state"]),"expected_state":None})
        if len({item["pane_ref"] for item in panes}) != len(panes):
            raise ValueError("duplicate_pane_ref")
        result["panes"]=panes
    if "layout" in value:
        x=value["layout"]
        if not isinstance(x,Mapping) or set(x)!={"observed_revision","observed_digest","observation_delta","reason","evidence_ref"} or x["observation_delta"] not in {"match","mismatch","unknown"}: raise ValueError("layout_invalid")
        result["layout"]={"expected_revision":None,"expected_digest":None,"observed_revision":_optional_token(x["observed_revision"]),"observed_digest":_optional_digest(x["observed_digest"]),"observation_delta":x["observation_delta"],"reason":_token(x["reason"]),"evidence_ref":_ref(x["evidence_ref"])}
    if "reconciliation" in value:
        x=value["reconciliation"]
        if not isinstance(x,Mapping) or set(x)!={"state","last_revision","last_digest","age","evidence_ref"} or x["state"] not in {"pending","succeeded","failed","unknown","unavailable"}: raise ValueError("reconciliation_invalid")
        result["reconciliation"]={"state":x["state"],"last_revision":_optional_token(x["last_revision"]),"last_digest":_optional_digest(x["last_digest"]),"age":_token(x["age"]),"evidence_ref":_ref(x["evidence_ref"])}
    return result


def _safe_dimension(value: Any) -> Any:
    """Reject unbounded/raw transport content while retaining normalized contract values."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value < 0 or value > 4096:
            raise ValueError("dimension_integer_invalid")
        return value
    if isinstance(value, str):
        # Contract tokens and aqrefs are the only strings permitted in P0B.
        if _TOKEN.fullmatch(value) or _DIGEST.fullmatch(value) or _REF.fullmatch(value):
            return value
        raise ValueError("dimension_string_invalid")
    if isinstance(value, list):
        if len(value) > 64:
            raise ValueError("dimension_list_too_large")
        return [_safe_dimension(item) for item in value]
    if isinstance(value, Mapping):
        if len(value) > 16 or any(not isinstance(k, str) or not _TOKEN.fullmatch(k) for k in value):
            raise ValueError("dimension_object_invalid")
        return {key: _safe_dimension(item) for key, item in value.items()}
    raise ValueError("dimension_type_invalid")


def project(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Project one normalized observation envelope into a closed presentation object.

    Missing or unauthorized input is intentionally represented as unavailable/unknown;
    it is never filled from configuration or inferred from desired layout.
    """
    if not isinstance(envelope, Mapping) or set(envelope) - {"sample_id", "sampled_at_bucket", "observation_revision", "generated_at", "policy_revision", "static_expected", "observer", "observation", "reference_bindings"}:
        raise ValueError("envelope_shape_invalid")
    if "sample_id" in envelope:
        sample_id = _token(envelope["sample_id"])
        if _token(envelope.get("sampled_at_bucket")) != _token(envelope.get("generated_at")):
            raise ValueError("sample_bucket_incoherent")
        if "policy_revision" not in envelope:
            raise ValueError("policy_revision_missing")
    result = _default(envelope)
    bindings = envelope.get("reference_bindings", [])
    if not isinstance(bindings, list) or len(bindings) > 64:
        raise ValueError("reference_bindings_invalid")
    seen: dict[str, tuple[str, str]] = {}
    replacements: dict[str, tuple[str, str]] = {}
    for binding in bindings:
        if not isinstance(binding, Mapping) or set(binding) != {"ref", "issuer_revision", "subject_digest", "state", "expiry_bucket", "replacement_ref", "replacement_subject_digest"}:
            raise ValueError("reference_binding_shape_invalid")
        ref = _ref(binding["ref"])
        if ref is None or binding["state"] not in {"active", "revoked", "expired", "superseded"} or binding["issuer_revision"] == "unknown" or not _TOKEN.fullmatch(binding["issuer_revision"]) or binding["expiry_bucket"] not in {"current", "future", "past", "expired"} or (binding["state"] == "active" and binding["expiry_bucket"] not in {"current", "future"}):
            raise ValueError("reference_lifecycle_invalid")
        digest = _optional_digest(binding["subject_digest"])
        if digest is None or ref in seen:
            raise ValueError("reference_subject_collision")
        seen[ref] = (digest, binding["state"])
        replacement = _ref(binding["replacement_ref"])
        replacement_digest = _optional_digest(binding["replacement_subject_digest"])
        if binding["state"] == "superseded" and (replacement is None or replacement_digest is None or replacement == ref):
            raise ValueError("reference_supersession_invalid")
        if binding["state"] == "superseded":
            replacements[ref] = (replacement, replacement_digest)
        if binding["state"] != "superseded" and (replacement is not None or replacement_digest is not None):
            raise ValueError("reference_replacement_invalid")
    for ref, (replacement, digest) in replacements.items():
        cursor, traversed = ref, set()
        while cursor in replacements:
            if cursor in traversed:
                raise ValueError("reference_supersession_cycle")
            traversed.add(cursor)
            cursor = replacements[cursor][0]
        if replacement not in seen or seen[replacement][0] != digest or seen[replacement][1] != "active":
            raise ValueError("reference_replacement_target_invalid")
    static_expected = {"version": result["version"]["expected"], "protocol": result["protocol"]["expected"], "layout_revision": result["layout"]["expected_revision"], "layout_digest": result["layout"]["expected_digest"], "session_count": result["session"]["expected_count"]}
    if "sample_id" in envelope:
        result["observation_revision"] = _token(envelope["observation_revision"]) + ":" + sample_id
        result["policy"]["observer_policy_revision"] = _token(envelope["policy_revision"])
    # Bind every accepted normalized input into the output identity, including
    # unauthorized observer metadata; this is not an authority upgrade.
    input_hash = hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()
    result["observation_revision"] = result["observation_revision"] + ":" + input_hash
    observer = envelope.get("observer")
    if observer is None:
        return _finalize(result)
    if not isinstance(observer, Mapping) or set(observer) != {"id", "authorization", "state", "reason", "revision", "digest"}:
        raise ValueError("observer_shape_invalid")
    authorization = observer["authorization"]
    if authorization not in {"authorized", "unauthorized", "unknown"} or observer["state"] not in {"known", "unknown", "unavailable", "stale", "conflict"}:
        raise ValueError("observer_state_invalid")
    health = {"observer": _token(observer["id"]), "authorization": authorization, "state": observer["state"], "reason": _token(observer["reason"])}
    result["source_health"] = [health]
    if authorization == "authorized" and observer["state"] == "known" and "sample_id" not in envelope:
        raise ValueError("coherent_sample_required")
    if authorization != "authorized" or observer["state"] != "known":
        return _finalize(result)
    result["source_digests"] = [{"observer": health["observer"], "revision": _token(observer["revision"]), "digest": _optional_digest(observer["digest"])}]
    if result["source_digests"][0]["digest"] is None:
        raise ValueError("authorized_digest_required")
    observation = envelope.get("observation")
    if observation is None:
        result["source_health"][0]["state"] = "unknown"
        result["source_health"][0]["reason"] = "observation_missing"
        return _finalize(result)
    result.update(_validated_observation(observation))
    result["version"]["expected"] = static_expected["version"]
    result["protocol"]["expected"] = static_expected["protocol"]
    result["layout"]["expected_revision"] = static_expected["layout_revision"]
    result["layout"]["expected_digest"] = static_expected["layout_digest"]
    result["session"]["expected_count"] = static_expected["session_count"]
    for pane in result["panes"]:
        if pane["observation_delta"] == "match" and (pane["expected_state"] is None or pane["observed_state"] is None or pane["expected_state"] != pane["observed_state"]):
            raise ValueError("pane_match_without_expected_identity")
    for name in ("version", "protocol"):
        item = result[name]
        if item["compatibility"] == "compatible" and (item["expected"] is None or item["observed"] is None or item["expected"] != item["observed"]):
            raise ValueError(name + "_compatible_without_match")
    layout = result["layout"]
    if layout["observation_delta"] == "match" and (layout["expected_revision"] is None or layout["expected_digest"] is None or layout["observed_revision"] is None or layout["observed_digest"] is None or layout["expected_revision"] != layout["observed_revision"] or layout["expected_digest"] != layout["observed_digest"]):
        raise ValueError("layout_match_without_identity")
    evidence_refs = [result["runtime"]["evidence_ref"], result["socket"]["evidence_ref"], result["layout"]["evidence_ref"], result["reconciliation"]["evidence_ref"]]
    evidence_refs = [item for item in evidence_refs if item is not None]
    if len(set(evidence_refs)) != len(evidence_refs):
        raise ValueError("duplicate_evidence_ref")
    for ref in evidence_refs + [item["session_ref"] for item in result["session"]["refs"]] + [item["pane_ref"] for item in result["panes"]] + [item["work_ref"] for item in result["panes"] if item["work_ref"] is not None]:
        if ref not in seen or seen[ref][1] != "active":
            raise ValueError("unbound_output_reference")
    return _finalize(result)
