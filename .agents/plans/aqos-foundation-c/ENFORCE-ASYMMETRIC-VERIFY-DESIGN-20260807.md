---
title: "Foundation C — enforce() asymmetric first-party verify (the CAPABILITY_ASYMMETRIC_LEASE flag-flip blocker)"
slice: "ALA-ENFORCE (ALA activation Phase 2 prerequisite)"
revision: 1
kind: "design-only (PREPARED_ONLY; DEFAULT-OFF; authorizes nothing)"
date: "2026-08-07"
author: "Claude Opus 4.8 (analysis)"
opens: "the enforce-side verifier that must exist before CAPABILITY_ASYMMETRIC_LEASE=1 can flip without a switchboard outage"
depends_on: "ALA rev4 BUILT + MINTER ACTIVATED (verify_authoritative + config/aqos/lease-signer-keys.json; confined authority live, canary-green 25/25)"
distinct_from: "C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806 (that issues C6 scheduler-context tokens; THIS makes enforce() admit Ed25519 first-party leases)"
unblocks: "ALA Phase 2 — flip CAPABILITY_ASYMMETRIC_LEASE=1 + live enforced-admission validation"
---

# enforce() asymmetric first-party verify

## 0. Why this slice exists (the blocker, precisely)

ALA activation flipped the MINT side only: with `CAPABILITY_ASYMMETRIC_LEASE=1`,
`issue_first_party_leases` returns Ed25519 leases minted by the confined authority
(`capability_lease_gate.py:395-403`). But the VERIFY side is untouched: `enforce()` verifies every
first-party lease with `cl.verify(lease, key, current_epoch=...)` — the symmetric HMAC verifier — at
`capability_lease_gate.py:690` (and candidate leases at `:645`). `verify_authoritative` has NO caller in
the switchboard. Because `CAPABILITY_LEASE_ENFORCEMENT=1` is already LIVE, flipping the asymmetric flag
today would mint Ed25519 leases (signature in the `signature` field, `sig_scheme="ed25519"`) that the
HMAC verifier rejects (`bad-signature`) → EVERY first-party built-in (`run_command`/`file_edit`/
`write_file`/…) denied → hard switchboard outage. This slice adds the missing enforce-side asymmetric
verifier so the flag can flip safely. Design-only, default-OFF, authorizes nothing.

## 1. Anchored baseline (verify at freeze; drift ⇒ re-freeze)

| Operation | Path | Role |
|---|---|---|
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` (`enforce()`, first-party branch ~:678-698; candidate branch ~:641-653) | Scheme-dispatch the lease verifier: an Ed25519-signed lease (`sig_scheme=="ed25519"`) verifies via `verify_authoritative` + layered expiry/epoch; a legacy (no `sig_scheme`) lease keeps the byte-identical `cl.verify()` HMAC path. |
| NO EDIT | `scripts/ai/lib/capability_lease.py` | `verify_authoritative` + `cl.verify` consumed as-is (ALA rev4 already built + code-reviewed). |
| NO EDIT | `nix/modules/services/switchboard.nix` | Byte-parity anchor — this is a code-level change in the gate; the flag flip is a separate later edit. |
| NEW | `scripts/testing/test-enforce-asymmetric-verify.py` | Offline admission vectors (below). |

## 2. The verifier change (exact semantics)

Introduce a single admission helper used by BOTH the candidate and first-party branches, replacing the
bare `cl.verify(lease, key, current_epoch=...)` call:

```
def _admission_verify(lease, hmac_key, current_epoch, keys_json_dict) -> str:  # returns cl.VERIFY_OK or a deny reason
    if lease.get("sig_scheme") == cl.SIG_SCHEME_ED25519:
        v = cl.verify_authoritative(lease, keys_json_dict)         # signature + active-key ONLY (OBLIG-1)
        if not v.ok:
            return f"auth-{v.reason}"                              # e.g. auth-bad-signature, auth-unknown-key-id
        # OBLIG-1: verify_authoritative does NOT check validity. Layer it here, same source as HMAC path:
        if cl.is_expired(lease):            return cl.VERIFY_EXPIRED
        if cl.epoch_stale(lease, current_epoch): return cl.VERIFY_EPOCH_STALE
        return cl.VERIFY_OK
    return cl.verify(lease, hmac_key, current_epoch=current_epoch) # legacy HMAC path — byte-identical
```

Key properties for the reviewer to confirm:
- **Scheme-pinned, no downgrade:** the branch is driven by the lease's OWN signed `sig_scheme`. An
  Ed25519 lease can NEVER fall through to the HMAC path (and vice-versa). `verify_authoritative` itself
  is scheme-pinned (denies non-ed25519 before any key lookup), so a forged `sig_scheme` can't cross over.
- **OBLIG-1 layering is MANDATORY and co-located:** `verify_authoritative` returns "authentically signed
  by an active key," NOT "currently valid." Expiry + epoch are re-checked here using the SAME
  `current_epoch` (`resolve_current_epoch()`) and the SAME `is_expired`/`epoch_stale` helpers the HMAC
  path uses — so an ed25519 lease and an HMAC lease with identical temporals get identical validity
  verdicts. Absent this, a stale/expired Ed25519 lease would admit (fail-open).
- **Deny-closed + typed:** any `verify_authoritative` failure maps to a typed `auth-<reason>` deny that
  flows into the existing `_decision(..., reason=f"first-party-lease-{verdict}")` record — observable,
  never an exception, never an admit.
- **codex-1 / codex-3 preserved:** the mint-once `_FIRST_PARTY_LEASE_CACHE` (reset-only reissue) is
  untouched; the codex-3 tamper/drift tripwire that re-reads the signed lease's own fields
  (`:699+`) still runs AFTER a VERIFY_OK, now on an authentically-signed lease.

## 3. Open questions for the independent reviewer

- Q-E1 (candidate-lease scheme): first-party leases are the only ones ALA mints as Ed25519. Candidate
  (caller-presented, third-party) leases at `:641` remain HMAC today. Confirm the scheme-dispatch helper
  applied to the candidate branch is correct (an Ed25519 candidate lease, if ever presented, verifies via
  the SAME authoritative allowlist — NOT forgeable — which is strictly safe), OR whether candidate leases
  must stay HMAC-only pending a separate third-party-lease design. Recommendation: apply the helper to
  both (uniform, and the allowlist makes it deny-closed), but flag for the reviewer.
- Q-E2 (epoch source): the layered epoch check uses `resolve_current_epoch()` — the epoch file today
  (`config/capability-lease-epoch` = 0), the C6 epoch authority once activated. Confirm a mismatch denies
  and that this is the SAME source the mint side stamps (`revocation_epoch`), so freshly-minted leases are
  never self-stale.
- Q-E3 (keys_json load site + failure): where `enforce()` loads `config/aqos/lease-signer-keys.json`
  (once per enforce call vs cached) and that a missing/malformed allowlist denies ALL ed25519 leases
  (fail-closed) without affecting the HMAC path. `verify_authoritative` already deny-alls on a non-dict
  keys_json; confirm the load passes a parsed dict (the live-probe bug — a raw string denies-all).
- Q-E4 (flag interaction): with the scheme-dispatch driven by the lease's own `sig_scheme`, is the
  `CAPABILITY_ASYMMETRIC_LEASE` flag still needed at the verify site, or is it purely a mint-side switch
  (verify auto-adapts per-lease)? Recommendation: verify is flag-agnostic (per-lease scheme dispatch);
  the flag stays mint-side only. Confirm this can't create a window where mint=HMAC but a stale cached
  ed25519 lease is verified (cache reset on flag change is an owner act at rebuild).

## 4. Test vectors (offline, hermetic)

1. Ed25519 first-party lease (authority-minted, current epoch, unexpired) → ADMIT.
2. Ed25519 lease, `expires_at` in the past → DENY `first-party-lease-expired`.
3. Ed25519 lease, `revocation_epoch` < current → DENY `first-party-lease-epoch-stale`.
4. Ed25519 lease, signature byte-flipped → DENY `first-party-lease-auth-bad-signature`.
5. Ed25519 lease, `key_id` not in allowlist / `status:revoked` → DENY `auth-unknown-key-id` / `auth-key-not-active`.
6. Legacy HMAC first-party lease (no `sig_scheme`) → ADMIT via the byte-identical HMAC path (parity).
7. Malformed/missing `lease-signer-keys.json` → ALL ed25519 leases DENY; HMAC leases UNAFFECTED.
8. Flag-OFF / sig_scheme-absent corpus → enforce() decisions byte-identical to pre-change (regression).

## 5. Path

Independent binding review of these exact semantics → hash-bound freeze → single-use owner build
activation → default-OFF build (scheme-dispatch is inert until an Ed25519 lease appears, i.e. until the
mint flag flips) → independent code review → commit. THEN ALA Phase 2: flip
`CAPABILITY_ASYMMETRIC_LEASE=1` + `AQ_LEASE_SIGNING_SOCKET_PATH` in switchboard.nix + rebuild + a LIVE
enforced-admission validation (a real first-party tool admits on an Ed25519 lease; forged/expired deny).

`RECORD: PREPARED_ONLY enforce-asymmetric-verify design. No implementation, key material, flag flip, or
activation authority.`
