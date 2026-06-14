# PRD: aq-chat Unified Routing & Tool-Calling Architecture
## Status: DRAFT — Claude Team

**Date:** 2026-06-14
**Problem Domain:** Local inference interactive path — routing, tool parity, intent classification
**Team Roles:** Systems Architect · Coordinator/Switchboard Domain Expert · Tool Registry Specialist · CLI UX Designer · Performance Analyst · Observability Engineer · QA/Test Engineer

---

## 1. Executive Summary

`aq-chat` is the primary interactive interface to the local AI stack, but it currently operates
through a patchwork of routing conditions and heuristics that diverge from the clean contracts
established for autonomous agent delegation. The result is a system where the profile shown to
the user does not match the profile sent to the coordinator, tool availability differs between
interactive and autonomous sessions in underspecified ways, every conversational turn pays full
coordinator delegate overhead, and mode selection is driven by brittle keyword matching rather
than the coordinator's existing intent classifier.

This PRD defines a unified routing and tool-calling architecture that eliminates these gaps,
makes routing decisions transparent and deterministic, and establishes a single canonical tool
registry contract for all local inference sessions regardless of how they enter the stack.

---

## 2. Mission

Establish aq-chat as a first-class equal of the autonomous agentic delegation path — same tool
access, same routing transparency, same intent-driven mode selection — while preserving
performance characteristics appropriate to interactive use (low latency for conversational turns,
full agent power for agentic turns).

---

## 3. Scope

### 3a. In Scope
- Unified routing decision contract: single signal (intent class) driving tool-call mode
- Tool registry parity: aq-chat sessions get a canonically defined, documented tool set
- Profile name/behavior coherence: what HUD shows == what coordinator receives
- Direct llama.cpp routing for pure conversational turns (bypass coordinator overhead)
- Replacement of keyword-based tool bypass with coordinator intent classification
- Elimination of `local_tools_enabled` / `tool_free_turn` dual-control redundancy
- Observability: routing decision event emission so every turn's routing path is auditable

### 3b. Out of Scope
- AppArmor profile changes (separate concern, pending rebuild queue)
- Dashboard UI changes (Codex owns dashboard work on separate branch)
- Remote profile routing (non-local profiles unaffected)
- Training ingest / RAG pipeline changes
- Any changes to `delegate-to-local`, `aq-agent-loop`, or `aq-qa` scripts beyond
  confirming tool registry contracts

### 3c. Constraints
- NixOS-first — no bare pip install, no manual systemctl
- Never hardcode ports — source: `nix/modules/core/options.nix`
- `enable_thinking: false` in every llama.cpp request (`chat_template_kwargs`)
- GPU layers ceiling = 12 (Renoir APU, 4GB shared VRAM)
- n_ctx = 8192; budget-sensitive — any new system prompt additions must be audited
- Must not regress existing 114/114 aq-qa checks
- Must not interfere with Codex dashboard branch

---

## 4. Current State Architecture

### 4.1 Routing Logic (aq-chat `_stream_chat`)

```
active_profile (CLI arg, default "local")
    │
    ├── if profile in {"local","local-tool-calling"} OR local_snapshot OR tool_free_turn
    │       → POST coordinator /control/ai-coordinator/delegate
    │         payload.profile = "local-tool-calling" if local_tools_enabled and not tool_free_turn
    │                        else "default"
    │
    └── else → POST coordinator /v1/orchestrate
```

**Gaps identified:**
- `active_profile="local"` → payload `profile="local-tool-calling"`: HUD shows `[local]`
  but coordinator receives `local-tool-calling`. User cannot observe actual routing.
- `tool_free_turn` determined by `_should_bypass_tools_for_turn()` — substring match
  against `TOOL_FREE_PHRASES` / `TOOL_FREE_SPEC_PHRASES`. Fragile, not intent-based.
- `local_snapshot` (operational context turns) also routes to coordinator delegate,
  then the snapshot payload is passed alongside — coordinator delegate is not the right
  path for snapshot-grounded turns (no tool execution needed).
- Every turn, including `"what is X?"` pure chat, pays the full coordinator delegate
  round-trip (~200-400ms overhead + slot occupancy on coordinator).

### 4.2 Tool Registry State (confirmed by code read 2026-06-14)

**Path A: `aq-agent-loop` → `build_registry()`**
Registers: `file_tools` + `shell_tools` + `git_tools` + `ai_coordination`
Does NOT register: `computer_use`, `code_execution`
Tool count: ~29 in "full" manifest, ~8 in "self-improvement" manifest

**Path B: coordinator `initialize_builtin_tools()` (used by `/control/ai-coordinator/delegate`)**
Registers: `file_tools` + `shell_tools` + `ai_coordination` + `computer_use` + `code_execution` + `git_tools`
Tool count: higher than Path A (adds computer_use + code_execution)

**The divergence is real but in the opposite direction from initial assumption:**
`aq-agent-loop` (direct autonomous path) has FEWER tools than the coordinator delegate path
(which aq-chat also uses). No explicit contract governs which tools are available in each mode.
No documentation. No aq-qa check. Silent divergence.

### 4.3 Dual Controls on Tool Usage

```python
self.local_tools_enabled = not getattr(args, "no_tools", False)  # session-level
tool_free_turn = self._should_bypass_tools_for_turn(prompt)       # per-turn
```

Both affect the same payload field. Interaction:
- `local_tools_enabled=False` + any `tool_free_turn` → `profile="default"`, `tools=[]`
- `local_tools_enabled=True` + `tool_free_turn=True` → same result, different code path
- `local_tools_enabled=True` + `tool_free_turn=False` → `profile="local-tool-calling"`

Two controls, same outcome, no documented contract between them.

### 4.4 Observability Gap

Routing decisions are not emitted as events. When a turn routes to coordinator vs
direct llama.cpp, or when tool-free mode activates, no event appears in
`agent-run-events.jsonl`. Operators cannot audit why a given turn was routed the way
it was.

---

## 5. Proposed Architecture

### 5.1 Core Principle: Single Routing Signal

Replace the two-control system with one canonical routing decision based on **intent class**:

```
Intent Class (from coordinator _classify_routing_intent OR local fast classifier)
    │
    ├── CONVERSATIONAL  → direct llama.cpp (port 8080), no coordinator overhead
    ├── AGENTIC         → coordinator /control/ai-coordinator/delegate, local-tool-calling profile
    └── OPERATIONAL     → coordinator /control/ai-coordinator/delegate, local-tool-calling profile
                          + snapshot context prepended (current behavior, but clearly signaled)
```

### 5.2 Routing Decision Point

A lightweight intent classifier runs **before** building the request. Two options (let
all teams evaluate both during PRD review):

**Option A — Coordinator pre-flight (preferred for consistency):**
POST a lightweight `/control/ai-coordinator/classify-intent` with the prompt text.
Coordinator returns `{intent: "conversational"|"agentic"|"operational", confidence: float}`.
aq-chat uses this to select the routing path.
Cost: one additional HTTP round-trip per turn (~50-100ms).
Benefit: uses the same classifier as autonomous delegation, guaranteed consistency.

**Option B — Local fast classifier (preferred for latency):**
Port the keyword/pattern logic from `_classify_routing_intent()` into a local function
in aq-chat. No HTTP overhead. Runs synchronously in <1ms.
Cost: duplicated logic, must stay in sync with coordinator classifier.
Risk: drift between interactive and autonomous classification.

**Systems Architect recommendation:** Option A for correctness; Option B acceptable if
the coordinator endpoint adds >200ms latency in practice. Measure before deciding.

### 5.3 Profile Name/Behavior Coherence

`active_profile` should reflect what the coordinator actually receives:
- Replace `--profile local` default with `--profile local-tool-calling`
- OR: when `active_profile="local"` and tool-calling is active, HUD shows
  `[local-tool-calling]` not `[local]`
- The payload `profile` field must always equal the resolved active profile.

### 5.4 Tool Registry Contract

Define and document a **canonical tool set contract** as a checked artifact:

```yaml
# .agent/tool-registry-contract.yaml
profiles:
  local-tool-calling:
    required_tools:
      - read_file, write_file, edit_file           # file_operations
      - run_command, execute_shell                  # shell_tools
      - git_add, git_commit, git_status            # git_tools
      - query_aidb, store_memory, get_hint         # ai_coordination
      - get_working_memory, mesh_discovery          # ai_coordination
      - delegate_to_remote, harness_health          # ai_coordination
      - query_context                               # ai_coordination
    optional_tools:
      - computer_use                                # coordinator path only
      - code_execution                              # coordinator path only
    explicitly_excluded:
      - danger_tool                                 # security fixture, never in production
  direct-local:                                     # direct llama.cpp, no tools
    required_tools: []
```

`initialize_builtin_tools()` and `build_registry()` must both satisfy the
`local-tool-calling` required_tools contract. An aq-qa check validates this at test time.

### 5.5 Eliminate Dual Controls

Remove `local_tools_enabled` as a session-level flag. Replace with:
- `--mode` flag: `chat` (conversational, direct llama.cpp) | `agent` (always agentic, always tools) | `auto` (default, intent-classified per turn)
- Per-turn override still supported via explicit `/notool` or `/tool` prefix commands (slash commands, not keyword matching)

### 5.6 Direct llama.cpp Path for Conversational Turns

When intent class = `CONVERSATIONAL`:
```python
target_url = f"{self.llama_url}/v1/chat/completions"
payload = build_llama_payload(messages, max_tokens=1024, task_type="lookup")
payload["stream"] = True
```
No coordinator, no delegate overhead. Full streaming from llama.cpp directly to console.
System prompt still injected (already in `context_history`).

### 5.7 Routing Decision Event Emission

Every turn emits a `routing_decision` event to `agent-run-events.jsonl`:
```json
{
  "event_type": "routing_decision",
  "source": "aq-chat",
  "run_id": "<turn-id>",
  "payload": {
    "intent_class": "agentic",
    "routing_path": "coordinator-delegate",
    "profile": "local-tool-calling",
    "tool_free": false,
    "classifier_method": "coordinator-preflight",
    "confidence": 0.92
  }
}
```

---

## 6. Security & Configuration

- No new auth surfaces introduced — direct llama.cpp path uses same loopback as existing
  calls; no token required for 127.0.0.1:8080
- No new coordinator endpoints required for Option A if `/classify-intent` is added with
  loopback auth exemption (same pattern as Phase 162C `/search/` fix)
- `--mode` flag replaces `--no-tools` — backwards compatibility: `--no-tools` maps to
  `--mode chat` with deprecation warning
- Tool registry contract YAML is read-only checked artifact — never executed, no injection risk
- `routing_decision` events contain no user prompt content (only metadata/classification)

---

## 7. Implementation Phases (High-Level)

### Phase A — Tool Registry Contract (no rebuild, low risk)
- Write `.agent/tool-registry-contract.yaml`
- Add aq-qa check verifying `initialize_builtin_tools()` and `build_registry()` both
  satisfy the required_tools contract
- No behavior changes — documentation and validation only

### Phase B — Profile Coherence (no rebuild, medium risk)
- Change default `--profile` to `local-tool-calling` OR update HUD display logic
- Ensure payload `profile` field always matches resolved active profile
- Update system prompt injection condition to track resolved profile, not original `--profile`

### Phase C — Intent-Based Routing (no rebuild, medium risk)
- Implement chosen option (A or B) for intent classification
- Replace `_should_bypass_tools_for_turn()` keyword matching with intent classifier result
- Add `--mode` flag, deprecate `--no-tools`
- Emit `routing_decision` events per turn

### Phase D — Direct llama.cpp Conversational Path (no rebuild, medium risk)
- Add direct llama.cpp routing for `CONVERSATIONAL` intent class
- Validate streaming path matches existing llama.cpp streaming behavior
- Add aq-qa smoke check: conversational turn does NOT hit coordinator delegate endpoint

**Phase ordering rationale:** A→B→C→D. Each phase is independently shippable and
additive. Phase A has zero behavior risk. Phase D is highest risk (new code path) and
comes last after the routing contract is validated.

---

## 8. Validation & Success Criteria

| Criterion | Measurement |
|---|---|
| Profile coherence | HUD profile == coordinator payload `profile` field on every turn |
| Tool parity | aq-qa checks `initialize_builtin_tools()` satisfies tool-registry-contract.yaml |
| Tool parity | aq-qa checks `build_registry()` satisfies tool-registry-contract.yaml |
| Intent routing | Conversational turns do NOT appear in coordinator delegate logs |
| Intent routing | Agentic turns DO appear in coordinator delegate logs with `local-tool-calling` |
| Observability | Every turn produces a `routing_decision` event in agent-run-events.jsonl |
| Regression | 114/114 aq-qa checks pass after each phase |
| Latency | Conversational turn round-trip < 50ms to first token (vs current ~200-400ms) |
| Dual control elimination | `local_tools_enabled` field removed from AQChat class |

---

## 9. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Intent misclassification routes agentic turn to direct path — tools not called | High | Default to `agentic` on classifier uncertainty; confidence threshold < 0.8 → agentic |
| Option A adds per-turn HTTP round-trip — latency regression for fast conversational turns | Medium | Measure actual latency; use Option B if >200ms; cache classifier for repeated prompt patterns |
| `build_registry()` and `initialize_builtin_tools()` diverge after this PRD ships | Medium | Tool registry contract YAML + aq-qa check enforces parity at every commit |
| Phase C keyword removal breaks existing user muscle memory ("no tools" phrase) | Low | Slash command `/notool` replaces keyword; add migration notice to aq-chat startup for one cycle |
| Direct llama.cpp path doesn't handle streaming errors the same way as coordinator path | Medium | Shared `_handle_llama_stream()` helper; validate against existing direct-llama path in aq-chat |
| `--no-tools` removal breaks existing scripts or cron tasks that call aq-chat | Low | Deprecation warning for two release cycles; `--no-tools` maps to `--mode chat` |

---

## 10. Open Questions

1. **Option A vs Option B for intent classification:** Which latency budget is acceptable
   for interactive turns? Need empirical measurement. Recommend: benchmark Option A round-trip
   before choosing.

2. **`computer_use` and `code_execution` in tool contract:** Should these be `required` or
   `optional` in the `local-tool-calling` profile? `computer_use` requires display; most
   agent tasks don't need it. Recommendation: `optional`, but this needs QA team input.

3. **`build_registry()` missing `computer_use` + `code_execution`:** Should `aq-agent-loop`
   direct invocations get these tools added, or should coordinator path have them removed?
   Tool Registry Specialist lean: add to `build_registry()` behind a feature flag.

4. **Snapshot-grounded turns routing:** Should operational snapshot turns (`local_snapshot=True`)
   continue routing through coordinator delegate, or switch to direct llama.cpp with the
   snapshot prepended? Coordinator path adds context injection (hints, working memory) which
   may be valuable for operational queries.

5. **`routing_decision` event schema location:** Add to existing `agent-run-event.schema.json`
   or create a separate `aq-chat-turn-event.schema.json`? Observability Engineer leans toward
   extending the existing schema for unified replay.

---

## 11. Team Sign-off

- **Systems Architect:** APPROVED — phased plan is independently shippable, Option A/B decision
  is the only blocker for Phase C. Architecture is clean and reversible.

- **Coordinator/Switchboard Domain Expert:** APPROVED with concern — `_classify_routing_intent()`
  in `ai_coordinator_handlers.py` was designed for async coordinator contexts; exposing it as a
  synchronous pre-flight endpoint may require a thin wrapper. Verify it doesn't trigger
  coordinator-internal state mutations as a side effect.

- **Tool Registry Specialist:** APPROVED — confirming that `initialize_builtin_tools()` ALREADY
  registers all required AI coordination tools (Phase 162 fix). The gap vs `build_registry()`
  is `computer_use` + `code_execution` (coordinator has more). Contract YAML + aq-qa check
  is the right fix. No emergency.

- **CLI UX Designer:** APPROVED — `--mode auto|chat|agent` is a much cleaner user model than
  `--no-tools` + keyword phrases. HUD should show the resolved mode and intent class on each
  turn, not just the profile name.

- **Performance Analyst:** APPROVED with concern — must measure Option A latency before Phase C
  commit. If coordinator pre-flight adds >100ms on conversational turns, Option B is mandatory.
  Direct llama.cpp path for conversational turns is the highest-value performance win in this PRD.

- **Observability Engineer:** APPROVED — `routing_decision` event is essential. Also recommends
  adding `intent_confidence` to the event payload so operators can identify miscalibrated turns.
  Extend existing `agent-run-event.schema.json`.

- **QA / Test Engineer:** APPROVED — phased validation plan is solid. Adds: need an explicit
  test for the `CONVERSATIONAL` → direct path that verifies coordinator delegate is NOT called
  (mock or log check). Phase A aq-qa check for tool contract should run in CI, not just locally.
