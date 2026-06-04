---
name: async-delegation
description: "Skill: Asynchronous Delegation"
---

# Skill: Asynchronous Delegation

- **Purpose**: Autonomously execute arbitrary tasks dropped into the `tasks_inbox/` directory by users or other agents.
- **Variables**:
  - `task_file`: Path to the `.md` file containing the task description.
- **Instructions**:
  1. Read the `task_file` to understand the objective.
  2. Map the objective to the codebase using Agentic Grep (`agrep`).
  3. Formulate a `PLAN.md` and check it into memory.
  4. Handoff to the Coder agent to implement the required changes within an Intent Lock (`PENDING.json`).
  5. The Coder will handoff to the Auditor for review.
  6. Upon successful audit, commit the changes with a message referencing the original `task_file`.
  7. Move the `task_file` to `tasks_inbox/archive/` to prevent re-triggering.
- **Workflow**:
  1. `read_file` (task_file)
  2. Handoff: Architect -> Coder -> Auditor
  3. `run_shell_command` (git commit)
  4. `run_shell_command` (mv task_file tasks_inbox/archive/)
- **Report**: A summary of the completed task and the commit hash.
