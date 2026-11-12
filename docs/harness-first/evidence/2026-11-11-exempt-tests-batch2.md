# 2026-11-11 exempt-tests-batch2

## Objective
Continue clearing exempt tests (P2.1 sweep, "missing file" group). Scope was narrowed mid-run by the coordinator: the 15 hybrid-coordinator tests that read the removed `http_server.py` and 7 self-contained known-failing tests belong to a Codex worktree (Wave 2026-11-10-E Slice 10) and are NOT part of this batch; my edits to them were reverted. No assertion was weakened; no test was deleted or archived.

## Workflow/Session IDs
Branch fix/exempt-tests-batch2 (worktree .agents/delegation/worktrees/exempt-batch2), date 2026-11-11. Staged, not committed, not pushed.

## Delegation Decision
Orchestrator: claude-opus. Implementer: Claude Sonnet 5.5 (Rule 17, bounded triage slice).

## Commands Executed
CI-like environment as batch 1: venv from `config/ci-test-requirements.txt`, `CI=true`, HOME/XDG/TMPDIR redirected, a HOME `.gitconfig` equal to the workflow's (`user.name ci`, `init.defaultBranch main`), `PYTHONPATH` unset, host-only `LD_LIBRARY_PATH` for libstdc++. Each test run directly, then `scripts/testing/run-test-group.py tests-misc-a-c` (86/86) and `tests-delegate` (13/13). `scripts/governance/tier0.d/check-ci-test-coverage.sh` PASS (777 tests: 658 declared, 119 exempt). No golden-fixture-pinned file was touched (`live_source_manifest` has no entry for them), so no hash refresh.

## Validation Evidence

| test | diagnosis | action | verified how |
|---|---|---|---|
| test-adk-declarative-wiring.sh, test-adk-reviewer-gate-checklist.sh | `lib/adk` moved to `lib/l4-coord/adk` (2e65cae38). Moving it also broke the producers: `wiring-validator.sh` and `implementation-discovery.sh` computed `REPO_ROOT` with `../..` (now `lib/`), so the validator scanned `lib/nix` and both wrote `lib/.agent/adk/...` into the checkout (sourcing the discovery script `mkdir`s its data dirs). | Producer fix: `REPO_ROOT` uses `../../..`; added `ADK_DATA_DIR` override; tests use the new path and a temp `ADK_DATA_DIR`. Un-exempted, tests-misc-a-c. | direct, group 86/86, `lib/.agent` and `.agent/adk` absent after runs |
| test-delegate-wrapper-shell-safety.py | Not a missing file: it fails only under `run-test-group.py`, which sets `AQ_DELEGATION_DIR`; the wrappers honour it and write the registry elsewhere while the test reads `<fixture>/.agents/delegation/registry.jsonl` (the old exemption text, "missing file ... registry.jsonl"). Test bug: fixture env did not pin the state dir. | `_fixture_env(root)` pins `AQ_DELEGATION_DIR` to the fixture in all four env builders. Un-exempted, tests-delegate. | direct x3, group 13/13 |
| test-optional-performance-completion.py | Roadmap moved to `.agents/planning/plans/`; the semantic-cache query escaping now escapes the whole `NAME=value` arg (`lib.escapeShellArg "AI_SEMANTIC_CACHE_WARM_QUERIES=..."`). Both fixed. Remaining 3 assertions need the dashboard `deployment-ops` card and its lazy-load registration, removed by the dashboard consolidation 1acd19966 (18K to 1K lines). That is dropped behaviour, not a moved one. | Path and escape assertions updated; stays exempt, reason rewritten. | run output |
| test-advanced-reasoning-patterns.py, test-pipeline-orchestration.py | Test `ai-stack/agentic-patterns/*`, archived by 49720f3be ("zero Python imports") to `archive/ai-stack-deprecated-2026-05/agentic-patterns/`. Behaviour dropped on purpose. | none; stays exempt, reason rewritten with the decision | file search, git log |
| test-codex-subagent-configuration.py | Reads `.codex/` which is gitignored (.gitignore:322); present only for the operator. | reclassified sandbox-env, reason rewritten | git check-ignore |
| test-tier0-staged-isolation.sh | Runs the full gate three times (80-90 s each, over the 120 s timeout) and copies the gitignored PULSE.log. | reclassified slow, reason rewritten | code read |
| 18 tests reading http_server.py | Wave E overlap: Codex has a near-complete version. My per-test edits (18 tests moved to the files that own each asserted symbol, all passing) were reverted; the full diff is kept at the scratchpad path in the report for the coordinator. | none in this branch | n/a |

## Product bugs found
- `lib/l4-coord/adk/wiring-validator.sh`, `implementation-discovery.sh`: `REPO_ROOT` off by one level since 2e65cae38; fixed (see above).
- `scripts/automation/adk/schedule-discovery.sh`: `REPO_ROOT` used `../..` from `scripts/automation/adk` (resolves to `scripts/`) and `LIB_ADK_DIR` pointed at the removed `lib/adk`, so scheduled ADK discovery could never find its script. Fixed to `../../..` and `lib/l4-coord/adk`.
- Backlog-ready: [OPEN] ADK-INTEGRATION-VACUOUS scripts/testing/test-adk-integration.py (tests-misc-a-c) ends with `pytest.main([...])` without `SystemExit`, so it always exits 0; under pytest 19 of 25 fail (paths `lib/adk`, `scripts/adk`, `docs/adk` all moved). Needs a path migration across ~20 sites; Severity medium.
- Observation: `workflow/workflow_planning.py:443` passes `memory_recall_priority` into `_select_reasoning_pattern`'s `continuation_query` parameter (3181cadc6); naming mismatch, not verified as a bug.

## Exemptions
Before 122, after 119 (3 removed: the two ADK tests and delegate-wrapper-shell-safety). Five reasons or classes rewritten.

## Decisions needed
- Dashboard `deployment-ops` card and lazy loading (removed in 1acd19966): restore, or drop the three assertions in test-optional-performance-completion.py.
- `agentic-patterns` tests: archive with their module (Rule 12) or restore the module (49720f3be).

## Rollback Plan
Revert the commit. The ADK producer fixes stand alone; reverting returns the validator to scanning the wrong tree and writing `lib/.agent`.

## Residual Risk
Verified in a venv on this host, not a GitHub runner. One tests-misc-a-c run showed a single transient failure of test-c6c-owner-submission-service-coverage.py (untouched, passed on two reruns), and the tests-delegate/other groups touched by Wave E were not run here. Groups tests-agent, -d-h, -i-m, -n-r, -s-z were not run because the tests promoted into them were reverted.

## Hint Feedback
No hints were consulted. Test failures and git history defined the work.
