"""Pure, closed H2A-P0 normalized-envelope resolver (no adapters or I/O)."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "aq.operator-context.v1"
SERIALIZER_REVISION = "operator-context-canonical-json.v2"
MAX_ITEMS = 64
REF_RE = re.compile(r"^aqref:v1:[a-z][a-z0-9_-]{0,31}:[a-f0-9]{32,128}$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
REV_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
DIGEST_RE = re.compile(r"^[a-f0-9]{64}$")
TEXT_RE = re.compile(r"^[A-Za-z0-9 _.,:;()\-]{1,160}$")
CREDENTIAL_RE = re.compile(r"(?:AKIA[0-9A-Z]{16}|bearer |begin private key)", re.IGNORECASE)
# Text is presentation-only: reject compact shell/control syntax even where
# each character itself belongs to the conservative display alphabet.
# A display field may contain prose, but never an operator expression or a
# command-head followed by an argument.  This is a category boundary, rather
# than a deny-list for individual examples: privilege, service, interpreter,
# filesystem, network, package, VCS, container, and shell command families.
SHELL_TOKEN_RE = re.compile(r"(?:\$\(|`|[;|&<>])")
OBJECTIVE_RE = re.compile(r"^[A-Z][A-Za-z0-9 _.,:()\-]{0,159}$")
ENVELOPES = (
    "program_workflow_facts", "exclusive_lease_facts", "independent_review_facts",
    "agent_progress_facts", "canonical_attention_facts", "learning_facts",
)
STATES = {"fresh", "stale", "unknown", "unavailable", "degraded", "conflict"}
LIFECYCLES = {"active", "revoked", "expired", "superseded"}
ISSUERS = {"canonical", "unknown"}
BASE = {"sample_id", "sampled_at_bucket", "adapter_revision", "digest", "state", "issuer", "issuer_revision", "subject_digest", "reference_status", "expires_at_bucket", "expiry_evidence", "replacement_ref", "replacement_subject_digest", "supersession_chain"}
EXTRA = {
    "program_workflow_facts": {"mission", "work"},
    "exclusive_lease_facts": set(),
    "independent_review_facts": {"verdict"},
    "agent_progress_facts": {"progress"},
    "canonical_attention_facts": {"attention"},
    "learning_facts": {"accepted_count", "regression_count"},
}


class ProjectionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    """The sole byte serialization: UTF-8, compact, and mapping-order independent."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _text(value: Any, field: str, *, unknown: bool = True) -> str:
    if unknown and value in (None, "unknown"):
        return "unknown"
    if not isinstance(value, str) or not TEXT_RE.fullmatch(value) or CREDENTIAL_RE.search(value) or SHELL_TOKEN_RE.search(value):
        raise ProjectionError(f"{field}_unsafe")
    return value


def _objective(value: Any) -> str:
    if value in (None, "unknown"):
        return "unknown"
    if not isinstance(value, str) or not OBJECTIVE_RE.fullmatch(value) or CREDENTIAL_RE.search(value) or SHELL_TOKEN_RE.search(value):
        raise ProjectionError("objective_unsafe")
    return value


def _ref(value: Any, field: str, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not REF_RE.fullmatch(value):
        raise ProjectionError(f"{field}_reference")
    return value


def _count(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {"state": "unknown", "value": None}
    if not isinstance(value, dict) or set(value) != {"state", "value"}:
        raise ProjectionError(f"{field}_count_shape")
    state, number = value["state"], value["value"]
    if state not in {"known", "unknown", "unavailable"}:
        raise ProjectionError(f"{field}_count_state")
    if state == "known":
        if not isinstance(number, int) or isinstance(number, bool) or not 0 <= number <= 65535:
            raise ProjectionError(f"{field}_count_value")
    elif number is not None:
        raise ProjectionError(f"{field}_unknown_count_value")
    return {"state": state, "value": number}


def _bucket(value: Any, field: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"b[0-9]{1,4}", value):
        raise ProjectionError(f"{field}_bucket")
    return int(value[1:])


def _envelope(facts: dict[str, Any], name: str) -> dict[str, Any]:
    value = facts.get(name)
    if not isinstance(value, dict) or set(value) != BASE | EXTRA[name]:
        raise ProjectionError(f"{name}_closed_shape")
    if not ID_RE.fullmatch(str(value["sample_id"])) or not REV_RE.fullmatch(str(value["adapter_revision"])):
        raise ProjectionError(f"{name}_identity")
    _bucket(value["sampled_at_bucket"], name)
    if not isinstance(value["digest"], str) or not DIGEST_RE.fullmatch(value["digest"]):
        raise ProjectionError(f"{name}_digest")
    if value["state"] not in STATES or value["issuer"] not in ISSUERS or value["reference_status"] not in LIFECYCLES:
        raise ProjectionError(f"{name}_category")
    if value["issuer"] == "unknown" or value["issuer_revision"] == "unknown" or not REV_RE.fullmatch(str(value["issuer_revision"])):
        raise ProjectionError(f"{name}_reference_lifecycle")
    if value["subject_digest"] != value["digest"] or not DIGEST_RE.fullmatch(str(value["subject_digest"])):
        raise ProjectionError(f"{name}_subject_binding")
    if _bucket(value["expires_at_bucket"], name) < _bucket(value["sampled_at_bucket"], name) or _ref(value["expiry_evidence"], f"{name}_expiry_evidence") is None:
        raise ProjectionError(f"{name}_expiry")
    replacement_ref = _ref(value["replacement_ref"], f"{name}_replacement_ref", nullable=True)
    replacement_digest = value["replacement_subject_digest"]
    if replacement_digest is not None and (not isinstance(replacement_digest, str) or not DIGEST_RE.fullmatch(replacement_digest)):
        raise ProjectionError(f"{name}_replacement_binding")
    chain = value["supersession_chain"]
    if not isinstance(chain, list) or len(chain) > MAX_ITEMS or any(not isinstance(token, str) or not DIGEST_RE.fullmatch(token) for token in chain) or len(set(chain)) != len(chain):
        raise ProjectionError(f"{name}_supersession_chain")
    status = value["reference_status"]
    if status in {"revoked", "expired"}:
        raise ProjectionError(f"{name}_reference_lifecycle")
    if status == "active" and (replacement_ref is not None or replacement_digest is not None or chain):
        raise ProjectionError(f"{name}_active_replacement")
    if status == "superseded" and (replacement_ref is None or replacement_digest is None or value["state"] != "unavailable"):
        raise ProjectionError(f"{name}_replacement_binding")
    return value


def _coherent(facts: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    allowed = {"projection_meta_facts", *ENVELOPES}
    if not isinstance(facts, dict) or set(facts) != allowed:
        raise ProjectionError("undeclared_or_missing_input")
    meta = facts["projection_meta_facts"]
    if not isinstance(meta, dict) or set(meta) != {"projection_revision", "generated_at", "policy_revision", "schema_revision", "sample_id", "sampled_at_bucket"}:
        raise ProjectionError("projection_meta_closed_shape")
    if not ID_RE.fullmatch(str(meta["sample_id"])) or _bucket(meta["sampled_at_bucket"], "meta") < 0:
        raise ProjectionError("projection_meta_sample")
    for key in ("projection_revision", "generated_at", "policy_revision", "schema_revision"):
        _text(meta[key], key, unknown=False)
    envelopes = {name: _envelope(facts, name) for name in ENVELOPES}
    sample_ids = {meta["sample_id"], *(env["sample_id"] for env in envelopes.values())}
    if len(sample_ids) != 1:
        raise ProjectionError("incoherent_sample_id")
    buckets = [_bucket(meta["sampled_at_bucket"], "meta"), *(_bucket(env["sampled_at_bucket"], name) for name, env in envelopes.items())]
    if max(buckets) - min(buckets) > 1:
        raise ProjectionError("incoherent_sample_skew")
    # A digest identifies the content regardless of the adapter revision that
    # transported it; accepting the same digest under two revisions would make
    # the source binding ambiguous.
    digests = [env["digest"] for env in envelopes.values()]
    if len(set(digests)) != len(digests):
        raise ProjectionError("duplicate_source_digest")
    # Supersession is a bounded directed graph of subject digests.  A replaced
    # subject must target another declared subject and no chain may loop.
    graph = {env["subject_digest"]: env["replacement_subject_digest"] for env in envelopes.values() if env["reference_status"] == "superseded"}
    if any(target not in digests for target in graph.values()):
        raise ProjectionError("replacement_subject_unknown")
    for origin in graph:
        seen, cursor = set(), origin
        expected_chain = []
        while cursor in graph:
            if cursor in seen: raise ProjectionError("supersession_cycle")
            seen.add(cursor); cursor = graph[cursor]; expected_chain.append(cursor)
        envelope = next(env for env in envelopes.values() if env["subject_digest"] == origin)
        if envelope["supersession_chain"] != expected_chain:
            raise ProjectionError("supersession_chain_mismatch")
    return envelopes, sha256_hex(facts)


def _state(envelopes: dict[str, dict[str, Any]]) -> str:
    states = [env["state"] for env in envelopes.values()]
    if all(state == "fresh" for state in states):
        return "fresh"
    if "conflict" in states:
        return "conflict"
    if "degraded" in states or "stale" in states:
        return "degraded"
    if all(state == "unavailable" for state in states):
        return "unavailable"
    return "unknown"


def _work(item: Any, verdict: str, progress: dict[str, str]) -> dict[str, Any]:
    if not isinstance(item, dict) or set(item) - {"work_ref", "parent_ref", "child_count", "role", "lane", "slice", "canonical_state", "record_revision", "interaction_mode", "interaction_reason", "blocker", "next_gate"}:
        raise ProjectionError("work_closed_shape")
    mode = item.get("interaction_mode", "unknown")
    if mode not in {"direct", "through_parent", "read_only", "unavailable", "unknown"}:
        raise ProjectionError("work_mode")
    parent = _ref(item.get("parent_ref"), "parent_ref", True)
    if mode == "through_parent" and parent is None:
        raise ProjectionError("through_parent_requires_parent")
    state = item.get("canonical_state", "unknown")
    if state not in {"unknown", "queued", "running", "blocked", "needs_review", "accepted", "done"}:
        raise ProjectionError("work_state")
    work_ref = _ref(item.get("work_ref"), "work_ref")
    return {"work_ref": work_ref, "parent_ref": parent, "child_count": _count({"state": "known", "value": item.get("child_count", 0)}, "child_count"), "role": item.get("role", "unknown") if item.get("role", "unknown") in {"unknown", "implementer", "reviewer", "orchestrator"} else (_ for _ in ()).throw(ProjectionError("work_role")), "lane": item.get("lane", "unknown") if item.get("lane", "unknown") in {"unknown", "local", "remote"} else (_ for _ in ()).throw(ProjectionError("work_lane")), "slice": _text(item.get("slice", "unknown"), "slice"), "canonical_state": "needs_review" if state == "done" and verdict != "accepted" else state, "record_revision": _text(item.get("record_revision", "unknown"), "record_revision"), "interaction_mode": mode, "interaction_reason": _text(item.get("interaction_reason", "unknown"), "interaction_reason"), "progress_age": progress.get(work_ref, "unknown"), "blocker": _text(item.get("blocker", "unknown"), "blocker"), "next_gate": _text(item.get("next_gate", "unknown"), "next_gate"), "allowed_controls": [], "presentation_observation": "unknown", "drift": "unknown"}


def _attention(item: Any) -> dict[str, Any]:
    allowed = {"work_ref", "evidence_ref", "severity", "category", "reason", "recommended_action", "required_authority", "availability", "rank"}
    if not isinstance(item, dict) or set(item) != allowed:
        raise ProjectionError("attention_closed_shape")
    for key, choices in {"severity": {"unknown", "low", "medium", "high", "critical"}, "category": {"unknown", "safety", "review", "blocker", "advisory"}, "recommended_action": {"unknown", "request_review", "inspect_blocker", "defer"}, "required_authority": {"unknown", "reviewer", "owner", "operator"}, "availability": {"available", "through_parent", "read_only", "blocked", "unavailable", "unknown"}}.items():
        if item[key] not in choices:
            raise ProjectionError(f"attention_{key}")
    if not isinstance(item["rank"], int) or isinstance(item["rank"], bool) or not 0 <= item["rank"] <= 65535:
        raise ProjectionError("attention_rank")
    return {"work_ref": _ref(item["work_ref"], "attention_work", True), "evidence_ref": _ref(item["evidence_ref"], "attention_evidence", True), "severity": item["severity"], "category": item["category"], "reason": _text(item["reason"], "attention_reason"), "recommended_action": item["recommended_action"], "required_authority": item["required_authority"], "availability": item["availability"], "rank": item["rank"]}


def project(facts: dict[str, Any]) -> tuple[dict[str, Any], bytes, str]:
    envelopes, input_digest = _coherent(facts)
    meta = facts["projection_meta_facts"]
    overall = _state(envelopes)
    program, review, attention, learning, progress_env = (envelopes["program_workflow_facts"], envelopes["independent_review_facts"], envelopes["canonical_attention_facts"], envelopes["learning_facts"], envelopes["agent_progress_facts"])
    mission = program.get("mission", {}) if program["state"] == "fresh" else {}
    if not isinstance(mission, dict) or set(mission) - {"objective", "workflow_phase", "total", "satisfied", "unknown", "next_gate", "blocker", "reference"}:
        raise ProjectionError("mission_closed_shape")
    raw_work = program.get("work", []) if program["state"] == "fresh" else []
    raw_attention = attention.get("attention", []) if attention["state"] == "fresh" else []
    if not isinstance(raw_work, list) or not isinstance(raw_attention, list) or len(raw_work) > MAX_ITEMS or len(raw_attention) > MAX_ITEMS:
        raise ProjectionError("array_bound")
    # A review that is unavailable, stale, or otherwise non-fresh cannot grant
    # acceptance.  Its embedded verdict is retained only as untrusted input.
    review_verdict = review["verdict"] if review["state"] == "fresh" else "unknown"
    raw_progress = progress_env.get("progress", []) if progress_env["state"] == "fresh" else []
    if not isinstance(raw_progress, list) or len(raw_progress) > MAX_ITEMS:
        raise ProjectionError("progress_array_bound")
    progress: dict[str, str] = {}
    for item in raw_progress:
        if not isinstance(item, dict) or set(item) != {"work_ref", "progress_age"}:
            raise ProjectionError("progress_closed_shape")
        work_ref = _ref(item["work_ref"], "progress_work_ref")
        age = item["progress_age"]
        if age not in {"recent", "stale", "unknown"} or work_ref in progress:
            raise ProjectionError("progress_binding")
        progress[work_ref] = age
    work = [_work(item, review_verdict, progress) for item in raw_work]
    attention_items = [_attention(item) for item in raw_attention]
    if len({item["work_ref"] for item in work}) != len(work):
        raise ProjectionError("reference_subject_collision")
    learning_counts = (
        (_count(learning.get("accepted_count"), "learning_accepted"), _count(learning.get("regression_count"), "learning_regression"))
        if learning["state"] == "fresh"
        else ({"state": "unavailable" if learning["state"] == "unavailable" else "unknown", "value": None}, {"state": "unavailable" if learning["state"] == "unavailable" else "unknown", "value": None})
    )
    payload = {"schema_version": SCHEMA_VERSION, "projection_revision": meta["projection_revision"], "generated_at": meta["generated_at"], "freshness": {"state": overall, "age_bucket": meta["sampled_at_bucket"]}, "source_health": {"state": overall, "reason": "coherent_sample"}, "source_digests": [{"source": name, "adapter_revision": env["adapter_revision"], "digest": env["digest"]} for name, env in envelopes.items()], "mission": {"objective": _objective(mission.get("objective", "unknown")), "workflow_phase": mission.get("workflow_phase", "unknown") if mission.get("workflow_phase", "unknown") in {"unknown", "plan", "execute", "validate", "review", "complete", "blocked"} else (_ for _ in ()).throw(ProjectionError("workflow_phase")), "definition_of_done": {"total": _count(mission.get("total"), "mission_total"), "satisfied": _count(mission.get("satisfied"), "mission_satisfied"), "unknown": _count(mission.get("unknown"), "mission_unknown")}, "next_gate": _text(mission.get("next_gate", "unknown"), "next_gate"), "blocker": _text(mission.get("blocker", "unknown"), "blocker"), "reference": _ref(mission.get("reference"), "mission_reference", True)}, "work": work, "attention": attention_items, "evidence": [], "learning": {"state": learning["state"], "accepted_count": learning_counts[0], "regression_count": learning_counts[1]}, "coverage": {"known_sources": _count({"state": "known", "value": sum(env["state"] == "fresh" for env in envelopes.values())}, "known_sources"), "unknown_sources": _count({"state": "known", "value": sum(env["state"] != "fresh" for env in envelopes.values())}, "unknown_sources"), "visible_budget": 64, "overflow_count": _count({"state": "known", "value": 0}, "overflow")}, "policy": {"policy_revision": meta["policy_revision"], "schema_revision": meta["schema_revision"], "serializer_revision": SERIALIZER_REVISION, "digest_algorithm": "sha256", "reference_grammar": "aqref:v1", "input_digest": input_digest}}
    encoded = canonical_bytes(payload)
    return payload, encoded, hashlib.sha256(encoded).hexdigest()
