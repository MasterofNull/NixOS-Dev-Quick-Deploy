# Knowledge sync reports degraded instead of failing on a few upstream errors

Date: 2026-11-18
Task ID: HF-20261118-knowledge-sync-degraded

## Objective
- Stop `ai-sync-knowledge-sources.service` from ending `failed` when a minority of the ~513 sources fail, so it no longer holds QA phase-0 check 0.1.2 ("no AI units in failed state") open and blocks #781 auto-retirement.
- Delivered: DEGRADED/FAILED exit policy with a machine-readable status file, an explicit reason per failed source, the github_repo default-branch fix, and removal of `Restart=on-failure` from the timer-driven oneshot.
- Journal excerpt (owner, 2026-11-16 01:02): the run ended `synced=505 skipped=27 fetch_failed=8`, exited 1, `Restart=on-failure` retried every 10 min until `start-limit-hit`, leaving the unit failed. Recurring since 2026-11-02 (backlog LIVE-SYNC-KNOWLEDGE-SOURCES-FAILED).
- Root causes: (1) exit 1 whenever any import failed, regardless of how many sources succeeded; (2) the start limit turned the retry into a permanent failed unit; (3) `gh_raw` fetched `.../main/README.md`, but `mitre-attack/attack-stix-data` and `google/osv.dev` default to `master`, so both 404 (`git ls-remote` shows `refs/heads/master` only for attack-stix-data); fixed by fetching `/HEAD/`.

## Workflow/Session IDs
- Workflow ID: n/a (bounded slice from orchestrator Simurg@claude/opus-5.5#da0ef470)
- Session ID: Simurg@claude/sonnet implementer; branch `fix/knowledge-sync-degraded`

## Delegation Decision
- Delegated bounded implementation to Sonnet per Rule 17; independent review is required from a different lane (implementer does not review its own work).

## Commands Executed
```bash
python3 scripts/testing/test-sync-knowledge-sources-retry.py
python3 scripts/testing/test-sync-knowledge-sources-dry-run.py
python3 scripts/testing/test-oneshot-no-restart.py
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```
No real sync was run against live AIDB.

## Validation Evidence
- Policy: exit 0 when synced > 0, failed-source share <= `KNOWLEDGE_SYNC_DEGRADED_MAX_PCT` (default 25) and no AIDB connectivity error; exit 1 otherwise.
- Status file: `KNOWLEDGE_SYNC_STATUS_FILE`, set by the Nix unit to `${dataDir}/hybrid/telemetry/knowledge-sync-status.json` (default `$XDG_CACHE_HOME/nixos-ai-stack/knowledge-sources/knowledge-sync-status.json`). Fields: status (ok|degraded|failed), counts, failed_pct, failed_sources[{id,type,reason}].
- Tests (offline, stubbed fetch/import): all OK exits 0; 8 of 513 failed exits 0 with 8 listed; above threshold exits 1; zero synced exits 1; AIDB connectivity error exits 1; a silent github_repo source (empty response) now names its reason; dry-run writes no status; raw URL uses `/HEAD/`.
- Dry-run bug SYNC-KNOWLEDGE-SOURCES-DRY-RUN-IMPORTS confirmed fixed on main by #701 (`.lower() in ("1","true","yes")`); `test-sync-knowledge-sources-dry-run.py` passes (0 POSTs). Backlog marked RESOLVED.
- Nix: `Restart=no` now inherited from `oneshotServiceConfig`; `StartLimit*` and `RestartSec` removed; `test-oneshot-no-restart.py` no longer exempts this unit.
- VERIFY.md success metric: the unit is never failed due to a minority of upstream failures; degraded runs are visible (`status: degraded`, `failed_sources` listed, one `WARN: source failed:` line each); phase-0 0.1.2 stays green.

## Rollback Plan
- `git revert` the commit. Trigger: a real outage that exits 0 (check `status` in the status file is `failed` when synced == 0 or the failed share is above threshold).

## Residual Risk
- Activation: needs rebuild to apply the Nix change; the status file is not yet consumed by health/dashboard (follow-up: surface "degraded: N sources"). Until then it is observable via the file and the `DEGRADED:` stdout line.
- A real failure now waits for the next weekly timer run (Persistent=true) instead of retrying in 10 minutes.
- Per-document import HTTP errors count as a failed source; a persistent AIDB-side 4xx on one source stays degraded, not failed.

## Hint Feedback
- No hints used.
