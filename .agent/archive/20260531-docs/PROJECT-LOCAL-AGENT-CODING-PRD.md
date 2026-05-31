# PRD — Phase 32: Local Agent Coding Loop

**Author**: hyperd (orchestrated with Claude Sonnet 4.6)
**Date**: 2026-05-13
**Status**: APPROVED — executing immediately

---

## Problem

The local Qwen3.6-35B model can GENERATE code but cannot EXECUTE file changes
autonomously. Gemini and Codex have agent loops (reason → tool-call → execute → repeat).
The local model has no equivalent entry point, so all implementation work routes through
remote paid agents, burning daily/weekly token limits unnecessarily.

## Existing Infrastructure (Phase 11 — already complete)

- `ai-stack/local-agents/tool_registry.py` — ToolRegistry, ToolDefinition, SafetyPolicy
- `ai-stack/local-agents/builtin_tools/file_operations.py` — read_file, write_file, list_files, search_files (ALLOWED_BASE_PATHS includes ~/Documents — covers repo)
- `ai-stack/local-agents/builtin_tools/shell_tools.py` — run_command (whitelisted), get_system_info, check_service
- `ai-stack/local-agents/agent_executor.py` — LocalAgentExecutor with full tool-use loop, remote fallback
- Switchboard `local-tool-calling` profile — wired into http_server.py

## Gaps (what is actually missing)

1. **Git tools** — no git_status, git_diff, git_add, validate_before_commit
2. **LocalAgentExecutor bugs blocking coding use**:
   - `_call_llama` timeout = 30s → must be 300s+ (Qwen3.6-35B takes 90–120s/response)
   - `max_tokens = 2000` → must be 4096 for coding tasks
3. **No `aq-agent-loop` CLI** — no command-line entry point to run a coding task
4. **`delegate-to-local`** has no `--mode agent` option

## Goal

Enable the local model to perform bounded coding tasks:
- Read files → understand context
- Write files → implement changes
- Run git_diff / validate_before_commit → verify changes
- Produce a summary the orchestrator (Claude) can audit and commit

## Scope

**In scope (Phase 32):**
- `ai-stack/local-agents/builtin_tools/git_tools.py` — 4 git tools
- `ai-stack/local-agents/agent_executor.py` — fix timeout (30s→300s) + max_tokens (2000→4096)
- `scripts/ai/aq-agent-loop` — CLI entry point
- `scripts/ai/delegate-to-local` — add `--mode agent`

**Out of scope:**
- Rewriting the agent loop (LocalAgentExecutor works)
- OpenAI native tool_calls format (current text-parsing loop is functional)
- NixOS module / systemd service wrapping
- Model routing changes

## Acceptance Criteria

1. `aq-agent-loop --task "read AGENTS.md and summarize it" --wait` completes in <300s
2. Local model can read a file, write a modified version, and run git_diff
3. `validate_before_commit` blocks writes if tier0 gate fails
4. `delegate-to-local --mode agent --prompt "..."` dispatches to aq-agent-loop
5. tier0 passes on all changed files

## Security Requirements

- `write_file` already has path validation (ALLOWED_BASE_PATHS)
- `git_add` restricted to repo root and below
- `validate_before_commit` must run before any `git_add` + commit sequence
- `run_command` safe-list maintained — do NOT add `rm` or `sudo` to whitelist
- All tool calls audited via existing SQLite audit trail

## Rollback

- Revert git_tools.py (new file — just delete)
- Revert agent_executor.py timeout change (restore 30.0 / 2000)
- Delete aq-agent-loop
- Revert delegate-to-local --mode agent addition
