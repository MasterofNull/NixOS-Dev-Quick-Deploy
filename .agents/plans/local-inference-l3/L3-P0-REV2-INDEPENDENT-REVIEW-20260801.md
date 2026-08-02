# L3-P0 Revision 2 — Independent Review

Status: `REVIEW_COMPLETE — REQUEST_REVISION`  
Reviewer: `Codex orchestrator, independent of revision author`  
Reviewed subject SHA-256: `7851b310d20420ce0f73bf4dcf2776e51d852614272dfe26e31697d526b803f2`

## Finding closure

The revision closes most of the prior review:

- fact envelope, producer set, request projection, resolved plan, observation,
  and unavailable result now have closed canonical contracts;
- the fixed eight-entry provenance vector is sorted, duplicate-free, and bound
  into the resolved plan digest together with request, authority-set, decision,
  adapter, and divergence inputs;
- the nine-path NEW inventory and five no-edit anchors are explicit; and
- hermetic forbidden-capability, canonicalization, schema, mutation, and digest
  sensitivity vectors materially strengthen the purity oracle.

## Remaining blocker

Two public function inputs from the prior finding remain outside the exact
contract inventory:

1. `build_shadow_observation(resolved, observation_metadata)` still accepts an
   unspecified `observation_metadata` value. The prose says authority fields are
   rejected, but no closed schema/canonical in-module type fixes the permitted
   metadata fields, lengths, encodings, ordering, or relationship to request and
   producer bindings.
2. `build_trusted_fact_unavailable(failure)` exposes an unspecified public
   `failure` value. Either make this an internal-only constructor reached from a
   typed resolver failure, or define a closed bounded failure-input contract;
   otherwise callers can shape error category/evidence without the claimed
   boundary validation.

Add the observation-metadata schema (and failure-input schema if the constructor
remains public), update the exact inventory and schema-validation vectors, and
state whether those values participate in the observation digest or are merely
validated redacted envelope fields. No adapter, persistence, dashboard, AQ-QA,
provider, or runtime path is needed.

## Verdict

`VERDICT: REQUEST_REVISION` — the provenance/digest and purity findings are
closed, but every public input is not yet a closed enforceable contract. A
hash-bound implementation authorization may not be prepared until the amended
subject receives a fresh independent PASS.

No implementation, activation, staging, commit, runtime, provider, network, or
deployment authority follows from this review.
