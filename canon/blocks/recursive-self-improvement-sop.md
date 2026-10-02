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
  - **Gate Contention**: When multiple agents run heavyweight validation simultaneously, serialize access by running tier0 via its wrapper (`scripts/governance/tier0-validation-gate.sh`), which acquires and releases the `aq-gate-checkout` lock itself — never take a second checkout around it — to prevent tool contention, memory exhaustion, and hanging processes.

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

### 3. Owner Decision Inbox (approval SOP, owner-adopted 2026-10-02)
Supersedes the 2026-09-30 "approvals CLI-first" rule. Plan: `.agents/plans/approval-inbox-20261002/PLAN.md`.
- **One inbox, one record:** `aq-approve` lists and acts over the canonical PRSI/RSI queue and the attention queue. Decisions are audited (`approval-inbox-audit.jsonl`, `prsi-actions.jsonl`).
- **Two sections, one numbering:** *Needs approval* (a fix is ready and waits for the owner) and *Deferred* (found and logged, but low priority or not fixable yet). Deferred items come from the existing RSI intake (`rsi_lifecycle failure` / `aq-rsi-run`); there is no second intake path.
- **Surfacing:** `aq-resume` prints the inbox summary at session start. Any agent turn that adds items ends by printing `aq-approve` (the numbered list with its snapshot tag).
- **Deciding in chat:** the owner replies "approve 1 3" / "deny 2" / "dismiss 4". The agent runs `aq-approve <verb> <numbers> --tag <tag> --door chat`. That command always raises the harness permission prompt, and the owner's confirmation is the approval. The prompt is forced by the PreToolUse hook `scripts/ai/aq-approval-ask-hook`, because permission `ask` rules do not prompt in auto mode (verified live 2026-10-02). Codex uses its own approval prompt. Local/Qwen proposes only.
- **Guards:**
  - A stale tag refuses the action and re-lists, so the owner never approves a renumbered list.
  - Agents never run the write forms without that prompt; there is no self-approval.
  - Dismiss hides an item but never marks it resolved (anti-gaming).
  - Approve/deny on a deferred item is refused.
- **Deferred surface:** the `/approve` dashboard page will use the same backend later.
