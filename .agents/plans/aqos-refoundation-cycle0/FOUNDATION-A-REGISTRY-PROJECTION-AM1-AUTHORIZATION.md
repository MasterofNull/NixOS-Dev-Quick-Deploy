# Foundation A Registry Projection AM1 — Test-State Transition

Authorization ID: `auth-foundation-a-registry-projection-am1-20260718`
Idempotency key: `foundation-a:ten-row-registry-projection:am1:20260718`
Parent: `auth-foundation-a-registry-projection-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded gating tasks.

The parent implementer correctly stopped without a completed report, so the parent grant is
unconsumed but retired as insufficient: it required the 27-case suite to pass while forbidding the
test expectations that necessarily change when the production registry transitions from PENDING to
ADJUDICATED.

## Frozen partial candidate

1. `config/system-state-authorities.yaml`
   `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a`
2. `scripts/testing/test-state-authorities.py`
   `50b3051bac6ae7cc7acdf444017cc5b6b91bdf40dd95b393247b8c6cf12c0bc9`

Frozen production contract: schema
`8b74069ddb85384e458ec16b5bfb18c607b8f0be34cb3d4dc4fd39de41a6ee63`, checker
`4a4c93caecf3f4c18c46f64c13f9a2db0dcb48ed6624248e3a869712f51c3820`.

Any mismatch is a hard stop. File 1 is frozen and must not change under AM1.

## Exact test-only grant

One bounded implementer may edit only file 2 to align production-registry assertions with the
authorized state transition:

1. assert the exact ten production rows are ADJUDICATED, content-bound to decision ID/source hash,
   while retaining `current_condition: SPLIT_BRAIN` and Cycle1 `NOT_AUTHORIZED`;
2. update current-registry blocker-dimension expectations to owner=0, convergence=10, aggregate=10,
   with convergence-only finding flags;
3. update the current-state half of the exact-count test to PENDING=0/ADJUDICATED=10 without weakening
   the independently constructed pending and adjudicated fixtures; and
4. advance the injected production-registry check date from 2026-07-17 to the owner decision date
   2026-07-18 so the test does not falsely classify a same-day decision as future, while preserving
   explicit future-date adversarial cases; and
5. keep exactly 27 tests and all schema/provenance/clock/rollback/read-only adversarial coverage.

Run the full 27-case suite, checker machine/strict/changed modes, direct source-digest/count proof,
YAML/schema parsing, Python compilation, and diff hygiene. Any checker/schema/config or second test
surface change requires AM2.

## Consumption and exclusions

The first completed exact two-hash report consumes AM1; interruption without a completed report does
not. No staging, commit, deployment, delegation, or self-review. Independent exact-subject acceptance
and Tier-0 remain mandatory.

No registry semantic change beyond the frozen candidate, observed-condition change, convergence,
Cycle1/B2/Postgres write, runtime, generated snapshot, dashboard/Phase0, Nix/deployment, Q1/Q10,
Track-V activation, or third file is authorized.

`RECORD: prepared single-use test-state transition lease; parent retired unconsumed.`
