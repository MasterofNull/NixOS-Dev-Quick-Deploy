# Advanced System Update Plan: Software Factory Implementation (v3)

---

## Phase 1: Team Infrastructure & DAG Sessions
**Goal:** Deploy the multi-agent registry and the branchable history engine.

1.  **Agent Registry:** Create `ai-stack/agents/registry.json` to define role profiles (L1/L2/L3) and their specific ASLAs.
2.  **DAG Manager:** Implement the JSONL-based session tree in `ai-stack/agent-memory/dag_manager.py`.
3.  **Hierarchical Context:** Implement the recursive `AGENTS.md` loader.
4.  **Validation:** Verify `aq-session-start` correctly identifies the "Architect" for planning and "Coder" for execution.

---

## Phase 2: Autonomous Intake & Drop Zones
**Goal:** Transition from manual session starts to event-driven automation.

1.  **Drop Zone Daemon:** Implement `scripts/ai/aq-drop-daemon` using `inotify` to monitor `drops.yaml` paths.
2.  **Workflow Router:** Create the logic to map file events to `SKILL.md` workflows.
3.  **Intent Locking:** Deploy the `PENDING.json` Intent Lock mechanism to prevent agent collisions.
4.  **Validation:** Drop a file into `research_inbox/` and verify an agent autonomously starts a planning session.

---

## Phase 3: The Implementation-Review Loop
**Goal:** Eliminate "vibe coding" through formalized verification.

1.  **Handoff Protocol:** Implement the "Plan -> Implementation -> Review" bridge.
2.  **Auditor Logic:** Create the "Critic" persona in `ai-stack/agents/auditor.py` with a "Trust but Verify" prompt.
3.  **Dual-Layer Eval:** Deploy the Selection vs. Execution benchmark suite.
4.  **Validation:** Intentionally introduce a bug in a Coder's work and verify the Auditor blocks the commit.

---

## Phase 4: Control Plane & Token Arbitrage
**Goal:** System-wide observability and cost/speed optimization.

1.  **Oz Control Plane:** Add the "Agent Fleet" tab to the dashboard (`dashboard.html` + `assets/dashboard.js`).
2.  **L1/L2 Routing:** Configure `switchboard` to auto-tier tasks (L1 for Triage, L2 for Reasoning).
3.  **Textual TUI:** Refactor `aq-qa` into a rich terminal dashboard.
4.  **Validation:** Measure the latency of a multi-agent task and confirm >40% improvement via L1 triage.

---

## Phase 5: Dark Factory Operations
**Goal:** Full autonomy and self-improvement.

1.  **Temporal Hardening:** Deploy the 48h min-age check for Nix flake inputs.
2.  **Skill Factory:** Implement `aq-factory` to allow agents to "code their own skills."
3.  **Collective Intelligence:** Automate the lesson-pushing loop from `aq-insights` to AIDB.
4.  **Final Validation:** Trigger a "System Hardening" task via a Drop Zone and verify a full multi-agent cycle (Plan/Code/Audit/Commit) completes without human intervention.
