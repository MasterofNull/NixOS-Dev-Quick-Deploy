<!--
Skill: create-prd
Role: architect
Inputs: project objective, constraints
Outputs: PRD file (default .agent/PROJECT-PRD.md)
Example: /create-prd "A NixOS deployment dashboard"
-->
---
description: Create or refresh PRD for this project
argument-hint: [output-path]
---

# Create PRD

**First (mandatory) — pull frontier prior-art:** run
`scripts/ai/aq-frontier context "<the PRD subject>"` and fold the result into the PRD.
It surfaces the frontier techniques we've already assessed for this subject WITH OUR
verdicts/corrections (so the PRD doesn't re-chase what we measured and dropped, e.g.
speculative decoding, or corrected, e.g. BitNet-30B), and flags any STALE/GAP concept.
If it recommends a refresh, run the suggested targeted scan (or open a research task in
the PRD) before finalizing.

Write PRD to `$ARGUMENTS` (default `.agent/PROJECT-PRD.md`) using:
1. Executive Summary
2. Mission
3. Scope (in/out)
4. Constraints
5. Architecture
6. Security and config
7. Implementation phases
8. Validation and success criteria
9. Risks and mitigations
10. **Frontier prior-art** — the `aq-frontier context` block: relevant assessed
    techniques + our verdicts, and any coverage gap turned into a research task.

Ask clarifying questions if critical information is missing.
