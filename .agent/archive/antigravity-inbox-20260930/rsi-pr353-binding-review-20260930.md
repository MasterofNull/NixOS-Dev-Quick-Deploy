# A2A task for antigravity — round 'rsi-pr353-binding-review-20260930'

Dropped: 2026-09-30T21:52:12Z

Respond by writing `.agents/plans/rsi-pr353-binding-review-20260930/antigravity.md`.

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

COLLABORATIVE ROUND 'rsi-pr353-binding-review-20260930'.
TASK:
ROLE: independent reviewer (you did NOT author these commits). Read-only: do not edit files, commit, or run services.
SUBJECT: branch chore/commit-backlog-20260930 (PR #353). Review ONLY these commits:
- 0c0ff4d7 fix(report): aq-report useful_token_metrics streams agent-run-events.jsonl (PRSI 256M OOM)
- 923e9c75 feat(rsi): rsi_lifecycle ledger + scripts/security/rsi-intake-code-scanning.py (Trivy alerts -> RSI incidents)
- 7a1cf7a9 + a7f39858 fix(rsi): prsi-orchestrator cmd_rsi_dispatch skip-reason copy-back, aq-rsi-pending, aq-resume banner, dispatch unit PATH (bash, util-linux, curl, /run/current-system/sw for cliPython)
- e1e4fd69 fix(rsi): dispatch unit ReadWritePaths (+.agent/collaboration, issues-backlog.md, WORKAROUND-REGISTER.md), --timeout-seconds 2400 / TimeoutSec 2460, MemoryHigh 768M / MemoryMax 1G
Use: git show <sha>. Key files: scripts/automation/prsi-orchestrator.py (cmd_rsi_dispatch), scripts/security/rsi-intake-code-scanning.py, nix/modules/roles/ai-stack.nix (ai-prsi-rsi-dispatch), scripts/ai/aq-rsi-pending.
QUESTIONS: (1) correctness regressions; (2) does widening ReadWritePaths or MemoryMax weaken the sandbox beyond need; (3) is an owner verifier sign-off still required for every high-risk RSI row (no gate bypass); (4) prior local finding: intake identity includes fixed_version, so a raised fix version opens a duplicate incident — agree/disagree and fix.
OUTPUT: first line `VERDICT: PASS` or `VERDICT: REQUEST_CHANGES`, then at most 6 numbered findings with file:line and severity.

Write your contribution to YOUR OWN file ONLY: .agents/plans/rsi-pr353-binding-review-20260930/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
