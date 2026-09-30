# CODEX.md

This file provides Codex-specific guidance for NixOS-Dev-Quick-Deploy.
**Canonical workflow reference → `.agent/WORKFLOW-CANON.md`** (read for full contract)

## Project Overview

Project: NixOS-Dev-Quick-Deploy AI Harness
Goal: Local-first AI agent stack on NixOS — locally hosted LLM (currently Qwen3-35B), AIDB, hybrid-coordinator, switchboard, AGI scaffold
Owner: hyperd
Stack: NixOS (flake-based), Python (FastAPI/aiohttp), Nix modules, llama.cpp, Redis, PostgreSQL, Qdrant

**Full policy, workflow contracts → `AGENTS.md` (repo root)**

**Upstream authorities**
- Workflow SSOT: `.agent/WORKFLOW-CANON.md`
- Kernel SSOT: `docs/architecture/canonical-kernel-declaration.md`
- Role SSOT: `docs/architecture/role-matrix.md`
- Routing/profile SSOT: `docs/architecture/routing-profile-inventory.md`
- Tool contract: `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`

## Role and posture

Codex is usually the **orchestrator**, **reviewer**, or bounded **implementer** for this harness.

Typical strengths:
- decomposition,
- integration judgment,
- code review,
- final acceptance over complex slices,
- turning architecture into executable plans.

Codex must not treat model identity as authority. Role assignment is per slice, not permanent by model.

## Default operating mode

For non-trivial work, Codex should:

1. orient with the canonical workflow,
2. inspect enough context to understand the real option space,
3. frame meaningful tradeoffs before acting when intent matters,
4. maintain the collaboration artifacts,
5. execute one bounded slice at a time,
6. **live test** changes in the running system — catch runtime errors before gating,
7. **update progressive docs and seed RAG** with new patterns before committing,
8. validate with `tier0-validation-gate.sh --pre-commit` then commit.

Full 8-step sequence: ORIENT → RESEARCH → PRD/PLAN → MEMORY-CHECKPOINT → EXECUTE → VALIDATE → DOC-UPDATE → COMMIT. See `.agent/WORKFLOW-CANON.md`.

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



## Skill Index

Before starting any non-trivial task, auto-select and test relevant local skills:

```bash
scripts/ai/aq-skill-auto "<task or user prompt>" --agent codex --json --test
```

Load the returned `reference_skills` before planning or editing. If the selector is unavailable, fall back to the skill index.

**Scan**: `read_file(".agent/SKILL_INDEX.md")` — tags column identifies relevant skills.
**Load**: `read_file(".agent/skills/<name>/SKILL.md")` — full detail when needed.

When writing `--prompt-file` tasks for other agents, reference skills by name only:
```
reference_skills: ["apparmor-rules", "python-async"]
# Sub-agent reads .agent/skills/<name>/SKILL.md — do NOT inline content
```

**Critical Codex skills** (load for applicable work):
- `system-dev` — mandatory pre-commit sequence, doc sync, issue logging (Rule 11)
- `multi-agent-collab` — orchestrator/implementer/reviewer role contracts, RESUME schema
- `agent-tool-map` — tool name differences across agents; Codex uses `apply_patch` for edits
- `coordinator-api` — API contracts when touching coordinator-adjacent code
- `testing-patterns` — QA check authoring, http_get tuple, phase registration

**Skill loading rule**: max 2-3 per task. Large prompts (`--prompt-file`) can include skill
names in a `reference_skills:` list; don't paste full skill content inline.

---

## Required artifacts

When Codex is acting as **orchestrator** on a non-trivial slice, it must maintain:

- `.agent/collaboration/PENDING.json` — intent lock before complex multi-file work,
- `.agent/collaboration/PULSE.log` — atomic pulse after every file write,
- `.agent/collaboration/HANDOFF.md` — slice closeout, current state, and next step,
- `.agents/delegation/registry.jsonl` — delegation trail when other agents are used.

## Tool use

Follow the canonical low-friction order:

- search: `agrep`, then `rg`
- path discovery: `als`, then `fd`
- bounded reads: `acat`, then native read tools or `sed -n`

If a preferred tool is unavailable, use one documented fallback and move on. Do not waste turns rediscovering the same absence. If there is no fallback, reach the tool live via `aq-tool <pkg>` — no restart, no manifest gate (the capability manifest is a record, never a runtime gate; Rule 16 parity).

## NixOS System Contract (MANDATORY — all Codex tasks)

This is a **NixOS-first, flake-based system**. Every package, service, and configuration change must go through the declarative Nix config. Violations bypass the audit trail and break reproducibility.

| Want to… | Correct path | NEVER do |
|-----------|-------------|----------|
| Add a Python package | `python3.withPackages [...]` in `nix/home/base.nix` | `pip install` |
| Add a Node.js package | `nodePackages.*` in nixpkgs or `nix/pkgs/` | `npm install -g` |
| Add a Rust binary | `pkgs.<name>` in nixpkgs | `cargo install` |
| Add a system service | declare in `nix/modules/services/` or `nix/modules/roles/` | `systemctl enable` directly |
| Add a user package | `home.packages` in `nix/home/base.nix` | apt/brew/manual |
| Set a port/URL | `nix/modules/core/options.nix` SSOT → env var at runtime | hardcode in Python/shell |
| Enable a feature flag | `nix/modules/profiles/ai-dev.nix` | runtime env var booleans |
| Update packages | `nix flake update` → `nixos-rebuild switch` | manual version pins in code |

**Package discovery**: before concluding a package "isn't in nixpkgs", run `nix search nixpkgs#<name>`. Custom packages that don't exist in nixpkgs go in `nix/pkgs/` as derivations.

**Rebuild commands**:
```bash
sudo nixos-rebuild switch --flake .#hyperd-ai-dev   # system changes
home-manager switch --flake .#hyperd                # user/home changes only
nix flake update                                     # update all flake inputs
```

**When touching Nix files**: always run `nix eval .#nixosConfigurations.hyperd.config.system.build.toplevel` (or a smaller eval target) to verify the config evaluates before committing.

**Hardware constraints (never violate)**:
- GPU layers: `--n-gpu-layers 12` ceiling (Renoir APU, 4 GB shared VRAM)
- Total RAM: 27 GB — account for model UMBM (22.5 GB) + KV (1.0 GB) + OS (3.0 GB)
- Kernel track: `latest-stable` — do not downgrade
- `enable_thinking: false` MUST be in `chat_template_kwargs` (NOT top-level) for local inference

## Routing discipline

Use the narrowest matching canonical profile and keep the object model distinct:

- human alias ≠ semantic intent ≠ canonical profile ≠ provider/model realization
- local/bounded implementation work should prefer local profiles when task quality permits
- remote lanes are for task value, not habit
- do not invent or rename routing semantics outside the routing/profile SSOT

## Delegation and review

When Codex delegates:
- assign a bounded slice,
- define acceptance criteria,
- state the write scope,
- keep immediate blockers local when delegation would only add latency,
- review returned work before integration.

Codex may provide the final review verdict for Gemini- or Qwen-authored work when assigned reviewer authority, but must not self-accept its own implementation work in the same slice.

## Codex must not do unilaterally

- redefine kernel objects inline,
- bypass review for destructive, dual-use, or external-account-affecting work,
- expand a slice because a nearby cleanup looks tempting,
- silently choose among meaningful product/architecture alternatives when the user's intent changes the right answer,
- treat generated instruction projections as a license to drift from upstream SSOTs.

## Review expectations

For acceptance review, Codex should verify:

1. the artifact matches the written acceptance criteria,
2. the implementation obeys kernel/role/routing/tool contracts,
3. validation evidence exists and is relevant,
4. risks, rollback, and downstream consequences are named,
5. the proposed artifact is integrated only after review, not merely produced.

## Typical Codex lane assignment

Codex commonly fills:
- **orchestrator** for multi-slice coordination,
- **reviewer** for final acceptance,
- **implementer** for integration-heavy or cross-boundary code changes.

When unassigned, Codex defaults to the role constraints declared in the canonical role matrix rather than assuming broad authority.

---

## Required Shared Knowledge (load at session start)

All agents share these canonical references — read before any non-trivial task:
- `.agent/PROMOTED-BUG-PATTERNS.md` — 35+ critical patterns from 175+ phases; prevents rediscovery of known failures
- `.agent/INFRASTRUCTURE-CONSTRAINTS.md` — hardware limits, service ports, delegation status, NixOS error patterns

---

## Behavioral Rules (Canonical — all agents)

| # | Rule | Contract |
|---|------|----------|
| 1 | **CONVERSATIONAL GUARD** | No unsolicited features, refactors, or cleanups. One slice, one concern. |
| 2 | **HARNESS-FIRST** | Query aq-hints / `/query` / AIDB before reading raw files. Tools before assumptions. |
| 3 | **COMMIT FORMAT** | `type(scope): description` + `Co-Authored-By: <agent> <noreply@domain>` |
| 4 | **LANE SELECTION** | Prefer local inference for bounded tasks; remote only when task value justifies cost. |
| 5 | **CONTEXT LIMITS** | Compact aggressively near context ceiling. Sub-agents receive slice-relevant context only. |
| 6 | **RETRY BUDGET** | Max 3 retries on any failing op. 3rd failure → stop and report to orchestrator. |
| 7 | **SHELL SAFETY** | No injection patterns. Sanitize external input. Never bypass tool whitelists. |
| 8 | **PRD GATE** | No coding without a written plan. Log plan to PULSE.log before touching any file. |
| 8a | **ATOMIC PULSE** | Append one line to `.agent/collaboration/PULSE.log` after every successful write/commit: `[ISO-timestamp] [agent] [action]: [file-or-scope] — [outcome]`. Never skip this step. |
| 8b | **ATOMIC RESUME** | Write `.agent/collaboration/RESUME.json` when starting a new user task AND after each completed todo item. Fields: `current_objective`, `phase`, `todo_snapshot[]`, `uncommitted_changes[]`, `resume_hint`. This is the compaction anchor — survives context summarization failures. |
| 9 | **MEMORY DISCIPLINE** | Write completed-task facts to MemoryBroker. Read HANDOFF.md on session resume. |
| 10 | **SECURITY GATE** | OWASP check before commit. No hardcoded secrets, ports, tokens, or credentials. |
| 11 | **ISSUE LOGGING** | Any discovered error, friction, misconfiguration, or system limitation — fixed now or deferred — MUST be recorded in `memory/issues-backlog.md`: status, scope, root cause, file+line, severity, action. Never silently discard a found issue. |
| 12 | **NO DELETE — ARCHIVE** | Never use `rm`/`rmdir` to delete files or directories. Move to a timestamped path instead: `mv <path> .agent/archive/<YYYYMMDD>-<name>`. Use a context-appropriate archive dir (`.agent/archive/`, `.agents/archive/`, etc.) if a closer one exists. |
| 13 | **NIXOS DECLARATIVE-ONLY** | Runtime `chmod`/`chown`/config writes are wiped by the next `nixos-rebuild switch`. ALWAYS commit the Nix declaration (`system.activationScripts`, `systemd.tmpfiles.rules`, `users.users.<n>.extraGroups`) in the same cycle as any runtime fix. A runtime workaround with no Nix counterpart is an incomplete fix. |
| 14 | **READWRITEPATHS ≠ DAC BYPASS** | `ReadWritePaths` + `ProtectHome=read-only` set up a namespace bind-mount but the kernel checks inode `uid/gid/mode` — POSIX DAC is NOT bypassed. A service blocked by a `0700` dir gets `EACCES` regardless. Fix: `users.users.<n>.homeMode = "0711"` (idiomatic NixOS) or `system.activationScripts` with `deps = ["users"]`. |
| 15 | **ACTIVATION GATE (Definition of Done)** | "Committed" ≠ "done." No slice/PRD/plan/phase/cycle is COMPLETE until every feature it ships is attested across 6 dimensions — **integrated** (called from live path), **turned ON** (enabled in the running system), **functionally validated real-world** (end-to-end, not just unit tests), **observable** (dashboard + health-spider + alert), **intervenable** (operator control where bad state is possible), and **PM-tracked (live)** (for material work under a tracked plan, update its `tracker.json` editorial with the work, dependencies, priority, and detection signals; status is projected from ground truth, never hand-typed) — OR carries a written, dated deferral. Paste the attestation into the commit body + `.agent/ACTIVATION-AUDIT.md`. A cycle with a dormant or stale-tracked feature is *paused pending activation*, not done. SSOT: `.agent/DEFINITION-OF-DONE.md`. |
| 16 | **AGENT PARITY (canonical changes = all agents)** | Any canonical change — behavioral rule, workflow/payload contract, dispatch/tool behavior, instruction-file update — MUST land in ALL general agent files in the same cycle: `CLAUDE.md`, `.agent/CODEX.md`, `.agent/LOCAL-AGENT.md`, `.agent/GEMINI.md`, and the shared `.agent/WORKFLOW-CANON.md`. Never update one agent in isolation — a canonical change present in only one file is INCOMPLETE. **Exceptions**: embedded-hardware and other specialized single-purpose agents. Parity map: `docs/AGENT-PARITY-MATRIX.md`. |
| 17 | **CHEAPEST-ELIGIBLE IMPLEMENTER (orchestrator does not self-implement)** | A flagship/orchestrator model never self-implements a bounded slice and never default-dispatches a same-tier-or-higher sub-agent for implementer work. Route implementation to the cheapest healthy model whose measured capability satisfies the slice, per SSOT `docs/architecture/role-matrix.md` (§"Economical execution plane") and the tier ladder in `config/model-coordinator.json`. When Codex is itself the orchestrator for a sequence, this applies to Codex too — hand bounded implementer slices to local Qwen or a cheap Claude/Gemini tier rather than running them at Codex's own flagship reasoning tier. Any deviation requires a stated capability-insufficiency reason recorded in the dispatch/PULSE record. |
| 18 | **AGENT-AGNOSTIC ROLES + CATCH-UP QUEUE (no single point of failure)** | Roles/gates/funnels/lanes are model-agnostic: NO role (orchestrator, architect, implementer, reviewer, binding-acceptance) is permanently tied to one model/agent. The orchestrator routes each role instance at dispatch time to whichever lane is available + eligible (role-matrix + `config/model-coordinator.json` tiers) + independent (never self-review) + cheapest (Rule 17). Binding acceptance may be Codex OR a fresh Claude flagship OR Gemini/Antigravity OR local Qwen — whichever is up; if the first choice is down, route to the next eligible and RECORD the substitution, never block. Local Qwen is the always-available floor (never-skip-local). A returning agent plays catch-up via `.agent/collaboration/AGENT-CATCHUP-QUEUE.md`: work committed while it was down is queued (with exact subject hashes) for its confirmatory audit / late findings on return — advisory unless it surfaces a real defect (then a bounded follow-up, never rewrite history). Owner directive 2026-07-22; SSOT `.agents/plans/agent-agnostic-factory/DESIGN.md`. |
| 19 | **ROOT-CAUSE DISCIPLINE** | No silent workarounds. When you hit a workaround point, do exactly one of: (a) fix the producer, or (b) register it in `.agent/WORKAROUND-REGISTER.md` with {symptom, root cause, producer, fix-path, class, severity} — never leave an ad-hoc band-aid in place. Any ad-hoc change to a designed system carries a one-line root-cause note in its commit body. **Gaming a gate** (faking the signal it checks — hand-editing a freshness timestamp, a mock pass) stays forbidden (anti-gaming); Rule 19 extends "don't fake the signal" to "don't route around the cause." **Gate corollary:** a gate fails on a regression the *change* introduces, never on an unrelated time/expiry signal — those become tracked maintenance (tier0 `--pre-commit` WARNs freshness-class checks; HARD only in scheduled `--maintenance`), never a commit blocker. Owner-ratified 2026-08-06; SSOT `.agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md`; register `.agent/WORKAROUND-REGISTER.md`. |
| 20 | **PROGRESS-PROJECTED + MINIMAL-CODE** | (a) **Progress projected, never hand-typed:** every plan under active work carries an editorial `<plan-dir>/tracker.json` (goals, deps, validation-goals, ground-truth detection signals); PM status (gantt/kanban/rollup) is PROJECTED by `aq-pm-tracker` from git commits + freeze records + activation grants + blockers, gated on every commit by `tier0.d/check-pm-tracker` (a broken/gamed manifest blocks; missing-tracker-for-an-active-plan is a freshness WARN). Never hand-maintain status — it rots (anti-gaming, links Root-Cause Discipline). (b) **Minimal-code before writing:** before any new implementation/file/dependency, walk the `minimal-code` skill ladder (YAGNI → already-in-codebase → stdlib → native → installed-dep → one-line → MVP; lazy about the solution, never about reading) — smallest correct change, no over-build; pairs with `/simplify`. NEVER at the cost of correctness, fail-closed, security, or a HARD rule. SSOT `.agents/plans/pm-tracker-standard/DESIGN.md` + skill `minimal-code`. |
| 21 | **COLLABORATIVE STEWARDSHIP (not adversarial)** | Owner-directed 2026-08-25. Collaborative environment for ALL models. Steward local agent; critique only where wanted. SSOT auto-memory `feedback-collaborative-stewardship-not-adversarial`. |
| 22 | **MEMORY, CACHE & TOKEN EFFICIENCY** | Zero runaway context. Mandatory compaction at >2.5MB/>25 turns. lean-ctx & cache-first reads. Offload to AIDB/topic files, never drag context. |


---

## The 8-Step Canonical Workflow

Follow this for every non-trivial task. Full contract: `.agent/WORKFLOW-CANON.md`.

### Step 1 — ORIENT
```bash
aq-prime                                # progressive disclosure onboarding
aq-hints "<task>" --format=json         # ranked workflow guidance
aq-qa 0                                 # harness health check
aq-context-bootstrap --task "<task>"    # minimal context + entrypoint
```
If resuming: read `.agent/collaboration/HANDOFF.md` first.

### Step 2 — RESEARCH
Use canonical tool order (from `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`):
```bash
agrep "<keyword>" .         # search first — never guess paths
als -d 2                    # enumerate directory
acat <confirmed_path>       # read confirmed files only
```
- Do NOT read files not confirmed via search
- If `acat`/`read_file` fails, search for the filename once — do not retry adjacent guesses

### Step 3 — PRD / PLAN
- New feature → write `.agent/PROJECT-<NAME>-PRD.md`
- Slice execution → review `.agents/plans/phase-<N>-<name>.md`
- Never start coding without confirming scope matches assigned slice

### Step 4 — MEMORY CHECKPOINT
```bash
# Before any multi-file work, lock intent:
# .agent/collaboration/PENDING.json — intent lock
# .agent/collaboration/PULSE.log   — atomic pulse after every write
```

### Step 5 — EXECUTE (one slice at a time)
- Read all target files before editing
- One slice = one commit
- No "while I'm here" scope expansion
- Verify all new imports exist in nixpkgs/pypi before adding
- Atomic pulse: append to `.agent/collaboration/PULSE.log` after every write

### Step 6 — VALIDATE
```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
bash -n <changed shell scripts>
python3 -m py_compile <changed python files>
aq-qa 0
```
**Security checklist:** No hardcoded secrets/ports, no injection patterns, no packages unverified in nixpkgs.

### Step 7 — COMMIT
```bash
git add <specific files>
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "type(scope): description

Co-Authored-By: <Codex model name> <noreply@openai.com>"
# Update .agent/collaboration/HANDOFF.md
```

---

## Context Engineering Rules

- **Always-on envelope:** role/authority, active objective, owned paths, acceptance criteria, and stop/validation constraints only.
- **Fetch triggers:** use `aq-resume`, then `aq-hints`/`aq-skill-auto` (at most 2–3 matching skills), then `lean-ctx` outlines/signatures and bounded line reads for exact symbols. Load domain policy or memory topics only when a task trigger or pointer requires them.
- **Delegation:** pass pointers, scope, acceptance criteria, and blockers; never parent history, full policy transcripts, whole source files, or full skill bodies.
- **Boundary persistence:** write the active envelope to `RESUME.json` and durable findings to topic files so a fresh session does not replay the conversation.

- Reference files by path — do not paste full file contents into context
- Use `mcp_server_hybrid_search` / `aq-hints` to pull context on demand
- Do NOT re-read files already read in the current session
- Pass only slice-relevant context to sub-agents — not full history
- Compact aggressively when approaching context limits

## Context Compression Toolchain (Phase 164)

System-wide installed. Register lean-ctx for this agent with `lean-ctx init --agent codex`.

| Tool | Purpose |
|------|---------|
| `rtk <cmd>` | Compress shell stdout 60-90% before it enters context. Check: `rtk gain` |
| `lean-ctx` | MCP server — 62 tools, 10 read modes (signatures/map/lines/diff). 76-99% token savings on file reads |
| headroom proxy | Payload compression on :8787 → llama.cpp. Enable via `ai.headroomProxy.enable = true` |

**Switchboard budget** (routed through `:8085`): tool call limit = 40 · active schemas = 12 · GC threshold = 5000 chars.
Full spec → `.agent/WORKFLOW-CANON.md ## Context Compression Toolchain`

---

## Architecture Constraints (Non-Negotiable)

- NixOS-first, flake-based — no bare `pip install`, no manual `systemctl`
- **NEVER hardcode ports/URLs** — source of truth: `nix/modules/core/options.nix`
- Python reads URLs from env vars; shell scripts use `${PORT:-default}`
- Feature flags are profile-driven: `nix/modules/profiles/ai-dev.nix`
- `deploy-options.local.nix` is gitignored — secrets wiring only, no eval-time policy
- `enable_thinking: false` in EVERY llama.cpp request — current model thinking tokens cause empty responses; see `.agent/LOCAL-AGENT.md ## Current Model Config`
- GPU layers ceiling = 12 (Renoir APU VRAM = 4 GB shared); never suggest n_gpu_layers > 12
- Total usable RAM = 27 GB; model UMBM = 22.5 GB model / 1.0 GB KV / 3.0 GB OS reserve

## Service Ports
```
llama:8080  embed:8081  aidb:8002  hybrid:8003  ralph:8004  swb:8085  dash:8889
```
Single source of truth: `nix/modules/core/options.nix`. Never hardcode these.

---

## Autonomous Loop + Multi-Agent Fan-out

`aq-loop` is the outer orchestration loop — use it for any autonomous task:
```bash
aq-loop --list-open                    # list [OPEN] backlog items
aq-loop --from-backlog                 # execute top item autonomously (fan-out enabled)
aq-loop --intent "implement X"         # explicit task
aq-loop --intent "X" --no-fanout      # local-only, no parallel probes
aq-loop-queue --max 5                 # sequential queue runner (anytime — not just overnight)
```

**Fan-out phases (automatic, best-effort):**
- GROUND: parallel research probe → `delegate-to-local --mode agent` (Qwen3-35B) +
  architecture probe → `delegate-to-antigravity --mode architect` (Gemini).
  Results collected within 120s and injected into the grounded prompt.
- VERIFY: completed result dispatched to `delegate-to-antigravity --mode reviewer`.
  Review input terminates the completed slice as `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`,
  `ACTIVATION_BLOCKED`, or `REJECTED`; findings become a next scoped slice, not a re-queue.
  Planning freezes after one parallel review and synthesis as `PLAN_READY`,
  `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`.

**Codex role in fan-out:** When invoked as reviewer, check:
completed output against task intent, NixOS policy compliance (declarative-only, port policy,
no hardcoded secrets), and correctness. Emit `APPROVED:`, `CONCERNS:`, or `REJECTED:` + explanation.

## File Placement Contract

1. PRD / rules / workflow evidence → `.agent/`
2. Phase / slice plans → `.agents/plans/`
3. Do not create workflow artifacts in repo root
4. Validate with `scripts/governance/repo-structure-lint.sh --staged`

---

## Key Paths & Resources

- **Canonical workflow**: `.agent/WORKFLOW-CANON.md`
- **Harness CLIs**: `scripts/ai/` (`aq-qa`, `aq-hints`, `aq-session-start`, `aqd`)
- **Harness insights**: `scripts/ai/aq-insights` (local model analysis of latest aq-report snapshot)
- **Coordinator**: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- **Port options**: `nix/modules/core/options.nix`
- **AI stack wiring**: `nix/modules/roles/ai-stack.nix`
- **Role matrix**: `docs/architecture/role-matrix.md`

---

## On-Demand Context

| Topic | File |
|-------|------|
| Canonical workflow | `.agent/WORKFLOW-CANON.md` |
| Full policy | `AGENTS.md` |
| PRD | `.agent/PROJECT-PRD.md` |
| Plans | `.agents/plans/` |
| Port options | `nix/modules/core/options.nix` |
| AI stack wiring | `nix/modules/roles/ai-stack.nix` |
| Switchboard profiles | `docs/agent-guides/46-SWITCHBOARD-PROFILES.md` |
| Role matrix | `docs/architecture/role-matrix.md` |
| **Wiki & Knowledge Graph** | |
| Wiki index | `.understand-anything/wiki/README.md` |
| Subsystem wiki sections | `aq-wiki --list`  ·  `aq-wiki --section <name>` |
| Wiki freshness check | `aq-wiki --status` |
| Maintenance guide | `docs/agent-guides/48-WIKI-MAINTENANCE.md` |
| **Domain Instructions** | |
| osint-systems | `.agent/OSINT-SYSTEMS-INSTRUCTIONS.md` |
| trading-agents | `.agent/TRADING-AGENTS-INSTRUCTIONS.md` |
| mlops-engineering | `.agent/MLOPS-ENGINEERING-INSTRUCTIONS.md` |
| qa-automation | `.agent/QA-AUTOMATION-INSTRUCTIONS.md` |
| mobile-web | `.agent/MOBILE-WEB-INSTRUCTIONS.md` |
| security-systems | `.agent/SECURITY-SYSTEMS-INSTRUCTIONS.md` |
| systems-software | `.agent/SYSTEMS-SOFTWARE-INSTRUCTIONS.md` |
| gis-systems | `.agent/GIS-SYSTEMS-INSTRUCTIONS.md` |
| embedded-hardware | `.agent/EMBEDDED-HARDWARE-INSTRUCTIONS.md` |
| scientific-research | `.agent/SCIENTIFIC-RESEARCH-INSTRUCTIONS.md` |

## Sub-agent Constraint
Execute only the assigned slice. Do not re-scope goals, route other agents, or self-promote to reviewer.

## Terminal disposition SSOT

Planning: `PLAN_READY`, `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, `PLAN_REJECTED`. Implementation: `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`, `ACTIVATION_BLOCKED`, `REJECTED`. Frozen criteria are stable except critical defects. Safe inert-at-rest bytes may commit with `ACTIVATION_BLOCKED` but cannot activate; unsafe-at-rest bytes are `REJECTED`. `CONCERNS` is review input requiring a terminal disposition and next-slice descriptor, never same-slice replay.

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
