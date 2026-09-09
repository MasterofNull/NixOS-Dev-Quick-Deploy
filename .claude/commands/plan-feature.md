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

**First (mandatory) — pull frontier context:** run
`scripts/ai/aq-frontier context "<the feature/slice subject>"`. Fold the assessed
techniques + our verdicts into the plan's context, and turn any STALE/GAP concept it
flags into an explicit research task/slice (run the recommended targeted scan on need).
This is how frontier research enters every plan by default — no re-prompting.

Create a plan file in `.agents/plans/` with:
- objective, problem, solution
- **frontier context** (the `aq-frontier context` block: prior art + our verdicts + any gap→research slice)
- context files/docs to read first
- step-by-step tasks
- validation commands
- evidence requirements
- rollback notes
