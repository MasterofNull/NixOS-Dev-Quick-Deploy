---
doc_type: skill
id: self-improvement
title: Self-Improvement Slice Workflow
status: active
tags: [self-improvement, harness-evolution, PRD, issues-backlog, aq-report, slice, improvement, roadmap]
description: "How to identify, propose, and execute the next highest-priority self-improvement dev slice for the harness."

---

# Self-Improvement Slice Workflow

## When to Use
When asked to "run a self-improvement slice", "improve the harness", "find the next best thing to work on",
or any variant of autonomous harness improvement. **Do NOT invent work from scratch** — always derive it
from authoritative sources first.

---

## Step 1 — Discover Priority from Authoritative Sources

Check these sources **in order** to identify the next highest-priority improvement:

### A. Open Issues & Backlog (Highest signal)
```bash
# Scan issues backlog for OPEN P1/P2 items
acat memory/issues-backlog.md | head -80
# Or grep for open items
agrep "OPEN\|P1\|P2" memory/issues-backlog.md
```

### B. Active PRD / Plans
```bash
# List open phase plans
als .agents/plans/ | head -20
als .agents/planning/plans/ | head -20

# Check active PRDs
acat .agent/PROJECT-PRD.md | head -60
acat .agent/PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md | head -40
```

### C. Current System Health (aq-report + aq-qa)
```bash
# Quick health snapshot (skip slow checks)
AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 90 scripts/ai/aq-qa 0 2>&1 | tail -30

# Check for failing checks or degraded services
scripts/ai/aq-report --format json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
# Surface top-level failures
checks = d.get('checks', {})
for k, v in checks.items():
    if isinstance(v, dict) and v.get('status') not in ('pass', 'ok', None):
        print(f'DEGRADED: {k} — {v.get(\"status\",\"?\")} — {v.get(\"message\",\"\")}')
" 2>/dev/null || echo "Use: scripts/ai/aq-report"
```

### D. Roadmaps and System Improvement Plans
```bash
acat docs/development/SYSTEM-UPGRADE-ROADMAP-UPDATES.md | head -80
acat .agents/plans/EFFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md | head -60
```

### E. RESUME.json + HANDOFF.md (In-flight work)
```bash
acat .agent/collaboration/RESUME.json
# Shows: current_objective, phase, todo_snapshot, uncommitted_changes
```

---

## Step 2 — Synthesize: Propose 3 Options to the Operator

After discovery, **never silently pick one and start**. Present a ranked list:

```
Here are the top 3 candidate slices, ranked by priority and impact:

1. [P1 — HIGHEST] <Title>
   Source: issues-backlog line N / PRD section X
   Problem: <what is broken or missing>
   Impact: <what improves if fixed>
   Effort: <estimated complexity, rebuild required? yes/no>

2. [P2] <Title>
   ...

3. [P3] <Title>
   ...

Which slice should I execute? (Or describe a different priority.)
```

Give the operator the choice. Do not proceed to Step 3 until they confirm.

---

## Step 3 — Execute the Chosen Slice

Once a slice is selected:

1. **Check for a relevant skill first**: `aq-skill-suggest "<slice description>"`
2. **Write RESUME.json** with `current_objective` = chosen slice title
3. **Append to PULSE.log**: `[ISO] [local-agent] [plan]: <slice-title> — starting`
4. **Scope check**: Is this a no-rebuild slice or rebuild-required? Confirm with operator if rebuild needed.
5. **Implement**: Make minimal, targeted changes. One concern per slice.
6. **Validate**:
   ```bash
   python3 -m py_compile <edited_files>
   AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 90 scripts/ai/aq-qa 0 2>&1 | tail -20
   scripts/governance/tier0-validation-gate.sh --pre-commit
   ```
7. **Seed new bug patterns** if the slice fixed a real bug: `scripts/data/seed-rag-knowledge.py`
8. **Stage and describe the commit** for operator review (do NOT commit autonomously unless operator authorizes it):
   ```
   Files changed: <list>
   Proposed commit message: feat(<scope>): <description>
   ```

---

## Step 4 — Update State

After execution:
- Update `RESUME.json`: `todo_snapshot` marks the item complete
- Append to `PULSE.log`: `[ISO] [local-agent] [complete]: <slice-title> — <outcome>`
- Record new issue/pattern to `memory/issues-backlog.md` if discovered during the slice

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It Fails |
|---|---|
| Inventing work from scratch | Misses actual system priorities; wastes operator time |
| Picking documentation cleanup as "safe" work | Low impact; doesn't advance system capability |
| Starting implementation before confirming the choice | Operator loses control of priorities |
| Running improvement without checking issues-backlog first | May duplicate work or miss P1 blockers |
| Committing without operator sign-off | Violates harness governance (Rule 1) |

---

## Quick Reference — Key Files to Scan

| File | What it tells you |
|---|---|
| `memory/issues-backlog.md` | Open bugs, P1/P2/P3, root causes |
| `.agent/collaboration/RESUME.json` | In-flight objective and todos |
| `.agent/collaboration/PULSE.log` | What was done recently |
| `.agent/collaboration/HANDOFF.md` | Session-to-session continuity |
| `.agents/plans/*.md` | Active implementation plans |
| `.agent/PROJECT-PRD.md` | Current project priorities |
| `aq-report` | Live system health snapshot |
| `aq-qa 0` | Pass/fail check suite |
