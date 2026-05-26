# PRD: Project Agentic Engineering Advancement (P.A.E.A)

**Status:** Draft
**Owner:** hyperd
**Date:** 2026-05-25
**Sources:** `earendil-works/pi` repository, "Top #1 Opportunity for Senior Engineers: Agentic Engineering" (YouTube)

---

## 1. Problem Statement

While the current NixOS AI harness is robust and feature-rich, it operates primarily in a **reactive, session-based mode**. To reach parity with industry-leading agentic engineering benchmarks (like the `pi` harness) and realize the vision of "Always-On Agents," we must transition from "vibe coding" to a formal **Agentic Engineering** paradigm.

### Key Gaps:
*   **Isolation of Intelligence:** Lessons learned in one session aren't immediately available to others without manual memory promoter steps.
*   **Synchronous Bottlenecks:** Agents are tethered to the active session; backgrounding complex research or long-running tasks is not yet native.
*   **Extensibility Overhead:** Adding new capabilities requires manual wiring of scripts rather than an automated "Software Factory" approach.
*   **UI/UX for Local Dev:** Monitoring long-running deployments lacks the high-fidelity differential rendering (TUI) seen in advanced agent toolkits.

---

## 2. Goals & Objectives

1.  **Collective Intelligence:** Implement a real-time lesson-sharing mechanism via AIDB.
2.  **AFK (Always On) Capability:** Enable agents to run background "Software Factory" tasks (e.g., automated refactoring, continuous QA).
3.  **Agent-Native Extensibility:** Formalize the "Software Factory" concept to automate the creation and registration of new agent tools.
4.  **Local Dev Fidelity:** Upgrade CLI tools with differential TUI for live, high-signal progress monitoring.

---

## 3. High-Level Requirements

### R1: Collective Intelligence Loop (CIL)
*   **Lesson Pushing:** Agents MUST automatically push "learned patterns" (success/failure) to a dedicated `agent-intelligence` AIDB namespace after each task.
*   **Proactive Retrieval:** The `hybrid-coordinator` MUST query this namespace during the ORIENT phase of every new session.

### R2: Background Operation Daemon (BOD)
*   **`aq-daemon`**: A service to manage backgrounded agent tasks.
*   **Task Handover**: Ability to start a task in a session and "detach" it to the daemon for completion.
*   **Telemetry**: Dashboard cards for background agent status, CPU/Memory pressure, and task completion.

### R3: Software Factory Formalization
*   **Auto-Tooling**: A command to scaffold, test, and register a new tool in the `ai-stack` from a simple description.
*   **Parity with `pi`**: Adopt supply-chain hardening policies (min-release-age, etc.) within the Nix build process.

### R4: Agentic TUI (A-TUI)
*   **Differential Rendering**: Implement a TUI library (e.g., `textual` or `blessed`) for `aq-qa` and `nixos-quick-deploy`.
*   **Rich Signals**: Live diffs, progress bars, and "thought traces" in the terminal.

---

## 4. Constraints

*   **NixOS-First**: All changes must be declaratively managed via Nix flakes.
*   **Local-Inference Priority**: Heavy lifting (reasoning) should favor the local Qwen3-35B model.
*   **Hardware Floor**: Must respect the 27GB RAM and Renoir APU VRAM limits.
*   **No "Just-in-case" Logic**: Maintain surgical implementation and avoid feature creep.

---

## 5. Acceptance Criteria

*   [ ] `aq-qa 0` includes a check for the Collective Intelligence endpoint.
*   [ ] A backgrounded `aq-daemon` task can successfully commit code and signal the dashboard.
*   [ ] `scripts/ai/` contains a `factory` CLI for tool generation.
*   [ ] Deployments show a live TUI progress indicator instead of scrolling logs.
*   [ ] Every new service has a dashboard card and `aq-qa` check (Service Coverage Contract).
