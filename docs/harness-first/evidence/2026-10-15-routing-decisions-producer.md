# DEC-S0: routing_decisions producer (2026-10-15)

## Objective
`routing_metrics.db` tables `routing_decisions` and `advisor_consultations` had 0 rows and `escalations` 4 although routing runs. Find the root cause, fix the producer (Rule 19), make write failures observable. Part of `.agents/plans/aq-decide/DESIGN.md` (DEC-S0). No task text is stored (design section 3/4.2: text lives only in the future aq-decide log); only classes, model names, lane, source, bounded alternatives list.

Root cause (three compounding defects):
1. **Dead producer path.** The live router, `ModelCoordinator.classify_and_route` (`ai-stack/mcp-servers/hybrid-coordinator/extensions/model_coordinator.py`), only appended to an in-memory `_routing_history`. Every DB insert (`_record_routing`, `_record_escalation`, `_record_advisor_consultation` in `knowledge/llm_router.py`) is reachable only through `LLMRouter.execute_with_routing`, which is called solely by the HTTP handler `POST /control/llm/execute` (`knowledge/llm_router_handlers.py`), never used by the dispatch path. `LLMRouter.route_task` (called from classify_and_route) is a pure function with no recorder.
2. **Unwritable, cwd-relative DB path.** `LLMRouter.__init__` used `"routing_metrics.db"` relative to cwd. The service unit has `WorkingDirectory=/var/lib/ai-stack` (`systemctl cat ai-hybrid-coordinator`), `User=ai-hybrid`; that directory is `root:ai-stack 0750` (not group-writable) and the existing `/var/lib/ai-stack/routing_metrics.db` is `hyperd:users 0644` (Apr 25). So even a reachable insert gets "attempt to write a readonly database" (POSIX DAC, Rule 14; AppArmor `/var/lib/ai-stack/** rwk` does not bypass it). The 4 escalation rows came from manual/test runs by hyperd. `AQ_ROUTING_METRICS_DB_PATH` (declared in env-contract for the reader) was never read by the router.
3. **Silent failure.** `_init_metrics_db` / inserts had no handling or counters; nothing surfaced.
Side evidence: repo-root `routing_metrics.db` holds 45 `advisor_consultations` rows from tests running with cwd=repo, i.e. the code can write when the path is writable.

Fix: persist from the live path (`record_route_decision`), resolve DB path from `AQ_ROUTING_METRICS_DB_PATH` > `DATA_DIR` > cwd, `_write()` that is fire-and-forget (review follow-up): one daemon writer thread, bounded queue (1024, drop-with-counter, never blocks the caller), one reused connection, WAL + `synchronous=NORMAL`, 1 s busy timeout, `flush()`/`close()` wired into the coordinator's `on_cleanup` via `shutdown_router()`; failures log `routing_metrics write failed ...` and count (`write_stats` queued/written/dropped/failed/init_failed, `last_write_error`, exposed in `get_metrics()["write_health"]`), init failure no longer raises out of `get_router()`. Additive migration via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` (`lane`, `source`, `alternatives` JSON capped 8x64 chars, `handoff`). Free-text fields (`question`, `guidance_summary`, escalation `reason`) capped at 200 chars. Nix: hybrid unit gets `AQ_ROUTING_METRICS_DB_PATH=${dataDir}/hybrid/routing_metrics.db` (ai-hybrid-owned dir); the autonomous-improvement reader points at the same file; env-contract updated.

## Workflow/Session IDs
Branch `fix/routing-decisions-producer`, worktree `.agents/delegation/worktrees/dec-s0`, base origin/main. Plan: `.agents/plans/aq-decide/` (tracker item DEC-S0). Delegated slice from the orchestrator session (Claude Sonnet 5.5 implementer).

## Delegation Decision
Bounded single-slice implementation by the Sonnet implementer lane (Rule 17) under the frozen design; staged, not committed. Independent review is the orchestrator's to route (Rule 18).

## Commands Executed
- `rg -n "routing_decisions|advisor_consultations"` over code; `sed` of `llm_router.py`, `model_coordinator.py`
- Read-only sqlite row counts of `/var/lib/ai-stack/routing_metrics.db` (0/0/4/0) and repo-root db (advisor 45)
- `systemctl cat ai-hybrid-coordinator` (User, WorkingDirectory); `ls -la /var/lib/ai-stack`
- `python3 -m pytest tests/test_routing_decisions_producer.py tests/test_advisor_fallback_chains.py tests/test_ai_coordinator_model_awareness.py -q`
- `python3 scripts/ai/aq-pm-tracker .agents/plans/aq-decide --check`; `bash scripts/governance/tier0.d/check-pm-tracker.sh --pre-commit`

## Validation Evidence
- New tests (`ai-stack/mcp-servers/hybrid-coordinator/tests/test_routing_decisions_producer.py`): 6 passed; with the `classify_and_route` hook neutralised the end-to-end test fails (`AssertionError: classify_and_route did not persist a routing decision`), 5 others pass. With hook restored plus neighbour suites: 51 passed.
- Tracker: `PASS: aq-decide/tracker.json valid + projects`; check-pm-tracker: `PASS: 23 plan tracker(s) valid + projecting`.
- Not validated live: service restart and real rows (needs owner action below).

- Review follow-ups: 9 tests pass (added WAL + mode=ro reader check, full-queue drop test, 0444-file failure test, benchmark); coordinator-env test now asserts `_LLM_ROUTER_AVAILABLE` instead of skipping; hook removed -> 2 fail (e2e + benchmark). With neighbours: 54 passed.
- Micro-benchmark (in-process, n=1000, `classify_and_route`, ms): recorder off p50 0.144 / p99 0.271 / mean 0.146; on p50 0.212 / p99 0.601 / mean 0.247; 1050 queued, 1050 written, 0 dropped, 0 failed. Overhead about 0.07 ms median.
- Snapshot design (replaces the earlier 0664 chmod, per confirmatory review): the live WAL db stays owner-only (db 0640, `-wal`/`-shm` default modes, ai-hybrid). The writer thread publishes a read-only snapshot via `VACUUM INTO routing_metrics.snapshot.db.tmp`, chmod 0644, atomic `os.replace` to `routing_metrics.snapshot.db`: on the first write, then at most every 60 s (`AQ_ROUTING_METRICS_SNAPSHOT_INTERVAL_S`) while rows were written, and on close. Consumers (autonomous-improvement) read the snapshot via `AQ_ROUTING_METRICS_DB_PATH`; the writer uses `AQ_ROUTING_METRICS_DB_PATH` = live and `AQ_ROUTING_METRICS_SNAPSHOT_PATH` = snapshot (env-contract + Nix). Counters in `write_health`: `snapshots`, `snapshot_failed`, `last_snapshot_ts`. Tests: snapshot readable `mode=ro` with no `-wal`/`-shm`; live db 0640 (not group-writable); 40 snapshots under a concurrent reader never produce an error or partial count.
- Startup warm-up: `_scheduler_startup` builds the router in an executor (init/migration off the request path).
- Shutdown lifecycle finding: `run_http_mode` ended with `await asyncio.Event().wait()` and never called `runner.cleanup()`, and no signal handler existed, so aiohttp `on_cleanup` (incl. the earlier-added writer shutdown and `scheduler.stop`) never ran on systemd SIGTERM. Fixed: SIGTERM/SIGINT set a stop event, then `await runner.cleanup()` runs `on_cleanup` while the loop is still alive, before `asyncio.run` returns. Not exercised against the real service (unverified live); hard kill loses at most the queued rows and up to 60 s of snapshot staleness (the live db commits are durable apart from WAL/NORMAL power-loss semantics).
- Data-integrity residual (follow-up, not now): the ai-stack group can only READ the snapshot (dir `/var/lib/ai-stack/hybrid` is 0750 ai-hybrid:ai-stack, file 0644); only ai-hybrid or root can replace it. Residual = a compromised ai-hybrid/root plus no per-row provenance. aq-decide training must later read via a coordinator API or verify per-row provenance (hash chain or HMAC) before using these rows as labels.
- Benchmark (latest run, n=1000, ms): off p50 0.148 / p99 0.270 / mean 0.146; on p50 0.256 / p99 0.579 / mean 0.274; 1050 queued = 1050 written, 0 dropped, 0 failed.
- Tests: 12 passed in test_routing_decisions_producer.py (hook removed: 2 fail, 10 pass); with neighbours 57 passed.

- Bounded shutdown (round-3 review): `_scheduler_cleanup` -> `bounded_shutdown`: metrics writer flushed and snapshotted FIRST (in an executor), then `scheduler.stop()` under `wait_for(20s)`; `runner.cleanup()` under `wait_for(30s)`; a second SIGTERM/SIGINT calls `os._exit(0)`. Hybrid unit sets `TimeoutStopSec = 45`. Owner restart timing check: `time sudo systemctl restart ai-hybrid-coordinator` must finish well under 45 s, and `journalctl -u ai-hybrid-coordinator -n 50` should show "Shutdown signal received; running aiohttp cleanup" and "routing metrics writer flushed and snapshot published" (and no "exceeded" errors).

## Rollback Plan
Revert the producer commit (also reverts the SIGTERM handling). Added columns are additive and ignored by older code; the old db file is untouched. Unsetting `AQ_ROUTING_METRICS_DB_PATH` falls back to `DATA_DIR/routing_metrics.db`.

## Residual Risk
- Activation (Rule 15) needs an owner rebuild: Nix env change for `ai-hybrid-coordinator` and `autonomous-improvement`. Owner command: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` (or `nrs`), then `sudo systemctl restart ai-hybrid-coordinator`. Verify: issue any task through the coordinator, then `python3 -c "import sqlite3;print(sqlite3.connect('file:/var/lib/ai-stack/hybrid/routing_metrics.db?mode=ro',uri=True).execute('select count(*),max(timestamp) from routing_decisions').fetchone())"` shows count > 0; `GET /control/llm/metrics` shows `write_health.failed == 0`.
- The old `/var/lib/ai-stack/routing_metrics.db` (4 escalations) is not migrated; history there stays readable only.
- Success/outcome is NULL at decision time (outcome backfill is DEC-S3's labeler). Observable via metrics endpoint only; no dashboard panel/alert yet (deferred, DEC-S3). Intervention: unset env / revert.
- Hot-path cost: one sqlite insert per `classify_and_route` (not benchmarked).
- Rule 11 backlog entry not written here (main-checkout append-only file); orchestrator to log it.

## Hint Feedback
No aq-hints consulted in this slice (direct code search sufficed); hint gap: no hint pointed at the router-vs-executor recorder split.
