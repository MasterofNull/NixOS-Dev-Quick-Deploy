Decision: derive trend metrics from agent-run-events.jsonl (live, schema-validated, already streamed by aq-report), not routing_metrics.db; keep routing_decisions as an optional secondary source.
Metrics: local_routing_pct (lane==local share of runs), run_success_rate, p50/p95 duration_ms per lane, useful_token_ratio (reuse aq-report useful_token_metrics logic).
Design: new TrendDatabase.collect_run_event_metrics(since_hours) streaming the JSONL line-by-line with a window filter (same pattern as aq-report 0c0ff4d7); per-hour buckets; no switchboard/llm_config edits (frozen L2B).
Acceptance: fixture with in/out-of-window + malformed/empty-timestamp rows; unit test for each metric; live: service run completes with metrics_collected>0 under its cgroup limit; fail-closed kept when zero live rows.
Risks: 7.5k events have empty timestamps (skip + count); lane field naming drift across producers.
Out of scope: resurrecting LLMRouter recording; dashboard work.
VERDICT: PLAN_READY_WITH_FOLLOWUPS — follow-up: decide whether routing_metrics.db is retired.
