---
round: stage1-owner-key-lever-activation-20260926
type: activation-readiness-consensus
disposition_options: [READY_TO_ACTIVATE, ACTIVATE_WITH_CONDITIONS, NOT_READY]
gate: "This round decides ACTIVATION readiness ONLY. No switch flips from this round. Activation remains the owner's explicit gated act, AFTER consensus + guard-armed confirmation."
roster: "claude (now), antigravity/gemini (now, inbox wake). Codex queued ~14:00 (quota reset) — binding confirmatory vote folds on return; round stays OPEN. local SKIPPED this round (owner-directed 2026-09-26: read-stagnation failure loop; see issues-backlog LOCAL-LANE)."
---

# Stage 1 activation-readiness consensus — owner-key kill-lever (P-F4)

## The proposal (what would be turned on)
Activate the **owner-signed epoch-bump kill-lever** — the fleet-wide intervention that voids
capability leases on an owner-authorized epoch bump. Concretely, the activation ceremony is:

1. **Enable the authority service** — `mySystem.aiStack.revocationEpochAuthority.enable = true`
   (currently default-OFF/inert, `nix/modules/services/revocation-epoch-authority.nix:37,81`). NixOS
   module change → requires a `nixos-rebuild switch` (owner terminal).
2. **Owner OFFLINE Ed25519 keygen** — private key generated off-host, NEVER on the host, never in SOPS
   (`C6-ACTIVATION-20260815.md:16-19`). Only the PUBLIC key comes to the repo.
3. **P-F4 allowlist advance** — `config/aqos/c6-owner-public-keys.json` rev-4 → rev-5, adding the owner's
   real active public key. Current dormant baseline = rev-4, sole key `owner-mechtest-2026-08` REVOKED,
   **zero active signers** (`C6c §… , c6-owner-public-keys.json`). Public-only, monotonic; does not
   mutate frozen code bytes.
4. **Verified bump** — owner signs the canonical bytes offline, delivers via
   `aq-epoch-bump submit --signed <file> --socket <control.sock>` (C6c's landed socket path) → the
   running authority verifies against the rev-5 allowlist under `epoch.lock` and increments the epoch →
   fresh leases stamp the new epoch. This is the operational proof the lever works.

## Confirmed readiness facts (verified on main @ 48045af6, 2026-09-26)
- C6c socket-submit path IS landed: `aq-epoch-bump submit --signed --socket` present; the earlier
  `NameError: missing import os` IS fixed (`import os` at `scripts/ai/aq-epoch-bump:47`).
- Authority handler already accepts `{"bump": <signed doc>}` and a read-only `{"op":"read-epoch"}`
  (reachability probe) — no new authority op needed (`revocation_epoch_transport.py:283-296`).
- `apply_bump` verifies signature + re-checks `status=="active"` on EVERY call (no caching), advances
  epoch +1 under one exclusive lock; replay denied on `(request_id, idempotency_key)`
  (`revocation_epoch.py:432,609-664`).
- Historical proof-of-mechanism: the 08-15 ceremony advanced epoch 0→1 and the live ALA→C2 mint smoke
  PASSED at epoch 1 (system healthy — revoke without breaking the chain) before being rolled back to the
  dormant baseline. So the mechanism has worked end-to-end before, with the earlier key.
- Stage 0 auto-revert safety net is live (timer active, self-test proven the revert fires).

## Guard wiring for THIS control (must be armed before activation)
- **health-check (green = keep):** authority reachable via `{"op":"read-epoch"}` AND a fresh
  capability-lease mint still succeeds stamping the current epoch (chain not broken).
- **revert (fires if health red past the window):** roll the allowlist back rev-5 → rev-4 (re-revoke the
  active key) — a **runtime** action the guard timer CAN perform. NOTE: `enable=true` is a NixOS-module
  state a shell-command revert CANNOT undo; the runtime revert is allowlist-rollback (+ optional
  `systemctl stop aq-revocation-epoch-authority`), and the durable disable is a follow-up rebuild.

## Questions for the cohort to resolve (vote + reasoning on each)
1. **Boundary / stagger depth.** Owner wants the SMALLEST safe stage. Options:
   (1a) split — Stage 1a = authority-enable with ZERO active signers (observable-only, no signer can
   bump = inert but running); Stage 1b = P-F4 keygen + allowlist advance + verified bump. OR
   (1b) single stage — enable + P-F4 + verified-bump together. Which is safer to catch issues early?
2. **Ceremony correctness.** Confirm the activation uses the C6c-sanctioned `submit --signed --socket`
   path (owner private key never on host), NOT the deprecated in-process/`_load_owner_key` host-key path.
3. **Revert adequacy.** Is allowlist-rollback (runtime) + queued rebuild-disable a sufficient revert for
   a Nix-module-enabled control, given the guard timer can't rebuild? Any gap where bad state persists?
4. **C4 independence.** Confirm Stage 1 (P-F4 / C6c own activation) does NOT depend on the C4-amendment
   PASS (amendment gates C4 FREEZE, not the owner-key lever). If correct, Stage 1 need not wait on the
   ~14:00 Codex amendment PASS — only on this consensus + guard + owner act.
5. **Residual blockers / observability.** Is the revocation surface on the dashboard live and correct
   (DoD: observable)? Any pre-activation smoke that must pass first?

## Vote format
Each agent appends to its own file `.agents/plans/stage1-owner-key-lever-activation-20260926/<agent>.md`:
disposition (READY_TO_ACTIVATE | ACTIVATE_WITH_CONDITIONS | NOT_READY), then per-question reasoning,
then any conditions/blockers. Reason from the full expert-team baseline (security + systems + reviewer).
