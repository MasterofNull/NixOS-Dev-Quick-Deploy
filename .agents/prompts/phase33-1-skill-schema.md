You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy.
Follow AGENTS.md and WORKFLOW-CANON.md.

## Task: Phase 33.1 — Skill I/O Schema Standardization

Add a standardized header block to every skill file in `.claude/commands/`.

### Step 1 — Read all skill files
List and read every .md file in `.claude/commands/`.

### Step 2 — Add schema header to each file
Each file must have this block at the TOP (before any existing content):

```
<!--
Skill: <filename without .md>
Role: <orchestrator|architect|implementer|reviewer — pick the best fit>
Inputs: <what the caller must provide, one line>
Outputs: <what this skill produces, one line>
Example: /<skill-name> "brief example invocation"
-->
```

Rules for picking Role:
- orchestrator: high-level planning, session start, routing decisions (prime, primer, explore-harness)
- architect: design, PRD creation, feature planning (create-prd, plan-feature, brownfield, project-init)
- implementer: writes/edits code, executes plans (execute, commit, impeccable, trading-analysis)
- reviewer: quality checks, audits (no current skills — skip)

### Step 3 — Validate
```bash
for f in .claude/commands/*.md; do
  grep -q "Skill:" "$f" && echo "OK: $f" || echo "MISSING: $f"
done
```

### Step 4 — Commit
```bash
git add .claude/commands/
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "feat(skills): Phase 33.1 — add I/O schema headers to all skill files

Standardize skill catalog with Role/Inputs/Outputs/Example headers.
Enables harness to route, log, and arbitrate by role.
Part of tokenmaxxing standardization (Phase 33).

Co-Authored-By: Gemini Code Assist <noreply@google.com>"
```

Working directory: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
