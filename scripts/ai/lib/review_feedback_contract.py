#!/usr/bin/env python3
"""Pure C0.5A review-receipt and recursive-feedback contract.

All facts are injected.  This module performs validation and deterministic
projection only; it owns no persistence, lifecycle, dispatch, or consumer.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import Enum
from typing import Annotated, Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator, model_validator


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$")
IMMUTABLE_REF_RE = re.compile(r"^(?:sha256|event|artifact|receipt):[A-Za-z0-9._:+/-]{1,240}$")
Id = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:+/-]*$")]
Hash = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
Reason = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512)]


class ContractError(ValueError):
    """Stable fail-closed semantic violation."""


class StrictModel(BaseModel):
    # Enum strings are wire values; scalar fields carry explicit strict constraints.
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class LaneState(str, Enum):
    pending = "pending"
    dispatching = "dispatching"
    running = "running"
    submitted = "submitted"
    failed = "failed"
    timed_out = "timed_out"
    amended = "amended"
    parked = "parked"
    unavailable = "unavailable"


class LaneEligibility(str, Enum):
    advisory = "advisory"
    binding_flagship = "binding_flagship"
    recused = "recused"


class TypedVerdict(str, Enum):
    passed = "pass"
    revision_required = "revision_required"
    failed = "fail"
    abstain = "abstain"


class TerminalDecision(str, Enum):
    accepted = "accepted"
    revision_required = "revision_required"
    rejected = "rejected"
    incomplete = "incomplete"


class LocalModality(str, Enum):
    agentic_coding = "agentic_coding"
    bounded_logic = "bounded_logic"
    embedded_retrieval = "embedded_retrieval"


class AffectedConsumer(str, Enum):
    shared_contract = "shared_contract"
    flagship_prompt = "flagship_prompt"
    implementer_prompt = "implementer_prompt"
    local_agent_profile = "local_agent_profile"
    local_logic_template = "local_logic_template"
    embedded_corpus = "embedded_corpus"
    skill_or_instruction = "skill_or_instruction"
    tool_contract = "tool_contract"
    routing_policy = "routing_policy"
    evaluator = "evaluator"
    regression_fixture = "regression_fixture"
    monitoring_rule = "monitoring_rule"


class LearningState(str, Enum):
    captured = "captured"
    triaged = "triaged"
    fixture_bound = "fixture_bound"
    candidate_prepared = "candidate_prepared"
    shadow_validated = "shadow_validated"
    flagship_accepted = "flagship_accepted"
    canary = "canary"
    promoted = "promoted"
    rolled_back = "rolled_back"
    non_propagated = "non_propagated"


VERDICT_MAP = {
    "APPROVE": TypedVerdict.passed,
    "PASS": TypedVerdict.passed,
    "APPROVE_WITH_CHANGES": TypedVerdict.revision_required,
    "REQUEST_REVISION": TypedVerdict.revision_required,
    "REJECT": TypedVerdict.failed,
    "FAIL": TypedVerdict.failed,
    "ABSTAIN": TypedVerdict.abstain,
}


class EvidenceRef(StrictModel):
    ref: Annotated[str, StringConstraints(strict=True, min_length=8, max_length=256)]
    artifact_hash: Hash
    source_event_hash: Hash
    trust_class: Literal["dispatch_bound", "independently_verified", "legacy_manual"]
    verifier_principal: Id
    sanitized: StrictBool
    redacted: StrictBool

    @model_validator(mode="after")
    def immutable_and_safe(self) -> "EvidenceRef":
        if not IMMUTABLE_REF_RE.fullmatch(self.ref):
            raise ValueError("evidence_ref_mutable")
        if not self.sanitized:
            raise ValueError("evidence_not_sanitized")
        return self


class CriterionResult(StrictModel):
    criterion_id: Id
    result: Literal["pass", "revision_required", "fail", "not_assessed"]
    evidence_refs: Annotated[list[EvidenceRef], Field(max_length=32)] = Field(default_factory=list)
    residual_risk: Annotated[str | None, StringConstraints(strict=True, max_length=512)] = None


class Lineage(StrictModel):
    dispatch_request_hash: Hash
    dispatch_task_id: Id
    idempotency_key: Id
    execution_principal: Id
    model_artifact: Id
    model_family: Id
    model_profile: Id
    implementer_principal: Id
    material_rewriters: Annotated[list[Id], Field(max_length=32)] = Field(default_factory=list)
    provenance: Literal["trusted_dispatch", "legacy_manual"]


class LaneReview(StrictModel):
    lane_id: Id
    required: StrictBool
    state: LaneState
    eligibility: LaneEligibility
    assigned_role: Id
    subject_hash: Hash
    baseline_hash: Hash
    criteria_hash: Hash
    roster_hash: Hash
    policy_hash: Hash
    verdict: TypedVerdict | None = None
    terminal_reason: Reason | None = None
    amended_subject_hash: Hash | None = None
    lineage: Lineage
    criteria: Annotated[list[CriterionResult], Field(max_length=64)] = Field(default_factory=list)
    reproduced_checks: Annotated[list[Id], Field(max_length=64)] = Field(default_factory=list)
    local_modality: LocalModality | None = None

    @model_validator(mode="after")
    def state_contract(self) -> "LaneReview":
        if self.state == LaneState.submitted and self.verdict is None:
            raise ValueError("submitted_verdict_required")
        if self.state != LaneState.submitted and self.verdict is not None:
            raise ValueError("verdict_only_for_submitted")
        if self.state in {LaneState.failed, LaneState.timed_out, LaneState.parked, LaneState.unavailable} and not self.terminal_reason:
            raise ValueError("terminal_reason_required")
        if self.state == LaneState.amended and self.amended_subject_hash is None:
            raise ValueError("amended_subject_hash_required")
        if self.local_modality == LocalModality.embedded_retrieval:
            raise ValueError("embedded_retrieval_cannot_be_lane")
        return self


class AdvisoryFinding(StrictModel):
    finding_hash: Hash
    lane_id: Id
    severity: Literal["low", "medium", "high", "critical"]
    attributable: StrictBool
    fresh: StrictBool
    evidence_refs: Annotated[list[EvidenceRef], Field(min_length=1, max_length=16)]


class FindingDisposition(StrictModel):
    finding_hash: Hash
    reviewer_principal: Id
    reviewer_eligibility: Literal["binding_flagship"]
    decision: Literal["revision_required", "rejected", "incomplete"]
    evidence_refs: Annotated[list[EvidenceRef], Field(min_length=1, max_length=16)]


class ReviewFeedbackPolicy(StrictModel):
    schema_version: Literal["aq.review-feedback-policy.v1"]
    policy_version: Id
    binding_count: Annotated[int, Field(strict=True, ge=1, le=16)]
    minimum_independent_principals: Annotated[int, Field(strict=True, ge=1, le=16)]
    minimum_independent_families: Annotated[int, Field(strict=True, ge=1, le=16)]
    critical_advisory_blocks: Literal[True]
    decision_precedence: Annotated[list[Literal["incomplete", "rejected", "revision_required", "accepted"]], Field(min_length=4, max_length=4)]
    max_lanes: Annotated[int, Field(strict=True, ge=1, le=64)]
    max_findings: Annotated[int, Field(strict=True, ge=1, le=256)]

    @field_validator("decision_precedence")
    @classmethod
    def precedence_is_frozen(cls, value: list[str]) -> list[str]:
        if value != ["incomplete", "rejected", "revision_required", "accepted"]:
            raise ValueError("decision_precedence_invalid")
        return value


class ReviewRoundInput(StrictModel):
    schema_version: Literal["aq.review-round-input.v1"]
    round_id: Id
    pass_id: Id
    pass_index: Annotated[int, Field(strict=True, ge=0, le=1024)]
    baseline_id: Id
    baseline_hash: Hash
    subject_hash: Hash
    subject_package_hash: Hash
    criteria_hash: Hash
    roster_hash: Hash
    policy_hash: Hash
    expert_roles: Annotated[list[Id], Field(min_length=1, max_length=32)]
    eligibility_source: Id
    implementer_principal: Id
    predecessor_hash: Hash | None = None
    supersedes_hash: Hash | None = None
    expires_at: Annotated[str, StringConstraints(strict=True, min_length=20, max_length=35, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$")]
    evaluated_at: Annotated[str, StringConstraints(strict=True, min_length=20, max_length=35, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$")]
    lanes: Annotated[list[LaneReview], Field(min_length=1, max_length=64)]
    findings: Annotated[list[AdvisoryFinding], Field(max_length=256)] = Field(default_factory=list)
    dispositions: Annotated[list[FindingDisposition], Field(max_length=256)] = Field(default_factory=list)

    @field_validator("expires_at", "evaluated_at")
    @classmethod
    def timestamp_has_zone(cls, value: str) -> str:
        if not RFC3339_RE.fullmatch(value):
            raise ValueError("timestamp_invalid")
        return value

    @model_validator(mode="after")
    def unique_normalized_values(self) -> "ReviewRoundInput":
        for values, code in ((self.expert_roles, "duplicate_expert_role"), ([x.lane_id for x in self.lanes], "duplicate_lane")):
            normalized = [unicodedata.normalize("NFC", x) for x in values]
            if len(normalized) != len(set(normalized)):
                raise ValueError(code)
        if self.predecessor_hash and self.predecessor_hash == self.subject_hash:
            raise ValueError("revision_hash_reuse")
        if self.supersedes_hash and self.supersedes_hash == self.subject_hash:
            raise ValueError("supersession_hash_reuse")
        return self


class ReviewRoundReceipt(StrictModel):
    schema_version: Literal["aq.review-round-receipt.v1"]
    round_id: Id
    pass_id: Id
    pass_index: Annotated[int, Field(strict=True, ge=0, le=1024)]
    baseline_id: Id
    baseline_hash: Hash
    subject_hash: Hash
    subject_package_hash: Hash
    criteria_hash: Hash
    roster_hash: Hash
    policy_hash: Hash
    policy_version: Id
    expert_roles: Annotated[list[Id], Field(min_length=1, max_length=32)]
    eligibility_source: Id
    required_lane_ids: Annotated[list[Id], Field(max_length=64)]
    optional_lane_ids: Annotated[list[Id], Field(max_length=64)]
    adjudication_input_hash: Hash
    predecessor_hash: Hash | None = None
    supersedes_hash: Hash | None = None
    expires_at: Annotated[str, StringConstraints(strict=True, min_length=20, max_length=35, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$")]
    terminal_decision: TerminalDecision
    binding_passes: Annotated[int, Field(strict=True, ge=0, le=64)]
    independent_principals: Annotated[int, Field(strict=True, ge=0, le=64)]
    independent_families: Annotated[int, Field(strict=True, ge=0, le=64)]
    terminal_accounted: Annotated[int, Field(strict=True, ge=0, le=64)]
    quorum_met: StrictBool
    independence_met: StrictBool
    blocking_codes: Annotated[list[Id], Field(max_length=128)]
    evaluated_at: Annotated[str, StringConstraints(strict=True, min_length=20, max_length=35, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$")]
    canonical_hash: Hash


class LearningEvidence(StrictModel):
    original_failure: EvidenceRef
    successful_retry: EvidenceRef | None = None
    reproduction: EvidenceRef
    fixture: EvidenceRef | None = None
    shadow_evaluation: EvidenceRef | None = None
    canary_soak: EvidenceRef | None = None
    rollback_target_hash: Hash | None = None


class LearningCandidate(StrictModel):
    schema_version: Literal["aq.learning-candidate.v1"]
    candidate_id: Id
    candidate_hash: Hash
    source_event_hash: Hash
    deduplication_hash: Hash
    severity: Literal["low", "medium", "high", "critical"]
    state: LearningState
    affected_consumers: Annotated[list[AffectedConsumer], Field(min_length=1, max_length=12)]
    local_modality: LocalModality | None = None
    hardware_profile: Id | None = None
    model_profile: Id | None = None
    candidate_author: Id
    evaluator_principal: Id | None = None
    independent_verifier: Id
    accepted_receipt_hash: Hash | None = None
    consumer_freshness_plan_hash: Hash | None = None
    expected_revision: Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)]
    evidence: LearningEvidence
    non_propagation_reason: Reason | None = None
    evaluated_at: Annotated[str, StringConstraints(strict=True, min_length=20, max_length=35, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$")]

    @field_validator("evaluated_at")
    @classmethod
    def timestamp_has_zone(cls, value: str) -> str:
        if not RFC3339_RE.fullmatch(value):
            raise ValueError("timestamp_invalid")
        return value

    @model_validator(mode="after")
    def semantic_rules(self) -> "LearningCandidate":
        normalized = [x.value for x in self.affected_consumers]
        if len(normalized) != len(set(normalized)):
            raise ValueError("duplicate_affected_consumer")
        if self.independent_verifier == self.candidate_author:
            raise ValueError("independent_verifier_is_candidate_author")
        if self.evaluator_principal == self.candidate_author and self.independent_verifier == self.candidate_author:
            raise ValueError("candidate_evaluator_coauthorship")
        if self.state == LearningState.non_propagated and not self.non_propagation_reason:
            raise ValueError("non_propagation_reason_required")
        if self.local_modality == LocalModality.embedded_retrieval and self.evaluator_principal is not None:
            raise ValueError("embedded_retrieval_cannot_evaluate")
        evidence_refs = [self.evidence.original_failure, self.evidence.reproduction]
        evidence_refs.extend(x for x in (self.evidence.successful_retry, self.evidence.fixture,
                                         self.evidence.shadow_evaluation, self.evidence.canary_soak) if x is not None)
        if any(item.verifier_principal != self.independent_verifier for item in evidence_refs):
            raise ValueError("independent_verifier_mismatch")
        expected_dedup = hashlib.sha256(json.dumps({
            "source_event_hash": self.source_event_hash,
            "failure_hash": self.evidence.original_failure.artifact_hash,
            "affected_consumers": sorted(item.value for item in self.affected_consumers),
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if self.deduplication_hash != expected_dedup:
            raise ValueError("deduplication_hash_mismatch")
        return self


ALLOWED_TRANSITIONS: Mapping[LearningState, frozenset[LearningState]] = {
    LearningState.captured: frozenset({LearningState.triaged, LearningState.non_propagated}),
    LearningState.triaged: frozenset({LearningState.fixture_bound, LearningState.non_propagated}),
    LearningState.fixture_bound: frozenset({LearningState.candidate_prepared, LearningState.non_propagated}),
    LearningState.candidate_prepared: frozenset({LearningState.shadow_validated}),
    LearningState.shadow_validated: frozenset({LearningState.flagship_accepted}),
    LearningState.flagship_accepted: frozenset({LearningState.canary}),
    LearningState.canary: frozenset({LearningState.promoted, LearningState.rolled_back}),
    LearningState.promoted: frozenset(), LearningState.rolled_back: frozenset(),
    LearningState.non_propagated: frozenset(),
}


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def map_verdict(value: str) -> TypedVerdict:
    try:
        return VERDICT_MAP[value]
    except KeyError as exc:
        raise ContractError("verdict_untyped") from exc


def subject_package_hash(items: Sequence[tuple[str, str]]) -> str:
    normalized: list[tuple[str, str]] = []
    for path, digest in items:
        clean = unicodedata.normalize("NFC", path)
        if not clean or clean.startswith("/") or ".." in clean.split("/") or not SHA256_RE.fullmatch(digest):
            raise ContractError("subject_item_invalid")
        normalized.append((clean, digest))
    if len({path for path, _ in normalized}) != len(normalized):
        raise ContractError("subject_path_duplicate")
    return canonical_hash(sorted(normalized))


def _lineage_independent(lane: LaneReview, implementer: str) -> bool:
    lineage = lane.lineage
    if lineage.provenance != "trusted_dispatch":
        return False
    identities = {implementer, lineage.implementer_principal, *lineage.material_rewriters}
    return lane.eligibility == LaneEligibility.binding_flagship and lineage.execution_principal not in identities


def adjudicate_review(review: ReviewRoundInput, policy: ReviewFeedbackPolicy) -> ReviewRoundReceipt:
    if len(review.lanes) > policy.max_lanes or len(review.findings) > policy.max_findings:
        raise ContractError("policy_bound_exceeded")
    codes: set[str] = set()
    terminal = {LaneState.submitted, LaneState.failed, LaneState.timed_out, LaneState.parked, LaneState.unavailable, LaneState.amended}
    accounted = sum(lane.state in terminal for lane in review.lanes)
    required_nonterminal = any(lane.required and lane.state not in terminal for lane in review.lanes)
    if required_nonterminal:
        codes.add("required_lane_nonterminal")

    eligible: list[LaneReview] = []
    for lane in review.lanes:
        if (lane.subject_hash, lane.baseline_hash, lane.criteria_hash, lane.roster_hash, lane.policy_hash) != (
            review.subject_hash, review.baseline_hash, review.criteria_hash, review.roster_hash, review.policy_hash
        ):
            codes.add("review_drift")
            continue
        if lane.state == LaneState.amended and lane.amended_subject_hash != review.subject_hash:
            codes.add("amended_subject_mismatch")
            continue
        if lane.lineage.execution_principal in lane.lineage.material_rewriters:
            codes.add("material_rewriter_recused")
            continue
        if lane.state == LaneState.submitted and _lineage_independent(lane, review.implementer_principal):
            eligible.append(lane)

    binding_passes = [lane for lane in eligible if lane.verdict == TypedVerdict.passed]
    principals = {lane.lineage.execution_principal for lane in binding_passes}
    families = {unicodedata.normalize("NFC", lane.lineage.model_family).casefold() for lane in binding_passes}
    if len(principals) != len(binding_passes):
        codes.add("duplicate_binding_principal")
    if len(families) != len(binding_passes):
        codes.add("duplicate_binding_family")
    quorum = len(binding_passes) >= policy.binding_count
    independence = len(principals) >= policy.minimum_independent_principals and len(families) >= policy.minimum_independent_families
    if not quorum:
        codes.add("binding_quorum_missing")
    if not independence:
        codes.add("independence_missing")

    dispositions = {item.finding_hash: item for item in review.dispositions}
    critical = [f for f in review.findings if f.severity == "critical" and f.attributable and f.fresh]
    eligible_principals = {lane.lineage.execution_principal for lane in eligible}
    invalid_dispositions = {item.finding_hash for item in review.dispositions
                            if item.reviewer_principal not in eligible_principals}
    if invalid_dispositions:
        codes.add("disposition_reviewer_ineligible")
    unresolved = [f for f in critical if f.finding_hash not in dispositions or f.finding_hash in invalid_dispositions]
    if unresolved:
        codes.add("critical_dissent_undisposed")
    disposed_decisions = {dispositions[f.finding_hash].decision for f in critical if f.finding_hash in dispositions}

    if required_nonterminal or unresolved or "review_drift" in codes:
        decision = TerminalDecision.incomplete
    elif any(lane.verdict == TypedVerdict.failed for lane in eligible) or "rejected" in disposed_decisions:
        decision = TerminalDecision.rejected
    elif any(lane.verdict == TypedVerdict.revision_required for lane in eligible) or "revision_required" in disposed_decisions:
        decision = TerminalDecision.revision_required
    elif quorum and independence and not codes and all(lane.verdict == TypedVerdict.passed for lane in eligible):
        decision = TerminalDecision.accepted
    else:
        decision = TerminalDecision.incomplete

    body = {
        "schema_version": "aq.review-round-receipt.v1", "round_id": review.round_id,
        "pass_id": review.pass_id, "pass_index": review.pass_index, "baseline_id": review.baseline_id,
        "baseline_hash": review.baseline_hash, "subject_hash": review.subject_hash,
        "subject_package_hash": review.subject_package_hash, "criteria_hash": review.criteria_hash,
        "roster_hash": review.roster_hash, "policy_hash": review.policy_hash,
        "policy_version": policy.policy_version, "expert_roles": sorted(review.expert_roles),
        "eligibility_source": review.eligibility_source,
        "required_lane_ids": sorted(lane.lane_id for lane in review.lanes if lane.required),
        "optional_lane_ids": sorted(lane.lane_id for lane in review.lanes if not lane.required),
        "adjudication_input_hash": canonical_hash(review), "predecessor_hash": review.predecessor_hash,
        "supersedes_hash": review.supersedes_hash, "expires_at": review.expires_at,
        "terminal_decision": decision,
        "binding_passes": len(binding_passes), "independent_principals": len(principals),
        "independent_families": len(families), "terminal_accounted": accounted,
        "quorum_met": quorum, "independence_met": independence,
        "blocking_codes": sorted(codes), "evaluated_at": review.evaluated_at,
    }
    body["canonical_hash"] = canonical_hash(body)
    return ReviewRoundReceipt.model_validate(body)


def validate_transition(current: LearningState, target: LearningState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ContractError("learning_transition_forbidden")


def promotion_intent(candidate: LearningCandidate, receipt: ReviewRoundReceipt, *, actual_revision: int) -> dict[str, Any]:
    if candidate.state != LearningState.canary:
        raise ContractError("candidate_not_at_canary")
    if candidate.expected_revision != actual_revision:
        raise ContractError("cas_revision_mismatch")
    if receipt.terminal_decision != TerminalDecision.accepted or candidate.accepted_receipt_hash != receipt.canonical_hash:
        raise ContractError("accepted_receipt_missing")
    evidence = candidate.evidence
    if not all((evidence.fixture, evidence.shadow_evaluation, evidence.canary_soak, evidence.rollback_target_hash)):
        raise ContractError("promotion_evidence_incomplete")
    if candidate.consumer_freshness_plan_hash is None:
        raise ContractError("freshness_plan_missing")
    if candidate.evaluator_principal is None or candidate.evaluator_principal == candidate.candidate_author:
        raise ContractError("independent_evaluator_missing")
    return {
        "action": "promote", "candidate_hash": candidate.candidate_hash,
        "source_event_hash": candidate.source_event_hash, "expected_revision": actual_revision,
        "next_revision": actual_revision + 1, "rollback_target_hash": evidence.rollback_target_hash,
        "freshness_plan_hash": candidate.consumer_freshness_plan_hash,
    }


def schema_projection(name: Literal["receipt", "candidate", "policy"]) -> dict[str, Any]:
    models = {"receipt": ReviewRoundReceipt, "candidate": LearningCandidate, "policy": ReviewFeedbackPolicy}
    return models[name].model_json_schema(mode="validation")
