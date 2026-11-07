# Dashboard truth remediation, 2026-11-06

## Objective
Recovery item P4.2 (`.agents/plans/system-integrity-recovery/tracker.json`): no hardcoded or fake card values; a failed or missing source shows `--` with a reason, never a number. Findings come from the P2.4 sweep (`docs/harness-first/evidence/2026-11-06-sweep-dashboard.md`, worktree `p24-dashboard-sweep`). Bug fixes only: no new cards, routes or redesign.

## Workflow/Session IDs
Branch fix/dashboard-truth, worktree `.agents/delegation/worktrees/dash-truth`. Staged for review, not committed. Detection subject to use: `fix(dashboard): ...` (P4.2 `commit_match` is `fix\(dashboard\):`).

## Delegation Decision
Orchestrator: caller session. Implementer: Claude Sonnet 5.5 (Rule 17, balanced tier). The sweep script is not on main, so the regression test is a focused static check plus one behavioural check.

## Validation Evidence

- `scripts/testing/test-dashboard-no-false-values.py`: PASS on the new code; on the old code (assets, dashboard.html, backend stashed) it FAILS with 60 findings (every id below, both retired-lane references, both NO_ROUTE callers, the scheduler except branch).
- `scripts/governance/tier0.d/check-ci-test-coverage.sh`: PASS (761 tests: 611 declared, 150 exempt). Registered in `config/ci-checks.json` group `tests-dashboard` (workflow `test.yml#syntax`).
- `scripts/testing/run-test-group.py tests-dashboard`: 22/22 passed (includes the new test). `test-maeah-api-surface-contract.py` and `test-dashboard-routing-ratio.js` pass. `node --check assets/dashboard.js` clean.
- 16 other dashboard/orchestration tests that read these files (not in the group) fail identically on the unmodified tree (base=1, new=1 for each); none pinned a fake value. No existing test asserted any value changed here, so none was edited.
- Extension round: the test also fails on the tree as staged before the extension (exported with `git checkout-index` to a temp dir and run with `DASHBOARD_TRUTH_ROOT`, no `git stash`): 27 findings covering the four rag writes, `calibrateVal` and its floor/cap arithmetic, the `|| "98"` gauge fallbacks, the OPTIMAL defaults, the static objective and stream text, and the `|| 2.5/256/0.7` limits. The behavioural check was skipped in that run (backend deps not importable from the export) and passes on the real tree.
- Class-wide test (round 3): the test now also scans all of `assets/dashboard.js` for number-bearing fallbacks (`x || <n>`, `x ?? "<n>"`, `cond ? v : "<n>"`, literal `setText`/`fwRow`/`textContent` arguments) and every id the script writes in `dashboard.html` and `stream-card.html` for a hand-typed value. Result on the tree: 0 unallowlisted hits, 46 allowlisted. On commit 60df0e9db (exported with `git archive` to a temp dir and run with `DASHBOARD_TRUTH_ROOT`, no stash) it fails with 78 findings: 13 JS fallbacks and 65 HTML elements. Allowlist (each entry has its reason in the test): SVG width/height defaults 800/500/400, `|| 1` divisors, graph node radius `|| 3`, API label `"v1"`, window default `"7d"`, fail-closed severity `?? 2`, poll cadence, font size, CSS opacity and weight, CSS colour strings, `D3_LOADING` label, static MCP protocol labels, and five zero-branches that are reached only after an explicit measured/ok guard (`0 vulns`, `0 alerts`, `0 Pending`, empty-list rows, agent-pool `0`).
- Sweep (`scripts/governance/sweep-dashboard.py` from the `feat/sweep-dashboard` worktree, static, `--repo` pointing at each tree): HARDCODED 33 (22 high, 11 medium) on the merge base `e46253bdb`, 0 on 60df0e9db, 0 on this tree; `--fail-on HARDCODED` exits 0. Other classes: NO_ROUTE 2 -> 0, RETIRED_REF 6 -> 0, SILENT_DEFAULT 6 -> 2 (the two left are `proxy_traces_summary` and `get_firewall_audit_log`, out of scope). NO_FETCH rose 3 -> 10: seven ids now honestly read `--` with no script writing them (`execGovernanceScore`, `histCurGates`, `secHeroGates`, `opsHeroServices`, `fleetHeroConsensus`, `metric-tokens`, `metric-latency`; plus the three pre-existing); they need a real producer, not a literal. FAKE_FALLBACK stays at the one `_stub_catalog` finding, which is now labelled `available: false` (the helper was renamed `_registry_snapshot_body` so it counts once).
- Not run (instructed): tier0, full run-ci-checks. Not verified live: needs a dashboard restart (owner action).

### Decision table (value before -> after, source)

| Id / item | Before | After | Source |
|---|---|---|---|
| healthScore, kpiHealthScore, execSwarmHealth, health gauge (failure, null score) | `98` / `98%`, green gauge | `--`, title with reason, gauge 0 | `/api/metrics/health-score` `score`; unavailable if missing |
| vCacheHit | `92%` on missing | `--` + title | hotspots `cache.hit_pct` |
| vLatP95, histCurLat | `<1ms`, `18 ms` | `--` + title | hotspots `route_latency.backend_valid_p95_ms` |
| histCurCtx, intelHeroPrecision, context gauge | `85%` (and cache hit rate mislabelled as precision) | `--` + title | `/api/metrics` has no precision field; not measured |
| vLogicDiscipline | `100%` | `--` | analytics `logic_discipline_rate` |
| kpiUptime | `22.5h` | `--` | `/api/metrics/system` `uptime` |
| kpiLocalPct, execLocalRatio, sovereignty gauge, intelHeroSovereignty | default `94%` / `100%` | `--` | `/api/metrics` `llm_routing_local_pct` |
| kpiCacheHit | default `92%` | `--` | `embedding_cache_hit_rate_pct` |
| kpiEval | default `100%` | `--` | `eval_latest_pct` |
| kpiHintPct | default `100%` | `--` | `hint_adoption_pct` |
| vStack | `0%` | `--` | `eval_latest_pct` |
| vIntentUnknown | `0%` | `--` | query traces |
| kpiTokSaved | `2.4k` / default 2400 | `--` | routing analytics `query_ok_n` |
| kpiVectors, intelHeroVectors | `100,680` / `100,781` | `--` | `/api/ai/metrics` `knowledge_base.total_points` |
| kpiQdrant, kpiCoord | default `ONLINE` | `--` | `/api/ai/metrics` service status |
| kpiPgLat, kpiRedisLat | `<1ms` | `--` | `/api/ai/metrics` `database_metrics` |
| healthScore pending branch | `0` | `--` | layer health run pending |
| `/api/metrics` producer | `100.0` local, `100.0` hint, `0.0` eval/cache for unmeasured | `null` | `aistack.py get_aistack_metrics` (producer fix) |
| execGovernanceScore, histCurGates, secHeroGates, secHeroBadge | `53/53 ...` | `--` / "GATES NOT MEASURED", title "Not measured yet" | no gate-result source exists in a route the page fetches |
| opsHeroServices, opsHeroBadge | `16 / 17`, `16/17 SERVICES ONLINE` | `--` / "SERVICES NOT MEASURED" | not measured (no agreed service-count definition); not invented |
| spiderHeroLayers, spiderHeroBadge | `8 / 8 LAYERS` | wired: `N / M LAYERS` | `/api/health/layered` `layers` (already fetched by `loadOSI`); `--` until the layer run exists |
| fleetHeroConsensus | `NOMINAL` | `--` | not measured |
| metric-tokens, metric-latency (stream-card) | `3,420`, `1.6ms` | `--` | not measured |
| decideEngineStatus, decidePsiDrift, decideCalibrationStatus | `Active (T0/T1)`, `0.002 (Stable)`, `Optimal` | `--` | no route reports these; the old `GET /api/status` does not exist; fetch removed |
| cockpitLaneBadge | `ORCHESTRATOR: ANTIGRAVITY` | `PHASE: --`, filled from collab-state `resume.phase` (existing JS) | data |
| cockpitThoughtLine | `[antigravity] Mounting ...` | "Waiting for the live collaboration pulse..." | collab-state `pulse[0]` (existing JS) |
| dispatch option, em-tag | `Google Antigravity / Gemini 3.8`, `gemini / antigravity` | `Gemini headless CLI (delegate-to-gemini)`, `gemini (headless CLI)` | lane retirement |
| stream-card lane-tag; delegation mermaid | `antigravity`; `antigravity CLI` | `--`; `delegate-to-gemini headless CLI` | lane retirement |
| ragHarmfulness, ragRerankMrr, ragCompRecall, ragHandoffParity | `0.0%`, `0.84`, `91.2%`, `100%` written under a "Zero Blank Policy" comment; the ids exist in no HTML, so nothing rendered them | writes and comment removed | not measured; no source |
| ragSampleCount (HTML `142`, JS `100`), evalSamples (`100`), evalRunCount (`3`) | invented counts | `--` unless `/api/eval/trend` reports them | `ragas_metrics.sample_count`, `count` |
| RAGAS answer relevance, context precision, faithfulness (`loadRagQuality`) | `calibrateVal` lifted low scores to a 0.72-0.98 band; null-but-not-empty read `0.0%` | raw measured value, `--` if absent; zero measured shows `0.0%` | `/api/eval/trend` `ragas_metrics.*_avg` (faithfulness is ~0.6 per backlog and is now shown as such) |
| raw telemetry `distilled_vitals` | fallbacks `"98"`, `"94%"`, `"44.5°C"`, `"95%"` | `null` when the gauge has no reading; otherwise the gauge text as displayed now | live gauges (not a stored snapshot, so no age label applies) |
| cockpitHomeostasisBadge (HTML, JS default, resume handler) | `HOMEOSTASIS: OPTIMAL`, `state \|\| "OPTIMAL"` | `HOMEOSTASIS: --` until `/api/affective/state` returns a state | affective state |
| cockpitActiveObjective | "Executing SOTA Command Center Dashboard Revamp ..." | `--` until collab-state `resume.current_objective` | collab-state (existing JS) |
| cockpitStreamState | `● STREAMING ACTIVE` (green, static) | `● STREAM: --` | not measured |
| session safety row (`threshold_mb \|\| 2.5`), Hot Redis (`hot_max_mb \|\| 256`), Pass Rate (`pass_rate \|\| 0`, `target \|\| 0.7`) | invented limit/target, missing pass rate shown `0%` | limit/target omitted, pass rate `--` when absent | `agent_safety.session_safety`, context lifecycle status, harness scorecard |
| CPU temperature gauge, histCurTemp, opsHeroTemp (`loadSystem`) | `tempRaw \|\| 44.5` drew `44.5°C` and badge OPTIMAL when unmeasured; `\|\|` also turned a real 0 into the fallback | `--` + title, gauge 0, badge UNAVAILABLE; a measured value (including 0) is shown | `/api/metrics/system` `cpu.temperature` |
| histCurMem | `12.8G` when `mem.used` missing | percentage only | `/api/metrics/system` `memory` |
| vOpsDay, histCurOps on routing-analytics null or reject; HTML `142`, `142 ops` | kept the HTML literals | `--` + title | `/api/insights/routing/analytics` `query_ok_n` |
| 63 HTML elements the script writes (kpi*, v*, hist*, gauge*Val, cpuTemp, memUsed/Total, dsk*, opsHeroRam/Disk, intelHero*, execLocalRatio, svcCount, anomaly-count, fleet-count, gpuName, piActiveAgentModel, ...) | hand-typed readings (`12%`, `48%`, `44.5°C`, `100,781`, `claude-fable-5`, ...) that a failed fetch would leave on screen | `--` | each id's existing fetch; left as `--` if it fails |
| vNet, vConnections, vLoad5, vLoad15, vBackendN, Unprocessed, Threshold, Max Wait, CPU/GPU temp rows, Embed Busy | `0MB`, `0`, `0.00`, `0`, `0 MB`, `0.4`, `0s`, `62.0°C`, `58.0°C`, `0.00` | `--` | respective fields |
| approvals badge, vulnerability badge, health-alerts badge, agent-pool card (`runtime-summary` null) | `0 Pending`, `0 vulns`, `0 alerts`, `0` / "no pool data" on a failed or unmeasured source | `unavailable` / `--` | respective routes |
| quickApproveUI (button) | POST to a route that does not exist; UI then claimed "Action Approved" / "Approval Recorded" | no request; UI says nothing was approved, use the Approval Inbox; button greyed with title | real approvals need `/api/approvals/{id}/approve` with a WebAuthn assertion; no one-click route exists |
| `GET /api/scheduler/queue` on read failure | `available: true, depth: 0` | `available: false, depth: null, error: <class>` | `aistack.py get_scheduler_queue`; UI shows unavailable |
| `GET /api/drops/status` on failure | counts 0, `daemon_active: false` | `available: false`, counts `null`, `errors: {field: class}`, `daemon_active: null` | `aistack.py get_drops_status`; UI shows unavailable |
| `GET /api/stats/learning` | zeroed stand-in (paused=false) when coordinator down; `_count_text_records` 0 on unreadable file | HTTP 503; unreadable file counts `null` | consumers already render unavailable on a null response |
| `GET /api/models` stub | `_stub_catalog()` indistinguishable | adds `available: false, stub: true, reason`, `source` (`registry_file` or `stub`); UI badge "stub" and a warning row | callers: `loadModels` only (plus CLI clients reading the JSON) |

## Residual Risk

- Backend changes (`aistack.py`, `models.py`) take effect only after a dashboard backend restart, which is the owner's action. Frontend assets are served from disk and need only a reload.
- With the producer change, `/api/metrics` returns `null` for unmeasured percentages; `scripts/testing/test-dashboard-visual.sh` reads `llm_routing_local_pct` with `.get(..., 'null')` and tolerates it. Other API clients of `/api/metrics` were not audited.
- `/api/scheduler/queue` will read unavailable on a host with no `scheduler-state.json` (the live sweep saw exactly that), which is now the honest state.
- Zero-count defaults (`x ?? 0`, `|| 0` on counts, several hundred across `dashboard.js`) are a known larger class that this change does not attempt: a missing count renders `0`. The test does not match them; each needs its own source check. This is the main thing still able to show a false value.
- Not fixed, still unmeasured or static: the history table columns next to `histCurGates` (`53 / 53 (100%)`, `51 / 52 (98.1%)`) are hand-typed comparison rows; the `histCur*` neighbours and any other static table cells; `kpiTokSaved` is labelled tokens saved but shows a query count; the sweep's UNTRACED cards and remaining medium items were not individually audited. `get_latest_remediation`, `adk`, `workflow_graph` NO_PRODUCER routes, unmounted route modules, and `/api/aistack/advanced/runtime-summary` timing out at 8 s are out of scope and unchanged.

## Rollback Plan
Revert the commit; no data, config or Nix change besides one `config/ci-checks.json` entry.

## Hint Feedback
No hints were consulted.
