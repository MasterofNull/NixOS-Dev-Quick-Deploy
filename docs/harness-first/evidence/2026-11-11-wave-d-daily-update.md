# Wave D: daily system update separated from the LLM domain

Date: 2026-11-12 (recovery of Codex candidate `e87fe145c`, Wave D of delivery-loop simplification S4)

## Objective

Separate the daily system-update domain (flake inputs, `aq-update`) from the lower-frequency LLM domain (models, profile).
PRD: `.agent/PROJECT-WAVE-D-RECOVERY-PRD.md`. Original Codex staged diff preserved at
`.agents/delegation/outputs/wave-d-original.diff`.

- `aq-update --daily` / `--refresh-inputs` (aliases, may be combined): prepare-phase mode that refreshes inputs even with no
  Nix-affecting repo change. Unchanged refreshed lock: prints "nothing to deploy", syncs the checkout, no READY, no sudo.
  Changed lock: lands via aq-land and ends with the single READY line; `aq-update --deploy` (unchanged) rebuilds. Mode is
  recorded in the ledger `begin` event so `--resume` keeps it. Rejected with `--deploy`; duplicate flag rejected.
- `aq-model-eval --status`: offline LLM-domain report (profile + freshness, catalog, coordinator tiers, models dir links and inventory).
- `config/model-catalog.yaml`: registers on-disk `qwen3.5-9b` (recommended_gpu_layers 12, Renoir ceiling) and `qwen3-embedding-4b`. The
  active model is not changed (owner decision on Q4_K_XL stays open).
- `test-model-probe-freshness.py`: status edge cases (dangling active link, missing models dir, offline).

## Workflow/Session IDs

Original work: Codex session (Wave D candidate, worktree recovery-wave-d-update-20261111). Rebase onto #745/#746/#747 and
re-implementation of the aq-update part: Claude Sonnet 5.5 sub-agent, 2026-11-12. Not committed, no tier0, no PR (by instruction).

## Delegation Decision

Bounded recovery slice under PRD PLAN_READY; catalog, aq-model-eval and probe-test staged changes were kept as Codex wrote them
(main had not touched those files). `aq-update` and `test-aq-update.py` were re-written against #745's structure, not forced from the old diff.

## Commands Executed

- `git diff --cached > .agents/delegation/outputs/wave-d-original.diff`
- `git fetch origin`; `git checkout HEAD -- aq-update test-aq-update.py`; `git merge refs/remotes/origin/main` (7c0a84ea7, then 11e6e7aec); clean, no conflicts
- `python3 scripts/testing/test-aq-update.py`, `test-aq-update-tiers.py`, `test-model-probe-freshness.py`, `test-local-agent-config.py`
- the new tests copied into a detached worktree of origin/main (removed afterwards) to confirm they fail there
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`; `aq-model-eval --status --json`

## Validation Evidence

- test-aq-update: 37/37 pass (33 existing + 4 new: daily no-change refresh prepares nothing and `--deploy` then refuses; refreshed lock
  with no repo delta ends with one READY line, no sudo, then `--deploy` rebuilds; kill in `flake check` then plain `--resume` keeps daily
  mode and ends READY with no sudo; alias pair, dry-run changes nothing, bad combinations exit 2).
- On origin/main (11e6e7aec) with the new test file: 33/37, the 4 daily tests fail (usage error).
- test-aq-update-tiers: 8 passed. test-model-probe-freshness: PASS. check-ci-test-coverage: PASS (779 tests).
- test-local-agent-config: FAILS identically on origin/main (hyperd pins qwen3.6-35b-mtp rather than -q5); already a registered
  known-failing exemption in config/ci-checks.json, unrelated to this change.
- `local-inference-l2b-payload-golden.json` does not reference any changed file; no hash refresh needed.

## Rollback Plan

Nothing is committed. Discard the branch `recovery-wave-d-update-20261111`; the original diff is kept in `.agents/delegation/outputs/`.
Runtime rollback: none needed (`--daily` is opt-in and manual; catalog additions are inert until selected).

## Residual Risk

- `--daily` was exercised only against stubbed nix/aq-land/deploy; no real flake update or deploy was run.
- `aq-model-eval --status` ran on this host only with the models dir as found.
- Nothing schedules `--daily`; it is on demand. A timer is a separate decision (Rule 15 activation not attested here).
- Rebuild items: none for this change (scripts and catalog yaml only; checkout sync). A real `--daily` that lands a lock will need the usual `aq-update --deploy`.

## Hint Feedback

No aq-hints were consulted for this recovery. Useful: the PRD and the preserved original diff made intent unambiguous.
