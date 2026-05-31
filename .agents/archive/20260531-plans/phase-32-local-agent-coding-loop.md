# Phase 32 — Local Agent Coding Loop

## Objective
Wire the existing Phase 11 tool infrastructure into a functional coding agent loop
so Qwen3.6-35B can read/write files, validate changes, and produce auditable output —
reducing dependency on paid remote agents (Gemini/Codex/Claude) for bounded coding tasks.

## Scope Lock
- **In scope**: git_tools.py (new), agent_executor.py (timeout fix only), aq-agent-loop (new CLI), delegate-to-local (--mode agent only)
- **Out of scope**: Rewriting agent loop, new NixOS modules, model routing, tool registry schema changes
- **Constraints**: No new Python packages; stdlib + httpx only; no destructive tools

## Workstreams

### 32.1 — Git tools for local agents
File: `ai-stack/local-agents/builtin_tools/git_tools.py`
Tools:
- `git_status()` → READ_ONLY — run `git status --short` in repo root
- `git_diff(staged=False)` → READ_ONLY — `git diff` or `git diff --staged`
- `git_add(files: list[str])` → WRITE_SAFE — `git add <files>` (repo-relative paths only)
- `validate_before_commit()` → READ_ONLY — run tier0-validation-gate.sh --pre-commit

### 32.2 — Fix LocalAgentExecutor for coding workloads
File: `ai-stack/local-agents/agent_executor.py`
Changes (minimal):
- `_call_llama` timeout: 30.0 → 300.0 (Qwen3.6 needs 90-120s per call)
- `_call_llama` max_tokens: 2000 → 4096
- `_call_llama` temperature: 0.7 → 0.2 (deterministic code generation)

### 32.3 — `aq-agent-loop` CLI
File: `scripts/ai/aq-agent-loop`
Python script that:
1. Sets sys.path to include `ai-stack/local-agents/`
2. Instantiates ToolRegistry and registers file_ops + shell + git tools
3. Creates LocalAgentExecutor (offline_mode=True by default — no remote fallback for coding)
4. Runs execute_task with max_tool_calls=15
5. Writes JSON summary + full response to --output file
6. Returns 0 on success, 1 on failure

CLI interface:
  `aq-agent-loop --task "TEXT" [--output FILE] [--max-calls N] [--fallback]`
  `aq-agent-loop --list-tools`

### 32.4 — Wire delegate-to-local --mode agent
File: `scripts/ai/delegate-to-local`
Change: Add `--mode agent` that calls `aq-agent-loop --task "$prompt" --output "$output_file"`
(blocking or background, same registry pattern as other modes)

## Step Plan
1. Write git_tools.py (32.1) → py_compile validate → commit
2. Patch agent_executor.py timeout/max_tokens (32.2) → py_compile validate → commit
3. Write aq-agent-loop script (32.3) → bash -n + py_compile → smoke test → commit
4. Patch delegate-to-local (32.4) → bash -n → commit

## Validation
```bash
python3 -m py_compile ai-stack/local-agents/builtin_tools/git_tools.py
python3 -m py_compile ai-stack/local-agents/agent_executor.py
bash -n scripts/ai/aq-agent-loop
bash -n scripts/ai/delegate-to-local
scripts/governance/tier0-validation-gate.sh --pre-commit
aq-qa 0
```

## Rollback
- git_tools.py: `git rm ai-stack/local-agents/builtin_tools/git_tools.py`
- agent_executor.py: `git checkout HEAD~1 -- ai-stack/local-agents/agent_executor.py`
- aq-agent-loop: `git rm scripts/ai/aq-agent-loop`
- delegate-to-local: `git checkout HEAD~1 -- scripts/ai/delegate-to-local`
