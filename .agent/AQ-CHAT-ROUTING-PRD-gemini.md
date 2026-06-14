# PRD: aq-chat Unified Routing & Tool-Calling Architecture
## Status: DRAFT — Gemini Expert Team

---

## 1. Executive Summary

`aq-chat` is the primary interactive terminal for the local AI stack. After Phase 169
fixes (c028c2d8, f86f5f9e), it routes local profile turns through the coordinator
`/control/ai-coordinator/delegate` endpoint — the same path used by `delegate-to-local
--mode agent`. Harness system prompts are now injected for local profiles, achieving
partial parity with autonomous agentic dispatches.

However, five architectural inconsistencies remain that prevent full parity, reduce
transparency, and impose unnecessary overhead on every conversational turn:

1. **Profile name/behavior split** — the HUD shows `[local]` but the coordinator
   receives `local-tool-calling`. The user cannot verify what routing is active.
2. **Dual tool registries** — `aq-agent-loop` uses `build_registry()` (14 AI
   coordination tools via the Phase 11 `ToolRegistry`). The coordinator's
   `_spawn_local_agent()` invokes `local_agent_runtime.py`, which defines its own
   hardcoded `TOOL_SCHEMAS` (3 tools: `route_search`, `recall_memory`,
   `run_harness_cli`). Interactive and autonomous paths have materially different
   tool access with no governance contract between them.
3. **Fragile per-turn keyword bypass** — `_should_bypass_tools_for_turn()` uses
   substring matching against `TOOL_FREE_PHRASES`/`TOOL_FREE_SPEC_PHRASES`. The
   coordinator's own `_is_tool_free` logic (line 1491) performs a parallel but
   not identical check. Two independent bypass gates with no shared contract.
4. **Full coordinator overhead on every turn** — conversational queries ("explain X")
   traverse the full delegate pipeline before reaching `local_agent_runtime.py` which
   then calls the switchboard/llama.cpp. Simple turns pay the coordinator+subprocess
   spawn overhead unnecessarily.
5. **Dual redundant controls on tool usage** — `local_tools_enabled` (session-level,
   `--no-tools` flag) and `tool_free_turn` (per-turn keyword detection) both suppress
   tool calling through different code paths with underspecified interaction semantics.

This PRD defines the architecture to resolve all five issues under a single unified
routing contract, without introducing new auth surfaces, changing AppArmor profiles, or
hardcoding ports.

---

## 2. Mission

Deliver full bidirectional parity between interactive `aq-chat` sessions and autonomous
`delegate-to-local --mode agent` dispatches: identical tool access, transparent routing,
minimal coordinator overhead on non-agentic turns, and a single authoritative bypass
decision path shared by both `aq-chat` and the coordinator.

---

## 3. Scope

### 3a. In Scope

- **Issue 1**: Align HUD display with the actual coordinator profile being dispatched.
  Either rename `active_profile` to always reflect the wire profile or add a secondary
  "effective profile" display field.
- **Issue 2**: Audit and align tool sets between `build_registry()` (Phase 11 path) and
  `local_agent_runtime.py` `TOOL_SCHEMAS`. Define a governance contract specifying which
  tools must be present on both paths.
- **Issue 3**: Replace both `_should_bypass_tools_for_turn()` in `aq-chat` and the
  coordinator's inline `_is_tool_free` check with a shared `RoutingIntent` classifier
  that calls (or mirrors) `_classify_routing_intent()` semantics.
- **Issue 4**: Add a fast-path direct-to-llama.cpp route in `aq-chat` for turns
  classified as conversational (no tool need, no local snapshot needed).
- **Issue 5**: Consolidate `local_tools_enabled` and `tool_free_turn` into a single
  canonical `ToolMode` enum (`ENABLED`, `DISABLED_SESSION`, `DISABLED_TURN`) with
  documented interaction semantics and a single code path per mode.
- Observability: emit structured routing decision events so decisions are auditable in
  the dashboard and telemetry pipeline.
- Tests: contract tests verifying parity between `aq-chat` and `aq-agent-loop` tool sets.

### 3b. Out of Scope

- Dashboard UI work (separate Codex branch — do not conflict).
- AppArmor profile changes (non-negotiable constraint).
- New authentication surfaces or credential exposure.
- Coordinator-side refactors beyond what is required for Issue 3 (shared classifier).
- `aq-agent-loop` CLI interface changes.
- Switchboard profile additions or removals.
- Remote agent delegation paths.
- Training pipeline / telemetry ingestion changes.

### 3c. Constraints (Non-Negotiable)

| Constraint | Contract |
|---|---|
| NixOS-first | All service restarts require `nixos-rebuild`. No bare `pip install`. |
| Port SSOT | All ports from `nix/modules/core/options.nix`. Never hardcode. |
| `enable_thinking` | `chat_template_kwargs: {"enable_thinking": false}` in every llama.cpp request. |
| GPU layers | Ceiling = 12 (Renoir APU, 4 GB VRAM shared). Never suggest higher. |
| n_ctx | 8192 tokens for local model. |
| No new auth surfaces | No new endpoints requiring auth. No hardcoded credentials. |
| No AppArmor changes | All AppArmor profiles frozen for this PRD scope. |
| Codex branch isolation | Do not touch dashboard routes, frontend, or `aistack.py`. |

---

## 4. Current State Architecture

### 4.1 Request Flow (Interactive Turn)

```
User input
  → aq-chat._stream_chat()
      → _should_bypass_tools_for_turn()  [LOCAL keyword check]
      → _build_local_snapshot()          [keyword-triggered preflight]
      → _build_coordinator_delegate_payload()
          profile: "local-tool-calling" (if tools enabled) | "default"
      → POST /control/ai-coordinator/delegate  [coordinator :8003]
          → ai_coordinator_handlers.handle_ai_coordinator_delegate()
              → _is_tool_free check  [PARALLEL coordinator keyword check]
              → _spawn_local_agent()
                  → subprocess: local_agent_runtime.py
                      TOOL_SCHEMAS = [route_search, recall_memory, run_harness_cli]
                      POST switchboard/v1/chat/completions [profile-dependent]
```

### 4.2 Request Flow (Autonomous Delegation)

```
delegate-to-local --mode agent
  → dispatch.py AgentRunner
      → subprocess: aq-agent-loop
          → build_registry()  [Phase 11 ToolRegistry]
              register_file_tools()
              register_shell_tools()
              register_git_tools()
              register_ai_coordination_tools()  [14 tools]
          → LocalAgentExecutor.execute_task()
              → POST llama.cpp :8080/v1/chat/completions  [direct]
```

### 4.3 Gap Analysis (All Seven Perspectives)

**Systems Architect — Component Boundary Gaps**

- `aq-chat` and `aq-agent-loop` share no contract document. Two separate tool
  registration code paths exist with no enforcement that they stay in sync.
- The coordinator delegate endpoint is stateless per-request; it cannot signal back to
  `aq-chat` which effective profile was used. The `active_profile` field in `aq-chat`
  state is disconnected from the wire.
- Two bypass decision sites (`aq-chat` line 165, coordinator line 1491) with overlapping
  but non-identical phrase sets — coordination failure risk when phrases are updated in
  one location but not the other.

**Coordinator/Switchboard Domain Expert — Profile Path Gaps**

- `active_profile="local"` in the HUD maps to `profile="local-tool-calling"` in the
  coordinator payload (line 383 of `aq-chat`). The coordinator's `local-tool-calling`
  profile card (switchboard lines 229-255) defines a full self-improvement workflow.
  Users seeing `[local]` in the HUD have no signal that this profile card is active.
- The coordinator's `_spawn_local_agent()` sets `AGENT_TOOLS_ENABLED` from
  `data.get("tools_enabled", False)` (line 1255). The `aq-chat` delegate payload does
  not explicitly set `tools_enabled` — it passes `tools: [], tool_choice: "none"` for
  tool-free turns but relies on the coordinator's `_is_tool_free` detection rather than
  a clean boolean. This is fragile.
- `_should_short_circuit_to_continue_local_http()` in the coordinator (signature read)
  exists as a potential fast-path but is not connected to `aq-chat` conversational turns.

**Tool Registry Specialist — Parity Gaps (CRITICAL)**

Current tool counts per path:

| Path | Registry | Tool Count | Source |
|---|---|---|---|
| `aq-agent-loop` (autonomous) | Phase 11 `ToolRegistry` | 29 (full) / 8 (self-improvement) | `build_registry()` |
| Coordinator `local_agent_runtime.py` | Hardcoded `TOOL_SCHEMAS` | 3 | `local_agent_runtime.py` lines 100-183 |
| `aq-chat` `/tools` display | Phase 11 `ToolRegistry` (client-side) | Same as aq-agent-loop | `_show_tools()` |

The `/tools` slash command in `aq-chat` shows Phase 11 tools (14 AI coordination tools
included). But the actual tools available during an interactive turn are the 3 tools in
`local_agent_runtime.py`. The display is actively misleading.

The 3 runtime tools (`route_search`, `recall_memory`, `run_harness_cli`) are a strict
subset and serve a different abstraction than the 14 Phase 11 AI coordination tools:
- `route_search` → maps to `query_aidb` (partial overlap)
- `recall_memory` → maps to `get_working_memory` (partial overlap)
- `run_harness_cli` → no equivalent in Phase 11 registry

Phase 11 tools with no runtime equivalent: `store_memory`, `get_hint`,
`delegate_to_remote`, `query_context`, `get_workflow_status`, `run_opencode`,
`harness_health`, `get_prsi_pending`, `prsi_orchestrate`, `recommend_agent_for_task`,
`mesh_discovery`, `collective_memory_search`.

**CLI UX Designer — Transparency Gaps**

- The HUD prompt `[local] ❯` does not reveal:
  - Actual coordinator profile (`local-tool-calling` vs `default`)
  - Whether tools are enabled for this turn
  - Whether a local snapshot was injected
  - What tool set is actually available
- `/status` shows "Current Profile: local" — user cannot verify what the coordinator
  will actually receive.
- `/tools` shows 29 Phase 11 tools, but 26 of them are not available in the active
  runtime. This is actively confusing.
- `--no-tools` flag silently switches profile to `"default"` and role to `"reviewer"`,
  but there is no indication of this in the HUD.
- The feedback loop (`/rate`) records `profile: self.active_profile` which is `"local"`,
  not `"local-tool-calling"`. Training data has the wrong profile label.

**Performance Analyst — Overhead Gaps**

- Every `aq-chat` turn, regardless of content ("what is X?", "explain Y"), routes
  through the full coordinator delegate pipeline:
  - HTTP POST to coordinator :8003
  - Coordinator: intent classification, profile selection, delegate planning event
  - `asyncio.create_subprocess_exec()` for `local_agent_runtime.py`
  - Subprocess: context-bootstrap (if enabled), model call via switchboard
  - Response JSON assembly, HTTP response back to aq-chat
- Estimated overhead per conversational turn: 400-800ms coordinator + 200-400ms
  subprocess spawn + `AGENT_BOOTSTRAP_TIMEOUT=15s` potential bootstrap call.
- For a pure "what does X mean?" query, this overhead is wasted entirely.
- `AGENT_MAX_TOKENS=768` (default in `local_agent_runtime.py`) vs `max_tokens=1024`
  in `aq-chat` delegate payload — token budget mismatch creates confusing truncation
  behavior that is invisible to the user.
- Conversational turns that do NOT need tools should bypass coordinator entirely and
  go direct to llama.cpp :8080, reducing latency by ~50-70%.

**Observability Engineer — Event Coverage Gaps**

- `aq-chat` does NOT emit a structured routing decision event (no
  `routing_intent`, `bypass_reason`, or `effective_profile` field in telemetry).
- The `_write_feedback()` method records `profile: self.active_profile` = `"local"`,
  not the effective coordinator profile. Training/feedback data has the wrong label.
- There is no event differentiating "tool-free turn taken" from "tool-calling turn
  taken" in the telemetry stream. Post-hoc analysis of turn types is impossible.
- The coordinator emits a delegation planning event, but the `local_path` field only
  contains `_runtime_path`, not whether the fast-path or full-path was used.
- No metric tracks the ratio of conversational vs agentic turns in `aq-chat` sessions,
  making it impossible to size the coordinator load or justify the fast-path investment.

**QA/Test Engineer — Coverage Gaps**

- No test verifies that `aq-chat` and `aq-agent-loop` expose the same tool set.
- No test verifies that `_should_bypass_tools_for_turn()` and the coordinator's
  `_is_tool_free` check agree on a canonical test set of phrases.
- No regression test for the HUD display showing the correct effective profile.
- No test for the `--no-tools` flag correctly suppressing tool calls in the payload.
- `_show_tools()` in `aq-chat` never validates against the runtime's actual `TOOL_SCHEMAS`.

---

## 5. Proposed Architecture

### 5.1 Design Principles

1. **Single bypass authority** — one classifier, called in one place, drives both
   aq-chat payload construction and coordinator tool suppression.
2. **Tool set parity contract** — a manifest file lists required tools for the
   interactive path; CI enforces that both registries satisfy it.
3. **Fast-path for conversational turns** — classify intent before sending to
   coordinator; bypass for pure conversational queries.
4. **Transparent HUD** — show the effective coordinator profile, tool state, and
   turn type in the HUD or status display.
5. **Single source of truth for tool mode** — replace two boolean flags with one
   `ToolMode` enum.

### 5.2 Component Changes

#### 5.2.1 Shared Turn Classifier (`scripts/ai/lib/turn_classifier.py`) [NEW]

A new shared module providing `classify_turn(prompt, session_state) -> TurnClassification`.

```
TurnClassification:
  intent: "conversational" | "agentic" | "tool_free_explicit" | "spec_only"
  tool_mode: ToolMode  ("ENABLED" | "DISABLED_SESSION" | "DISABLED_TURN")
  effective_profile: str  ("local-tool-calling" | "default" | "direct")
  bypass_reason: Optional[str]
  snapshot_needed: bool
```

This module:
- Imports phrase sets from a canonical location (no duplication).
- Is called by `aq-chat._stream_chat()` to build the payload.
- Is importable by coordinator tests to verify agreement.
- Exposes `BYPASS_PHRASES` and `SPEC_PHRASES` as module-level constants so both
  `aq-chat` and coordinator can import them rather than maintaining separate copies.

The classifier maps to existing intent logic:
- `"conversational"` → no tool need, no snapshot need → eligible for fast-path
- `"agentic"` → tool-calling profile, full coordinator path
- `"tool_free_explicit"` → explicit phrase match → tool-free system prompt
- `"spec_only"` → spec phrases match → tool-free but structured output

#### 5.2.2 `ToolMode` Enum (`scripts/ai/lib/turn_classifier.py`)

Replace dual boolean flags with:

```python
class ToolMode(Enum):
    ENABLED          = "enabled"           # tools active (default)
    DISABLED_SESSION = "disabled_session"  # --no-tools flag set
    DISABLED_TURN    = "disabled_turn"     # per-turn classifier fired
```

Interaction semantics:
- `DISABLED_SESSION` → `profile="default"`, `role="reviewer"`, `tools=[]` in payload
- `DISABLED_TURN` → `profile="local-tool-calling"` preserved, but `tools=[]`,
  `tool_choice="none"` injected, and tool-free system prompt used
- `ENABLED` → `profile="local-tool-calling"`, role per caller

This eliminates the current ambiguity where `local_tools_enabled=False` produces the
same payload as `local_tools_enabled=True + tool_free_turn=True` via different paths.

#### 5.2.3 Fast-Path Direct Route in `aq-chat`

For turns classified as `"conversational"` (no snapshot need, no tool need, no
explicit phrases):

```
Classified "conversational"
  → POST http://127.0.0.1:8080/v1/chat/completions  [direct to llama.cpp]
      payload: build_llama_payload(messages, max_tokens=768, stream=True,
                                   task_type="lookup",
                                   chat_template_kwargs={"enable_thinking": False})
      No coordinator, no subprocess spawn.
```

Fast-path eligibility:
- `active_profile in {"local", "local-tool-calling"}`
- `tool_mode == ToolMode.ENABLED` (session tools on; turn classifier says no tools needed)
- `turn_class.intent == "conversational"`
- Snapshot NOT needed (`_should_use_local_snapshot()` returns False)

Fast-path must:
- Use streaming (SSE) for real-time output.
- Include `chat_template_kwargs: {"enable_thinking": false}`.
- NOT hardcode the port — read from `LLAMA_URL` env var with default from
  `nix/modules/core/options.nix` :8080.
- Emit a `routing_decision` telemetry event with `route="direct"`.
- Fall back to the coordinator path on any HTTP error.

#### 5.2.4 Tool Set Parity Contract

Introduce `.agent/tool-parity-contract.json` — a machine-readable manifest listing
tools that MUST be available on every interactive aq-chat turn. This list is a
negotiated subset: the tools most useful interactively that the runtime can support.

Proposed initial parity set (available in both paths):
- `route_search` (maps to `query_aidb`)
- `recall_memory` (maps to `get_working_memory`)
- `run_harness_cli` (no Phase 11 equivalent — add as a Phase 11 tool OR keep as runtime-only)
- `store_memory`
- `get_hint`

The `_show_tools()` command in `aq-chat` MUST reflect the runtime-actual tool set, not
the Phase 11 registry. Two options:
- **Option A**: Query the coordinator for the actual runtime tool list via a new
  `/control/local-agent/tools` endpoint.
- **Option B**: `_show_tools()` reads `.agent/tool-parity-contract.json` for the
  interactive-path tool list, and clearly labels Phase 11 tools as "agent-loop only".

Option B is lower-risk (no new endpoint, no AppArmor changes required).

The Phase 11 `register_ai_coordination_tools()` should be updated to also register
runtime-compatible tool names as aliases where semantics overlap, so that `aq-agent-loop`
and the interactive path can converge over time without a flag day.

#### 5.2.5 HUD Transparency

The HUD prompt and `/status` output should show:

```
[local-tool-calling | tools:ON] ❯     # tool-calling turn
[local | tools:OFF | session] ❯        # --no-tools session
[local | direct | conversational] ❯    # fast-path turn
```

Implementation: `AQChat._build_prompt_text()` (new method) reads `active_profile`,
`tool_mode`, and `last_turn_classification` to build the prompt string.

The `show_status()` method should add:
- "Effective Wire Profile" row (the profile the coordinator will receive)
- "Tool Mode" row (ENABLED / DISABLED_SESSION / DISABLED_TURN)
- "Last Turn Route" row (coordinator-delegate / direct-llama)

The feedback loop (`_write_feedback()`) MUST record the effective wire profile, not
`self.active_profile`. This fixes the training data labeling gap.

#### 5.2.6 Coordinator Alignment (Issue 3 — Minimal Scope)

Rather than restructuring the coordinator's `_is_tool_free` check, align it to import
the same phrase constants from `turn_classifier.py` (or a shared constants module
accessible to both `scripts/ai/lib/` and the coordinator). The coordinator's check
remains its own code path but draws from the same phrase corpus.

This is safer than refactoring the coordinator delegate handler, which is a hot path
with broad blast radius.

### 5.3 Architecture Diagram

```
aq-chat._stream_chat(prompt)
        │
        ▼
classify_turn(prompt, session_state)
        │
   TurnClassification
        │
   ┌────┴──────────┐
   │               │
conversational    agentic / tool-calling / tool-free
   │               │
   ▼               ▼
POST :8080      POST :8003/control/ai-coordinator/delegate
direct llama    (existing coordinator path, unchanged)
SSE stream              │
                        ▼
                  _spawn_local_agent()
                  local_agent_runtime.py
                  TOOL_SCHEMAS (3 tools, to be extended)
```

---

## 6. Security & Configuration

### 6.1 No New Auth Surfaces

- The fast-path direct route to llama.cpp uses the same loopback connection that
  `DirectRunner` in `dispatch.py` uses. No new auth headers or endpoints.
- The shared `turn_classifier.py` module is a pure Python library with no HTTP surface.
- `.agent/tool-parity-contract.json` is a static JSON file read at startup; no
  runtime eval or exec.

### 6.2 Port Handling

- `aq-chat` already reads `LLAMA_URL` from the environment with default
  `http://127.0.0.1:8080`. The fast-path MUST use this pattern.
- `DEFAULT_LLAMA_URL = "http://127.0.0.1:8080"` in `aq-chat` line 38 is acceptable
  as a fallback only if `LLAMA_URL` env var is absent and the value matches
  `nix/modules/core/options.nix` llamaCpp.port default.

### 6.3 Tool Safety Policy

- The fast-path (direct to llama.cpp) bypasses the coordinator's tool security
  gate. It must only be used for `"conversational"` turns where `ToolMode.ENABLED`
  is active but the classifier has determined no tools will be called.
- If the direct-path model response contains a tool call pattern, `aq-chat` should
  detect this and emit a warning (not silently drop the tool call), then fall back
  to the coordinator path for retry.

### 6.4 Data in Transit

- No change to existing TLS/loopback security posture.
- Feedback events: effective profile label fix prevents wrong-labelled entries from
  polluting training data. This is a data integrity improvement.

---

## 7. Implementation Phases

### Phase A — Shared Classifier + ToolMode (Foundation)
Introduce `scripts/ai/lib/turn_classifier.py` with `classify_turn()`, `ToolMode`,
and `TurnClassification`. Refactor `aq-chat` to use `ToolMode` enum internally.
No behavior change yet — replace existing dual booleans with enum, same logic.

### Phase B — HUD Transparency + Feedback Label Fix
Update HUD prompt text and `/status` output to show effective wire profile and tool
mode. Fix `_write_feedback()` to record effective profile. Update `/tools` display to
show runtime-actual tool list (Option B: parity contract file).

### Phase C — Fast-Path Direct Route
Implement the conversational fast-path in `aq-chat`. Guarded by a `--no-fastpath`
flag for debugging. Emit `routing_decision` telemetry events. Validate with tests
against a mock llama.cpp SSE response.

### Phase D — Tool Set Parity Contract
Audit `local_agent_runtime.py` `TOOL_SCHEMAS` against Phase 11 `ToolRegistry`.
Publish `.agent/tool-parity-contract.json`. Add `store_memory` and `get_hint` to
`local_agent_runtime.py` tool schemas. Update `_show_tools()` to use contract file.

### Phase E — Coordinator Phrase Alignment
Extract bypass phrases from `aq-chat` and coordinator into a shared constants module.
Verify both paths agree on all test cases in the parity contract test suite.

---

## 8. Validation & Success Criteria

### 8.1 Tool Parity (Issue 2)

| Criterion | Measurement |
|---|---|
| `/tools` in `aq-chat` shows only tools available in the interactive runtime | Manual + automated comparison of displayed vs contract tool list |
| `local_agent_runtime.py` has all tools listed in `.agent/tool-parity-contract.json` | Contract test: load runtime, assert all contract tools present in TOOL_SCHEMAS |
| Phase 11 registry has ≥ parity tool count | Contract test: `build_registry()`, assert contract tools present |

### 8.2 Profile Transparency (Issue 1)

| Criterion | Measurement |
|---|---|
| HUD shows `local-tool-calling` when tool-calling path is active | Visual + unit test on `_build_prompt_text()` |
| `show_status()` "Effective Wire Profile" matches payload `.profile` field | Unit test: assert `AQChat.show_status()` output matches `_build_coordinator_delegate_payload()` output |
| Feedback events have effective profile field matching wire profile | Assert `feedback_path` entries: `profile == "local-tool-calling"` not `"local"` |

### 8.3 Bypass Classifier (Issue 3)

| Criterion | Measurement |
|---|---|
| `classify_turn("do not call tools ...")` returns `tool_mode=DISABLED_TURN` | Unit test |
| `classify_turn("acceptance criteria for X")` returns `intent="spec_only"` | Unit test |
| Coordinator `_is_tool_free` check agrees with `classify_turn` on canonical test set (20 prompts) | Parity test file |
| No prompt in the test set produces different bypass decisions between aq-chat and coordinator | CI gate |

### 8.4 Fast Path (Issue 4)

| Criterion | Measurement |
|---|---|
| "Explain what X is" classified as `"conversational"` | Unit test `classify_turn` |
| Fast-path turn does NOT POST to coordinator | Mock test: assert `:8003` NOT called |
| Fast-path turn DOES stream from llama.cpp `:8080` | Mock test: assert `:8080` called with SSE |
| Latency reduction: p50 conversational turn < 1.5s (vs. full-path ~3-4s estimate) | Load test with representative prompts |
| Fallback to coordinator path on `:8080` connection refused | Integration test |

### 8.5 ToolMode Semantics (Issue 5)

| Criterion | Measurement |
|---|---|
| `--no-tools` produces `profile="default"`, `role="reviewer"` | Unit test payload builder |
| Explicit "no tools" phrase produces `profile="local-tool-calling"`, `tools=[]` | Unit test payload builder |
| Both modes produce non-overlapping log events | Telemetry test |

### 8.6 System-Level Regression

- `aq-qa 0` passes 114/114 after all phases complete.
- Existing `aq-chat` session behavior (harness context injection, snapshot grounding,
  `/save`/`/load`, `/rate`, `/search`) unchanged.
- No AppArmor DENIED events related to `aq-chat` after changes.

---

## 9. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Fast-path silently drops tool calls on conversational turns | HIGH | Detect tool-call patterns in direct-path response; warn and fall back to coordinator |
| `local_agent_runtime.py` tool schema additions cause prompt truncation (n_ctx=8192) | MEDIUM | Measure token cost of expanded TOOL_SCHEMAS before adding; cap at 3 additional tools |
| `classify_turn()` misclassifies agentic turns as conversational → tool calls lost | HIGH | Conservative classifier: only classify as conversational when no action verbs present AND no snapshot keywords AND no tool-calling profile explicitly selected |
| Coordinator `_is_tool_free` and new classifier diverge after future edits | MEDIUM | Both import from shared constants; CI test verifies agreement on canonical set |
| HUD prompt change breaks user muscle memory | LOW | Keep `[profile]` format; extend with optional second token only when non-default |
| Tool parity contract file becomes stale | MEDIUM | CI lint: `tool-parity-contract.json` must be regenerated when `local_agent_runtime.py` or `ai_coordination.py` changes |
| `--no-fastpath` debug flag accidentally deployed to production config | LOW | Flag defaults to False; not wired to any NixOS module option |
| n_ctx overflow from larger tool schemas | HIGH | Measure: current 3-tool TOOL_SCHEMAS ≈ 350 tokens. Budget 800 tokens max for tool schemas. Test with 8 tools before adding all 14. |

---

## 10. Open Questions

1. **Runtime tool architecture**: Should `local_agent_runtime.py` be refactored to
   import and use the Phase 11 `ToolRegistry` and `register_*` functions directly,
   achieving full code-path unification? This would be the highest-fidelity parity
   solution but requires verifying the import chain is available inside the subprocess
   environment. The current hardcoded `TOOL_SCHEMAS` approach is more portable but
   requires manual synchronization. **Team is split: Architect favors unification;
   Tool Registry Specialist favors parity contract as a safer interim step.**

2. **Fast-path classifier threshold**: What is the correct precision/recall tradeoff
   for `"conversational"` classification? Too aggressive → tool calls silently lost.
   Too conservative → no latency benefit. Should the classifier be user-configurable
   via a `--conversational-threshold` flag or config file? **Performance Analyst
   recommends tunable; Systems Architect recommends hardcoded conservative default
   with user override flag.**

3. **`/tools` command scope**: Should `/tools` show both the interactive-path tools
   AND the Phase 11 tools (with clear labeling), or only the interactive-path tools?
   Showing both provides more information but may be confusing. **UX Designer
   recommends two modes: `/tools` (interactive only) and `/tools all` (full registry).**

4. **Feedback profile label migration**: Existing feedback entries in
   `delegation-feedback.jsonl` have `profile: "local"`. Should the training pipeline
   be updated to normalize these retroactively, or accept the label shift going
   forward? **Training pipeline owners not consulted — open.**

5. **`store_memory` in `local_agent_runtime.py`**: The Phase 11 `store_memory_handler`
   is async and calls the coordinator's `/memory/store` endpoint. Inside
   `local_agent_runtime.py` (a subprocess), the event loop is already running. Can
   the store_memory tool be safely integrated as an async tool in the current
   subprocess runtime architecture? **Tool Registry Specialist needs to verify the
   async execution model in `local_agent_runtime.py` before committing to this.**

6. **`_should_short_circuit_to_continue_local_http()`**: The coordinator already has
   a fast-path for `continue-local` profiles. Could `aq-chat` leverage this by
   switching to `continue-local` profile for conversational turns rather than
   bypassing the coordinator entirely? This avoids adding a direct-to-llama route
   in `aq-chat` but does not reduce coordinator overhead. **Open architectural choice.**

---

## 11. Team Sign-off

- **Systems Architect**: APPROVED with concern — the dual registry architecture
  (Issue 2) is the highest architectural risk. Phase D (parity contract) should be
  treated as Phase B priority. Recommend reversing Phase B and Phase D order.

- **Coordinator/Switchboard Domain Expert**: APPROVED — the coordinator-side change
  (Phase E phrase alignment) is minimal and safe. Strongly recommend NOT restructuring
  `handle_ai_coordinator_delegate()` in this PRD scope; it is too broad.

- **Tool Registry Specialist**: CONCERNS — Open Question 1 (runtime unification vs
  parity contract) must be resolved before Phase D starts. The current hardcoded
  `TOOL_SCHEMAS` in `local_agent_runtime.py` is a maintenance liability. Recommend
  Phase D include a feasibility spike on import-chain unification before committing
  to the contract-file approach.

- **CLI UX Designer**: APPROVED — the HUD changes in Phase B are overdue. Recommend
  adding a `--verbose-hud` flag rather than always showing the extended prompt, to
  preserve default terminal cleanliness for users who don't need routing visibility.

- **Performance Analyst**: APPROVED — fast-path (Phase C) is the highest-value
  delivery. On the Renoir APU at measured 1-2 tok/s prefill, eliminating
  ~400-800ms coordinator overhead on conversational turns is meaningful for
  interactive feel. Recommend Phase C be prioritized alongside Phase A.

- **Observability Engineer**: CONCERNS — routing decision events (Phase C) must be
  emitted BEFORE the fast-path response begins, not after. If aq-chat crashes
  mid-stream, the routing decision must already be in telemetry. Require atomic
  event emission at classification time, not at response completion.

- **QA / Test Engineer**: APPROVED with requirement — a `tests/test_turn_classifier.py`
  module with ≥ 30 canonical test cases (covering all five issue scenarios) must be
  delivered as part of Phase A, not as a follow-on. The parity contract test (Phase D)
  must be a CI gate, not advisory. All five issues require automated regression
  coverage before this PRD is considered complete.

---

*Draft produced by: Gemini Expert Team (independent)*
*Repo root: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy*
*Files examined: aq-chat (848L), agent_executor.py, __init__.py, ai_coordination.py (731L),*
*local_agent_runtime.py (772L), ai_coordinator_handlers.py (2728L), aq-agent-loop (282L),*
*dispatch.py (1170L), switchboard.py (profile sections), options.nix*
