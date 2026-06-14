# PRD: aq-chat Unified Routing & Tool-Calling Architecture
## Status: LOCKED — All teams APPROVED — Ready for Plan Drafting
## Version: 0.3 (locked; all divergences resolved)

**Date:** 2026-06-14
**Locked by:** Claude (consolidator/orchestrator)
**Sign-off round complete:** Claude team ✓ · Gemini team ✓ · Codex team ✓ · Local/Qwen3 [proxy] ✓
**All 6 divergences resolved** (see §11 for resolution record)
**PRD is locked.** No further revisions without new sign-off round.
**Next phase:** Implementation plan drafting — same 7-role team composition per agent, parallel fan-out.
**Problem domain:** aq-chat routing, tool registry parity, intent classification, agent observability

---

## Consolidation Notes

This document synthesizes all four independent PRD drafts. Where all teams converged, the
consensus position is stated directly. Where teams diverged, the divergence is preserved
verbatim in §11 (Divergence Register) and flagged inline with `[DIVERGENCE: Dx]`. No
divergence has been resolved by the consolidator — resolution requires full team sign-off.

**v0.3 changes from v0.2 (lock round):**
- All 6 divergences resolved; resolutions recorded in §11
- Factual correction: §4.1 "3 keyword lists" → "2 confirmed lists" (switchboard.py has none — confirmed by Claude team grep)
- Factual correction: `continue-local` 768-token "ceiling" is a caller-default in `local_agent_runtime.py`, NOT a profile ceiling; fast-path caller sets `max_tokens=1024` explicitly
- Phase D implementation note added: fast-path payload MUST set `max_tokens=1024` explicitly
- Phase E watchdog clarification: timer resets on ANY `_emit_agent_event()` call, not only step-start
- Phase E events: `seq` field (monotonic integer, per-task) added for unambiguous ordering
- OQ-E1 resolved: shared `agent-run-events.jsonl` (D6 resolution)
- OQ-E2 resolved: use `asyncio.get_running_loop().call_later()` (Python 3.10+ correct form)
- AC-E5 upgraded: schema-level field-name check (no forbidden field names), not runtime grep
- Phase A prerequisite: async execution model check before adding coordination tools
- Tool parity contract: machine-generated from `ai_coordination.py`, not hand-maintained
- Individual team drafts/sign-offs were used as provenance for this locked document.
  They are intentionally local-only artifacts; the consensus decisions are folded into
  this consolidated PRD and the locked implementation plan.

**PRD is locked.** All implementation plans reference this document as the canonical spec.
Implementers must follow phase ordering: A → B → C → D (unblocked) → E.
Phase D required D1/D2 resolution — both now resolved (see §11).

---

## 1. Executive Summary

`aq-chat` is the primary interactive terminal for the local AI stack. After Phase 169
(c028c2d8, f86f5f9e), it routes local profile turns through the coordinator delegate path
and injects the harness system prompt — achieving partial parity with autonomous
`delegate-to-local --mode agent` dispatches. Five structural issues remain.

**Critical finding confirmed by Gemini team (authoritative — file read directly):**
The coordinator delegate path spawns `local_agent_runtime.py` which defines its own
hardcoded `TOOL_SCHEMAS` containing exactly **3 tools**: `route_search`, `recall_memory`,
`run_harness_cli`. The autonomous delegation path (`aq-agent-loop`) registers **29 tools**
via `build_registry()`. Interactive sessions have ~90% fewer tools than autonomous sessions.
The aq-chat `/tools` slash command displays the Phase 11 registry (29 tools) — this is
**actively misleading**. The display does not reflect what is actually available during an
interactive turn.

**Secondary finding (all three remote teams):**
Three independent keyword lists govern tool-free turn detection: one in `aq-chat` (lines
165-169), one in `ai_coordinator_handlers.py` (lines 1491-1493), and one in `switchboard.py`.
These can drift silently. No shared source of truth.

**New finding from Local team (Issue 6 — first-class, not polish):**
`aq-agent-loop` emits only post-tool-completion checkpoints to `.log.steps.jsonl`. There is
no real-time event stream: no event when LLM generation starts, no tool intent event before
execution, no synthesis-start event, no task-complete event in `agent-run-events.jsonl`.
Monitoring long-running local inference tasks requires schedule-based polling. This prevents
event-driven orchestration, pipeline chaining, and immediate stall detection.

**Outcome of this PRD:** Unified routing contract, transparent HUD, single intent classifier,
tool parity fix for `local_agent_runtime.py`, reduced coordinator overhead on conversational
turns, a single coherent tool-disable mechanism, and a real-time agent event stream.

---

## 2. Mission

Deliver full parity between interactive `aq-chat` sessions and autonomous
`delegate-to-local --mode agent` dispatches:
- Identical tool access (same 14 AI coordination tools available in both paths)
- Transparent routing (HUD shows actual wire profile and tool state)
- Intent-driven mode selection (shared classifier, not duplicated keyword lists)
- Minimal coordinator overhead on non-agentic turns (direct path for conversational queries)
- Single orthogonal tool-disable mechanism

The organization operates as a flat collaborative software factory. This PRD is the
agreed contract for all agent teams before any implementation begins.

---

## 3. Scope

### 3a. In Scope

- `local_agent_runtime.py` tool schema expansion to include the 14 AI coordination tools
  (verified gap — top priority fix)
- HUD transparency: display actual wire profile, tool mode, and tool count per turn
- Single shared intent classifier replacing the three independent keyword lists
- Conversational fast-path: bypass coordinator subprocess overhead for non-agentic turns
- `ToolMode` enum replacing `local_tools_enabled` + `tool_free_turn` dual controls
- `/tools` command correction: display runtime-actual tool set, not Phase 11 registry
- `routing_decision` telemetry event on every turn
- Training data fix: feedback records effective wire profile, not `active_profile`
- Tool parity contract: machine-readable manifest + aq-qa CI check

### 3b. Out of Scope

- AppArmor profile changes (non-negotiable constraint)
- Dashboard UI changes (Codex dashboard branch — do not conflict)
- `delegate-to-local`, `aq-agent-loop`, autonomous delegation path changes
- Remote profile routing (remote-gemini, remote-coding, remote-reasoning)
- Training pipeline, continuous learning, or telemetry consumers
- New auth surfaces or credential changes
- Coordinator-side refactors beyond minimal phrase-alignment and optional fast-path guard
- `ralph-wiggum` agent path

### 3c. Constraints (Non-Negotiable)

| Constraint | Contract |
|---|---|
| NixOS-first | No bare pip install. Nix store layout compatible. |
| Port SSOT | All ports from `nix/modules/core/options.nix`. Never hardcode. |
| `enable_thinking` | `chat_template_kwargs: {"enable_thinking": false}` in every llama.cpp request — at aq-chat payload level, not relying on downstream injection |
| GPU layers | Ceiling = 12 (Renoir APU, 4 GB VRAM shared) |
| n_ctx | 8192 tokens. Tool schema expansion must be audited for token cost. |
| `frequency_penalty` | 0.0 on all structured output requests |
| No new auth surfaces | No new coordinator or switchboard endpoints requiring auth |
| No AppArmor changes | All AppArmor profiles frozen for this PRD scope |
| Codex branch isolation | Do not touch dashboard routes, frontend, or `aistack.py` |
| Tool schema budget | Current 3-tool TOOL_SCHEMAS ≈ 350 tokens. Budget ≤ 800 tokens for expanded schemas. Test with 8 tools before committing to all 14. |

---

## 4. Current State Architecture

### 4.1 aq-chat Interactive Turn Flow (confirmed by all three teams)

```
user turn
  → AQChat._stream_chat()
      ├─ _should_use_local_snapshot(prompt)        [keyword: status/health/etc.]
      ├─ _should_bypass_tools_for_turn(prompt)     [keyword: TOOL_FREE_PHRASES — list 1 of 3]
      │
      ├─ if profile in {local,local-tool-calling} OR local_snapshot OR tool_free_turn:
      │     POST coordinator:8003/control/ai-coordinator/delegate
      │       payload.profile = "local-tool-calling"  (if tools enabled & !tool_free)
      │       payload.profile = "default"             (if tools disabled OR tool_free)
      │         → ai_coordinator_handlers.py
      │             _is_tool_free check              [keyword list 2 of 3]
      │             _spawn_local_agent_with_lease()
      │               subprocess: local_agent_runtime.py
      │                 TOOL_SCHEMAS (hardcoded) = [route_search, recall_memory, run_harness_cli]
      │                 POST switchboard:8085 (profile-dependent)
      │                   → llama.cpp:8080
      │
      └─ else: POST coordinator:8003/v1/orchestrate (SSE)

switchboard.py — NO independent phrase list confirmed by Claude team grep (PRD v0.1 claim of "3 of 3" was inaccurate; only 2 confirmed phrase lists)
```

**HUD**: `[{self.active_profile}]` — always `"local"` (default CLI arg). Never reflects
actual wire profile (`local-tool-calling` or `default`). Never shows tool count or mode.

### 4.2 Autonomous Delegation Turn Flow

```
delegate-to-local --mode agent
  → dispatch.py AgentRunner
      → subprocess: aq-agent-loop
          → build_registry()  [Phase 11 ToolRegistry]
              register_file_tools()           # ~5 tools
              register_shell_tools()          # ~5 tools
              register_git_tools()            # ~5 tools
              register_ai_coordination_tools() # 14 tools (get_hint, store_memory, etc.)
          → LocalAgentExecutor.execute_task()
              → POST llama.cpp:8080 directly
```

### 4.3 Confirmed Gap Table

| Dimension | Interactive (aq-chat) | Autonomous (delegate-to-local) | Gap |
|---|---|---|---|
| Tool count | 3 (hardcoded in local_agent_runtime.py) | 29 (Phase 11 build_registry) | 26 tools missing |
| AI coord tools | 0 of 14 available | 14 of 14 available | ALL missing |
| Tool display (/tools) | Shows 29 (Phase 11 — WRONG) | N/A | Actively misleading |
| HUD profile shown | "local" | N/A | Wrong |
| Wire profile sent | "local-tool-calling" | N/A | Split |
| Intent classification | 3 independent keyword lists | dispatch.py classify_mode() | Fragile |
| Coordinator overhead | ~80-300ms + spawn every turn | 0 (direct llama.cpp) | Unnecessary for chat |
| Training data label | "local" (wrong) | Correct | Corrupted feedback signal |

### 4.4 Dual Control Asymmetry (confirmed by all three teams)

`local_tools_enabled=False` (session `--no-tools`) → `profile="default"`, `role="reviewer"`,
no system message injection.

`local_tools_enabled=True` + `tool_free_turn=True` (per-turn keyword) → same `profile="default"`
BUT additionally injects `TOOL-FREE TURN:` system message.

Same coordinator payload, different system message. Undocumented, untested, asymmetric.

---

## 5. Proposed Architecture

### 5.1 Design Principles (all three teams converged)

1. **Single bypass authority** — one classifier, one location, drives both aq-chat payload
   construction and any coordinator-side tool suppression.
2. **Tool registry parity by contract** — a manifest lists required tools for the interactive
   path; CI enforces that `local_agent_runtime.py` satisfies it.
3. **Conservative intent default** — classifier defaults to `"agentic"` on ambiguity. Only
   classify as `"conversational"` on high-confidence short queries with no action verbs,
   file/command keywords, or harness-specific terms. Never lose a tool call silently.
4. **Transparent HUD** — what the user sees matches what the coordinator receives.
5. **Single tool-mode signal** — one `ToolMode` with documented precedence rules.
6. **`enable_thinking: false` is the caller's responsibility** — the fast-path payload
   must include `chat_template_kwargs` at aq-chat level, not rely on downstream injection.

### 5.2 Priority-Ordered Component Changes

#### P0 — Fix `local_agent_runtime.py` tool schemas (Issue 2 — CRITICAL)

`local_agent_runtime.py` `TOOL_SCHEMAS` must be expanded to include at minimum the 14 AI
coordination tools from `ai_coordination.py`. Implementation options:

**Option P0-A (preferred — Gemini + Codex):** Add explicit call to
`register_ai_coordination_tools(registry)` in `local_agent_runtime.py` startup, OR extend
`TOOL_SCHEMAS` list to include the 14 tools defined in `ai_coordination.py`.

**Option P0-B (longer-term — Gemini Domain Expert):** Refactor `local_agent_runtime.py` to
import and use the Phase 11 `ToolRegistry` and `register_*` functions directly, achieving full
code-path unification. Higher fidelity but requires verifying the subprocess import chain.

**Constraint:** Current 3-tool schema ≈ 350 tokens. Adding all 14 AI coordination tools
estimated at 800 additional tokens. Total ≤ 800 token budget for all tool schemas. Test with
8 tools first; add remaining 6 only after confirming no n_ctx overflow at 8192.

**Acceptance gate:** `aq-chat /tools` shows same AI coordination tool names as
`build_registry()` in `aq-agent-loop`. Contract test in CI.

#### P1 — Shared Intent Classifier (`scripts/ai/lib/chat_intent.py`)

A new standalone module: `classify_chat_intent(prompt: str, messages: list) -> TurnClassification`.

```python
@dataclass
class TurnClassification:
    intent: str          # "conversational" | "agentic" | "tool_free_explicit" | "spec_only"
    tool_mode: ToolMode
    effective_profile: str
    bypass_reason: Optional[str]
    snapshot_needed: bool
```

- **Pure function** — no network calls, no AIDB queries (Performance Analyst: classifier
  calling `get_hint()` creates a bootstrapping paradox).
- Reuse `classify_mode()` heuristics from `dispatch.py` as implementation basis (Codex).
- Import `BYPASS_PHRASES` and `SPEC_PHRASES` as module-level constants shared with coordinator.
- Conservative: returns `"agentic"` when `confidence < 0.8` or prompt contains any
  file/git/shell/harness keywords.
- Replaces `_should_bypass_tools_for_turn()` in aq-chat.
- Coordinator `_is_tool_free` (line 1491) imports the same phrase constants — no longer
  maintains its own list.

#### P2 — `ToolMode` Enum (replaces dual booleans)

```python
class ToolMode(Enum):
    ENABLED          = "enabled"           # default; tools active
    DISABLED_SESSION = "disabled_session"  # --no-tools flag
    DISABLED_TURN    = "disabled_turn"     # per-turn classifier
```

Precedence (single resolution point `resolve_tool_mode()`):
1. `DISABLED_SESSION` → `profile="default"`, `role="reviewer"`, no system message injection
2. `DISABLED_TURN` → `profile="local-tool-calling"` preserved, `tools=[]`, `tool_choice="none"`,
   inject `TOOL-FREE TURN:` system message
3. `ENABLED` → `profile="local-tool-calling"`, role per caller

This eliminates the asymmetry: `--no-tools` never injects `TOOL-FREE TURN:` system message
(it was never intended for that case). Only `DISABLED_TURN` injects it.

#### P3 — HUD Transparency + Training Data Fix

**HUD format** `[DIVERGENCE: D3 on exact format — see §11]`:
- All teams agree on showing: effective wire profile + tool mode + tool count
- Proposed: `[local | ltc | tools:14] ❯` with `/status` expansion for full names
- CLI UX Designer (all teams): add `--verbose-hud` flag; keep compact default for experienced
  operators; session-start banner prints full resolved routing config

**Training data fix (all teams):** `_write_feedback()` records `profile: effective_wire_profile`,
not `self.active_profile`. Existing `delegation-feedback.jsonl` entries with `profile: "local"`
should be normalized forward (new entries correct); retroactive normalization deferred to
training pipeline owners.

**`/tools` fix (all teams):** Display runtime-actual tool set. `[DIVERGENCE: D5 on format]`.

#### P4 — Conversational Fast-Path `[DIVERGENCE: D1, D2 on implementation — see §11]`

**Convergence:** All teams agree a conversational fast-path should exist that bypasses the full
coordinator subprocess overhead for turns classified as `"conversational"`.

**Divergence on location and profile** — see §11 D1, D2. This phase cannot be implemented
until D1 and D2 are resolved in the sign-off round.

**Conservative eligibility criteria (all teams agree):**
- `intent == "conversational"` from classifier
- `tool_mode == ToolMode.ENABLED` (session tools on, but classifier says none needed)
- `local_snapshot == False`
- No prior tool-call response in `context_history` (not a continuation of an agentic turn)
- On any HTTP error: fall back to coordinator delegate path automatically

**Fallback guard (Gemini + Codex):** If fast-path response contains self-referential regret
phrases ("I cannot access", "I don't have tools"), automatically resubmit via coordinator path
for one retry.

#### P5 — Routing Decision Event Emission

Every non-command turn emits a `routing_decision` event to `agent-run-events.jsonl` via
`asyncio.create_task()` (fire-and-forget, non-blocking):

```json
{
  "event_type": "routing_decision",
  "source": "aq-chat",
  "run_id": "<turn-id>",
  "status": "started",
  "model": "local",
  "route_profile": "<effective_wire_profile>",
  "payload": {
    "intent": "conversational|agentic|tool_free_explicit|spec_only",
    "routing_path": "coordinator-delegate|direct-switchboard|direct-llama",
    "tool_mode": "enabled|disabled_session|disabled_turn",
    "tool_count": 14,
    "fast_path": true,
    "classifier_method": "chat_intent_local",
    "latency_budget_ms": null,
    "snapshot_injected": false
  }
}
```

Emit BEFORE the HTTP request begins — not after — so the event is written even if the
connection fails (Observability Engineer, all teams).

---

## 6. Security & Configuration

### 6.1 No New Auth Surfaces

- Fast-path uses existing switchboard loopback connection (127.0.0.1:8085) — same as
  existing local routes. No new auth headers.
- `chat_intent.py` is a pure Python library — no HTTP surface.
- Tool parity contract YAML/JSON is a static read-only checked artifact.
- `routing_decision` events contain no user prompt content — only metadata/classification.

### 6.2 Port Handling

All fast-path URLs must use env vars: `LLAMA_URL`, `SWITCHBOARD_URL`, `HYBRID_URL` with
defaults matching `nix/modules/core/options.nix`. Never hardcoded.

### 6.3 `enable_thinking: false` Invariant (Critical)

The fast-path payload MUST include `chat_template_kwargs: {"enable_thinking": False}` at
aq-chat construction time. Cannot rely on switchboard or coordinator to inject this. Known
failure mode from MEMORY.md: omitting this causes thinking token fill and empty response.

### 6.4 Tool Safety in Fast-Path

Fast-path (direct route, no tools available) must detect if the model emits a tool-call
pattern in its response and surface a warning to the user. Do not silently drop the call —
resubmit via coordinator delegate path for one retry (Gemini).

---

## 7. Implementation Phases

Ordered by risk and dependency. P0 is independent and highest severity. P1 must precede P3
and P4. P4 blocked until D1/D2 resolved.

### Phase A — Tool Registry Fix (P0, no rebuild, high severity, low risk)
1. Read `ai-stack/agents/runtimes/local_agent_runtime.py` — confirm exact tool initialization
   (Gemini found 3 hardcoded tools; Codex flagged as unread — must verify line numbers)
2. Expand `TOOL_SCHEMAS` in `local_agent_runtime.py` to include 14 AI coordination tools
   (start with 8, verify n_ctx, add remaining 6)
3. Write `.agent/tool-parity-contract.json` — canonical required tool list
4. Add aq-qa CI check verifying `local_agent_runtime.py` satisfies contract
5. Fix `/tools` slash command to show runtime-actual tool set `[DIVERGENCE: D5 format TBD]`
6. **Acceptance:** `aq-chat /tools` matches `build_registry()` AI coordination tools

### Phase B — Shared Classifier + ToolMode (P1+P2, no rebuild, medium risk)
1. Create `scripts/ai/lib/chat_intent.py` with `classify_chat_intent()` + `ToolMode`
2. Unit tests: ≥ 30 canonical test cases covering all intent classes (QA, all teams)
3. Refactor `aq-chat` to use `ToolMode` + `resolve_tool_mode()` — same behavior, new internals
4. Coordinator `_is_tool_free` (line 1491) imports shared phrase constants from `chat_intent.py`
5. **Acceptance:** Existing behavior unchanged; `aq-qa 114/114`

### Phase C — HUD Transparency + Training Data Fix (P3, no rebuild, low risk)
1. Update HUD prompt format (format TBD per D3 resolution)
2. Update `/status` to show effective wire profile, tool mode, tool count
3. Fix `_write_feedback()` to record effective wire profile
4. Session-start banner prints full resolved routing config
5. **Acceptance:** `[local]` prompt replaced with profile+tools display; feedback JSONL has
   correct profile field

### Phase D — Conversational Fast-Path (P4, no rebuild, medium risk)
**Blocked on D1 and D2 sign-off resolution.**
1. Implement fast-path branch per resolved D1/D2 design
2. Guard with `--no-fastpath` debug flag (default False)
3. Emit `routing_decision` events (P5)
4. Validate: conversational turn does NOT hit coordinator delegate (mock/log check)
5. **Acceptance:** `p50` conversational turn latency reduced by ≥ 50ms; 114/114 aq-qa

### Phase E — Agent Loop Event Streaming (no rebuild, medium risk) **[NEW — v0.2, Local team]**

`aq-agent-loop` and `agent_executor.py` gain a real-time event stream to
`agent-run-events.jsonl`, enabling push-based monitoring instead of schedule polling.

**Event types:**

| Event | Emission point | Key payload fields |
|---|---|---|
| `agent_step_start` | Top of model-call loop | task_id, step, elapsed_s |
| `agent_tool_intent` | After `parse_tool_call()`, before execution | task_id, step, tool, args_preview (≤200 chars) |
| `agent_tool_result` | After `execute_tool()` returns | task_id, step, tool, ok, ms, elapsed_s |
| `agent_synthesis_start` | No more tool calls, final answer generating | task_id, tool_call_count, elapsed_s |
| `agent_complete` | On task exit (success) | task_id, status, tool_call_count, elapsed_s, output_bytes |
| `agent_failed` | On exception / timeout / abort | task_id, status, error, elapsed_s |
| `agent_stall` | Watchdog: no new event for >300s | task_id, last_step, stall_s |

**All writes are async fire-and-forget** (`asyncio.create_task()`). Never block the agent loop.

**Implementation steps:**
1. Add `_emit_agent_event(event_type, **fields)` helper to `aq-agent-loop`
2. Add same helper to `agent_executor.py` (coordinator delegate path)
3. Add `asyncio.get_event_loop().call_later(300, emit_stall)` watchdog, reset on each step
4. `[DIVERGENCE: D6]` on event schema location — see §11
5. Security gate: no user prompt content in any event; `args_preview` truncated to 200 chars

**Monitor integration:** Consumer watching `agent-run-events.jsonl` for
`"event_type":"agent_complete","task_id":"<id>"` fires immediately — ScheduleWakeup
becomes fallback-only (process died / hung), not the primary signal.

**Acceptance gates (AC-E1 through AC-E5):**
- AC-E1: `agent_tool_intent` event appears before tool executes (log sequence test)
- AC-E2: `agent_complete` event appears within 5s of task exit (timing test)
- AC-E3: `agent_stall` event fires after 300s step silence (watchdog test)
- AC-E4: End-to-end: Monitor watching `agent_complete` fires without ScheduleWakeup
- AC-E5: No user prompt content in any event (security gate — grep audit)

---

## 8. Validation & Success Criteria

| ID | Criterion | Measurement Method |
|---|---|---|
| AC-1 | `local_agent_runtime.py` registers all 14 AI coordination tools | Contract test: load runtime, assert all required tools in TOOL_SCHEMAS |
| AC-2 | `aq-chat /tools` matches `build_registry()` AI coordination tools | Diff `/tools` output vs `aq-agent-loop --list-tools` output |
| AC-3 | HUD shows effective wire profile, not `active_profile` | Unit test `_build_prompt_text()` |
| AC-4 | `_write_feedback()` records effective wire profile | Assert JSONL: profile field != `"local"` when tools active |
| AC-5 | Three keyword lists unified to single source in `chat_intent.py` | Grep: no `TOOL_FREE_PHRASES` outside `chat_intent.py` |
| AC-6 | `classify_chat_intent("what is X")` → `"conversational"` | Unit test |
| AC-7 | `classify_chat_intent("implement X in Y")` → `"agentic"` | Unit test |
| AC-8 | `--no-tools` does NOT inject `TOOL-FREE TURN:` system message | Unit test payload builder |
| AC-9 | Explicit "no tools" phrase DOES inject `TOOL-FREE TURN:` system message | Unit test payload builder |
| AC-10 | Conversational turn does NOT POST to coordinator delegate endpoint | Mock test: assert :8003 not called |
| AC-11 | Agentic turn DOES POST to coordinator delegate | Mock test: assert :8003 called |
| AC-12 | Fast-path payload includes `chat_template_kwargs: {"enable_thinking": False}` | Unit test wire payload |
| AC-13 | `routing_decision` event emitted before HTTP request | Log sequence test |
| AC-14 | 114/114 aq-qa after all phases | `aq-qa 0 --machine` |
| AC-15 | Autonomous delegation path unchanged | `delegate-to-local --mode agent --prompt "list open issues"` succeeds |
| AC-E1 | `agent_tool_intent` event in `agent-run-events.jsonl` before tool executes | Log sequence test |
| AC-E2 | `agent_complete` event appears within 5s of task exit | Timing test |
| AC-E3 | `agent_stall` event fires after 300s step silence | Watchdog test |
| AC-E4 | Monitor watching `agent_complete` fires without ScheduleWakeup | End-to-end integration test |
| AC-E5 | No user prompt content in any event payload | grep audit: no prompt/message field in events JSONL |

---

## 9. Risks & Mitigations

| Risk | Sev | Mitigation |
|---|---|---|
| Tool schema expansion causes n_ctx overflow at 8192 | HIGH | Budget ≤ 800 tokens for all schemas. Test with 8 tools first. Measure before committing to all 14. |
| Intent classifier misclassifies agentic as conversational → tool calls lost | HIGH | Default `"agentic"` on any uncertainty. Detect tool-call patterns in direct-path response; warn + retry via coordinator. |
| `enable_thinking` omitted in fast-path → empty response | HIGH | Explicit `chat_template_kwargs` in aq-chat payload builder. AC-12 validates this. |
| `local_agent_runtime.py` runs as `ai-hybrid` user — tool registration fails | MEDIUM | Tool registration is in-memory only (ToolRegistry objects). No file writes. Verify with test invocation. |
| `_is_tool_free` and classifier drift after future edits | MEDIUM | Both import from shared `chat_intent.py` constants. CI parity test on canonical phrase set. |
| `local_agent_runtime.py` tool schema additions break context (n_ctx=8192) | HIGH | Per constraint: budget 800 tokens max. Measure each addition before committing. |
| Fast-path bypass location creates maintenance divergence (two routing paths) | MEDIUM | Document explicitly in AGENTS.md. Single test validates both paths. |
| Tool parity contract YAML becomes stale after edits to `ai_coordination.py` | MEDIUM | CI lint: regenerate contract when source files change. |
| HUD format change confuses existing users | LOW | `--verbose-hud` flag. Session-start banner explains new format once. |
| `agent-run-events.jsonl` write blocks agent step loop | MEDIUM | Async fire-and-forget via `asyncio.create_task()`. No `await` in hot path. |
| `agent_stall` watchdog fires on legitimate slow generation | MEDIUM | Emit as INFO only. Orchestrator uses as advisory; Phase 165 stagnation guard remains abort authority. |
| Event file owned by ai-hybrid; aq-agent-loop runs as hyperd — append denied | LOW | Verify file ownership/mode. If needed, add tmpfiles `z` rule for group write (0664) per MEMORY.md pattern. |

---

## 10. Open Questions

**OQ-1 — RESOLVED (Gemini team, authoritative):**
`local_agent_runtime.py` contains hardcoded `TOOL_SCHEMAS` with exactly 3 tools:
`route_search`, `recall_memory`, `run_harness_cli`. Phase A fix is confirmed feasible (~2-line
addition or TOOL_SCHEMAS list extension). All teams must review Phase A scope with this fact.

**OQ-2 — UNRESOLVED [DIVERGENCE D1]: Fast-path bypass location**
See §11 D1. Must be resolved before Phase D begins.

**OQ-3 — UNRESOLVED [DIVERGENCE D2]: Conversational path profile + token budget**
See §11 D2. Must be resolved before Phase D begins.

**OQ-4 — UNRESOLVED: Long-term `local_agent_runtime.py` architecture**
Should `local_agent_runtime.py` eventually be refactored to use `ToolRegistry` /
`initialize_builtin_tools()` directly (Gemini Tool Registry Specialist recommendation), or
remain hardcoded-schemas extended by parity contract (Codex Tool Registry Specialist as
safer interim)? Phase A fixes the immediate gap regardless. Long-term architecture is a
follow-on decision — not a blocker for this PRD.

**OQ-5 — UNRESOLVED: Coordinator `routing_metadata` in response**
Codex Observability Engineer: for full HUD accuracy, coordinator should return
`selected_profile` in response body (`X-Routing-Profile` header). Currently out of scope.
File as follow-on issue in `memory/issues-backlog.md` after PRD is locked.

**OQ-6 — UNRESOLVED [DIVERGENCE D5]: `/tools` command display format**
Three proposals. See §11 D5.

**OQ-E1 — UNRESOLVED [DIVERGENCE D6]: Event schema location for agent loop events**
Should `agent_*` events be added to the existing `agent-run-event.schema.json` (unified
telemetry replay, simpler consumer) OR written to `.agents/delegation/outputs/<task-id>.events.jsonl`
per task (task-scoped, cleaner separation, easier Monitor targeting)?
Argument for shared: unified replay across all event types.
Argument for per-task: `agent-run-events.jsonl` is currently coordinator-path; aq-agent-loop
writing to it creates cross-concern coupling. Monitor can target per-task path directly.
**Must resolve before Phase E implementation begins.**

**OQ-E2 — UNRESOLVED: Stall watchdog implementation style**
Thread-based (`threading.Thread`) vs event-loop-based (`asyncio.get_event_loop().call_later()`)
for the stall watchdog in `aq-agent-loop`. Local team recommends `call_later()` to avoid
GIL/loop-thread conflicts in the subprocess environment. Must verify which event loop pattern
`aq-agent-loop` uses before committing.

---

## 11. Divergence Register — ALL RESOLVED (v0.3 locked)

### D1 — Fast-Path Bypass Location — **RESOLVED: aq-chat-direct**
| Votes | Claude ✓ | Gemini ✓ (changed from coordinator-internal) | Codex ✓ | Local [proxy] ✓ |
**Implementation contract:** Conditional branch in `_stream_chat()`. Falls back to coordinator on any HTTP error. Document both paths in AGENTS.md (Phase D acceptance gate). `--no-fastpath` debug flag (default False).
**Note:** `_should_short_circuit_to_continue_local_http()` fires only at `delegated_max_tokens <= 48` — confirmed not a general fast-path. Repurposing it would add coordinator complexity equivalent to aq-chat direct. (Claude team verification.)

### D2 — Conversational Path Profile + Token Budget — **RESOLVED: continue-local with max_tokens=1024**
| Votes | Claude ✓ | Gemini ✓ | Codex (local-tool-calling-notool) | Local [proxy] ✓ |
**Implementation contract:** Fast-path uses `continue-local` profile. `max_tokens` MUST be set explicitly to 1024 in the fast-path payload — do NOT rely on caller defaults (768 is `local_agent_runtime.py`'s default for delegate tasks, NOT a `continue-local` profile ceiling). `continue-local` profile enforces no token ceiling — caller controls budget freely.
**Codex note (documented):** If future operators need a longer budget, use env override for the payload builder; do not change the profile.

### D3 — HUD Display Format — **RESOLVED: compact-three-field**
| Votes | Claude ✓ | Gemini ✓ | Codex ✓ | Local [proxy] ✓ |
**Implementation contract:** `[local | ltc | tools:14] ❯` (compact, three-field). `--verbose-hud` flag expands to full profile names. HUD shows `[local | off | session] ❯` when `ToolMode.DISABLED_SESSION` (not `tools:0`). Session-start banner prints full resolved routing config once per session.

### D4 — Phase Ordering — **RESOLVED: A → B → C → D → E**
All teams agreed. No conflict. Verified: Phase A independent of all others. Phase B before C and D. Phase D unblocked by D1/D2 resolution (now resolved). Phase E last.

### D5 — `/tools` Command Display Format — **RESOLVED: runtime-plus-all**
| Votes | Claude ✓ | Gemini ✓ | Codex ✓ | Local [proxy] ✓ |
**Implementation contract:** `/tools` shows runtime-actual tool set (parity-contract defined), with `[GAP]` prefix on any tool in contract but absent from runtime (Codex addition). `/tools all` shows full Phase 11 `build_registry()` tool list with labels indicating "agent-loop only" where tools are not in the interactive runtime.

### D6 — Agent Loop Event Schema Location — **RESOLVED: shared agent-run-events.jsonl**
| Votes | Claude ✓ | Gemini ✓ | Codex (per-task-file) | Local [proxy] (per-task-file) |
**Implementation contract:** All `agent_*` events written to `agent-run-events.jsonl` via `AQ_AGENT_RUN_EVENTS_PATH` env var (already established in coordinator, aq-report, race-harness — Claude team verification). `task_id` MUST be a mandatory top-level field in every `agent_*` event (not nested under `payload`) to enable `grep task_id <id>` filtering without JSON parsing. Writes use `open(path, 'a')` — POSIX-atomic for lines ≤ PIPE_BUF (Codex Coord verification). Per-task cross-reference: add `session_index` field referencing the run_id for cross-task correlation (Codex mitigation).

**OQ-E1 RESOLVED:** shared `agent-run-events.jsonl` (D6 resolution above).
**OQ-E2 RESOLVED:** Use `asyncio.get_running_loop().call_later(300, emit_stall)` for watchdog. Avoid deprecated `asyncio.get_event_loop()`. Thread-based watchdog is the fallback only if `aq-agent-loop` proves to be synchronous (verify at Phase E step 0). Watchdog timer MUST reset on ANY `_emit_agent_event()` call, not only on `agent_step_start`.

---

## 12. Sign-off Status — LOCKED

| Team | Sign-off | File |
|---|---|---|
| **Claude team** | APPROVED | folded into this consolidated PRD |
| **Gemini team** | APPROVED | folded into this consolidated PRD |
| **Codex team** | APPROVED | folded into this consolidated PRD |
| **Local team** | PROXY (all roles) | folded into this consolidated PRD |

**PRD is LOCKED.** Implementation plan drafting begins immediately.
Plan drafting uses the same 7-role team composition per agent, same parallel fan-out,
same consensus protocol. Implementers reference this document (v0.3) as canonical spec.

---

*Locked by: Claude (orchestrator/consolidator)*
*Source drafts and sign-off files were retained as local provenance only; consensus content is captured here.*
*v0.1: 3-team draft · v0.2: Phase E added, Local proxy, D6 · v0.3: All divergences resolved, locked*
