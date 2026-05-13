<!--
Skill: plan-feature
Role: architect
Inputs: feature or slice description
Outputs: plan file in .agents/plans/
Example: /plan-feature "add dark mode support"
-->
---
description: Build implementation plan for a feature/slice
argument-hint: [feature-or-slice]
---

# Plan Feature

Create a plan file in `.agents/plans/` with:
- objective, problem, solution
- context files/docs to read first
- step-by-step tasks
- validation commands
- evidence requirements
- rollback notes
