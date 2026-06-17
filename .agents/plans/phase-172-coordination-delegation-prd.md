---
doc_type: prd
id: phase-172-coordination-delegation-prd
title: "Phase 172 — Coordination & Delegation Architecture: llama.cpp Dependency Gap, Readiness Gate, Circuit Breaker"
status: active
owner: orchestrator
phase: "Phase 172"
priority: P0-critical
authors:
  - claude-sonnet-4-6 (orchestrator — startup chain analysis, auth audit, live failure analysis)
  - gemini-2.5-pro (SRE reviewer — dependency ordering, circuit breaker, observability)
  - qwen3-35b (code analyst — attempted; failed with provider_http_error, itself evidence of root cause)
evidence_required: >
  delegation_success_rate_24h ≥ 0.80; aq-qa 0.12.x delegation checks all PASS;
  /readyz returns {"llama_cpp": "ready"} within 120s of boot; no provider_http_error
  failures in delegation-feedback.jsonl for 24h soak after rebuild
review_session: "2026-06-17 — multi-agent team review"
---

# Phase 172 — Coordination & Delegation Architecture Review

## 0. Review Session Summary

**Team:** Claude (orchestrator), Gemini (SRE/distributed systems), Qwen3 (code analyst — failed during session with `LLM connection refused`, confirming root cause live).

**184A PRD accuracy assessment:** The 184A draft was partially stale at review time. Two of its three primary fixes (`event_type` in `delegation_feedback.py` + `performance_window.record()`) were already committed in `01f3ba41` (2026-06-15). The "23 startup 500 errors = 52% of failures" claim is **unverified** and does not appear in the actual `delegation-feedback.jsonl` failure class distribution. The draft's core startup race theory (None globals from port-before-init) is **wrong** — the port opens after `initialize_server()` completes (confirmed from `server.py:main()` call sequence).

**Real failure distribution (live data, last 50 events):**
| Failure Class | Count | % |
|---|---|---|
| `provider_http_error` | 30 | 60% |
| `provider_request_error` | 15 | 30% |
| `json_contract_failed` | 5 | 10% |

**Root cause confirmed:** `hybridDeps` in `mcp-servers.nix` (line 442-449) does not include `llama-cpp.service`. The coordinator starts and accepts delegation requests while llama.cpp is still loading the 22GB model (30-90s), producing `provider_http_error` on every local delegation call during that window. Confirmed live: Qwen3 agent dispatched during this review session returned `"error": "LLM connection refused at http://127.0.0.1:8080: All connection attempts failed"`.

---

## 1. Problem Statement

The `ai_coordinator_delegate` tool succeeds at **4.5% over 24 hours**. The actual failure
breakdown (from live `delegation-feedback.jsonl`) is:

- **60% `provider_http_error`**: coordinator reaches llama.cpp but gets a non-2xx response —
  most commonly because the model is still loading (returns HTTP error) or the slot queue
  is full under load.
- **30% `provider_request_error`**: network-level connection refused — llama.cpp process is
  not yet listening (early in boot) or has crashed and not yet restarted.
- **10% `json_contract_failed`**: coordinator received a response but could not parse it as
  valid JSON — malformed model output escaping the JSON wrapper.

There is no readiness gate between coordinator startup and llama.cpp availability. There is no
circuit breaker around the `llama_cpp_client` httpx calls. There is no `/readyz` endpoint that
callers can poll before sending delegation requests. Once llama.cpp is stable and loaded, the
delegation path works — the problem is startup sequencing and the absence of a graceful
degradation path during model load.

---

## 2. Root Cause Analysis

### 2A. hybridDeps Excludes llama-cpp.service (Primary)

**File:** `nix/modules/services/mcp-servers.nix`, lines 442-449

```nix
hybridDeps =
  ["network-online.target" mutableBootstrapUnit "ai-aidb.service"]
  ++ [otlpCollectorUnit]
  ++ lib.optional sec.enable authSelfTestUnit
  ++ lib.optional embedEnabled "llama-cpp-embed.service"
  ++ lib.optional mcp.postgres.enable "postgresql.service"
  ++ lib.optional mcp.redis.enable redisUnit
  ++ lib.optional ai.vectorDb.enable "qdrant.service";
```

`llama-cpp.service` is **not in this list**. The coordinator has `after = hybridDeps` and
`requires = hybridDeps`, but llama.cpp is not a dependency. Systemd starts the coordinator
immediately after AIDB is ready — but llama.cpp may still be loading its 22GB model
(30-90s on Renoir APU). During this window, every `ai_coordinator_delegate` call that
routes to local returns `provider_http_error` or `provider_request_error`.

**Why was llama-cpp.service excluded?** Llama.cpp boot is slow (30-90s model load).
Including it in `requires` with no readiness probe causes coordinator startup to block
or fail if llama.cpp takes too long. The intent was to start the coordinator immediately
and let it degrade gracefully when llama.cpp is unavailable — but no graceful degradation
path (circuit breaker, 503 response, readiness gate) was implemented to back that up.

### 2B. No Circuit Breaker on llama_cpp_client (Secondary)

**File:** `ai-stack/mcp-servers/hybrid-coordinator/server.py`, lines ~568-571

```python
llama_cpp_client = httpx.AsyncClient(
    base_url=Config.LLAMA_CPP_URL,
    timeout=Config.LLAMA_CPP_INFERENCE_TIMEOUT,
)
```

There is no circuit breaker wrapping `llama_cpp_client`. When llama.cpp is down or returning
errors, every delegation call fails immediately and these failures are not tracked to
fast-fail subsequent calls. Callers experience full request latency (until timeout) for
every failed delegation.

The MLFQ scheduler has per-level circuit breakers, but these protect the queue processing
lanes — not the downstream network boundary. They do not trip based on `llama_cpp_client`
response codes.

### 2C. No /readyz Endpoint (Secondary)

There is no `/readyz` endpoint that exposes component-level readiness. The existing `/health`
endpoint returns service-level health (is the coordinator process running?) but does not
indicate whether llama.cpp is loaded and serving inference requests. Callers (dashboards,
agents, external tools) cannot distinguish "coordinator up but model loading" from
"coordinator up and model ready".

### 2D. Port Binds After initialize_server() — Gemini's P0 Not Applicable Here

Gemini's review recommended moving `initialize_server()` into `app.on_startup.append()`.
**This does not apply**: `server.py:main()` calls `await initialize_server()` *then*
`await http_server.run_http_mode(port=port)`. The port opens after full init completes.
The "None globals" startup race does not exist in this codebase. Gemini's recommendation
is architecturally sound for aiohttp in general but not the root cause here.

**However:** Gemini's `ExecStartPost` health probe recommendation IS correct and addresses
the actual problem (see Fix 172-B).

### 2E. json_contract_failed — 10% of failures

Five of the last 50 delegation events have `failure_class: json_contract_failed`. These
occur when the model response is not parseable as valid JSON by the delegation handler.
Root cause: the model occasionally produces prose + JSON (mixed output) when not properly
grounded. This is a separate issue from the llama.cpp availability problem and is deferred
to Phase 172-B as a lower-priority hardening item.

---

## 3. What Is Already Fixed (Do Not Re-implement)

From commit `01f3ba41` (2026-06-15):

| Fix | Status | Evidence |
|---|---|---|
| `event_type` parameter in `record_delegation_feedback()` | DONE | `delegation_feedback.py:407` has `event_type: str = "delegation_outcome"` |
| `"event_type": event_type` in payload dict | DONE | `delegation_feedback.py:412` |
| `performance_window.record(bucket, success)` after each feedback write | DONE | `delegation_feedback.py:436-441` |
| 184A draft PRD + 4 sibling PRDs written | DONE | `.agents/plans/phase184[A-C].md`, `phase185[A-B].md` |

The 135 events with `null event_type` in the live JSONL file are **historical** (from before the fix).
New events written post-rebuild will have correct `event_type`. No action needed.

---

## 4. Fixes

### Fix 172-A: Add llama-cpp.service to coordinator After= with Wants= (No Rebuild Ordering Change — NixOS Only)

**Problem:** Coordinator starts before llama.cpp is ready.

**Fix:** Add `llama-cpp.service` to the coordinator's `after` list with `wants` (not `requires`).
`wants` = soft dependency (coordinator can start even if llama.cpp fails).
`after` = ordering guarantee (coordinator starts AFTER llama.cpp process has started).
This alone improves timing but doesn't guarantee model readiness — see Fix 172-B.

**File:** `nix/modules/services/mcp-servers.nix`, line 1029-1036

```nix
# BEFORE:
systemd.services.ai-hybrid-coordinator = {
  after = hybridDeps;
  requires = hybridDeps;
  wants = ["network-online.target"];

# AFTER:
systemd.services.ai-hybrid-coordinator = {
  after = hybridDeps ++ ["llama-cpp.service"];
  requires = hybridDeps;
  wants = ["network-online.target" "llama-cpp.service"];
```

`wants` + `after` = coordinator starts after llama.cpp process launches, but does not fail
if llama.cpp fails. Combined with Fix 172-B, this gives an 80-90s head start for model loading.

**Rebuild required:** YES.

---

### Fix 172-B: ExecStartPost Readiness Probe on llama-cpp.service (NixOS)

**Problem:** llama.cpp binds the HTTP port immediately but the model takes 30-90s to load.
The port is open but `/v1/models` returns an error until loading completes.

**Fix:** Add `ExecStartPost` to the llama.cpp systemd unit that polls `/health` (or `/v1/models`)
until it gets a 200 response, with a 120s timeout. This delays the llama.cpp unit from
transitioning to `active` until the model is actually ready to serve inference.

**File:** Find the llama.cpp systemd service definition in `nix/modules/services/ai-stack.nix`
or the llama.cpp service module. Add:

```nix
serviceConfig = {
  # ... existing config ...
  TimeoutStartSec = "180";   # model load can take 90s; allow 3× headroom
  ExecStartPost = pkgs.writeShellScript "llama-cpp-ready-probe" ''
    until ${pkgs.curl}/bin/curl -sf http://127.0.0.1:${toString llamaPort}/health > /dev/null 2>&1; do
      sleep 3
    done
  '';
};
```

Combined with Fix 172-A (`after llama-cpp.service`), the coordinator now waits until
llama.cpp is confirmed serving before systemd reports the dependency as ready.

**Rebuild required:** YES.

---

### Fix 172-C: /readyz Endpoint in Coordinator (Python, Service Restart)

**Problem:** No way for callers to check whether the coordinator is fully ready (including
model availability) before sending delegation requests.

**Fix:** Add `GET /readyz` route to the coordinator that probes each component and returns
structured health:

```python
# In http_server_impl.py, register new route:
async def handle_readyz(request):
    components = {}
    # Check llama.cpp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{Config.LLAMA_CPP_URL}/health",
                             timeout=aiohttp.ClientTimeout(total=3.0)) as r:
                components["llama_cpp"] = "ready" if r.status == 200 else "degraded"
    except Exception:
        components["llama_cpp"] = "unavailable"
    # Check AIDB
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{Config.AIDB_URL}/health",
                             timeout=aiohttp.ClientTimeout(total=2.0)) as r:
                components["aidb"] = "ready" if r.status == 200 else "degraded"
    except Exception:
        components["aidb"] = "unavailable"
    components["coordinator"] = "ready"
    overall = "ready" if all(v == "ready" for v in components.values()) else "degraded"
    status = 200 if overall == "ready" else 503
    return web.json_response({"status": overall, "components": components}, status=status)

# In route registration block:
http_app.router.add_get("/readyz", handle_readyz)
```

Add `/readyz` to `LOOPBACK_AGENT_PREFIXES` in `middleware/auth.py` (no auth required for health).
Add `/readyz` to `NO_AUTH_ENDPOINTS` in `http_server.py` if it exists.

**Service restart required** (Python-only change, no rebuild).

---

### Fix 172-D: Outbound Circuit Breaker on llama_cpp_client (Python, Service Restart)

**Problem:** When llama.cpp is down, every delegation call burns full timeout latency before
failing. No fast-fail path. MLFQ queue fills with doomed tasks.

**Fix:** Wrap `llama_cpp_client` POST calls in a lightweight circuit breaker. The existing
MLFQ scheduler has `CircuitBreaker` at `mlfq_scheduler.py:~131`. Extract this or implement
a simple inline breaker at the delegation call site in `ai_coordinator_handlers.py`:

```python
# Module-level in ai_coordinator_handlers.py:
_llama_cb_failures = 0
_llama_cb_open_until = 0.0
_LLAMA_CB_THRESHOLD = 3   # open after 3 consecutive failures
_LLAMA_CB_RESET_S = 30    # try again after 30s

async def _llama_cpp_is_circuit_open() -> bool:
    import time
    global _llama_cb_open_until
    if _llama_cb_open_until and time.monotonic() < _llama_cb_open_until:
        return True
    return False

# In the delegation hot path, before calling llama_cpp_client:
if await _llama_cpp_is_circuit_open():
    return web.json_response(
        {"error": "llama_cpp_circuit_open",
         "detail": "local model unavailable, retry in 30s"},
        status=503
    )
```

On `provider_http_error` or `provider_request_error`, increment `_llama_cb_failures`.
When `_llama_cb_failures >= _LLAMA_CB_THRESHOLD`, set `_llama_cb_open_until = time.monotonic() + _LLAMA_CB_RESET_S`.
On success, reset `_llama_cb_failures = 0`.

**Service restart required** (Python-only, no rebuild).

---

### Fix 172-E: aq-qa Delegation Health Checks (Python, No Restart)

Add checks `0.12.1` through `0.12.4` to the QA suite:

| Check ID | Name | Pass Criteria |
|---|---|---|
| 0.12.1 | `coordinator-readyz-endpoint` | `GET /readyz` returns 200 or 503 (not 404) |
| 0.12.2 | `delegate-success-rate-24h` | Last 24h events in feedback JSONL: success fraction ≥ 0.50 (warn) / ≥ 0.80 (pass) |
| 0.12.3 | `feedback-event-type-coverage` | Last 20 events in feedback JSONL: null `event_type` fraction = 0 |
| 0.12.4 | `llama-cpp-slot-available` | `GET /slots` returns at least 1 slot with `state == 0` (idle) |

**File:** `scripts/testing/harness_qa/phases/phase0.py` — add after check `0.10.22`.

---

## 5. Implementation Plan

Steps ordered: Python-only changes first (immediate, service restart only), NixOS changes last.

### Step 1 — Add /readyz endpoint (no rebuild, ~30 min)

File: `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py`
- Add `handle_readyz` handler (Fix 172-C)
- Register `http_app.router.add_get("/readyz", handle_readyz)`

File: `ai-stack/mcp-servers/hybrid-coordinator/middleware/auth.py`
- Add `"/readyz"` to `NO_AUTH_ENDPOINTS` frozenset (line ~58)

**Validate:**
```bash
sudo systemctl restart ai-hybrid-coordinator
sleep 5
curl -s http://127.0.0.1:8003/readyz | python3 -m json.tool
# Expect: {"status": "degraded", "components": {"llama_cpp": "unavailable", ...}}
# (llama.cpp is down, so degraded is correct)
```

### Step 2 — Add outbound circuit breaker on llama_cpp_client (no rebuild, ~45 min)

File: `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`
- Add module-level circuit breaker state (Fix 172-D)
- Add `_llama_cpp_is_circuit_open()` check before delegation call

**Validate:**
```bash
sudo systemctl restart ai-hybrid-coordinator
# With llama.cpp still down:
curl -s -X POST http://127.0.0.1:8003/control/ai-coordinator/delegate \
  -H "Content-Type: application/json" \
  -d '{"task":"test","profile":"local"}' | python3 -m json.tool
# Expect: {"error": "llama_cpp_circuit_open", ...} with HTTP 503
# (NOT connection refused, NOT 500 — clean fast-fail)
```

### Step 3 — Add aq-qa checks 0.12.1-0.12.4 (no rebuild, ~30 min)

File: `scripts/testing/harness_qa/phases/phase0.py`
- Add checks after `_check_phase171_throughput_calibration` (Fix 172-E)

**Validate:**
```bash
aq-qa 0.12
# 0.12.1 should PASS (endpoint exists)
# 0.12.2 may WARN/FAIL until llama.cpp is back up
# 0.12.3 should PASS (event_type fix deployed)
# 0.12.4 will SKIP when llama.cpp is down
```

### Step 4 — Add llama-cpp.service to coordinator after/wants (rebuild, ~20 min)

File: `nix/modules/services/mcp-servers.nix`, line ~1033 (Fix 172-A)
- Change `after = hybridDeps` → `after = hybridDeps ++ ["llama-cpp.service"]`
- Change `wants = ["network-online.target"]` → `wants = ["network-online.target" "llama-cpp.service"]`

### Step 5 — Add ExecStartPost probe to llama.cpp service (rebuild, ~30 min)

Locate llama.cpp systemd service definition (in `ai-stack.nix` or dedicated nix file).
Add `TimeoutStartSec = "180"` and `ExecStartPost` probe script (Fix 172-B).

**Validate (post-rebuild):**
```bash
# Reboot and watch timing:
journalctl -u llama-cpp.service -f &
journalctl -u ai-hybrid-coordinator.service -f &
# Coordinator should NOT appear in logs until llama.cpp ExecStartPost probe succeeds
systemctl status ai-hybrid-coordinator | grep "Active:"
# Should show "active (running)" only after model load completes
```

### Step 6 — Tier 0 gate and commit

```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
git add <specific files>
git commit -m "fix(coordinator): Phase 172 — llama.cpp readiness gate, circuit breaker, /readyz"
```

---

## 6. Files to Modify

**Python-only (Steps 1-3, service restart):**
| File | Change |
|---|---|
| `ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py` | Add `/readyz` handler + route registration |
| `ai-stack/mcp-servers/hybrid-coordinator/middleware/auth.py` | Add `/readyz` to `NO_AUTH_ENDPOINTS` |
| `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` | Add circuit breaker state + guard |
| `scripts/testing/harness_qa/phases/phase0.py` | Add checks 0.12.1-0.12.4 |

**NixOS (Steps 4-5, rebuild required):**
| File | Change |
|---|---|
| `nix/modules/services/mcp-servers.nix` | `after` + `wants` include `llama-cpp.service` |
| llama.cpp service nix file (locate) | `TimeoutStartSec=180` + `ExecStartPost` probe |

---

## 7. Dashboard Panels (Phase 184C dependency — defer)

These panels require the delegation feedback data to be reliable. Implement after Phase 172 soak:
- Delegation success rate 24h rolling time series
- Per-profile success rate table
- llama.cpp readiness gauge (fed from `/readyz`)

---

## 8. Observability

New telemetry events to emit (write via `record_telemetry_event()` in server.py):

| Event | When | Key Fields |
|---|---|---|
| `llama_cpp_circuit_opened` | CB trips after 3 failures | `failure_count`, `open_until_s` |
| `llama_cpp_circuit_closed` | CB resets on success | `was_open_for_s` |
| `readyz_probe_result` | Each `/readyz` call | `components`, `overall_status` |

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| ExecStartPost probe delays entire boot if llama.cpp hangs | HIGH | `TimeoutStartSec=180` ensures SIGKILL if stuck; don't use `until` without a timeout bound |
| Circuit breaker false-positives during thermal throttle (Phase 171: CLM slot-busy) | MEDIUM | CB threshold=3 + 30s reset is conservative; Phase 171 CLM guard prevents slot contention that would otherwise trip it |
| `/readyz` adds latency to health checks if llama.cpp is slow to respond | LOW | 3s timeout on llama.cpp probe; returns immediately with `unavailable` on failure |
| json_contract_failed (10%) not addressed by this phase | LOW | Deferred to 172-B; fix is `rfind('{')` extraction pattern in delegation response parser |

---

## 10. Success Criteria

This phase closes when ALL of the following are true for a 24h soak window:
1. `aq-qa 0.12.1` PASS — `/readyz` endpoint exists
2. `aq-qa 0.12.2` PASS — delegation success rate ≥ 80% over 24h
3. `aq-qa 0.12.3` PASS — zero null `event_type` in last 20 feedback events
4. `aq-qa 0.12.4` PASS — llama.cpp slot available when loaded
5. `provider_http_error` + `provider_request_error` combined < 20% of feedback events
6. Dashboard `/readyz` panel shows component-level status

---

## Appendix A: Gemini SRE Review Key Points (Incorporated)

From `gemini-20260617-105801-6ro46o.log`:
- **FINDING (confirmed):** `Requires=` + `After=` do not guarantee service readiness. ExecStartPost probe required.
- **FINDING (confirmed):** MLFQ circuit breakers are at the wrong boundary. Outbound CB on llama_cpp_client needed.
- **FINDING (partially applicable):** Move initialize_server() into on_startup — **NOT APPLICABLE** here (port binds after init already). Noted as [UNVERIFIED] in Gemini review.
- **RECOMMENDATION (adopted):** Granular /readyz with per-component health. `{"aidb": "ok", "llama_cpp": "loading"}`.
- **RECOMMENDATION (adopted):** `TimeoutStartSec=300` on llama.cpp unit (we use 180 — model load is 30-90s, 3× headroom = 180s sufficient for Renoir APU).
- **RISK (added):** Thundering herd if clients retry aggressively during startup — CB + 503 response prevents queue saturation.

## Appendix B: What the 184A Draft Got Wrong

| 184A Claim | Reality |
|---|---|
| "52% of failures = startup 500 errors from None globals" | Not in actual feedback data. Port binds after init. |
| "`event_type` missing from delegation_feedback.py" | Already fixed in 01f3ba41 (June 15) |
| "`performance_window.record()` not called" | Already fixed in 01f3ba41 (June 15) |
| "APScheduler at http_server_impl.py:2650" | Coordinator uses MLFQ, not APScheduler |
| "Startup 500s = 23 events, 52% of failures" | Failure distribution shows provider_http_error + provider_request_error |

## Appendix C: Live Evidence From Review Session

The local Qwen3 agent dispatched during this review session (`local-20260617-105803-gwi57t`)
failed with:
```json
{
  "result": null,
  "error": "LLM connection refused at http://127.0.0.1:8080: All connection attempts failed"
}
```
This is `provider_request_error` — the exact failure class representing 30% of historical
delegation failures. The coordinator was running, AIDB was running, but llama.cpp was down.
The agent completed 5 steps of tool use (AIDB queries via coordinator) before the final
synthesis step required llama.cpp inference and failed.
