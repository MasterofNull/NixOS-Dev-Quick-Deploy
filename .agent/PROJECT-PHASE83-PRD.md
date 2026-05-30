# Phase 83 PRD — Agentic Mind Activation: DAG + Context Wiring + Rust Pre-flight

**Status:** ACTIVE
**Authored:** 2026-05-29
**Orchestrator:** Claude Sonnet 4.6
**Team:** Gemini (Architect), Qwen3-35B (Implementer), Claude (Reviewer/Committer)
**Parent plan:** `.agents/plans/PROJECT-PAEA-UPDATE-PLAN-V3-1.md` Phase 1

---

## Problem

Phase 1 PAEA infrastructure exists and tests pass (4/4) but nothing in production uses it:

- `ai-stack/agent-memory/dag_manager.py` — tree-based session DAG, Pydantic `AgentHandoff` schema — **not wired into coordinator**
- `scripts/ai/lib/context-merger.py` — hierarchical AGENTS.md loader — **not called by any CLI or agent**
- `ai-stack/local-agents/tests/integration/test-phase1-dag-context.py` — 4/4 PASS — **never run in CI**
- Rust refactoring pre-flight: instructions + skill created, **AIDB not seeded, workspace not initialized**

The "agentic mind" has working components but zero synaptic connections. No workflow session is tracked in the DAG, no hierarchical context is loaded at session start, and the Rust lane is blocked pending AIDB + workspace bootstrap.

---

## Goal

Wire Phase 1 PAEA components into the live stack so the agentic mesh has:
1. **Persistent DAG session memory** for every coordinator workflow run (branching, handoff, compaction)
2. **Hierarchical context loading** at session start (recursive AGENTS.md merge)
3. **Rust workspace bootstrapped** with AIDB knowledge seeded
4. **aq-qa coverage** so a Phase 1 regression can't silently re-enter

---

## Scope

**IN scope:**
- `workflow/workflow_session_handlers.py` — add DAG session recording on create/update
- `scripts/ai/aq-session-start` — add context-merger invocation at hydration step
- Rust pre-flight completion (AIDB seed + cargo init in `ai-stack/rust-core/`)
- One new aq-qa check for Phase 1 (dag_manager import + context_merger import)

**OUT of scope:**
- Phase 2 Drop Zone daemon (next phase)
- L1/L2 routing (Phase 3)
- Agent Fleet dashboard panel (Phase 4)
- Production eval score regression (separate investigation)

---

## Acceptance Criteria

| # | Criterion | Test |
|---|-----------|------|
| AC1 | Every workflow session creation calls `dag_manager.create_entry()` | Live test: create a run, inspect DAG JSONL |
| AC2 | `aq-session-start` merges hierarchical context from current working dir | `scripts/ai/aq-session-start --task test` outputs context from AGENTS.md |
| AC3 | Rust workspace exists at `ai-stack/rust-core/Cargo.toml` | `ls ai-stack/rust-core/` |
| AC4 | AIDB `skills-patterns` collection has Rust entries | `aq-qa 0` or curl Qdrant |
| AC5 | Phase 1 test still passes after all wiring changes | `python3 tests/integration/test-phase1-dag-context.py` = 4/4 |
| AC6 | One new aq-qa check passes for Phase 1 infrastructure | `aq-qa 0` green |

---

## Risks

| Risk | Mitigation |
|------|-----------|
| DAG writes add I/O to every coordinator session create (async path) | Use `asyncio.to_thread` — never sync I/O in aiohttp handlers |
| context-merger breaks `aq-session-start` if AGENTS.md not found | Graceful fallback: return empty string if no files found (already coded) |
| cargo init adds files outside .gitignore scope | Add `ai-stack/rust-core/target/` to .gitignore |
| DAG JSONL file grows unbounded | Storage in `.agents/dag-sessions/` (gitignored), pruned by retention policy |

---

## Rollback

- Coordinator: revert `workflow/workflow_session_handlers.py` to pre-wiring (one-line import removal + guard)
- aq-session-start: revert context-merger call (one-block removal)
- Rust: `rm -rf ai-stack/rust-core` (no service dependency)
- aq-qa: revert the phase check

---

## Slice Plan

See: `.agents/plans/phase-83-dag-context-wiring.md`
