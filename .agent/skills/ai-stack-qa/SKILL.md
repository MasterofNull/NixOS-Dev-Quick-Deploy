---
name: ai-stack-qa
description: QA workflow for the NixOS-Dev-Quick-Deploy AI stack. Use when running health checks, smoke tests, or phase verification on the local AI stack.
---

# Skill: ai-stack-qa

## Description
Provides efficient QA patterns for the local AI stack harness. Prioritizes single-command batch checks over individual per-service calls to minimize token consumption.

## When to Use
- Verifying services after a deploy or restart
- Running QA plan phase checks
- Troubleshooting a failing service
- Before committing AI stack changes

## Key Commands (in order of preference)

### 1. Phase runner — use first, replaces 10-20 bash calls
```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
aq-qa 0           # Phase 0: service health + ports + pings
aq-qa 1           # Phase 1: redis/postgres/qdrant/aidb/hybrid
aq-qa 2           # Phase 2: runtime/package/confinement loop (llama preset)
aq-qa 3           # Phase 3: AppArmor/confinement loop
aq-qa 0 --json    # Machine-readable output
aq-qa 0 --sudo    # Include AppArmor checks
```

### 1.1 runtime diagnosis loop — use before rebuild churn
```bash
aq-runtime-diagnose --preset llama-cpp
aq-runtime-diagnose --preset llama-cpp --json
aq-runtime-diagnose --preset apparmor --json
aq-llama-debug
aq-llama-debug --json
aq-llama-debug --smoke
python3 scripts/ai/aq-runtime-plan
python3 scripts/ai/aq-runtime-act
python3 scripts/ai/aq-runtime-act --brief
python3 scripts/ai/aq-runtime-remediate
```

### 2. Comprehensive health check — use when aq-qa isn't enough
```bash
bash scripts/ai-stack-health.sh
bash scripts/check-mcp-health.sh
```

### 3. Service-specific checks
```bash
# AIDB
curl -sf http://127.0.0.1:8002/health | python3 -m json.tool
AIDB_API_KEY=$(cat /run/secrets/aidb_api_key | tr -d '\n') \
  bash scripts/import-agent-instructions.sh

# Hybrid coordinator
curl -sf http://127.0.0.1:8003/health | python3 -m json.tool
curl -sf 'http://127.0.0.1:8003/hints?q=nixos' | python3 -m json.tool

# llama.cpp
curl -sf http://127.0.0.1:8080/health

# Qdrant
curl -sf http://127.0.0.1:6333/collections | python3 -m json.tool

# Redis
redis-cli ping && redis-cli info server | grep redis_version

# PostgreSQL
psql -U ai_user -d aidb -c '\dt'
```

### 4. Logs — use when a service fails
```bash
journalctl -u ai-aidb.service -n 30 --no-pager
journalctl -u ai-hybrid-coordinator.service -n 30 --no-pager
journalctl -u llama-cpp.service -n 20 --no-pager
```

### 5. Syntax validation before commit
```bash
python3 -m py_compile <file.py>
bash -n <file.sh>
nix-instantiate --parse <file.nix>
```

## QA Plan Reference
Full plan: `docs/archive/root-docs/AI-STACK-QA-PLAN.md`
- Phase 21 (tooling) → do first
- Phase 0 (smoke) → `aq-qa 0`
- Phase 1 (infra) → `aq-qa 1`
- Phase 2 (runtime/package/confinement loop) → `aq-qa 2`
- Phase 3 (AppArmor/confinement loop) → `aq-qa 3`
- Phases 4-10 → see QA plan, run manually

## Token Efficiency Rules
1. Always run `aq-qa <phase>` before individual service checks.
2. Use `--json` when you need to parse results programmatically.
3. For runtime, driver, package, or confinement issues, run `aq-qa 2` first and `aq-qa 3` when confinement is plausible.
4. Use `aq-runtime-diagnose --preset ...` before patching or rebuilding.
5. Start onboarding with one context card, not a full doc dump:
```bash
aq-context-card --card repo-baseline --level brief
aq-context-card --recommend "<task>" --level brief --format=json
aq-context-bootstrap --task "<task>" --format json
aq-capability-gap --tool <name> --format json
python3 scripts/ai/aq-capability-plan --tool <name>
python3 scripts/ai/aq-capability-remediate --tool <name>
python3 scripts/ai/aq-system-act --task "tool not available: <name>"
```
6. Escalate `aq-context-card` from `brief` to `standard` or `deep` only when a specific layer still has a concrete gap.
7. Only open full logs if the phase runner or diagnostic loop reports a FAIL.
8. Trust exit codes — don't re-run checks after a pass.
7. When changing planner or runtime diagnosis behavior, run:
```bash
scripts/testing/check-runtime-incident-tooling.sh
```
This wrapper now covers planner fixtures, diagnosis classifications, `aq-qa` runtime-phase integration, and the remediation runner.
It also covers the context-card progressive-disclosure tooling, so onboarding and incident-entry guidance stay cheap and tested.
Use `aq-runtime-remediate` in dry-run first; only pass `--execute` when the selected action matches the current host state.
Execution is bounded by `config/runtime-remediation-policy.json`; update that policy before broadening any automatic command families.
Use `config/runtime-remediation-catalog.json` to tune `risk`, `requires_sudo`, and `safe_in_live_session` on specific remediation paths before changing runner logic.
For mixed-risk actions, prefer per-command command entries in the catalog instead of widening a whole action’s metadata.
When `aq-runtime-remediate` blocks a command, read `block_reason`, `required_overrides`, and `rollback` from the JSON result instead of inferring from stderr text.
Before using the runner, inspect `approval_summary` from `aq-runtime-plan` to see highest command risk and any override pressure per action.
Read `provenance` alongside `confidence`: built-in planner guardrails should now show stable subtypes such as `planner_builtin_phase0`, `planner_builtin_healthy`, or `planner_builtin_confinement`, while diagnosis-derived actions should show `catalog_diagnosis`.
Prefer `action_kind` over summary parsing when consuming planner output programmatically; it now distinguishes built-in steps like `phase0_stabilization` and `healthy_cleanup` from diagnosis-driven actions.
Prefer `action_origin` when you want one structured source object; it now carries `source`, `trigger`, and diagnosis context such as `preset`, `classification`, `service`, and `layer`.
Prefer `action_id` when correlating planner output across sections or handing an action to later tooling; it is more stable than using list position.
`aq-runtime-remediate` now accepts `--action-id` as well as `--action-index`; prefer the ID path when consuming planner output programmatically.
Use `aq-runtime-remediate --list-actions` when you need cheap action discovery without overloading dry-run preview as a listing API.
Use `aq-runtime-remediate --action-group <bucket>` when you want execution to follow planner buckets directly instead of resolving indices by hand.
Use repeated `--prefer-group` flags when automation should fall back across buckets, for example `observe_first` then `safe_to_run_now`.
Prefer `aq-runtime-remediate --prefer-plan-order` when the planner’s own recommended bucket order should drive selection instead of a caller-defined fallback order.
Use `aq-runtime-act` when you want the planner plus recommended runner selection in one command instead of chaining both tools manually.
Use `aq-runtime-act --brief` when you need a handoff-safe summary with minimal token load instead of the full wrapper payload.
Read `selection_strategy` from `aq-runtime-act` when automation needs to know whether the wrapper followed planner order or an explicit caller override. Current modes include `list_actions`, `explicit_action_id`, `explicit_action_group`, and `prefer_plan_order`.
Read `selection_reason` when you want a compact explanation of why the wrapper chose the current action without reconstructing that reasoning from multiple fields.
Read `incident_summary` first when you need a fast operator-facing status line before inspecting the full wrapper payload.
Read `context_cards.recommended_card_order` from the planner or wrapper when you want the next minimal context load without scanning diagnoses by hand.
Use `aq-runtime-act --save-artifact <path>` when you need a replayable incident artifact from the current planner/remediation state.
Use `artifact_meta` from saved wrapper payloads when you need to verify where and when an incident artifact was captured.
Use the runner’s top-level `selection` object and `available_actions` error hints when wiring automation; they are more robust than scraping nested preview payloads or retrying blind on stale IDs.
Use `action_groups` from `aq-runtime-plan` as the default read order: `observe_first`, then `safe_to_run_now`, then `requires_override`.
If an expected follow-up is missing, check `suppressed_actions` and read `suppression_reason` plus `winner_summary` before assuming the planner lost information.
Use `confidence` to distinguish directly grounded actions from more heuristic ones; suppressed actions should generally carry lower confidence than the winner they point to.
Use `evidence_refs` from `aq-runtime-plan` to trace an action back to the originating QA phase or service/layer signal before executing follow-up commands.
Use `evidence_index` when you need the concrete payload behind a ref instead of manually cross-matching planner sections.
Prefer `evidence_kind` and `evidence_id` when consuming planner output programmatically; treat raw ref strings as compatibility fields.
When task scope is still fuzzy, prefer `aq-context-card --recommend "<task>" --level brief` before loading the full runtime runbook or broad policy docs.
For non-runtime work, prefer `aq-context-bootstrap --task "<task>" --format json` so the system can choose between system-fix, feature-development, PRSI, runtime-incident, and harness-first entrypoints before you open deeper docs.
When a command, workflow, or skill is missing, run `aq-capability-gap` before inventing a manual install path; it classifies the gap and points to the preferred declarative or repo-local fix layer.
When you want the same bounded planner/runner pattern as the runtime stack, use `aq-capability-plan` and `aq-capability-remediate` instead of executing the catalog suggestions manually.
When you want one entrypoint across runtime, capability, and broader bootstrap work, use `aq-system-act`.

## AIDB Import (Phase 11.2)
After AIDB restarts (to pick up schema migration):
```bash
sudo systemctl restart ai-aidb.service
sleep 5
AIDB_API_KEY=$(cat /run/secrets/aidb_api_key | tr -d '\n') \
  bash scripts/import-agent-instructions.sh
```

## Port Reference
| Service | Port |
|---------|------|
| Redis | 6379 |
| PostgreSQL | 5432 |
| Qdrant | 6333 |
| llama.cpp | 8080 |
| llama-embed | 8081 |
| AIDB | 8002 |
| hybrid-coordinator | 8003 |
| ralph-wiggum | 8004 |
| switchboard | 8085 |
| Open WebUI | 3001 |
| Grafana | 3000 |
| Prometheus | 9090 |
