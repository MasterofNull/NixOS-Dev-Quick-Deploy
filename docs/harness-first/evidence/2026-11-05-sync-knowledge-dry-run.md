## Objective
Make `scripts/data/sync-knowledge-sources --dry-run` a real dry run. Before this fix the flag was ignored: bash passed `DRY_RUN=true` (lowercase) to the embedded Python, which compared it against `"True"`, so every "dry run" POSTed real imports to AIDB.

Incident: on 2026-11-05 an orchestrator diagnostic run with `--dry-run` imported the normal source set into AIDB.

## Workflow/Session IDs
Branch fix/sync-knowledge-dry-run, worktree `.agents/delegation/worktrees/sync-dry-run`. Slice is bounded to the sync script, its new regression test, the ci-checks manifest entry, and this evidence file.

## Delegation Decision
Implementer: Claude Haiku 5.5 sub-agent, dispatched by the orchestrator (Rule 17, mechanical bounded fix with a checkable result). Changes are staged and not committed.

## Commands Executed
- `python3 scripts/testing/test-sync-knowledge-sources-dry-run.py` on the fixed script: PASS.
- Same test against the original script (`git show HEAD:scripts/data/sync-knowledge-sources`): FAIL (rc=1). The dry run ignored `--dry-run`, read the real `ai-stack/data/knowledge-sources.yaml` because the path was hardcoded, and POSTed to the stub. This run was against a stub only, never the live AIDB.
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`: PASS (767 tests: 623 declared, 144 exempt).
- `python3 scripts/testing/run-test-group.py tests-misc-s-z`: first run 81/82 (`test-security-audit-gate.sh` hit the 120 s per-test timeout under 4-way parallel load; it passes alone in 67 s and is unrelated to this change). Second run 82/82.

## Validation Evidence
Root cause: `scripts/data/sync-knowledge-sources` line 79 compared the bash value `"true"`/`"false"` against `"True"`, so `dry_run` was always False.

Fix:
- Line 79: `dry_run = dry_run_str.strip().lower() in ("1", "true", "yes")`. The bash value is passed unchanged.
- Line 17: `SOURCES_FILE` honours a `KNOWLEDGE_SOURCES_FILE` override, defaulting to the existing path.
- Import-path audit: the `if dry_run: continue` guard (before any fetch) precedes every GET and every `aidb_import` POST in the loop. The `--list` path exits before any network use. No import path sits outside the guard, so no further guard was needed.

Regression test `scripts/testing/test-sync-knowledge-sources-dry-run.py` (stdlib only): a stub HTTP server on 127.0.0.1 port 0 records every request. A temp YAML declares one enabled url source served by the stub. Assertions: `--dry-run` exits 0 with zero POSTs and prints the DRY RUN marker. The run without `--dry-run` sends at least one POST, which shows the stub can observe imports.

Manifest: the test is listed in `tests-misc-s-z` `paths` and `tests`, sorted, between `test-switchboard-useful-ratio.py` and `test-synthesis-guard.py`.

## Rollback Plan
Revert the two-line change in `scripts/data/sync-knowledge-sources`, the new test file, and the two manifest lines in `config/ci-checks.json`. No data or schema migration is involved. Note that reverting restores the bug, so any dry-run use before the revert must be treated as a real import.

## Residual Risk
- Any AIDB imports made by the 2026-11-05 incident run are not reverted by this change. Those rows need a separate cleanup decision by the owner; this slice does not touch live AIDB.
- The test covers the url source type only. The github_repo and local_dir branches also sit behind the same dry-run guard but have no regression coverage here.
- `test-security-audit-gate.sh` is near the 120 s per-test timeout under parallel load. It is not caused by this change but is a flake risk for `tests-misc-s-z`.

## Hint Feedback
No hints were consulted. The script's own dry-run guard and the existing `aidb_import` retry logic were the useful context.
