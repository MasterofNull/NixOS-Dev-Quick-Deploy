<!--
Skill: execute
Role: implementer
Inputs: plan file path
Outputs: execution report, changed files
Example: /execute .agents/plans/phase-1-setup.md
-->
---
description: Execute implementation from a plan file
argument-hint: [plan-file]
---

# Execute Plan

1. Read plan file from `$ARGUMENTS`.
2. Implement tasks in order.
3. Run validation commands.
4. Report:
   - files changed
   - commands run
   - validation results
   - rollback note
