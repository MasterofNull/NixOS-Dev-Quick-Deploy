# Implementation Authorization — Foundation A Adjudication Contract

Authorization ID: `auth-foundation-a-adjudication-contract-20260718`
Idempotency key: `aqos:foundation-a:adjudication-contract:c0:20260718`
Status: **PREPARED_ONLY — PENDING INDEPENDENT AUTHORIZATION REVIEW**
Owner basis: the repository owner directed completion of the gating tasks and supplied the ten
mechanical authority targets on 2026-07-18.

## Frozen inputs

- Accepted design SHA-256:
  `13a2a13c20f4a9df75ccb7a9def545e05be59e3b58b053129cd5438ce0abb82e`
- Design review SHA-256:
  `0ddf36ef3ed790ecc1e84d51012f6203411a0fe89ff2a059bf511b8bf92f2b2a`
- Design commit: `295273f5`
- Current C0.3 implementation acceptance commit: `fcb39571`

## Exact three-file implementation lease

1. `config/schemas/system-state-authorities.schema.json`
   predecessor SHA-256 `122b2a47f71912b53ee2be4daa3017a06d64f44f544047e5832f61f73d4a8d78`
2. `scripts/governance/check-state-authorities.py`
   predecessor SHA-256 `5ebce0f038a99d8679ace58f07202c4a8f41a0e04926efb0e6b4bd2cca056cc6`
3. `scripts/testing/test-state-authorities.py`
   predecessor SHA-256 `703eb2bb7b4edfa5930743d7d2745056c20019cc5c64b45c0cc20340df742db3`

Any mismatch before implementation or any fourth implementation file is a hard stop.

## Grant

One bounded Codex implementer may implement exactly the accepted design in the three files above:

- preserve all current unadjudicated-row behavior and output keys;
- add the closed adjudication fields/invariants and deterministic identity/date checks;
- produce the mandatory additive finding flags and meta counts;
- preserve truthful observed-condition blockers after adjudication;
- implement the complete 27-case focused matrix;
- keep the checker read-only, bounded, deterministic, and free of model/network/runtime writes.

The implementer may run the focused test and checker. It may not stage, commit, delegate, deploy, edit
the registry rows, claim owner decisions, review its own work, or touch Phase0/dashboard/runtime files.

## Consumption and acceptance

The first completed exact three-file candidate consumes this grant regardless of later verdict.
Interruption without a completed candidate does not consume it. `REQUEST_REVISION` requires a new
amendment and idempotency key.

Integration requires exact candidate hashes, the 27-case focused suite, current-registry and fully
adjudicated-fixture count evidence, checker budget/read-only proof, and an independent exact-subject
`PASS` from an agent/session that did not author or materially rewrite the candidate.

## Non-authority

This contract slice does not adjudicate any row, alter observed `SPLIT_BRAIN` conditions, authorize
Foundation B2 or Cycle 1, choose a physical state store, create a lifecycle store, change runtime
writers/readers, deploy, migrate, cut over traffic, or archive rejected evidence.

`RECORD: prepared single-use three-file contract grant; inactive until independent PASS.`
