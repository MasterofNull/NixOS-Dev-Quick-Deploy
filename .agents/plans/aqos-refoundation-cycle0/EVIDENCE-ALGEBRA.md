# AQ-OS Cycle 0 — Evidence Algebra and Required-Claim Matrix

**Status:** proposed C0.2 contract

## Orthogonal values

```text
EvidenceCondition = VALID | MISSING | STALE | INVALID | CONFLICTING | UNAUTHORIZED | INSUFFICIENT_SAMPLE
ClaimAssessment   = PASS | WARN | FAIL | UNKNOWN | NOT_APPLICABLE
GateOutcome       = PASS | DEGRADED | FAIL | BLOCKED
```

An evidence gate also has an evidence condition. If its policy, required-claim declaration or producer
assurance is absent/invalid, the gate is `BLOCKED`; it cannot evaluate itself to pass.

## Deterministic aggregation

1. Non-`VALID` required evidence yields `UNKNOWN`; a known adverse valid measurement yields `FAIL`.
2. `NOT_APPLICABLE` requires a versioned applicability predicate and reason. Missing data, zero
   denominator, provider failure or low sample can never become N/A.
3. Zero declared required claims is a schema/config error and gate `BLOCKED/NO_REQUIRED_CLAIMS`.
4. Optional-only composites cannot be authoritative; they are `BLOCKED/NO_REQUIRED_CLAIMS`.
5. Required `FAIL` yields gate `FAIL`; otherwise required `UNKNOWN` yields `BLOCKED`; otherwise required
   `WARN` yields `DEGRADED`; only all applicable required claims `PASS` yields `PASS`.
6. An optional unknown is displayed and contributes no positive weight.
7. Conflicting candidate evidence is never selected by newest timestamp alone. The declared authority,
   revision and hash must agree; otherwise `CONFLICTING/UNKNOWN/BLOCKED`.
8. Producer assurance below claim policy is `UNAUTHORIZED/UNKNOWN/BLOCKED`.
9. Sample size below the versioned minimum is `INSUFFICIENT_SAMPLE/UNKNOWN/BLOCKED` for required claims.
10. A proxy has a different metric ID and `proxy_for`. Only an explicit policy revision may substitute
    it; substitution remains visible in reasons/provenance.
11. `automation_allowed=true` only when the automation's named gate is `PASS`, evidence condition is
    `VALID`, policy is current and no revocation/suspension exists. `DEGRADED` never silently enables it.
12. Blocking reasons sort by `(claim_id, evidence_condition, assessment, reason_code, source_id)` and
    include remediation. Free-form text is presentation only.

## Required-claim matrix

| Composite gate | Required claims | Optional/display-only inputs |
|---|---|---|
| `operator_trust` | `intent_bound`, `trace_complete`, `validation_current`, `required_reviews_complete`, `authorization_current` | hint adoption, cache hit rate, locality |
| `collaboration_direction` | `subject_hash_valid`, `eligible_quorum`, `model_diversity`, `principal_diversity`, `all_required_lanes_terminal_or_waived`, `no_reject`, `no_unresolved_change`, `aggregate_bound` | unavailable-lane diagnostics |
| `collaboration_plan` | all direction claims plus `direction_current`, `plan_hash_valid`, `integration_contracts_dispositioned`, `resource_budget_declared`, `rollback_declared` | estimated effort |
| `implementation_assignment` | `direction_ratified`, `plan_ratified`, `owner_authorization`, `authorization_unexpired_unconsumed`, `ownership_preflight`, `evidence_current` | queue estimate |
| `qa_certification` | `artifact_hash_valid`, `pointer_revision_valid`, `producer_authorized`, `suite_completed`, `required_checks_evaluated`, `environment_declared` | skipped optional checks |
| `effectiveness` | `task_outcome_denominator_valid`, `artifact_usefulness_measured`, `review_outcome_measured`, `trace_complete`, `measurement_window_valid` | token/cache efficiency |
| `learning_promotion` | `scorer_certified`, `eval_isolated`, `dataset_lineage_valid`, `sample_minimum_met`, `candidate_beats_threshold`, `safety_regression_absent`, `promotion_authorized` | teacher/provider identity statistics |
| `authority_registry` | `scan_complete_within_bound`, `observed_claims_recorded`, `writers_recorded`, `target_disposition_reviewed`, `owner_and_deadline_present`, `recovery_source_present` | candidate architecture score |

## Mandatory fixtures

Fixtures cover N/A abuse, zero required claims, optional-only composite, unknown producer, insufficient
sample, conflicting equal/newer artifacts, zero denominator, unauthorized proxy substitution, stale
policy, deterministic reason ordering and recovery from invalid evidence to a valid non-manually-edited
result. CLI, API, dashboard and automation must consume the same serialized output bytes or verified
semantic hash.

`VERDICT: REQUEST_REVISION — algebra and claim requirements are explicit; thresholds, sample minima,
freshness windows and policy owners still require measured owner ratification.`
