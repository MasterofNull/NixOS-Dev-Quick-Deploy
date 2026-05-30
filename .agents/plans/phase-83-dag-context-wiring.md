# Phase 83 Slice Plan — DAG Context Wiring + Rust Pre-flight

**Phase:** 83
**Status:** EXECUTING
**Orchestrator:** Claude Sonnet 4.6
**PRD:** `.agent/PROJECT-PHASE83-PRD.md`

---

## Slice 83.1 — Wire DAGSessionManager into workflow session handlers

**Objective:** Every coordinator workflow run creates a parallel DAG session record.

**Files to touch:**
- `ai-stack/mcp-servers/hybrid-coordinator/workflow/workflow_session_handlers.py`

**Change:**
- Import `DAGSessionManager` from `ai-stack/agent-memory/dag_manager.py`
- On session create (`_handle_workflow_run_start` or equivalent), call `dag_manager.create_entry(session_id, "message", role="system", content=...)`
- All I/O must be wrapped in `asyncio.to_thread` (async safety rule)
- DAG sessions stored in `.agents/dag-sessions/` (create dir, add to .gitignore)

**Validation:** Create a workflow run via `curl POST /v1/run`, confirm JSONL file created in `.agents/dag-sessions/`

---

## Slice 83.2 — Wire context-merger into aq-session-start

**Objective:** Session hydration automatically includes hierarchical AGENTS.md context.

**Files to touch:**
- `scripts/ai/aq-session-start`

**Change:**
- After task context hydration, call `python3 scripts/ai/lib/context-merger.py` with CWD
- Append merged context to the session output
- Fail gracefully: if no AGENTS.md found, skip with info message

**Validation:** `scripts/ai/aq-session-start --task "test"` shows "Context from: AGENTS.md" in output

---

## Slice 83.3 — Complete Rust pre-flight

**Objective:** Rust refactoring lane is unblocked and AIDB has the engineering instructions.

**Files created:**
- `ai-stack/rust-core/Cargo.toml` (via `cargo init`)
- `ai-stack/rust-core/src/main.rs`
- `.gitignore` addition: `ai-stack/rust-core/target/`

**Change:**
- Seed RUST-ENGINEERING-INSTRUCTIONS.md content into AIDB `skills-patterns` collection
- `cargo init --name nixos-ai-core ai-stack/rust-core/`

**Validation:** `ls ai-stack/rust-core/`, curl Qdrant skills-patterns for "rust"

---

## Slice 83.4 — aq-qa Phase 1 coverage check

**Objective:** Phase 1 regression is caught by the health gate.

**Files to touch:**
- `scripts/testing/harness_qa/phases/phase0.py`

**Change:**
- Add one `CheckResult` that verifies `dag_manager.py` exists + imports cleanly
- Add one `CheckResult` that verifies `context-merger.py` exists + imports cleanly
- Wire into existing `phase0` check list

**Validation:** `aq-qa 0` shows new checks PASS

---

## Execution Order

1. 83.1 → 83.2 → 83.3 → 83.4
2. After all 4 slices: run `python3 tests/integration/test-phase1-dag-context.py` (must be 4/4)
3. Run `scripts/governance/tier0-validation-gate.sh --pre-commit`
4. Commit with single atomic message referencing PRD
