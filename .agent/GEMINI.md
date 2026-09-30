# GEMINI.md

Guidance for Gemini / Antigravity agents in NixOS-Dev-Quick-Deploy.
**Canonical workflow reference -> `.agent/WORKFLOW-CANON.md`** · **Full policy -> `AGENTS.md`**

## Operating Context & Port SSOT
- **Stack**: NixOS flake, FastAPI, llama.cpp, Redis, Postgres, Qdrant. Hardware: max 12 GPU layers, 27GB RAM.
- **Port SSOT**: llama:8080 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dash:8889 (`nix/modules/core/options.nix`).
- **Rule Budget**: Rule files in this repository MUST stay strictly under **24,000 bytes** to prevent IDE truncation.

## Progressive disclosure and fetch-on-demand
- Keep the always-on prompt to role/authority, objective, owned paths, acceptance criteria, and stop/validation constraints.
- Fetch active state, task hints, and at most 2–3 matching skills first; use outlines/signatures before bounded reads of exact symbols.
- Load domain instructions, memory topics, and full policy sections only when a trigger or pointer requires them.
- Delegation carries pointers and slice criteria, never parent history, full transcripts, whole files, or full skill bodies.

## Auth & Multi-Agent Collaboration
- Remote agents use IDE OAuth/session storage. Never store or extract API keys for Antigravity.
- Multi-agent rounds: watch `.agent/collaboration/antigravity-inbox/<round>.md`, output to `.agents/plans/<round>/antigravity.md`.
- Reviewer verdicts: exactly one line (`APPROVED`, `CONCERNS`, or `REJECTED`) + concise (<=200 words) explanation.

## Role, Modes & Tool Surface
- Repo root boundary: `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy`. Scratch dir: `<appDataDir>/brain/<conv>/scratch/`.
- Modes: `auto_edit` (read_file, grep_search, list_directory, replace, write_file; no shell) vs `yolo`/IDE (full shell & editor).
- Tool Mapping: Search before reading (`agrep`/`ctx_search`). Prune reads (`ctx_read` outline/signatures). Deduplicate calls (Rule 14).
- Declarative Only (Rule 15): Never propose imperative installs (`pip/npm/cargo install`). Declare in Nix.

## Key Behavioral Rules Summary (SSOT: AGENTS.md)
1. **Conversational Guard**: One slice, one concern. No unsolicited refactors.
2. **PRD GATE**: No coding without a written plan. Lock scope. Sub-agents execute only assigned slices; do not re-scope.
9a. **Atomic Pulse**: Append to `.agent/collaboration/PULSE.log` after every write/commit.
9b. **Atomic Resume**: Update `.agent/collaboration/RESUME.json` on task start and todo completion.
11a. **Issue Logging**: Log bugs/frictions to `.agent/memory/issues-backlog.md`.
12. **No Delete**: Move to `.agent/archive/`. Never `rm`/`rmdir`.
13. **Scope Lock**: Verify slice scope before edit. No infrastructure edits without assignment.
14. **Deduplication**: Never repeat identical tool calls.
17. **Activation Gate**: Integrated, ON, live-tested, observable, intervenable, PM-tracked.
19. **Cheapest Implementer**: Orchestrator routes bounded slices to cheapest eligible lane.
21. **Root Cause Discipline**: No silent workarounds. Register in `WORKAROUND-REGISTER.md`.
22. **Minimal Code**: Smallest correct change; progress projected by `aq-pm-tracker`.
24. **Context Efficiency**: Zero runaway context. Compact at >2.5MB/>25 turns.

<!-- canon:begin fable-parity -->
## Fable-Parity Behavior (Canonical — all agents)

SSOT: `.agent/FABLE-PARITY-CONTRACT.md`. Every agent and inference lane in this harness mirrors Claude Fable 5 operating behavior. Capability differs by model; the behavior contract does not.

1. **Lead with the outcome** — first sentence answers "what happened / what did you find"; detail after.
2. **Final message is complete** — answers/findings/conclusions live in the last message; anything shown only mid-turn gets restated there.
3. **Selective, then clear** — shorten by dropping what doesn't change the reader's next action, never by compressing into undecodable shorthand.
4. **Act when informed** — no re-deriving established facts, no re-litigating settled decisions, no permission-asking for reversible in-scope work. Weighing options → one recommendation, not a survey.
5. **Finish the turn** — never end on a plan, a promise ("I'll…"), or a self-answerable question; do it or name the exact blocker. Retry within Rule 6 budget.
6. **Evidence before state change** — before restart/delete/config write, verify the evidence supports THAT specific action; pattern-match ≠ diagnosis. Look at a target before overwriting it.
7. **Report faithfully** — failures stated with output; skipped steps stated; verified work stated plainly without hedging. Never fake a result (anti-gaming).
8. **Comments state constraints code can't show** — never narrate the next line or justify the change; match surrounding idiom, naming, and comment density.
9. **Confirm only irreversible or outward-facing actions** — everything else proceeds (or batches to end-of-cycle per operator preference).
10. **Match response shape to the question** — direct prose for simple questions; headers/tables only when they earn their place.

Enforcement: local payloads auto-inject the MICRO variant (`shared/llm_config.py`); switchboard chat profiles inject the CARD variant (`${FABLE_PARITY_BODY}`); remote Claude lanes resolve to `claude-fable-5` via `config/model-coordinator.json`. Kill switch: `FABLE_PARITY=0`. HARD harness rules win on any conflict.
<!-- canon:end fable-parity -->

<!-- canon:begin memory-cache-sop -->
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
- **Sub-Agent Context Slicing**: When delegating to sub-agents, pass ONLY the slice objective (1-2 sentences), target file paths (by address, not content), acceptance criteria, constraints, and reference skill names. NEVER forward conversation history or prior agent transcripts.
- **Standby Mode by Default**: Workspace panes and daemon processes must launch in standby (`prompt`) mode (`read -n 1`). Never run unthrottled auto-execution loops in background terminals.
- **Session-Scoped Shutdown**: Workspace reset/exit may terminate only the requested workspace. Never invoke global process reaping as an implicit side effect; separate cleanup requires evidence of ownership and must preserve other active workspaces.
<!-- canon:end memory-cache-sop -->

<!-- canon:begin recursive-self-improvement-sop -->
## Recursive Self-Improvement (RSI) Closed-Loop SOP (Canonical — all agents)

SSOT: `.agent/WORKFLOW-CANON.md` · Philosophy: `AGENTS.md` §Project Philosophy · Rule SSOT: Rule 11a & Rule 21.
NixOS-Dev-Quick-Deploy is an immutable, declarative **Pessimistic Recursive Self-Improvement (PRSI)** environment. Every agent (Claude, Codex, Gemini/Antigravity, local Qwen) and every task slice MUST execute within the recursive self-improvement closed-loop: findings, friction, errors, and mitigations are never discarded or bypassed with silent workarounds; they MUST be dogfooded back into the system to drive continuous, compounding platform evolution.

### 1. The 5-Stage Recursive Self-Improvement Closed-Loop
The recursive self-improvement loop operates across every phase of task execution:

```
[1. DETECT & MEASURE]           [2. DIAGNOSE & REGISTER]         [3. SEED & DOGFOOD]
Runtime friction, race       ──► Root cause analysis (R-21)   ──► Store facts in MemoryBroker (:8003)
conditions, tool contention,     Register in issues-backlog       Seed RAG vectors (error-solutions)
or metric anomalies              and WORKAROUND-REGISTER          Update topic memory & MEMORY.md
                                                                           │
                                                                           ▼
[5. RECURSIVE REUSE]            [4. SYNTHESIZE GUARDS]                     │
Next task hydrates via       ◄── Harden CLI tools & scripts   ◄────────────┘
aq-session-start + aq-hints      Add deterministic checks (tier0.d)
Lean-ctx & pre-warmed caches     Zero recurring failures
```

- **Stage 1: Detect & Measure (Execution / Mid-Phase)**:
  - Continuously monitor execution for runtime friction, concurrency races, latency spikes, or tool contention.
  - "You cannot manage what you cannot measure": if an issue occurs without observable telemetry or clear diagnostics, instrument it immediately.
  - **Gate Contention**: When multiple agents run heavyweight validation simultaneously, serialize access using `aq-gate-checkout` to prevent tool contention, memory exhaustion, and hanging processes.

- **Stage 2: Root-Cause Diagnosis & Registration**:
  - **No Silent Workarounds (Rule 21)**: Trace every failure or friction point to its system producer. Never leave an ad-hoc band-aid in place.
  - **Mandatory Issue Logging (Rule 11a)**: Any discovered error, friction, misconfiguration, or system limitation (fixed immediately or deferred) MUST be recorded in `.agent/memory/issues-backlog.md`:
    ```markdown
    [STATUS] SCOPE — Description — Root cause / fix notes
      Severity: low|medium|high|critical
      Action: specific next step
      File: path/to/file ~line N
    ```
  - **Workaround Registration (Rule 21)**: If an interim mitigation is necessary, register it in `.agent/WORKAROUND-REGISTER.md` with `{symptom, root cause, producer, fix-path, class, severity}`.

- **Stage 3: Knowledge Seeding & Dogfooding (Doc-Update / Backend Ingest)**:
  - **Store Factual Learnings**: POST architectural and operational facts to MemoryBroker (`POST :8003/api/memory/facts` or `mcp_server_store_memory`).
  - **Seed RAG Vectors**: Seed AIDB collections via `scripts/data/seed-rag-knowledge.py`:
    - `error-solutions`: newly identified bugs, root causes, and verified fixes.
    - `best-practices`: operational patterns, harness conventions, and tool contracts.
    - `skills-patterns`: reusable workflows and multi-agent coordination patterns.
  - **Topic Memory Curation**: Write detailed findings to `.agent/memory/<topic>.md` and update index entries in `ai-stack/agent-memory/MEMORY.md` within the line budget.

- **Stage 4: Automated Guard & Gate Synthesis**:
  - Never stop at fixing a bug in code: synthesize an automated, deterministic guard to prevent recurrence.
  - Add regression tests to `scripts/testing/` or deterministic pre-commit checks to `scripts/governance/tier0.d/`.
  - Update tool wrappers (e.g. `aq-gate-checkout`, `aq-session-compact`, `aq-reap-orphans`) to enforce guards mechanically rather than relying on agent discipline.

- **Stage 5: Continuous Reuse in Frontend Prep**:
  - Every completed cycle enriches the shared AIDB knowledge base, MemoryBroker, and cached indexes.
  - Future agent sessions hydrate these learnings automatically in Step 1 (ORIENT) via `aq-session-start`, `aq-hints`, and `aq-resume`.
  - The harness achieves compounding capability: each task makes subsequent tasks faster, leaner, and less error-prone.

### 2. Mandatory Task Closeout Checklist
Before marking any slice, phase, or PRD complete, verify that the recursive self-improvement loop is closed:
- [ ] Any friction, concurrency hang, or error observed during the task is diagnosed to root cause.
- [ ] Documented in `.agent/memory/issues-backlog.md` (and `.agent/WORKAROUND-REGISTER.md` if an interim workaround was used).
- [ ] Newly discovered patterns or fixes are seeded to MemoryBroker (:8003) and AIDB RAG (`error-solutions`).
- [ ] A deterministic guard, check, or test was added or updated to prevent recurrence.
- [ ] Findings and evidence are recorded in `.agent/collaboration/HANDOFF.md` and `.agent/collaboration/PULSE.log`.
<!-- canon:end recursive-self-improvement-sop -->

## 8-Step Canonical Workflow (SSOT: .agent/WORKFLOW-CANON.md)
1. **ORIENT**: `aq-session-start --task "<task>"` · `aq-hints` · recall working memory.
2. **RESEARCH**: Search before read (`agrep`, `als`, `acat`, `asum`, `ctx_search`). Bounded context.
3. **PRD/PLAN**: Plan before coding (`.agent/PROJECT-<NAME>-PRD.md` or `.agents/plans/phase-<N>.md`). Lock scope.
4. **MEMORY-CHECKPOINT**: Intent lock (`PENDING.json`) & `RESUME.json`.
5. **EXECUTE**: One slice at a time. Read before edit. Log pulse to `PULSE.log`.
6. **VALIDATE**: Live test. Acquire `aq-gate-checkout acquire --gate tier0`. Run `tier0-validation-gate.sh --pre-commit`.
7. **DOC-UPDATE**: Log to `issues-backlog.md` & `WORKAROUND-REGISTER.md`. Seed RAG (`seed-rag-knowledge.py`). Update `HANDOFF.md`.
8. **COMMIT**: Step 8 evidence contract (root cause, files changed, results, trailers). Release gate checkout.

<!-- canon:begin mvp-delivery-sop -->
## Design, Build, and MVP Audit (owner directive 2026-09-27)

This procedure governs delivery cadence for every agent and supersedes older
requirements for repeated full expert rounds during ordinary implementation.
The eight workflow steps remain; the depth of ceremony depends on the phase.

### Design and freeze

Use full, independent domain-expert teams across available model lanes for the
PRD and plan. Cover architecture, implementation, UX, operations, measurement,
failure modes, and security implications. Give teams the same evidence and
criteria; consolidate disagreements into one decision record. Freeze the MVP
scope, dependency contracts, owners, acceptance tests, rollout/rollback limits,
and deferred questions as PLAN_READY or PLAN_READY_WITH_FOLLOWUPS. Existing
approved plans are reused, not redrafted solely to satisfy this procedure.
Record unavailable lanes honestly; never manufacture their consensus.

### Build the working MVP

Once the plan is frozen, prioritize implementation and end-to-end operation.
Use bounded slices, the cheapest eligible implementers, and focused regression,
integration, and live checks. Fix ordinary defects directly within the frozen
scope. Do not require a fresh full expert round, debate, or all-model consensus
for each implementation slice, fix, or commit. Collect non-blocking critique for
the MVP audit instead of repeatedly reopening accepted design decisions.

Keep atomic commits, evidence, service/dashboard coverage, and required automated
gates. Preserve existing protections and explicit activation boundaries. A
specific high-risk change may require targeted independent review; that is not
a reason to restart the entire ceremony. Reopen only the affected decision for
material scope/contract changes or critical correctness, data-loss, authority,
or security defects. MVP implementation is not automatically release acceptance.

Declare a working MVP only after the frozen end-to-end user journeys succeed
with real dependencies, visible progress and terminal outcomes, and reproducible
evidence. Source presence, green syntax checks, staged files, and simulated
success do not prove operational readiness. Record limitations explicitly.

### Full MVP audit and acceptance

At the working MVP boundary, restore full expert scrutiny: independent code and
runtime review, adversarial and failure testing, operator UX, performance,
observability, and cross-model consensus. Review one exact integrated subject
against the frozen criteria. Consolidate findings into one prioritized list;
repair blockers and validate affected paths without restarting unrelated debate.
Record real participant verdicts and outstanding concerns. Only that evidence
can support release acceptance; deferred security/containment activation still
requires its own readiness evidence and owner decision.

Track delivery phase, demonstrable journeys, defects, and implementation versus
live readiness separately. Measure time to working MVP and review overhead;
never inflate progress to make the fast-build phase appear complete.
<!-- canon:end mvp-delivery-sop -->
