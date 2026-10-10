# Harness-First Task Evidence

Date: 2026-10-10
Task ID: HF-20261010-080

## Objective
- Meta-optimization on real data (2026-10-10)

- Its tables (`ai-stack/postgres/migrations/008_meta_optimization.sql`) were raw SQL no runner applied;
  the live path is alembic `aidb@head` in `ai-aidb` preStart.
- It read a `routing_log` table that exists nowhere (no alembic version, no schema.py, no SQL file).
- `interaction_history` queries used columns that don't exist (`timestamp`, `outcome_success`,
  `completion_time_ms`, `token_count`; real: `created_at`, `outcome`, `latency_ms`, `tokens_in/out` —
  `ai-stack/mcp-servers/aidb/schema.py` INTERACTION_HISTORY).
- `meta_optimizer.py` ignored the `--days/--output-dir` flags the unit passes (hardcoded 7 days).
- The Nix module had never been evaluated enabled: `aiStack.postgres`, `aiStack.repoPath` don't exist
  (`mySystem.mcpServers.postgres`, `mySystem.mcpServers.repoPath` do) — enabling it would have broken
  the rebuild.

- `ai-stack/migrations/versions/20261010_01_meta_optimization.py`: the three tables + indexes, the five
  SQL functions the code calls, and `meta_optimization_impact_summary`; idempotent; downgrade. On the
  `aidb` chain (`down_revision 20260125_01`); `20260718_01_b2_shadow` is a separate root, so no new head.
- `ai-stack/meta-optimization/routing_source.py`: stdlib streaming reader over the canonical
  `agent-run-events.jsonl` (`model_call`, fixtures excluded, `running` heartbeats excluded from success
  rate) + switchboard `routing-decisions.jsonl`. Replaces every `routing_log` use.
- Column fixes above; `to_regclass` guards log "no data source" instead of raising; UTC-aware datetimes
  for `timestamptz`. `agent_patterns` (007, federated learning, never migrated) → lesson analysis skips
  cleanly rather than this slice adopting another feature's table.
- `meta_optimizer.py`: `parse_args` (`--days`, `--output-dir`), `dump_proposals` writes
  `proposals-<UTC>.json`.
- Nix: `AGENT_RUN_EVENTS_PATH` from `mySystem.mcpServers.dataDir`; option paths fixed; enabled in
  `profiles/ai-dev.nix` (`autoApplyProposals` stays false — proposals only).

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer (migration + reader + query fixes); orchestrator review found and fixed 3 non-existent Nix option paths by evaluating the module enabled.

## Commands Executed
```bash
python3 scripts/testing/test-meta-optimization-routing-source.py
nix eval --impure --json --expr '<hyperd-ai-dev extendModules metaOptimization.enable=true; systemd env + timer>'
AGENT_RUN_EVENTS_PATH=/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl python3 -c 'import routing_source; ...'
```

## Validation Evidence
- `test-meta-optimization-routing-source.py` PASS (exact aggregates incl. fixture/bad/out-of-window rows,
  missing file, env override, switchboard reader, migration objects + downgrade, CLI args, proposal dump).
- Migration run twice + downgrade against a throwaway PostgreSQL 17 cluster (implementer run).
- `nix eval` with the module enabled: analysis/validator env resolve (`POSTGRES_USER=aidb`,
  `AGENT_RUN_EVENTS_PATH=/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl`), timer 24h.
  Secret `postgres_password` is `root:ai-stack 0440`; service user is in `ai-stack`.
- Real-log smoke (7d): local-llama succeeded 478 / failed 4 / running 3123 heartbeats; switchboard 210
  decisions, 193 local.

## Rollback Plan
- Revert the PR commit.

## Residual Risk
- Activation needs `nrs` (applies the migration via ai-aidb preStart, installs the units). First run is
  OnBootSec 1h / every 24h; it calls the local model for analysis.
- `agent_id` is null in real model_call events, so per-agent breakdown reads "unknown" — producer gap.
- Nothing writes `metadata.hint_template` into `interaction_history`; hint analysis stays empty until a
  producer exists.

## Hint Feedback
- None.
