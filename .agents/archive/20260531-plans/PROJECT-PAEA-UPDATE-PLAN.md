# System Update Plan: Agentic Engineering Advancement

**Project:** P.A.E.A (Project Agentic Engineering Advancement)
**Phasing Strategy:** Incremental deployment with mandatory validation gates.

---

## Phase 1: Collective Intelligence (CI) & Shared Lessons
**Goal:** Break the silos between agent sessions.

1.  **Implement CI Endpoint:** Add a `/lessons/push` and `/lessons/query` route to the `hybrid-coordinator`.
2.  **AIDB Integration:** Create the `agent-intelligence` namespace in Qdrant/PostgreSQL.
3.  **Workflow Update:** Modify `scripts/ai/aq-session-end` to automatically push insights from `aq-insights` to the CI endpoint.
4.  **Validation:** Run two concurrent sessions and verify the second session "recalls" the lessons from the first via `aq-hints`.

---

## Phase 2: Always-On Background Agents (AFK)
**Goal:** Enable asynchronous, long-running agent tasks.

1.  **`aq-daemon` Service:** Create a background service in `ai-stack/agents/daemon/` to manage task queues.
2.  **Detach/Attach Protocol:** Implement CLI flags for `aq-session-start --background` and a way to re-attach to view progress.
3.  **Dashboard Wiring:** Add an "Agent Fleet" tab to the dashboard showing active daemon tasks.
4.  **Validation:** Background a linting/refactoring task across the entire codebase and verify its successful completion/commit without user intervention.

---

## Phase 3: Software Factory & Hardening
**Goal:** Automate the dev lifecycle and secure the supply chain.

1.  **Factory CLI:** Implement `scripts/ai/aq-factory` to automate tool scaffolding and Nix registration.
2.  **Nix Hardening:** Update `flake.nix` and `nix/modules/core/base.nix` to implement `min-release-age` checks on flake inputs (via a custom lint script).
3.  **Self-Extensibility:** Enable the agent to use `aq-factory` to create its own tools when a capability gap is detected.
4.  **Validation:** Use the agent to "identify a missing tool, create it via factory, and use it" in a single session.

---

## Phase 4: Agentic TUI & Performance Optimization
**Goal:** High-fidelity monitoring and system-wide efficiency.

1.  **TUI Library Integration:** Integrate a Python TUI library (e.g., `Rich` or `Textual`) into the core CLI tools.
2.  **Differential Deployment Logs:** Replace `nixos-quick-deploy.sh` standard output with a TUI showing live stage progress and error callouts.
3.  **Token Arbitrage Logic:** Optimize `switchboard` to more aggressively route small sub-tasks to smaller, faster local models to save context for the main orchestrator.
4.  **Validation:** Run a full system deployment and verify the TUI provides actionable feedback without log flooding.

---

## Next Steps

1.  **Review:** Present the PRD and Update Plan for user approval.
2.  **Bootstrap:** Execute `scripts/ai/aq-context-bootstrap --task "Phase 1: Collective Intelligence"`.
3.  **Implement:** Begin surgical updates to the `hybrid-coordinator` for the CI endpoint.
