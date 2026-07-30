# A2A task for antigravity — round 'stream-auth-rereview'

Dropped: 2026-07-21T01:47:53Z

Respond by writing `.agents/plans/stream-auth-rereview/antigravity.md`.

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

COLLABORATIVE ROUND 'stream-auth-rereview'.
TASK:
Independent re-review (reviewers only, no code). The prior flagship-review docs for these 3 authorizations cite subject hashes that do NOT match the live files — re-review each against CURRENT on-disk bytes and, CRITICALLY, compute the real SHA-256 yourself and cite it, confirming your verdict binds to that exact current hash. For EACH of the 3, verify it is a sound, implementable, fail-closed contract (bounded file ceiling, clear constraints, no live-data/network/credential exposure), then give a per-slice verdict. Subjects (compute each hash live): (1) .agents/plans/aqos-foundation-b3/B3-C1-CANON-COMPILER-AUTHORIZATION.md [should be d6676252dc30061d58d9a2f8d5339cc2fc828b59eb3f41a6abc2552b746621ad — confirm]; (2) .agents/plans/verified-factory/VF-7-EVIDENCE-PATH-AUTHORIZATION.md [should be 71c5df38e736c48d86371c9aff294299e1c1dd0896adb80e4186b762547a1741 — confirm]; (3) .agents/plans/local-inference-l2b-b/L2B-B-IMPLEMENTATION-AUTHORIZATION.md [should be b9055bb6a763189fd0b5fbc054ead4fc6a41d41ed117181039f0ce67d62f7cb8 — confirm]. End with three explicit lines: 'B3-C1 VERDICT: PASS|REQUEST_REVISION (hash <computed>)', 'VF-7 VERDICT: ...', 'L2B-B VERDICT: ...'.

Write your contribution to YOUR OWN file ONLY: .agents/plans/stream-auth-rereview/<AGENT>.md (<AGENT> = codex | local | antigravity). Do NOT edit any shared file. Do NOT read the artifact file (it is inlined above). Be decisive and concise.
