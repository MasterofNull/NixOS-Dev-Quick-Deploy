# PRD: Tokenmaxxing — Multi-Agent Collaboration Standards
**Date**: 2026-05-13
**Owner**: hyperd
**Phase**: 33 — Tokenmaxxing Harness Standardization

## Problem
The YC "tokenmaxxing" framework describes practices that maximize AI output per founder:
parallel fan-out, skill I/O contracts, background arbitration, token efficiency, and
structured role specialization. Our harness has the primitives but lacks the standardized
glue that makes these behaviors predictable and ubiquitous across all agents.

## Goal
Every agent (Claude, Gemini, Codex, Qwen) operates from the same playbook:
1. Named, structured skills with explicit I/O contracts
2. Fan-out delegation with result arbitration
3. Token spend tracked per task
4. Output compression to reduce wasted context
5. Role-tagged delegation (plan vs implement vs review)

## Non-Goals
- Replacing the existing switchboard routing
- External LLM API subscriptions
- Unrestricted token spend

## Workstreams

### 33.1 — Skill I/O Standardization (HIGHEST PRIORITY)
**What**: Enforce a standard schema on all `.claude/commands/*.md` skills.
**Schema**:
```
## Skill: <name>
## Role: orchestrator | architect | implementer | reviewer
## Inputs: <what the caller must provide>
## Outputs: <what this skill produces>
## Example: <one-line invocation>
## Body: ...
```
**Acceptance**: All existing skills updated; new skill template enforces schema.

### 33.2 — delegate-fanout Script
**What**: New script `scripts/ai/delegate-fanout` — sends same task to N agents in
parallel, waits for all, selects best result by heuristic (length + no-error + fastest).
**Usage**: `delegate-fanout --prompt "task" --agents gemini,local --wait`
**Output**: Winner task ID + all outputs in registry
**Acceptance**: Script exists, runs parallel delegation, produces `winner` field in registry.

### 33.3 — Token Spend Tracking
**What**: Add `tokens_in` / `tokens_out` fields to delegation registry entries.
Gemini and local agents report token counts from response headers/metadata.
**Acceptance**: `delegate-to-gemini --list` shows token columns; weekly summary available.

### 33.4 — Tool Output Compression
**What**: In `local_agent_runtime.py` tool dispatch, trim verbose tool outputs to
a compact form before injecting back into context. Max 800 chars per tool result
unless the agent explicitly requested full output.
**Acceptance**: `_dispatch_tool` truncates outputs; test verifies 800-char limit.

### 33.5 — Role-Tagged Delegation
**What**: Add `--role plan|implement|review|research` flag to delegation scripts.
Role is logged in registry and prepended to system prompt as `[ROLE: implement]`.
**Acceptance**: Registry has `role` field; agents respect role in behavior.

## Slice Order
33.1 → 33.4 → 33.2 → 33.3 → 33.5

## Validation
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
- `python3 scripts/testing/test-local-agent-config.py`
- `delegate-fanout --prompt "say: ok" --agents gemini,local --wait` exits 0

## Rollback
Each slice is independently reversible. Skills schema is additive (backwards-compatible).
