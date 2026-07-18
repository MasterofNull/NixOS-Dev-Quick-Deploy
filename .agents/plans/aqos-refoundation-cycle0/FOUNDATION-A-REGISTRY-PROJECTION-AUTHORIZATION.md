# Foundation A Registry Projection Authorization

Authorization ID: `auth-foundation-a-registry-projection-20260718`
Idempotency key: `foundation-a:ten-row-registry-projection:20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: the repository owner supplied the ten target decisions and directed completion of the
gating tasks; the content-bound owner record is independently accepted.

## Frozen inputs

- Registry predecessor `config/system-state-authorities.yaml`:
  `d88788f16e947b583dfc02b86e3dcb7cc32f70d0ab3551940bd729898d9502e3`.
- Accepted owner decision record:
  `.agents/plans/aqos-refoundation-cycle0/FOUNDATION-A-OWNER-ADJUDICATION-20260718.md`,
  SHA-256 `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a`.
- Owner-record review:
  `120064018d753dcbd144d348237e56b67459d397487c816f2f08b510c71b6921`.
- Accepted adjudication contract commit: `2dc7ab36`.
- Contract candidate hashes: schema
  `8b74069ddb85384e458ec16b5bfb18c607b8f0be34cb3d4dc4fd39de41a6ee63`, checker
  `4a4c93caecf3f4c18c46f64c13f9a2db0dcb48ed6624248e3a869712f51c3820`, tests
  `50b3051bac6ae7cc7acdf444017cc5b6b91bdf40dd95b393247b8c6cf12c0bc9`.

Any mismatch is a hard stop.

## Exact one-file grant

One bounded implementer may edit only `config/system-state-authorities.yaml` to:

1. set all ten existing rows to `adjudication_status: ADJUDICATED`;
2. project the exact logical target, `transition_owner: hyperd`, default deadline, and complete
   per-row rollback boundary from the accepted owner record;
3. bind every `decision_provenance` to decision ID
   `foundation-a-authority-targets-20260718`, `authority: OWNER`, `decided_by: hyperd`, decision date
   `2026-07-18`, the exact repo-relative source path above, and source SHA
   `3c05728f8011db002b8c1504757dd1b43421f151268718a0c275219ccd15bc7a`;
4. increment registry metadata/version and correct only the stale header wording needed to distinguish
   owner adjudication from physical convergence; and
5. preserve every `current_condition: SPLIT_BRAIN`, every observation/evidence field, every deadline
   unless the owner record explicitly says otherwise, and `meta.cycle1_authority: NOT_AUTHORIZED`.

The completed checker must report exactly: PENDING=0, ADJUDICATED=10, owner-decision blockers=0,
observed-convergence blockers=10, aggregate blockers/findings=10, errors=0, Cycle1 `NOT_AUTHORIZED`.
Strict mode must continue to exit 1 because convergence remains incomplete.

## Consumption and acceptance

The first completed exact one-file candidate report consumes this grant. Interruption without a
completed report does not. No staging, commit, deployment, delegation, or self-review. Integration
requires an independent exact-subject PASS, the 27-case contract suite, machine/strict/changed checks,
source digest proof, YAML/schema validation, diff hygiene, and Tier-0.

## Exclusions

No observed-condition change, writer retirement, source/runtime mutation, Cycle 1, Foundation B2
write, Postgres/outbox activation, Q1/Q10 decision, Track-V activation, live cutover, new lifecycle
store, schema/checker/test change, generated snapshot, dashboard/Phase0, Nix/deployment, or second file
is authorized.

`RECORD: prepared single-use projection of ten accepted owner decisions; convergence remains blocked.`
