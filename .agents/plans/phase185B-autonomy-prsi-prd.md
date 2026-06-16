---
doc_type: prd
id: phase185B-autonomy-prsi-prd
title: "Phase 185B — Autonomous Improvement Activation: PRSI Timer, Delegation Feedback Wiring, Self-Optimization Loop"
status: draft
owner: architect
phase: "Phase 185B"
priority: P1-high
evidence_required: ai-autonomous-improvement.timer active and fires on schedule; delegation feedback events consumed by PRSI orchestrator; at least 1 improvement cycle completes without human intervention
---

# Phase 185B — Autonomous Improvement Activation: PRSI Timer, Delegation Feedback Wiring, Self-Optimization Loop

---

## 1. Problem Statement

The AI harness has a fully implemented autonomous self-improvement system — 13 source files, 3387 lines of production code, a PostgreSQL schema with 8 tables and 4 views, a complete PRSI policy, and a working dry-run CLI. Despite this, the system has never run a single improvement cycle autonomously. The `ai-autonomous-improvement.timer` has never been activated. Every recurring failure requires a human to notice, diagnose, and intervene.

The gap is not capability. The gap is activation and integration.

Three specific problems compound each other:

**Problem 1 — Timer Not Activated.** `nix/modules/services/autonomous-improvement.nix` is fully declared and builds successfully. However, `nix/hosts/hyperd/facts.nix` contains no `autonomousImprovement` block, which means `mySystem.aiStack.autonomousImprovement.enable` evaluates to false (the `mkEnableOption` default). The systemd timer and service are never instantiated. A single `nixos-rebuild switch` with the correct `facts.nix` stanza would activate the system today.

**Problem 2 — Delegation Feedback Not Consumed.** `delegation-feedback.jsonl` accumulates records of every delegation outcome — failure classes, improvement actions, HTTP statuses, salvage data — but nothing reads this log and converts it into PRSI action queue entries. The `prsi-orchestrator.py` `cmd_sync` function (lines 384–446) calls `_fetch_structured_actions()` which calls `aq-report` to get `structured_actions`. Delegation feedback patterns are not in `structured_actions`. They exist in a separate JSONL file that `prsi-orchestrator.py` never opens. Repeated delegation failures such as `rate_limited`, `json_contract_failed`, `invented_repo_paths`, and `empty_content` recur because the feedback loop that would generate corrective routing or prompt actions does not exist.

**Problem 3 — No Closed Loop.** Even if the timer fires and generates hypotheses, the bridge from `autonomous_loop.py` (which discovers anomalies and generates hypotheses) to `prsi-orchestrator.py` (which manages the action queue and executes improvements) is not wired. Hypotheses are stored to PostgreSQL but never translated into PRSI queue entries. The two subsystems are effectively parallel processes that do not speak to each other.

The cost of inaction is measurable: 135 delegation feedback events have accumulated with null `event_type` (Phase 184A will fix the null). Even after the null is fixed, those events will still not be consumed. Every session that ends with a delegation failure adds another record that helps no one.

---

## 2. Architecture Overview

The intended PRSI loop and where each component currently sits:

```
TELEMETRY SOURCES
==================
  delegation-feedback.jsonl          routing_metrics.db        experiments.sqlite
  (DATA_DIR/telemetry/)              (hybrid-coordinator)      (AIDB layer)
         |                                   |                       |
         |  [MISSING WIRE — Phase 185B]       |                       |
         v                                   v                       v
  ┌──────────────────────────────────────────────────────────────────────┐
  │                  TrendDatabase (trend_database.py)                    │
  │           PostgreSQL: system_metrics_timeseries, metric_trends,       │
  │           anomaly_events, improvement_cycles, hypotheses              │
  └──────────────────────────────────────────────────────────────────────┘
         |
         v
  ┌──────────────────────────────┐
  │  TriggerEngine (trigger_engine.py)                                    │
  │  - degradation_threshold: -10.0%                                      │
  │  - volatility_threshold: 0.4                                          │
  │  - cooldown_minutes: 60                                               │
  │  - Calls local LLM (localhost:8080) for trigger decision              │
  │  OUTPUT: TriggerEvent {id, trigger_type, severity, metric_name, ...}  │
  └──────────────────────────────┘
         |
         v
  ┌──────────────────────────────┐
  │  ResearchPhase (research_phase.py)                                    │
  │  - LLM acts as "Research Director"                                    │
  │  - Generates OptimizationHypothesis list (3–5 per cycle)             │
  │  - hypothesis_type: PROMPT_OPTIMIZATION, CONFIG_TUNING, ARCH_CHANGE  │
  │  - Stores to PostgreSQL hypotheses table                              │
  └──────────────────────────────┘
         |
         v
  ┌──────────────────────────────┐
  │  ExperimentExecutor (experiment_executor.py)                          │
  │  - Converts hypotheses into ExperimentSpec                            │
  │  - blast_radius: low → auto-apply; medium/high → PRSI queue          │
  │  - Budget cap: AUTONOMOUS_MAX_EXPERIMENTS (default 3)                 │
  │  - Writes artifacts to PRSI_ARTIFACT_DIR                             │
  └──────────────────────────────┘
         |
         v
  ┌──────────────────────────────┐
  │  SandboxValidator (sandbox_validator.py)                              │
  │  - Gate 1: syntax (bash -n, python3 -m py_compile, nix-instantiate)  │
  │  - Gate 2: smoke (smoke-focused-parity.sh)                           │
  │  - Gate 3: aq-qa 0 → require >=39 passes                            │
  │  - Gate 4: check-aq-report-contract.sh                               │
  │  - recommendation: accept | revert | queue                           │
  └──────────────────────────────┘
         |
         |──── recommendation=accept (blast_radius=low) ──────────────┐
         |                                                              |
         v                                                              v
  ┌──────────────────────────────────────────────────────────────────────┐
  │  prsi-orchestrator.py  (PRSI Control Loop)                           │
  │  Action Queue: /var/lib/nixos-ai-stack/prsi/action-queue.json        │
  │  Policy: config/runtime-prsi-policy.json                             │
  │  - cmd_sync: fetches structured_actions from aq-report               │
  │    [+ NEW: ingest_delegation_feedback() — Phase 185B]                │
  │  - cmd_agent: dispatches OBSERVE→REFLECT task to aq-agent-loop       │
  │  - cmd_execute: runs approved actions via aq-optimizer                │
  │  - Budget gating: 120k remote tokens/day hard cap                    │
  │  - Risk tiers: low=auto-approve, medium/high=human gate              │
  └──────────────────────────────┘
         |
         v
  ┌──────────────────────────────┐
  │  Approved Actions                                                     │
  │  - type: routing → routing_rules config update                       │
  │  - type: prompt → prompt template update                             │
  │  - type: knowledge → RAG seeding / AIDB write                       │
  │  - type: maintenance → script/service config change                  │
  │  - type: workflow → workflow YAML update                             │
  └──────────────────────────────┘
         |
         v
  ┌──────────────────────────────┐
  │  nixos-rebuild switch                                                 │
  │  (for high blast_radius actions only — always requires human gate)   │
  └──────────────────────────────┘
         |
         v
  [cycle recorded to PostgreSQL improvement_cycles → feeds TrendDatabase next cycle]


ACTIVATION CONTROL (Phase 185B adds this stanza to facts.nix):
================================================================
  facts.nix → mySystem.aiStack.autonomousImprovement.enable = true
  → nixos-rebuild switch → systemd timer: ai-autonomous-improvement.timer
     OnBootSec = 10min
     OnUnitActiveSec = 60min
     Persistent = true
```

**Where `delegation_feedback.py` feeds in (the missing wire):**

```
  delegation-feedback.jsonl
  (written by: workflow/delegation_feedback.py:record_delegation_feedback())
       |
       v
  [NEW] ingest_delegation_feedback() in prsi-orchestrator.py
       |
       |  Groups events by (failure_class, profile) over a rolling window
       |  Threshold: >=3 occurrences of same failure class in 24h
       |
       v
  PRSI action queue entry:
    type:   "routing"    (for rate_limited, provider_http_error)
    type:   "prompt"     (for json_contract_failed, meta_reasoning_leak,
                          exact_output_too_verbose, low_signal_generic)
    type:   "knowledge"  (for invented_repo_paths — seed missing paths to AIDB)
    risk:   "low"        (routing/prompt updates qualify for auto-approve)
    safe:   true
    reason: "3 occurrences of json_contract_failed on profile=gemini in 24h.
             improvement_action: tighten prompt contract to require strict
             JSON-only output and validate before acceptance"
```

---

## 3. Current State Audit

| Component | File Path | Implementation | Activation |
|-----------|-----------|---------------|------------|
| TrendDatabase | `ai-stack/autonomous-improvement/trend_database.py` | Complete | coded-not-activated |
| TriggerEngine | `ai-stack/autonomous-improvement/trigger_engine.py` | Complete (389L) | coded-not-activated |
| AutonomousLoop | `ai-stack/autonomous-improvement/autonomous_loop.py` | Complete (446L) | coded-not-activated |
| ResearchPhase | `ai-stack/autonomous-improvement/research_phase.py` | Complete (511L) | coded-not-activated |
| ExperimentExecutor | `ai-stack/autonomous-improvement/experiment_executor.py` | Complete (292L) | coded-not-activated |
| SandboxValidator | `ai-stack/autonomous-improvement/sandbox_validator.py` | Complete (243L) | coded-not-activated |
| Nix service definition | `nix/modules/services/autonomous-improvement.nix` | Complete (214L) | coded-not-activated |
| Nix service import | `nix/modules/services/default.nix` | Verify import chain | unknown |
| Timer activation stanza | `nix/hosts/hyperd/facts.nix` | **Missing** (no `autonomousImprovement` block) | **not-activated** |
| PRSI orchestrator | `scripts/automation/prsi-orchestrator.py` | Complete (769L) — action queue, approve/execute/agent cmds | coded-not-activated |
| PRSI policy | `config/runtime-prsi-policy.json` | Complete (95L) | active (read on demand) |
| PRSI state | `/var/lib/nixos-ai-stack/prsi/runtime-state.json` | Written on first run | not-created-yet |
| PRSI action queue | `/var/lib/nixos-ai-stack/prsi/action-queue.json` | Written on first sync | not-created-yet |
| delegation_feedback log | `DATA_DIR/telemetry/delegation-feedback.jsonl` | Written continuously | **active — 135+ events** |
| delegation_feedback classifier | `ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback.py` | Complete (507L) | active — called on every delegation |
| delegation_feedback → PRSI intake | `scripts/automation/prsi-orchestrator.py` | **Missing** — no `ingest_delegation_feedback()` function | **not-implemented** |
| autonomous_loop → PRSI bridge | `ai-stack/autonomous-improvement/autonomous_loop.py` | Hypotheses stored to PostgreSQL; no PRSI queue write | **stub** |
| aq-auto-remediate PRSI integration | `scripts/ai/aq-auto-remediate.py` | `# TODO: Integrate with PRSI for auto-patching if safe` (line ~367) | **stub** |
| PostgreSQL schema | `ai-stack/postgres/migrations/006_autonomous_improvement.sql` | Complete (8 tables, 4 views) | active (migration applied) |
| aq-autonomous-improve CLI | `scripts/ai/aq-autonomous-improve` | Complete | coded-not-activated (not in PATH until rebuild) |

---

## 4. Activation Requirements

### 4.1 Nix Configuration Change (Required)

Add the following stanza to `nix/hosts/hyperd/facts.nix` inside the `mySystem` block, alongside the existing `aiStack` block:

```nix
aiStack = {
  # ... existing aiStack config unchanged ...

  autonomousImprovement = {
    enable = true;
    interval = 60;     # minutes between cycles
    dryRun = false;    # false = experiments execute; true = hypotheses only
    maxExperimentsPerCycle = 3;
    autoApplyBlastRadiusMax = "low";  # medium/high always queue to PRSI
  };
};
```

Option types and defaults are declared in `nix/modules/services/autonomous-improvement.nix` lines 59–84. The `enable` option is an `mkEnableOption`; the remaining options have defaults that match the values above. Explicitly declaring all four prevents surprises if defaults change.

### 4.2 Prerequisite Services

The timer's `after` and `requires` directives (autonomous-improvement.nix lines 103–114) mandate:
- `postgresql.service` — active and accepting connections on port 5432
- `llama-cpp.service` — responding on port 8080 (`/health` returns 200)
- `network-online.target` — satisfied (always true on operational system)

Current operational status per ACTIVATION-STATUS.md:
- PostgreSQL: active
- llama.cpp: active
- Secrets: `/run/secrets/postgres_password` available via SOPS

### 4.3 Activation Command

```bash
sudo nixos-rebuild switch --flake .#hyperd-ai-dev
```

This instantiates `systemd.services.ai-autonomous-improvement` and `systemd.timers.ai-autonomous-improvement` and adds `aq-autonomous-improve` to PATH.

### 4.4 Verify import chain

Before rebuild, confirm `nix/modules/services/autonomous-improvement.nix` is imported. It was listed in `nix/modules/services/` directory tree alongside `ai-stack.nix`, `mcp-servers.nix`, etc. Verify it appears in `nix/modules/services/default.nix` imports list. If missing, add it before rebuild.

---

## 5. Delegation Feedback Wiring Design

### 5.1 Event Structure (from `workflow/delegation_feedback.py:record_delegation_feedback()`)

Each JSONL record in `delegation-feedback.jsonl` contains:

```json
{
  "timestamp": "2026-06-15T12:00:00Z",
  "task_excerpt": "...",
  "requested_profile": "gemini",
  "selected_profile": "gemini",
  "selected_runtime_id": "gemini-2.5-pro",
  "final_profile": "gemini",
  "final_runtime_id": "gemini-2.5-pro",
  "requesting_agent": "human",
  "requester_role": "orchestrator",
  "failure_stage": "response",
  "http_status": 200,
  "outcome": "failed",
  "failure_class": "json_contract_failed",
  "failure_classes": ["json_contract_failed"],
  "fallback_applied": false,
  "handoff_requested": false,
  "response_preview": "...",
  "salvage": { "text_excerpt": "...", "existing_paths": [], ... },
  "improvement_actions": ["tighten prompt contract to require strict JSON-only output ..."]
}
```

After Phase 184A fixes the null `event_type` (a field not present in the current schema — likely a separate `event_type` field that Phase 184A will add), failed events will be consistently classifiable.

### 5.2 New Function: `ingest_delegation_feedback()` in `prsi-orchestrator.py`

Add a new function `ingest_delegation_feedback(since_hours: int = 24) -> Dict[str, Any]` to `scripts/automation/prsi-orchestrator.py`. This function:

1. Reads `delegation_feedback_log_path()` from `workflow/delegation_feedback.py` (imported via the existing Python path resolution pattern, or by reading the env var `DATA_DIR` directly, since `prsi-orchestrator.py` is a standalone script).

2. Filters events from the last `since_hours` window.

3. Groups by `(failure_class, final_profile)` and counts occurrences.

4. For each group exceeding the threshold (default: `PRSI_FEEDBACK_THRESHOLD=3`), generates a PRSI action dict and calls `_action_fingerprint()` + queue insertion logic from `cmd_sync`.

### 5.3 Failure Class → PRSI Action Type Mapping

| `failure_class` | PRSI `type` | `risk` | `safe` | Generated action |
|-----------------|-------------|--------|--------|-----------------|
| `rate_limited` | `routing` | `low` | `true` | Reduce `max_tokens` cap for profile; add profile to backoff config |
| `json_contract_failed` | `prompt` | `low` | `true` | Add JSON-strict system prompt enforcement for profile |
| `meta_reasoning_leak` | `prompt` | `low` | `true` | Enforce EXACT-OUTPUT gate in system prompt for profile |
| `exact_output_too_verbose` | `prompt` | `low` | `true` | Enforce word-count constraint in delegated prompt template |
| `low_signal_generic` | `prompt` | `low` | `true` | Add evidence-first output requirement to prompt contract |
| `invented_repo_paths` | `knowledge` | `low` | `true` | Seed missing paths to AIDB `codebase-context` collection |
| `empty_content` | `routing` | `medium` | `false` | Route profile to fallback before retry; review max_tokens |
| `provider_http_error` | `routing` | `medium` | `false` | Add circuit-breaker cooldown for profile on 5xx |
| `policy_refusal` | `prompt` | `low` | `true` | Narrow delegated task scope; remove ambiguous phrasing |
| `tool_call_without_final_text` | `prompt` | `low` | `true` | Add explicit post-tool finalization pass requirement |

`low` risk + `safe=true` actions are auto-approved by the existing `AUTO_APPROVE_LOW_RISK` logic in `cmd_sync` (line 396). They will execute on the next `cmd_execute` call.

### 5.4 Integration Call Site

`cmd_sync` in `prsi-orchestrator.py` (currently lines 384–446) currently calls only `_fetch_structured_actions()`. The new call site is:

```python
def cmd_sync(args: argparse.Namespace) -> int:
    # ... existing logic (lines 384-433) unchanged ...
    
    # NEW: ingest delegation feedback patterns
    feedback_results = ingest_delegation_feedback(since_hours=24)
    added += feedback_results.get("added", 0)
    
    # ... rest of function unchanged ...
```

This ensures every `prsi-orchestrator sync` call (which is called by the autonomous loop and by human operators) also ingests feedback patterns.

### 5.5 Dependency on Phase 184A

Phase 184A must complete first. It fixes the null `event_type` on delegation feedback events. Without this fix, `failure_class` may be empty or null for events recorded before the fix. The `ingest_delegation_feedback()` function should guard against null `failure_class` values (`if not record.get("failure_class"): continue`) to be safe against pre-184A records.

---

## 6. Goals and Success Criteria

### 6.1 Goals

1. Activate `ai-autonomous-improvement.timer` so the system runs improvement cycles without human scheduling.
2. Wire `delegation_feedback.jsonl` into the PRSI action queue so recurring delegation failures generate corrective actions automatically.
3. Demonstrate at least one complete unattended improvement cycle: trigger detected → hypothesis generated → experiment executed → sandbox validated → action approved → applied.

### 6.2 Success Criteria (Measurable)

| Criterion | Target | How to Measure |
|-----------|--------|---------------|
| Timer activation | `systemctl status ai-autonomous-improvement.timer` shows `Active: active (waiting)` with a `Next run:` timestamp | Post-rebuild check |
| First autonomous cycle | `aq-autonomous-improve status` shows at least 1 completed cycle within 90 minutes of timer activation | Query `improvement_cycles` table |
| Metric ingestion | `aq-autonomous-improve trends` shows trending data for at least 3 metrics | PostgreSQL `metric_trends` table |
| Delegation feedback consumed | `prsi-orchestrator sync` adds ≥1 action from feedback patterns within first 24h (if failure events exist) | `action-queue.json` `meta.feedback_ingested` field |
| Routing action auto-approved | At least 1 routing or prompt action auto-approved within first cycle | `action-queue.json` status=approved entries |
| Delegation failure rate decrease | Rolling 7-day delegation failure rate decreases by ≥10% within 2 weeks of first adaptation cycle | `delegation-feedback.jsonl` outcome=failed count trend |
| Improvement cycles per week | ≥7 cycles/week (1/day minimum; 60min interval = 24/day theoretical) | `improvement_cycles` table count over 7 days |
| Zero runaway rebuilds | No unsolicited `nixos-rebuild` executions initiated without human gate (high blast_radius stays queued) | PRSI actions log; no rebuild events from ai-hybrid user |

---

## 7. Scope

### In Scope

- Add `autonomousImprovement` stanza to `nix/hosts/hyperd/facts.nix`
- Confirm `autonomous-improvement.nix` is in the service import chain
- Verify `nixos-rebuild switch` activates timer and service correctly
- Implement `ingest_delegation_feedback()` in `scripts/automation/prsi-orchestrator.py`
- Hook `ingest_delegation_feedback()` into `cmd_sync` call path
- Add `prsi_cycle_started`, `prsi_experiment_run`, `prsi_action_approved`, `prsi_action_rejected`, `delegation_feedback_consumed` telemetry events
- Add aq-qa checks for timer active status and PRSI queue depth
- Add dashboard panels for PRSI cycle visibility

### Out of Scope

- Implementing the autonomous_loop → PRSI bridge (hypothesis → queue entry translation) — this is Phase 185C
- Modifying the PostgreSQL schema
- Changing existing PRSI policy gates
- Cross-agent learning (federated patterns across Claude/Qwen/Codex) — deferred per ACTIVATION-STATUS.md
- Rust refactor — deferred indefinitely per MEMORY.md

---

## 8. Technical Approach

### 8.1 Nix Config Change (Phase A)

The single required edit is in `nix/hosts/hyperd/facts.nix`. The `autonomousImprovement` block must be nested inside the `aiStack` block because the option is declared under `mySystem.aiStack.autonomousImprovement` in `autonomous-improvement.nix` line 58:

```nix
options.mySystem.aiStack.autonomousImprovement = {
  enable = lib.mkEnableOption "autonomous improvement system ...";
  ...
```

The `active` local variable in `autonomous-improvement.nix` line 31:
```nix
active = cfg.roles.aiStack.enable && mcp.enable && autonomous.enable;
```

Both `cfg.roles.aiStack.enable` and `mcp.enable` are already true on the operational system. Only `autonomous.enable` is missing.

The timer `timerConfig` (autonomous-improvement.nix lines 155–162):
```nix
timerConfig = {
  OnBootSec = "10min";
  OnUnitActiveSec = "${toString autonomous.interval}min";
  Unit = "ai-autonomous-improvement.service";
  Persistent = true;
};
```

With `interval = 60`, the timer fires 10 minutes after boot, then every 60 minutes. `Persistent = true` means missed fires (e.g., during suspension) run on next boot.

### 8.2 Delegation Feedback Wiring (Phase B)

New function location: `scripts/automation/prsi-orchestrator.py`, inserted before `cmd_sync` (~line 384).

Reading the feedback log path without importing the coordinator module: `DATA_DIR` env var + `telemetry/delegation-feedback.jsonl` suffix — this mirrors what `delegation_feedback_log_path()` computes, avoiding a cross-package import from a standalone script. Fallback: read the path from `os.getenv("DELEGATION_FEEDBACK_LOG_PATH", ...)`.

Aggregation window is configurable via `PRSI_FEEDBACK_WINDOW_HOURS` env var (default 24). Threshold is configurable via `PRSI_FEEDBACK_THRESHOLD` env var (default 3).

The generated action dict must be structurally compatible with what `_action_fingerprint()` hashes (lines 277–288). The stable fields are `type`, `action`, `reason`, `topic`, `services`, `env_overrides`, `script`, `script_args`. For delegation feedback actions, populate `type`, `action` (the improvement_action text), and `reason` (failure class + profile + count).

### 8.3 PRSI Policy Gates Already in Place

The existing `config/runtime-prsi-policy.json` already has:
- `block_high_risk_without_approval: true` — high blast_radius actions never auto-execute
- `auto_revert_on_required_gate_failure: true` — failed gate = automatic revert
- `required_verification: ["syntax_or_lint", "runtime_contract", "report_schema", "security_checks", "focused_smoke_or_eval", "critical_regression_scan"]`
- `stop_conditions` with `halt_and_escalate` on boot regression, unexplained failures, safety uncertainty

These gates protect against runaway cycles. No changes to the policy file are required for Phase 185B.

### 8.4 Autonomous Loop → PRSI Bridge (Phase B partial, Phase C full)

In `autonomous_loop.py`, after `ResearchPhase` generates hypotheses and `ExperimentExecutor` runs experiments with `recommendation=queue` (blast_radius medium/high), the loop should write those queued experiments as PRSI action entries. This is the hypothesis→queue bridge.

For Phase 185B, implement only the minimal wire: after `ExperimentExecutor` sets `recommendation=queue`, write a JSON file to a well-known spool directory (`PRSI_ARTIFACT_DIR/spool/*.json`). The next `prsi-orchestrator sync` call picks up these spooled files and inserts them into the queue. This avoids a direct Python import dependency between the two subsystems.

Full bidirectional bridge (including feedback from executed PRSI actions back into TrendDatabase) is Phase 185C.

---

## 9. Implementation Plan

### Phase A — Activate Timer (requires nixos-rebuild)

**Precondition:** Phase 184A complete (delegation_feedback null event_type fix committed and live).

1. Verify `nix/modules/services/default.nix` imports `./autonomous-improvement.nix`. If not, add it.
2. Add `autonomousImprovement` stanza to `nix/hosts/hyperd/facts.nix`.
3. Run pre-commit gate: `scripts/governance/tier0-validation-gate.sh --pre-commit`
4. Commit: `chore(autonomy): activate ai-autonomous-improvement timer (Phase 185B-A)`
5. Run: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`
6. Validate (see Section 12).

**Estimated effort:** 30 minutes (mostly rebuild time).

### Phase B — Wire Delegation Feedback → PRSI

**Precondition:** Phase A complete. Timer is running and producing cycles.

1. Implement `ingest_delegation_feedback(since_hours: int = 24) -> Dict[str, Any]` in `scripts/automation/prsi-orchestrator.py`.
2. Hook into `cmd_sync` (after existing `_fetch_structured_actions` call, before `_save_queue`).
3. Add `PRSI_FEEDBACK_WINDOW_HOURS` and `PRSI_FEEDBACK_THRESHOLD` env var reads alongside existing env vars at file top (lines 33–36 area).
4. Add `delegation_feedback_consumed` event to `_log_event()` calls in `ingest_delegation_feedback()`.
5. Run: `python3 scripts/automation/prsi-orchestrator.py sync --since=1d` and verify output includes `feedback_ingested` count.
6. Verify at least one action is generated from existing feedback events.
7. Run pre-commit gate and commit: `feat(prsi): ingest delegation feedback patterns into action queue (Phase 185B-B)`

**Estimated effort:** 2–3 hours (implementation + validation).

### Phase C — Validate Closed Loop

**Precondition:** Phase B complete. At least 24h of timer-driven cycles.

1. Query `improvement_cycles` table: confirm cycles completing, not erroring.
2. Query `metric_trends` table: confirm trends updating each cycle.
3. Inspect `action-queue.json`: confirm feedback-derived actions appear and are auto-approved.
4. Trigger a deliberate delegation failure (dry-run, not production): verify it appears in feedback log → appears in PRSI queue on next sync.
5. Add aq-qa checks (see Section 12).
6. Update `ACTIVATION-STATUS.md` to reflect activated state.
7. Seed AIDB with Phase 185B patterns: `python3 scripts/data/seed-rag-knowledge.py` with new bug/fix patterns.
8. Commit: `test(prsi): Phase 185B closed-loop validation (Phase 185B-C)`

**Estimated effort:** 2–4 hours.

---

## 10. Monitoring and Observability

### 10.1 New Telemetry Events

All events appended to `ACTIONS_LOG_PATH` (`/var/log/nixos-ai-stack/prsi-actions.jsonl`) by `_log_event()` in `prsi-orchestrator.py`. Additionally emit to the coordinator telemetry stream where possible.

| Event Name | Payload Fields | Emitted From |
|------------|----------------|-------------|
| `prsi_cycle_started` | `ts, cycle_id, triggered_by, trigger_type, severity` | `autonomous_loop.py` on cycle start |
| `prsi_experiment_run` | `ts, cycle_id, hypothesis_id, experiment_type, blast_radius, recommendation` | `experiment_executor.py` after each run |
| `prsi_action_approved` | `ts, action_id, action_type, risk, approved_by (auto\|human)` | `prsi-orchestrator.py cmd_approve / auto-approve path` |
| `prsi_action_rejected` | `ts, action_id, action_type, risk, reason` | `prsi-orchestrator.py` rejection path |
| `delegation_feedback_consumed` | `ts, window_hours, events_read, failure_classes_seen, actions_generated` | `ingest_delegation_feedback()` |

### 10.2 Metric Keys for Dashboard

| Metric Key | Source | Calculation |
|------------|--------|-------------|
| `prsi.cycles_per_day` | `improvement_cycles` table, `status=completed` | COUNT per day |
| `prsi.experiments_run` | `improvement_cycles`, `experiments_run` field | SUM per day |
| `prsi.approval_rate` | `prsi-actions.jsonl`, `event=approve` / `event=approve + event=reject` | ratio |
| `prsi.queue_depth` | `action-queue.json`, count of `status=pending_approval` entries | gauge |
| `prsi.routing_adaptation_count` | `prsi-actions.jsonl`, `event=execute` with `type=routing` | COUNT |
| `prsi.delegation_failure_rate` | `delegation-feedback.jsonl`, `outcome=failed` / total | ratio, 24h rolling |
| `prsi.feedback_to_action_ratio` | `delegation_feedback_consumed.actions_generated` / `delegation_feedback_consumed.events_read` | ratio |

---

## 11. Dashboard Visualizations

All panels to be added to the existing `command-center-dashboard.nix` frontend. Backend data route: `GET /api/aistack/prsi/metrics` (new route, returns the metric keys above from `prsi-actions.jsonl` + `action-queue.json`).

### Panel 1 — PRSI Improvement Cycle Timeline (Time Series)

- Type: line chart
- X-axis: time (last 7 days)
- Y-axis: cycles completed per hour (binned)
- Series: `cycles_completed` (green), `cycles_failed` (red)
- Alert: red bar if 0 cycles in any 4-hour window during business hours

### Panel 2 — Experiment Pass/Fail Rate (Gauge)

- Type: gauge, 0–100%
- Value: `experiments_accepted / (experiments_accepted + experiments_rejected)` over last 24h
- Thresholds: green ≥70%, yellow 50–70%, red <50%
- Subtext: `N experiments run today`

### Panel 3 — PRSI Action Queue Depth (Gauge with Alert)

- Type: gauge, 0–50
- Value: count of `pending_approval` entries in `action-queue.json`
- Thresholds: green 0–5, yellow 6–10, red >10
- Alert text at >10: "PRSI queue backed up — run `prsi-orchestrator agent` or review pending actions"
- Subtext: oldest pending action age

### Panel 4 — Delegation Failure → PRSI Action Conversion Funnel (Bar Chart)

- Type: horizontal bar chart
- Bars (from top):
  1. `delegation_failures_24h`: total failed delegation events in last 24h
  2. `failure_patterns_detected`: distinct (failure_class, profile) groups above threshold
  3. `prsi_actions_generated`: queue entries generated from feedback
  4. `prsi_actions_approved`: auto-approved (auto-eligible) entries
  5. `prsi_actions_executed`: executed (applied) entries
- Goal: bars should narrow down predictably; large drop between `detected` and `generated` indicates threshold too high

### Panel 5 — Autonomous Improvement ROI: Delegation Success Rate Before/After (Comparison Panel)

- Type: dual metric comparison (before / after)
- "Before" baseline: 7-day delegation success rate on the day Phase 185B was activated
- "After" value: rolling 7-day delegation success rate (current)
- Delta: shown as percentage point change with arrow
- Sub-metric: routing adaptation count (number of routing changes applied)
- This is the core ROI signal: if PRSI is working, the success rate should trend up over weeks

---

## 12. Validation Plan

### 12.1 Timer Activation Without Waiting a Full Cycle

```bash
# After nixos-rebuild switch:

# 1. Confirm timer is instantiated
systemctl status ai-autonomous-improvement.timer
# Expected: Active: active (waiting), Next run: <timestamp>

# 2. Confirm service is declared
systemctl cat ai-autonomous-improvement.service | head -5
# Expected: Description=Autonomous Improvement - Local LLM-driven...

# 3. Force a single cycle immediately (bypasses timer interval)
sudo systemctl start ai-autonomous-improvement.service

# 4. Check service completed
systemctl status ai-autonomous-improvement.service
# Expected: Active: inactive (dead), ExecStart= ... code=exited, status=0/SUCCESS

# 5. Check logs
journalctl -u ai-autonomous-improvement.service -n 50
# Expected: Phase 1 metrics sync, Phase 2 trigger check, no Python errors

# 6. CLI available
aq-autonomous-improve --help
aq-autonomous-improve status
aq-autonomous-improve trends
```

### 12.2 Dry-Run Test (Safe Pre-Activation Check)

Before the first non-dry-run cycle, validate the full loop in dry-run mode:

```bash
# Edit facts.nix temporarily with dryRun = true, rebuild, then:
aq-autonomous-improve run --dry-run
# Expected output (from ACTIVATION-STATUS.md Scenario 2 if anomalies exist):
#   Phase 1: Metrics collected: N, inserted: N, trends: N, anomalies: N
#   Phase 2: Trigger activated OR No triggers
#   Phase 3: Generated N hypotheses
#   DRY RUN MODE - Skipping actual experiment execution
```

### 12.3 Delegation Feedback Wiring Test

```bash
# 1. Check existing feedback events
wc -l "${DATA_DIR}/telemetry/delegation-feedback.jsonl"
# Expected: >0 lines

# 2. Run sync with feedback ingestion enabled
python3 scripts/automation/prsi-orchestrator.py sync --since=1d
# Expected JSON output includes: "feedback_ingested": N

# 3. Inspect queue for feedback-derived actions
python3 scripts/automation/prsi-orchestrator.py list
# Expected: routing or prompt actions with reason starting "delegation feedback:"
```

### 12.4 New aq-qa Checks

Add the following checks to `scripts/ai/aq-qa` (Phase C):

| Check ID | Description | Command | Pass Condition |
|----------|-------------|---------|---------------|
| `0.11.01` | ai-autonomous-improvement.timer is active | `systemctl is-active ai-autonomous-improvement.timer` | exit 0 |
| `0.11.02` | ai-autonomous-improvement last run succeeded | `systemctl show ai-autonomous-improvement.service --property=ExecMainStatus` | `ExecMainStatus=0` |
| `0.11.03` | PRSI queue depth below alert threshold | Check `action-queue.json` pending count | count ≤ 10 |
| `0.11.04` | delegation_feedback consumed in last 24h | Check `prsi-actions.jsonl` for `delegation_feedback_consumed` event | present |
| `0.11.05` | improvement_cycles table has recent entry | PostgreSQL: `SELECT COUNT(*) FROM improvement_cycles WHERE started_at > NOW() - INTERVAL '90 minutes'` | count ≥ 1 |

---

## 13. Risks

### Risk 1 — PRSI Loop Triggering Disruptive Changes

**Description:** If TriggerEngine misclassifies a transient anomaly as a systemic issue, the LLM may generate a hypothesis that proposes a disruptive experiment (e.g., changing LLM model parameters, modifying routing rules in production).

**Mitigations already in place:**
- `AUTONOMOUS_AUTO_APPLY_BLAST_RADIUS_MAX = "low"` in the Nix config means only low blast_radius experiments auto-apply.
- Medium and high blast_radius experiments always route to the PRSI queue for human review (`sandbox_validator.py` line 16: `queue — blast_radius >= medium`).
- `cooldown_minutes = 60` in `trigger_engine.py` line 82 prevents re-triggering the same metric within an hour.
- `stop_conditions.boot_shutdown_regression = "halt_and_escalate"` in PRSI policy halts the loop if a rebuild regression occurs.

**Residual risk:** Low. The human gate on medium/high blast_radius is the primary safety net.

### Risk 2 — Experiment Executor Affecting Production Services

**Description:** A `low` blast_radius experiment that modifies a Python file in a live service path could cause immediate service disruption if the syntax check passes but runtime behavior breaks.

**Mitigations:**
- `SandboxValidator` runs 4 gates in sequence before `accept` recommendation.
- `auto_revert_on_required_gate_failure = true` means any gate failure triggers automatic revert.
- `blast_radius = "low"` is restricted to `_RUNTIME_EXTENSIONS = {".py", ".sh"}` files only (experiment_executor.py line 35). Nix files always get `high`.

**Residual risk:** Medium. Gate 3 (aq-qa ≥39 passes) provides regression protection but may not catch every service-specific runtime failure. Monitoring (Panel 2) detects if experiment failure rate spikes.

### Risk 3 — Runaway Rebuild Cycles

**Description:** If a bug in `autonomous_loop.py` or `prsi-orchestrator.py` causes them to enqueue high blast_radius actions and a human accidentally approves them in bulk, multiple `nixos-rebuild switch` executions could occur in rapid succession.

**Mitigations:**
- High blast_radius actions require `require_independent_verifier_for_high_risk = true` (PRSI policy).
- Timer is one-shot per 60-minute interval — it cannot loop internally.
- `max_execute_per_cycle = 5` in PRSI policy caps how many actions execute per cycle.

**Residual risk:** Low. Manual human approval is required for any action that would trigger a rebuild.

### Risk 4 — Feedback Threshold Too Low → Queue Flooding

**Description:** If `PRSI_FEEDBACK_THRESHOLD` is set too low (e.g., 1), every single delegation failure immediately generates a PRSI action, flooding the queue and hitting the daily token budget.

**Mitigation:** Default threshold = 3. Queue depth alert at >10 (Panel 3). `hard_stop_on_cap = true` in PRSI budget policy. Monitor Panel 4 funnel; if `actions_generated` is disproportionately large vs `failure_patterns_detected`, raise the threshold.

### Risk 5 — Phase 184A Not Complete Before Phase B

**Description:** If `ingest_delegation_feedback()` is implemented before Phase 184A fixes the null `event_type`, all 135 existing feedback events may have null `failure_class`. The ingestion function would generate zero actions despite processing many events.

**Mitigation:** Phase 184A is declared a hard dependency. The function guards against null `failure_class` values to prevent silent zero-result processing. A log warning ("N events had null failure_class — Phase 184A pending?") makes the dependency visible.

---

## 14. Dependencies

### Hard Dependencies

| Dependency | Phase | Description | Status |
|------------|-------|-------------|--------|
| Phase 184A | Before Phase B | Fix null `event_type` on delegation_feedback events so `failure_class` is populated and events are classifiable | Must complete before Phase B implementation |
| PostgreSQL migration 006 | Pre-existing | 8-table autonomous improvement schema must be applied | Applied per ACTIVATION-STATUS.md |
| SOPS secret `/run/secrets/postgres_password` | Pre-existing | Postgres credentials for autonomous_loop.py | Active per ACTIVATION-STATUS.md |
| llama.cpp at port 8080 | Runtime | TriggerEngine and ResearchPhase call `localhost:8080/v1/chat/completions` | Active |

### Soft Dependencies (Recommended Before Full Capability)

| Dependency | Phase | Description |
|------------|-------|-------------|
| Phase 185A — Workflow Engine | Before Phase C | PRSI autonomous agent (`cmd_agent`) dispatches multi-step experiments via aq-agent-loop. The workflow engine from Phase 185A provides structured multi-step execution context that makes complex experiment tasks more reliable. Phase B can operate without it (single-tool actions work via direct execution). |
| Phase 185C — Hypothesis→Queue Bridge | After Phase B | Full bridge from `autonomous_loop.py` hypothesis generation to `prsi-orchestrator.py` queue insertion. Phase 185B uses a spool-file pattern as a minimal bridge. |

### Files Modified or Created

| File | Change Type | Description |
|------|-------------|-------------|
| `nix/hosts/hyperd/facts.nix` | Modify | Add `autonomousImprovement` stanza |
| `nix/modules/services/default.nix` | Verify / possibly modify | Confirm import of `autonomous-improvement.nix` |
| `scripts/automation/prsi-orchestrator.py` | Modify | Add `ingest_delegation_feedback()` function; hook into `cmd_sync` |
| `scripts/ai/aq-qa` | Modify (Phase C) | Add checks 0.11.01–0.11.05 |
| `ai-stack/autonomous-improvement/ACTIVATION-STATUS.md` | Modify (Phase C) | Update to reflect activated state |

---

*End of PRD — Phase 185B — Autonomous Improvement Activation*
