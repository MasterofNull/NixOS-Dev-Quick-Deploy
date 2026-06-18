# Expert Review: Local Agent Coordination Layer
## Phase 175 — Senior Agent Systems Engineer Critique

**Scope:** `ai-stack/agents/runtimes/local_agent_runtime.py`, `ai-stack/local-agents/agent_executor.py`, `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`, `ai-stack/local-agents/builtin_tools/ai_coordination.py`, `scripts/ai/aq-agent-loop`  
**Reviewer:** Claude Sonnet 4.6 (agent-systems role)  
**Date:** 2026-06-17

---

## 1. Architecture Assessment

### Subprocess Spawning for Every Request

The coordinator spawns `local_agent_runtime.py` as a fresh OS subprocess for every local agent call (`_spawn_local_agent` in `ai_coordinator_handlers.py:1261`). This has real costs:

- **Startup overhead:** Python interpreter cold-start + `sys.path` manipulation + module imports on every request. On Renoir APU with limited I/O bandwidth this is measurable (~2-5s before first LLM token).
- **Process isolation is good:** Crashes in the subprocess don't corrupt coordinator state. Tool registry, stagnation counters, and performance trackers are per-process (intentionally).
- **Semaphore is correct:** `_LOCAL_SUBPROCESS_LEASES = asyncio.Semaphore(_LOCAL_SUBPROCESS_CONCURRENCY)` (default 1) correctly serializes llama.cpp slot access. The `_spawn_local_agent_with_lease` guard is right.
- **ISSUE:** The subprocess uses `start_new_session=True` (`ai_coordinator_handlers.py:1321`), which is correct for detachment, but stderr is only read on non-zero exit. On timeout, `proc.kill()` is called with no `await proc.wait()`, which risks zombie processes accumulating.

**Recommendation:** Add `await proc.wait()` after `proc.kill()` in both the SSE and non-SSE timeout paths.

### Two Parallel Runtime Paths (DIVERGENCE RISK)

There are **two distinct local agent runtimes**:
1. `ai-stack/agents/runtimes/local_agent_runtime.py` — used by `_spawn_local_agent()` in the coordinator for single-turn conversation tasks (no tool loop, just prompt→response). TOOL_CATALOG has 17 tools in progressive disclosure mode. Tool format is **OpenAI function-calling JSON schema** (`"type": "function"` wrapper).
2. `ai-stack/local-agents/agent_executor.py` — used by `aq-agent-loop` for multi-turn tool-use loops. Tool descriptions use a **compact text format** (not OpenAI schema). Tool format is `{"function": "name", "arguments": {...}}`.

These are **not equivalent**. When the coordinator dispatches via `_spawn_local_agent` and sets `AGENT_TOOLS_ENABLED=false`, it uses `local_agent_runtime.py` which speaks OpenAI-style function calling. When `aq-agent-loop` or the coordinator dispatches with `AGENT_TOOLS_ENABLED=true` via the executor path, it uses `agent_executor.py` which expects `{"function": ...}` format.

**Bug risk:** `local_agent_runtime.py` uses `TOOL_CATALOG` (OpenAI schema format) but `agent_executor.py` uses `tool_registry.get_tools_for_model()` (compact text). If tools are selectively enabled/disabled in one catalog, the other may not reflect the change. They currently have different tool sets: runtime has 17, executor has 29+.

### Coordinator→Runtime→Executor Hop Count

- `aq-chat` → coordinator POST `/control/ai-coordinator/delegate` → `_spawn_local_agent()` → `local_agent_runtime.py` subprocess → llama.cpp at :8085 (via switchboard). This is 4 hops for a simple text reply.
- For an agentic task (async_mode=True): `aq-chat` → coordinator → `asyncio.create_task(_run_async_delegate(...))` → `_spawn_local_agent_with_lease()` → subprocess → the subprocess calls `agent_executor.py`... wait. It does **not** call `agent_executor.py`. `local_agent_runtime.py` has its own LLM call loop. `agent_executor.py` is only called directly by `aq-agent-loop`.

The coordinator's "local subprocess" path uses `local_agent_runtime.py`, NOT `agent_executor.py`. The PRE-FLIGHT RESEARCH, stagnation guards, two-phase token budget, and all the sophisticated loop logic in `agent_executor.py` are **only available via `aq-agent-loop`**. When aq-chat classifies a prompt as agentic and routes to the coordinator, it gets the simpler `local_agent_runtime.py` path.

**This is a significant architectural inconsistency.** `agent_executor.py` has better guard rails.

---

## 2. Tool Calling Pipeline Critique

### `role:"tool"` vs `role:"function"` — FIXED

Confirmed fixed. `agent_executor.py:1307-1310` uses `"role": "tool"` for tool result messages. The Qwen3 constraint is respected.

### Mixed Prose+JSON Parse — Partially Robust

`tool_registry.parse_tool_call_from_llama` (`tool_registry.py:557-659`) has a multi-tier parse strategy:
1. Direct `json.loads(output)`
2. `_sanitize_json()` to escape bare control chars then retry
3. `rfind('{"function"')` to skip prose prefix, then retry both paths

This is solid. However, there is a **gap**:

The sanitizer handles `\n`, `\r`, `\t` inside string values but **does not handle `\x08` (backspace)** — a stray control char known from MEMORY.md to have caused silent regex corruption before. If the model emits `\x08` inside a JSON string value, `_sanitize_json` will pass it through to `json.loads()` which will reject it, causing `parse_tool_call_from_llama` to return `None`. The model's tool call is then silently treated as a prose final answer and the loop exits prematurely.

**File:** `ai-stack/local-agents/tool_registry.py:606-616` — add `elif ord(ch) < 0x20:` catch-all to escape any remaining control chars.

### Tool Result Size Cap

`_RESULT_CHAR_CAP = 3000` chars (`tool_registry.py:663`). At 4 chars/token this is ~750 tokens per result. With 5 active tools × 750 = 3750 tokens, plus system prompt (~500) + messages, context can exceed 8192 tokens on a multi-tool sequence. The context pruner in `agent_executor.py` catches this at 12,000 chars total but there is no per-call guard for large results before that threshold is hit. A single `read_file` on a large file that returns 2999 chars + overhead from surrounding messages can push past the 8k limit silently.

### Tool Schema Mismatch Between Runtimes

`local_agent_runtime.py` defines `TOOL_CATALOG` with OpenAI `{"type": "function", "function": {...}}` wrappers. `agent_executor.py` builds tool descriptions as compact text (`_minimal_tool`). If the model trained on Qwen3's OpenAI-schema format expects function objects in its context, the compact text format in `agent_executor.py` may produce less accurate tool calls.

### Security: Tool Whitelist

`local_agent_runtime.py` has `_ALLOWED_HARNESS_CLI_TOOLS` (10 tools) and `_ARG_BLOCKLIST_CHARS` for shell injection prevention. `ai_coordination.py` has `_HARNESS_CLI_WHITELIST` (8 tools). These are **different sets**. The runtime has `aq-context-bootstrap`, `aq-context-manage`, `aq-feedback-loop`, `aq-introspection-validate`, `aq-memory`, `aq-operational-perspective`, `aq-runtime` that the executor whitelist does not have. Neither sanitizes the `args` array beyond blocklist chars. A model call like `run_harness_cli(tool="aq-qa", args=["0; rm -rf /"])` would be blocked by `_ARG_BLOCKLIST_CHARS` (`;&|><\`\n\r`) but `0$(reboot)` would pass through since `$` and `(` are not in the blocklist.

**Recommendation:** Add `$`, `(`, `)` to `_ARG_BLOCKLIST_CHARS`. Or better: validate each arg against `[a-zA-Z0-9._@/-]+` allowlist instead of blocklist.

---

## 3. Memory and Context Management

### Conversation History Threading

The agent does **not** thread prior conversation turns across tasks. Each task invocation starts with a fresh `messages` list (`agent_executor.py:750-758`). Working memory prefetch at startup (`_execute_with_tools:771-790`) fetches 3 prior semantic memory entries and injects them as `PRIOR WORKING MEMORY` in the system prompt. This is the only cross-session continuity.

For `local_agent_runtime.py`, the coordinator builds `messages` from the original request's `messages` field, so multi-turn conversation history IS propagated there — but only for the non-tool-use path.

### Two-Phase Token Budget (512/1200) — Correct But Fragile

Implementation at `agent_executor.py:1035`:
```python
call_max_tokens = AGENT_TASK_MAX_TOKENS if tool_call_count > 0 else AGENT_TOOL_CALL_MAX_TOKENS
```

`AGENT_TOOL_CALL_MAX_TOKENS=512`, `AGENT_TASK_MAX_TOKENS=1200` from `shared/llm_config.py`.

The logic is correct. However:

- **First-call synthesis:** If the model answers the question directly on its first response (no tool calls), `tool_call_count == 0` so the synthesis is capped at 512 tokens. A first-call prose answer is capped to 512 even if 1200 would be appropriate. The condition should be `if tool_call_count > 0 OR no tool call was parsed` to use the larger budget when we detect synthesis.
- **`aq-agent-loop` hardcodes LLAMA_MAX_TOKENS=512:** `scripts/ai/aq-agent-loop:~line 180` sets `os.environ["LLAMA_MAX_TOKENS"] = os.environ.get("LLAMA_MAX_TOKENS", "512")`. This env var is checked in some paths but `agent_executor._call_llama` uses `AGENT_TOOL_CALL_MAX_TOKENS` and `AGENT_TASK_MAX_TOKENS` constants from `llm_config.py`, not `LLAMA_MAX_TOKENS`. So the env var comment is misleading — it doesn't actually cap agent_executor. This could confuse future maintainers.

### Context Pruning Strategy

`agent_executor.py:987-1030` implements pinned+sliding: PINNED=messages[0:4] (system+user+first assistant+first tool result), SLIDING=messages[-4:] (last 2 assistant+tool pairs). This is a sound strategy for preserving the task objective and most recent work. The `_store_prune_checkpoint` fires-and-forgets the dropped middle messages to working memory.

**Gap:** The char budget check (`_ctx_chars > _CTX_CHAR_BUDGET`) uses a coarse 12,000-char estimate that maps to ~3000 tokens at 4 chars/token. For Chinese text or code-heavy output, the ratio can be 2:1 (6000 chars = 3000 tokens). The budget may be too conservative for English and too aggressive for mixed-language output. This is probably acceptable given the Renoir APU context limit of 8192 tokens.

**Gap:** When `len(messages) > 6` but `<= 8`, the fallback prune (`messages[:2] + messages[4:]`) drops messages[2:4] (first assistant+tool) — exactly the PINNED content that should be preserved. This edge case should apply the same PINNED+SLIDING logic instead.

### PRE-FLIGHT RESEARCH Block

The `_get_system_prompt` for `AgentType.AGENT` mandates `get_hint + query_aidb(collection='error-solutions') + get_working_memory` before touching any file. The working memory prefetch (lines 771-790) covers `get_working_memory` at loop start. The system prompt instructs the model to call all three. These add 3 serial HTTP round trips (~500ms each on local stack = ~1.5s overhead per task start).

The quality improvement from pre-flight is genuine — `error-solutions` has 66+ seeded patterns. But the model sometimes treats these 3 calls as satisfying the `_MAX_OBSERVATIONS_WITHOUT_ACTION=6` observation budget early, leaving only 3 more query calls before stagnation detection fires. This is tight for research tasks.

---

## 4. AIDB Integration

### `query_aidb_handler` Routing — CORRECT (Phase 175 fix)

`ai_coordination.py:785-803` now correctly routes harness-seeded collections:
- `_QDRANT_COLLECTIONS` frozenset covers the 14 real collection names
- Routes to `_query_qdrant_direct()` (embed via llama-embed:8081 + Qdrant:6333)
- Falls back to AIDB pgvector only for non-harness collections

The ALLOWED_COLLECTIONS fix from Phase 175 is confirmed present. The `discover_objectives` handler at line 452 also correctly uses `/vector/search` directly.

### `collective_memory_search_handler` — INCOMPLETE

`ai_coordination.py:838-852` calls `AIDB_URL/vector/search` with `collection="knowledge"`. But `"knowledge"` IS in `_QDRANT_COLLECTIONS` frozenset (line 778). Yet `collective_memory_search_handler` does NOT call `_query_qdrant_direct` — it goes directly to AIDB pgvector. This is inconsistent with the routing logic in `query_aidb_handler`.

**Bug:** `collective_memory_search_handler` should use `_query_qdrant_direct(query, "knowledge", limit)` to match the routing in `query_aidb_handler`. Currently these two handlers produce different results for the same `"knowledge"` collection.

**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py:838-852`

### Fallback Path: Direct Qdrant

`_query_qdrant_direct` (lines 725-770) correctly embeds via llama-embed:8081 and searches Qdrant:6333. The deduplication by title is a good touch.

**Gap:** No timeout on the embed step beyond httpx default (5s per connection). If llama-embed is busy serving the main llama.cpp model during a concurrent generation, the embed request will block. A 20s timeout is set (`timeout=20.0`) which is probably correct but tight during heavy APU load.

**Gap:** `_query_qdrant_direct` constructs the Qdrant search URL as `{qdrant_url}/collections/{collection}/points/search`. This is Qdrant REST v1.x. If Qdrant is upgraded to v2.x which uses a different API path, this silently fails with 404 and returns `{"success": False}`. No version check.

---

## 5. Reliability / Failure Mode Analysis

### Subprocess Crash Handling

If `local_agent_runtime.py` crashes (non-zero returncode), `ai_coordinator_handlers.py:1383-1406` reads stderr[:500] and attempts JSON parse to distinguish `local_agent_timeout` vs `local_slot_busy` vs generic failure. This is correct.

**Gap:** If the subprocess crashes due to an OOM kill (SIGKILL, returncode=-9), stderr may be empty. The code falls through to the generic `local_agent_failed` 500 response. No distinction between OOM kill and logic error. Consider logging `proc.returncode` in the error payload for diagnostics.

**Gap:** `_DELEGATE_TASK_REGISTRY` is a module-level dict. Async tasks in `_run_async_delegate` update this dict but if the coordinator restarts while tasks are pending, all in-flight async task states are lost. The poll URL returns 404 after restart. No persistence of async task state. For tasks taking 20-40 minutes, this is a real data loss scenario.

### Timeout Configuration Mismatch

- `aq-agent-loop` default: `--timeout 300` (seconds) per-inference, sets `LLAMA_CHUNK_TIMEOUT = max(900, timeout*2) = 900s`
- `local_agent_runtime.py` default: `AGENT_TIMEOUT = 600s` (total wall clock for the subprocess)
- Coordinator `_DELEGATE_DEFAULT_TIMEOUT_S = 240s` (from routing policy defaults)
- `_spawn_local_agent` waits `asyncio.wait_for(proc.communicate(), timeout=timeout_sec)` where `timeout_sec` is `local_agent_timeout_s = max(1.0, timeout_s - min(slack, timeout_s * 0.125))`

With default `timeout_s=240s`: `local_agent_timeout_s ≈ 240 - 30 = 210s`. The coordinator kills the subprocess after 210s. But `local_agent_runtime.py`'s own wall-clock timeout is 600s. The coordinator's outer timeout dominates and the inner timeout never fires. The inner 600s default is thus unreachable via the coordinator path and can mislead operator configuration.

### Synthesis Truncation Bug (512-cap) — VERIFIED FIXED

`agent_executor.py:1035` correctly uses `AGENT_TASK_MAX_TOKENS=1200` when `tool_call_count > 0`. The fix from Phase 159 is confirmed present.

### Resource Leaks

- **SQLite audit DB:** `tool_registry.py:_audit_tool_call` opens `conn = sqlite3.connect(db_path)` and calls `conn.commit(); conn.close()` on every tool call. This is synchronous I/O inside an async context. Under load (many tool calls), this adds latency.
- **`_agent_event_seq` dict:** Populated on `_emit_agent_event`, cleaned up in `_emit_terminal_agent_event`. If a task crashes before the terminal event fires, the task_id entry leaks. Not a serious leak (small dict) but it grows monotonically if tasks crash at the right time.
- **Async subprocess zombies:** `proc.kill()` without `await proc.wait()` in the timeout handler (`ai_coordinator_handlers.py:1373-1376`). The OS will reap the zombie eventually but it sits as Z state until the coordinator's event loop ticks. Under rapid timeout bursts this could accumulate.
- **`_DELEGATE_TASK_REGISTRY` growth:** TTL-based cleanup happens only on read (`handle_ai_coordinator_delegate_status:2784`). If callers never poll the status, entries accumulate until coordinator restart. TTL is 600s but cleanup is lazy. No background sweeper.

---

## 6. Training Data Quality

### Timestamp Format — INCONSISTENT

`agent_executor.py:466`:
```python
"ts": datetime.now(timezone.utc).isoformat() + "Z",
```
`isoformat()` produces `2026-06-17T20:08:01.123456+00:00`, then `+ "Z"` appends Z, yielding `2026-06-17T20:08:01.123456+00:00Z` — a double-suffix that is NOT valid ISO 8601.

`_emit_step_telemetry` at line 887 uses `strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"` — this correctly produces `2026-06-17T20:08:01.123456Z`.

`aq-agent-loop` emit at the wrapper level (line ~93) uses `.isoformat().replace("+00:00", "Z")` — this correctly produces `2026-06-17T20:08:01.123456Z`.

**So `_emit_agent_event` (the main event emitter) produces malformed timestamps in `agent-run-events.jsonl`, while `_emit_step_telemetry` (training signal) produces correct ones.** Any consumer parsing `agent-run-events.jsonl` timestamps with `datetime.fromisoformat()` on Python < 3.11 will crash (Python 3.11+ accepts the double-suffix).

**File:** `ai-stack/local-agents/agent_executor.py:466` — change to `.isoformat().replace("+00:00", "Z")`.

### `tool_result` Events — Correct Format

`_emit_step_telemetry:921-939` uses `json.dumps(tc_result.result)[:1500]` — correct JSON serialization, not Python repr. The query and response fields are correctly populated.

### `agent_step_complete` Training Signal

`agent_executor.py:654-670` emits `agent_step_complete` with `useful_ratio: 1.0`. The MEMORY.md note about `training_ingest` quality score being too harsh for structured outputs was addressed in a prior phase. Confirmed no `frequency_penalty` in `build_llama_payload` for agent calls (uses `repeat_penalty` instead).

### Training Ingest Subprocess Spawning

`agent_executor.py:677-687` spawns `training_ingest.py --hours 2` via `asyncio.create_task(asyncio.to_thread(subprocess.run(...)))` after every completed task. This is a nested async→thread→subprocess pattern. On APU under load, a training ingest scan of 2 hours of telemetry takes 5-30s. Since it's fire-and-forget this is acceptable but it adds process count pressure.

---

## 7. What's Working Well

1. **Stagnation detection is comprehensive and calibrated.** Five distinct guards (identical-result, file-not-found, per-tool-failure, exploration, observation) with appropriate thresholds and soft nudges before hard abort. The validation stall nudge is particularly thoughtful.

2. **Context pruning (pinned+sliding) is architecturally sound.** Preserving the first 4 messages (task anchor) prevents the most common local-model failure mode where the model forgets what it was asked to do by step 6.

3. **`query_aidb_handler` routing is correct post-Phase 175.** The `_QDRANT_COLLECTIONS` frozenset approach is clean — explicit membership check, no guessing.

4. **Two-runtime architecture is pragmatic.** `local_agent_runtime.py` for fast coordinator-spawned single-turn tasks, `agent_executor.py` for heavy multi-turn loops via `aq-agent-loop`. The separation is reasonable even if the boundary is implicit.

5. **Hot-swap tool injection** (`_refresh_active_tools`) is elegant — monotonic expansion based on result content, never shrinks, max_tools guard. Combined with progressive disclosure in system prompt, this keeps context lean.

6. **Circuit breaker for llama.cpp** (`_llama_cb_is_open()` at line 910) prevents queue pile-up during model unavailability. 3-failure threshold + 30s reset is sensible for a single-slot server.

7. **`_HARNESS_CLI_WHITELIST` + arg blocklist** provides meaningful defense-in-depth even if imperfect.

8. **Terminal tool gate** for `discover_objectives` is correctly wired — injects synthesis nudge and returns, preventing the model from acting before user approval.

---

## 8. Priority Recommendations (Ranked by Severity)

### P1 — CRITICAL

**8.1 — `collective_memory_search_handler` bypasses Qdrant routing (collection="knowledge" goes to AIDB pgvector, not Qdrant)**  
File: `ai-stack/local-agents/builtin_tools/ai_coordination.py:838-852`  
Fix: Replace the body with `return await _query_qdrant_direct(query, "knowledge", limit)`.  
Impact: Silent wrong results on every `collective_memory_search` call.

**8.2 — `_emit_agent_event` produces malformed timestamps (`+00:00Z` double-suffix)**  
File: `ai-stack/local-agents/agent_executor.py:466`  
Fix: Change `datetime.now(timezone.utc).isoformat() + "Z"` → `datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")`.  
Impact: Downstream timestamp parsers (Python < 3.11, ISO 8601 strict parsers) will crash or produce wrong times on every agent-run-events.jsonl entry.

**8.3 — `_sanitize_json` misses `\x08` and other control chars (< 0x20 except \n\r\t)**  
File: `ai-stack/local-agents/tool_registry.py:605-616`  
Fix: Add `elif ord(ch) < 0x20: result.append(f"\\u{ord(ch):04x}")` as catch-all.  
Impact: Model emitting backspace/other control chars in tool call JSON silently aborts tool loop — treated as prose final answer.

### P2 — HIGH

**8.4 — Subprocess zombie leak: `proc.kill()` without `await proc.wait()`**  
File: `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py:1373-1376, 1362`  
Fix: Add `await asyncio.shield(proc.wait())` (with timeout guard) after `proc.kill()`.  
Impact: Zombie accumulation under timeout bursts.

**8.5 — `_DELEGATE_TASK_REGISTRY` has no background TTL sweeper**  
File: `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py:1659-1708`  
Fix: Add `asyncio.create_task(_sweep_delegate_registry())` at module init with periodic cleanup.  
Impact: Memory leak on coordinators with many async delegate requests and no polling callers.

**8.6 — Shell injection vector: `$` and `()` not in `_ARG_BLOCKLIST_CHARS`**  
File: `ai-stack/agents/runtimes/local_agent_runtime.py:90`  
Fix: Either add `$(){}` to the blocklist OR switch to allowlist validation `re.fullmatch(r'[a-zA-Z0-9._@/-]+', arg)`.  
Impact: Potential command injection if model is manipulated into calling `run_harness_cli` with crafted args.

**8.7 — First-call synthesis capped at 512 tokens even for direct-answer tasks**  
File: `ai-stack/local-agents/agent_executor.py:1035`  
Fix: Check if no tool call was parsed: `call_max_tokens = AGENT_TASK_MAX_TOKENS if (tool_call_count > 0 or not self.tool_registry.parse_tool_call_from_llama(response)) else AGENT_TOOL_CALL_MAX_TOKENS` — but simpler is to just use a 3-way: 512 for call 0, 1200 for call 1+. Alternatively, apply AGENT_TASK_MAX_TOKENS whenever the previous response had no tool call.  
Impact: Multi-sentence answers on call 0 are cut off at ~512 tokens.

### P3 — MEDIUM

**8.8 — Two divergent runtimes: `local_agent_runtime.py` (simple, from coordinator) vs `agent_executor.py` (rich, from aq-agent-loop)**  
File: `ai-stack/agents/runtimes/local_agent_runtime.py` vs `ai-stack/local-agents/agent_executor.py`  
Fix: Document the split explicitly, or route coordinator's `local-tool-calling` profile through `aq-agent-loop` wrapper instead of `local_agent_runtime.py`.  
Impact: Agentic tasks routed via aq-chat → coordinator get the weaker runtime with no stagnation guards, no context pruner, no two-phase budget.

**8.9 — `context_prune` edge case: 6 < len <= 8 drops pinned content**  
File: `ai-stack/local-agents/agent_executor.py:1026-1028`  
Fix: Apply `pinned = messages[:2]; sliding = messages[-2:]; messages = pinned + sliding` for the 6-8 length case.  
Impact: Model loses task objective in the middle of a short tool sequence.

**8.10 — SQLite audit I/O is synchronous inside async context**  
File: `ai-stack/local-agents/tool_registry.py:_audit_tool_call`  
Fix: Wrap with `await asyncio.to_thread(...)` or use aiosqlite.  
Impact: Latency spike on every tool call on I/O-constrained APU.

**8.11 — Async task registry `_DELEGATE_TASK_REGISTRY` lost on coordinator restart**  
File: `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py:1659`  
Fix: Persist registry to a temp file on write; load on startup.  
Impact: All in-flight 20-40 minute async agent tasks lose state on restart. Callers see 404 on poll.

**8.12 — `delegate_to_remote_handler` timeout is 60s for a task that routes back to the coordinator**  
File: `ai-stack/local-agents/builtin_tools/ai_coordination.py:129`  
Fix: Increase to 300s minimum to match the coordinator's local agent dispatch time. A local agentic task can take 5-10 minutes.  
Impact: Tool call returns "timeout" for tasks that would have succeeded.

### P4 — LOW / INFORMATIONAL

**8.13 — `LLAMA_MAX_TOKENS` env var set by aq-agent-loop is not used by agent_executor._call_llama (misleading comment)**  
File: `scripts/ai/aq-agent-loop:~180`  
Fix: Remove the `LLAMA_MAX_TOKENS` env var assignment or add a comment that it only affects `local_agent_runtime.py` (non-executor path).

**8.14 — `_load_prompt_extensions` cached per-instance but executor is recreated per aq-agent-loop call**  
File: `ai-stack/local-agents/agent_executor.py:1817-1851`  
Note: Caching is per-instance which means per task invocation. On APU, each YAML read is ~1ms so this is not a problem. The comment "only changes with a rebuild" is correct. No action needed.

**8.15 — `run_harness_cli` whitelist divergence between `local_agent_runtime.py` and `ai_coordination.py`**  
File: `ai-stack/local-agents/builtin_tools/ai_coordination.py:963-967` vs `ai-stack/agents/runtimes/local_agent_runtime.py:92-103`  
Fix: Extract to a shared config constant.  
Impact: Operator adding a new aq-* CLI tool must update two files or the tool will be available via one path but not the other.

---

## Summary Table

| # | Severity | File | Issue |
|---|----------|------|-------|
| 8.1 | CRITICAL | ai_coordination.py:838 | collective_memory_search wrong store (pgvector vs Qdrant) |
| 8.2 | CRITICAL | agent_executor.py:466 | malformed timestamp `+00:00Z` |
| 8.3 | CRITICAL | tool_registry.py:606 | `_sanitize_json` misses `\x08` |
| 8.4 | HIGH | ai_coordinator_handlers.py:1373 | zombie subprocess on timeout |
| 8.5 | HIGH | ai_coordinator_handlers.py:1659 | registry memory leak |
| 8.6 | HIGH | local_agent_runtime.py:90 | `$()` shell injection vector |
| 8.7 | HIGH | agent_executor.py:1035 | 512-cap on direct-answer call 0 |
| 8.8 | MEDIUM | both runtimes | divergent path — weaker runtime from coordinator |
| 8.9 | MEDIUM | agent_executor.py:1026 | context prune drops pinned at 6 < len ≤ 8 |
| 8.10 | MEDIUM | tool_registry.py:_audit | sync SQLite in async context |
| 8.11 | MEDIUM | ai_coordinator_handlers.py:1659 | async registry lost on restart |
| 8.12 | MEDIUM | ai_coordination.py:129 | 60s timeout for delegate_to_remote |
| 8.13 | LOW | aq-agent-loop:180 | LLAMA_MAX_TOKENS misleading comment |
| 8.15 | LOW | both files | run_harness_cli whitelist divergence |

---

*Review complete. Three findings warrant immediate fixes before any future phase work: (8.1) wrong Qdrant routing for collective_memory_search, (8.2) malformed timestamps corrupting agent-run-events.jsonl, (8.3) incomplete JSON sanitizer allowing silent tool call drops on control char injection.*
