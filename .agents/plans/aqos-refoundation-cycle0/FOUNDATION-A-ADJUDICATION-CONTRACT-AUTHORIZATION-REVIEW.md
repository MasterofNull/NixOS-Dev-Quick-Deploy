# Foundation A Adjudication Contract — Independent Authorization Review

**Verdict:** `PASS`
**Authorization state:** `ACTIVE` for the exact single-use grant reviewed here
**Reviewed authorization:** `FOUNDATION-A-ADJUDICATION-CONTRACT-AUTHORIZATION.md`
**Reviewed authorization SHA-256:**
`9bd23da3526785db340b5885effb4f97e820da6a578e0a2a9c9815bba0d659ec`
**Authorization ID:** `auth-foundation-a-adjudication-contract-20260718`
**Idempotency key:** `aqos:foundation-a:adjudication-contract:c0:20260718`
**Review date:** 2026-07-18 UTC
**Reviewer:** Codex sub-agent, OpenAI GPT-5 model family
**Role:** independent read-only authorization reviewer; the reviewer did not author the authorization,
design, or future implementation candidate and did not adjudicate an authority row

## Activation boundary

This independent `PASS` satisfies the reviewed document's activation condition and activates exactly
one bounded implementation grant for one Codex implementer. The grant permits modification of only:

1. `config/schemas/system-state-authorities.schema.json`
2. `scripts/governance/check-state-authorities.py`
3. `scripts/testing/test-state-authorities.py`

It permits implementation and focused validation of the accepted Foundation A adjudication contract.
It does not permit staging, commit, delegation, deployment, registry-row edits, owner-decision claims,
self-review, Phase-0 or dashboard changes, runtime changes, migration, cutover, lifecycle-store work,
Foundation B2 activation, or Cycle-1 authority.

## Frozen-input verification

The exact authorization bytes recomputed to the reviewed SHA above. Its frozen inputs were independently
verified:

- Accepted design SHA-256:
  `13a2a13c20f4a9df75ccb7a9def545e05be59e3b58b053129cd5438ce0abb82e`.
- Independent design review SHA-256:
  `0ddf36ef3ed790ecc1e84d51012f6203411a0fe89ff2a059bf511b8bf92f2b2a`.
- Design commit `295273f59e8ccc6ef61398a1a4e6e6cf5f46a17d` contains exactly the design and
  independent review artifacts and records the same reviewed hashes and non-authority boundary.
- C0.3 implementation-acceptance commit `fcb39571338784607e36676e256f0a73693985d0`
  preserves exact-current implementation acceptance while leaving all ten `SPLIT_BRAIN` decisions,
  Cycle-0 ratification, and Cycle-1 authority unresolved.

The predecessor hashes also match the current clean implementation surfaces exactly:

| Leased path | Verified predecessor SHA-256 |
|---|---|
| `config/schemas/system-state-authorities.schema.json` | `122b2a47f71912b53ee2be4daa3017a06d64f44f544047e5832f61f73d4a8d78` |
| `scripts/governance/check-state-authorities.py` | `5ebce0f038a99d8679ace58f07202c4a8f41a0e04926efb0e6b4bd2cca056cc6` |
| `scripts/testing/test-state-authorities.py` | `703eb2bb7b4edfa5930743d7d2745056c20019cc5c64b45c0cc20340df742db3` |

Any predecessor drift before implementation or any fourth implementation file is a hard stop and is
not covered by this verdict.

## Grant integrity

- Repository search found the authorization ID and idempotency key only in the reviewed authorization;
  no duplicate or prior consumption record exists.
- The owner basis is sufficient and bounded: on 2026-07-18 the repository owner directed completion of
  the gating tasks and supplied the ten mechanical authority targets. This grant implements only the
  contract capable of recording later decisions; it does not treat those targets as already recorded
  or converged.
- The implementation obligation matches the accepted design: closed adjudication schema, deterministic
  identity and injected-UTC-date validation, mandatory additive blocker dimensions and counts, truthful
  convergence-only findings, and the complete 27-case focused matrix.
- The checker remains read-only, bounded, deterministic, and free of model, network, service-control,
  database, or runtime-writer effects.
- The first completed exact three-file candidate consumes this grant, regardless of its later review
  verdict. An interruption without a completed candidate does not consume it. `REQUEST_REVISION` after
  a completed candidate requires a new amendment and a distinct idempotency key.
- Integration remains separately gated on exact candidate hashes, focused 27-case evidence,
  current-registry and fully adjudicated-fixture count evidence, budget/read-only proof, and an
  independent exact-subject `PASS` by an agent/session that did not author or materially rewrite the
  candidate.

## Non-authority

Activation of this contract-only implementation grant does not adjudicate any authority row, modify
`config/system-state-authorities.yaml`, change an observed `SPLIT_BRAIN` condition, infer physical
convergence, choose a state store, authorize Foundation B2 or Cycle 1, grant a runtime writer or reader,
archive rejected evidence, deploy, migrate, restart a service, or cut over traffic.

`RECORD: authorization ACTIVE for exact SHA-256 9bd23da3526785db340b5885effb4f97e820da6a578e0a2a9c9815bba0d659ec; single-use key unconsumed until the first completed exact three-file candidate.`

VERDICT: PASS — exact single-use three-file Foundation A adjudication-contract implementation grant is active
