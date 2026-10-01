# A2A task for antigravity — round 'autonomous-metrics-source-prd-20260930'

Dropped: 2026-09-30T21:52:55Z

Respond by writing `.agents/plans/autonomous-metrics-source-prd-20260930/antigravity.md`.

## SCOPE & STOP (HARD — read before writing)
- Edit ONLY the files this task names as surfaces. A related-looking file is still out of scope.
- NEVER implement a data/config change as a filesystem shortcut: no symlink, bind mount, mount,
  chmod/chown/rm on tracked or runtime paths. 'Single source of truth' = a resolver in code,
  never one directory replacing/redirecting another.
- NO DELETE — archive to a timestamped path; never rm/rmdir.
- If this task references an authorization/round: confirm it still reads AUTHORIZED and (where a
  package root is named) that `aq-package-freeze verify` exits 0 BEFORE writing. If suspended,
  STOP — do not recreate or continue suspended files.
- Undeclared dependency discovered -> STOP and report; do not expand scope to 'make it work'.
- Budgets/acceptance criteria are hard facts: a measured violation FAILS; a sentence calling it
  'acceptable' does not change the number. Report the real value.
- Write ONLY your own named output file. Do NOT edit shared files. Do NOT commit.
- When unsure whether something is in scope: it is not. Report, do not act.

COLLABORATIVE ROUND 'autonomous-metrics-source-prd-20260930'.
TASK:
ROLE: architect perspective for a PRD + plan (read-only; do not edit files).
PROBLEM: ai-autonomous-improvement.service now fails closed with RuntimeError no-metrics-observed (ai-stack/autonomous-improvement/autonomous_loop.py ~306). TrendDatabase (ai-stack/autonomous-improvement/trend_database.py:105-275) reads routing_decisions from /var/lib/ai-stack/routing_metrics.db (0 rows, untouched since 2026-04-25) and experiments.sqlite (last 2026-03-13); baseline collector returns []. The producer LLMRouter._record_routing (ai-stack/mcp-servers/hybrid-coordinator/knowledge/llm_router.py:1108) only runs via the coordinator's own route(); live traffic goes through the switchboard (ai-stack/switchboard/switchboard.py), which never records there. Live telemetry that does exist: /var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl (~92MB, schema scripts/ai/lib/agent_run_events.py: run_id, event_type, status, lane/tier, duration_ms, tokens, timestamp Z).
ASK: propose the minimal MVP to give the autonomous-improvement loop a live, trustworthy metric source. Cover: which source(s) are canonical; metric names/definitions (local_routing_pct, success rate, latency, token efficiency); bounded memory (the PRSI unit is capped at 256M — stream, do not load whole files); keep the fail-closed on zero live rows; acceptance tests; rollout + rollback; what NOT to build. Note: switchboard.py and llm_config.py are frozen L2B live sources (sha-pinned) — prefer designs that do not edit them.
OUTPUT: <= 40 lines: Decision, Metrics, Design, Acceptance tests, Risks, Out of scope. End with `VERDICT: PLAN_READY` or `VERDICT: PLAN_READY_WITH_FOLLOWUPS` or `VERDICT: NEEDS_DECISION` plus the open question.

Write your contribution to YOUR OWN file ONLY: .agents/plans/autonomous-metrics-source-prd-20260930/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
