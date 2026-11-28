# Control-plane consolidation S1 (contract guard, CI trust boundary, ADRs)

## Objective

Slice S1 of the control-plane consolidation plan (rev 5, amended to rev 5.1): a Rust contract guard driven by `config/system-state-authorities.yaml`, run always in tier0 and as a required CI check whose privileged half never builds or runs candidate code; a derived `CONFIG_SCHEMA_REGISTRY`; ADRs 0001-0015; the architecture summary and Phase 0 evidence moved under `docs/`; the stale switchboard schema path recorded as a dated exception. S1 was built in two parts: S1A (the crate, registry fields, tier0 check) and S1B (this document's CI trust boundary, derived registry, ADRs, docs, amendment).

Not done here: GitHub branch protection must list `contracts-boundaries` as a required status check (repository setting, owner act); the real `model-coordinator` schema (S3); the other four dangling `$schema` references listed under Residual Risk.

## Workflow/Session IDs

- Plan: `.agents/plans/control-plane-consolidation-20261122/` (DESIGN.md rev 5.1, REVIEW-R5.md "Amendment rev5.1").
- Worktree: `.claude/worktrees/agent-a427f5668420a28de`, HEAD `1e0f03a59` (origin/main), changes staged and not committed.
- Author: Simurg@claude/sonnet#s1-part-b (headless implementer, explicit `sonnet` override).
- Reviewer: to be chosen from the lane-eligibility registry at review time (see Delegation Decision).

## Delegation Decision

Rule 18 record (also in REVIEW-R5.md "S1 author substitution"). The S1 plan reserves Codex as author for the Rust crate and CI. Codex was usage-limited twice on 2026-11-27, so S1 is authored by Claude Sonnet with an explicit `sonnet` model override as a headless implementer. The reason is availability, not a capability gap. The reviewer must be a non-author lane chosen from the registry at review time: Codex when available, else Gemini (reviewer), else Opus (same vendor, different model, last resort, flagged). Sonnet holds a reviewer grant but may not review this slice (never self-review). Binding acceptance under D11 is a non-author Codex or Claude lane (Opus for Claude, since Sonnet holds no binding-acceptance grant). Local Qwen was not used for S1B: the work is multi-site and trust-critical, outside the local capability envelope.

## Commands Executed

All inside the worktree; no commit, no push, no rebuild.

- `cargo build --release -p harness-contracts`, `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`.
- `scripts/governance/contracts-corpus.sh target/release/harness-contracts .` (known-bad corpus).
- `python3 scripts/testing/test-contracts-ci-trust.py` (N2, N4, N8), `python3 scripts/testing/test-config-schema-derived.py`, `python3 scripts/testing/test-config-loader.py`, `bash scripts/governance/tier0.d/check-config-contracts.sh`.
- `python3 scripts/governance/check-workflow-trust.py`, `python3 scripts/governance/check-workflow-masks.py`.
- `harness-contracts --root . contracts --write-lock` after the schema edits (contracts/.lock).
- Seeded refusal: staged `scripts/ai/aq-role-route-canary.py` (import of a K1 module from K2) and `scripts/ai/corpus-canary.sh` (`eval "$CMD"`), ran `scripts/governance/tier0.d/check-contracts.sh --pre-commit`, then unstaged and moved both out of the tree.
- `python3 scripts/governance/tier0.d/check-plan-paths.py`, then the full `scripts/governance/tier0-validation-gate.sh --pre-commit` (result below).

## Validation Evidence

S1A mutation results (reproduced this session as the trusted corpus `tests/contracts-corpus/cases`, run through `scripts/governance/contracts-corpus.sh`; the S1A author's own mutation log was not available to this session). Each case mutates a throwaway git repo built from the trusted tree and requires the checker to fail with a specific message:

| Case | Mutation | Required result | Observed |
|---|---|---|---|
| ok-clean-tree | none (control) | `PASS: contracts` | PASS |
| n1-deleted-decision-row | delete the D06 row | `decision row D06 was deleted` | fails as required |
| n3-extended-exception-expiry | extend a baseline exception expiry | message contains `expiry` | fails as required |
| n7-edited-published-schema | edit a locked schema | `changed since it was locked` | fails as required |
| n5-dynamic-call-in-scope | unannotated `eval` in scanned scope | message contains `dynamic` | fails as required |

Unit tests: `cargo test --workspace` 26 passed (includes n1, n3, n5, n6, n7 cases in `contracts.rs` and `boundaries.rs`); `cargo fmt` and `cargo clippy -D warnings` clean.

N2, N4, N8 (`scripts/testing/test-contracts-ci-trust.py`, PASS). Each runs the unfixed behaviour next to the fix:

- N2, a checker edited to return success. Without the corpus, a stub that prints PASS and exits 0 is accepted on a known-bad tree (asserted: rc 0). With `contracts-corpus.sh` run from the trusted checkout it fails (rc non-zero), and the packaged checker passes the same corpus, so the corpus is satisfiable.
- N4, a candidate weakens the corpus. When the corpus is read from the candidate (every case rewritten to expect a pass), the lying stub passes (asserted: rc 0). Read from the trusted root, the stub still fails. `.github/workflows/contracts-candidate.yml` checks the base commit out into `trusted/` and runs the runner and corpus from there.
- N8, privileged-context invariant. `scripts/governance/check-workflow-trust.py` fails a `pull_request_target` job that checks out the PR head, or runs a build or script at or after the step that materialises the head (three canary workflows: checkout of head, fetch then build, same-step exec); the older mask lint returns no finding on all three (asserted), so the new lint is the only detection. A `pull_request` job that builds the PR head passes (it is the unprivileged half), and so do all real workflows. Mutating the real `contracts-boundaries.yml` (add `ref: head.sha` to the checkout, or `cargo build` after the fetch) is reported by the lint; the unmutated file passes. The test also asserts the privileged workflow holds no `secrets.` or `GH_TOKEN`, declares `contents: read` only, and builds the base checker before the PR head is fetched.

N6 (derived registry), `scripts/testing/test-config-schema-derived.py`: a registered model with no `config_files` row and a row with no model both fail; the real tree is 1:1 (`config/switchboard-profiles.yaml`). `reference_exceptions` keeps the stale `./schemas/model-coordinator-schema.json` as a dated exception to 2027-03-31 (slice S3); the test fails if the exception goes stale or expires.

Seeded refusals (`tier0.d/check-contracts.sh --pre-commit`, staged canaries, rc 1):

- `scripts/ai/aq-role-route-canary.py:2: import: import 'lib.task_registry' crosses K2 -> K1; owner: K1 (must name: contracts.events)`
- `scripts/ai/corpus-canary.sh:2: dynamic: dynamic construct eval; owner: UNASSIGNED (must name: annotate with `# contract: <id>` naming the enforcing contract)`

After removal the same command prints PASS for contracts and boundaries. A required-CI refusal on a seeded violation in a throwaway PR cannot be shown before the workflows exist on `main`: the privileged workflow treats a base without the guard as a bootstrap (warning, exit 0) and the owner must set the required check first.

Latency (2026-11-27, release build, whole repo): `contracts --base-ref` 33 ms, whole-tree `boundaries` 905 ms over 1415 scanned files, `boundaries --staged` 93 ms, `decisions --count` 12 ms; `check-contracts.sh --pre-commit` about 0.45 s wall.

Matrix counts (`harness-contracts decisions --count`): 28 rows; overlapping rows 7 verified, 4 carried, 5 unverified; excess-writer total unknown (17 rows lack a verified writer list), no upper bound; 6 verified orphans, 1 new, 5 single-owner.

tier0 (`scripts/governance/tier0-validation-gate.sh --pre-commit`, full run in the worktree): first run failed 3 gates caused by this slice or S1A and fixed here (basedpyright on `test-contracts-ci-trust.py`; `check-contracts.sh` had no gate-mutation case and `check-config-contracts.sh`'s mutation sandbox lacked the registry YAML, both fixed in `test-tier0d-gate-mutation.py`, now 40/40; `test-plans-index.py` needed `.plan-classification.json`; `check-ci-test-coverage` needed `--only` entries in `test.yml`). Final run: Passed 76, Failed 0, exit 0. Non-blocking WARNs seen: lane-hook parity (2 gaps) and review-receipt audit items on PRs 868-877, none from this change.

## Rollback Plan

Nothing is committed. Before commit, `git restore --staged` and revert of the worktree discards S1B. After merge: the privileged workflow is a no-op until `contracts-boundaries` is made required, so removing the required check (owner act) disables it; `tier0.d/check-contracts.sh` is one file and can be reverted in one commit; the registry additions are additive YAML fields that the Python checker ignores; `CONFIG_SCHEMA_REGISTRY` falls back to an empty registry if the YAML cannot be read, and `check-config-contracts.sh` then fails loudly. Rev 5.1 text changes revert with the plan files.

## Residual Risk

- The `contracts-boundaries` check is not required until the owner adds it in repository settings; the bootstrap rule (base without the guard passes with a warning) is closed once the guard is on `main`.
- `refs/pull/N/head` is fetched anonymously on a public repo; the candidate worktree is read as data, but a candidate symlink is followed by the scanner. The job holds no secrets and no write token, so the exposure is a read of runner files whose contents are never printed.
- The privileged job builds the base checker with `cargo` on the runner (no vendored crates today, so no network step); a future crate dependency adds a supply-chain input to that job.
- Four other configs carry a dangling `$schema` (`capability-lifecycle-registry`, `reasoning-profiles`, `route-aliases`, `tool-pins`). They are not in `reference_exceptions` yet and are not gated; log and register them with their owning slices.
- The writer total stays unknown until each row has a verified writer list; no zero claim is made.
- Rev 5.1 changes bound files (DESIGN.md, tracker.json) and needs re-review; F2 (S12 acceptance wording) is deferred to the S12 slice as listed.
- Dynamic calls: an annotated site is not proven safe (scanner limit declared in DESIGN.md).

## Hint Feedback

Hints were not queried for this slice (headless sub-agent, slim payload, no aq-session-start). The plan files, REVIEW-R5.md followups and the S1A tool were the grounding. Friction found: `check-plan-paths.py` strips only a single `:line` suffix (not `:a,b` lists or ranges) and ignores paths that start with `.`; an `aq-hints` entry for plan authors would save the rewrite. No hint outcome to record.
