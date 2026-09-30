# Consensus — Stage 1 owner-key-lever (P-F4) activation readiness

Aggregated 2026-09-26 by claude-opus orchestrator. Owner directed: progress without Codex for now
(Codex binding confirmatory stays queued, advisory on return — Rule 18, never block).

## Verdict: ACTIVATE_WITH_CONDITIONS — 2/2 available independent lanes concur

| Lane | Disposition | Notes |
|------|-------------|-------|
| claude (Opus 4.8) | ACTIVATE_WITH_CONDITIONS | split 1a/1b; allowlist-rollback revert; socket-only ceremony; C4-independent |
| antigravity (Gemini IDE) | ACTIVATE_WITH_CONDITIONS | concurs on all five; independent security+systems reasoning |
| codex | QUEUED (~14:00 reset) | binding confirmatory folds on return; advisory, does not gate |
| local | SKIPPED | owner-directed (read-stagnation loop) |

Both lanes agreed on identical conditions: (1) stage smallest-first; (2) guard armed with runtime
allowlist-rollback revert; (3) ceremony via `submit --signed --socket`, owner key never on host;
(4) pre-activation smoke green; (5) mechtest key stays revoked. C4-independence confirmed by both.

## MATERIAL DISCOVERY during pre-flip smoke (corrects the proposal's staging)
Verified on the live system + main @48045af6:
- **The authority service is ALREADY enabled + running** (`mySystem.aiStack.revocationEpochAuthority.enable
  = true` at `nix/modules/profiles/ai-dev.nix:64`; `systemctl is-active aq-revocation-epoch-authority` =
  `active`; control socket present). It has run since C2-SCI. So **"Stage 1a = enable the service" is
  already the live, weeks-soaked state** — NOT a step still to take. "Dormant" = zero active signers
  (key revoked), not a stopped service.
- **Allowlist baseline confirmed:** `config/aqos/c6-owner-public-keys.json` rev-4, sole key
  `owner-mechtest-2026-08` = revoked, **0 active signers** → lever is `none(revoked-only)`, inert.
- **Owner-keys path is the repo working-tree file** (`AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH=<repo>/config/
  aqos/c6-owner-public-keys.json`), read fresh per request. Confirms the **runtime allowlist-rollback
  revert is feasible** (no rebuild to revert), and that the P-F4 advance is a runtime+commit edit.

## Corrected activation ladder (given the service is already on)
- **~~Stage 1a (service enable)~~ — ALREADY LIVE.** Service-enable + systemd/DAC/confinement legs are
  soaked in production. REMAINING 1a leg to confirm = OBSERVABILITY: the dashboard revocation surface
  actually RENDERS authority state + current epoch live (surface code present in `aistack.py` +
  `dashboard.js`; live render NOT yet re-verified this session).
- **P-F4a (signer-live, NO bump) — the real smallest next step.** Owner OFFLINE Ed25519 keygen → advance
  allowlist rev-4 → rev-5 adding the owner's ACTIVE public key (edit + commit the repo file via PR). A
  signer now CAN bump; none has. No epoch mutation. Reversible: re-revoke (rev-5 → rev-4). Guard armed.
- **P-F4b (verified bump).** Owner signs canonical bytes offline → `aq-epoch-bump submit --signed <file>
  --socket <control.sock>` → epoch +1 → validate leases re-mint at the new epoch (chain intact). First
  real state mutation + operational proof.

## Owner-gated boundary reached
P-F4a is BLOCKED on the owner's OFFLINE keygen — I cannot and must not generate the private key. Next
owner act: generate the Ed25519 keypair off-host, provide ONLY the public key. Then the orchestrator
prepares the allowlist-advance PR (rev-4→rev-5) + the guard-arm runbook + the observability smoke, for
the owner's flip. Nothing activates without the owner's explicit act + guard armed.

## Pre-flip smoke — status
- [x] allowlist rev-4, mechtest revoked, 0 active signers (verified)
- [x] authority service active + socket present (verified)
- [x] revocation surface code present (aistack.py, dashboard.js)
- [ ] dashboard revocation surface RENDERS live authority state + epoch (owner/orchestrator to confirm)
- [ ] `{"op":"read-epoch"}` answers over socket (needs client-group access; not runnable from this shell)
- [ ] fresh capability-lease mint healthy at current epoch (to confirm before P-F4b)
