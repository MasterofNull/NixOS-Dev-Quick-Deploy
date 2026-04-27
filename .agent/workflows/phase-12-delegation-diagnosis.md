# Phase 12.1 — Delegation Root-Cause Diagnosis

Status: `complete`
Date: 2026-04-26
Author: Claude (orchestrator)
Evidence: aq-report telemetry, code audit (http_server.py, delegation_handlers.py, quality_assurance.py)

---

## Baseline Metrics (as of 2026-04-26)

| Metric | Value |
|--------|-------|
| `ai_coordinator_delegate` total calls (7d) | 34 |
| Success rate | 23.5% (8/34) |
| Error count | 26 |
| P50 latency | 10,577ms |
| P95 latency | 208,355ms |
| Remote routing share | 0% |
| Active services | llama-cpp only (port 8080) |

---

## Root Cause Analysis

### RC-1 (PRIMARY) — Switchboard Offline: All Local Delegation Hard-Fails

**Severity**: Critical — explains most of the 76.5% failure rate

**Finding**:
Every local agent subprocess spawned by `_spawn_local_agent()` (http_server.py:5933)
makes its inference call to `SWITCHBOARD_URL/v1/chat/completions`:

```python
# http_server.py:6129-6130 (inside embedded agent subprocess code)
resp = await client.post(
    f"{SWITCHBOARD_URL}/v1/chat/completions",  # → localhost:8085
```

`SWITCHBOARD_URL` defaults to `http://127.0.0.1:8085`. When `ai-switchboard.service`
is inactive, every subprocess hits ECONNREFUSED immediately. The subprocess exits with
code 1 (uncaught exception path at line 6179), which `_spawn_local_agent` returns as
HTTP 500 ("local_agent_failed").

**Confirmed**: `systemctl is-active switchboard.service` → `inactive`

**The bimodal latency signature**:
- P50 = 10.5s: fast failures (subprocess starts, connects, fails, returns)
- P95 = 208s: rare slow path (either timeout or switchboard was up briefly)
- 8 successes: these calls happened when switchboard was running

**No fallback exists**: The agent subprocess has no retry or direct-llama.cpp fallback.
`llama-cpp.service` IS active on port 8080, but the agent never tries it directly.

**Fix (RC-1-FIX)**: Add llama.cpp direct fallback in `_spawn_local_agent` for
`local-tool-calling` profile when switchboard is unreachable. Try switchboard first;
on `httpx.ConnectError`, retry against `LLAMA_CPP_URL` (port 8080) directly.

---

### RC-2 (SECONDARY) — Quality Scorer: Keyword Overlap Kills Valid Responses

**Severity**: Medium — affects calls that reach inference but paraphrase the query

**Finding**:
`QualityChecker` (quality_assurance.py:84) uses `ACCEPTABLE` threshold (0.70).
The `_check_relevance` dimension (weight 0.30) uses raw term overlap:

```python
# quality_assurance.py:190-191
overlap = query_terms & response_terms
relevance = len(overlap) / len(query_terms)  # pure keyword match
```

A valid response that uses synonyms or paraphrasing will have low overlap even if
semantically correct. Combined weights:

| Dimension | Weight | Typical score for paraphrased response |
|-----------|--------|----------------------------------------|
| RELEVANCE | 0.30 | 0.2–0.4 (paraphrase → low overlap) |
| ACCURACY | 0.25 | 0.7–1.0 |
| COMPLETENESS | 0.20 | 0.7 |
| CLARITY | 0.15 | 0.8–0.9 |
| SAFETY | 0.10 | 1.0 |

Worst-case combined: `0.3*0.3 + 0.25*0.9 + 0.20*0.7 + 0.15*0.85 + 0.10*1.0 = 0.61`
— below the 0.70 pass threshold, despite being a valid response.

The accuracy scorer also penalises hedging phrases like "I'm not sure" or "I cannot"
(each -0.1), which local quantized models use frequently.

**Fix (RC-2-FIX)**: Lower pass threshold from 0.70 to 0.55 (MINIMAL+), and optionally
add a bigram/n-gram overlap step to `_check_relevance` to reduce false negatives.
Long-term: replace with embeddings-based semantic similarity.

---

### RC-3 (TERTIARY) — Timeout Risk on Complex Queries

**Severity**: Low — affects < 10% of calls based on P95 pattern

**Finding**:
Default `timeout_s = 180.0` (http_server.py:5916). With llama.cpp taking 90–120s per
simple response, multi-step tasks (fallback chain + quality retry + refinement) can
exceed 180s. P95 = 208s > 180s confirms some calls hit the timeout and return 504.

The inner agent subprocess also has `AGENT_TIMEOUT = timeout_sec` (inherits 180s),
so the outer `asyncio.wait_for(proc.communicate(), timeout=timeout_sec)` and the inner
httpx client timeout are the same — no slack.

**Fix (RC-3-FIX)**: Set `timeout_s` default to `240` and inner subprocess timeout to
`210` to give the subprocess 30s slack for process overhead. Wire via env var
`AI_DELEGATE_TIMEOUT_S` in `nix/modules/core/options.nix`.

---

### RC-4 (INFRASTRUCTURE) — nixos-rebuild Not Run

**Severity**: Blocking — all Phase 10/11 service fixes are undeployed

**Finding**:
Phase 10/11 commits include:
- Correct service startup ordering (switchboard depends-on llama-cpp)
- Shim request fixes, loopback bypass, advisor wiring

None of these are active in the running system. The coordinator itself is currently
INACTIVE (`systemctl is-active hybrid-coordinator.service` → `inactive`).

The 34 delegation calls happened during a previous window when it was running from
pre-Phase-11 code.

**Fix (RC-4-FIX)**: Run `sudo nixos-rebuild switch --flake .#nixos` in a terminal
session (requires sudo access). This unblocks RC-1 through RC-3 measurably.

---

## Fix Priority Order

| Priority | ID | Fix | Effort | Impact |
|----------|----|-----|--------|--------|
| 1 | RC-1-FIX | Add llama.cpp direct fallback in agent subprocess | Medium | ~40% success rate gain |
| 2 | RC-4-FIX | `sudo nixos-rebuild switch` | Low (ops) | Activates all Phase 10/11 fixes |
| 3 | RC-2-FIX | Lower quality pass threshold 0.70 → 0.55 | Low | ~10–15% additional gain |
| 4 | RC-3-FIX | Increase timeout_s default to 240 | Low | ~5% additional gain |

**Expected combined result post-fixes**: ≥75% success rate (from RC-1-FIX alone when
switchboard is online). With nixos-rebuild (RC-4), targeting ≥85%. The 90% target
requires RC-2-FIX and production validation over a week.

---

## Phase 12.1.a — Immediate Fix: Llama.cpp Fallback in Agent Subprocess

**Status**: planned → see Phase 12 plan slice 12.1

**Files to change**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (agent subprocess code
  block, add fallback in the `except` path after switchboard connection failure)

**Validation**:
```bash
# With switchboard stopped, delegation should still succeed via llama.cpp:
systemctl stop ai-switchboard  # (when accessible)
curl -s -X POST localhost:8003/control/ai-coordinator/delegate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(cat /run/secrets/hybrid_coordinator_api_key)" \
  -d '{"task": "what is 2+2", "profile": "local-tool-calling"}' \
  | python3 -m json.tool | grep -q "choices"
```

---

## Phase 12.1.b — Quick Fix: Quality Threshold

**Status**: planned → implement after RC-1-FIX

**Files to change**:
- `ai-stack/offloading/quality_assurance.py`: `ACCEPTABLE = 0.7 → 0.55`
  OR
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py:234`:
  `QualityThreshold.ACCEPTABLE → QualityThreshold.MINIMAL`

**Note**: Do not change `MINIMAL = 0.5`. Create a new `PERMISSIVE = 0.55` level if
needed to avoid semantic confusion.

---

## Open Questions

1. Was switchboard ever reliably online during the 34-call window? (Check service logs)
2. Is the quality checker even reached for the 26 failures, or do they all fail at
   the subprocess level? (Need log evidence post-rebuild)
3. What is the `ai_coordinator_delegate` success rate post-nixos-rebuild?
   (Current: 23.5% pre-rebuild, target: ≥80% gate for Phase 11.6 re-enablement)
