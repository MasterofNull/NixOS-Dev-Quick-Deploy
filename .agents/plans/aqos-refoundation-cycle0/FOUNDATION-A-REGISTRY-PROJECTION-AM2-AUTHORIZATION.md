# Foundation A Registry Projection AM2 — Semantic Fixture RSS Isolation

Authorization ID: `auth-foundation-a-registry-projection-am2-20260718`
Idempotency key: `foundation-a:ten-row-registry-projection:am2:20260718`
Parent: `auth-foundation-a-registry-projection-am1-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded gating tasks.

AM1 completed and consumed. Independent acceptance found that its in-process semantic calls to
`checker.run()` inherit the reviewer process's lifetime `ru_maxrss` (362 MiB), so they return budget
exit 3 even though the isolated CLI/subprocess budget test passes. This is test-process contamination,
not a production checker or registry failure.

## Frozen candidate

1. `config/system-state-authorities.yaml`
   `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a`
2. `scripts/testing/test-state-authorities.py`
   `4f3aeb027fa07db728ec9b4e0ec1292092b895a36bf04202d77d920b9a80de0d`

Production schema/checker remain frozen at
`8b74069ddb85384e458ec16b5bfb18c607b8f0be34cb3d4dc4fd39de41a6ee63` and
`4a4c93caecf3f4c18c46f64c13f9a2db0dcb48ed6624248e3a869712f51c3820`.

## Exact test-only grant

One bounded implementer may edit only file 2 to isolate or inject `_peak_rss_mib()` solely around
in-process semantic fixture calls, restoring it afterward even on failure. Test 26 must continue to
launch the real checker subprocess and verify the actual 256 MiB RSS/time/output budgets without any
injection. The suite must retain exactly 27 tests and all current state/provenance/date/rollback/
read-only coverage.

Run the suite from both a normal process and a deliberately high-RSS parent/reviewer context, plus
machine/strict/changed subprocesses, YAML/schema, Python compilation, digest/count proof, and diff
hygiene. Any production, registry, or second-test-file change requires AM3.

## Consumption and exclusions

The first completed exact two-hash report consumes AM2; interruption without completion does not.
No staging, commit, deploy, delegation, or self-review. Independent acceptance and Tier-0 remain
mandatory.

No checker/schema/config semantic change, budget relaxation, observed-condition/convergence change,
Cycle1/B2/Postgres, runtime, snapshot, dashboard/Phase0, Nix/deployment, Q1/Q10, Track V, or third file
is authorized.

`RECORD: prepared single-use semantic-fixture RSS isolation lease.`
