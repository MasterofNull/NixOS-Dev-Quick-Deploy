# PRD: aq-chat Unified Routing & Tool-Calling Architecture
## Status: DRAFT — Codex Expert Team

---

## 1. Executive Summary

`aq-chat` is the primary human-in-the-loop terminal interface for the local AI stack. Following
Phase 169 work (commits c028c2d8, f86f5f9e), it now routes interactive turns through
`/control/ai-coordinator/delegate` using the `local-tool-calling` profile — the same path used
by autonomous `delegate-to-local --mode agent` dispatches. This parity fix closed the system
prompt injection gap but left five structural inconsistencies in routing transparency, tool
registry alignment, intent classification, per-turn coordinator overhead, and dual control
interaction.

This PRD specifies the architectural changes required to achieve full parity between interactive
and autonomous agentic paths, improve observability of routing decisions for the operator, reduce
unnecessary coordinator overhead on conversational turns, and consolidate the two redundant
tool-calling disable controls into a single coherent contract.

The expected outcomes are: deterministic and verifiable tool access parity, a transparent
per-turn routing HUD visible to the operator, a single authoritative intent classification path
shared between CLI and coordinator, reduced latency on conversational turns (direct llama.cpp
path without coordinator round-trip), and a single orthogonal tool disable mechanism.

---

## 2. Mission

Eliminate the architectural gap between interactive `aq-chat` sessions and autonomous
`delegate-to-local --mode agent` dispatches so that:

1. The set of tools available to the local model is identical in both execution paths.
2. The routing decision and active tool profile are transparent to the operator in the HUD.
3. Intent classification — conversational vs. tool-requiring — uses a single shared classifier
   rather than duplicated per-caller keyword lists.
4. Conversational turns bypass the coordinator delegate pipeline and route directly to llama.cpp,
   eliminating the fixed coordinator overhead (~80–200ms per turn plus spawn overhead) when no
   tools are needed.
5. Tool disabling is expressed by a single session-level flag (`local_tools_enabled`) with
   per-turn overrides surfaced as structured intent metadata, not raw string matching.

---

## 3. Scope

### 3a. In Scope

- `scripts/ai/aq-chat`: HUD label correction, payload profile transparency, per-turn routing
  logic, integration with a shared intent classifier.
- `ai-stack/local-agents/__init__.py`: Verification that `initialize_builtin_tools()` registers
  all 14 AI coordination tools via `register_ai_coordination_tools()`.
- `ai-stack/local-agents/agent_executor.py`: No functional changes. Reference only for parity
  verification.
- `ai-stack/switchboard/switchboard.py`: `_classify_routing_intent()` — expose as a shared
  utility callable from aq-chat without importing the full switchboard module.
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`:
  `_classify_routing_intent`-aware fast-path guard for purely conversational delegate requests.
- `scripts/ai/lib/dispatch.py`: `classify_mode()` function as a lightweight intent classifier
  candidate that already exists and runs without coordinator overhead.
- Telemetry event emission: add `routing_decision` event with profile, intent class, and tool
  count to every aq-chat turn for observability.
- `aq-chat` `--no-tools` flag semantics: define its interaction with per-turn bypass precisely.

### 3b. Out of Scope

- AppArmor profile changes (explicit constraint from brief).
- Dashboard UI changes (Codex dashboard branch — separate concern).
- Changes to `delegate-to-local`, `aq-agent-loop`, or autonomous agent paths.
- Remote profile routing (remote-gemini, remote-coding, remote-reasoning) — not affected.
- New auth surfaces or credential changes.
- The training pipeline, continuous learning, or telemetry consumers.
- `ralph-wiggum` tool-calling agent path.

### 3c. Constraints

- NixOS-first: all Python path changes must be compatible with `repoSource` Nix store layout;
  no bare pip installs.
- Ports sourced exclusively from `nix/modules/core/options.nix`; never hardcoded.
- `enable_thinking: false` in `chat_template_kwargs` on every llama.cpp request.
- GPU layers ceiling = 12 (Renoir APU, 4 GB VRAM shared); `n_ctx = 8192`.
- `frequency_penalty = 0.0` on all structured output requests (see MEMORY.md critical pattern).
- No new loopback auth surfaces.
- Do not break the existing `local-tool-calling` → coordinator → switchboard → `agent_executor`
  path that already works for tool-requiring turns.

---

## 4. Current State Architecture

### 4.1 aq-chat turn routing (as of commit f86f5f9e)

```
user turn
  → AQChat._stream_chat()
       ├─ _should_use_local_snapshot(prompt) → bool     [keyword match: status/health/etc.]
       ├─ _should_bypass_tools_for_turn(prompt) → bool  [keyword match: TOOL_FREE_PHRASES]
       │
       ├─ IF profile in {local, local-tool-calling} OR local_snapshot OR tool_free_turn:
       │     POST hybrid_url/control/ai-coordinator/delegate
       │       payload.profile = "local-tool-calling"   [if tools enabled & !tool_free]
       │       payload.profile = "default"              [if tools disabled OR tool_free]
       │
       └─ ELSE:
             POST hybrid_url/v1/orchestrate (streaming SSE)
```

**HUD display**: `[{self.active_profile}]` — always shows "local" (default CLI arg) regardless
of whether `local-tool-calling` or `default` profile was actually sent.

**Delegate endpoint** (`/control/ai-coordinator/delegate`):
- Reads `profile` from request body → routes to `selected_runtime_id`.
- For `local-tool-calling`: `_is_local_runtime` → `_spawn_local_agent_with_lease()`.
- Spawned subprocess: `local_agent_runtime.py` with env `AGENT_TOOLS_ENABLED`.
- Tool loading path inside spawned subprocess: **currently unverified** as to whether it calls
  `initialize_builtin_tools()` from `ai-stack/local-agents/__init__.py` or a different path.

**`aq-agent-loop` / `dispatch.py` AgentRunner path**:
- `build_registry()` explicitly calls `register_ai_coordination_tools(registry)` (line 92).
- Registers: `get_hint`, `delegate_to_remote`, `query_context`, `store_memory`,
  `get_workflow_status`, `run_opencode`, `harness_health`, `get_prsi_pending`,
  `prsi_orchestrate`, `recommend_agent_for_task`, `query_aidb`, `get_working_memory`,
  `mesh_discovery`, `collective_memory_search` (14 tools).

**`__init__.py` `initialize_builtin_tools()` path**:
- Calls `register_ai_coordination_tools(registry)` explicitly (line ~93 in __init__.py).
- Also registers: `file_operations`, `shell_tools`, `computer_use`, `code_execution`, `git_tools`.
- On paper, parity exists — but whether `local_agent_runtime.py` calls `initialize_builtin_tools()`
  vs. `build_registry()` vs. a separate registration sequence is not confirmed from files read.

### 4.2 Identified Gaps

#### Gap 1 — HUD/profile name split (Issue 1 from brief)

`self.active_profile` is set from `--profile` CLI arg (default `"local"`). The coordinator
delegate payload uses `"local-tool-calling"` (when tools enabled) or `"default"` (when disabled).
The HUD always shows `[local]`. The operator cannot tell:
- What profile the coordinator actually routed the turn through.
- Whether tools are currently active.
- What the switchboard's `local-tool-calling` profile config (maxInputTokens=12000,
  maxOutputTokens=2048, toolExecution="built-in") is doing to their turn.

#### Gap 2 — Dual tool registry paths (Issue 2 — CRITICAL)

Two initialization paths exist:
- `aq-agent-loop` → `build_registry()` → explicitly calls `register_ai_coordination_tools`.
- Coordinator-spawned subprocess (via `/control/ai-coordinator/delegate`) → `local_agent_runtime.py`
  → unknown initialization sequence.

`initialize_builtin_tools()` in `__init__.py` does call `register_ai_coordination_tools()`, but
it is not confirmed from code inspection that `local_agent_runtime.py` calls this function rather
than a subset. Without proof of parity, interactive turns may silently lack 14 AI coordination
tools that autonomous agent turns have.

#### Gap 3 — Fragile per-turn keyword bypass (Issue 3)

`_should_bypass_tools_for_turn()` uses `TOOL_FREE_PHRASES` and `TOOL_FREE_SPEC_PHRASES`
substring matching. The coordinator's `_classify_routing_intent()` in switchboard.py uses
`routing_rules` from `harness-prompt-extensions.json` — a config-driven, extensible task matrix
that already has the remote/local determination logic. The two classifiers can diverge silently
as the config evolves without code changes. There is no shared contract.

Additionally, the coordinator has its own tool-free detection at lines 1491–1493 of
`ai_coordinator_handlers.py` that duplicates the same phrase set. Three independent phrase lists
with no shared source of truth.

#### Gap 4 — Coordinator overhead on every conversational turn (Issue 4)

All turns, including `"explain X"` or `"what is Y"`, route through:
```
aq-chat → POST /control/ai-coordinator/delegate
        → runtime registry lookup (async lock)
        → lesson registry lookup (async lock)
        → progressive context application
        → _spawn_local_agent_with_lease() (asyncio.Semaphore check)
        → subprocess exec of local_agent_runtime.py
        → wait for subprocess stdout
```

Estimated fixed overhead: 80–300ms coordinator processing + subprocess spawn latency (~50ms).
For a purely conversational turn, direct POST to `llama.cpp:8080/v1/chat/completions` via
switchboard `continue-local` or `default` profile would be sufficient and cheaper.

#### Gap 5 — Dual redundant tool controls (Issue 5)

Two independent boolean controls both disable tool calling:
- `local_tools_enabled` (session-level): set `False` by `--no-tools` flag. Affects payload
  profile selection (sends `"default"` instead of `"local-tool-calling"`).
- `tool_free_turn` (per-turn): set by `_should_bypass_tools_for_turn()`. Also affects payload
  profile selection to `"default"` and injects a `TOOL-FREE TURN:` system message.

Both result in `profile="default"` in the payload, but via different code paths with different
side effects (the per-turn path adds a system message; the session-level path does not). The
interaction: `local_tools_enabled=True AND tool_free_turn=True` produces the same coordinator
payload as `local_tools_enabled=False AND tool_free_turn=False`, but the former injects a
`TOOL-FREE TURN:` system message while the latter does not. This asymmetry is silent and
untested.

### 4.3 Component Map (Current)

```
scripts/ai/aq-chat
  ├── AQChat._build_coordinator_delegate_payload()  → profile selection (dual path)
  ├── AQChat._should_bypass_tools_for_turn()        → TOOL_FREE_PHRASES keyword match
  ├── AQChat._stream_chat()                         → routing branch (local vs orchestrate)
  └── HUD: [self.active_profile]                    → always "local", never actual profile

ai-stack/local-agents/__init__.py
  └── initialize_builtin_tools()                    → registers 6 tool modules incl. ai_coordination

ai-stack/local-agents/agent_executor.py             → used by local_agent_runtime.py subprocess
ai-stack/local-agents/builtin_tools/ai_coordination.py → 14 AI coord tools

ai-stack/switchboard/switchboard.py
  └── _classify_routing_intent()                    → routing_rules based classifier (NOT used by aq-chat)
  └── DEFAULT_PROFILE_CATALOG["local-tool-calling"] → forceProvider:local, toolExecution:built-in

ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py
  └── handle_ai_coordinator_delegate()              → subprocess spawn for local runtimes

scripts/ai/aq-agent-loop
  └── build_registry()                              → explicit 14 AI coord tool registration
```

---

## 5. Proposed Architecture

### 5.1 Overview

The proposed architecture resolves all five gaps via four targeted interventions:

1. **HUD transparency**: Display actual coordinator profile + tool status in HUD.
2. **Tool registry parity verification**: Add a `/control/ai-coordinator/tool-manifest` endpoint
   or startup check to surface the actual tool list seen by spawned subprocess agents; add an
   `aq-chat /tools` panel that shows what the live coordinator path registers.
3. **Shared intent classifier**: Extract a lightweight `classify_chat_intent(prompt, messages)`
   utility function callable by both aq-chat and the coordinator delegate handler. Sourced from
   `dispatch.py`'s existing `classify_mode()` which already performs heuristic intent
   classification.
4. **Conversational fast-path**: For turns classified as `intent=conversational`, bypass
   coordinator delegate pipeline and POST directly to switchboard `continue-local` or `default`
   profile via `hybrid_url/v1/orchestrate`.
5. **Unified tool control**: Collapse `local_tools_enabled` (session) and `tool_free_turn`
   (per-turn) into a single decision point with explicit precedence: session-level overrides
   per-turn, per-turn overrides auto-classification.

### 5.2 Component Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│ aq-chat (scripts/ai/aq-chat)                                    │
│                                                                 │
│  Session state:                                                 │
│    active_profile    = "local"                 (display only)   │
│    active_wire_profile = "local-tool-calling"  (actual payload) │
│    tool_mode = "enabled" | "disabled" | "per-turn"              │
│                                                                 │
│  Per-turn:                                                      │
│    intent = classify_chat_intent(prompt, messages)              │
│      → "conversational" | "agentic" | "tool-required"           │
│                                                                 │
│  Routing branch:                                                │
│    intent=conversational AND tool_mode≠"enabled"                │
│      → POST switchboard /v1/chat/completions  (fast path)       │
│    intent=agentic OR tool_mode="enabled"                        │
│      → POST coordinator /control/ai-coordinator/delegate        │
│           payload.profile = active_wire_profile                 │
│                                                                 │
│  HUD: [{active_profile} | {active_wire_profile} | tools:{N}]   │
└─────────────────────────────────────────────────────────────────┘
                │ fast path                  │ delegate path
                ▼                            ▼
┌──────────────────────┐     ┌──────────────────────────────────┐
│ switchboard:8085     │     │ coordinator:8003                 │
│ /v1/chat/completions │     │ /control/ai-coordinator/delegate │
│ profile: continue-  │     │   ↓                              │
│ local or default    │     │  _spawn_local_agent_with_lease() │
│ (no tool execution) │     │    → local_agent_runtime.py      │
└──────────────────────┘     │       initialize_builtin_tools() │
         │                   │         → 14 AI coord tools      │
         ▼                   └──────────────────────────────────┘
   llama.cpp:8080                        │
                                         ▼
                                  llama.cpp:8080
                                  (via switchboard)
```

### 5.3 Shared Intent Classifier

Extract a standalone `classify_chat_intent(prompt: str, messages: list) -> str` function into
`scripts/ai/lib/chat_intent.py`. It returns one of three classes:

- `"conversational"`: No tool call needed. Pure reasoning, explanation, or question answering
  from context. Suitable for direct switchboard fast-path.
- `"agentic"`: Task involves file reads, shell commands, git, memory operations, or harness
  health. Should route through coordinator delegate with `local-tool-calling` profile.
- `"tool-required"`: Explicit user request for tool use, or prompt matches TOOL_FREE_PHRASES
  negation (tools explicitly disabled). Also covers `local_snapshot` turns.

**Implementation basis**: Reuse `classify_mode()` from `scripts/ai/lib/dispatch.py` which
already classifies `hybrid | direct | agent` using prompt text heuristics. Map:
- `direct` → `conversational`
- `hybrid` → `conversational` (no tools, coordinator context only)
- `agent` → `agentic`

Add: check for explicit tool-free phrases (TOOL_FREE_PHRASES) → return `"tool-required"` with
`tools_enabled=False` metadata to distinguish the "force-no-tools" case from "use coordinator
with tools".

This function is **not** called by the coordinator or switchboard. It runs in aq-chat before the
HTTP call is made, using only local computation.

### 5.4 HUD Transparency Design

Current HUD prompt format:
```
[local] ❯
```

Proposed HUD prompt format:
```
[local | ltc | tools:14] ❯
```
Fields:
- `local`: `active_profile` (user-visible routing label, set by `--profile` arg or `/route`)
- `ltc`: abbreviated `active_wire_profile` actually sent to coordinator
  (`ltc`=local-tool-calling, `def`=default, `cont`=continue-local)
- `tools:N`: count of tools registered in the active path (fetched once per session from
  coordinator tool manifest endpoint; cached)

Fallback if tool count unavailable: `tools:?`

This makes routing fully transparent to the operator without requiring any flags.

### 5.5 Tool Registry Parity Verification

**Problem**: `initialize_builtin_tools()` in `__init__.py` calls `register_ai_coordination_tools()`
(confirmed from code inspection). `local_agent_runtime.py` is the subprocess entry point spawned
by the coordinator delegate handler. Whether it calls `initialize_builtin_tools()` is not
confirmed from the files read.

**Proposed resolution**:

Phase A (verification): Read `ai-stack/agents/runtimes/local_agent_runtime.py` to confirm whether
`initialize_builtin_tools()` is called on the subprocess tool registry. This is a pre-implementation
verification step, not a code change.

Phase B (if gap found): Add an explicit call to `register_ai_coordination_tools(registry)` in
`local_agent_runtime.py` if the AI coordination tools are not already registered there. Mirror
`build_registry()` in aq-agent-loop which does this explicitly.

Phase C (ongoing): Add a coordinator endpoint `GET /control/ai-coordinator/tool-manifest` that
returns the tool list seen by a freshly-spawned test subprocess. Called once at aq-chat startup
to populate the `tools:N` HUD counter and log tool count to stdout. Divergence from 14 becomes
immediately visible.

### 5.6 Conversational Fast-Path Design

When `classify_chat_intent()` returns `"conversational"` AND `local_tools_enabled=True`
(tools not explicitly disabled by user):

```python
target_url = f"{self.switchboard_url}/v1/chat/completions"
payload = {
    "model": local_model_id,
    "messages": request_messages,
    "stream": True,
    "temperature": self.temperature,
    "frequency_penalty": 0.0,
    "chat_template_kwargs": {"enable_thinking": False},
}
headers = {
    "X-AI-Profile": "continue-local",
    "X-AI-Route": "local",
    "X-Agent-Source": "aq-chat",
    "X-Agent-Role": "orchestrator",
}
```

This routes through switchboard `continue-local` profile:
- `forceProvider: local`
- `injectHints: true`
- `maxInputTokens`: env `SWB_CONTINUE_LOCAL_MAX_INPUT_TOKENS` (default 4000)
- `maxOutputTokens: 768`
- No tool execution (`toolExecution: None`)

The switchboard streams SSE tokens back directly. aq-chat consumes the stream in its existing
SSE consumer loop (the `async for line in response.aiter_lines()` branch).

**Conditions where fast-path is NOT used** (force coordinator path):
- `local_tools_enabled=False` (session): Use switchboard `default` profile directly, no coordinator.
- `intent="agentic"`: Coordinator delegate with `local-tool-calling`.
- `local_snapshot=True`: Coordinator delegate (snapshot grounding requires system message injection
  that is best handled via the existing delegate path's message construction).
- Any turn where `context_history` contains a prior tool-call response (continuation of an
  agentic turn in the same session).

### 5.7 Unified Tool Control

Replace the two-variable system with one structured `ToolMode` state:

```python
@dataclass
class ToolMode:
    session_enabled: bool    # True unless --no-tools flag
    per_turn_override: Optional[bool]  # None = auto-classify; True/False = forced
```

Decision logic (single point, documented):

```python
def resolve_tool_mode(self, intent: str) -> tuple[bool, str]:
    """Returns (tools_enabled, coordinator_profile)."""
    if not self.tool_mode.session_enabled:
        return False, "default"  # --no-tools flag: no tools, no tool message injection
    if self.tool_mode.per_turn_override is False:
        return False, "default"  # explicit user phrase: inject tool-free system message
    if intent == "conversational" and self.tool_mode.per_turn_override is None:
        return False, "continue-local"  # auto: fast-path, no tools
    return True, "local-tool-calling"  # agentic or explicit tool request
```

**Side effect parity fix**: When `tools_enabled=False` AND `session_enabled=False`, do NOT
inject the `TOOL-FREE TURN:` system message (it was never intended for the `--no-tools` session
case). Only inject it when `per_turn_override=False` (explicit user request in prompt).

### 5.8 Event Emission (Observability)

Add a `routing_decision` event emitted by aq-chat on every non-command turn:

```json
{
  "event_type": "routing_decision",
  "source": "aq-chat",
  "turn_index": N,
  "intent": "conversational|agentic|tool-required",
  "wire_profile": "continue-local|local-tool-calling|default",
  "tool_mode": "enabled|disabled|per-turn-override",
  "tool_count": 14,
  "fast_path": true|false,
  "timestamp": "ISO-8601"
}
```

Written to the same `delegation-feedback.jsonl` telemetry path used by `/rate` feedback, using
`asyncio.to_thread` to avoid blocking the async loop.

This event is not consumed by any existing pipeline but provides a ground truth audit trail for
debugging routing decisions without needing to instrument the coordinator.

---

## 6. Security & Configuration

### 6.1 No new auth surfaces

The conversational fast-path POSTs to the existing switchboard endpoint on loopback (127.0.0.1:8085).
The switchboard already handles `X-AI-Profile` and `X-AI-Route` headers for local routing.
No new credentials, API keys, or auth middleware are introduced.

The `/control/ai-coordinator/tool-manifest` endpoint (proposed in Phase C) is a read-only GET
on the existing coordinator service. It requires the same loopback-agent headers already in use
(`X-Agent-Source: aq-chat`). No new auth surface.

### 6.2 Port sourcing

All URL defaults in `aq-chat` must reference env vars with fallbacks matching `options.nix`:
- `LLAMA_URL` → `http://127.0.0.1:8080`
- `HYBRID_URL` → `http://127.0.0.1:8003`
- `SWITCHBOARD_URL` → `http://127.0.0.1:8085`

The new fast-path uses `self.switchboard_url` which already sources from `--switchboard-url`
or `SWITCHBOARD_URL` env var. No hardcoding.

### 6.3 `enable_thinking: false` invariant

The fast-path payload MUST include `"chat_template_kwargs": {"enable_thinking": False}` at the
aq-chat payload construction level. It cannot rely on switchboard to inject this because the
current switchboard `continue-local` profile card uses `/no_think` text prefix but does not
inject `chat_template_kwargs`. The aq-chat caller is responsible for this field.

### 6.4 Nix store path compatibility

The new `scripts/ai/lib/chat_intent.py` file will be a pure Python module with no runtime
file writes. It imports only from stdlib (re, typing). No REPO_ROOT derivation needed. Safe
in Nix store context.

---

## 7. Implementation Phases

### Phase A — Verification (no code changes)

Read `ai-stack/agents/runtimes/local_agent_runtime.py` to confirm the actual tool initialization
sequence used by coordinator-spawned subprocess agents. Document findings. Confirm presence or
absence of `register_ai_coordination_tools()` call. This is a mandatory prerequisite for Phase B.

### Phase B — Tool Registry Parity

If Phase A reveals a gap, add the missing `register_ai_coordination_tools(registry)` call to
`local_agent_runtime.py`. Add a startup log line `[local_agent_runtime] tools registered: N`
that is captured in the subprocess stderr for diagnostics. This is a one-line or two-line fix
if the gap exists.

### Phase C — Shared Intent Classifier

Create `scripts/ai/lib/chat_intent.py` with `classify_chat_intent(prompt, messages) -> str`.
Reuse classify_mode() heuristics from dispatch.py as the implementation basis. Add unit tests
in `scripts/testing/` covering the three intent classes and edge cases (empty prompt, tool-free
phrases, snapshot keywords).

### Phase D — HUD Transparency + Tool Control Unification

Update `AQChat.__init__()` and `_stream_chat()`:
- Replace `local_tools_enabled` + `tool_free_turn` with `ToolMode` dataclass.
- Use `resolve_tool_mode()` single decision point.
- Update HUD prompt format string to include `active_wire_profile` and tool count.
- Add `active_wire_profile` instance variable, updated on every `resolve_tool_mode()` call.
- Fix the `TOOL-FREE TURN:` injection asymmetry.

### Phase E — Conversational Fast-Path

Update `_stream_chat()` to route `intent=conversational` turns directly to switchboard
`/v1/chat/completions` instead of coordinator delegate. This is a conditional branch addition,
not a removal of the existing delegate path. The delegate path remains intact for agentic turns.
Validate that `local_snapshot=True` turns still go through the delegate path.

### Phase F — Routing Decision Event Emission

Add `_emit_routing_decision_event()` call in `_stream_chat()` before the HTTP request. Use
`asyncio.create_task()` (fire-and-forget) to avoid blocking.

---

## 8. Validation & Success Criteria

### 8.1 Tool registry parity

**AC-1**: `aq-chat /tools` command output shows exactly 14 AI coordination tools (same names as
`build_registry()` in `aq-agent-loop`). Verified by running `/tools` and diffing against the
`register_ai_coordination_tools()` registration list in `ai_coordination.py`.

**AC-2**: Spawning a task via `aq-chat` (interactive) and the same task via
`delegate-to-local --mode agent --wait` produces the same set of available tools reported in
the agent's first tool enumeration step.

### 8.2 HUD transparency

**AC-3**: HUD format is `[profile | wire-profile | tools:N]`. After a tool-free turn,
`wire-profile` shows `cont` (continue-local) or `def` (default). After an agentic turn,
`wire-profile` shows `ltc` (local-tool-calling).

**AC-4**: `--no-tools` flag changes `tools:N` to `tools:0` in HUD immediately at session start.

### 8.3 Intent classifier

**AC-5**: `classify_chat_intent("what is a nixos flake?", [])` returns `"conversational"`.

**AC-6**: `classify_chat_intent("implement the missing cache-eviction handler in dispatcher.py", [])`
returns `"agentic"`.

**AC-7**: `classify_chat_intent("explain X without using tools", [])` returns `"tool-required"`
with `tools_enabled=False` metadata.

**AC-8**: Unit test suite passes with 100% coverage of intent classifier logic.

### 8.4 Conversational fast-path

**AC-9**: A conversational turn (e.g. "explain what aq-qa does") routes to switchboard, not
coordinator. Confirmed by: (a) no entry in coordinator delegate metrics for the turn, (b)
`routing_decision` event shows `fast_path=true`.

**AC-10**: An agentic turn (e.g. "read the issues backlog and suggest the top fix") routes to
coordinator. Confirmed by coordinator delegate metrics showing the turn.

**AC-11**: Fast-path turn latency is measurably lower than delegate-path latency on identical
conversational prompts. Target: ≥50ms reduction in time-to-first-token.

### 8.5 Unified tool control

**AC-12**: `--no-tools` session flag: `TOOL-FREE TURN:` system message is NOT injected.
Coordinator receives `profile=default` with no tool-free system message prefix.

**AC-13**: Explicit per-turn tool-free phrase in prompt: `TOOL-FREE TURN:` system message IS
injected. Coordinator receives `profile=default` with tool-free system message.

**AC-14**: Both AC-12 and AC-13 produce `profile=default` in the coordinator payload, with
identical coordinator behavior but different system message content (AC-12: no injection,
AC-13: injection).

### 8.6 Regression: existing paths unbroken

**AC-15**: Agentic turns that previously worked (e.g. "run a self-improvement slice") continue
to route to coordinator `local-tool-calling` profile and complete successfully.

**AC-16**: `aq-qa 0` health check score does not decrease after implementation (baseline ≥ the
score at implementation start).

**AC-17**: `delegate-to-local --mode agent --wait --prompt "list open issues"` continues to
work without modification.

---

## 9. Risks & Mitigations

### Risk 1 — Tool parity gap confirmed in Phase A

**Description**: `local_agent_runtime.py` may not call `register_ai_coordination_tools()`,
meaning coordinator-spawned agents have a subset of tools compared to `aq-agent-loop`.
**Severity**: HIGH — interactive sessions have systematically fewer tools than stated.
**Mitigation**: Phase A is mandatory first. If gap found, Phase B fix is ~2 lines. The fix
carries no performance risk (registration is startup-time, not per-turn).
**Residual risk**: LOW after fix.

### Risk 2 — Intent classifier false negatives on agentic turns

**Description**: `classify_chat_intent()` misclassifies an agentic prompt as `"conversational"`,
routing it to the fast-path where no tools are available, producing an unhelpful response.
**Severity**: MEDIUM — user receives a response without tool grounding.
**Mitigation**: (a) Conservative classifier: default to `"agentic"` on any uncertainty; only
return `"conversational"` on high-confidence short queries with no file/command keywords.
(b) When fast-path response contains self-referential regret phrases ("I cannot access",
"I don't have tools") — resubmit via coordinator path automatically (one retry).
(c) User can always force coordinator path via `/route ltc` or `--profile local-tool-calling`.
**Residual risk**: LOW with conservative default.

### Risk 3 — Switchboard `continue-local` profile token budget too small

**Description**: `continue-local` has `maxOutputTokens=768` vs `local-tool-calling`'s 2048.
A conversational turn that generates a long response may be truncated.
**Severity**: MEDIUM — truncated responses for verbose conversational queries.
**Mitigation**: Expose `SWB_CONTINUE_LOCAL_MAX_OUTPUT_TOKENS` env override in the profile
(already exists: `SWB_CONTINUE_LOCAL_MAX_INPUT_TOKENS`). Document recommendation to increase
this for aq-chat use. The fast-path payload can also specify `max_tokens` to override per-turn.
**Residual risk**: LOW — operator-configurable.

### Risk 4 — `chat_template_kwargs` not forwarded through fast-path

**Description**: If aq-chat omits `chat_template_kwargs: {enable_thinking: false}` in the
fast-path payload, the model may produce thinking tokens and an empty/malformed response.
**Severity**: HIGH — known failure mode documented in MEMORY.md.
**Mitigation**: The proposed fast-path payload construction in §5.6 explicitly includes this
field. Test AC validation must verify it is present in the wire payload.
**Residual risk**: LOW if AC validation covers this field.

### Risk 5 — Coordinator `_spawn_local_agent` ignores `local_snapshot` case

**Description**: If a `local_snapshot=True` turn is accidentally routed to the fast-path,
the snapshot system message is not sent to the coordinator, and the model answers without
grounding.
**Severity**: MEDIUM.
**Mitigation**: The fast-path branch condition in §5.6 explicitly excludes `local_snapshot=True`
turns. This is a guard, not a heuristic — snapshot turns always go to coordinator.
**Residual risk**: LOW.

### Risk 6 — Dual control asymmetry produces untested edge case with `--no-tools` + per-turn phrase

**Description**: User starts session with `--no-tools` AND includes a tool-free phrase in prompt.
**Severity**: LOW — same outcome either way (`profile=default`, no tools).
**Mitigation**: `ToolMode.session_enabled=False` takes unconditional precedence in
`resolve_tool_mode()`. Per-turn override is only evaluated when `session_enabled=True`.
**Residual risk**: NONE — defined precedence.

### Risk 7 — `local_agent_runtime.py` cannot be modified (runs as ai-hybrid service user)

**Description**: If `local_agent_runtime.py` runs as service user `ai-hybrid` and tool
registration requires writing to paths owned by `hyperd`, the fix may fail silently at runtime
even if the code is correct.
**Severity**: MEDIUM.
**Mitigation**: Tool registration in `local_agent_runtime.py` only creates in-memory
`ToolRegistry` objects — no file writes. The httpx calls from tool handlers go to loopback
services. The service user constraint documented in MEMORY.md applies to file writes, not in-memory
registration. Should be safe. Verify with a test invocation under `ai-hybrid` user context.
**Residual risk**: LOW.

---

## 10. Open Questions

**OQ-1 — local_agent_runtime.py tool initialization path (BLOCKING for Phase B)**
The key file `ai-stack/agents/runtimes/local_agent_runtime.py` was not available in the files
listed in the brief and was not read during this analysis. Whether it calls
`initialize_builtin_tools()` or `build_registry()` or a custom subset is **unknown**. This
must be resolved in Phase A before any implementation work on tool parity.

**OQ-2 — Coordinator delegate fast-path: should conversational turns go to switchboard directly
from aq-chat, or should the coordinator grow a fast-path that transparently passes through to
switchboard without subprocess overhead?**
The proposed architecture (§5.6) bypasses the coordinator from aq-chat. An alternative is to
add a `intent=conversational` fast-path inside `handle_ai_coordinator_delegate()` that calls
`_post_delegate("continue-local")` without spawning a subprocess. This would preserve the
single-entry-point invariant but add complexity to the coordinator. The team was split: Systems
Architect and Performance Analyst favor the aq-chat bypass (simpler, less coordinator complexity);
Coordinator/Switchboard Domain Expert prefers the coordinator fast-path (single audit trail,
consistent event emission). Resolution needed before Phase E.

**OQ-3 — Should `active_wire_profile` be the profile sent to coordinator, or the profile the
coordinator ultimately selected after routing/fallback?**
For HUD accuracy, the operator wants to know what routing decision was actually made, including
fallbacks. This requires the coordinator to return `selected_profile` in the response body.
Currently the coordinator returns a standard OpenAI-compat response body without routing metadata.
Adding `routing_metadata` to the response body is out of scope for this PRD but is a prerequisite
for full HUD accuracy. For Phase D, `active_wire_profile` should show what aq-chat sent (the
requested profile), not what the coordinator selected. A follow-on phase can add `X-Routing-Profile`
response header from the coordinator.

**OQ-4 — What is the right `maxOutputTokens` for the conversational fast-path?**
The `continue-local` profile has 768 tokens. For `aq-chat` interactive use, this may be too
small (harness explanations can be 1500–2000 tokens). The `local-tool-calling` profile has 2048.
Should the fast-path use `continue-local` or a new `local-chat` profile with higher output budget?
The Systems Architect recommends using `local-tool-calling` profile for the fast-path (same
token budget, same hints injection) but with `tools=[]` and `tool_choice=none` to disable tool
execution while keeping the same context budget. The Coordinator/Switchboard Domain Expert
disagrees — misusing `local-tool-calling` with empty tools is semantically confusing. Needs
resolution.

**OQ-5 — Should `classify_chat_intent()` be a pure function in `chat_intent.py` or should it
use the AIDB/hints service for semantic classification?**
A pure heuristic classifier (dispatch.py style) is fast (< 1ms, no network) but may miss novel
agentic patterns. A hybrid classifier that optionally queries `get_hint()` for context-specific
guidance would be more accurate but adds ~10–50ms latency on every turn. The Performance
Analyst strongly prefers the pure heuristic approach with a conservative default of `"agentic"`
on ambiguity. The Tool Registry Specialist notes that a classifier that calls `get_hint()` would
itself require a tool call, creating a bootstrapping paradox. Team consensus: pure heuristic,
conservative default. Document this in the classifier's docstring.

**OQ-6 — Tool count in HUD: fetch from coordinator tool-manifest endpoint or from local
`initialize_builtin_tools()` invocation?**
Fetching from the coordinator reflects the actual runtime tool set. A local invocation is
faster but may not reflect what the subprocess sees. Given OQ-1 is unresolved, the team
recommends fetching from coordinator tool-manifest endpoint (to be created in Phase C) rather
than trusting a local in-process count.

---

## 11. Team Sign-off

**Systems Architect**: APPROVED with CONCERN: OQ-2 (bypass location) must be resolved before
Phase E implementation. Recommend coordinator fast-path to preserve single-entry-point audit
contract. The aq-chat bypass creates a second routing code path that must be maintained in
parallel. If the team selects aq-chat bypass, document it explicitly in AGENTS.md.

**Coordinator/Switchboard Domain Expert**: APPROVED with CONCERN: OQ-4 (token budget). The
fast-path must not use `local-tool-calling` with empty tools — this creates an implicit contract
that the profile is always used with tools. Recommend a new `local-chat` profile entry in
`DEFAULT_PROFILE_CATALOG` (switchboard.py) with `toolExecution: None` and `maxOutputTokens: 1536`.
This is a one-entry catalog addition, not a rebuild concern.

**Tool Registry Specialist**: APPROVED — Phase A verification is critical and must produce a
documented finding before any other phase begins. The 14-tool inventory in `ai_coordination.py`
is the canonical reference. Any divergence in `local_agent_runtime.py` is a P0 fix. The
`/tools` slash command in aq-chat (§5.5 Phase C) should call the tool-manifest endpoint and
render both the expected list and the actual list side-by-side for diff visibility.

**CLI UX Designer**: APPROVED with CONCERN: The proposed HUD format `[local | ltc | tools:14]`
uses abbreviations that are not self-explanatory to a new operator. Recommend adding a `/status`
sub-panel that expands abbreviations to full names on demand, and updating the session start
banner to print the full resolved routing config. The compact HUD is acceptable for experienced
operators; onboarding needs the expanded view.

**Performance Analyst**: APPROVED. The coordinator fast-path bypass (§5.6) is the highest-value
change in this PRD. Estimated savings: 80–300ms per conversational turn, reduced coordinator
asyncio lock contention, zero subprocess spawn cost. On a Renoir APU at 10 tok/s, eliminating
200ms overhead saves 2 output tokens of equivalent model time per turn — marginal but meaningful
for interactive use. Recommend adding a per-turn latency annotation to the `routing_decision`
telemetry event (time-to-first-token measured from prompt submission to first response byte).

**Observability Engineer**: APPROVED with CONCERN: The `routing_decision` event (§5.8) is
necessary but not sufficient. The coordinator delegate handler should emit a complementary
`coordinator_routing` event on every delegate call that includes `selected_profile`,
`routing_rationale`, `tool_count_spawned`, and `spawn_latency_ms`. Without this, the aq-chat
`routing_decision` event cannot be correlated with the actual coordinator execution. The
coordinator event is explicitly out of scope for this PRD but should be filed as a follow-on
issue in `memory/issues-backlog.md`.

**QA / Test Engineer**: APPROVED with CONCERN: AC-9 ("no entry in coordinator delegate metrics
for conversational turn") requires coordinator metrics to have per-turn resolution. Current
coordinator metrics (`/api/health/layered`) are aggregate, not per-turn. Recommend using the
`routing_decision` telemetry event as the primary AC-9 validation mechanism (inspect JSONL file
after a test conversation) rather than coordinator metrics. Add a test fixture in
`scripts/testing/` that runs a 5-turn conversation with known intents and validates the
`routing_decision` events in the JSONL output match expected `fast_path` values. This test must
be non-destructive (read-only) and runnable as `hyperd` user without rebuilds.

---

*Document version: 1.0-draft*
*Produced by: Codex Expert Team (7-role independent analysis)*
*Files read: scripts/ai/aq-chat (848L), ai-stack/local-agents/agent_executor.py (1387L),*
*ai-stack/local-agents/__init__.py (169L), ai-stack/local-agents/builtin_tools/ai_coordination.py (731L),*
*ai-stack/switchboard/switchboard.py (3117L, sampled), ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py (2728L, sampled),*
*scripts/ai/aq-agent-loop (282L), scripts/ai/delegate-to-local (193L), scripts/ai/lib/dispatch.py (signatures)*
*NOTE: ai-stack/agents/runtimes/local_agent_runtime.py was NOT read (not in listed relevant files).*
*This is OQ-1 — the single most critical unresolved item.*
