# PRD: Project Agentic Engineering Advancement (P.A.E.A) v3.1

**Status:** Definitive Draft
**Owner:** hyperd
**Date:** 2026-05-25

---

## 1. Vision: The Sovereign Software Factory
Transition the NixOS AI Harness into a **Level 5 "Dark Factory"**. This system does not just assist; it autonomously manages the entire SDLC using a hierarchical team of specialized agents with direct **Agentic Access** to system resources.

---

## 2. The 5 Pillars of Agentic Engineering (Framework)
All features MUST align with these pillars:
1.  **The Agent Harness**: The NixOS-based infrastructure hosting the agents.
2.  **Agentic Access**: Direct programmatic reach via CLI/API (eliminating the "Token Tax").
3.  **Agentic Memory**: Compounding knowledge via DAG-based session trees and AIDB.
4.  **Agentic Orchestration**: Multi-agent handoffs with formal JSON schemas.
5.  **Agentic Verification**: Dual-layer evals (Selection vs. Execution).

---

## 3. Team Hierarchy & Specialized Roles

The factory operates via a **Hierarchical Team** model.

| Role | Grade | Responsibility |
| :--- | :--- | :--- |
| **Orchestrator (Oz)** | L3 (Gemini/Claude) | **Control Plane.** Manages agent lifecycle, session DAGs, and handoff loop protection. |
| **Architect (Manager)** | L2 (Qwen3-35B) | **Planning.** Decomposes tasks, maps dependencies, and writes the `PLAN.md`. |
| **Unit (Coder)** | L1/L2 (Local/Mixed) | **Execution.** Implements the code changes within an **Intent Lock**. |
| **Auditor (Critic)** | L2 (Qwen3-35B) | **Verification.** Reviews implementation vs. plan. Red-teams proposed changes. |
| **Guardian (Tester)** | L1 (Llama-3-8B) | **Validation.** Writes/runs tests and monitors system health. |

---

## 4. Orchestration Protocols & Schemas

### 4.1 Branchable DAG Session Manager (BSM)
*   **Schema**: JSONL format with `id`, `parentId`, and `type` (message, tool_call, compaction).
*   **Compaction**: At 85% context, the agent MUST trigger a `compaction` event, extracting **Key Facts** and a **Summary** to reset the window while preserving the DAG.

### 4.2 Agent Handoff Protocol
Handoffs MUST use the following JSON schema to preserve state:
```json
{
  "trace_id": "uuid-v4",
  "source": "Architect-01",
  "target": "Coder-05",
  "handoff_count": 1,        // Loop protection (max 10)
  "reason": "Planning complete",
  "payload": {
    "summary": "Step-by-step implementation plan for Nix refactor.",
    "state": { "target_file": "nix/core.nix", "port": 8080 },
    "pending_tasks": ["Apply replace", "Run validation"]
  }
}
```

### 4.3 Drop Zone Automation (`drops.yaml`)
```yaml
drop_zones:
  - name: "Autonomous Refactor"
    watch: ["src/api/*.py"]
    trigger: ["modified"]
    skill: ".agent/skills/refactor/SKILL.md"
    team: ["Architect", "Coder", "Auditor"]
    handoff_limit: 5
```

---

## 5. Agentic Service Level Agreements (ASLAs)

| Constraint | Limit | Logic |
| :--- | :--- | :--- |
| **Turn Budget** | Max 12 turns | Prevent reasoning loops. |
| **Token Arbitrage** | L1 for Triage | Use Llama-3-8B for all `ls`, `grep`, `read` ops. |
| **Intent Lock** | Sequential Edits | `PENDING.json` blocks concurrent edits to the same file. |
| **Hardening** | 48h Min-Age | Flake inputs must be >= 48h old to mitigate protestware. |

---

## 6. Acceptance Criteria (Hardened)

*   [ ] **Autonomous Handoff**: Architect can successfully hand off a task to a Coder with a valid `handoff_count`.
*   [ ] **DAG Branching**: `aq-branch` successfully splits a session into two divergent histories.
*   [ ] **Loop Protection**: Orchestrator terminates a session if `handoff_count` exceeds 10.
*   [ ] **Token Efficiency**: Research phases show >30% reduction in L2 model token usage via L1 triage.
*   [ ] **Verification Depth**: Auditor correctly identifies and blocks a "bad but passing" code change.
