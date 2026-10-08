## Local Agentic Memory, Cache & Token Efficiency SOP (Canonical — all agents)

SSOT: `.agent/skills/context-efficiency/SKILL.md` · Harness memory contract: `AGENTS.md` §Memory Discipline.
Every agent (Claude, Codex, Gemini, local Qwen) MUST leverage local memory, caching, and compaction as first-line context offloaders to maximize reasoning performance, ensure deterministic outcomes, and prevent token burn.

### 0. Operational priority (owner directive 2026-09-27)

Memory, cache, context, token accounting, and supporting system tools are core operational infrastructure. Prioritize correct structure, integration, actual agent use, runtime enablement, and observable evidence across all providers. Documented, implemented, configured, enabled, and verified are distinct states. Treat silent memory failures, ineffective compaction, ignored cache paths, and uncontrolled token use as delivery blockers for the affected workflow. Apply shared contracts with provider-specific adapters; never claim universal enforcement from instruction text alone.

### 1. The Tri-Phase Memory & Caching Closed-Loop
The memory and cache architecture operates as a continuous, closed-loop lifecycle across all 8 canonical workflow steps:

```
[FRONTEND PREP: Steps 1-2]         [MID-PHASE: Steps 3-6]            [BACKEND INGEST: Steps 7-8]
Fast/Lazy Cache & Vector Hits  ──►  AST Scoping & DB Cache Hits  ──►  Seed & Update Caches, DBs & Vectors
(ctx_*, hints, RESUME, AIDB)       (error-solutions, KV cache)        (MemoryBroker facts, RAG seeds)
       ▲                                                                            │
       └─────────────────────────── Reused by Next Task ────────────────────────────┘
```

- **Frontend Task Prep (Steps 1–2: ORIENT & RESEARCH)**:
  - **`lean-ctx` First**: Use frontend task prep tools like `lean-ctx` (`ctx_read`, `ctx_search`, `ctx_tree`, `ctx_shell`) throughout every phase where applicable.
  - **Lightweight, Fast, Lazy Retrieval**: Never drag full conversation history or entire files into context. Hydrate instantly from pre-warmed caches and vectors:
    - `aq-resume` (state anchor from `RESUME.json`, ~150–300 tokens)
    - `aq-session-start --task "<task>"` + `aq-hints` (ranked vector hints from AIDB)
    - `ctx_read(path, mode="signatures"|"outline")` (AST pruning; cached re-reads cost ~13 tokens)
    - Redis KV and embedding cache hits (sub-millisecond semantic retrieval)

- **Mid-Phase Execution (Steps 3–6: PRD/PLAN, EXECUTE, VALIDATE)**:
  - **Vector & Cache Traversal**: Before writing code or diagnosing errors, leverage targeted database and vector queries:
    - Query AIDB collection `error-solutions` before investigating bug patterns
    - Query `best-practices` and `skills-patterns` for harness idioms
    - Use `ctx_search` (bounded regex) and `ctx_read` with offset/limit instead of unbounded file scans
    - **Prompt Cache Alignment**: Keep system prompts, instructions, and grounding SSOT at the message head to maximize KV cache hits on local models and provider prompt cache hits (90%+ cost/token reduction)
    - **Output Capping**: Strictly cap tool outputs at 3,000 characters (~750 tokens) to prevent megabyte log dumps

- **Backend Task Closeout & Ingest (Steps 7–8: DOC-UPDATE, COMMIT & HANDOFF)**:
  - **Input and Update Caches, Databases, and Vectors**: Every completed task must feed its findings back into the system so subsequent tasks can reuse them in lightweight, fast, lazy mode:
    - **Seed RAG Vectors**: Seed AIDB collections (`error-solutions`, `best-practices`, `skills-patterns`) with newly discovered patterns and root-cause solutions
    - **Store Facts**: POST completed-task learnings to MemoryBroker (`POST :8003/api/memory/facts` or `mcp_server_store_memory`)
    - **Warm Memory**: Write architecture notes to `.agent/memory/<topic>.md`; collapse old pointers in `ai-stack/agent-memory/MEMORY.md`
    - **Checkpoint & Compact**: Update `.agent/collaboration/RESUME.json` and append to `PULSE.log`. Use `aq-session-compact` for read-only size diagnostics. Compact through the provider's supported mechanism or start a fresh session from a deliberate handoff; never archive/delete provider-owned transcripts to simulate context compaction.

### 2. High-Signal Anti-Thrashing Compaction (Selective Eviction vs. Anchor Retention)
Compaction and trimming must be **aggressive but discerning** — never strip context so deeply that the agent wastes tokens re-discovering active working context:

- **What to Evict Aggressively (No Longer Used or Cheaply Retrievable)**:
  - Stale intermediate tool executions: raw grep dumps already acted upon, verbose file listings, resolved lint/build outputs
  - Historical conversation turns from completed sub-tasks or merged slices
  - Full file bodies already saved to disk (re-read cheaply on demand via `ctx_read` at ~13 tokens)
  - Static background documentation easily retrieved from AIDB vectors or `aq-hints`
- **What to Retain as Working Anchors (Active Execution State)**:
  - The active slice objective, immediate task constraints, and acceptance criteria
  - The exact list of uncommitted modified files and active symbol names under edit
  - Unresolved error traces or test failure outputs currently being diagnosed
  - Explicit pointers/paths to relevant topic memory files so retrieval is single-step rather than exploratory
- **Anti-Thrashing Principle**: If an item is actively needed for the next 1–2 turns, keep it in working context. If an item is historical, resolved, or indexable, evict it to MemoryBroker or topic files immediately.

### 3. Zero Runaway Context & Compaction Mandate
- **Measured guard, every model**: Before continued autonomous execution, use the latest total input-token measurement (including cached input), not transcript bytes or uncached tokens alone. Budget is at most 50,000 tokens and 80% of the model's actual context window, whichever is smaller. If over budget, checkpoint and use supported native compaction or a fresh-session handoff before further work. If measurements are unavailable, label them unknown and obtain evidence; do not claim a clean guard.
- **Verify the reduction**: `aq-session-compact --verify-usage <record.json>` accepts provider-neutral telemetry: `session_id`, `input_tokens`, `context_window_tokens`, `before_input_tokens`, `compaction_observed`, `before_request_sequence`, `request_sequence`. Inputs must refer to the same session with the after request later than the before request. Only a measured decrease within budget returns `verified_reduction` / exit 0; all other outcomes exit 2. Codex rollouts can use `--verify-rollout <path>` directly. This verifier observes evidence; it does not itself trigger provider compaction.
- **Provider adapters**: Codex native startup configuration uses `model_auto_compact_token_limit = 50000` and scope `total`. Claude, Gemini/Antigravity, local models, and future providers follow the same measured guard contract using their supported context management. Do not pretend a provider adapter is installed or operational merely because this instruction is projected. Verify each adapter separately.
- **Avoid amplification**: No full-history delegation; pass a bounded task and file pointers. Wait inside tools between meaningful events instead of repeated model-driven status polls. Saving memory or compressing tool output does not remove the existing conversation history.
- **Hard Session Thresholds**: If active conversation history exceeds **2.5 MB** on disk, **25 turns**, or **50k tokens**, agents MUST compact before executing further turns.
- **Never Resume Bloat**: Diagnose oversized sessions with `aq-session-compact` (or `aq-workspace compact`), then use supported compaction or a fresh-session handoff. Historical scans must never replace the active objective, and transcript size alone does not establish live token usage or a successful context reset.
- **Clean Hydration**: All sessions hydrate leanly via `aq-resume` + `aq-session-start --task "<task>"` (~1,500 tokens), preserving full task continuity without token bloat.

### 4. Bounded Sub-Agents & Standby Pane Execution
- **Sub-Agent Context Slicing & Lean Tooling**: When delegating to sub-agents, pass ONLY the slice objective (1-2 sentences), target file paths (by address, not content), acceptance criteria, constraints, and reference skill names. NEVER forward conversation history or prior agent transcripts. Sub-agents run with slim, token-efficient tool surfaces (`lean-ctx`, `agrep`, `acat`, edit tools) and reach unlisted packages on-demand via `aq-tool <pkg>` without expanding baseline payloads.
- **Standby Mode by Default**: Workspace panes and daemon processes must launch in standby (`prompt`) mode (`read -n 1`). Never run unthrottled auto-execution loops in background terminals.
- **Session-Scoped Shutdown**: Workspace reset/exit may terminate only the requested workspace. Never invoke global process reaping as an implicit side effect; separate cleanup requires evidence of ownership and must preserve other active workspaces.
- **Claude Code Plugin Load Strategy**: Claude Code plugins load statically at session start. Enable language/tool plugins per project by stack (via `.claude/settings.json`), never globally by default. Use `aq-payload-audit` to flag unused enabled plugins and reduce session overhead.
