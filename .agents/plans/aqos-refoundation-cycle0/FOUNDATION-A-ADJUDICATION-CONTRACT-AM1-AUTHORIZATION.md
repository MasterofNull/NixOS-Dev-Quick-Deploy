# Foundation A Adjudication Contract — Amendment 1 Authorization

Authorization ID: `auth-foundation-a-adjudication-contract-am1-20260718`
Idempotency key: `foundation-a:adjudication-contract:am1:20260718`
Parent authorization: `auth-foundation-a-adjudication-contract-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: the owner preauthorized the bounded plans, slices, and tasks needed to complete the
stated refactor goals; the original single-use implementation grant was consumed by a completed
candidate that received `REQUEST_REVISION`.

## Frozen revision baseline

1. `config/schemas/system-state-authorities.schema.json`
   `932c6af6a918fe050ee0c33b6d195f3ccf5e61f0b2c320a7dcfb4f0de765f02e`
2. `scripts/governance/check-state-authorities.py`
   `482b4a157b47112973a25136bb7d6eb146e70ce78548fe6aa466b6deec70e9cf`
3. `scripts/testing/test-state-authorities.py`
   `0669e00a65372ece365aa42a598b4b3c3bfee32335937067f594ecda63a4dff9`

Bound design SHA-256:
`13a2a13c20f4a9df75ccb7a9def545e05be59e3b58b053129cd5438ce0abb82e`.

Bound original authorization SHA-256:
`9bd23da3526785db340b5885effb4f97e820da6a578e0a2a9c9815bba0d659ec`.

Bound exact-candidate review: `/root/foundation_a_candidate_review`, `REQUEST_REVISION`, candidate
hashes exactly as listed above.

Any baseline mismatch before implementation is a hard stop.

## Exact revision grant

One bounded implementer may edit only the three frozen files to:

1. reject whitespace-only `rollback_boundary.trigger`, `.action`, and
   `.authority_during_rollback` deterministically in both schema/checker contract as appropriate;
2. add focused positive and negative cases covering all four rollback strings, including the already
   normalized owner field;
3. correct the stale schema description so owner adjudication clears only the owner-decision
   dimension and does not imply C0.3 ratification or physical convergence; and
4. rerun the focused matrix, machine/strict/changed modes, JSON parsing, Python compilation, and diff
   hygiene.

No other semantic, vocabulary, output-shape, budget, provenance, date, count, or convergence change
is authorized. If the tests reveal a different defect, stop and request AM2.

## Consumption and acceptance

The first completed exact three-file revision report consumes AM1. Interruption without a completed
candidate does not consume it. The implementer may not stage, commit, deploy, delegate, or review its
own work. Integration requires new exact hashes and an independent exact-subject `PASS` from a
different agent/session.

## Exclusions

This amendment does not authorize registry-row adjudication, authority convergence, Cycle 1,
Foundation B2, runtime routes, Phase 0, dashboard changes, Nix/deployment work, evidence disposition,
or any fourth implementation file.

`RECORD: prepared single-use correction lease; owner standing preauthorization activates it only after independent review PASS.`
