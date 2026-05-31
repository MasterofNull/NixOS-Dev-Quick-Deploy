# PRD: Project Agentic Engineering Advancement (P.A.E.A) v2.0

**Status:** High-Granularity Draft
**Owner:** hyperd
**Date:** 2026-05-25

---

## 1. Architectural Vision: The Software Factory
Transition the NixOS AI Harness from a session-based assistant to a **Sovereign Software Factory**. This requires moving "outside the loop" to engineer the environment, observability, and toolsets that allow for autonomous, reliable operation.

---

## 2. Core Functional Requirements

### FR1: Hierarchical Context Engine (HCE)
*   **Requirement:** Implement recursive instruction loading. The `hybrid-coordinator` MUST walk up the directory tree and merge all `AGENTS.md` or `CLAUDE.md` files found.
*   **Logic:** Child instructions override parent instructions. Root rules (security, formatting) are always preserved.
*   **Benefit:** Precise, context-aware instructions for different sub-systems (e.g., Nix vs. Python vs. Dashboard).

### FR2: Branchable DAG Session Manager (BSM)
*   **Requirement:** Refactor the session storage from a linear JSON array to a **Directed Acyclic Graph (DAG)** stored in JSONL.
*   **Features:**
    *   `aq-branch`: Create a new session branch from any previous turn ID.
    *   `aq-merge`: Synthesize the findings of two branches into a single state.
*   **Benefit:** Eliminates "rabbit hole" failure modes and allows for parallel research branches.

### FR3: Gherkin Intent-Based Tooling (GIT)
*   **Requirement:** All tool registrations in AIDB MUST follow the **Purpose-Variable-Instruction-Workflow-Report (PVIWR)** schema.
*   **Benefit:** Drastically improves tool selection accuracy and reliability of implementation turns.

### FR4: Dual-Layer Validation Gate (DLV)
*   **Requirement:** Implement a new QA suite in `aq-qa` that measures:
    *   **Selection F1-Score:** Accuracy of picking the right tool for a given natural language intent.
    *   **Execution Pass-Rate:** Success of the tool in achieving the desired system state.
*   **Benefit:** Identifies whether a failure is due to reasoning (selection) or implementation (execution).

### FR5: Temporal Supply-Chain Guard (TSG)
*   **Requirement:** A Nix-integrated check that audits flake inputs.
*   **Rule:** `age(input) >= 48h`.
*   **Benefit:** Mitigates "protestware" and zero-day supply chain attacks against the agent's environment.

---

## 3. Technical Implementation Details

### R1: Token Arbitrage via Switchboard
*   **Policy:**
    *   **L1 (Triage):** Small local model (Llama-3-8B) for `ls`, `grep`, `find`.
    *   **L2 (Reasoning):** Qwen3-35B for plan generation and complex edits.
    *   **L3 (Verification):** Dedicated review gate (Gemini/Claude) for high-impact commits.

### R2: Differential TUI (Terminal UI)
*   **Library:** Use `Textual` (Python) to refactor `aq-qa` and `nixos-quick-deploy`.
*   **UI Components:** Live tree-view of task progress, real-time diff previews, and "thought-trace" sidebars.

### R3: Extension Framework
*   **Mechanism:** `importlib`-based plugin architecture in `ai-stack/plugins/`.
*   **capability:** Allow agents to write and register their own "Skills" (bundled workflows) as Python modules.

---

## 4. Acceptance Criteria (Hardened)

*   [ ] `aq-load-context` correctly merges rules from 3 directory levels.
*   [ ] `aq-branch` successfully restores a previous state and generates a divergent path.
*   [ ] Synthetic benchmark achieves >90% **Selection Accuracy** on standard toolsets.
*   [ ] Nix build fails if a flake input is less than 48 hours old (without `--force-fresh`).
*   [ ] Dashboard reflects "Agent Fleet" status with live DAG visualization of active sessions.
