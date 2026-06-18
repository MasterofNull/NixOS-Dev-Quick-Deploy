# Expert Review: Switchboard Routing Layer & llama.cpp Integration

**Scope**: `ai-stack/switchboard/switchboard.py` (3124 lines), `ai-stack/mcp-servers/shared/llm_config.py` (324 lines), `config/routing-policy.yaml`, `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`
**Reviewer**: Claude Sonnet 4.6 (senior inference systems engineer perspective)
**Date**: 2026-06-17
**Phase**: 175 pre-commit expert review

---

## 1. Architecture Assessment

### Profile System Design: Mostly Coherent, One Critical Inconsistency

The profile system is a sound design. Profiles are well-separated, each with a clear purpose, and the `DEFAULT_PROFILE_CATALOG` is authoritative at startup. The YAML/JSON override mechanism (`SWB_PROFILE_CATALOG_YAML_FILE`) provides runtime flexibility without a rebuild. Profile cards are thoughtfully written and grounded.

**Critical inconsistency — `local-tool-calling` has `injectHints: True` but the profile card says nothing about hints.** Profile lines 388-400 show `injectHints: True`. However, the 46-SWITCHBOARD-PROFILES.md explicitly lists `local-tool-calling` as having `Hints: no` in its profile matrix. This is a direct contradiction between the code (truth) and the documentation. When the tool-calling loop is running and hints are injected, the hint text prepends itself to the FIRST user message's context (line 2810), which can shift tool-call intent detection results if the first user turn was a short command. This is probably benign but the doc/code mismatch is a governance violation.

**`continue-local` also has `injectHints: True`.** The 46-SWITCHBOARD-PROFILES.md matrix says `Hints: no` for `continue-local`. Again, code (line 294) says `True`, docs say `no`. The profile is intended as a fast-path IDE lane; hints injection adds a 3-second timeout per turn (`HINTS_TIMEOUT_S=3.0`) to every Continue.dev interaction. This is a real latency regression for the stated use case.

### The Switchboard Is Doing Too Much

At 3124 lines, the switchboard is a routing proxy, an agentic tool executor, a context window manager, a loop detector, a semantic reranker, an SSE stream parser, a token budget enforcer, a circuit breaker client, and a telemetry emitter — all in a single FastAPI process. This is a significant complexity concentration. When the tool loop hangs or the semantic embed times out, everything hangs together. The modularity exists (helpers are extracted to functions) but the blast radius of a bug in any one subsystem is the entire inference path.

**Specific concern**: `_execute_local_tool_calling()` is a synchronous-style `while True:` loop that calls `await` on each llama.cpp round-trip but holds the local semaphore for the entire multi-turn tool exchange. One tool loop with 40 tool calls at 3.45 tok/s and a 256-token budget per call = 40 × (256/3.45 + overhead) ≈ 3000+ seconds of semaphore hold time. Any other caller is blocked for the entire duration.

### Stream Override Logic: Partially Broken by Design

Lines 2827–2836 force `stream=True` for all local chat/completions except `coordinator-internal`, `embedding-local`, and `local-tool-calling`. This was introduced to fix the switchboard's own stream parsing (Phase 107). The logic itself is valid, but:

- `is_stream` is computed at line 2838 AFTER the override at line 2834. The override and the flag derivation are in the correct order. This is fine.
- Callers that set `stream: false` explicitly in their payload will have it silently overridden. The only indication is a stderr print (line 2836). There is no response header signaling this to callers.
- `_execute_local_tool_calling()` manually sets `request_payload["stream"] = False` at line 1440, correctly exempting itself. Good.
- The `_finalize_after_local_tool_limit()` function at line 1390 also forces `stream = False` in its final synthesis call. Good.

---

## 2. Payload Construction Issues

### `build_llama_payload()` Bypass — Major Issue

`build_llama_payload()` is imported and used in exactly **two places** in switchboard.py:
1. Line 2505: `_warm_local_profile_prefix()` — startup KV cache warm (correct use, max_tokens=4).
2. The main proxy path (`proxy()`) does NOT call `build_llama_payload()` at all.

**The entire main request path — the path that serves 100% of production traffic — bypasses `build_llama_payload()` entirely.** The payload arriving from the caller is passed through after preprocessing (profile card injection, trimming, hint injection), but none of the SSOT constraints from `build_llama_payload()` are applied:

- `repeat_penalty: 1.08` — NOT applied to proxy path
- `repeat_last_n: 64` — NOT applied to proxy path
- `cache_prompt: True` — partially applied at line 2823 (only if `not payload.get("cache_prompt")`), this one is OK
- `stream_options: {include_usage: True}` — NOT applied to proxy path (so the usage chunk that the `_iter()` closure is trying to parse may never arrive unless the caller sets it)
- Role injection via `_inject_role()` — NOT applied to proxy path
- Task profile temperature/frequency_penalty selection — NOT applied to proxy path

This means a caller sending `{"messages": [...], "max_tokens": 800}` gets none of the anti-loop guardrails, no role injection, and no task-profile frequency_penalty enforcement. The SSOT is only consulted for the 4-token startup warm probe.

**`_execute_local_tool_calling()` also bypasses `build_llama_payload()`.** It builds `request_payload` by copying `dict(payload)` and mutating it (lines 1432–1440). The `chat_template_kwargs` key is not set in this copy unless the incoming payload already had it. The `_apply_local_thinking_profile()` guard at line 2735 runs BEFORE `_execute_local_tool_calling()` is dispatched (line 2892), so `enable_thinking: false` IS correctly applied to the payload before tool calling starts. However on subsequent loop iterations (line 1617: `request_payload["messages"] = messages`), the payload is reused from the first call — the `chat_template_kwargs` persists. This is safe but fragile.

### `enable_thinking` in `chat_template_kwargs` — Correctly Applied, Partially

`_apply_local_thinking_profile()` (lines 2316–2340) is called on all local targets before routing. It correctly:
- Forces `enable_thinking: false` when not in a reasoning profile
- Inserts the key if absent

**Gap**: This function checks `"reasoning" in profile.lower()` (line 2330) to allow thinking for reasoning profiles. But none of the current profiles have "reasoning" in their name except `remote-reasoning` (which never reaches this function since `target_type != "local"`). `local-agent` does not contain "reasoning". There is no local profile that would pass this guard. This means thinking is universally disabled for all local profiles — which is the desired behavior currently, but it means the `research` and `deep_reasoning` task profiles from `llm_config.py` (which enable thinking with a budget) would be silently overridden if ever used via the switchboard proxy path. The `build_llama_payload()` bypass means these profiles are never consulted anyway.

### `frequency_penalty` — Absent from Main Proxy Path

The main proxy path does not set `frequency_penalty` at all. It passes the caller's payload through unmodified in this regard. A caller that sends no `frequency_penalty` gets llama.cpp's default (0.0). This is **accidentally correct** for structured output, but any caller explicitly sending `frequency_penalty: 0.05` (the legacy default from early `build_llama_payload()` versions) would regress into the early-EOS dense-JSON truncation bug. There is no guard in the switchboard to strip or normalize this value.

### Token Budget Leaks — Two Sites

1. **`_finalize_after_local_tool_limit()`** (line 1391): Budget is `max(768, min(int(final_payload.get("max_tokens") or 1536), 2048))`. At 3.45 tok/s, 2048 tokens = ~594 seconds. This function is called only after the tool limit is hit, so it is bounded, but the upper ceiling of 2048 is above the `AGENT_TASK_MAX_TOKENS=800` that MEMORY.md documents as the correct ceiling for synthesis tasks. The local semaphore is held while this call completes.

2. **`local-agent` and `coordinator-internal` profiles**: Both have `maxOutputTokens: 4096`. The budget validation at startup (lines 497–511) warns when `maxInputTokens + maxOutputTokens > LLAMA_CTX_SIZE - 600`. With `n_ctx=8192`: local-agent allows `8000 + 4096 = 12096 > 7592` — **this fires a startup warning**. Callers that pass `max_tokens: 4096` and the profile passes it through to llama.cpp get a potential 4096 × (1/3.45) ≈ 1187-second slot lock. The 46-SWITCHBOARD-PROFILES.md documents this as 1024 max output for local-agent, but the code says 4096.

---

## 3. Streaming Correctness

### `run_id` NameError Fix at Line 2880 — Correct

The fix at line 2880 defines `run_id` unconditionally before the streaming closure is created. The closure correctly captures it via `nonlocal` variables. This is the known fix referenced in the task brief.

### Remaining Closure Variable Scope Issues

The `_iter()` closure at line 2929 captures:
- `run_id` — defined at 2880, correct
- `profile` — outer function local, correct
- `payload` — outer function local, correct
- `full_content`, `token_usage_emitted`, `last_activity` — nonlocal declarations at line 2930, correct
- `upstream` — captured from enclosing `if is_stream:` block, correct
- `client` — created at line 2910 inside the `else:` branch, captured by closure, correct

**Issue**: `local_active_request_id` is captured by the closure (line 2993) but it is defined in the outer scope at line 2876. If `retain_local_request_until_stream_close` is False, the `finally` block at line 3066 clears it before the streaming response is returned. However the StreamingResponse is returned at line 2997 and the `_iter()` generator hasn't run yet. The `finally` at line 3066 runs when the `try:` block exits, which is immediately after `response = StreamingResponse(...)` is assigned. At that point `local_active_request_id` is cleared by the finally block. The closure then tries to clear it again at line 2994, but `_clear_local_active_request()` checks the ID match at line 2662 and returns silently if it doesn't match. This is a potential double-clear but not a crash.

**More serious**: `last_activity` is updated inside `_iter()` (line 2933) but never used. The inactivity timeout machinery referenced in constants `INACTIVITY_TIMEOUT_S` and `MAX_TOTAL_TIMEOUT_S` is not implemented in `_iter()`. The `_timeout_for()` function at line 2455 uses `MAX_TOTAL_TIMEOUT_S` as the read timeout. If llama.cpp produces no output for 300+ seconds (e.g., thinking phase on a pathologically long prompt), the httpx connection will time out before the model responds, even though `INACTIVITY_TIMEOUT_S` would have been the right threshold. The `last_activity` variable is dead code — inactivity timeout is not actually implemented, and the comment block at lines 56–59 implies it was intended.

### SSE Parsing Completeness

The `_iter()` SSE parser (lines 2936–2961) is minimal:
- Parses only `data: ` prefixed lines
- Breaks on `[DONE]` — but only for the inner loop; the outer `async for chunk` continues
- `break` on `[DONE]` only breaks the inner `for line in chunk_str.splitlines():` loop, NOT the outer `async for chunk`. The generator continues consuming bytes after `[DONE]` until httpx closes the connection. This is a latent issue: if llama.cpp sends any bytes after `[DONE]` (rare but possible with SSE framing artifacts), the generator will re-enter the line loop and attempt to parse them.

**Missing**: The SSE parser does not extract or surface `finish_reason`. It collects `full_content` but never records the stop reason. A token-budget exhaustion (`finish_reason: length`) looks the same as a normal completion (`finish_reason: stop`) from the switchboard's perspective.

### Partial/Interrupted Stream Handling

`httpx.RemoteProtocolError` is caught at line 2988 and logged. The generator exits normally; the client streaming to the end-user sees a truncated SSE without a `[DONE]` frame. This is correct behavior (no crash) but no 5xx is returned. Callers that don't detect truncation will silently receive incomplete responses.

There is no timeout on the `async for chunk` loop itself. If llama.cpp stalls (e.g., blocked on GPU memory swap), the stream hangs indefinitely until the httpx read timeout fires. With `MAX_TOTAL_TIMEOUT_S = 3600`, this means a 1-hour hang before the stream is terminated.

---

## 4. Profile Analysis

### `local-tool-calling` — Misconfigured

| Setting | Catalog Value | 46-PROFILES.md | Assessment |
|---------|---------------|-----------------|------------|
| `maxInputTokens` | 12000 | 2400 | **CRITICAL mismatch** |
| `maxOutputTokens` | 2048 | 768 | Mismatch |
| `maxMessages` | 20 | 12 | Mismatch |
| `injectHints` | True | no | Mismatch |
| `forceProvider` | local | local | OK |

The catalog (code truth) allows 12000 input tokens. 12000 + 2048 = 14048 < 16384 (the code comment says `13024 < 16384 ctx headroom` with n_ctx=8192 but 14048 > 8192 actual context). **12000 + 2048 = 14048 tokens exceeds n_ctx=8192 by 5856 tokens.** The startup warning fires. At runtime, llama.cpp will reject or silently truncate prompts that exceed its context window. The comment on line 393 says `12000 input + 1024 output = 13024 < 16384 ctx headroom` — but `n_ctx=8192` not 16384. The code comment has wrong math AND wrong n_ctx assumption.

The profile is further exempted from the stream-override at line 2830. Tool calling is always synchronous (stream=False). This is correct design but means no streaming heartbeat while tool loops run — the client sees no activity for the duration of the tool exchange.

### `continue-local` — Correctly Configured (with caveat)

Profile has `forceProvider: local`, compact card, 4000 input tokens (env-configurable), 768 output. The `injectHints: True` in code is a latency regression vs. the documented `no` but otherwise the profile is coherent. The compact guidance contract (≤3 lines) is appropriate for IDE inline use.

### `local-agent` — Over-provisioned Output Budget

`maxOutputTokens: 4096` while MEMORY.md documents `AGENT_TASK_MAX_TOKENS=800` as the calibrated ceiling. This means callers can request 4096 output tokens via this profile; at 3.45 tok/s that's ~1187 seconds of slot lock. The `build_llama_payload()` SSOT would cap this at 800 via `LLAMA_MAX_TOKENS` env var, but since the main proxy path doesn't call `build_llama_payload()`, the profile's `maxOutputTokens` is an advisory limit only — the actual limit comes from the caller's `max_tokens` field, which the switchboard passes through unmodified to llama.cpp.

### `coordinator-internal` — No Profile Card, maxOutputTokens: 4096

Empty `profileCard` (line 435). No system-level grounding for the model. This profile is intended for internal coordinator traffic, which presumably sends its own system prompts. However if a caller reaches this profile without a system message, the model receives no behavioral contract. The high output budget (4096) is the same concern as `local-agent` above.

### `injectHints` Discrepancies — Summary

Profiles with `injectHints: True` in code:
- `default` (line 282) — documented as `yes`. Consistent.
- `continue-local` (line 294) — documented as `no`. **Inconsistent.**
- `local-agent` (line 306) — documented as `yes`. Consistent.
- `local-tool-calling` (line 390) — documented as `no`. **Inconsistent.**

Two profiles inject hints that are documented not to. This adds up to a 3-second synchronous wait on every Continue.dev and local-tool-calling request when the hybrid coordinator is up.

---

## 5. Reliability / Failure Mode Analysis

### Semaphore Under Load

`LOCAL_CONCURRENCY = 1` (default). The `async with sem:` at line 2875 blocks all requests beyond the first. There is no queue depth limit or caller timeout on the semaphore wait. If a client sends a 4096-token `local-agent` request and a second client sends a chat request 1ms later, the second client blocks for potentially 1187 seconds waiting for the semaphore. FastAPI's uvicorn worker will hold the coroutine but the HTTP connection stays open. Under load this can exhaust uvicorn's async task queue.

**The lane reservation logic at lines 2860–2869 is a stub.** The comment says "instead of fail-fast, allow wait" and the body is `pass`. Reserved slot enforcement does nothing. This is dead code.

### Circuit Breaker for llama.cpp

`_call_upstream_with_resilience()` at line 2342: when `service_name == "llama"`, the code sets `breaker = None` (line 2358). This means **llama.cpp has NO circuit breaker**. The local inference path gets `retry_with_backoff` (3 attempts) but no open/half-open/closed state tracking. If llama.cpp is down, every single request retries 3× before failing, with exponential backoff delay each time. Under concurrent load, 4 simultaneous clients × 3 retries each = 12 connection attempts flooding a dead service.

This is the most surprising reliability gap in the codebase. Remote providers get circuit breakers via `REMOTE_CIRCUIT_BREAKERS`; the local path that serves the majority of traffic does not.

### Timeout Chain

```
SWB_CONNECT_TIMEOUT_S = 10s (connection establishment)
SWB_WRITE_TIMEOUT_S   = 60s (request send)
SWB_POOL_TIMEOUT_S    = 30s (connection pool)
MAX_TOTAL_TIMEOUT_S   = 3600s (read timeout — effectively the absolute wall-clock ceiling)
```

`_timeout_for()` uses `MAX_TOTAL_TIMEOUT_S` as the read timeout for ALL requests (line 2459). This means a single local request can hold an httpx connection (and the local semaphore) for up to 1 hour. For a production system this is the right design for long inference, but it means recovery from a crashed llama.cpp takes up to 1 hour per in-flight request — the httpx connection hangs waiting for bytes that never come rather than timing out quickly and freeing the slot.

`INACTIVITY_TIMEOUT_S = 300s` is defined at line 58 but never used in any timeout logic. The `last_activity` variable in `_iter()` is set but never read. This is documented intent that was never implemented.

### Silent Failures Inventory

1. **Hints failure is silent to callers** — `_get_hints()` catches all exceptions and returns `None`; `hints_skipped = True` is set but only surfaced in a response header. The caller has no way to know their request was grounded without hints.

2. **Loop detection log write failure is silently swallowed** (line 808: `except Exception: pass`). If `/var/log/nixos-ai-stack/loop-events.jsonl` becomes unwritable, loop events are lost with no stderr output.

3. **Routing log append failure** (line 2592: `except Exception as exc: print(...)`) — this one at least logs, good.

4. **`_record_local_completion()` never updates token budget accounting.** The local budget (token count per request) is tracked only for remote calls (lines 3115–3120). Local calls have no such tracking. Over time, the system has no persistent record of local token spend for capacity planning.

5. **`_emit_reasoning_summary_events()` failure** (line 96: `except Exception as e: print(...)`) — logged to stderr. Acceptable.

6. **`_apply_local_thinking_profile()` leaves `enable_thinking` absent if the incoming payload has no `chat_template_kwargs` key at all** — wait, this IS handled: line 2336 checks `elif "enable_thinking" not in kwargs:` and inserts it. Correct.

7. **Stream-forced-True override has no caller-facing signal.** Only stderr (line 2836). A caller relying on `stream: false` response semantics (expecting a full JSON body, not SSE) will get SSE and silently fail to parse it.

---

## 6. What's Working Well

**`_apply_local_thinking_profile()` safety guard** (lines 2316–2340) is a solid defense. Even if a caller accidentally sends `enable_thinking: true` in `chat_template_kwargs`, this function resets it to `false` for non-reasoning profiles. This prevents the "thinking fills all tokens" silent failure.

**Dual circuit breaker registries** (LOCAL/REMOTE, lines 104–117) with independent configs are well-architected. Remote provider failures cannot cascade into local inference blocking.

**`_finalize_after_local_tool_limit()`** (lines 1364–1409) is a thoughtful mitigation. Rather than returning a partial result or an error when tool budget is exhausted, it makes one final synthesis call. The skipped-tool messages are properly injected so the model knows what was skipped.

**Context output GC** (lines 1305–1337) is a useful token-budget protection. Large tool results are compacted to summaries and stored as artifacts. The tool result deduplication cache (line 1574) prevents identical repeated tool calls from burning context budget.

**`cache_prompt: True` enforcement at line 2823** for all local chat/completions is correct and important for KV-cache hit rate on repeated system prompts.

**`_semantic_scores()` with retry and circuit breaker** (lines 1809–1854) is correctly structured. The embedding client has a separate circuit breaker from the main local breaker.

**Token estimation fallback** in `_iter()` (lines 2967–2987) is a good defensive measure for providers that don't return usage in the final SSE chunk.

**`_is_self_referential()` guard** (line 2464) prevents recursive routing loops. Clean and correct.

---

## 7. Priority Recommendations (Ranked by Severity)

### SEV-1: No Circuit Breaker for llama.cpp (Critical)

**File**: `switchboard.py:2358`
**Issue**: `if service_name == "llama": breaker = None` disables circuit breaking for the primary inference path.
**Fix**: Create and use `LOCAL_CIRCUIT_BREAKERS.get("llama")` — the same registry infrastructure used for embedding. Change line 2358 to `breaker = LOCAL_CIRCUIT_BREAKERS.get("llama")`.
**Risk if unresolved**: llama.cpp crash floods the system with 3× retried requests; recovery blocked for up to 3600s.

---

### SEV-1: Main Proxy Bypasses `build_llama_payload()` SSOT (Critical)

**File**: `switchboard.py:2726–2768` (entire payload preprocessing block in `proxy()`)
**Issue**: The main request path modifies caller payloads but never applies the SSOT constraints from `build_llama_payload()`. Missing: `repeat_penalty`, `repeat_last_n`, `stream_options.include_usage`, role injection, task-profile frequency_penalty.
**Fix option A**: Call `build_llama_payload()` on the processed messages before passing to llama.cpp, for local targets only, preserving caller-supplied `max_tokens` and stripping any conflicting keys. This requires careful merge logic.
**Fix option B** (lower risk): Apply the missing guardrails selectively — add `repeat_penalty` and `repeat_last_n` at line 2768 for local targets; add `stream_options` when `is_stream=True`.
**Risk if unresolved**: Anti-loop guardrails absent; usage stats may not appear in SSE (usage chunk never sent without `stream_options.include_usage`).

---

### SEV-1: `local-tool-calling` maxInputTokens Exceeds n_ctx (Critical)

**File**: `switchboard.py:394`
**Issue**: `maxInputTokens: 12000` (default) + `maxOutputTokens: 2048` = 14048 > `n_ctx=8192`. Comment on line 393 incorrectly cites 16384 as ctx headroom.
**Fix**: Set `maxInputTokens` to `int(os.environ.get("SWB_LOCAL_TOOL_MAX_INPUT_TOKENS", "5500"))` and `maxOutputTokens` to 1024. With 8192 context: 5500 input + 1024 output = 6524 < 7592 (8192-600). Update the comment.
**Risk if unresolved**: Prompts over 6000 tokens passed to `local-tool-calling` silently fail or get truncated by llama.cpp without a useful error.

---

### SEV-2: `injectHints` Code/Documentation Mismatch for `continue-local` and `local-tool-calling` (High)

**File**: `switchboard.py:294` (`continue-local`) and `switchboard.py:390` (`local-tool-calling`)
**Issue**: Both profiles have `injectHints: True` in code but `no` in documentation. For `continue-local`, this adds a 3s latency penalty per IDE chat turn.
**Fix**: Change both to `injectHints: False`. Update 46-SWITCHBOARD-PROFILES.md to match. If hints are actually desired for these profiles, fix the documentation instead.
**Risk if unresolved**: Continue.dev users experience 3s added latency on every turn when hybrid coordinator is running.

---

### SEV-2: Inactivity Timeout Is Dead Code (High)

**File**: `switchboard.py:56–59` (constants), `switchboard.py:2933` (`last_activity` set but unused)
**Issue**: `INACTIVITY_TIMEOUT_S = 300s` and `last_activity` are defined but never enforced. The current implementation uses `MAX_TOTAL_TIMEOUT_S = 3600s` as an absolute wall-clock ceiling. A stalled llama.cpp can hold the local semaphore for 1 hour.
**Fix**: Implement inactivity detection in `_iter()`: if `time.time() - last_activity > INACTIVITY_TIMEOUT_S`, break the stream and close the upstream.
**Risk if unresolved**: llama.cpp hang = 1-hour semaphore lock = complete local inference unavailability.

---

### SEV-2: `local-agent` and `coordinator-internal` maxOutputTokens: 4096 Token Leak (High)

**File**: `switchboard.py:311` (local-agent), `switchboard.py:432` (coordinator-internal)
**Issue**: 4096 max output at 3.45 tok/s = 1187-second potential slot lock. Conflicts with `AGENT_TASK_MAX_TOKENS=800` in `llm_config.py`.
**Fix**: Reduce to 1200 (matching `AGENT_TASK_MAX_TOKENS` with margin). Or enforce via `build_llama_payload()` integration (see SEV-1 fix).
**Risk if unresolved**: A single local-agent request with high max_tokens can lock out all other local inference for ~20 minutes.

---

### SEV-2: No `stream_options: {include_usage: True}` in Proxy Path (High)

**File**: `switchboard.py:2827–2836` (stream override block)
**Issue**: When stream is forced True, `stream_options` is not added. The `_iter()` closure at line 2947 checks for `usage` in the SSE chunk, but llama.cpp only sends usage when `stream_options.include_usage=True` is in the request. Without it, the fallback estimator (lines 2967–2987) runs on every local streaming request, emitting estimated (inaccurate) token counts to telemetry.
**Fix**: Add `payload["stream_options"] = {"include_usage": True}` alongside the `payload["stream"] = True` at line 2834.
**Risk if unresolved**: Token usage telemetry is always estimated for local streaming calls; `cache_hit_rate` and prompt_tokens data is inaccurate.

---

### SEV-3: `_iter()` `break` on `[DONE]` Only Breaks Inner Loop (Medium)

**File**: `switchboard.py:2940`
**Issue**: `if data_str == "[DONE]": break` breaks `for line in chunk_str.splitlines()` but not the outer `async for chunk in upstream.aiter_bytes()`. The generator continues consuming chunks after `[DONE]`.
**Fix**: Add a flag: `done = False` before the outer loop; set `done = True` on `[DONE]`; after `yield chunk`, check `if done: break`. Or use `return` after `[DONE]` detection within the outer loop.
**Risk if unresolved**: Minimal in practice (httpx closes after `[DONE]`), but protocol artifacts after `[DONE]` can cause spurious parse errors.

---

### SEV-3: Lane Reservation Logic Is a Stub (Medium)

**File**: `switchboard.py:2860–2869`
**Issue**: `is_priority` is read from the `X-AI-Lane: high-priority` header, active_slots is computed, but the reservation enforcement is `pass`. The comment says "allow wait but don't force-preempt" — but no reservation semantics are implemented.
**Fix**: Either implement reservation (maintain a count of high-priority-reserved slots and reject non-priority requests that would consume the last reserved slot) or remove the dead code. Dead code in a hot path is a maintenance hazard.

---

### SEV-3: Budget Token Tracking Reads/Writes the Budget State File Synchronously (Medium)

**File**: `switchboard.py:2420–2439`
**Issue**: `_budget_state_current()` and `_budget_state_save()` do synchronous file I/O inside the async `proxy()` handler. With `asyncio.to_thread()` pattern established elsewhere in this file (line 2960: `asyncio.to_thread(_are.append_jsonl, ...)`), this is a consistency gap and will block the event loop on file I/O for every remote request.
**Fix**: Wrap in `asyncio.to_thread()` or maintain state in-memory with a periodic flush.

---

### SEV-4: `_loop_detect_log` Silently Swallows All Exceptions (Low)

**File**: `switchboard.py:797–809`
**Issue**: `except Exception: pass` with no logging. Log write failures for loop events are invisible.
**Fix**: Add `print(f"[switchboard] loop_log_write_failed: {exc}", file=sys.stderr)` in the except block.

---

### SEV-4: `continue-local` `injectHints: True` Documentation for 46-PROFILES.md Says `no` (Low — Governance)

Already covered in SEV-2 above from a runtime perspective. The documentation file at `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` profile matrix must be updated to match code truth (or vice versa).

---

## Summary Table

| # | Severity | Issue | File:Line |
|---|----------|-------|-----------|
| 1 | SEV-1 | No circuit breaker for llama.cpp | `switchboard.py:2358` |
| 2 | SEV-1 | Main proxy bypasses `build_llama_payload()` SSOT | `switchboard.py:2726–2768` |
| 3 | SEV-1 | `local-tool-calling` maxInputTokens exceeds n_ctx | `switchboard.py:394` |
| 4 | SEV-2 | `injectHints` code/doc mismatch on 2 profiles | `switchboard.py:294,390` |
| 5 | SEV-2 | Inactivity timeout is dead code; 1-hour hang possible | `switchboard.py:56,2933` |
| 6 | SEV-2 | `local-agent`/`coordinator-internal` 4096 token budget leak | `switchboard.py:311,432` |
| 7 | SEV-2 | `stream_options.include_usage` missing from stream override | `switchboard.py:2834` |
| 8 | SEV-3 | `break` on `[DONE]` only exits inner loop | `switchboard.py:2940` |
| 9 | SEV-3 | Lane reservation logic is a stub (`pass`) | `switchboard.py:2869` |
| 10 | SEV-3 | Budget state file I/O is synchronous in async handler | `switchboard.py:2420,2438` |

---

## Files Reviewed

- `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/switchboard/switchboard.py` (3124 lines, full read)
- `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/shared/llm_config.py` (324 lines, full read)
- `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/routing-policy.yaml` (47 lines, full read)
- `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/docs/agent-guides/46-SWITCHBOARD-PROFILES.md` (162 lines, full read)
