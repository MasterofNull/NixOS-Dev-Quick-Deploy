---
description: Execute implementation from a plan file
argument-hint: [plan-file]
---

# Execute Plan

## Step 0 — Harness Bootstrap (always)
```bash
aq-session-zero 2>/dev/null || echo "HARNESS: unreachable (proceeding locally)"
```

## Step 1 — Pre-Task Hints
```bash
aq-hints "<plan summary from file>" --format=json --agent=codex
```

## Step 2 — Implementation
1. Read plan file from `$ARGUMENTS`.
2. Implement tasks in order.
3. Run validation commands.

## Step 3 — Review & Evidence
Report:
- files changed
- commands run
- validation results
- harness hints consulted (or note if unreachable)
- rollback note
