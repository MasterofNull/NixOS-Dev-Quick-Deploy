# System Improvement Plan and Working Document (March 2026)

Last updated: 2026-03-04
Primary tracking doc for multi-agent execution across Codex/Claude/Qwen/Continue workflows.

## Implemented Slice (2026-03-04)

- PRSI orchestrator control plane implemented:
  - `scripts/prsi-orchestrator.py` (sync/list/approve/reject/execute/cycle)
  - Queue state and action logs persisted under PRSI paths
- Optimizer executor integration:
  - `scripts/aq-optimizer` supports `--actions-json` and `--output-json`
- Command Center API integration:
  - `GET /api/prsi/actions`
  - `POST /api/prsi/sync`
  - `POST /api/prsi/approve`
  - `POST /api/prsi/execute`
- Dashboard integration:
  - PRSI queue card with counts + pending action list + sync/execute buttons
- Declarative runtime orchestration:
  - `ai-prsi-orchestrator.service` + hourly timer
- Telemetry persistence fix (declarative):
  - `ai.aiHarness.runtime.telemetryEnabled` option
  - AIDB telemetry config now wired to declarative option
- Dashboard API telemetry hardening:
  - Fixed DSN password injection logic for secret-file auth
  - Added legacy `telemetry_events` schema fallback insert path
  - Added richer telemetry insert failure logging (`err_type`, repr)
- Runtime metric verification recovery:
  - Re-ran `ai-pgvector-bootstrap.service` to sync DB role password with secret
  - Re-seeded routing traffic so `hybrid_llm_backend_selections_total` emits samples
- npm supply-chain hardening:
  - Added `scripts/npm-security-monitor.sh` with IOC-aware threat-intel checks
  - Added declarative `deployment.npmSecurity.*` options
  - Added `ai-npm-security-monitor.service` + periodic timer wiring
  - Added declarative npm threat response modes (`report|fail|quarantine`)
  - Added quarantine state + incident ledger artifacts for downstream gating
  - Exposed npm monitor/quarantine data in command-center `/api/security/audit`
- Prompt intent/spirit contract enforcement:
  - Added intent-contract schema validation in hybrid coordinator workflow runtime
  - `/workflow/run/start` now requires valid `intent_contract` fields
  - `/workflow/blueprints` now returns validation status/errors for blueprint quality gates
  - Added declarative validation check for intent-contract fields in `config/workflow-blueprints.json`

## Objective

Increase system quality and reliability while keeping the stack declarative-first:
- Raise quality outcomes (eval + hint adoption + tool success)
- Reduce report noise and stale gaps
- Improve observability and CI validity
- Strengthen tool-security enforcement with low repeat-audit cost

## Scope and Constraints

- Declarative-first implementation:
  - `nix/modules/core/options.nix`
  - `nix/modules/roles/ai-stack.nix`
  - `nix/modules/services/*.nix`
- Script/runtime fallback only when declarative is not practical.
- No hardcoded ports/URLs/secrets.
- Rollback must remain available through NixOS generation rollback.

## Operating Model (Multi-Agent)

- One task per branch/PR/commit.
- Every task must include:
  - changed files
  - validation commands
  - pass/fail evidence
  - rollback note
- Session handoff format:
  - `Task ID`
  - `Phase`
  - `Current status`
  - `Next command`
  - `Risks/blockers`

## Global Success Criteria (Program-Level)

- `aq-report` targets (7d window):
  - Semantic cache hit rate `>= 60%`
  - Hint adoption success `>= 70%`
  - Routing split present (non-zero local or remote)
  - Top query gaps contain no synthetic/test prompts
- Tooling:
  - At least 5 active tool rows in report tool-performance section for active windows
  - No failed required services after deploy
- Quality:
  - Strategy leaderboard mean score improves beyond baseline 66% for at least one non-baseline strategy

## Phase Plan

## Phase 0 — Baseline and Guardrails

Status: `in_progress`

Tasks:
1. Baseline snapshot
- Tools: `scripts/check-mcp-health.sh`, `scripts/aq-report --since=7d --format=text`
- Success criteria: health check passes; report captured in logs/artifacts.

2. Enforce synthetic-gap filtering
- Tools: `scripts/aq-report`, `scripts/curate-residual-gaps.sh`
- Success criteria: no `analysis only task`, `fetch/curl localhost`, or `test` rows in Top Query Gaps.

3. Post-deploy smoke standardization
- Tools: `scripts/seed-routing-traffic.sh`, `scripts/aq-report`
- Success criteria: routing split and cache metrics present after every deploy.

## Phase 1 — Observability and Metrics Integrity

Status: `pending`

Tasks:
1. Tool audit coverage expansion
- Tools: `ai-stack/mcp-servers/shared/tool_audit.py`, hybrid/aider handlers
- Success criteria: report shows >=5 active tools when traffic is generated.

2. Metric-name compatibility hardening
- Tools: `scripts/aq-report`, Prometheus queries
- Success criteria: routing/cache sections remain populated across restarts and metric variant names.

3. CI metric smoke
- Tools: `.github/workflows/test.yml`, `scripts/seed-routing-traffic.sh`, `scripts/aq-report`
- Success criteria: CI fails if sections 2/3/9 are unavailable after seeded traffic.

## Phase 2 — Hinting and Tooling Orchestration Quality

Status: `pending`

Tasks:
1. Hint injection precision tuning
- Tools: `ai-stack/mcp-servers/aider-wrapper/server.py`, declarative options for thresholds
- Success criteria: hint adoption `>= 70%` for a 7d window.

2. Tooling plan relevance scoring
- Tools: `/workflow/plan`, aider-wrapper tooling telemetry
- Success criteria: `tooling_plan_injected=true` tasks show improved success vs non-injected baseline.

3. Skip-gap tracking enforcement for probes/tests
- Tools: hybrid/aider request context handling
- Success criteria: probe traffic does not create query-gap entries.

## Phase 3 — Cache and Routing Optimization

Status: `pending`

Tasks:
1. Prewarm strategy improvement
- Tools: `scripts/seed-routing-traffic.sh`, timer config in Nix modules
- Success criteria: cache hit rate `>= 60%` sustained.

2. Declarative routing SLO policy
- Tools: `nix/modules/core/options.nix`, `scripts/validate-ai-slo-runtime.sh`
- Success criteria: explicit routing and latency thresholds validated in runtime checks.

3. Failure-aware routing fallback validation
- Tools: `scripts/check-mcp-health.sh`, `/query` synthetic probes
- Success criteria: degraded local path still yields successful remote fallback.

## Phase 4 — Eval Improvement Loop

Status: `pending`

Tasks:
1. Replace/repair failing strategy packs
- Tools: `scripts/aq-prompt-eval`, `scripts/run-eval.sh --strategy ...`
- Success criteria: no strategy remains at `0%` over 3+ runs.

2. Prompt registry optimization cycle
- Tools: `ai-stack/prompts/registry.yaml`, eval scripts
- Success criteria: at least one non-baseline strategy beats baseline mean score.

3. Automated weekly scorecard import
- Tools: `scripts/aq-report --aidb-import`, timers
- Success criteria: weekly report artifacts present and searchable.

## Phase 5 — Security Auditor Maturity

Status: `pending`

Tasks:
1. First-use auditor cache-key hardening
- Tools: `tool_security_auditor.py`
- Success criteria: cache key includes `tool + version/hash + policy_version`.

2. Re-audit-on-change only
- Tools: auditor cache policy + TTL
- Success criteria: repeated safe tool calls skip full audits unless fingerprint/policy changes.

3. Security regression tests
- Tools: `scripts/check-api-auth-hardening.sh`, targeted tool-policy tests
- Success criteria: unsafe tool metadata/params are blocked and logged with reason.

## Phase 6 — CI and Release Discipline

Status: `pending`

Tasks:
1. Align CI to real runtime expectations
- Tools: GitHub Actions jobs, smoke scripts
- Success criteria: no false-fail CI checks due to stale assumptions.

2. Declarative validation gate
- Tools: `scripts/validate-runtime-declarative.sh`
- Success criteria: required declarative artifacts/options validated on every PR.

3. Multi-client compatibility gate
- Tools: `scripts/smoke-cross-client-compat.sh`
- Success criteria: HTTP/RPC/SDK paths all pass for core workflow endpoints.

## Work Queue Template (Copy Per Task)

Use this block for each task execution:

```md
### Task: <short-id>
- Phase: <phase>
- Owner agent: <codex|claude|qwen|continue>
- Files: <path list>
- Commands:
  - `<command 1>`
  - `<command 2>`
- Success criteria:
  - `<criterion 1>`
  - `<criterion 2>`
- Evidence:
  - `<output summary>`
- Rollback:
  - `sudo nixos-rebuild switch --rollback`
- Status: <pending|in_progress|blocked|done>
```

## Immediate Next Tasks (Start Here)

1. Phase 1.1: expand tool-audit coverage so report tool table shows operational breadth.
2. Phase 2.1: tune hint thresholds to reach `>= 70%` adoption success.
3. Phase 3.1: improve cache prewarm with repeated-query replay and verify `>= 60%` hit rate.
4. Phase 4.1: remediate `gap_pack_v1` evaluation strategy from `0%`.
