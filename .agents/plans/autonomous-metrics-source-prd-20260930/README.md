# Collaborative Round — autonomous-metrics-source-prd-20260930

Opened: 2026-09-30T21:52:12Z
Target artifact (if a review round): (none — fresh drafting round)

## Task
ROLE: architect perspective for a PRD + plan (read-only; do not edit files).
PROBLEM: ai-autonomous-improvement.service now fails closed with RuntimeError no-metrics-observed (ai-stack/autonomous-improvement/autonomous_loop.py ~306). TrendDatabase (ai-stack/autonomous-improvement/trend_database.py:105-275) reads routing_decisions from /var/lib/ai-stack/routing_metrics.db (0 rows, untouched since 2026-04-25) and experiments.sqlite (last 2026-03-13); baseline collector returns []. The producer LLMRouter._record_routing (ai-stack/mcp-servers/hybrid-coordinator/knowledge/llm_router.py:1108) only runs via the coordinator's own route(); live traffic goes through the switchboard (ai-stack/switchboard/switchboard.py), which never records there. Live telemetry that does exist: /var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl (~92MB, schema scripts/ai/lib/agent_run_events.py: run_id, event_type, status, lane/tier, duration_ms, tokens, timestamp Z).
ASK: propose the minimal MVP to give the autonomous-improvement loop a live, trustworthy metric source. Cover: which source(s) are canonical; metric names/definitions (local_routing_pct, success rate, latency, token efficiency); bounded memory (the PRSI unit is capped at 256M — stream, do not load whole files); keep the fail-closed on zero live rows; acceptance tests; rollout + rollback; what NOT to build. Note: switchboard.py and llm_config.py are frozen L2B live sources (sha-pinned) — prefer designs that do not edit them.
OUTPUT: <= 40 lines: Decision, Metrics, Design, Acceptance tests, Risks, Out of scope. End with `VERDICT: PLAN_READY` or `VERDICT: PLAN_READY_WITH_FOLLOWUPS` or `VERDICT: NEEDS_DECISION` plus the open question.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/collaboration/antigravity-inbox/autonomous-metrics-source-prd-20260930.md` and writes `antigravity.md`. No API keys.
