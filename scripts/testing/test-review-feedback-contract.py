#!/usr/bin/env python3
"""C0.5A executable acceptance tests for pure review/feedback contracts."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError


REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "scripts/ai/lib/review_feedback_contract.py"
SCHEMAS = {
    "receipt": REPO / "config/schemas/review-round-receipt.schema.json",
    "candidate": REPO / "config/schemas/learning-candidate.schema.json",
    "policy": REPO / "config/schemas/review-feedback-policy.schema.json",
}
POLICY = REPO / "config/review-feedback-policy.json"
FIXTURE = REPO / "scripts/testing/fixtures/review-feedback-contract-golden.json"
spec = importlib.util.spec_from_file_location("review_feedback_contract_c05", MODULE)
assert spec and spec.loader
contract = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = contract
spec.loader.exec_module(contract)

H = {letter: letter * 64 for letter in "abcdef0123456789"}


def evidence(label: str = "artifact", verifier: str = "verifier:independent") -> dict:
    return {
        "ref": f"artifact:{label}", "artifact_hash": H["a"], "source_event_hash": H["b"],
        "trust_class": "independently_verified", "verifier_principal": verifier,
        "sanitized": True, "redacted": True,
    }


def lineage(principal: str, family: str, *, implementer: str = "implementer:sonnet",
            provenance: str = "trusted_dispatch", rewriters: list[str] | None = None) -> dict:
    return {
        "dispatch_request_hash": H["c"], "dispatch_task_id": f"task:{principal.split(':')[-1]}",
        "idempotency_key": f"key:{principal.split(':')[-1]}", "execution_principal": principal,
        "model_artifact": f"model:{family}", "model_family": family, "model_profile": "flagship",
        "implementer_principal": implementer, "material_rewriters": rewriters or [],
        "provenance": provenance,
    }


def lane(name: str, principal: str, family: str, *, state: str = "submitted",
         verdict: str | None = "pass", eligibility: str = "binding_flagship",
         required: bool = True, terminal_reason: str | None = None,
         provenance: str = "trusted_dispatch", rewriters: list[str] | None = None) -> dict:
    item = {
        "lane_id": name, "required": required, "state": state, "eligibility": eligibility,
        "assigned_role": "security-reviewer", "subject_hash": H["d"], "baseline_hash": H["e"],
        "criteria_hash": H["f"], "roster_hash": H["0"], "policy_hash": H["1"],
        "verdict": verdict, "terminal_reason": terminal_reason, "amended_subject_hash": None,
        "lineage": lineage(principal, family, provenance=provenance, rewriters=rewriters),
        "criteria": [], "reproduced_checks": ["focused-contract"], "local_modality": None,
    }
    if state == "amended":
        item["verdict"] = None
        item["amended_subject_hash"] = H["d"]
    return item


def review(lanes: list[dict] | None = None) -> dict:
    return {
        "schema_version": "aq.review-round-input.v1", "round_id": "round:c05",
        "pass_id": "pass:1", "pass_index": 1, "baseline_id": "baseline:c05",
        "baseline_hash": H["e"], "subject_hash": H["d"], "subject_package_hash": H["2"],
        "criteria_hash": H["f"], "roster_hash": H["0"], "policy_hash": H["1"],
        "expert_roles": ["architecture", "security", "sre"], "eligibility_source": "role-matrix:v1",
        "implementer_principal": "implementer:sonnet", "predecessor_hash": H["3"],
        "supersedes_hash": H["4"], "expires_at": "2026-07-17T00:00:00Z",
        "evaluated_at": "2026-07-16T22:00:00Z",
        "lanes": lanes or [lane("fable", "reviewer:fable", "claude"),
                            lane("antigravity", "reviewer:antigravity", "gemini")],
        "findings": [], "dispositions": [],
    }


def candidate(*, state: str = "canary", consumers: list[str] | None = None) -> dict:
    consumers = consumers or ["shared_contract"]
    failure = evidence("failure")
    dedup = hashlib.sha256(json.dumps({
        "source_event_hash": H["b"], "failure_hash": failure["artifact_hash"],
        "affected_consumers": sorted(consumers),
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version": "aq.learning-candidate.v1", "candidate_id": "candidate:c05",
        "candidate_hash": H["5"], "source_event_hash": H["b"], "deduplication_hash": dedup,
        "severity": "high", "state": state, "affected_consumers": consumers,
        "local_modality": "bounded_logic", "hardware_profile": "local:4090",
        "model_profile": "qwen:logic", "candidate_author": "author:implementer",
        "evaluator_principal": "evaluator:flagship", "independent_verifier": "verifier:independent",
        "accepted_receipt_hash": None, "consumer_freshness_plan_hash": H["6"],
        "expected_revision": 7,
        "evidence": {"original_failure": failure, "successful_retry": evidence("retry"),
                     "reproduction": evidence("reproduction"), "fixture": evidence("fixture"),
                     "shadow_evaluation": evidence("shadow"), "canary_soak": evidence("canary"),
                     "rollback_target_hash": H["7"]},
        "non_propagation_reason": None, "evaluated_at": "2026-07-16T22:00:00Z",
    }


class ReviewFeedbackContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy_raw = json.loads(POLICY.read_text())
        cls.policy = contract.ReviewFeedbackPolicy.model_validate(cls.policy_raw)
        cls.fixture = json.loads(FIXTURE.read_text())

    def adjudicate(self, value: dict | None = None):
        return contract.adjudicate_review(contract.ReviewRoundInput.model_validate(value or review()), self.policy)

    def test_01_generated_draft202012_schemas_are_closed_and_exact(self) -> None:
        for name, path in SCHEMAS.items():
            frozen = json.loads(path.read_text())
            Draft202012Validator.check_schema(frozen)
            self.assertEqual(frozen, contract.schema_projection(name))
            self.assertFalse(frozen["additionalProperties"])
        for model, value in ((contract.ReviewFeedbackPolicy, self.policy_raw),
                             (contract.ReviewRoundInput, review()),
                             (contract.LearningCandidate, candidate())):
            bad = copy.deepcopy(value); bad["unknown"] = True
            with self.assertRaises(ValidationError): model.model_validate(bad)

    def test_02_purity_and_determinism_surface(self) -> None:
        tree = ast.parse(MODULE.read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module.split(".")[0])
        self.assertFalse(imports & {"os", "pathlib", "subprocess", "socket", "requests", "urllib", "time", "datetime", "random", "secrets"})
        first = self.adjudicate(); second = self.adjudicate()
        self.assertEqual(contract.canonical_bytes(first), contract.canonical_bytes(second))
        self.assertEqual(first.canonical_hash, second.canonical_hash)

    def test_03_full_roster_accepts_and_verdict_mapping_is_total(self) -> None:
        receipt = self.adjudicate()
        self.assertEqual(receipt.terminal_decision.value, "accepted")
        self.assertEqual((receipt.binding_passes, receipt.independent_principals, receipt.independent_families), (2, 2, 2))
        self.assertEqual(receipt.required_lane_ids, ["antigravity", "fable"])
        self.assertEqual(receipt.adjudication_input_hash,
                         contract.canonical_hash(contract.ReviewRoundInput.model_validate(review())))
        expected = {"APPROVE": "pass", "PASS": "pass", "APPROVE_WITH_CHANGES": "revision_required",
                    "REQUEST_REVISION": "revision_required", "REJECT": "fail", "FAIL": "fail", "ABSTAIN": "abstain"}
        self.assertEqual({key: contract.map_verdict(key).value for key in expected}, expected)
        with self.assertRaisesRegex(contract.ContractError, "verdict_untyped"): contract.map_verdict("prose pass")

    def test_04_drift_and_required_nonterminal_precede_failure(self) -> None:
        for field in ("subject_hash", "baseline_hash", "criteria_hash", "roster_hash", "policy_hash"):
            value = review(); value["lanes"][0][field] = H["8"]
            self.assertEqual(self.adjudicate(value).terminal_decision.value, "incomplete")
        value = review([lane("running", "reviewer:running", "openai", state="running", verdict=None),
                        lane("fail", "reviewer:fail", "claude", verdict="fail")])
        self.assertEqual(self.adjudicate(value).terminal_decision.value, "incomplete")

    def test_05_lane_terminal_accounting_is_not_quorum(self) -> None:
        for state in ("failed", "timed_out", "parked", "unavailable"):
            value = review([lane("terminal", "reviewer:terminal", "claude", state=state, verdict=None,
                                 terminal_reason="capacity_failure"),
                            lane("pass", "reviewer:pass", "gemini")])
            receipt = self.adjudicate(value)
            self.assertEqual(receipt.terminal_accounted, 2)
            self.assertEqual(receipt.terminal_decision.value, "incomplete")
        abstain = self.adjudicate(review([lane("a", "reviewer:a", "claude", verdict="abstain"),
                                         lane("p", "reviewer:p", "gemini")]))
        self.assertEqual(abstain.terminal_accounted, 2); self.assertFalse(abstain.quorum_met)
        amended = review(); amended["lanes"][0] = lane("amended", "reviewer:a", "claude", state="amended")
        self.assertEqual(self.adjudicate(amended).terminal_accounted, 2)

    def test_06_independence_alias_and_material_rewriter_fail_closed(self) -> None:
        self_review = review([lane("self", "implementer:sonnet", "claude"),
                              lane("other", "reviewer:other", "gemini")])
        self.assertEqual(self.adjudicate(self_review).terminal_decision.value, "incomplete")
        rewritten = review([lane("edit", "reviewer:edit", "claude", rewriters=["reviewer:edit"]),
                            lane("other", "reviewer:other", "gemini")])
        self.assertIn("material_rewriter_recused", self.adjudicate(rewritten).blocking_codes)
        aliases = review([lane("one", "reviewer:same", "Claude"), lane("two", "reviewer:same", "claude")])
        receipt = self.adjudicate(aliases)
        self.assertIn("duplicate_binding_principal", receipt.blocking_codes)
        self.assertIn("duplicate_binding_family", receipt.blocking_codes)
        low_trust = review([lane("legacy", "reviewer:legacy", "claude", provenance="legacy_manual"),
                            lane("other", "reviewer:other", "gemini")])
        self.assertEqual(self.adjudicate(low_trust).terminal_decision.value, "incomplete")

    def test_07_revision_supersession_hashes_and_unicode_subjects(self) -> None:
        with self.assertRaises(ValidationError):
            bad = review(); bad["predecessor_hash"] = bad["subject_hash"]; contract.ReviewRoundInput.model_validate(bad)
        digest = H["a"]
        self.assertEqual(contract.subject_package_hash([("b", digest), ("a", digest)]),
                         contract.subject_package_hash([("a", digest), ("b", digest)]))
        with self.assertRaisesRegex(contract.ContractError, "subject_path_duplicate"):
            contract.subject_package_hash([("caf\u00e9", digest), ("cafe\u0301", digest)])

    def test_08_critical_advisory_requires_eligible_typed_disposition(self) -> None:
        value = review()
        value["findings"] = [{"finding_hash": H["8"], "lane_id": "local", "severity": "critical",
                              "attributable": True, "fresh": True, "evidence_refs": [evidence("finding")]}]
        self.assertEqual(self.adjudicate(value).terminal_decision.value, "incomplete")
        value["dispositions"] = [{"finding_hash": H["8"], "reviewer_principal": "reviewer:fable",
                                  "reviewer_eligibility": "binding_flagship", "decision": "revision_required",
                                  "evidence_refs": [evidence("disposition")]}]
        self.assertEqual(self.adjudicate(value).terminal_decision.value, "revision_required")
        value["dispositions"][0]["reviewer_principal"] = "reviewer:forged"
        self.assertEqual(self.adjudicate(value).terminal_decision.value, "incomplete")

    def test_09_bounds_types_timestamps_nested_unknown_and_mutable_evidence(self) -> None:
        for mutation in ({"pass_index": True}, {"evaluated_at": "2026-07-16T22:00:00"},
                         {"subject_hash": "bad"}, {"expert_roles": ["x"] * 33}):
            bad = review(); bad.update(mutation)
            with self.assertRaises(ValidationError): contract.ReviewRoundInput.model_validate(bad)
        bad = candidate(); bad["evidence"]["original_failure"]["unknown"] = True
        with self.assertRaises(ValidationError): contract.LearningCandidate.model_validate(bad)
        bad = candidate(); bad["evidence"]["original_failure"]["ref"] = "/tmp/mutable"
        with self.assertRaises(ValidationError): contract.LearningCandidate.model_validate(bad)

    def test_10_learning_taxonomy_modalities_dedup_and_retry_preservation(self) -> None:
        consumers = [item.value for item in contract.AffectedConsumer]
        value = candidate(consumers=consumers)
        parsed = contract.LearningCandidate.model_validate(value)
        self.assertEqual(len(parsed.affected_consumers), 12)
        self.assertIsNotNone(parsed.evidence.original_failure)
        self.assertIsNotNone(parsed.evidence.successful_retry)
        for modality in ("agentic_coding", "bounded_logic"):
            item = candidate(); item["local_modality"] = modality
            contract.LearningCandidate.model_validate(item)
        embedded = candidate(); embedded["local_modality"] = "embedded_retrieval"
        with self.assertRaises(ValidationError): contract.LearningCandidate.model_validate(embedded)
        poisoned = candidate(); poisoned["deduplication_hash"] = H["9"]
        with self.assertRaises(ValidationError): contract.LearningCandidate.model_validate(poisoned)

    def test_11_learning_transition_graph_nonpropagation_and_coauthorship(self) -> None:
        path = [contract.LearningState.captured, contract.LearningState.triaged,
                contract.LearningState.fixture_bound, contract.LearningState.candidate_prepared,
                contract.LearningState.shadow_validated, contract.LearningState.flagship_accepted,
                contract.LearningState.canary, contract.LearningState.promoted]
        for source, target in zip(path, path[1:]): contract.validate_transition(source, target)
        with self.assertRaisesRegex(contract.ContractError, "learning_transition_forbidden"):
            contract.validate_transition(contract.LearningState.captured, contract.LearningState.promoted)
        nonprop = candidate(state="non_propagated"); nonprop["non_propagation_reason"] = "not reproducible"
        contract.LearningCandidate.model_validate(nonprop)
        coauthored = candidate(); coauthored["candidate_author"] = "verifier:independent"; coauthored["evaluator_principal"] = "verifier:independent"
        with self.assertRaises(ValidationError): contract.LearningCandidate.model_validate(coauthored)

    def test_12_promotion_requires_receipt_fixture_shadow_canary_rollback_freshness_and_cas(self) -> None:
        receipt = self.adjudicate(); value = candidate(); value["accepted_receipt_hash"] = receipt.canonical_hash
        parsed = contract.LearningCandidate.model_validate(value)
        intent = contract.promotion_intent(parsed, receipt, actual_revision=7)
        self.assertEqual((intent["action"], intent["next_revision"]), ("promote", 8))
        with self.assertRaisesRegex(contract.ContractError, "cas_revision_mismatch"):
            contract.promotion_intent(parsed, receipt, actual_revision=8)
        for field in ("fixture", "shadow_evaluation", "canary_soak", "rollback_target_hash"):
            bad = copy.deepcopy(value); bad["evidence"][field] = None
            with self.assertRaisesRegex(contract.ContractError, "promotion_evidence_incomplete"):
                contract.promotion_intent(contract.LearningCandidate.model_validate(bad), receipt, actual_revision=7)
        bad = copy.deepcopy(value); bad["consumer_freshness_plan_hash"] = None
        with self.assertRaisesRegex(contract.ContractError, "freshness_plan_missing"):
            contract.promotion_intent(contract.LearningCandidate.model_validate(bad), receipt, actual_revision=7)

    def test_13_fixture_names_pin_every_design_family(self) -> None:
        required = {"same_baseline_full_roster", "mismatched_baseline", "subject_drift", "criteria_drift",
                    "policy_drift", "roster_drift", "permutation_invariance", "unicode_normalization",
                    "exact_boundary_sizes", "max_plus_one", "malformed_hash", "malformed_timestamp",
                    "nested_unknown", "advisory_local_dissent", "explicit_abstention",
                    "unavailable_vs_abstaining", "failed_flagship", "timed_out_flagship", "parked_flagship",
                    "required_lane_running", "amended_exact_subject", "self_review", "forged_self_review_false",
                    "material_rewriter_recusal", "insufficient_binding_quorum", "duplicate_lane",
                    "duplicate_principal_alias", "duplicate_family_alias", "superseded_hash", "revision_cycle",
                    "revision_hash_reuse", "typed_revision", "terminal_precedence", "finding_deduplication",
                    "successful_retry_preserves_failure", "critical_advisory_disposition", "all_affected_consumers",
                    "missing_fixture", "direct_mutation_attempt", "poisoned_mutable_evidence",
                    "candidate_evaluator_coauthorship", "embedded_vote_rejection", "local_modalities",
                    "local_capacity_not_abstention", "shadow_failure", "flagship_self_acceptance",
                    "missing_canary", "missing_rollback", "cas_replay", "valid_promotion", "rollback",
                    "typed_non_propagation", "stable_canonical_output_hash"}
        self.assertEqual(set(self.fixture["vectors"]), required)


if __name__ == "__main__":
    unittest.main(verbosity=2)
