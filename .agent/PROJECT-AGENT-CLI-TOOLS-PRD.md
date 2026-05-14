# PRD: Agentic CLI Tools
**Date**: 2026-05-14
**Owner**: hyperd
**Phase**: Agentic Tooling Enhancements

## Problem
AI agents and humans often use standard Unix CLI tools (`cat`, `ls`, `grep`, `tree`) during exploration and debugging. However, these tools are not optimized for LLM context windows. `cat` can dump massive files, blowing out context limits. `ls` and `tree` can output thousands of lines in large repositories (e.g., `node_modules`). `grep` can return endless repetitive matches. This leads to wasted tokens, context truncation, and inefficient agent loops.

## Goal
Design and build a suite of CLI tools optimized for agentic workflows and token efficiency. These tools will serve as safer, context-aware drop-in replacements for common commands.
They will be developed and tested locally within this project, with the eventual goal of being spun off into an open-source standalone package.

## Non-Goals
- Full POSIX compliance or feature parity with standard GNU tools.
- Replacing the agent's native MCP tool calls (these are for shell usage).
- Complex AST-based semantic parsing (for now, focus on token limits and smart defaults).

## Workstreams

### 1. `als` (Agent List)
**What**: A context-aware replacement for `ls` and `tree`.
**Features**:
- Automatically ignores common noise directories (`.git`, `node_modules`, `__pycache__`, `.pytest_cache`, `.venv`).
- Limits output depth and total item count by default.
- Groups files by type or provides a summary rather than an exhaustive list if the directory is too large.
- Output is compact and token-efficient.

### 2. `acat` (Agent Cat)
**What**: A context-aware replacement for `cat`.
**Features**:
- Adds line numbers by default (crucial for agent editing).
- Hard limits the number of lines or tokens output to prevent context blowout (e.g., max 500 lines).
- Provides a warning if the file was truncated, suggesting the use of `head`/`tail` or a specific line range.
- Supports `--start` and `--end` flags for surgical reads.

### 3. `agrep` (Agent Grep)
**What**: A context-aware replacement for `grep`.
**Features**:
- Limits the number of matches *per file* (e.g., max 5 matches per file) to prevent repetitive noise.
- Limits the *total* number of matches across all files.
- Automatically ignores noise directories.
- Formats output cleanly with line numbers and file paths.

### 4. Implementation & Validation
**What**: Develop the tools as robust scripts (e.g., Python or Bash) in `scripts/agent-tools/`.
**Validation**:
- Write tests to ensure output truncation and ignore logic work correctly.
- Ensure they handle edge cases gracefully (binary files, missing permissions).
- Add a Makefile target or Nix derivation to install them easily into the environment.

## Execution Status
- [x] Create the `scripts/agent-tools/` directory.
- [x] Implement `agrep` (Python) - Done.
- [x] Implement `als` (Python) - Done.
- [x] Implement `acat` (Python) - Done.
- [x] Implement `asum` (Python) - Done.
- [x] Add local unit tests/smoke tests - Done.
- [x] Update documentation - Done.

## Next Steps
- [ ] Integrate into `deploy` CLI or as a standalone Nix package.
- [ ] Add more specialized summarizers for `asum` (JSON, YAML, Go).
- [ ] Implement `adiff` for token-efficient diffing.