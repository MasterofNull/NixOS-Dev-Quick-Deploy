# PRD: Agent Role Standardization
**Phase**: 73 · **Status**: P1 implemented · **Date**: 2026-05-28

## Problem

The harness runs four models (Claude, Gemini, Codex, Qwen3) and routes tasks through a
coordinator, but every agent operates role-blind. The `Task` dataclass has no role field.
`build_llama_payload()` injects no authority context. Switchboard profiles are token-budget
configs with no role awareness. The result: agents overstep, re-scope tasks, and produce
misaligned output because they have no machine-readable signal for what they are authorised
to do in a given session.

## Goals

1. Every local inference call carries a compact role authority block in the system prompt
   when a role is explicitly assigned — zero overhead when unassigned.
2. The coordinator auto-assigns role at dispatch time from a stable
   `AgentType → default_role` mapping, eliminating manual role specification.
3. `AgentType` (capability class) and role (authority class) are formally documented as
   orthogonal axes; the mapping table is the SSOT for auto-assignment.

## Non-Goals

- Embedding server (port 8081) never receives role injection — it has no text generation.
- Switchboard profiles remain role-blind — they are token-budget configs, not authority
  configs. Mixing concerns would break both.
- Full rename of `AgentType → ExecutionModality` deferred (P2 — requires grep across all
  call sites and is a cosmetic change with no runtime impact today).

## Agreed Positions (tri-agent debate: Claude + Gemini round 1)

| Question | Position |
|----------|----------|
| Q1: Inject into every payload? | No — only when `task.role` is explicitly set. Implementer is implicit default (~25-40 tok overhead when active). |
| Q2: Auto-assignment mechanism | `Task.role: Optional[str]` field + `AgentType→default_role` mapping. Coordinator assigns at dispatch. |
| Q3: AgentType vs role matrix | Orthogonal — keep both. AgentType = capability, role = authority. Add mapping table as SSOT. |
| Q4: Embedded model + roles | Never. Would mathematically shift embedding vectors away from target semantics. |

## Implementation

### P1 — DONE (commit: pending)

| # | File | Change |
|---|------|--------|
| 1 | `ai-stack/local-agents/agent_executor.py` | `Task.role: Optional[str] = None` field + `to_dict()` update |
| 2 | `ai-stack/local-agents/agent_executor.py` | `AGENT_TYPE_DEFAULT_ROLE` + `AGENT_TYPE_ELIGIBLE_ROLES` mappings |
| 3 | `ai-stack/local-agents/agent_executor.py` | `execute_task` auto-assigns `task.role` from mapping if None |
| 4 | `ai-stack/local-agents/agent_executor.py` | `role` threaded through `_execute_with_tools` → `_call_llama` |
| 5 | `ai-stack/mcp-servers/shared/llm_config.py` | `ROLE_SYSTEM_PROMPTS` dict (4 compact role blocks, ~25-35 tok each) |
| 6 | `ai-stack/mcp-servers/shared/llm_config.py` | `_inject_role()` helper — prepends to existing system msg or inserts one |
| 7 | `ai-stack/mcp-servers/shared/llm_config.py` | `build_llama_payload(role=None)` — injects when set, zero cost when None |

**Default role mapping:**
```python
AGENT_TYPE_DEFAULT_ROLE = {
    AgentType.AGENT:    "implementer",
    AgentType.PLANNER:  "architect",
    AgentType.CHAT:     "implementer",
    AgentType.EMBEDDED: None,   # never injected
}
```

**Role blocks (injected into system prompt):**
- `orchestrator` — open/close sessions, assign slices, accept work, commit integration
- `architect` — draft architecture, flag risks, write PRDs; requires orchestrator review
- `implementer` — execute assigned slice only; validate; propose commit; no re-scoping
- `reviewer` — explicit pass/fail verdict against criteria; cannot review own work

### P2 — Pending

| # | Change | Owner |
|---|--------|-------|
| 1 | Rename `AgentType → ExecutionModality` (cosmetic, grep all call sites) | claude |
| 2 | Coordinator dispatch wires `task.role` from HTTP request body when caller specifies | claude |
| 3 | `delegate-to-local` / `delegate-to-gemini` accept `--role` flag and pass to coordinator | claude |
| 4 | Agent loop multi-role team prompt pattern documented in `.agent/LOCAL-AGENT.md` | gemini |

### P3 — Backlog

| # | Change | Owner |
|---|--------|-------|
| 1 | Dashboard panel: show role distribution across recent tasks | qwen (bounded) |
| 2 | QA check: verify role field present in task output for agent-mode tasks | qwen (bounded) |
| 3 | MemoryBroker stores `task.role` alongside completed task facts | qwen (bounded) |

## Validation

```bash
# Syntax
python3 -m py_compile ai-stack/local-agents/agent_executor.py
python3 -m py_compile ai-stack/mcp-servers/shared/llm_config.py

# Role injection smoke test
python3 -c "
from ai_stack.mcp_servers.shared.llm_config import build_llama_payload
msgs = [{'role': 'user', 'content': 'hello'}]
p = build_llama_payload(msgs, role='implementer')
assert p['messages'][0]['role'] == 'system'
assert 'implementer' in p['messages'][0]['content']
assert p['messages'][1]['content'] == 'hello'
print('PASS: role injection')

p2 = build_llama_payload(msgs)
assert p2['messages'][0]['content'] == 'hello'
print('PASS: no injection when role=None')
"

# Auto-assignment: task.role=None → becomes 'implementer' for AgentType.AGENT
```

## Open Questions (from Gemini round 3 — pending response)

- Should `reviewer` role suppress tool-use entirely? (reviewers shouldn't execute code)
- Is there a `trust_level` numeric field needed alongside role for finer-grained coordinator ACL?
- Multi-model team pattern: standardize prompt template for "speak as all specialists" tasks?
