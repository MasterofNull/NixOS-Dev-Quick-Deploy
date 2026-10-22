---
name: slice-authoring
description: "Slice Authoring Skill"
---

# Slice Authoring Skill
## Tags
slice, delegation, context, prompt, handoff, acceptance-criteria, scope, sub-agent, implementer, token_budget, check_command, turn_cap
## When to Use
Writing a delegation prompt for Gemini/Codex/Local; structuring a sub-agent task; defining
acceptance criteria; determining what context to include vs exclude; assigning a role to a delegatee.

---

## 1. Minimal Viable Slice Context

A well-formed slice prompt contains exactly this — no more, no less:

```yaml
slice_objective: <1-2 sentences — what to build, not how>
role: implementer  # or reviewer, architect
phase: Phase 86

# Frontier Parity (W4-S2): Mandatory execution controls & checks-over-plans
check_command: python3 scripts/testing/test-feature.py
token_budget: 15000
turn_cap: 8

relevant_files:
  - scripts/ai/lib/attention_queue.py   # paths only — agent reads them
  - dashboard/backend/api/routes/aistack.py

acceptance_criteria:
  - GET /api/aistack/alerts/status returns 200 with {"queue_depth": N, "pending": [...]}
  - aq-qa 0 passes (77/77) after change
  - No new AppArmor denials in journalctl -u apparmor.service

constraints:
  - Port from options.nix only — never hardcode 8889
  - NoNewPrivileges=true on this service — use ix not Ux for AppArmor subprocess rules
  - Async handlers only — no blocking I/O in FastAPI routes

reference_skills:
  - testing-patterns   # for http_get tuple, QA check authoring
  - coordinator-api    # if touching coordinator routes

resume_checkpoint: .agent/collaboration/RESUME.json
```

---

## 2. Mandatory Verification & Cap Fields (W4-S2)

Every slice brief MUST declare:
1. `check_command`: A single runnable verification command that asserts end-state correctness without relying on unvalidated plans.
2. `token_budget`: The upper ceiling of tokens allocated for this slice to prevent runaway context.
3. `turn_cap`: The maximum allowed agent conversation turns before halting and reporting back to the orchestrator.

A slice brief missing any of these three fields is invalid and will be rejected by `test-slice-authoring-lint.py`.

---

## 3. What to Include vs Exclude

| Include | Exclude |
|---------|---------|
| File paths (not content) | Full HANDOFF.md (link to it) |
| Acceptance criteria as explicit conditions | Previous agent outputs |
| 1-2 constraints most likely to bite | Full AGENTS.md |
| Skill names (not skill content) | Unrelated file contents |
| RESUME.json path for recovery | Full session history |
| Known gotchas specific to this slice | General system orientation |

**Why**: A sub-agent receiving 6000 tokens of context will spend its budget parsing noise.
A sub-agent receiving 500 tokens of signal will deliver better output.

---

## 4. Acceptance Criteria Format

Good acceptance criteria are binary — pass or fail, no ambiguity:

```
# GOOD:
- GET /api/route returns 200 with field "status" == "ok"
- aq-qa 0 passes (77/77 checks)
- File X contains pattern Y (verifiable with grep_search)
- No Python syntax errors (py_compile passes)

# BAD:
- "The code should work correctly"
- "The dashboard looks good"
- "Performance is acceptable"
- "Handle edge cases"
```

For Gemini (no shell): use file-verifiable criteria only:
```
- acceptance_criteria:
  - The file scripts/ai/aq-alerts contains a function named format_alert_line
  - The file imports attention_queue from scripts/ai/lib/attention_queue.py
  - No obvious syntax errors visible in the Python code
```

---

## 5. Role Assignment in Delegation Prompt

```bash
# In delegate-to-gemini:
scripts/ai/delegate-to-gemini --role implementer --prompt-file /tmp/slice.txt

# In delegate-to-local:
scripts/ai/delegate-to-local --mode agent --role implementer --prompt-file /tmp/slice.txt

# In Codex:
scripts/ai/delegate-to-codex --prompt-file /tmp/slice.txt
# (include "Your role: implementer" in the prompt text)
```

Role assignment in the prompt also sets the context tone:
- `implementer`: tell it exactly what to build, where, and what done looks like
- `reviewer`: give it the implementation + acceptance criteria; ask for explicit verdict
- `architect`: give it the problem space; ask for design + risk analysis

---

## 6. Slice Boundaries (Scope Control)

Before writing the slice prompt, declare the scope boundary explicitly:

```
scope_boundary:
  in_scope:
    - dashboard/backend/api/routes/aistack.py  (add 1 route)
    - scripts/testing/harness_qa/phases/phase86.py  (add check)
  out_of_scope:
    - Any changes to ai-stack/ services
    - NixOS module changes
    - Other dashboard routes
```

This prevents the implementer from "helpful" scope creep that breaks other things.

---

## 7. Token Budget by Agent

| Agent | Prompt budget | File reading budget | Output budget |
|-------|--------------|---------------------|---------------|
| Claude | ~4000 | Unlimited | Unlimited |
| Gemini | <2000 (routing 429 above this) | auto_edit reads on demand | ~1400 |
| Codex | Any (use --prompt-file) | reads on demand | Any |
| Local (direct) | <512 for best results | None — direct mode has no tool access | 180 (coordinator ceiling) |
| Local (agent) | <3500 | reads on demand | 512 |

**For Gemini**: if the slice prompt + context exceeds ~1500 tokens, split into 2 slices.

---

## 8. VERDICT Request (for Reviewer Slices)

When assigning reviewer role, always request an explicit verdict at the end:

```
After reviewing, output your final verdict as the LAST LINE in this exact format:
VERDICT: PASS|FAIL|REQUEST_REVISION — <one-line reason>

If REQUEST_REVISION: list specific changes needed with file:line references.
```

The orchestrator maps review input to `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`,
`ACTIVATION_BLOCKED`, or `REJECTED`; findings create a distinct next-slice descriptor, never an
automatic same-slice re-delegation. Planning freezes as `PLAN_READY`,
`PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`.

Terminal disposition SSOT: planning `PLAN_READY`, `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, `PLAN_REJECTED`; implementation `ACCEPTED`, `IMPLEMENTED_FOLLOWUP_REQUIRED`, `ACTIVATION_BLOCKED`, `REJECTED`. Frozen criteria are stable except critical defects. Safe inert-at-rest bytes may commit with `ACTIVATION_BLOCKED` but cannot activate; unsafe-at-rest bytes are `REJECTED`.
