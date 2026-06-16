---
doc_type: prd
id: phase184A-delegation-fix-prd
title: "Phase 184A — Delegation Infrastructure Fix: Startup 500s, Feedback Loop, Success Rate Recovery"
status: draft
owner: architect
phase: "Phase 184A"
priority: P0-critical
evidence_required: ai_coordinator_delegate 24h success rate ≥ 80%; delegation feedback events have non-null event_type; aq-qa delegate check passes
---

# Phase 184A — Delegation Infrastructure Fix

## 1. Problem Statement

The `ai_coordinator_delegate` tool — the primary mechanism for all Claude-to-local-model and Claude-to-remote-agent work — is succeeding at 4.5% over a 24-hour window. This represents a near-total delegation infrastructure failure.

**Quantified evidence:**

| Metric | Observed Value | Target |
|--------|---------------|--------|
| `ai_coordinator_delegate` 24h success rate | 4.5% | ≥ 80% |
| Coordinator startup 500 errors (24h) | 23 events (52% of all failures) | 0 |
| Other failures | ~18 events (39%) | — |
| Timeout failures | ~2 events (5%) | — |
| Adjusted success rate (excl. startup errors) | 9.5% | ≥ 80% |
| `delegation_feedback.py` events logged (24h) | 135 | — |
| Feedback events with non-null `event_type` | 0 (0%) | 100% |
| `qa_check` tool 24h success rate | ~5% | ≥ 80% |

**Secondary impact:** 135 delegation feedback events are stored in `~/.local/share/nixos-ai-stack/hybrid/telemetry/delegation-feedback.jsonl` but every `event_type` field is null. The routing policy (`RoutingConfig`, `PerformanceWindow`) never reads this file — feedback is write-only. Delegation failures do not drive adaptive fallback, threshold nudge, or PRSI action generation.

**Tertiary impact:** `qa_check` failures cascade from the same coordinator 500s. The PRSI orchestrator (`scripts/automation/prsi-orchestrator.py`) and the `PerformanceWindow` nudge logic (`core/config.py:790-820`) both operate blind.

---

## 2. Root Cause Analysis

### 2A. Startup 500s — Coordinator Not Ready When First Request Arrives

**Mechanism:** The coordinator startup sequence (`server.py:initialize_server()`) is long and serial:

1. `_enforce_startup_env()` — env/secret file validation
2. `_preflight_check()` — TCP probes for Redis, Qdrant, PostgreSQL (5s timeout each, sequential)
3. `QdrantClient` init (network call)
4. Multiple `httpx.AsyncClient` inits
5. `EmbeddingCache.initialize()` — Redis flush + model fingerprint check
6. `embedder.init()`, `model_probe.probe()`, `SemanticCache`, `SearchRouter`, `route_handler.init()`, `memory_manager.init()`, `harness_eval.init()`, `mcp_handlers.init()`, `http_server_impl.init()` — ~12 wiring calls

**The race:** systemd's `Restart=always` with `RestartSec=5s` means the process restarts every 5 seconds on crash. The ai-aidb service (a `hybridDeps` dependency at `mcp-servers.nix:443`) starts its own initialization concurrently. When AIDB or PostgreSQL is not yet fully ready, `_preflight_check()` at `server.py:554` raises `RuntimeError`, the process exits, and systemd counts it as "started" before the socket opens. Callers that hit the port during this 5-30 second initialization window get a connection refused or a half-formed HTTP 500 from the aiohttp app before handlers are registered.

**Evidence path:**
- `mcp-servers.nix:1034` — `requires = hybridDeps` — coordinator requires AIDB, but AIDB itself requires `ai-pgvector-bootstrap.service` and Qdrant (lines 432-440). A cold boot can result in dependency satisfaction without full AIDB readiness.
- `server.py:553-554` — `_enforce_startup_env()` and `_preflight_check()` run inside `initialize_server()`, which is called from `main()` as a coroutine. Any exception before `await http_server.run_http_mode(port=port)` at line 1057 means the port never opens — callers get `ECONNREFUSED`, not HTTP 500. **However**, the `http_server_impl.py:run_http_mode()` may register the aiohttp app and bind the port before `initialize_server()` completes wiring (if routing is different). This needs verification during implementation.
- `server.py:586` — `await embedding_cache.initialize(flush_on_model_change=True)` — Redis cache flush with network I/O. If Redis is slow, this blocks the whole init chain.
- `server.py:598-614` — `model_probe.probe()` — calls llama.cpp `/v1/models` or `/props`. If llama.cpp is loading a 22GB model (boot-time GGUF load takes 30-90s), this probe call returns an error and init continues with safe defaults. But the total init time grows.

**Most likely 500 surface:** the aiohttp `run_http_mode` binds the TCP port early (before `initialize_server` completes), and inbound requests hit handlers whose `_*_ref` lambdas still resolve to `None` (e.g., `_semantic_cache = None`, `qdrant_client = None`). Handler code dereferencing `None` raises `AttributeError` → aiohttp catches it → 500 response. This is the "infra startup 500" class.

**Confirmation target:** `journalctl -u ai-hybrid-coordinator --since "24h ago" | grep -E "preflight|initialized|error"` will show whether failures correlate with service restarts or with late dependency readiness.

### 2B. Null `event_type` in delegation-feedback.jsonl

**Root cause — precise dict key mismatch:**

The `record_delegation_feedback()` function at `workflow/delegation_feedback.py:393-428` builds the `payload` dict. Inspecting lines 400-428 of that file, the payload keys are:

```
timestamp, task_excerpt, requested_profile, selected_profile, selected_runtime_id,
final_profile, final_runtime_id, requesting_agent, requester_role,
failure_stage, http_status, outcome, failure_class, failure_classes,
fallback_applied, handoff_requested, response_preview, salvage, improvement_actions
```

**The key `event_type` is not in this dict.** The `record_delegation_feedback()` function signature does not accept an `event_type` parameter, and the payload construction block does not include it.

By contrast, `server.py:record_telemetry_event()` (lines 324-344) does write both `"event"` and `"event_type"` into its payloads. Those go to `hybrid-events.jsonl`, not `delegation-feedback.jsonl`.

The 135 events with null `event_type` are being read by a consumer (aq-report or dashboard) that expects a field `event_type` in the delegation feedback JSONL — but `record_delegation_feedback` never writes it.

**Call sites:** `extensions/ai_coordinator_handlers.py:2218` and `2233` — both calls to `record_delegation_feedback()` pass no `event_type` argument and cannot, because the function's keyword-only signature doesn't accept one.

**Consumer gap:** There is no code path in `routing_config`, `PerformanceWindow`, `prsi-orchestrator.py`, or any adaptation loop that reads `delegation-feedback.jsonl` and updates thresholds or generates PRSI actions. The feedback log is strictly write-only. Its data never closes the loop.

### 2C. Cascading qa_check Failures

`qa_check` (exposed as a coordinator tool) calls coordinator-internal HTTP endpoints. When the coordinator is in a crash-restart loop, `qa_check` calls hit the same 500 surface and fail for the same reason. This is a dependent failure, not an independent root cause.

---

## 3. Goals & Success Criteria

### Primary Goals

| Goal | Measurable Target | Measurement Method |
|------|------------------|-------------------|
| G1: Eliminate startup 500s | 0 startup 500 events in 24h post-fix | aq-qa delegate check; `delegation_startup_error` telemetry count |
| G2: Raise delegation success rate | ≥ 80% in 24h rolling window | aq-report delegation section; `delegation-feedback.jsonl` outcome field |
| G3: Non-null event_type in feedback | 100% of new feedback events have non-null `event_type` | JSONL field audit |
| G4: Feedback loop closure | PerformanceWindow reads feedback and nudges threshold within 1h of sufficient samples | Log line `performance_window_nudge` appears in coordinator logs |
| G5: qa_check recovery | qa_check success rate ≥ 80% | aq-qa 0 --json `delegate` section |

### aq-qa Test Assertions (New Checks to Add)

```
Check 0.12.1 [delegate-startup-500-rate]:  delegation_startup_error count (24h) == 0     PASS/FAIL
Check 0.12.2 [delegate-success-rate-24h]:  outcome=success rate (24h) >= 0.80            PASS/FAIL
Check 0.12.3 [feedback-event-type-null]:   null event_type fraction in latest 50 events == 0  PASS/FAIL
Check 0.12.4 [feedback-loop-nudge-fired]:  performance_window_nudge log line exists in last 24h PASS/WARN
Check 0.12.5 [coordinator-ready-gate]:     coordinator /health returns 200 within 30s of systemd start  PASS/FAIL
```

---

## 4. Scope

### In Scope

- Fix coordinator startup race: add a readiness gate before aiohttp port binding so handlers don't receive requests until `initialize_server()` has completed wiring all globals.
- Add `event_type` field to `record_delegation_feedback()` payload — both the function signature and the call sites in `extensions/ai_coordinator_handlers.py`.
- Implement `delegation-feedback.jsonl` consumer in `PerformanceWindow` or a new `DelegationFeedbackConsumer` class that reads the file, computes per-profile success rates, and feeds results into routing policy.
- Emit `delegation_startup_error` telemetry event when startup 500 is detected by the caller side.
- Add new aq-qa checks (0.12.1–0.12.5).
- Update dashboard with delegation-specific panels (see Section 8).

### Out of Scope

- Rewriting the coordinator startup sequence in Rust or splitting it into microservices.
- Changing the `hybridDeps` dependency chain in `mcp-servers.nix` (structural NixOS change; out of scope for this phase — see Risks).
- Fixing the underlying cause of "39% other failures" — those require separate investigation with the new telemetry in place.
- AppArmor rule changes.
- Changes to `switchboard.py` or llama.cpp launch flags.

---

## 5. Technical Approach

### Fix 5A: Coordinator Startup Readiness Gate

**Problem:** aiohttp TCP binding and `initialize_server()` wiring may race. If `run_http_mode()` calls `web.AppRunner.setup()` and `web.TCPSite.start()` before `http_server.init()` completes (or `server.py:initialize_server()` calls `http_server.run_http_mode()` after init), there is a window where the port accepts connections but handlers dereference None globals.

**Fix approach:**

1. In `server.py:main()` (line 1047), ensure `initialize_server()` fully completes before `http_server.run_http_mode()` is called. The current structure (`await initialize_server()` then `await http_server.run_http_mode()`) looks correct — but verify that `http_server_impl.init()` (called deep in `initialize_server`) is the last call before the function returns, and that none of the `asyncio.create_task()` calls inside `initialize_server` (e.g., `_run_semantic_warmup` at line 964) block or throw synchronously.

2. Add a `/readyz` endpoint (distinct from `/health`) that returns 503 until `initialize_server()` sets a global `_COORDINATOR_READY = True` flag. Wire systemd `ExecStartPost` or a `post-start` probe to poll `/readyz` before marking the service active.

3. In `extensions/ai_coordinator_handlers.py:handle_ai_coordinator_delegate()`, add a guard at the top:
   ```python
   if not _coordinator_ready():
       return web.json_response(
           {"error": "coordinator_not_ready", "retry_after_seconds": 10},
           status=503
       )
   ```
   This converts silent 500s into explicit 503s with `Retry-After` semantics, which callers can handle gracefully.

4. In `nix/modules/services/mcp-servers.nix`, extend `hybridDeps` to wait for `ai-aidb.service` readiness (not just activation). Consider using `ExecStartPost=/bin/sh -c 'until curl -sf http://127.0.0.1:${AIDB_PORT}/health; do sleep 2; done'` on the AIDB service, or use `systemd.services.ai-aidb.serviceConfig.Type = "notify"` if AIDB supports `sd_notify`.

**Files changed:**
- `ai-stack/mcp-servers/hybrid-coordinator/server.py` — add `_COORDINATOR_READY` flag, set it at end of `initialize_server()`
- `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py` — add `/readyz` endpoint; add not-ready guard in `handle_ai_coordinator_delegate`
- `nix/modules/services/mcp-servers.nix` — optionally extend `hybridDeps` with AIDB health probe (rebuild required)

**Rebuild required:** YES for NixOS service changes. The Python-only guard and `/readyz` endpoint can be tested without rebuild by restarting the coordinator service directly.

### Fix 5B: Add `event_type` to delegation feedback payload

**Problem:** `record_delegation_feedback()` in `workflow/delegation_feedback.py:393-428` does not write `event_type`. Consumers that parse the JSONL expecting this field get null.

**Fix — exact location:**

In `workflow/delegation_feedback.py`, function `record_delegation_feedback()` (line 393), add `event_type` as a keyword argument with a default, and include it in the `payload` dict:

```python
def record_delegation_feedback(
    *,
    task: str,
    requested_profile: str,
    selected_profile: str,
    selected_runtime_id: str,
    classification: Dict[str, Any],
    final_profile: str,
    final_runtime_id: str,
    requesting_agent: str = "human",
    requester_role: str = "orchestrator",
    event_type: str = "delegation_outcome",   # ADD THIS
) -> None:
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,              # ADD THIS
        "task_excerpt": task[:280],
        ...
    }
```

**Call sites to update** (`extensions/ai_coordinator_handlers.py`, lines 2218 and 2233):

- Line 2218 call (initial classification): pass `event_type="delegation_initial"` to distinguish first-attempt records from fallback records.
- Line 2233 call (fallback/failure path): pass `event_type="delegation_fallback"`.

This gives consumers two distinct event classes to aggregate:
- `delegation_initial` — overall success/failure rate per profile
- `delegation_fallback` — fallback activation frequency

**Files changed:**
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback.py` — function signature + payload dict
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` — two call sites

**Rebuild required:** YES (Python service file; must restart coordinator after nixos-rebuild or direct service restart).

### Fix 5C: Feedback Loop Consumer — Close the Write/Read Gap

**Problem:** `delegation-feedback.jsonl` is written by 135+ events but never read by any routing or adaptation logic.

**Fix:** Add a `DelegationFeedbackConsumer` class (new file: `workflow/delegation_feedback_consumer.py`) that:

1. Reads `delegation-feedback.jsonl` from the path returned by `delegation_feedback_log_path()`.
2. Aggregates per-`final_profile` success rates over a configurable window (default: 24h, matching `PerformanceWindow.WINDOW_DAYS` logic).
3. Exposes `get_profile_success_rates() -> Dict[str, float]` and `get_overall_success_rate() -> float`.
4. Feeds the overall rate into `PerformanceWindow.maybe_nudge(routing_config)` — currently the `PerformanceWindow` at `core/config.py:790` only reads its own `performance-window.json` bucket data, which is populated by calls to `performance_window.record(bucket, success)`. Those calls happen in the coordinator's query routing path — NOT in the delegation path. Delegation outcomes never call `performance_window.record()`.

**Two integration points:**

1. In `extensions/ai_coordinator_handlers.py`, after `record_delegation_feedback()`, call:
   ```python
   performance_window.record("delegation", not final_classification.get("is_failure"))
   ```
   This feeds delegation outcomes into the existing nudge mechanism immediately.

2. Schedule `DelegationFeedbackConsumer` as a periodic task (every 15 minutes) via the existing APScheduler instance (`http_server_impl.py:2650`) to compute profile-level stats and log them as a `delegation_feedback_consumed` telemetry event.

**Files changed:**
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback_consumer.py` — new file
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` — add `performance_window.record()` call after `record_delegation_feedback()`
- `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py` — register periodic consumer task

**Rebuild required:** YES.

---

## 6. Implementation Plan

Steps are ordered to minimize risk. Steps marked (no-rebuild) can be verified immediately by restarting the coordinator service. Steps marked (rebuild) require `nixos-rebuild switch`.

### Step 1: Diagnose startup race precisely (no-rebuild, ~30 min)

Before writing code, run:
```bash
journalctl -u ai-hybrid-coordinator --since "1 hour ago" --no-pager | grep -E "(preflight|initialized|error|500|startup)" | head -50
journalctl -u ai-aidb --since "1 hour ago" --no-pager | grep -E "(started|ready|error)" | tail -20
systemctl show ai-hybrid-coordinator --property=ActiveState,SubState,ExecMainStatus
```

Cross-reference timestamps: does the coordinator log `preflight_check status=passed` and `✓ Hybrid Agent Coordinator initialized successfully` before the first 500 hits? If the 500s appear AFTER `initialized successfully`, the race is in the handler code (None globals). If BEFORE, the race is in port binding.

**Output:** confirm exact 500 surface before writing fix. Record finding in `.agent/collaboration/PULSE.log`.

### Step 2: Add `event_type` to `record_delegation_feedback` (no-rebuild, ~20 min)

File: `ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback.py`
- Add `event_type: str = "delegation_outcome"` parameter
- Add `"event_type": event_type` to `payload` dict (after `"timestamp"`)

File: `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`
- Line 2218 call: add `event_type="delegation_initial"`
- Line 2233 call: add `event_type="delegation_fallback"`

Validate immediately (no rebuild needed — service can be restarted):
```bash
systemctl restart ai-hybrid-coordinator
sleep 10
# Trigger a delegation
curl -sf -H "Authorization: Bearer $(cat /run/secrets/hybrid-api-key)" \
  http://127.0.0.1:8003/ai/coordinate/delegate \
  -d '{"task":"test","profile":"local"}' | python3 -m json.tool
# Check feedback log
tail -5 ~/.local/share/nixos-ai-stack/hybrid/telemetry/delegation-feedback.jsonl | \
  python3 -c "import sys,json; [print(json.loads(l).get('event_type')) for l in sys.stdin]"
```

### Step 3: Add `performance_window.record()` call for delegation outcomes (no-rebuild, ~15 min)

File: `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`
- After the `record_delegation_feedback()` call at line ~2228, add:
  ```python
  performance_window.record(
      "delegation",
      not final_classification.get("is_failure")
  )
  ```
  Import `performance_window` from `config` at the top of the file (already imported in `server.py`; verify import chain in `extensions/ai_coordinator_handlers.py`).

### Step 4: Add coordinator readiness gate (no-rebuild for Python, rebuild for NixOS, ~45 min)

File: `ai-stack/mcp-servers/hybrid-coordinator/server.py`
- Add module-level `_COORDINATOR_READY: bool = False`
- At end of `initialize_server()` (after line 1039): `_COORDINATOR_READY = True`
- Expose `def coordinator_ready() -> bool: return _COORDINATOR_READY`

File: `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py`
- Add `/readyz` endpoint: returns `{"status": "ready"}` (200) when coordinator ready, `{"status": "initializing"}` (503) otherwise
- In `handle_ai_coordinator_delegate` (proxied via `ai_coordinator_handlers.py`): add not-ready guard returning 503

File: `nix/modules/services/mcp-servers.nix` (rebuild required)
- Add `ExecStartPost` health probe: poll `/readyz` up to 60s before service transitions to `active`

### Step 5: Add new aq-qa delegation checks (no-rebuild, ~30 min)

File: `scripts/ai/aq-qa` (or the checks module it calls)
- Add checks 0.12.1–0.12.5 per Section 3
- Check 0.12.2 reads `delegation-feedback.jsonl`, computes outcome=success fraction for last 24h
- Check 0.12.3 reads last 50 events, counts null event_type

### Step 6: Add DelegationFeedbackConsumer and periodic scheduler task (~45 min, rebuild required)

File: `ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback_consumer.py` (new)
File: `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py` — register 15-min APScheduler job

### Step 7: Tier 0 validation gate and commit

```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
git add <specific files>
git commit -m "fix(delegation): startup readiness gate, event_type in feedback, loop closure"
```

---

## 7. Monitoring & Observability

### New Telemetry Events to Emit

These events are written via `record_telemetry_event()` in `server.py:324` to `hybrid-events.jsonl`.

| Event Name | When Emitted | Key Fields |
|------------|-------------|-----------|
| `delegation_startup_error` | When a delegate request hits a not-ready coordinator | `request_id`, `coordinator_state`, `retry_after_s` |
| `delegation_feedback_consumed` | After `DelegationFeedbackConsumer` aggregation run | `profile_success_rates: Dict[str, float]`, `overall_success_rate`, `window_hours`, `events_read` |
| `delegation_ready_gate_passed` | When coordinator transitions from initializing → ready | `init_duration_seconds`, `dependency_probe_ms` |
| `delegation_ready_gate_failed` | When init fails and service will restart | `failure_reason`, `failed_dependency` |
| `performance_window_delegation_nudge` | After `performance_window.record("delegation", ...)` triggers a threshold change | `direction`, `old_threshold`, `new_threshold`, `delegation_success_rate`, `samples` |

### New Metric Keys (Prometheus / aq-report)

| Key | Type | Description |
|-----|------|-------------|
| `delegation_success_rate_24h` | Gauge | Rolling 24h delegate success rate |
| `delegation_startup_errors_total` | Counter | Cumulative startup 500/503 events |
| `delegation_feedback_null_event_type_total` | Counter | Historical null event_type events (resets to 0 post-fix) |
| `delegation_feedback_consumed_lag_minutes` | Gauge | Age of last `delegation_feedback_consumed` event |

### Alert Thresholds

| Alert | Condition | Severity |
|-------|-----------|---------|
| DelegationSuccessRateCritical | `delegation_success_rate_24h` < 0.50 | P0 — page |
| DelegationSuccessRateDegraded | `delegation_success_rate_24h` < 0.80 | P1 — warn |
| StartupErrorsActive | `delegation_startup_errors_total` increases > 0 in last 1h | P0 — page |
| FeedbackLoopStale | `delegation_feedback_consumed_lag_minutes` > 30 | P2 — warn |

---

## 8. Dashboard Visualizations

All panels feed from `hybrid-events.jsonl` (telemetry event stream) and `delegation-feedback.jsonl` (feedback stream), read via the existing dashboard backend's telemetry API.

### Panel 1: Delegation Success Rate — 24h Rolling Time Series

- **Panel name:** `Delegation Success Rate (24h rolling)`
- **Chart type:** Time series (line)
- **Data source:** `delegation-feedback.jsonl` aggregated by hour; field `outcome == "success"` / total events per hour
- **Refresh rate:** 5 minutes
- **Alert threshold:** Red line at 0.50; orange at 0.80; green above 0.80
- **Y-axis:** 0–1.0 (percentage rate)
- **X-axis:** Last 24h, 1h buckets

### Panel 2: Startup Error Histogram

- **Panel name:** `Coordinator Startup Errors (24h)`
- **Chart type:** Bar histogram (count per hour)
- **Data source:** `hybrid-events.jsonl`, filter `event_type == "delegation_startup_error"` OR `event_type == "delegation_ready_gate_failed"`
- **Refresh rate:** 2 minutes
- **Alert threshold:** Any bar > 0 shown in red
- **Annotation:** Overlay `delegation_ready_gate_passed` events as green vertical markers

### Panel 3: Feedback Loop Closure Rate

- **Panel name:** `Delegation Feedback Loop Closure`
- **Chart type:** Gauge (0–100%)
- **Data source:** Latest `delegation_feedback_consumed` event, field `overall_success_rate`; staleness indicator from `delegation_feedback_consumed_lag_minutes`
- **Refresh rate:** 5 minutes
- **Alert threshold:** Red < 50%, orange 50–79%, green ≥ 80%
- **Secondary display:** "Last consumed N minutes ago" text field

### Panel 4: Per-Tool / Per-Profile Success Rate Table

- **Panel name:** `Delegation Success by Profile (24h)`
- **Chart type:** Table
- **Data source:** `delegation-feedback.jsonl`, group by `final_profile`, count `outcome == "success"` / total
- **Columns:** `profile`, `total_attempts`, `success_count`, `success_rate_pct`, `primary_failure_class`
- **Refresh rate:** 10 minutes
- **Conditional formatting:** success_rate_pct < 50% → red cell; 50–79% → orange; ≥ 80% → green

### Panel 5: `event_type` Field Coverage (Audit Panel)

- **Panel name:** `Feedback Event Type Coverage`
- **Chart type:** Gauge (0–100%)
- **Data source:** Last 100 `delegation-feedback.jsonl` entries, `event_type != null` fraction
- **Refresh rate:** 10 minutes
- **Purpose:** Regression detector — immediately shows if `event_type` drops to null again
- **Alert threshold:** < 100% → orange warning

---

## 9. Validation Plan

### Pre-Implementation Baseline

Before making any changes, capture:
```bash
# Baseline feedback log event_type coverage
python3 -c "
import json
from pathlib import Path
log = Path.home() / '.local/share/nixos-ai-stack/hybrid/telemetry/delegation-feedback.jsonl'
lines = log.read_text().strip().splitlines()[-50:]
events = [json.loads(l) for l in lines if l]
null_count = sum(1 for e in events if e.get('event_type') is None)
print(f'Last 50 events: {null_count} null event_type ({100*null_count//len(events)}%)')
"

# Baseline success rate
python3 -c "
import json, datetime
from pathlib import Path
log = Path.home() / '.local/share/nixos-ai-stack/hybrid/telemetry/delegation-feedback.jsonl'
cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).isoformat()
events = [json.loads(l) for l in log.read_text().strip().splitlines() if l]
recent = [e for e in events if e.get('timestamp','') > cutoff]
success = sum(1 for e in recent if e.get('outcome') == 'success')
print(f'24h: {len(recent)} events, {success} success, rate={100*success//max(len(recent),1)}%')
"
```

### Post-Step-2 Validation (event_type fix)

After restarting coordinator with Step 2 changes:
```bash
# Trigger 3 delegation calls
for i in 1 2 3; do
  curl -sf -H "Authorization: Bearer $(cat /run/secrets/hybrid-api-key)" \
    http://127.0.0.1:8003/ai/coordinate/delegate \
    -d '{"task":"echo test '$i'","profile":"local"}' -o /dev/null
done
sleep 5
# Verify event_type populated
tail -6 ~/.local/share/nixos-ai-stack/hybrid/telemetry/delegation-feedback.jsonl | \
  python3 -c "import sys,json; [print(json.loads(l).get('event_type','NULL')) for l in sys.stdin]"
# Expected: delegation_initial, delegation_initial, delegation_initial (or delegation_fallback on failure)
```

Expected pass criteria: all 3 events show non-null `event_type`.

### Post-Step-4 Validation (readiness gate)

```bash
# Force-restart coordinator and immediately hit the delegate endpoint
systemctl restart ai-hybrid-coordinator &
sleep 1
response=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $(cat /run/secrets/hybrid-api-key)" \
  http://127.0.0.1:8003/ai/coordinate/delegate \
  -d '{"task":"test","profile":"local"}')
echo "Response during init: $response"
# Expected: 503 (not 500, not connection refused)

# Wait for ready
until curl -sf http://127.0.0.1:8003/readyz; do sleep 2; done
echo "Coordinator ready"
# Trigger real request
curl -sf -H "Authorization: Bearer $(cat /run/secrets/hybrid-api-key)" \
  http://127.0.0.1:8003/ai/coordinate/delegate \
  -d '{"task":"echo hello","profile":"local"}' | python3 -m json.tool
# Expected: 200 with response body
```

### Post-Phase aq-qa Assertions

Run `aq-qa 0 --json` and verify:
```
0.12.1 delegate-startup-500-rate:  PASS (count=0)
0.12.2 delegate-success-rate-24h:  PASS (rate >= 0.80)
0.12.3 feedback-event-type-null:   PASS (null_fraction=0.00)
0.12.4 feedback-loop-nudge-fired:  PASS or WARN (if < MIN_SAMPLES)
0.12.5 coordinator-ready-gate:     PASS
```

All 5 checks must pass before this phase is closed.

### Soak Period

Monitor `delegation_success_rate_24h` for 24h after deployment. Close phase only if rate stays ≥ 80% for a full 24h window without manual intervention.

---

## 10. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Startup race is in NixOS dependency ordering, not Python code | Medium | High — Python-only fix won't help | Step 1 diagnosis determines this before writing code. If confirmed, escalate to NixOS `sd_notify` fix for AIDB service. |
| `/readyz` endpoint introduces new attack surface | Low | Medium | Gate behind loopback (`127.0.0.1`) check; no auth required (health endpoint pattern consistent with `/health`) |
| Adding `event_type` parameter to `record_delegation_feedback` breaks existing callers | Low | Low | Default value `"delegation_outcome"` means existing callers are backward-compatible. |
| `performance_window.record("delegation", ...)` is called from `extensions/` which may not have access to `performance_window` singleton | Medium | Medium | Verify import chain: `extensions/ai_coordinator_handlers.py` imports from `config`; `performance_window` is a module-level singleton in `config.py`. If import fails due to circular reference, move the record call into `http_server_impl.py` post-processing. |
| `DelegationFeedbackConsumer` periodic task blocks async event loop if JSONL file is large | Medium | Low | Use `asyncio.to_thread()` for file I/O per MEMORY.md "Async blocking (CRITICAL)" pattern. |
| 39% "other failures" are not resolved by this phase | High | Medium | This PRD explicitly targets startup 500s and feedback loop. Other failures (provider_http_error, rate_limited, empty_content) require separate investigation once telemetry is reliable. |
| NixOS rebuild required for full fix — PENDING-REBUILD state adds to existing rebuild backlog | High | Low | Implement Python-only fixes first (Steps 2-3). These can be activated by service restart. NixOS rebuild gates Steps 4, 6. |

---

## 11. Dependencies

### Must Complete Before This Phase Starts

- Existing PENDING-REBUILD items (ebeae5ab switchboard useful_ratio, d501b1e8 health-spider, 35438312 AppArmor BPF) must be assessed: this phase adds a new rebuild requirement. Orchestrator must decide whether to bundle into one rebuild or proceed independently.
- Step 1 diagnosis (Section 6, Step 1) must produce a definitive answer on startup race surface before any code is written. If diagnosis reveals a different root cause than modeled in Section 2A, the technical approach for Fix 5A must be revised before implementation.

### What This Phase Blocks

- Phase 185+ (any work that depends on delegation reliability): PRSI autonomous improvement cycles, `aq-insights`, `tradingagents` multi-agent dispatch, any feature that uses `ai_coordinator_delegate` as a building block.
- PRSI orchestrator meaningful operation: `prsi-orchestrator.py` observes `aq-report structured_actions` but cannot act on delegation-derived insights until the feedback loop is closed.

### What This Phase Enables

- Reliable delegation → PRSI can actually execute improvement cycles driven by delegation failure patterns.
- Non-null `event_type` → aq-report delegation section becomes meaningful; dashboard Panels 1-5 light up with real data.
- Feedback-driven routing nudge → `PerformanceWindow` gains a new `"delegation"` bucket that can lower the `local_confidence_threshold` if delegation is succeeding, or raise it to route more locally if delegation is failing.

---

## Appendix A: File Reference Map

| File | Role | Change Required |
|------|------|----------------|
| `ai-stack/mcp-servers/hybrid-coordinator/server.py` | Startup, `initialize_server()`, `main()` | Add `_COORDINATOR_READY` flag |
| `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py` | HTTP app, route wiring, scheduler | Add `/readyz`; add delegate not-ready guard; register consumer task |
| `ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback.py` | Feedback JSONL writer | Add `event_type` param + field |
| `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` | Delegate handler | Update 2 `record_delegation_feedback` call sites; add `performance_window.record()` |
| `ai-stack/mcp-servers/hybrid-coordinator/core/config.py` | `PerformanceWindow` (line ~790) | No change needed — existing `record()` + `maybe_nudge()` works once call site is added |
| `ai-stack/mcp-servers/hybrid-coordinator/workflow/delegation_feedback_consumer.py` | New: consumer/aggregator | Create |
| `nix/modules/services/mcp-servers.nix` | systemd service definition | Add ExecStartPost readiness probe (rebuild) |
| `scripts/ai/aq-qa` | QA check runner | Add checks 0.12.1–0.12.5 |

## Appendix B: Key Line References

| Symbol | File | Lines | Purpose |
|--------|------|-------|---------|
| `initialize_server()` | `server.py` | 549–1039 | Full wiring sequence — readiness flag goes at end |
| `_preflight_check()` | `server.py` | 166–206 | TCP probes — first failure point for startup 500s |
| `_COORDINATOR_READY` (proposed) | `server.py` | After 1039 | New flag |
| `record_delegation_feedback()` | `workflow/delegation_feedback.py` | 393–428 | Payload builder — add `event_type` here |
| `record_delegation_feedback()` call 1 | `extensions/ai_coordinator_handlers.py` | 2218 | Add `event_type="delegation_initial"` |
| `record_delegation_feedback()` call 2 | `extensions/ai_coordinator_handlers.py` | 2233 | Add `event_type="delegation_fallback"` |
| `PerformanceWindow.record()` | `core/config.py` | ~800 | Target for delegation outcome recording |
| `PerformanceWindow.maybe_nudge()` | `core/config.py` | ~807–820 | Existing nudge mechanism — no change needed |
| `hybridDeps` | `nix/modules/services/mcp-servers.nix` | 442–449 | systemd dependency chain |
| `Restart=always` + `RestartSec=5s` | `nix/modules/services/mcp-servers.nix` | 1051–1052 | Crash-restart config |
| `_scheduler_startup` | `http_server_impl.py` | 2652–2658 | APScheduler hook — register consumer task here |
