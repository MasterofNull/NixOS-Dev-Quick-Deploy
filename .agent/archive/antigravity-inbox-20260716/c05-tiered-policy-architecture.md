# A2A task for antigravity — round 'c05-tiered-policy-architecture'

Dropped: 2026-07-16T20:59:47Z

Respond by writing `.agents/plans/c05-tiered-policy-architecture/antigravity.md`.

## SCOPE & STOP (HARD — read before writing)
- Edit ONLY the files this task names as surfaces. A related-looking file is still out of scope.
- NEVER implement a data/config change as a filesystem shortcut: no symlink, bind mount, mount,
  chmod/chown/rm on tracked or runtime paths. 'Single source of truth' = a resolver in code,
  never one directory replacing/redirecting another.
- NO DELETE — archive to a timestamped path; never rm/rmdir.
- If this task references an authorization/round: confirm it still reads AUTHORIZED and (where a
  package root is named) that `aq-package-freeze verify` exits 0 BEFORE writing. If suspended,
  STOP — do not recreate or continue suspended files.
- Undeclared dependency discovered -> STOP and report; do not expand scope to 'make it work'.
- Budgets/acceptance criteria are hard facts: a measured violation FAILS; a sentence calling it
  'acceptable' does not change the number. Report the real value.
- Write ONLY your own named output file. Do NOT edit shared files. Do NOT commit.
- When unsure whether something is in scope: it is not. Report, do not act.

COLLABORATIVE ROUND 'c05-tiered-policy-architecture'.
TASK:
Same-baseline expert review: architecture, security, SRE. Review only the exact staged changes in docs/architecture/role-matrix.md, docs/architecture/local-agent-task-eligibility.md, .agent/PROJECT-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md, .agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md, and .agents/plans/agent-connection-reliability/PROGRAM-PLAN.md. Determine whether they correctly enforce flat reasoning collaboration, cheapest eligible bounded implementers, independent flagship review and re-review after edits, orchestrator-only submission, first-class but hardware-aware local coding/logic/embedded modalities, and eval-gated recursive correction propagation. Read-only. Check contradictions, authority escalation, poisoning, monitoring, and implementability. End with exact VERDICT: PASS or REQUEST_REVISION or FAIL — reason.

Write your contribution to YOUR OWN file ONLY: .agents/plans/c05-tiered-policy-architecture/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
