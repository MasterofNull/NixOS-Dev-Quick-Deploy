# Runtime state out of tracked config (P1.10 F2)

## Objective
Stop runtime jobs from rewriting tracked, build-affecting files (`ai-stack/prompts/registry.yaml` `mean_score`/`last_evaluated`; `config/frontier-radar-registry.json` `updated_at`), which dirtied the main checkout and made `scripts/governance/check-deploy-source.sh` refuse rebuilds. Runtime-mutable fields now live in gitignored state files; tracked files keep static content only.

## Workflow/Session IDs
Slice P1.10 F2, branch `fix/rebuild-path-runtime-state`, worktree `.agents/delegation/worktrees/runtime-state`. Session ID: not recorded (delegated implementer run).

## Delegation Decision
Bounded implementer slice delegated by the orchestrator (Rule 17); implemented on Claude balanced tier (Sonnet 5.5). No commit/push performed by the implementer.

## Commands Executed
- `rg` for writers of both files; read of `nix/modules/roles/ai-stack.nix` (`ai-prompt-eval` unit, ~L2240) and `nix/modules/services/durable-sweeper.nix`.
- `python3 scripts/testing/test-runtime-state-out-of-tracked-config.py` (red on pre-fix code, green after).
- `test-radar-ingest`, `test-prompt-eval-transport-guard`, `test-aq-report-prompt-registry-fallback`, `test-aq-report-prompt-cache-fallback`, `test-functional-prompt-eval`, `test-gepa-prompt-compile`, `test-hints-agent-lessons`, `test-hints-route-selection`, `test-ci-test-coverage-gate`, `tier0.d/check-ci-test-coverage.sh`.

Writers found:
- `scripts/ai/aq-prompt-eval` `update_registry_entry` (regex rewrite of `mean_score`, `last_evaluated`) and `registry_path.write_text` in `run_eval`; run by systemd service/timer `ai-prompt-eval` (`nix/modules/roles/ai-stack.nix`, User=primaryUser, ReadWritePaths=`ai-stack/prompts`) and by hand.
- `scripts/ai/aq-radar-ingest` `save_registry` (`data["updated_at"] = now`, rewrite of the registry) called from `discover`; `scripts/testing/test-radar-ingest.py` ran `discover` against the tracked file and rewrote it in cleanup (the likely source of the observed `updated_at`-only diff). The sweeper unit (`aq-durable-sweeper`, user service) only runs `scan`, which does not save the registry.

Fix: `aq-prompt-eval` writes `ai-stack/prompts/eval-state.json` (override `AQ_PROMPT_EVAL_STATE`), atomic via tmp+replace; `registry.yaml` is never rewritten. Readers (`scripts/ai/aq-report` `read_prompt_registry`, `hints_engine_impl.py` `_hints_from_registry`) merge the state file, state wins; the in-file `mean_score` remains the seed value (compat). `aq-radar-ingest` writes `updated_at` to `config/frontier-radar-state.json` (override `AQ_RADAR_STATE_PATH`; registry override `AQ_RADAR_REGISTRY_PATH`); `load_registry` merges it over any legacy in-file value; the legacy `updated_at` was removed from the tracked registry in this change, and `save_registry` never writes it and skips the rewrite when the content is unchanged. Both state files are in `.gitignore`. No Nix change needed: the prompt-eval state file sits inside the already-declared `ReadWritePaths` directory (Rule 13 satisfied declaratively). `test-radar-ingest.py` now runs against a temp copy (scan dropped: network + writes `.agent/research`) and was removed from `ci_exempt`/`test_exempt` and added to the `tests-misc-n-r` group together with the new test.

## Validation Evidence
- Red (pre-fix code, new test): `AssertionError: tracked registry.yaml was rewritten by aq-prompt-eval`.
- Green (with fix): `PASS: aq-prompt-eval leaves registry.yaml untouched, writes eval-state.json, aq-report merges it` / `PASS: aq-radar-ingest keeps updated_at in the state file, not the tracked registry` / `ALL RUNTIME-STATE TESTS PASSED`.
- Related suites pass (outputs in the implementer report); `check-ci-test-coverage` PASS (755 tests: 611 declared, 144 exempt); `git status` after the runs shows no change to `registry.yaml` or `frontier-radar-registry.json`.

## Rollback Plan
Revert the commit; delete the gitignored `eval-state.json` / `frontier-radar-state.json` (archive per Rule 12). Scores then fall back to the seed values in `registry.yaml`.

## Residual Risk
- Coordinator `hints_engine_impl` resolves the state file beside its registry path; if the coordinator runs from a Nix store copy of the repo instead of `repoPath`, it will not see `eval-state.json` and uses seed scores (same staleness as before for a store copy). Not verified live (no restart permitted).
- Existing registry `mean_score` values are seeds; the next prompt-eval run populates the state file.
- Radar `scan` is no longer covered by the CI test (network + untracked writes); needs an `AQ_RADAR_RESEARCH_DIR` override to be hermetic.
- Not activated: needs owner rebuild/restart for the coordinator to pick up the reader change.

## Hint Feedback (facts only)
- `ci_exempt` reason on `test-radar-ingest.py` correctly predicted the mutation of tracked state.
- The documented registry-update path (`scripts/ai/aq-prompt-eval` header) described in-place YAML rewrite; updated.
