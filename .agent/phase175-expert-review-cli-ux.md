# Expert Review: aq-chat CLI & Intent Routing System
**Phase 175 — Senior CLI/UX Engineering Critique**
**Date:** 2026-06-17
**Reviewer:** Claude Sonnet 4.6 (sub-agent, orchestrator-commissioned)
**Files Reviewed:**
- `scripts/ai/aq-chat` (1379 lines)
- `scripts/ai/lib/chat_intent.py` (162 lines)
- `scripts/ai/lib/dispatch.py` (1170 lines)
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` (2813 lines, delegate handler: lines 906–2772)

---

## 1. Architecture Assessment

### Fast-path vs Coordinator Routing Boundary

The routing decision is made entirely by `classify_chat_intent()` in `chat_intent.py`, called from two call sites: `_stream_chat()` (aq-chat line 785) and `_should_bypass_tools_for_turn()` (line 194). The binary is: if `is_conversational()` returns True AND six guard conditions all hold, the turn goes to `_stream_fast_path()` (switchboard `continue-local` profile, direct SSE); otherwise it goes to `coordinator /control/ai-coordinator/delegate` which spawns `local_agent_runtime.py` as a subprocess (the "coordinator path").

**The boundary is architecturally well-motivated.** The ~50s coordinator overhead for conversational turns is real and correctly avoided for simple exchanges. The fast-path implementation is clean: it builds a proper SSE payload, parses SSE correctly, emits telemetry, and handles token counting.

**However, several structural problems with the boundary exist:**

**Problem 1: The fast-path silently drops messages when switchboard returns non-200.** Lines 624–631 of aq-chat: when the fast-path gets a non-200 response, it prints an error and `return`s. It does NOT fall through to the coordinator path. The user sees a red error and the query is lost. There is no automatic escalation. For a conversational turn that was misclassified (e.g., "explain this error to me" which happens to be mis-routed to fast-path when switchboard is degraded), the answer is dropped entirely.

**Problem 2: The coordinator path has a fundamentally wrong double-profile architecture.** When aq-chat routes to the coordinator (line 848), it sets `profile: "local-tool-calling"` but ALSO sets `X-AI-Profile: "local-tool-calling"` in headers (line 845). The coordinator then re-routes internally, ignoring the header and using `selected_profile` from its own `_ai_coordinator_route_by_complexity()`. Lines 949–951 show that the coordinator only uses `requested_profile` (from request body, not headers). So the header `X-AI-Profile` is dead weight — it never influences routing in the local subprocess path because lines 1491–1782 check `_is_local_runtime(selected_runtime_id)` and spawn a subprocess, not proxying via the `X-AI-Profile` header.

**Problem 3: Tool-free turn handling at the coordinator entry-point is partially duplicated.** `chat_intent.py` is the declared SSOT for TOOL_FREE_PHRASES, but lines 1540–1554 of `ai_coordinator_handlers.py` use a try/except import with a hardcoded fallback frozenset. The comment says "activate at rebuild" — but if the REPO_ROOT env var is absent (e.g., started manually without systemd), the fallback activates silently. The user sees different tool-free behavior depending on how the service was launched. This is a latent operational split-brain.

**Problem 4: `auto_prefer_local` threshold creates an invisible routing boundary at 10s.** Line 956 of the coordinator handler: `auto_prefer_local = not requested_profile and not tools_present and timeout_s <= _AUTO_PREFER_LOCAL_MAX_TIMEOUT_S` (default 10.0s). aq-chat sends `timeout_s = 240` (from `_DELEGATE_DEFAULT_TIMEOUT_S`). So `auto_prefer_local` is always False for aq-chat turns. This means unless the caller explicitly sets `prefer_local=True`, routing goes through `_ai_coordinator_route_by_complexity()` which may select a remote profile. For aq-chat local turns, `profile: "local-tool-calling"` is set in the payload (line 412), which overrides routing (line 988: `routing_decision["recommended_profile"] = requested_profile`). But if the profile field is omitted or changes, routing silently moves remote. No user feedback is given when this happens.

### What happens when `chat_intent.py` misclassifies?

**False Conversational (should be agentic → routed to fast-path):**
- User types: "what is the current state of the health monitoring system?"
- `_CONVERSATIONAL_INTENTS` contains `"what is"` as a prefix match — this matches.
- Result: routed to fast-path `continue-local`. Model answers without tool calls, potentially hallucinating service state.
- UX: user gets a plausible-sounding but ungrounded answer. No indication of routing path.

**False Agentic (should be conversational → routed to coordinator):**
- User types: "ok, explain that more"
- `ok` is in `_CONVERSATIONAL_INTENTS` — this DOES match correctly as conversational.
- But: "what are the trade-offs?" — `"what are"` matches conversational. BUT it's actually a reasoning task that might benefit from tools. The model gets no tools on the fast-path.
- UX: ~50ms fast response but potentially shallow analysis.

**The agentic default is correct insurance but the cost asymmetry is not as described.** The docstring claims "False conversational → hallucination" (catastrophic) vs "False agentic → 50s delay" (acceptable). In practice, the conversational fast-path ALSO injects harness hints (Phase 174, lines 594–605), so the model has some context grounding. The cost of false agentic is now closer to 90–240s in practice (coordinator overhead + subprocess spawn + single-slot contention), not just 50s. This asymmetry argues for being MORE aggressive about classifying conversational turns correctly.

### Is the agentic classification too aggressive?

**Yes, for specific patterns.** The specific example in the review prompt — "how are you today? what would you like to start working on?" — is correctly handled. The `_AGENTIC_OVERRIDE_PHRASES` set (lines 128–136 of `chat_intent.py`) catches "what would you like to start working on" and forces agentic. This is intentional and correct behavior for this specific case (the coordinator can call `discover_objectives`).

**But the classifier is systematically too aggressive in other ways:**

1. **Short question fragments**: "why does this fail?" → `"why does"` is in `_CONVERSATIONAL_INTENTS` — this correctly routes to fast-path. But the prefix is very short and matches many things: "why does the dashboard show..." is a valid conversational question but if the fragment is not at the start of the string, `phrase in lower` could miss it.

2. **`"what is"` as a prefix is dangerously broad.** `"what is the current best approach to..."` — the model on the fast-path will answer without any RAG context or tool calls. Compare: coordinator path would run `query_aidb` and inject relevant patterns. The information quality difference is significant.

3. **"explain " (with trailing space) classification**: anything starting with "explain " routes conversational. "Explain how to fix this AppArmor denial in our harness" goes to fast-path with no tool access. Correct for a generic explanation; arguably wrong when the explanation requires system-specific context.

4. **`"proceed"`, `"go ahead"`, `"sounds good"`**: these are continuations and fast-path is correct for them — but they have no conversation context on the fast-path since `_stream_fast_path` receives the full `context_history`. This is actually fine.

---

## 2. UX/CLI Issues Found

### Error Messages

**Critical — Error at coordinator path (lines 890–894):**
```python
console.print(f"[bold red]Error: Received {response.status_code} from local backend.[/]{suffix}")
return
```
The `suffix` variable comes from `_response_error_detail()`. For a `504 local_agent_timeout` response, the coordinator returns `{"error": "local_agent_timeout", "agent_id": "...", "timeout_s": 240}`. The user sees:
`Error: Received 504 from local backend. local_agent_timeout`
This is acceptable but the timeout_s is buried in the JSON `suffix`. A production CLI would say "Request timed out after 240s. The local model may be overloaded. Try a shorter question or use `/notoolsession`." instead of a raw error type.

**Non-critical — Fast-path error (line 627):**
```python
console.print(f"[bold red]Fast-path error: {response.status_code} from switchboard.[/]{suffix}")
```
Same pattern. Better: distinguish between "switchboard is down" (502), "model overloaded" (503), and "request rejected" (400/401).

**Non-critical — General exception handler (lines 960–964):**
```python
except Exception as e:
    err_msg = str(e)
    if not err_msg:
        err_msg = repr(e)
    console.print(f"[bold red]Inference Loop Interrupted: {err_msg}[/]")
```
`httpx.ConnectError` shows as "httpx.ConnectError: ..." — fine. But `asyncio.TimeoutError` shows as an empty string (it has no message), then falls back to `repr(e)` which is `asyncio.TimeoutError()`. A user sees "Inference Loop Interrupted: asyncio.TimeoutError()" which is meaningless. This should be: "Connection timed out. Is the coordinator running? (aq-qa 0 to check)".

### Timeout UX

**The coordinator path does not stream.** Lines 871–906: aq-chat sends `stream: False` in the coordinator delegate payload (line 418 of `_build_coordinator_delegate_payload`) and does `response = await self.client.post(...)` (a blocking POST, not streaming). The user sees only the spinner `"Synthesizing via local..."` for the full duration of the coordinator call (potentially 90–300s for tool-calling tasks). No intermediate output, no token progress indicator, no elapsed time counter.

Compare: the fast-path streams token-by-token in real time. The coordinator path is a black box until it completes. For a 3-minute tool-calling session, the user sees a spinner for 180 seconds then gets the full response all at once. This is the single biggest UX friction point in the system.

**The coordinator DOES support SSE streaming** (lines 1324–1365 of `ai_coordinator_handlers.py`, the `sse_request` path in `_spawn_local_agent`). But aq-chat never uses it — it sets `streaming_mode: False` (not set, so False by default). The infrastructure exists; aq-chat simply never enables it. This is a trivial fix with large UX impact.

**Timeout mismatch:** aq-chat sends a 1200s httpx client timeout (line 100) but the coordinator default timeout is 240s (`_DELEGATE_DEFAULT_TIMEOUT_S`). The coordinator itself times out the subprocess at `local_agent_timeout_s = max(1.0, timeout_s - slack_s)` ≈ 210s. So the actual user experience is a 210s wait then a 504 response. The httpx 1200s timeout is never hit. However, the HUD shows no countdown, so to the user it looks like the process is hung. A progress indicator or elapsed timer would help enormously.

### Streaming vs Non-Streaming Inconsistency

There is a fundamental inconsistency between the two routing paths:

| Path | Output | User Experience |
|------|--------|-----------------|
| Fast-path (`continue-local`) | Token-by-token SSE streaming | Real-time text appears as model generates |
| Coordinator path (`local-tool-calling`) | Full response returned all at once after completion | Black box spinner for 30–300s |

This inconsistency means the user has two completely different interaction modes depending on whether their turn was classified as conversational or agentic, with no visible indicator of which path was taken. The HUD shows the wire profile (`ltc` vs `cl`) but only after session start, not per-turn.

### Missing Features a Production CLI Should Have

1. **No per-turn routing indicator.** The user has no idea whether their message went via fast-path (2s) or coordinator (90s) or why. The routing decision is logged to `agent-run-events.jsonl` but never surfaced to the user. At minimum, a dim footer line like `[dim]→ fast-path (conversational) 0.8s[/dim]` or `[dim]→ coordinator (agentic/tools) 47s[/dim]` should appear after each response.

2. **No model warm-up / cold-start indicator.** If llama.cpp is not loaded (first inference of the session), the first coordinator call may take 60–120s for model load + KV cache warmup before any tokens appear. The spinner just says "Synthesizing via local..." for this entire period. No "model loading..." intermediate state.

3. **No `/cancel` or Ctrl-C mid-coordinator-turn.** The fast-path correctly handles `asyncio.CancelledError` and the interrupt event (lines 634, 683). But the coordinator path at line 871 is `response = await self.client.post(...)` — a single awaitable. If the user presses Ctrl-C here, Python raises `KeyboardInterrupt` at the outermost `except KeyboardInterrupt: continue` in the run loop (line 1348), which silently continues the loop without killing the coordinator subprocess. The coordinator subprocess continues running, consuming the single llama.cpp slot. The user's next message starts a new turn, but if the slot is still held, it gets a 503 immediately.

4. **No context length display.** As `context_history` grows over a long session (each turn appended), the prompt token count grows. No indicator is shown. Eventually the model will start truncating context silently. A token counter in the HUD would prevent silent context overflow.

5. **`/clear` vs `/reset` are identical.** Both preserve the system message and clear context (lines 971–980). The only difference is that `/clear` also clears the terminal. This is a trivial UX inconsistency — the two commands do essentially the same thing with no clear semantic difference.

6. **`/search` uses a stale endpoint.** Line 1122: `resp = await client.get(f"{self.hybrid_url}/api/documents?search={query}&limit=5")`. The RAG collection names have changed (AIDB ALLOWED_COLLECTIONS was rewritten in Phase 175). This endpoint may silently return 0 results for all queries without error.

7. **Cold-start harness context injection delay.** Lines 1300–1304: the system prompt injection calls `_build_harness_system_prompt()` which makes an HTTP call to `/api/hardware/state`. This runs at startup, before the first prompt. If the coordinator is starting up or slow, the user waits at this blocking call with only a spinner. No timeout guard beyond the 2.0s httpx timeout in `_build_harness_system_prompt()` (line 297). If this 2s call fails silently (exception caught, hardware state empty), the system prompt is built with `?` placeholders — acceptable but not communicated to the user.

### Additional Missing Features

- **No `/model` command** to show the actively loaded model, its context window, or current KV cache state.
- **No `/history` command** to show a compact summary of context depth and truncation risk.
- **`/rate good|bad`** binary rating is too coarse. A 1-5 scale or structured feedback (relevance, depth, correctness) would feed the training pipeline better.
- **`os.system("aq-prime")` at line 1006** runs aq-prime in a subprocess that shares stdout. This can produce garbled output if aq-prime writes ANSI codes that conflict with Rich console state.

---

## 3. Reliability / Failure Mode Analysis

### Single Points of Failure

**1. Single llama.cpp slot (`_LOCAL_SUBPROCESS_LEASES`, coordinator line 290):**
`_LOCAL_SUBPROCESS_LEASES: asyncio.Semaphore = asyncio.Semaphore(_LOCAL_SUBPROCESS_CONCURRENCY)` where `_LOCAL_SUBPROCESS_CONCURRENCY=1`. When a long-running agentic task holds the slot (aq-agent-loop doing a 50-call tool sequence), ALL new coordinator delegates immediately return 503 `local_slot_busy`. aq-chat handles this at line 1442 and returns 503. aq-chat receives 503, prints the error, and drops the query. The user must wait and retry manually. There is no retry-with-backoff in aq-chat for slot-busy responses.

**2. Coordinator subprocess lifetime is not visible to aq-chat:**
When the coordinator spawns `local_agent_runtime.py`, the subprocess PID is tracked in `agent_state_file` (line 1273) but aq-chat has no reference to it. If the coordinator service itself crashes mid-task, the subprocess becomes an orphan. The orphan continues using the llama.cpp slot indefinitely. aq-chat's next call will get 503 (slot busy from orphan) with no indication of root cause. The circuit breaker (lines 305–327) only resets after 30s of inactivity, not after orphan termination.

**3. Context history is in-memory with no persistence:**
`context_history: List[Dict[str, str]]` is stored only in the running process. If aq-chat crashes or is killed (SIGKILL, OOM), the entire conversation history is lost with no checkpoint. The chat can be saved with `/save` but there is no auto-save.

### What Happens When Services Are Down

**Switchboard down:**
- Fast-path: `httpx.ConnectError` → line 687 `console.print(f"[bold red]Fast-path error: {e}[/]")`. Turn dropped, no retry.
- Coordinator path: the coordinator POSTs to switchboard internally. If switchboard is down, coordinator returns 502 (line 2760 of `ai_coordinator_handlers.py`). aq-chat prints `Error: Received 502 from local backend.` and drops the turn.
- No user guidance. "Try aq-qa 0 to diagnose" would help.

**Coordinator down:**
- All coordinator-path turns hit `httpx.ConnectError` → `Inference Loop Interrupted: [Connect call failed ...]`.
- Fast-path turns continue working (they bypass coordinator).
- No clear indication to the user that some turns will still work.

**llama.cpp down:**
- Fast-path: switchboard returns 503 → fast-path prints error and returns.
- Coordinator path: coordinator has a circuit breaker (lines 305–327) that opens after 3 failures. aq-chat gets 503 with `{"error": "llama_cpp_circuit_open", "detail": "local model unavailable — circuit breaker open, retry in ~30s"}`. aq-chat's `_response_error_detail()` will extract the `"detail"` field. User sees: `Error: Received 503 from local backend. local model unavailable — circuit breaker open, retry in ~30s`. This is the best error message in the system — clear and actionable.

### Retry Implementation

**Fast-path:** No retries at all. One failure = turn dropped.

**Coordinator path (aq-chat):** No retries. One failure = turn dropped.

**Inside the coordinator (`_post_delegate`):** `RetryConfig(max_attempts=5, base_delay=2.0, max_delay=30.0)` with retry on `httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException`. This is for the switchboard HTTP call WITHIN the coordinator, not visible to aq-chat.

**Slot-busy retry (`_post_delegate_with_local_slot_retry`):** 1 retry with 1.25s delay, inside the coordinator. Still not visible to aq-chat.

**The retry gap:** aq-chat has zero retry logic for any error condition. A transient 503 (slot momentarily busy) will silently drop the user's message. The user must manually retype. This is a systemic gap.

### Race Conditions

**Race 1: Coordinator subprocess lease vs aq-chat timeout:**
aq-chat client timeout is 1200s (line 100). Coordinator subprocess timeout is ~210s. After 210s the subprocess is killed, coordinator returns 504, aq-chat prints the error. However, the `_LOCAL_SUBPROCESS_LEASES` semaphore is released in the `finally` block (line 1451) when the subprocess completes or times out. This is correct — no lease leak.

**Race 2: Fast-path harness hints fetch vs turn rendering:**
`_fetch_fast_path_hints()` (line 707) uses a 2.0s timeout. If the coordinator `/hints` endpoint is slow, the hints fetch adds 2s of latency to every fast-path conversational turn. This is not a race condition per se but is a cold-path latency adder for every conversational turn after Phase 174.

**Race 3: Routing event write vs turn start:**
`asyncio.create_task(self._write_routing_event(...))` (line 579) fires before the HTTP request. If `_write_routing_event` acquires the GIL for file I/O just as the HTTP request starts, there's a minor contention window. In practice, the 2s `asyncio.to_thread` write is fine for telemetry — but if the telemetry directory doesn't exist yet, `path.parent.mkdir(parents=True, exist_ok=True)` in `_write_routing_event` can fail silently (it's all wrapped in `try/except: pass`).

**Race 4: `_emit_local_inference_event` file handle leak:**
Line 759: `await asyncio.to_thread(lambda: open(tel_path, "a", encoding="utf-8").write(evt + "\n"))`. This opens the file, writes, and does NOT close it — the lambda returns after `write()` without calling `close()`. Python's reference counting will close it eventually, but under high load with many concurrent fast-path turns, this can exhaust file descriptors. Should use `with open(...)`.

---

## 4. Intent Classification Critique

### Specific Phrases That Would Be Misclassified

**Falsely classified as CONVERSATIONAL (would get fast-path, no tools):**

| Prompt | Matched Phrase | Why Wrong |
|--------|---------------|-----------|
| `"what is the best way to fix this AppArmor denial?"` | `"what is"` | Needs AIDB lookup + codebase context |
| `"explain the architecture of the routing system"` | `"explain "` | Needs file reads for accurate architecture |
| `"what are all the open issues right now?"` | `"what are"` | Needs tool call to read issues-backlog.md |
| `"describe the current state of the training pipeline"` | `"describe "` | Needs live service queries |
| `"how does the coordinator decide which profile to use?"` | `"how does"` | Needs codebase search for accurate answer |
| `"summarize the last 10 commits"` | `"summarize "` | Needs git log tool call |
| `"what does the dashboard OSI endpoint return?"` | `"what does"` | Needs HTTP query |
| `"ok, fix that bug"` | `"ok"` | "ok" matches conversational but the rest is agentic |
| `"sure, go ahead and implement it"` | `"sure"` | Same: continuation match clobbers imperative |

The `"ok"`, `"sure"`, `"proceed"` matches are the most dangerous. A prompt like `"ok let's implement the new health check endpoint"` matches `"ok"` (conversational) but is clearly an implementation task. The current code matches on `phrase in lower` — substring match, not prefix. `"ok"` will match in `"look"`, `"book"`, `"cookbook"`, etc.

**Falsely classified as AGENTIC (would incur 50–240s coordinator overhead):**

| Prompt | Why Wrong |
|--------|-----------|
| `"yes that looks correct"` | Matches `"yes"` → conversational. Actually CORRECT. |
| `"what time did the last build complete?"` | No match → agentic default. But this is a quick log query, not a multi-step agentic task. |
| `"is there anything blocking the release?"` | No match → agentic. Could be answered from snapshot data. |
| `"how many tools are registered?"` | No match → agentic. Could be answered by `/tools` command. |

The bigger problem is classification gaps — phrases that are genuinely conversational but fall through to the agentic default because they don't match any phrase in `_CONVERSATIONAL_INTENTS`. Any "yes/no question" that doesn't start with one of the listed prefixes goes agentic.

### Boundary Clarity: "Needs Tools" vs "Conversational"

The current boundary is defined by **user phrase syntax** (does it contain a question prefix?) rather than **task semantics** (does it require live data or file access?). This is fundamentally a shallow heuristic. The two dimensions that should determine routing are:

1. **Requires live system state**: "current status", "right now", "latest", "show me" → needs snapshot or tools
2. **Requires code/file manipulation**: "fix", "implement", "write", "commit", "create" → definitely needs tools

The current implementation ignores dimension 1 in the fast-path classifier and relies on `SNAPSHOT_KEYWORDS` (line 39) for it, but only in the coordinator path (line 786). A prompt matching SNAPSHOT_KEYWORDS but also matching a conversational phrase would be routed to fast-path FIRST (line 785) — the snapshot check at line 786 is only evaluated when the fast-path condition at line 780 is NOT met. This means "what is the current health status?" (`"what is"` matches conversational) gets fast-path, NOT the snapshot enrichment. This is a subtle but important bug: the SNAPSHOT_KEYWORDS guard is bypassed by the fast-path routing guard.

Wait — re-reading the code more carefully:

```python
if (
    is_local_profile
    and self.tool_mode == ToolMode.ENABLED
    and not self._no_fastpath
    and not self._last_turn_had_tool_calls
    and is_conversational(prompt)
    and not self._should_use_local_snapshot(prompt)   # ← LINE 786
):
    await self._stream_fast_path(...)
```

Actually line 786 IS a guard: `not self._should_use_local_snapshot(prompt)` must be True for fast-path to activate. `_should_use_local_snapshot` checks `SNAPSHOT_KEYWORDS`. So if the prompt contains "status", "health", "right now" etc., fast-path is blocked even if `is_conversational()` returns True. This is a safety net.

BUT `SNAPSHOT_KEYWORDS` is incomplete. "what is the current health?" would have "health" → blocked (correct). "what is the coordinator doing right now?" → "right now" → blocked (correct). But "what is the coordinator's profile?" → no snapshot keyword → fast-path (potentially wrong — no live data available on fast-path).

### Performance Impact of Intent Classification

`classify_chat_intent()` is a pure Python string operation with no I/O. It iterates through ~30 frozenset members per classification. At typical prompt lengths this runs in under 1ms. There is no performance concern.

The `_fetch_fast_path_hints()` call (Phase 174) adds up to 2.0s to EVERY fast-path turn — this is the real overhead. If the coordinator `/hints` endpoint is responding in 50–100ms, this adds 50–100ms to conversational turns. If it's slow or down, the 2.0s timeout adds 2.0s. This is a non-trivial overhead for what are supposed to be the "fast" turns. There is no caching of hints between turns on similar topics.

---

## 5. What's Working Well

**1. The three-state ToolMode design (`ENABLED` / `DISABLED_SESSION` / `DISABLED_TURN`) is clean.** It correctly separates session-level tool disabling (--no-tools flag) from turn-level tool disabling (explicit user phrases). The `local_tools_enabled` compatibility property (line 186) ensures backward compatibility without confusion.

**2. The circuit breaker on the coordinator side is well-implemented.** 3 failures → 30s open → auto-reset. Fast-fail with informative 503 response that includes `retry_after_s`. This is correct behavior.

**3. Phase 173 token counting in the fast-path is correct.** `stream_options: {include_usage: True}` ensures the final SSE chunk contains the usage object. The code correctly parses `_fp_tok_in` and `_fp_tok_out` from the usage chunk (lines 647–650). Many streaming implementations miss this.

**4. `enable_thinking: False` is correctly placed in `chat_template_kwargs` (not top-level).** This is a known critical bug that was properly fixed. Both `_build_fast_path_payload()` (line 540) and `_build_coordinator_delegate_payload()` (line 420) set it correctly.

**5. `frequency_penalty: 0.0` is explicitly set in both paths.** The MEMORY.md pattern about frequency_penalty causing dense JSON truncation is correctly addressed in both fast-path payload (line 539) and coordinator payload (line 418).

**6. SSE parsing is correct in the fast-path.** The code explicitly sends `stream: True` (line 535), which is required for the switchboard's behavior (MEMORY.md: switchboard forces stream=True for local targets). The fast-path was updated to match this in Phase 109.1. This is subtler than it looks — many implementations get this wrong.

**7. The fallback chain in the coordinator is genuinely multi-layer.** Remote availability caching (30s TTL), profile failover chain, local fallback from remote failure, circuit breaker — this is a robust degradation stack. The `_select_next_available_delegation_target()` + `_build_delegation_fallback_chain()` pattern gives real resilience.

**8. `_record_response()` vs `_record_and_render_assistant_response()` separation is correct.** Fast-path renders token-by-token during streaming and then calls `_record_response()` (no re-render). Coordinator path calls `_record_and_render_assistant_response()` once after completion. This prevents double-printing.

**9. The HUD prompt format is informative.** `[local | ltc | tools:15] ❯` gives the user the active profile, wire profile, and tool count at a glance. The verbose mode (`--verbose-hud`) expands abbreviations for debugging. Per-session banner with fast-path status is helpful.

**10. Fire-and-forget telemetry with `try/except: pass` everywhere is correct.** Telemetry must never block the chat loop. Every telemetry write is wrapped. This is the right pattern.

---

## 6. Priority Recommendations (Ranked by Severity)

### SEV-1: Coordinator path spinner blocks user with no progress for 30–300s

**File:** `scripts/ai/aq-chat`, lines 792, 871–906
**Issue:** The coordinator path is a blocking POST. User sees a static spinner with no feedback for the full duration of the agent task. For long tool-calling sessions, this is 90–300 seconds of uncertainty.
**Fix:** Enable `streaming_mode: true` in the coordinator delegate payload (line 411). The coordinator SSE streaming path (`_spawn_local_agent` with `sse_request`, lines 1323–1366) is already implemented. aq-chat would need to switch from `self.client.post()` to `self.client.stream()` for coordinator calls, parsing token chunks as they arrive. Alternatively, add a minimal elapsed-time counter that updates the spinner text every 5s: "Synthesizing... (47s elapsed)".
**Impact:** Transforms UX from "is it hung?" to real-time awareness.

### SEV-2: Ctrl-C during coordinator call leaves orphan subprocess consuming llama.cpp slot

**File:** `scripts/ai/aq-chat`, lines 1347–1348
**Issue:** `except KeyboardInterrupt: continue` in the run loop catches Ctrl-C but does not cancel the pending `self.client.post()` coroutine or kill the coordinator subprocess. The subprocess holds `_LOCAL_SUBPROCESS_LEASES` until its timeout (210s). All subsequent aq-chat calls get 503 `local_slot_busy` for up to 210s.
**Fix:** Cancel `self.current_stream_task` on Ctrl-C (the task tracking is already set up at line 131 but never used for coordinator path cancellation). Alternatively, set the interrupt_event and check it in the coordinator response handler.
**Impact:** Prevents a 3.5-minute dead period after any user interruption.

### SEV-3: Fast-path drop on error with no coordinator fallback

**File:** `scripts/ai/aq-chat`, lines 624–631
**Issue:** When switchboard returns non-200 on the fast-path, the turn is silently dropped (return, no retry, no escalation to coordinator).
**Fix:**
```python
if response.status_code != 200:
    # Fall through to coordinator path instead of dropping
    logger.debug("fast-path non-200 (%d), escalating to coordinator", response.status_code)
    return False  # signal to _stream_chat to retry via coordinator
```
Then in `_stream_chat`, check the return value and escalate.
**Impact:** Makes the system self-healing for transient fast-path failures.

### SEV-4: `"ok"`, `"sure"`, `"yes"`, `"proceed"` substring match falsely converts imperative prompts to fast-path

**File:** `scripts/ai/lib/chat_intent.py`, lines 57–63 (`_CONVERSATIONAL_INTENTS` frozenset)
**Issue:** `"ok let's implement..."`, `"sure, add that feature"`, `"yes and also fix the..."` all match short affirmatives via `phrase in lower` substring match, routing to fast-path without tools.
**Fix:** Change affirmative matching to `lower.startswith(phrase)` OR require the phrase to be the entire first word:
```python
words = lower.split()
first_word = words[0] if words else ""
if first_word in {"yes", "yeah", "sure", "ok", "okay"} and len(words) <= 3:
    # short affirmative — truly conversational
```
**Impact:** Prevents tool-less responses to imperative prompts that happen to start with affirmatives.

### SEV-5: File descriptor leak in `_emit_local_inference_event`

**File:** `scripts/ai/aq-chat`, line 759
**Issue:**
```python
await asyncio.to_thread(lambda: open(tel_path, "a", encoding="utf-8").write(evt + "\n"))
```
File handle is never explicitly closed. Python relies on GC for close.
**Fix:**
```python
def _write_event(path, line):
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
await asyncio.to_thread(_write_event, tel_path, evt)
```
**Impact:** Prevents fd exhaustion under high conversational turn rate.

### SEV-6: `chat_intent.py` import in coordinator uses brittle path injection

**File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`, lines 1540–1554
**Issue:** The coordinator tries to import `chat_intent.py` at RUNTIME via `sys.path.insert(0, _chat_intent_path)` where `_chat_intent_path` depends on `REPO_ROOT` env var. If REPO_ROOT is unset (manual startup, test environment), this silently falls back to a hardcoded frozenset that may drift from the production set. Comment says "activate at rebuild" but this has been the state since Phase B.
**Fix:** Package `chat_intent.py` in the coordinator's own module directory or in `shared/`. The coordinator is already a proper Python package — `chat_intent.py` should be in `ai-stack/mcp-servers/shared/` alongside `llm_config.py` and `retry_backoff.py`. Then the import is `from shared.chat_intent import TOOL_FREE_PHRASES`.
**Impact:** Eliminates split-brain tool-free behavior between production (REPO_ROOT set) and manual runs.

### SEV-7: No per-turn routing transparency for the user

**File:** `scripts/ai/aq-chat`, `_stream_fast_path` and `_stream_chat`
**Issue:** User has no visibility into which path their message took or how long it took.
**Fix:** After each response, print a single dim footer line:
```python
# After fast-path:
console.print(f"[dim]→ fast-path ({classification.mode}) {_fp_latency_ms:.0f}ms[/dim]")
# After coordinator:
elapsed_ms = round((time.perf_counter() - t0) * 1000)
console.print(f"[dim]→ coordinator (agentic) {elapsed_ms:.0f}ms[/dim]")
```
**Impact:** Demystifies routing, helps the user understand slow turns, aids debugging.

### SEV-8: `SNAPSHOT_KEYWORDS` check bypassed when conversational match fires first

**File:** `scripts/ai/aq-chat`, lines 780–789
**Issue:** `is_conversational(prompt)` is evaluated BEFORE `not self._should_use_local_snapshot(prompt)` in the guard condition. BUT in Python's short-circuit `and`, all conditions in the `if` block are evaluated left to right and the first False short-circuits. Line 785 (`is_conversational(prompt)`) and line 786 (`not self._should_use_local_snapshot(prompt)`) are both in the same `if` block and BOTH must be True for fast-path. So `SNAPSHOT_KEYWORDS` does guard correctly.

**HOWEVER** — the guard order matters for clarity. A prompt containing both a conversational phrase AND a snapshot keyword (e.g., "what is the current health status?") will:
1. Match `is_conversational()` → True
2. Match `_should_use_local_snapshot()` → True → `not` → False
3. Result: fast-path blocked → goes to coordinator

This is correct behavior. But if someone adds a new condition later and puts it between lines 785 and 786, the ordering guarantee breaks. Document this explicitly or reorder conditions so the snapshot check comes first.

### SEV-9: `/search` command uses potentially stale API endpoint

**File:** `scripts/ai/aq-chat`, line 1122
**Issue:** `GET /api/documents?search=...` — this endpoint path may not match current coordinator routes after Phase 175 AIDB collection restructuring. The endpoint silently returns 0 results if the collection names changed.
**Fix:** Update endpoint to use `/hints?q=...` (same endpoint as `_fetch_fast_path_hints`) or verify `/api/documents` is still wired and returns correct results from `error-solutions` collection.
**Impact:** `/search` may currently be silently broken.

### SEV-10: No retry in aq-chat for transient slot-busy or gateway errors

**File:** `scripts/ai/aq-chat`, coordinator path handler, lines 890–894
**Issue:** 503 `local_slot_busy` means the slot will be free in <30s (current task will complete or time out). But aq-chat immediately drops the user's query with an error message and expects the user to retype.
**Fix:** Add a simple retry loop for 503 responses with a visual countdown:
```python
if response.status_code == 503 and "slot_busy" in detail:
    for remaining in range(30, 0, -5):
        console.print(f"[yellow]Model slot busy. Retrying in {remaining}s...[/]", end="\r")
        await asyncio.sleep(5)
        response = await self.client.post(target_url, json=payload, headers=headers)
        if response.status_code != 503:
            break
```
**Impact:** Eliminates the need for the user to manually retry after slot contention.

---

## Summary of Top 3 Critical Findings

1. **Coordinator path has zero streaming — 30–300s black box spinner.** The infrastructure for SSE streaming from coordinator to aq-chat already exists (`streaming_mode=true` in the delegate handler). aq-chat never uses it. This is the single largest UX gap: the fast-path is real-time, the coordinator path is a blind wait. Fix: enable `streaming_mode: true` in `_build_coordinator_delegate_payload()` and switch the coordinator call from blocking POST to streaming.

2. **Ctrl-C during coordinator call orphans the local_agent_runtime.py subprocess, holding the single llama.cpp slot for up to 210s.** `except KeyboardInterrupt: continue` in the run loop does not cancel the inflight HTTP request or kill the subprocess. Every subsequent message gets 503 `local_slot_busy` until the orphan times out. Fix: track the coordinator task as `self.current_stream_task` and cancel it on interrupt, adding a subprocess kill signal path.

3. **`"ok"`, `"sure"`, `"yes"`, `"proceed"` substring matches falsely classify imperative prompts as conversational.** `"ok, implement the new health check"` matches `"ok"` in `_CONVERSATIONAL_INTENTS` via `phrase in lower` and routes to fast-path without tools. The model gives a plan/explanation instead of executing. Fix: affirmative-phrase matching must require the phrase to be a complete short utterance (≤3 words total), not a substring of a longer imperative.
