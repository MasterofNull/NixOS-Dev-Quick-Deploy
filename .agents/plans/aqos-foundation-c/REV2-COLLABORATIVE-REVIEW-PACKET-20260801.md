# Foundation C Revision 2 — Collaborative Review Packet

Status: `REVIEW_REQUEST — NO IMPLEMENTATION AUTHORITY`  
Prepared: 2026-08-01 UTC  
Observed HEAD: `17f899bf838973c755ab7a3e6095ec04a2e74220`

## Exact subjects

| Subject | Exact SHA-256 |
|---|---|
| `RUNNER-DEPLOYMENT-HARDENING.md` | `48cae30d1c93ff9e76fdff0e3866f885b54e544de95c978c8286a1c8065f0c63` |
| `RUNNER-DEPLOYMENT-HARDENING-FREEZE.md` | `4b5f9b4b4da272da7411f95cf2e6aeed1ac0783412dc434f66ce2748b8c2093f` |
| `C6-DESIGN-AND-AUTHORIZATION.md` | `927374039c17abe0103a262b24346d61afc6dc38e7fe6396f74812c17203703c` |
| `C4-DESIGN-AND-AUTHORIZATION.md` | `f535731e7fe1ad48c5c70d1f8ccc275ef9b61c731d35a265f876961ea5f14d5a` |
| `C3A-2-DESIGN-AND-AUTHORIZATION.md` | `7792e8537ac48c95837e2aedfec6794120a0550f1d274c0a76f29cab36c6a290` |

Read the four binding `*-CODEX-DEPTH-REVIEW-20260801.md` artifacts and verify
every finding against the revised subject. Review architecture, security/SRE,
concurrency/durability, identity/authority, rollback, privacy, exact inventory,
and the mandatory Service Coverage contract.

For each subject return one of:

- `PASS_DESIGN`: the design closes its prior findings while truthfully retaining
  prerequisites; this does not make it freeze/activation ready;
- `REQUEST_REVISION`: a design defect remains; identify exact section and fix;
- `FAIL`: the direction violates a governing invariant.

Separately state `FREEZE_ELIGIBLE: yes|no` and list every unresolved prerequisite.
Do not convert declared prerequisites into assumptions. In particular, C6's C2
scheduler-context issuer/transport and owner-key/service-hardening sources, C4's
runner/C6/receiver-gateway prerequisites, and C3a-2's runner/C4/C6/R5/principal
prerequisites remain explicit gates unless the repository already proves them.

## Evidence-integrity caveat

Commits `ec6fc69b` and `17f899bf` physically preserved intermediate drafts but
do not supply acceptance. Their commit bodies incorrectly credit zero-output
Claude task `claude-20260801-093407-umfyv7` for work actually completed by Codex
subagents. Do not propagate that attribution and do not credit stale, failed,
parked, or outputless tasks as authors/reviewers.

This is read-only review. Do not edit subjects, stage, commit, activate, deploy,
restart, invoke providers, or run network/live traffic. Write only the lane's
declared review output and include exact reviewed hashes.
