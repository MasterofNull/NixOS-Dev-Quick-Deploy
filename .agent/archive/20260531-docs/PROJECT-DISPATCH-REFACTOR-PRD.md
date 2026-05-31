# PRD: Local Agent Dispatch Consolidation
**Phase**: 74 · **Status**: Draft — pending team review · **Date**: 2026-05-28

## Problem

`delegate-to-local` is a 674-line bash script doing 7 separate jobs with no abstraction:
mode routing, registry management, payload construction, slot scheduling, token budget
management, audit logging, and background process management. The rest of the dispatch
chain has drifted to match its shape, producing six concrete fragmentation problems:

1. **run_direct bypasses build_llama_payload SSOT** — inline Python heredoc re-implements
   all constraints (`chat_template_kwargs`, `stream`, `max_tokens`) independently.
   Future constraint changes require two edits.

2. **104 llama.cpp call sites** — not all using shared/llm_config.py. Token constraint
   drift is guaranteed over time.

3. **Four token-limit env vars** (`DIRECT_MAX_TOKENS`, `LLAMA_MAX_TOKENS`, `EVAL_MAX_TOKENS`,
   `AGENT_MAX_TOKENS`) in different subsystems with different defaults. `config/switchboard-profiles.yaml`
   has canonical profiles but `delegate-to-local` never reads them.

4. **Mode selection is user-burden** — user must know `hybrid` silently returns empty for
   planning tasks; `direct` skips system-message role injection; `agent` has different
   timeout semantics. Wrong mode = silent failure.

5. **Inconsistent role injection across modes** — `run_agent` uses `build_llama_payload(role=)`
   (system message) ✓; `run_direct` uses `[ROLE: X]` text prefix in user message ✗;
   `run_hybrid` passes role in POST body but coordinator doesn't consume it ✗.

6. **Three divergent persistence paths** — `registry.jsonl` + `PENDING.json` + `HANDOFF.md`
   updated by 5 separate inline Python heredocs. Recent `update_status()` arg-order bug
   is a direct symptom.

## Goals

1. Single Python entry point for all local task dispatch — `scripts/ai/lib/dispatch.py`
2. `TaskConfig` dataclass as the single config object — built once, consumed by all runners
3. All modes use `build_llama_payload` (SSOT). Role injection consistent across direct/hybrid/agent.
4. Switchboard profiles consumed for token budgets — no more scattered env vars
5. Unified task registry — one Python class, one code path, three output formats
6. `delegate-to-local` shrinks to ~80-line arg-parsing shim
7. Backward compatibility: all existing CLI flags and env vars continue to work

## Non-Goals

- Changing coordinator (`hybrid-coordinator`) internals
- Renaming `AgentType → ExecutionModality` (P2.1 cosmetic, deferred)
- Mode auto-selection (Phase E — requires debate, deferred)
- Touching remote delegation scripts (`delegate-to-gemini`, `delegate-to-codex`)

## Phased Implementation

### Phase A — `lib/slot_scheduler.py` (Low risk)
Extract slot pre-poll logic from `run_direct` inline heredoc into a standalone Python module.
- Input: `base_url`, `timeout_secs`
- Output: slot confirmed free (or timed out with fallback)
- Reusable by all runners
- **Acceptance**: `python3 -c "from slot_scheduler import wait_for_slot; print('PASS')"` ✓

### Phase B — `lib/task_registry.py` (Medium risk)
Unified Python class replacing 5 inline Python heredocs for persistence.
- `TaskRegistry.append(task_id, ...)` → writes to `registry.jsonl`
- `TaskRegistry.update_status(task_id, status)` → updates `registry.jsonl`
- `TaskRegistry.record_dispatch(...)` → writes to `PENDING.json` + `HANDOFF.md`
- All three formats maintained from one code path
- **Acceptance**: existing `pending-update list` output unchanged

### Phase C — `lib/task_config.py` (Medium risk)
`TaskConfig` dataclass built from: CLI args → switchboard profile → AgentType default mapping → hardcoded fallbacks.
- Reads `config/switchboard-profiles.yaml` for token budgets
- Maps switchboard profile name to (max_tokens, timeout, temperature)
- `AgentType → mode` mapping: AGENT→agent, PLANNER→direct, CHAT→direct, EMBEDDED→None
- **Acceptance**: `TaskConfig.from_cli(mode="direct", role="architect")` returns correct budget

### Phase D — `lib/dispatch.py` (Medium-high risk)
Single Python entry point replacing `run_direct` / `run_hybrid` inline Python.
- All runners call `build_llama_payload(role=task_config.role)` — consistent system message injection
- `DirectRunner`, `HybridRunner` as thin wrappers consuming `TaskConfig`
- `AgentRunner` remains as `aq-agent-loop` invocation (already Python)
- **Acceptance**: smoke test each mode; verify role in system message for all three

### Phase E — Mode auto-selection (Deferred — needs team debate)
Heuristic: task content → suggested mode. Override always available.
- Open question: what signals reliably distinguish direct vs agent vs hybrid?
- Open question: should this be in the coordinator or in dispatch.py?

### Phase F — Thin bash shim (Final integration)
`delegate-to-local` becomes an 80-line arg-parsing shim calling `python3 -m lib.dispatch`.
- All logic moved to Python; bash handles: arg parsing, env var loading, nohup management
- **Acceptance**: all existing tests pass; `bash -n delegate-to-local` ✓

## Architecture Diagram

```
delegate-to-local (bash ~80 lines)
  └─ python3 lib/dispatch.py
       ├─ TaskConfig.from_cli(mode, role, timeout, tokens)
       │    ├─ reads config/switchboard-profiles.yaml
       │    └─ applies AgentType default mapping
       ├─ slot_scheduler.wait_for_slot(base_url, timeout)
       ├─ [DirectRunner | HybridRunner | AgentRunner]
       │    └─ build_llama_payload(messages, role=config.role)  ← ALL use SSOT
       └─ task_registry.record(task_id, status, output_file)
            ├─ registry.jsonl
            ├─ PENDING.json
            └─ HANDOFF.md
```

## Open Questions (for team review)

- Q1: Should `TaskConfig` consume the switchboard profile automatically based on mode,
  or should the caller always specify? (auto-select = less friction, explicit = more control)
- Q2: Phase E mode auto-selection — coordinator-side or client-side?
- Q3: Should `task_registry.py` replace `pending-update` entirely, or call it as a subprocess
  for backward compatibility?
- Q4: Is `run_ralph` (ralph-wiggum routing) in scope for this refactor?
- Q5: Should `HybridRunner` be deprecated in favor of coordinator improvements,
  or kept as a parallel path?

## Validation Suite

```bash
# Phase A
python3 -c "from lib.slot_scheduler import wait_for_slot; print('PASS: slot_scheduler importable')"

# Phase B
python3 -c "from lib.task_registry import TaskRegistry; print('PASS: registry importable')"
python3 scripts/ai/lib/pending-update list  # output unchanged

# Phase C
python3 -c "
from lib.task_config import TaskConfig
c = TaskConfig.from_cli(mode='direct', role='architect')
assert c.max_tokens <= 1200, 'token budget too high for direct'
print('PASS: TaskConfig direct budget')
"

# Phase D
delegate-to-local --mode direct --role implementer --prompt 'Say PASS' --wait --timeout 60
# verify: system message contains [Role: implementer]

# Full integration
scripts/governance/tier0-validation-gate.sh --pre-commit
```
