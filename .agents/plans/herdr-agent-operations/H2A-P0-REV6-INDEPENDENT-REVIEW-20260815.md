---
doc_type: design-review
id: herdr-h2a-p0-rev6-independent-review-20260815
title: HERDR H2A-P0 revision 6 independent review
status: complete
reviewed_at: 2026-08-15T19:10:48Z
reviewer: Gibbs
reviewer_role: independent-reviewer
verdict: REQUEST_REVISION
runtime_authority: false
---

# HERDR H2A-P0 revision 6 independent review

## Exact reviewed subject

- `config/schemas/operator-context.schema.json`: `1f5df849c9ab09ea7218967147d8f5c43c42d817c7c8cf4ef6d72c5ffe23ec87`
- `config/operator-context-source-to-field-ledger.v1.json`: `8544ef93edb2a0b5c609dc70711ae7e54b13756361854e8732d57c36c6e7ef71`
- `scripts/ai/lib/operator_context_projection.py`: `e61cbf882d6b3e315d477e97c644e7b5d09fed0ff76805d392c42de58a732124`
- `scripts/testing/fixtures/operator-context-golden.json`: `9849e17b69f63d3382cc275b4fa77f0c98d4ffe7d74f4c5865d203c6018ce5f8`
- `scripts/testing/test-operator-context-projection.py`: `53fcb26ace5d4ffcb2df055b8ccb7b6a27ea57e1c588c52d3b14ab20cd6b9cab`

The submitted hashes matched the reviewed bytes.

## Blocking findings

1. Shell-fragment rejection is incomplete. `TEXT_RE` permits semicolons and `_text()` applies no additional shell-token check. A targeted pure replay with `mission.objective = "x;curl"` was accepted and emitted unchanged. The literal `$(x)` fixture is rejected by the generic character allowlist and therefore does not exercise allowed-character shell syntax.
2. The ledger attributes `mission.workflow_phase` to `agent_progress_facts`, while the resolver obtains and emits that value from `program_workflow_facts`. Schema-leaf equality passes despite false source provenance.

## Verified gates

The reviewer confirmed the intended `work[].progress_age` repair, the hermetic oracle, Draft 2020-12 validation of golden outputs, 71-leaf bidirectional schema/ledger parity, literal canonical bytes and digests, insertion-order stability, count-state pairing, sampling/skew and complete-input binding, expiry/issuer/subject/revocation handling, valid supersession and actual cycle/chain rejection, array and chain bounds, credential/path/control rejection, unknown preservation, empty controls, and the pure no-I/O boundary.

The reviewer made no repository modification and performed no staging, commit, activation, runtime, or HERDR operation.

VERDICT: REQUEST_REVISION — reject allowed-character shell fragments and align `mission.workflow_phase` ledger provenance with the implemented source.
