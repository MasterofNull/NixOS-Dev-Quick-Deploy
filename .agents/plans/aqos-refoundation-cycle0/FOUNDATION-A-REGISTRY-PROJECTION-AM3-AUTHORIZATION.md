# Foundation A Registry Projection AM3 — Linux RSS Validation Split

Authorization ID: `auth-foundation-a-registry-projection-am3-20260718`
Idempotency key: `foundation-a:ten-row-registry-projection:am3-rss-validation:20260718`
Parent: `auth-foundation-a-registry-projection-am2-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded gating tasks.

AM2 remains unconsumed. Its semantic isolation implementation is correct, but its validation contract
was contradictory on Linux: a child process inherits the already-high parent's lifetime `ru_maxrss`
across fork/exec, so test 26 cannot both run from a 358 MiB parent and prove a <=256 MiB child budget.
Independent standalone checker processes run near 50 MiB and satisfy the real gate.

## Frozen no-edit candidate

1. `config/system-state-authorities.yaml`
   `d45c83720847f6342d5ff13597810b46c7c2ad58c1c1342fdbc3e9236452ac1a`
2. `scripts/testing/test-state-authorities.py`
   `ec2983cd17c551f9c6e8e28336a74ef3fd6964502347ab64dcdc15397ace4578`

Schema/checker remain frozen at the accepted contract hashes. No implementation file may change
under AM3.

## Exact validation-only grant

One bounded validator/implementer may issue a completed report only after proving:

1. a normal clean-process full suite passes all 27 tests, including test 26's real uninjected
   subprocess time/RSS/output gates;
2. a deliberately >256 MiB parent runs the 26 semantic tests excluding test 26, and all pass through
   the failure-safe semantic RSS injection;
3. separately launched clean checker machine/strict/changed processes satisfy actual budgets and
   exact 0-owner/10-convergence/10-aggregate counts;
4. the high-parent inheritance reproduction is retained as evidence, not misclassified as a checker
   regression; and
5. YAML/schema, digest/provenance/count, Python compilation, and diff hygiene pass.

Any file modification requires AM4.

## Consumption and exclusions

The first completed exact two-hash validation report consumes AM3; interruption without completion
does not. No staging, commit, deployment, delegation, or self-review. Independent final acceptance
and Tier-0 remain mandatory.

No file change, budget relaxation, checker/schema/config semantic change, convergence, Cycle1/B2/
Postgres, runtime, dashboard/Phase0, Nix/deployment, Q1/Q10, or Track V is authorized.

`RECORD: prepared single-use no-edit Linux RSS validation split.`
