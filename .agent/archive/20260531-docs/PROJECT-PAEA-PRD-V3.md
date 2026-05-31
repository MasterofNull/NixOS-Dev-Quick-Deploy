# PRD: Project Agentic Engineering Advancement (P.A.E.A) v3.0

**Status:** Definitive Draft
**Owner:** hyperd
**Date:** 2026-05-25

---

## 1. Vision: The Sovereign Software Factory
Transition the NixOS AI Harness into a **Level 5 "Dark Factory"**. This system does not just assist; it autonomously manages the entire SDLC—from requirement intake to verified deployment—using a hierarchical team of specialized agents.

---

## 2. Team Hierarchy & Roles

The factory operates via an **Orchestrator-Manager** model.

| Role | Grade | Responsibility |
| :--- | :--- | :--- |
| **Orchestrator (Oz)** | L3 (Gemini/Claude) | **Control Plane.** Manages agent lifecycle, session DAGs, and top-level routing. |
| **Manager (Architect)** | L2 (Qwen3-35B) | **Planning.** Decomposes tasks, maps dependencies, and writes the `PLAN.md`. |
| **Unit (Coder)** | L1/L2 (Local/Mixed) | **Execution.** Implements the code changes defined in the plan. |
| **Auditor (Critic)** | L2 (Qwen3-35B) | **Verification.** Reviews implementation vs. plan. No self-review allowed. |
| **Guardian (Tester)** | L1 (Llama-3-8B) | **Validation.** Writes/runs tests and monitors system health. |

---

## 3. Orchestration & Handoff Protocols

### 3.1 The State Machine
Tasks MUST transition through the following states, tracked in `session.jsonl`:
1.  **INTAKE**: User/System drops task into a **Drop Zone**.
2.  **PLANNING**: Architect produces a step-by-step `PLAN.md`.
3.  **IMPLEMENTATION**: Coder executes turns. `PENDING.json` acts as an **Intent Lock**.
4.  **VALIDATION**: Tester runs functional/security tests.
5.  **REVIEW**: Auditor provides a PASS/FAIL verdict.
6.  **COMMIT/DEPLOY**: Orchestrator finalizes the integration.

### 3.2 Hierarchical Conflict Resolution
*   If **Auditor** fails a review: Task returns to **Coder** with specific "Refactor Guidance".
*   If **Coder** disputes **Auditor**: **Orchestrator** performs a "Tie-Breaker" pass using a higher-tier model.
*   If **Tester** reports a regression: Task is auto-blocked from COMMIT and escalated to **Architect**.

---

## 4. Granular Data Schemas

### 4.1 `SKILL.md` (The Capability Protocol)
Every agent skill must follow the **PVIWR** schema:
```markdown
# Skill: [Name]
- **Purpose**: High-level goal (e.g., "Refactor Nix modules").
- **Variables**: Required inputs (e.g., `target_file`, `new_pattern`).
- **Instructions**: Specific rules for the LLM.
- **Workflow**: Step-by-step agentic execution path.
- **Report**: Expected success evidence (e.g., "Test pass + 0 lint errors").
```

### 4.2 `drops.yaml` (The Autonomous Intake)
```yaml
drop_zones:
  - name: "Security Audit"
    watch: ["src/**/*.py"]
    trigger: ["created", "modified"]
    skill: ".agent/skills/security-audit/SKILL.md"
    team: ["Architect", "Auditor"] # Specialized team for this zone
    model_tier: "L2"
```

### 4.3 `PENDING.json` (The Intent Lock)
```json
{
  "session_id": "dag-778",
  "active_agent": "Coder-01",
  "intended_changes": [
    {"file": "nix/core.nix", "action": "replace", "reason": "Fix port collision"}
  ],
  "locks": ["/home/hyperd/repo/nix/core.nix"]
}
```

---

## 5. Agentic Service Level Agreements (ASLAs)

| Constraint | Limit |
| :--- | :--- |
| **Turn Budget** | Max 10 turns per Implementation slice. |
| **Context Ceiling** | Auto-compact at 85% window utilization. |
| **Retry Budget** | Max 3 attempts for a failing `replace` before escalation. |
| **Token Arbitrage** | L1 models MUST be used for all `ls`, `grep`, and `read` ops. |

---

## 6. Acceptance Criteria (Production Grade)

*   [ ] **Cross-Agent Visibility**: Dashboard shows "Agent Fleet" with real-time state (Planning/Coding/Reviewing).
*   [ ] **Autonomous Handoff**: Architect can successfully hand off a `PLAN.md` to a Coder without user input.
*   [ ] **Review Gate Enforcement**: Code cannot be committed without a PASS verdict from an Auditor.
*   [ ] **DAG Persistence**: Full session history is stored as a branchable DAG, allowing "what-if" analysis.
*   [ ] **Supply-Chain Guard**: Flake inputs are temporal-gated (48h minimum age).
