# Round roster + queue — acp-killswitch-enduser-process-review-20260926

Design-review of the C6 kill-lever END-USER PROCESS against the owner's beginner-friendly control-surface
principle. Subject: `.agent/PROJECT-APPROVAL-CONTROL-PLANE-PRD.md` (draft) + P-F4.

- **claude** — voted PLAN_READY_WITH_FOLLOWUPS (see claude.md): ACP R2/R3/R4 is the right process; HOLD
  the CLI P-F4 activation; build the smallest slice (WebAuthn-gated epoch-switch signing + minimal approve
  surface, reusing C6c beneath); 3 security conditions (hardware-backed non-exportable key, action-bound
  assertion, fail-closed); confirm authenticator availability with the owner.
- **antigravity** — task dropped to inbox (owner may need to prompt the IDE — nudge-not-drain gap).
- **codex** — QUEUED (advisory). On availability: read PROPOSAL.md + claude.md; confirm/dispute the
  sequencing (hold vs CLI-interim) and the 3 security conditions; independent design lane. Does NOT gate
  (owner: progress without Codex).
- **local** — skipped (read-stagnation loop).

NOTE: created as untracked working-tree files because the shared checkout is on the parallel agent's
branch (feat/sota-agentic-workspace-gui). Persist/PR this round from a clean branch off main (or fold to
the ACP PRD) once the checkout is free — do NOT commit onto the parallel agent's branch.
