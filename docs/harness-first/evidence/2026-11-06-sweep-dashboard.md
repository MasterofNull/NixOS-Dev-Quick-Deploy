# Dashboard provenance sweep, 2026-11-06

## Objective
Recovery sweep P2.4 (`.agents/plans/system-integrity-recovery/tracker.json`): trace every dashboard card to its fetch, backend route and producer, and flag cards that show literals, defaults or retired lanes as if measured. Report only: no finding is fixed here.

## Workflow/Session IDs
Branch feat/sweep-dashboard, worktree `.agents/delegation/worktrees/p24-dashboard-sweep`. Date 2026-11-06. Command: `scripts/governance/sweep-dashboard.py --live --date 2026-11-06 --report docs/harness-first/evidence/2026-11-06-sweep-dashboard.md`.

## Delegation Decision
Orchestrator: caller session. Implementer: Claude Sonnet 5.5 (Rule 17, balanced tier). One new script, one test, a CI manifest entry and this report; no dashboard code changed.

## Validation Evidence

Scope: 22 HTML pages, 44 JS sources (305 function spans), 617 HTML ids, 474 mounted backend routes.
Cards traced: 482 (an id with a placeholder/literal, or one a script writes). Distinct endpoints the cards use: 147. Fetch calls whose URL could not be resolved statically: 19.

Card status: NO_FETCH 14, NO_ROUTE 3, TRACED 448, UNTRACED 17. TRACED = fetch and route both found. UNTRACED = no fetch found for a JS-written card (unknown, not a pass).

### Counts per class

| Class | Findings | Cards affected |
|---|---:|---:|
| NO_FETCH | 3 | 3 |
| NO_ROUTE | 2 | 6 |
| NO_PRODUCER | 3 | 8 |
| HARDCODED | 33 | 57 |
| SILENT_DEFAULT | 6 | 18 |
| FAKE_FALLBACK | 1 | 2 |
| RETIRED_REF | 6 | 3 |
| **Total** | **54** | |

Route modules defining routes but never included in `main.py` (their routes are not served): `dashboard/backend/api/routes/search_performance.py`, `dashboard/backend/api/routes/security.py`.

### Findings

| # | Class | Conf | Subject | Evidence | Where | Cards |
|---:|---|---|---|---|---|---|
| 1 | NO_FETCH | high | `cockpitApiHealth` | placeholder '--' and no script references #cockpitApiHealth | `dashboard.html:2309` | `cockpitApiHealth` |
| 2 | NO_FETCH | high | `handoffs-list` | placeholder '' and no script references #handoffs-list | `dashboard.html:4577` | `handoffs-list` |
| 3 | NO_FETCH | high | `loading-panel` | placeholder 'Loading live projection from /' and no script references #loading-panel | `assets/aqos-progress-tracker.html:491` | `loading-panel` |
| 4 | NO_ROUTE | high | `/api/control/ai-coordinator/approvals/quick-approve` | quickApproveUI() at 10069 fetches POST /api/control/ai-coordinator/approvals/quick-approve: no route serves this path | `assets/dashboard.js:10069` | `cockpitThoughtLine`, `stream-active-label`, `fleet-thought-stream` |
| 5 | NO_ROUTE | high | `/api/status` | loadAqDecide() at 965 fetches GET /api/status: no route serves this path | `assets/dashboard.js:965` | `decideEngineStatus`, `decidePsiDrift`, `decideCalibrationStatus` |
| 6 | NO_PRODUCER | medium | `dashboard/backend/api/routes/aistack.py:get_latest_remediation <- /var` | route reads /var/lib/ai-stack/hybrid/remediation/hint-remediation/aq-auto-remediation-latest.json (dashboard/backend/api/routes/aistack.py); no repo file writes that path or its basename | `dashboard/backend/api/routes/aistack.py` | `homeostasisBadge`, `homeostasisDetails`, `remedBadge`, `remediationList` |
| 7 | NO_PRODUCER | medium | `dashboard/backend/api/routes/adk.py:get_status <- /etc/nixos/.agent/ad` | route reads /etc/nixos/.agent/adk (dashboard/backend/api/routes/adk.py); no repo file writes that path or its basename | `dashboard/backend/api/routes/adk.py` | `adkStatusBadge`, `adkStatusDetails` |
| 8 | NO_PRODUCER | medium | `dashboard/backend/api/routes/aistack.py:get_workflow_graph <- /var/lib` | route reads /var/lib/nixos-ai-stack/audit/tool_audit.jsonl (dashboard/backend/api/routes/aistack.py); no repo file writes that path or its basename | `dashboard/backend/api/routes/aistack.py` | `workflowCanvas`, `workflowHud` |
| 9 | HARDCODED | high | `execGovernanceScore` | HTML shows literal '53/53 GATES' and no script ever references #execGovernanceScore: it is never replaced | `dashboard.html:2728` | `execGovernanceScore` |
| 10 | HARDCODED | high | `execSwarmHealth` | setText('execSwarmHealth', '98%') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:837` | `execSwarmHealth` |
| 11 | HARDCODED | high | `fleetHeroConsensus` | HTML shows literal 'NOMINAL' and no script ever references #fleetHeroConsensus: it is never replaced | `dashboard.html:4410` | `fleetHeroConsensus` |
| 12 | HARDCODED | high | `healthScore` | setText('healthScore', '98') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:835` | `healthScore` |
| 13 | HARDCODED | high | `histCurCtx` | setText('histCurCtx', '85%') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:885` | `histCurCtx` |
| 14 | HARDCODED | high | `histCurGates` | HTML shows literal '53 / 53 (100%)' and no script ever references #histCurGates: it is never replaced | `dashboard.html:2669` | `histCurGates` |
| 15 | HARDCODED | high | `histCurLat` | setText('histCurLat', '18 ms') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:1258` | `histCurLat` |
| 16 | HARDCODED | high | `kpiHealthScore` | setText('kpiHealthScore', '98') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:836` | `kpiHealthScore` |
| 17 | HARDCODED | high | `kpiUptime` | setText('kpiUptime', '22.5h') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:892` | `kpiUptime` |
| 18 | HARDCODED | high | `metric-latency` | HTML shows literal '1.6ms' and no script ever references #metric-latency: it is never replaced | `assets/cockpit/stream-card.html:35` | `metric-latency` |
| 19 | HARDCODED | high | `metric-tokens` | HTML shows literal '3,420' and no script ever references #metric-tokens: it is never replaced | `assets/cockpit/stream-card.html:34` | `metric-tokens` |
| 20 | HARDCODED | high | `opsHeroBadge` | HTML shows literal '16/17 SERVICES ONLINE' and no script ever references #opsHeroBadge: it is never replaced | `dashboard.html:4026` | `opsHeroBadge` |
| 21 | HARDCODED | high | `opsHeroServices` | HTML shows literal '16 / 17' and no script ever references #opsHeroServices: it is never replaced | `dashboard.html:4035` | `opsHeroServices` |
| 22 | HARDCODED | high | `secHeroBadge` | HTML shows literal '53/53 GATES PASS · HARDENED' and no script ever references #secHeroBadge: it is never replaced | `dashboard.html:3824` | `secHeroBadge` |
| 23 | HARDCODED | high | `secHeroGates` | HTML shows literal '53 / 53 PASS' and no script ever references #secHeroGates: it is never replaced | `dashboard.html:3833` | `secHeroGates` |
| 24 | HARDCODED | high | `spiderHeroBadge` | HTML shows literal '8/8 LAYERS VERIFIED' and no script ever references #spiderHeroBadge: it is never replaced | `dashboard.html:4328` | `spiderHeroBadge` |
| 25 | HARDCODED | high | `spiderHeroLayers` | HTML shows literal '8 / 8 LAYERS' and no script ever references #spiderHeroLayers: it is never replaced | `dashboard.html:4337` | `spiderHeroLayers` |
| 26 | HARDCODED | high | `vCacheHit` | setText('vCacheHit', '92%') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:1262` | `vCacheHit` |
| 27 | HARDCODED | high | `vIntentUnknown` | setText('vIntentUnknown', '0%') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:2056` | `vIntentUnknown` |
| 28 | HARDCODED | high | `vLatP95` | setText('vLatP95', '<1ms') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:1257` | `vLatP95` |
| 29 | HARDCODED | high | `vLogicDiscipline` | setText('vLogicDiscipline', '100%') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:1980` | `vLogicDiscipline` |
| 30 | HARDCODED | high | `vStack` | setText('vStack', '0%') writes a literal as if measured (failure/else branch: shown when the fetch fails) | `assets/dashboard.js:1242` | `vStack` |
| 31 | HARDCODED | medium | `loadKPIs:cur.query_ok_n` | `cur.query_ok_n ?? 2400` shows 2400 as if measured when the response lacks the field LIVE: key `query_ok_n` present in live response of /api/insights/routing/analytics; the literal is a fallback only | `assets/dashboard.js:940` | `lastUpdate`, `healthScore`, `kpiLocalPct`, `kpiCacheHit` +30 |
| 32 | HARDCODED | medium | `loadKPIs:hs.score` | `hs.score != null ? ... : 98` shows 98 as if measured when the field is missing | `assets/dashboard.js:809` | `lastUpdate`, `healthScore`, `kpiLocalPct`, `kpiCacheHit` +30 |
| 33 | HARDCODED | medium | `loadKPIs:metrics.embedding_cache_hit_rate_pct` | `metrics.embedding_cache_hit_rate_pct ?? 92` shows 92 as if measured when the response lacks the field | `assets/dashboard.js:845` | `lastUpdate`, `healthScore`, `kpiLocalPct`, `kpiCacheHit` +30 |
| 34 | HARDCODED | medium | `loadKPIs:metrics.embedding_cache_hit_rate_pct` | `metrics.embedding_cache_hit_rate_pct ?? 85` shows 85 as if measured when the response lacks the field | `assets/dashboard.js:868` | `lastUpdate`, `healthScore`, `kpiLocalPct`, `kpiCacheHit` +30 |
| 35 | HARDCODED | medium | `loadKPIs:metrics.eval_latest_pct` | `metrics.eval_latest_pct ?? 100` shows 100 as if measured when the response lacks the field | `assets/dashboard.js:844` | `lastUpdate`, `healthScore`, `kpiLocalPct`, `kpiCacheHit` +30 |
| 36 | HARDCODED | medium | `loadKPIs:metrics.hint_adoption_pct` | `metrics.hint_adoption_pct ?? 100` shows 100 as if measured when the response lacks the field | `assets/dashboard.js:846` | `lastUpdate`, `healthScore`, `kpiLocalPct`, `kpiCacheHit` +30 |
| 37 | HARDCODED | medium | `loadKPIs:metrics.llm_routing_local_pct` | `metrics.llm_routing_local_pct ?? 94` shows 94 as if measured when the response lacks the field | `assets/dashboard.js:843` | `lastUpdate`, `healthScore`, `kpiLocalPct`, `kpiCacheHit` +30 |
| 38 | HARDCODED | medium | `loadCLMStatus:d.hot_max_mb` | `d.hot_max_mb \|\| 256` shows 256 as if measured when the response lacks the field LIVE: key `hot_max_mb` present in live response of /api/context/lifecycle/status; the literal is a fallback only | `assets/dashboard.js:6074` | `clmBadge`, `clmDetails` |
| 39 | HARDCODED | medium | `loadCapabilities:sessSafety.threshold_mb` | `sessSafety.threshold_mb \|\| 2.5` shows 2.5 as if measured when the response lacks the field LIVE: key `threshold_mb` present in live response of /api/metrics/system; the literal is a fallback only | `assets/dashboard.js:332` | `capabilitiesBadge`, `capabilitiesOverviewDetails` |
| 40 | HARDCODED | medium | `loadHarnessScorecard:acc.target` | `acc.target \|\| 0.7` shows 0.7 as if measured when the response lacks the field LIVE: key `target` present in live response of /api/aistack/harness/scorecard; the literal is a fallback only | `assets/dashboard.js:6714` | `harnessScoreBadge`, `harnessScoreDetails` |
| 41 | HARDCODED | medium | `healthScore` | setText('healthScore', '0') writes a literal as if measured | `assets/dashboard.js:1771` | `healthScore` |
| 42 | SILENT_DEFAULT | high | `dashboard/backend/api/routes/aistack.py:get_scheduler_queue` | except branch returns ok/zero instead of unknown: return {'available': True, 'depth': 0, 'running': None, 'queue': [], 'note': 'no queue sta | `dashboard/backend/api/routes/aistack.py:3248` | `kpiQueueDepth`, `queueBadge`, `queueDetails` |
| 43 | SILENT_DEFAULT | high | `dashboard/backend/api/routes/aistack.py:get_drops_status` | except branch returns ok/zero instead of unknown: return 0 | `dashboard/backend/api/routes/aistack.py:8802` | `dropZoneBadge`, `dropZoneDetails` |
| 44 | SILENT_DEFAULT | medium | `dashboard/backend/api/routes/aistack.py:proxy_traces_summary` | missing-data branch `if not traces` returns ok/zero: return {'count': 0, 'intent_breakdown': {}, 'backend_breakdown': {}, ' | `dashboard/backend/api/routes/aistack.py:4423` | `routeBody`, `routeLocalP`, `routeTotal`, `statIntentUnknown` +2 |
| 45 | SILENT_DEFAULT | medium | `dashboard/backend/api/routes/aistack.py:get_learning_stats` | except branch returns ok/zero instead of unknown: return 0 [via dashboard/backend/api/routes/aistack.py:_count_text_records] | `dashboard/backend/api/routes/aistack.py:1203` | `learnPipelineBadge`, `learnPipelineDetails`, `learningActivity`, `learningBadge` +1 |
| 46 | SILENT_DEFAULT | medium | `dashboard/backend/api/routes/firewall.py:get_firewall_audit_log` | missing-data branch `if not log_path.exists()` returns ok/zero: return {'entries': [], 'count': 0} | `dashboard/backend/api/routes/firewall.py:804` | `fwAuditBadge`, `fwAuditDetails` |
| 47 | SILENT_DEFAULT | low | `dashboard/backend/api/routes/aistack.py:get_learning_stats` | missing-data branch `if not path.exists() or not path.is_file()` returns ok/zero: return 0 [via dashboard/backend/api/routes/aistack.py:_count_text_records] | `dashboard/backend/api/routes/aistack.py:1198` | `learnPipelineBadge`, `learnPipelineDetails`, `learningActivity`, `learningBadge` +1 |
| 48 | FAKE_FALLBACK | medium | `dashboard/backend/api/routes/models.py:list_models` | identifier `_stub_catalog` on a production path | `dashboard/backend/api/routes/models.py:116` | `mlBadge`, `modelList` |
| 49 | RETIRED_REF | high | `assets/cockpit/stream-card.html:9` | text 'antigravity' presents the retired Antigravity lane | `assets/cockpit/stream-card.html:9` | `active-agent-badge` |
| 50 | RETIRED_REF | high | `dashboard.html:2279` | text 'ORCHESTRATOR: ANTIGRAVITY' presents the retired Antigravity lane | `dashboard.html:2279` | `cockpitLaneBadge` |
| 51 | RETIRED_REF | high | `dashboard.html:2300` | text '[antigravity] Mounting Tier 1 Human Intervention Dock & Objective HUD ' presents the retired Antigravity lane | `dashboard.html:2300` | `cockpitThoughtLine` |
| 52 | RETIRED_REF | medium | `assets/modules/local-agent-delegation.html:326` | text 'graph TD A[Switchboard :8085] -->\|Routes\| B[antigravity CLI] B -->\|Pri' presents the retired Antigravity lane | `assets/modules/local-agent-delegation.html:326` |  |
| 53 | RETIRED_REF | medium | `dashboard.html:4445` | text 'gemini / antigravity' presents the retired Antigravity lane | `dashboard.html:4445` |  |
| 54 | RETIRED_REF | medium | `dashboard.html:4454` | text '\U000f06a9 Google Antigravity / Gemini 3.8 (Switchboard :8085)' presents the retired Antigravity lane | `dashboard.html:4454` |  |

### Live probe

Base URL: `http://127.0.0.1:8889` (config/service-endpoints.sh). Method: GET only. Probed 100; skipped 47 (unknown, not counted as pass).
Safe-GET determination: route declared GET in the AST, call site has no non-GET method, no path parameter, no verb-like segment, and no side-effect marker (subprocess, file write, outbound POST/PUT/DELETE, remove/rename) in the handler or helpers within 2 hops. The only server-side effect of a request is the operator-audit line and one rate-limit token counted by the middleware.

| Endpoint | HTTP | ms | Bytes | Blank fields | Freshness | Cards |
|---|---:|---:|---:|---|---|---:|
| `/api/adk/discoveries` | 200 | 32 | 104 | discoveries | unknown | 2 |
| `/api/adk/gaps` | 200 | 6 | 81 | gaps | unknown | 2 |
| `/api/adk/status` | 200 | 193 | 187 | components.parity_tracker.last_updated, components.discovery.last_run, components.gap_analysis.last_run | unknown | 2 |
| `/api/affective/state` | 200 | 62 | 193 | none | fresh (age 51s) | 9 |
| `/api/agent-ops/status` | 200 | 6 | 96 | profile_override, since | unknown | 2 |
| `/api/ai/health/rag` | 200 | 5 | 84 | none | unknown | 2 |
| `/api/ai/homeostasis/events` | 200 | 8 | 2 | <root empty> | unknown | 3 |
| `/api/ai/memory/status` | 200 | 5 | 199 | none | unknown | 2 |
| `/api/ai/remediation/latest` | 200 | 4 | 81 | none | fresh (age 0s) | 4 |
| `/api/aidb/health/detailed` | 200 | 275 | 632 | readiness.details.dependencies[].error | fresh (age 0s) | 2 |
| `/api/aistack/advanced/runtime-summary` | - | 8007 | - | TimeoutError: timed out | unknown | 17 |
| `/api/aistack/agent-runs/race` | 200 | 6745 | 6006 | experiment_id | unknown | 2 |
| `/api/aistack/agent-runs/swimlane` | 200 | 5569 | 357053 | experiment_id, lanes[].spec_variant, lanes[].summary.experiment_id, lanes[].summary.spec_variant, lanes[].summary.accept | unknown | 7 |
| `/api/aistack/agent-tree` | 200 | 5308 | 9840 | roots[].parent_id, roots[].last_thought, roots[].last_tool, roots[].children, roots[].parent_id +7 | unknown | 6 |
| `/api/aistack/agent/collab-state` | 200 | 1876 | 2969 | none | fresh (age 0s) | 13 |
| `/api/aistack/harness/scorecard` | 200 | 130 | 759 | failures.recent_failed_cases | fresh (age 0s) | 2 |
| `/api/aistack/harness/stats` | 200 | 5 | 410 | none | fresh (age 12s) | 2 |
| `/api/aistack/hints/stats` | 200 | 902 | 1234 | none | fresh (age 0s) | 2 |
| `/api/aistack/insights/tools/heatmap` | 200 | 1198 | 3014 | none | fresh (age 0s) | 2 |
| `/api/aistack/local-agent/monitor` | 200 | 506 | 29068 | tasks[].registry_status, tasks[].pid_alive, tasks[].inferred_reason, tasks[].stage, tasks[].latest_call_timing.call_numb | unknown | 2 |
| `/api/aistack/mcp/v2/tools` | 200 | 9 | 20341 | id | unknown | 2 |
| `/api/aistack/memory/supersede/history` | 200 | 8 | 2360 | none | stale (age 14459833s) | 2 |
| `/api/aistack/network-policy` | 200 | 11 | 263 | connectivity, freshness, lease, last_transition_age, transition_count_bucket +1 | unknown | 2 |
| `/api/aistack/operator/intelligence` | 200 | 6 | 215 | open_research_threads, prompt_specificity_trend, last_updated | unknown | 3 |
| `/api/aistack/orchestration/sessions` | 200 | 413 | 136625 | sessions[].orchestration_runtime.workspace.resolved_profile.network_policy, sessions[].orchestration_runtime.workspace.n | fresh (age 283s) | 5 |
| `/api/aistack/policy/tool-deny-stats` | 200 | 20 | 505 | breakdown, policy.execute-guarded, policy.worktree-guarded | unknown | 2 |
| `/api/aistack/prometheus/query` | 422 | 3 | - | HTTP 422 | unknown | 2 |
| `/api/aistack/switchboard/profiles` | 200 | 37 | 5099 | version, profiles.default.forceProvider, profiles.default.forceModel, profiles.continue-local.forceModel, profiles.local | fresh (age 0s) | 2 |
| `/api/aistack/task-classification/stats` | 200 | 8 | 1852 | none | fresh (age 0s) | 15 |
| `/api/approval-inbox` | 200 | 24 | 7229 | none | fresh (age 0s) | 2 |
| `/api/approvals` | 200 | 4 | 935 | none | stale (age 47379s) | 10 |
| `/api/approvals/pending` | 200 | 579 | 105 | none | unknown | 3 |
| `/api/audit/operator/events` | 200 | 475 | 39368 | filters.path_prefix, filters.method, filters.status_code, filters.category, filters.contains +3 | stale (age 6104s) | 2 |
| `/api/audit/operator/integrity` | 200 | 818 | 775 | first_invalid_index, invalid_reason | unknown | 2 |
| `/api/audit/operator/summary` | 200 | 755 | 848 | integrity.first_invalid_index, integrity.invalid_reason | fresh (age 0s) | 2 |
| `/api/budget/policy` | 200 | 361 | 412 | none | unknown | 2 |
| `/api/capabilities/overview` | 200 | 8 | 1524 | none | unknown | 2 |
| `/api/collaboration/locks` | 200 | 11 | 193 | locks | fresh (age 0s) | 3 |
| `/api/collaboration/metrics/summary` | 200 | 26 | 1529 | none | unknown | 2 |
| `/api/collaboration/patterns` | 200 | 4 | 290 | none | unknown | 2 |
| `/api/config` | 200 | 23 | 14218 | documentation_sources[].preview_lines, workflow_blueprints[].orchestration_policy.collaborator_lanes, workflow_blueprint | unknown | 2 |
| `/api/config/graphs/workflow-blueprints` | 200 | 338 | 74037 | blueprints[].orchestration_policy.collaborator_lanes, blueprints[].orchestration_policy.collaborator_lanes, blueprints[] | unknown | 2 |
| `/api/containers` | 200 | 111 | 1495 | [].image, [].created, [].image, [].created, [].image +1 | unknown | 2 |
| `/api/context/lifecycle/status` | 200 | 6 | 375 | none | unknown | 2 |
| `/api/coordinator/ai-status` | 200 | 1276 | 18682 | shared_skill_registry.skills[].description, report_summary.continue_editor.top_failure_category, report_summary.continue | fresh (age 2s) | 2 |
| `/api/discovery/signals` | 200 | 4 | 380 | candidates, signals, sources | stale (age 22391870s) | 2 |
| `/api/drops/status` | 200 | 12 | 243 | none | fresh (age 0s) | 2 |
| `/api/eval/trend` | 200 | 69 | 874 | ragas_by_model.remote.faithfulness_avg | unknown | 10 |
| `/api/firewall/audit-log` | 200 | 102 | 2160 | entries[].details.error, entries[].details.error, entries[].details.error | stale (age 14780883s) | 2 |
| `/api/fleet/status` | 200 | 230 | 119 | agents, sessions | fresh (age 0s) | 3 |
| `/api/fleet/summary` | 200 | 33 | 254 | recent_deployments | unknown | 2 |
| `/api/graph/vector` | 200 | 3 | 33475 | none | fresh (age 79s) | 4 |
| `/api/graph/workflow` | 200 | 3 | 1335 | none | fresh (age 0s) | 2 |
| `/api/hardware/state` | 200 | 25 | 6044 | reindex_status, slots[].params.lora, slots[].params.reasoning_format, slots[].params.generation_prompt, slots[].params.s | fresh (age 3s) | 3 |
| `/api/harness/overview` | 200 | 861 | 7261 | harness.scorecard.failures.recent_failed_cases, policies.tool_registry_security.missing_tools, maintenance.improvement_p | fresh (age 0s) | 6 |
| `/api/health/alerts` | 200 | 60 | 130 | alerts | unknown | 2 |
| `/api/health/categories` | 200 | 4 | 68 | none | unknown | 2 |
| `/api/health/layered` | 200 | 18 | 59741 | none | unknown | 4 |
| `/api/health/services/all` | 200 | 2796 | 35750 | services.ai-aidb.details, services.ai-hybrid-coordinator.http_health.payload.circuit_breakers.qdrant.last_failure_time,  | fresh (age 0s) | 2 |
| `/api/hints/active` | 200 | 1023 | 3867 | query, prompt_coaching.token_discipline.cloud_when, domain_context.primary_domain.skills, domain_context.primary_domain. | fresh (age 0s) | 2 |
| `/api/hints/report` | 200 | 3 | 1455 | agent_lessons.candidates | fresh (age 0s) | 2 |
| `/api/insights/cache/analytics` | 200 | 4 | 370 | none | fresh (age 369s) | 2 |
| `/api/insights/hints/effectiveness` | 200 | 220 | 1993 | adoption.tooling_plan_success_pct, adoption.analysis_profile_success_pct, recent_adoption.tooling_plan_success_pct, rece | fresh (age 369s) | 2 |
| `/api/insights/improvements/candidates` | 200 | 6 | 1799 | none | fresh (age 369s) | 2 |
| `/api/insights/metrics/ai-specific` | 200 | 1143 | 585 | delegated_prompt_optimization.avg_tokens_before, delegated_prompt_optimization.avg_tokens_after, delegated_quality.avg_q | fresh (age 371s) | 2 |
| `/api/insights/queries/complexity` | 200 | 5 | 5653 | query_gaps[].collection, gap_remediation.top_strategies, gap_remediation.candidates, gap_remediation.actions, retrieval_ | fresh (age 371s) | 2 |
| `/api/insights/routing/analytics` | 200 | 6 | 3141 | remote_profile_utilization.windows.1h.top_runtime_ids, remote_profile_utilization.windows.1h.top_requester_roles, remote | fresh (age 371s) | 45 |
| `/api/insights/security/compliance` | 200 | 911 | 1827 | audit.integrity.first_invalid_index, audit.integrity.invalid_reason, audit_integrity.first_invalid_index, audit_integrit | fresh (age 0s) | 2 |
| `/api/insights/tools/performance` | 200 | 240 | 2002 | none | fresh (age 372s) | 2 |
| `/api/insights/workflows/a2a-readiness` | 200 | 306 | 665 | none | unknown | 2 |
| `/api/insights/workflows/compliance` | 200 | 4 | 2339 | intent_contract.accepted_by_requester_role, intent_contract.rejected_by_requester_role, intent_contract.top_reviewers, i | fresh (age 373s) | 2 |
| `/api/knowledge/graph/fact-chain` | 200 | 224 | 48 | facts | unknown | 2 |
| `/api/loop/status` | 200 | 647 | 656 | pass_rate_alert, last_run.reason, checkpoint | unknown | 3 |
| `/api/memory/broker/status` | 200 | 5 | 199 | none | unknown | 2 |
| `/api/memory/crystalline/status` | 200 | 5 | 90 | none | stale (age 73309s) | 2 |
| `/api/memory/stats` | 200 | 10 | 302 | none | fresh (age 0s) | 2 |
| `/api/metrics/system` | 200 | 725 | 1355 | security.firewall.rules_count | unknown | 84 |
| `/api/model-optimization/readiness` | 200 | 23 | 1316 | none | unknown | 2 |
| `/api/model-optimization/training-data/stats` | 200 | 5 | 388 | none | unknown | 2 |
| `/api/orchestration/evaluations/trends` | 200 | 7 | 3902 | none | stale (age 16805905s) | 2 |
| `/api/orchestration/sessions` | 200 | 123 | 136625 | sessions[].orchestration_runtime.workspace.resolved_profile.network_policy, sessions[].orchestration_runtime.workspace.n | fresh (age 306s) | 2 |
| `/api/parity/scorecard` | 200 | 6 | 515 | none | unknown | 2 |
| `/api/ports/registry` | 200 | 7 | 863 | none | unknown | 2 |
| `/api/query/traces` | 200 | 196 | 24453 | traces[].llm_model, traces[].otel_attributes.gen_ai.request.model, traces[].otel_attributes.gen_ai.response.model, trace | unknown | 6 |
| `/api/ralph/integration-health` | 200 | 34 | 422 | none | fresh (age 0s) | 2 |
| `/api/ralph/stats` | 200 | 6 | 162 | adaptive.task_types | unknown | 2 |
| `/api/reasoning/profiles` | 200 | 6 | 3023 | profiles[].max_steps, profiles[].token_budget, active_profile | unknown | 2 |
| `/api/routing/decisions` | 200 | 43 | 1455 | filters.route_alias, filters.routed_profile, items[].category, items[].category, items[].category | fresh (age 0s) | 2 |
| `/api/scheduler/queue` | 200 | 3 | 69 | running, queue | unknown | 3 |
| `/api/scheduler/status` | 200 | 5 | 453 | backpressure_events | unknown | 2 |
| `/api/security/audit` | 200 | 491 | 15072 | npm_monitor.quarantine_state, dashboard_operator.checks.root.error, dashboard_operator.checks.root.headers.content_secur | fresh (age 0s) | 2 |
| `/api/stats/circuit-breakers` | 200 | 5 | 179 | circuit_breakers.qdrant.last_failure_time | fresh (age 0s) | 2 |
| `/api/stats/learning` | 200 | 276 | 1206 | recent_metrics | stale (age 20040980s) | 5 |
| `/api/testing/executions` | 200 | 49 | 27 | executions | unknown | 2 |
| `/api/testing/suites` | 200 | 264 | 977 | none | unknown | 2 |
| `/api/topology` | 200 | 53 | 1440 | none | fresh (age 0s) | 2 |
| `/api/topology/flow` | 200 | 4 | 969 | none | unknown | 2 |
| `/api/traces/drift` | 200 | 6 | 185 | none | unknown | 4 |
| `/api/traces/summary` | 200 | 16 | 230 | none | unknown | 6 |
| `/api/understand/summary` | 200 | 65 | 672 | staleness.commits_since_graph, staleness.reasons | unknown | 1 |

Files read by NO_PRODUCER routes (os.stat on this host, read-only):

- `/var/lib/ai-stack/hybrid/remediation/hint-remediation/aq-auto-remediation-latest.json`: missing (FileNotFoundError)
- `/etc/nixos/.agent/adk`: missing (FileNotFoundError)
- `/var/lib/nixos-ai-stack/audit/tool_audit.jsonl`: missing (FileNotFoundError)

Skipped:

- `/api/actions`: verb-like path segment
- `/api/actions/execute`: call site method is POST
- `/api/agent-ops/local-direct-health`: side-effect marker in handler chain: create_subprocess_exec() in _refresh_local_direct_health
- `/api/ai/metrics`: side-effect marker in handler chain: write() in _redis_ping_probe
- `/api/aistack/agent-runs/{}/control`: call site method is POST
- `/api/aistack/agent-runs/{}/guidance`: call site method is POST
- `/api/aistack/agent-tasks/active`: side-effect marker in handler chain: replace() in get_active_agent_tasks
- `/api/aistack/aq-qa/run/0`: verb-like path segment
- `/api/aistack/effectiveness/scorecard`: side-effect marker in handler chain: replace() in get_effectiveness_scorecard
- `/api/aistack/health/audit`: side-effect marker in handler chain: replace() in get_system_audit_log
- `/api/aistack/knowledge/observatory`: side-effect marker in handler chain: replace() in knowledge_observatory
- `/api/aistack/local-insights/latest`: side-effect marker in handler chain: replace() in get_local_insights_latest
- `/api/aistack/revocation/fire`: call site method is POST
- `/api/aistack/routing/summary`: side-effect marker in handler chain: replace() in _parse_iso_timestamp
- `/api/aistack/training/health`: side-effect marker in handler chain: replace() in get_training_health
- `/api/aistack/verify-self/results`: side-effect marker in handler chain: create_subprocess_exec() in get_verify_self_results
- `/api/alerts/status`: side-effect marker in handler chain: replace() in get_alerts_status
- `/api/control/ai-coordinator/approvals/quick-approve`: call site method is POST
- `/api/deployments/active`: side-effect marker in handler chain: execute() in get_recent_deployments
- `/api/deployments/history`: side-effect marker in handler chain: execute() in get_recent_deployments
- `/api/firewall/crowdsec/status`: side-effect marker in handler chain: create_subprocess_exec() in run_command
- `/api/firewall/rules`: side-effect marker in handler chain: create_subprocess_exec() in run_command
- `/api/firewall/status`: side-effect marker in handler chain: create_subprocess_exec() in run_command
- `/api/graph/vectorization`: side-effect marker in handler chain: replace() in knowledge_observatory
- `/api/health/aggregate`: side-effect marker in handler chain: run() in _run_full_health_probe
- `/api/health/categories/{}`: path has a parameter; no safe value to substitute
- `/api/insights/actions/recommendations`: verb-like path segment
- `/api/insights/performance/hotspots`: side-effect marker in handler chain: mkdir() in append
- `/api/insights/system/health`: side-effect marker in handler chain: mkdir() in append
- `/api/loop/control`: call site method is POST
- `/api/metrics`: side-effect marker in handler chain: write() in _redis_ping_probe
- `/api/metrics/health-score`: side-effect marker in handler chain: replace() in calculate_health_score
- `/api/models`: side-effect marker in handler chain: copy() in _catalog_metadata
- `/api/pm/progress`: side-effect marker in handler chain: create_subprocess_exec() in get_pm_progress
- `/api/prsi/actions`: verb-like path segment
- `/api/routing/lane-failures`: side-effect marker in handler chain: replace() in _parse_iso_timestamp
- `/api/security-settings/status`: side-effect marker in handler chain: replace() in _read_snapshot
- `/api/services`: side-effect marker in handler chain: replace() in list_services
- `/api/stats/capability-enforcement`: side-effect marker in handler chain: run() in get_capability_enforcement
- `/api/status`: no GET route (NO_ROUTE); not requested
- `/api/system-navigator`: side-effect marker in handler chain: replace() in get_system_navigator
- `/api/telemetry/anomalies`: side-effect marker in handler chain: run() in _run_full_health_probe
- `/api/verify-self/results`: side-effect marker in handler chain: create_subprocess_exec() in get_verify_self_results
- `/api/workflows/history`: side-effect marker in handler chain: replace() in get_workflow_history
- `/api/workflows/statistics`: side-effect marker in handler chain: replace() in get_statistics
- `/ws/agent-state`: call site method is WEBSOCKET
- `/ws/metrics`: call site method is WEBSOCKET

## Residual Risk

What this heuristic cannot see (each finding row also carries its own limit in the JSON output):

- html: ids are matched lexically; a label is the nearest preceding text chunk and can belong to a neighbour.
- js_span: functions are split on column-0 declarations; indented/minified code collapses to one span, so a card and an endpoint in the same span are linked without proof of data flow.
- js_ref: an id counts as referenced if it appears as a quoted string, `#id`, or under a dynamic-id prefix; ids built by concatenation from runtime data are invisible.
- chain: a render function with no fetch is linked to the endpoints of its callers (2 hops); data passed through globals, events or WebSocket frames is not followed and the card is reported UNTRACED.
- route: routes come from decorators plus include_router prefixes in main.py; routes added by loops, mounts or plugins are invisible, so NO_ROUTE can be a false positive for those.
- producer: producers are string constants, env defaults and calls found by AST within 2 hops; paths built at runtime are not seen, so NO_PRODUCER is limited to literal/default paths.
- writer: 'something writes it' means another repo file mentions the path/basename on a write-like line; a mention is not proof the writer runs or is enabled.
- silent: SILENT_DEFAULT is an AST pattern (except/missing-data branch returning 0/ok/healthy); a legitimate zero is indistinguishable from a masked failure without runtime evidence.
- hardcoded_route: a route is 'constant' only if its body has no call and no non-constant name; constants loaded from config files are not constant.
- live: freshness comes from timestamp-looking keys in the JSON; no timestamp means unknown freshness.

## Rollback Plan

Delete the script, test, CI manifest entry and this report. Nothing else is touched.

## Hint Feedback

No hints were consulted; the P2.3 sweep script supplied the layout and flag conventions.
