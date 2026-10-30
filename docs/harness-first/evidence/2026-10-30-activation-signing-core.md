# Activation signing core (slice 1): verifier library and single ACTIVATED path

## Objective

Slice 1 of the activation signing MVP (design: `.agents/plans/system-integrity-recovery/ACTIVATION-PIPELINE.md`, rev7). Add a pure verification library for the signed activation chain, make `scripts/ai/aq-pm-tracker` reach ACTIVATED only through `activation_verified`, and fix the false-SHIPPED projection. No root, no key provisioning, no Nix (slice 2).

## Workflow/Session IDs

- Branch `feat/activation-signing-core` (worktree `.agents/delegation/worktrees/activation-signing-core`)
- Implementer: Claude Sonnet 5.5 sub-agent dispatched by the orchestrator; uncommitted, left for orchestrator review.

## Delegation Decision

Bounded single-slice implementation on the Claude balanced tier (Rule 17). Independent review is the orchestrator's to route (not the implementer).

## Commands Executed

- `python3 scripts/testing/test-activation-chain.py`
- `python3 scripts/testing/test-pm-tracker-untrusted-hold.py`, `python3 scripts/testing/test-pm-tracker-acceptance-authority.py`, `python3 scripts/testing/test-dashboard-program-progress.py`
- `python3 scripts/ai/aq-pm-tracker --all-json` before and after the change
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Validation Evidence

- New test: 19 tests OK (relabel, domain separation, wrong key, replay, deleted revoke, truncated tail, segment beyond head blocks all and recovers, missing/corrupt head, missing dir, wave cannot clear revoke, individual regrant, wave forgery/duplicates, closure change, deployment mismatch, plus tracker cases: accepted-without-grant not ACTIVATED for is_activation/systemd/command items, service with verified grant ACTIVATED, stale/edited attestation, projector grep, false-SHIPPED fixtures).
- Existing pm-tracker tests pass (untrusted-hold, acceptance-authority, dashboard-program-progress). `check-ci-test-coverage.sh`: PASS.
- `aq-pm-tracker --all-json` before: SHIPPED 143 / ACTIVATED 0; after: SHIPPED 140 / ACTIVATED 0 (3 items SHIPPED to IN-PROGRESS, from the false-SHIPPED fix).
- Not covered here (slice 2): evidence-copy baseline recompute, Nix allowlist/eligibility manifest, signer, live round trip.

## Rollback Plan

Revert the slice commit. Reverting only the `aq-pm-tracker` hunk is not a valid rollback (it restores the unsigned `accepted`-based ACTIVATED path); keep the verifier and revert only new tooling per the design's Rollback section.

## Residual Risk

- The checkout projector reads chain, head and signers from fixed paths (`/var/lib/aq-activation`, `/etc/aq-activation/signers.json`) that do not exist yet, so nothing can be ACTIVATED until slice 2. It is not yet the store-installed verifier; the `unverified-checkout` marking is slice 2.
- `evidence_baseline_sha256` is carried and compared by the signed grant but not recomputed from a root-owned evidence copy yet.
- The CI `syntax` job now installs `cryptography` (setup-python + `uv pip install --system`) and runs `activation-chain-test`; the test fails hard if the module is missing.
- The expected deployment id comes from `/etc/aq-activation/deployment-id` (slice 2 provisions it from Nix); until present the chain is invalid and nothing ACTIVATES.
- Per-item `activation_stale` / `grants_unverified` and per-plan counters are emitted by the projector; a stale grant projects SHIPPED.

## Hint Feedback

No aq-hints were queried for this slice; design SSOT was read directly.
