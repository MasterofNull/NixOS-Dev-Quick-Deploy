# Advanced System Update Plan: Software Factory Implementation (v3.1)

---

## Phase 1: Fundamental Data Structures (DAG + Handoffs)
**Goal:** Deploy the tree-based session engine and the formal handoff protocol.

1.  **DAG Session Manager:** Implement `ai-stack/agent-memory/dag_manager.py` with `parentId` support and JSONL persistence.
2.  **Handoff Schema Enforcement:** Implement Pydantic-based validation for the handoff JSON payload.
3.  **Recursive AGENTS.md:** Deploy the hierarchical context loader (`scripts/ai/lib/context_merger.py`).
4.  **Validation:** Demonstrate an agent "branching" a session to try two different implementation strategies.

---

## Phase 2: Event-Driven Automation (Drop Zones)
**Goal:** Enable "Away From Keyboard" (AFK) autonomous intake.

1.  **Drop Zone Daemon:** Deploy `scripts/ai/aq-drop-daemon` to monitor `drops.yaml` paths.
2.  **Intent Locking (v2):** Enhance `PENDING.json` to include agent ID and TTL (Time-To-Live) for locks.
3.  **Skill Factory:** Implement `aq-factory` to scaffold new skills using the PVIWR schema.
4.  **Validation:** Modify a file in a watched directory and verify the Architect autonomously initiates a Planning phase.

---

## Phase 3: Token Arbitrage & Switchboard 2.0
**Goal:** Maximize speed and minimize "Token Tax."

1.  **L1 Triage Routing:** Configure `switchboard` to auto-route all "Read-Only" tool calls to the L1 model tier.
2.  **Complexity Estimator:** Implement the logic to promote high-complexity sub-tasks to the L2 model.
3.  **Compaction Logic:** Deploy the auto-compaction system to summarize DAG branches at 85% context.
4.  **Validation:** Run a full-system audit and confirm L2 model tokens are reserved strictly for reasoning/editing.

---

## Phase 4: High-Fidelity Observability (Oz + A-TUI)
**Goal:** Full transparency into agent "Thought Processes."

1.  **Oz Control Plane:** Add the "Agent Fleet" tab to the dashboard with live DAG visualizations.
2.  **Textual TUI:** Refactor `aq-qa` and `aq-report` into a rich terminal dashboard.
3.  **Trace Visualization:** Implement a "Thought Trace" viewer in the dashboard that shows the `parentId` tree for active sessions.
4.  **Validation:** Monitor a multi-agent handoff in real-time via the dashboard.

---

## Phase 5: Production Hardening & Sovereign Ops
**Goal:** Security and Self-Improvement.

1.  **Temporal Supply-Chain Guard:** Implement the 48h min-age check for Nix flake inputs.
2.  **Collective Intelligence Loop:** Automate the lesson-pushing process from `aq-insights` to the `agent-intelligence` AIDB namespace.
3.  **Final Integration:** Execute a "Full System Hardening" task from a Drop Zone to verify the entire Level 5 pipeline.
4.  **Validation:** System autonomously identifies a vulnerability, plans a fix, executes the refactor, verifies via Auditor, and commits—all while the user is AFK.
