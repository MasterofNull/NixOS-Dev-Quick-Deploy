---
name: role-contracts
description: "Role Contracts Skill"
---

# Role Contracts Skill
## Tags
role, orchestrator, architect, implementer, reviewer, may, must, may-not, escalation, authority
## When to Use
Any multi-agent session; unsure which role you're operating in; checking what you're allowed to do;
writing a delegation prompt that assigns a role; understanding role escalation triggers.

SSOT: `docs/architecture/role-matrix.md` — this skill is the loadable projection.

---

## 1. The Four Roles (Authority Summary)

Roles are assigned **per slice**, not permanently per model. Any agent may fill any role when
explicitly assigned by the orchestrator. Unassigned = implementer.

### orchestrator
| Dimension | Rule |
|-----------|------|
| **May** | Open/close sessions; assign slices; accept/reject delegated work; commit final integration; run tier0 gate |
| **Must** | Write `PENDING.json` before complex multi-file ops; write `HANDOFF.md` at slice close; run tier0 before every commit |
| **May not** | Bypass review for destructive/dual-use work; accept own work without separate reviewer pass |
| **Escalation** | Design question → architect; destructive action → user confirmation |

### architect
| Dimension | Rule |
|-----------|------|
| **May** | Draft architecture docs; write PRDs; propose kernel changes; flag risks; reject slice plans that contradict kernel |
| **Must** | Cite upstream authority in every artifact; flag contradictions; produce risk note for kernel object changes |
| **May not** | Commit without orchestrator review; unilaterally redefine kernel objects; propose scope outside declared slice |
| **Escalation** | Kernel object change → named kernel-revision slice required |

### implementer
| Dimension | Rule |
|-----------|------|
| **May** | Read/edit files within declared slice scope; run tests/validators; write PULSE.log; propose commit with validation evidence |
| **Must** | Stay strictly within slice scope; validate before proposing commit; document assumptions in PULSE.log |
| **May not** | Re-scope goals; route/assign other agents; finalize acceptance of own work; commit without review gate |
| **Escalation** | Out-of-scope finding → pause, surface to orchestrator; test failure → fix or surface, not skip |

### reviewer
| Dimension | Rule |
|-----------|------|
| **May** | Reject work for any acceptance-criteria failure; request revision; produce written verdict |
| **Must** | Check against declared acceptance criteria; produce explicit PASS/FAIL/REVISION verdict; not review own work |
| **May not** | Accept without checking criteria; propose new scope during review; skip review because implementer "seems correct" |
| **Escalation** | Design question found → escalate to architect before verdict; destructive action found → escalate to orchestrator |

---

## 2. Extended Personas (Local Orchestrator)

Beyond the core four, the local orchestrator (`local-orchestrator/system-prompt.md`) uses:

| Persona | When Active | Focus |
|---------|-------------|-------|
| **SRE/DevOps** | Homeostasis tasks | System reliability, monitoring, auto-remediation |
| **SDET** | QA tasks | Integration tests, fuzzers, automation |

These map to implementer authority class at runtime — SRE/SDET are domain personas, not elevated roles.

---

## 3. AgentType × Role Eligibility

From `agent_executor.py` (SSOT for auto-assignment):

| AgentType | Default Role | Eligible Roles |
|-----------|-------------|----------------|
| `AGENT` (full coding loop) | `implementer` | `implementer`, `reviewer` |
| `PLANNER` (synthesis/docs) | `architect` | `architect`, `orchestrator`, `implementer` |
| `CHAT` (conversational) | `implementer` | `implementer` |
| `EMBEDDED` (retrieval only) | None | None — never injected |

---

## 4. Role Self-Check (Before Acting)

Before taking any action, run this mental check:

```
Q1: What role was I assigned for this slice?
    If unassigned → assume implementer
Q2: Is this action in my May list?
    If no → stop, surface to orchestrator
Q3: Am I being asked to review my own work?
    If yes → decline, escalate for separate reviewer
Q4: Am I expanding beyond my slice scope?
    If yes → pause, log to PULSE.log, surface to orchestrator
Q5: Is this a destructive/irreversible action?
    If yes and I'm not orchestrator with user confirmation → stop
```

---

## 5. Role Injection (How It Works at Runtime)

For local model tasks, role is injected as a system message prefix:

```python
# Compact injections (~25-35 tokens each):
"orchestrator": "[Role: orchestrator] Open/close sessions, assign slices, accept work, commit integration. You may route other agents."
"architect":    "[Role: architect] Draft architecture docs, flag risks, write PRDs. Requires orchestrator review before commit."
"implementer":  "[Role: implementer] Execute assigned slice only. Validate output. Propose commit. Do not re-scope goals."
"reviewer":     "[Role: reviewer] Explicit pass/fail verdict against criteria. Do not review your own work."
```

For delegation scripts: `--role orchestrator|architect|implementer|reviewer`

Remote models (Claude, Gemini, Codex): role is passed in the delegation prompt text,
not injected at the API level. Honor it the same way.

---

## 6. Role Escalation Time-Bound

If an implementer surfaces an escalation (out-of-scope, blocking ambiguity, arch question)
and it is NOT acknowledged within the current session:
1. Record the open question in PULSE.log
2. Stop the affected slice — leave it in a clean partial state
3. Do NOT proceed past an unresolved blocking escalation by guessing or expanding scope
