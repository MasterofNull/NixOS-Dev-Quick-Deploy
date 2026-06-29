---
doc_type: skill
id: self-improvement
title: Self-Improvement Slice Workflow
status: active
tags: [self-improvement, harness-evolution, PRD, issues-backlog, aq-report, slice, improvement, roadmap]
description: "How to identify and execute the next highest-priority self-improvement dev slice for the harness autonomously."

---

# Self-Improvement Slice Workflow

## Description

Choose and execute the next highest-value harness improvement from backlog, PRD, plan, QA, report, and roadmap evidence.

## When to Use
When asked to "run a self-improvement slice", "improve the harness", "find the next best thing to work on",
or any variant of autonomous harness improvement. **Do NOT invent work from scratch** — always derive it
from authoritative sources first.

## Usage

Select one evidence-backed slice, update resume/pulse state, implement the smallest root fix, validate with focused checks plus tier0, and commit with notes.

---

## Step 1 — Discover Priority from Authoritative Sources

Check these sources **in order** to identify the next highest-priority improvement:

### A. Open Issues & Backlog (Highest signal)
Use read_file (preferred — no shell metachar issues):
```
read_file('.agent/memory/issues-backlog.md')
```
Or via shell (no metacharacters):
```bash
acat .agent/memory/issues-backlog.md
agrep "OPEN" .agent/memory/issues-backlog.md
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
scripts/ai/aq-report --format json
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

## Step 2 — Select and Announce the Target Slice

After discovery, **select the single highest-priority OPEN item** and announce it in one sentence before executing:

```
Fixing: [P1] <Title> — <one-sentence description of the change>
```

Then proceed immediately to Step 3. Do not present a menu or wait for confirmation.
The operator reviews the commit; they do not pre-approve each step.

---

## Step 3 — Execute the Chosen Slice

Once a slice is selected:

1. **Auto-select and test relevant skills first**:
   ```bash
   scripts/ai/aq-skill-auto "<slice description>" --agent local --json --test
   ```
   Load the returned `reference_skills` before edits. Pass only the skill names to sub-agents.
2. **Write RESUME.json** with `current_objective` = chosen slice title
3. **Append to PULSE.log**: `[ISO] [local-agent] [plan]: <slice-title> — starting`
4. **Scope check**: Note in the commit message if a nixos-rebuild is required to activate the change.
5. **Implement**: Make minimal, targeted changes. One concern per slice.
6. **Validate**:
   ```bash
   python3 -m py_compile <edited_files>
   AQ_QA_SKIP_REPORT_BACKED_CHECKS=1 timeout 90 scripts/ai/aq-qa 0 2>&1 | tail -20
   scripts/governance/tier0-validation-gate.sh --pre-commit
   ```
7. **Seed new bug patterns** if the slice fixed a real bug: `scripts/data/seed-rag-knowledge.py`
8. **Commit autonomously**:
   ```bash
   git add <specific files>
   scripts/governance/tier0-validation-gate.sh --pre-commit
   git commit -m "type(scope): description\n\nCo-Authored-By: AQ <noreply@harness.local>"
   ```
   Then report: what changed, what validation passed, what to review.

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
| Presenting a menu and waiting for selection | Breaks the autonomous execute loop; operator reviews commits |
| Running improvement without checking issues-backlog first | May duplicate work or miss P1 blockers |
| Skipping tier0-validation-gate before commit | Breaks governance contract — gate is mandatory |

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
| `aq-report` | Live system health report |
| `aq-qa 0` | Pass/fail check suite |

---

## Outer Loop Entry Point (aq-loop)

When operating as **orchestrator** or when asked to "run autonomously", prefer `aq-loop` over
executing this SKILL manually. `aq-loop` wraps the entire SKILL workflow with:
- Automatic backlog claim/release (`[OPEN]`→`[IN-PROGRESS]`→`[DONE]` / restored on failure)
- Retry up to 3 iterations if the COMPLETED: signal is not detected
- Auto tool-manifest selection (`self-improvement` = 8 tools, ~2500 fewer tokens than full)
- Durable STATE in `.agent/collaboration/LOOP_STATE.json` (survives compaction)

```bash
aq-loop --list-open                   # see what's actionable
aq-loop --from-backlog --dry-run      # preview grounded prompt for top issue
aq-loop --from-backlog                # execute autonomously (claim→implement→verify→release)
aq-loop --check                       # show active loop state
```

Use this SKILL (manual Steps 1–4) only when:
- Debugging a loop iteration or understanding why it failed
- Called as the implementer sub-agent from inside aq-loop
- The outer loop is unavailable or blocked
