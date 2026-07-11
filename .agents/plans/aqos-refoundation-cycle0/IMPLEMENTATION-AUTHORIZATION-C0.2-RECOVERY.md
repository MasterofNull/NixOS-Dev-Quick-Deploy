# Prepared Implementation Authorization — C0.2 Recovery Revision

**Decision:** `implementation_authorized = PENDING_REVIEW`  
**Prepared authorization ID:** `auth-c0.2-recovery-20260711`  
**Prepared idempotency key:** `344bdbf9-797e-4fe7-9196-5c0dc936b26e`  
**Prepared:** 2026-07-11  
**Issuer required for activation:** hyperd (owner)  
**Governing policy:** `OWNER-POLICY-RATIFICATION.md`

## Subject binding

| Subject | Value |
|---|---|
| Amended package root | Bound by inclusion of this immutable prepared record in `PACKAGE-ROOT.json`; the separate activation record must pin the resulting external root |
| Verification | Required exit 0 on the resulting package immediately before activation |
| Recovery governance commit | `42eb76f882f79ee77cee1d02bc2548b140cc1dca` |
| Plan | `CONSOLIDATED-PLAN.md` §C0.2 recovery amendment |
| Surface inventory | `C0.2-SURFACE-INVENTORY.md`, amended 2026-07-11 |
| Recovery evidence | `.agents/archive/c02-recovery-20260711/README.md` |

## Preconditions required before activation

1. Fresh exact-root `APPROVE` from two independent model families and two execution principals.
2. Package verification exit 0 immediately before owner activation.
3. Explicit disposition of the preserved suspended C0.2 implementation diff. It must be reviewed and
   assigned as inherited work, or preserved outside the worktree and the authorized surfaces restored
   clean. No silent reuse.
4. Ownership preflight shows no overlap on every amended inventory surface.
5. `.agents/telemetry` is a real directory, tracked projection bytes match Git, and no repo/deployed
   symlink or bind replacement exists.
6. The previous key `9ec8fd14-dd62-441f-9abe-e551bdd63d0e` remains suspended and unusable.

## Prepared grant

Once activated by a separate owner-signed activation record binding this prepared record's raw
SHA-256, the assigned implementer may modify only the amended
`C0.2-SURFACE-INVENTORY.md` surfaces and the three named focused tests. The implementer must begin
from the preserved baselines, implement producer-first additive compatibility, and address every
Codex pre-review finding before requesting acceptance.

Explicitly forbidden: `.agents/telemetry/**`, deployed telemetry contents, symlinks, bind mounts,
mount/service wiring, new stores/services/brokers, and mutable-latest fallback writes.

- **Prepared expiry:** 2026-07-18, activated only if owner issuance occurs before that date.
- **Use limit:** single-use after activation.
- **Reviewer of implementation:** a family other than the assigned implementer.
- **Automatic suspension:** root drift, ownership conflict, undeclared consumer, redirect attempt,
  mutable fallback, weak consumer verification, lost concurrent evidence, pointer-target GC, required
  UNKNOWN passing, or CLI/dashboard disagreement.

`RECORD: PREPARED_ONLY — this immutable prepared record grants no implementation authority. Fresh
reviews, ownership disposition and a separate explicit owner activation record are required; this
file is never edited in place to become AUTHORIZED.`
