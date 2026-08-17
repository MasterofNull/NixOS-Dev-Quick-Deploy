---
doc_type: plan
id: acp-p1b-build-20260817
title: ACP-P1b build record — lost-authenticator recovery core
status: complete
parent_prd: approval-control-plane
slice: acp-p1b
date: 2026-08-17
---

# ACP-P1b build record — lost-authenticator recovery core

The Python core of the multi-authenticator allowlist + console-gated declarative recovery bootstrap,
built to `ACP-P1b-DESIGN-20260816.md`, consuming the "P1b enrollment copy" / "P1b recovery copy" verbatim
from `ACP-PREP-COPY-20260816.md`. Implemented by the Claude sonnet lane (Rule 17, cheapest-eligible
implementer). No live activation — CORE only, same posture as P1.

## Files
- `scripts/ai/lib/approval_recovery.py` — `AllowlistManager` (enroll / set_status / remove /
  bootstrap_recovery), `require_console_root` (EUID-0 + un-forgeable presence-token gate, real NixOS
  activation-script/console wiring documented in its docstring, not built), `RecoveryAllowlistStore`
  (atomic read/write, same fsync-before-return idiom as `approval_signer.PendingChallengeStore`),
  `AuditLog` (append-only JSONL mutation trail), `ENROLLMENT_COPY`/`RECOVERY_COPY` (verbatim prep-copy
  constants for P2 to render). Zero edits to `approval_signer.py` — read-only reuse of its
  `CREDENTIAL_ALLOWLIST_SCHEMA_VERSION`/`CREDENTIAL_STATUS_ACTIVE`/`CREDENTIAL_STATUS_VALUES`/
  `load_credential_allowlist` for guaranteed on-disk compatibility. Credential entries persisted in P1's
  exact 4-key shape (`credential_id`/`public_key`/`sign_count`/`status`); `label`/`kind`/`enrolled_at`
  bookkeeping lives in a sibling top-level `recovery_metadata` map P1's loader simply ignores (verified,
  not assumed — the loader only requires `schema_version` + an exact-4-key `credentials` list, no
  top-level key restriction).
- `scripts/testing/test-approval-recovery.py` — 9 checks, dual-mode (main + pytest). `test_backup_works`
  and `test_lose_one_safe` go past the allowlist level: they run a REAL `approval_signer.ApprovalSigner`
  (real `python-fido2` verification) against a credential enrolled through `AllowlistManager`, proving the
  P1b-managed file is genuinely P1-consumable, not just structurally plausible.

## Validation (self-reported, real output below)
- `python3 scripts/testing/test-approval-recovery.py` → `PASS: 9 approval-recovery P1b checks`.
- `pytest scripts/testing/test-approval-recovery.py` → `9 passed`.
- Regression: `python3 scripts/testing/test-approval-signer.py` → still `PASS: 20 approval-signer P1
  checks` (P1 untouched); `pytest` → `20 passed`.
- tier0 `--pre-commit`: cross-surface docs/dashboard contract flagged the new
  `scripts/ai/lib/approval_recovery.py` runtime file with no connected doc — this record satisfies that
  contract (same pattern as `ACP-P1-BUILD-20260816.md` for P1).

## Design goals covered
- **backup-works** — a backup credential's assertion is accepted by the real P1 signer identically to a
  primary's (allowlist-level + end-to-end).
- **lose-one-safe** — revoking the primary via `set_status` leaves an active backup fully functional; the
  revoked primary is correctly rejected if reused.
- **console-only-recovery** — `bootstrap_recovery` refuses a non-root (simulated UDS-agent) caller, refuses
  root-with-wrong-token, refuses root-with-unconfigured-expected-token (fail CLOSED, not open), and
  succeeds only for a genuine root+matching-token (console-root-simulated) caller.
- **no-empty-allowlist** — `set_status`/`remove` both refuse any mutation that would leave zero ACTIVE
  credentials, unless a replacement is enrolled atomically in the same call; the invariant re-verified to
  hold after a replacement lands (not just at t=0).
- **audited** — every enroll/status-change/remove/recovery-bootstrap appends a durable JSONL event
  (`credential_id`/`actor`/`at` + mutation-specific fields); a refused mutation never appends an event;
  recovery gets its own distinct `recovery_bootstrap_enrolled` event type; durability re-checked through a
  fresh `AuditLog` reader instance.
- **no-stored-secret** — static source scan for recovery-code/break-glass/SMS-or-email-reset constructs
  (absent), a suspicious-name scan across the module's and `AllowlistManager`'s public surface (none), and
  a structural check that `MutationVerdict` (the return type of every mutation, including recovery) has no
  signature/secret-shaped field.

## Scope fence honored
No Nix/systemd unit, no live UDS/console wiring, no real crypto beyond public-key bytes (never touches
owner private-key material or a `.sign()` call anywhere), no UI, no CLI, no edits to `approval_signer.py`/
`approval_request.py`/`approval_executor.py`/`approval_runbook_engine.py`/`dashboard/`.

## Activation status (Activation Gate)
- **Integrated:** library present + unit-validated. **NOT turned ON** — CORE only; the confined service
  wiring, real console-presence-token minting (documented in `require_console_root`'s docstring), and live
  credential provisioning are the deployment layer (a separate owner-activated, default-OFF step), same
  posture as P1.
- **Deferral (dated 2026-08-17):** no running service, no console/UDS wiring, no key material. P1b is
  *built + validated*, **paused pending activation** — tracked for the deployment slice alongside P1.

## Catch-up
Codex confirmatory audit queued per Rule 18 (agent-agnostic roles + catch-up queue); confirms on return.
