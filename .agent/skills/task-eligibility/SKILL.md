# Task Eligibility Skill
## Tags
eligibility, task-class, routing, local, gemini, codex, claude, thermal, batch, background, MLFQ
## When to Use
Deciding which agent to route a task to; understanding why a task was refused by local model;
thermal-critical conditions; choosing between delegate-to-local modes; understanding batch vs
background task class restrictions.

---

## 1. Agent Capability Matrix

| Capability | Claude | Gemini (auto_edit) | Gemini (yolo) | Codex | Local (direct) | Local (agent) |
|-----------|--------|-------------------|---------------|-------|----------------|---------------|
| File read | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| File edit | ✓ | ✓ | ✓ | ✓ (patch) | ✗ | ✓ |
| Shell exec | ✓ | ✗ | ✓ | ✓ | ✗ | limited |
| Web fetch | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| RAG query | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ (MCP) |
| Live service query | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Multi-turn reasoning | ✓ | ✓ | ✓ | ✓ | ✓ | limited |
| Git operations | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |

---

## 2. Local Model Task Eligibility

The local model (Qwen3-35B) is bounded by hardware and MLFQ scheduling.

### Mode Selection

| Mode | Best for | Constraints |
|------|---------|-------------|
| `--mode direct` | Reasoning, analysis, debate, structured JSON output | No tool access; cannot call live services; max ~512 tokens |
| `--mode agent` | Tasks needing RAG/memory/coordinator queries | Tool calls via MCP; slow at 1 tok/s; 180 token output ceiling (coordinator) |
| `--mode hybrid` | RAG-grounded lookups ONLY | Coordinator intent classifier may defer "planning" tasks to Claude (empty response) |
| `--mode auto` | Default; heuristic selects direct/agent/hybrid | May mis-classify edge cases |

### Task Class Filter (MLFQ)

| Task Class | Eligibility | Notes |
|-----------|-------------|-------|
| `background` | ✓ always | Lowest priority, runs when CPU idle |
| `batch` | ✗ under thermal=critical | CPU temp ≥85°C blocks batch; use background instead |
| `interactive` | ✓ L0 priority | Set `agent_type=human` in coordinator delegate payload |
| `coding` | ✓ implementer only | Detected by `_CODE_TASK_RE` in agent_executor.py |

**Thermal gate**: when `thermal_tier == critical` (≥85°C), batch tasks are refused by MLFQ.
Use `background` task class or defer to remote agent.

---

## 3. Gemini Eligibility Rules

Gemini has **two modes** with different eligibility:

### auto_edit mode (default for most delegation)
- File read/edit/search: ✓
- Shell commands: ✗ (`run_shell_command` does not exist — wastes a turn)
- Live service queries: ✗
- Git operations: ✗
- Web fetch: ✓ (`web_fetch` tool available)

**Eligible task types in auto_edit**:
- Code editing within declared slice
- File content verification (acceptance criteria check via grep_search)
- Research and synthesis (reading files, searching patterns)
- Review (using file-verifiable criteria only)
- Writing new files

**Not eligible in auto_edit**:
- Running tests (`aq-qa`, `pytest`)
- Curling live endpoints
- Anything requiring shell execution

### yolo mode (explicit `--mode yolo`)
- Full shell access: ✓
- All git operations: ✓
- Live service queries: ✓
- Same eligibility as Codex

---

## 4. Codex Eligibility Rules

- Shell access: ✓ (but requires `< /dev/null` stdin)
- Large prompts: must use `--prompt-file /tmp/file.txt` (not inline)
- Edit format: uses `apply_patch` (unified diff) — request patches, not `replace` calls
- Git operations: ✓
- RAG queries: ✗ (no MCP access)

**Eligible for**: large implementation slices, complex multi-file refactors, integration work,
final acceptance when orchestrator needs a clean diff.

---

## 5. Task → Agent Routing Recommendations

| Task type | Preferred agent | Fallback |
|-----------|----------------|---------|
| Quick analysis, reasoning | Local (direct) | Claude |
| RAG lookup, memory recall | Local (agent) | Claude |
| Code edit (bounded slice) | Gemini (auto_edit) | Codex |
| Code edit (needs shell validation) | Gemini (yolo) or Codex | Claude |
| Large refactor (multi-file) | Codex | Claude |
| Review (file-verifiable) | Gemini (auto_edit) | Claude |
| Review (needs runtime check) | Claude | Gemini (yolo) |
| NixOS module changes | Claude (needs rebuild context) | Codex |
| Emergency fix (runtime needed) | Claude | Gemini (yolo) |

---

## 6. Refusing a Task (Implementer Self-Check)

If you receive a task that exceeds your eligibility:

```
ELIGIBILITY_REFUSED: <task type> exceeds this agent's capability class
Agent: gemini/auto_edit
Reason: task requires shell execution (aq-qa validation) — not available in auto_edit mode
Recommendation: re-delegate to Gemini yolo mode or Claude
```

Do NOT attempt a task you can't complete and then fail silently — state the limitation early
so the orchestrator can re-route efficiently.

---

## 7. Lane Selection (Cost-Aware Routing)

From CLAUDE.md Rule 4: "Prefer local inference for bounded tasks; remote only when task value justifies cost."

```
Local model:  0 API cost, 1-2 tok/s, 180 token output ceiling, thermal-sensitive
Gemini:       API cost, fast, no shell in auto_edit
Codex:        API cost, fast, needs /dev/null stdin
Claude:       API cost, highest quality, full tool access
```

Decision threshold:
- Task output < 180 tokens AND no shell needed → local (direct or agent)
- Task needs file edits + is bounded → Gemini (auto_edit)
- Task needs shell validation → Gemini (yolo) or Codex
- Task needs codebase understanding + high quality → Claude
