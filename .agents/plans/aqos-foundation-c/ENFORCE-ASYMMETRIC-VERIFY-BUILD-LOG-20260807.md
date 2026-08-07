# enforce-asymmetric-verify — build log (COMPLETE, default-OFF; flip is the final owner act)

Frozen `ENFORCE-ASYMMETRIC-VERIFY-FREEZE-20260807.md` (design rev2 SHA-256 `6a2e5f84…cd5`),
owner-activated (grant `activation.grant enforce-asymmetric-verify-build`, drift-clean).

## Build — DONE (commit `a4c496ec`)
Cheapest-eligible implementer (sonnet, Rule 17), orchestrator-verified against the diff. Two files:
- `ai-stack/switchboard/capability_lease_gate.py`: `_admission_verify` scheme-dispatch (Ed25519 →
  `verify_authoritative` + layered `is_expired`/`epoch_stale`; else byte-identical `cl.verify`), called
  INSIDE the existing try/except in BOTH branches (N2); `_load_lease_signer_keys_json` → parsed dict,
  local fail-closed `{}` sentinel, no exception escape (N1); loaded once per `enforce()`; codex-1 cache +
  codex-3 tripwire untouched.
- NEW `scripts/testing/test-enforce-asymmetric-verify.py`: 40/40 (V1–V11 incl. malformed-expires_at
  no-escape, keys-raise sentinel no-escape, epoch parity + mismatch-denies).

Validation: new 40/40 · regression `test-capability-lease` 54/54 (HMAC byte-parity) · ALA 24/24 · gate
regression `test-capability-lease-gate` 83/83 · tier0 25/25.

## Independent code review — PASS (`code-review-a4c496ec.md`)
Fresh Claude flagship (Codex-substitute, Rule 18), audited the committed bytes, ran both suites live. All
six points confirmed: no cross-verifier leak, no fail-open, downgrade-resistant, N1/N2 correct, regression
byte-identical, genuine tests with false-positive controls. "No defect introduced in the bytes."

## N3 pre-flip dry-run — GREEN (the reviewer's "most important" gate)
Against the LIVE `aq-lease-signing-authority`: minted all 25 first-party Ed25519 leases and ran each
through the FULL first-party admission path — `_admission_verify` (sig+expiry+epoch), lease↔lookup-key
match, AND the codex-3 projection-equality tripwire. **25 ADMIT-clean, 0 would-DENY.** Confirms the
authority's minted security projection byte-equals the switchboard's manifest projection, so flipping
`CAPABILITY_ASYMMETRIC_LEASE=1` will NOT deny first-party tools. N4 parity confirmed (authority + enforce
both resolve epoch 0). `scratchpad/n3-dryrun.py`.

## FLIP — DONE + VALIDATED LIVE (2026-08-07, commit 86ec204e, owner-rebuilt)
`switchboard.nix` Environment: `CAPABILITY_ASYMMETRIC_LEASE=1` + `AQ_LEASE_SIGNING_SOCKET_PATH`
(option-SSOT). Owner rebuilt; switchboard restarted clean (Uvicorn :8085, no fail-closed/signer-unavailable
errors). Rule-15 activation attestation — all 5 dimensions GREEN:
- **integrated**: switchboard `issue_first_party_leases` (flag-on) routes to the authority; `enforce()`
  verifies via `_admission_verify`. Both on the live path.
- **ON**: `systemctl show ai-switchboard` env confirms `CAPABILITY_ASYMMETRIC_LEASE=1`; switchboard proc in
  supplementary group `aq-lease-signing-clients` (gid 972) → reaches the 0660 socket.
- **real-world validated**: switchboard-side `issue_first_party_leases` → **25 leases, all sig_scheme=ed25519,
  25/25 verify_authoritative-accepted**; N3 full-`enforce()`-path dry-run **25/25 ADMIT, 0 deny** on those live
  leases; negatives (forged/expired/stale deny) proven by the 40/40 suite. Private key stays 0400 in the
  confined authority — switchboard (owner uid) never holds it (verify != forge).
- **observable**: dashboard `/stats/capability-enforcement` → `asymmetric_lease: on`, 1 active signer key,
  revision 1, `status: ok`.
- **intervenable**: REVERT = remove the 2 env lines + rebuild → byte-parity HMAC, no lease state lost.

**ALA activation COMPLETE** (Phase 0 key → 1 enable → 1b client-access → 2 flip). The asymmetric lease
spine is fully live: first-party leases are Ed25519-minted by a confined authority and enforce-verified
against a public allowlist; the owner-uid switchboard never holds signing material.

## (Superseded) pre-flip notes — the flip (final, separate OWNER act)
Default-OFF today (scheme-dispatch inert; zero behavior change for existing HMAC leases). To activate
asymmetric first-party enforcement:
1. Edit `nix/modules/services/switchboard.nix` Environment: add `CAPABILITY_ASYMMETRIC_LEASE=1` and
   `AQ_LEASE_SIGNING_SOCKET_PATH=/run/aq-lease-signing-authority/control.sock` (R6 `CAPABILITY_CELL_ADAPTER=1`
   precedent). REVERT: remove both → byte-parity HMAC.
2. **N5**: keep the HMAC SOPS secret (`aq-lease-signing-key`) provisioned — do NOT de-provision at flip
   (the `is_dev` degrade would read-only-outage all tools).
3. `nixos-rebuild switch` (owner).
4. LIVE validation: a real first-party tool admits on its Ed25519 lease; a forged/expired/stale lease
   denies; the switchboard uid still never holds the private key.
