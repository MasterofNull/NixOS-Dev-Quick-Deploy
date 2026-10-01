# A2A task for antigravity — round 'tiered-auto-update-prd-20261001'

Dropped: 2026-10-01T15:42:21Z

Respond by writing `.agents/plans/tiered-auto-update-prd-20261001/antigravity.md`.

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

COLLABORATIVE ROUND 'tiered-auto-update-prd-20261001'.
TASK:
ROLE: architect/PRD reviewer (read-only; do not edit files except your own verdict file). Read .agent/PROJECT-TIERED-AUTO-UPDATE-PRD.md, nix/overlays/fast-lane-manifest.nix, nix/modules/core/fast-lane-staleness-monitor.nix, scripts/maintenance/system-update-full.sh (bounded reads). In <= 40 lines answer the PRD's 4 open questions with a concrete recommendation each (frontier vs core initial package list by attr name; kernel strategy; post-switch health gate + rollback triggers; cadence/quiet-hours/agent-activity guard), list the top failure modes of an unattended rebuild+switch on this host (27 GB RAM, Renoir APU, llama.cpp resident, sops secrets) and the guard for each, and what to cut from MVP. End with VERDICT: PLAN_READY | PLAN_READY_WITH_FOLLOWUPS | NEEDS_DECISION.

Write your contribution to YOUR OWN file ONLY: .agents/plans/tiered-auto-update-prd-20261001/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
