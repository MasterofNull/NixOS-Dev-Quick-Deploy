# A2A task for antigravity — round 'unified-program'

Dropped: 2026-07-13T17:49:47Z

Respond by writing `.agents/plans/unified-program/antigravity.md`.

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

COLLABORATIVE ROUND 'unified-program'.
Review artifact: .agents/plans/unified-program (read it).
TASK:
Independent ratification review of the AQ-OS unified program package at commit aa2e4452. SUBJECTS: (1) .agents/plans/UNIFIED-PROGRAM-PLAN.md — consolidation of all four AQ-OS corpora + L-series + Track V into one spine (precedence, state ledger, traceability, loose threads, owner decisions Q1-Q9); (2) .agent/PROJECT-VERIFIED-FACTORY-PRD.md — Track V, 9 slices VF-1..VF-9; (3) .agent/PROJECT-CHECK-KERNEL-PRD.md — CheckSpec SSOT + aq check runner + section-6 amendments to the Antigravity ARE plan; (4) .agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md as parent architecture (owner decision Q1). PRODUCE in your own file: per-subject score 1-10 with specific defects (file+section refs); APPROVE/REVISE per owner decision Q1-Q9 (plan section 6); answers to CK PRD section 9 questions (interim runner: focused-CI vs minimal aq check; ratchet unit: directory vs module; biome vs eslint); VF PRD section 3 disposition challenges; slices your lane claims per lane eligibility. END with explicit verdict APPROVE / REQUEST_REVISION / BLOCKED per subject plus overall. RULES: do not read other lanes' files; claude-fable-5 authored subjects 1-3 and abstains from scoring its own artifacts; evidence over assertion — cite file:line where you contest; codex lane is offline until 2026-07-15 and the round stays OPEN for its late fold-in. Load skills: multi-agent-collab, context-efficiency, system-dev.

Write your contribution to YOUR OWN file ONLY: .agents/plans/unified-program/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
