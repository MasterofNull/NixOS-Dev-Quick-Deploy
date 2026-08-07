---
title: "Foundation C — enforce() asymmetric first-party verify (the CAPABILITY_ASYMMETRIC_LEASE flag-flip blocker)"
slice: "ALA-ENFORCE (ALA activation Phase 2 prerequisite)"
revision: 2
kind: "design-only (PREPARED_ONLY; DEFAULT-OFF; authorizes nothing)"
date: "2026-08-07"
author: "Claude Opus 4.8 (analysis)"
review: "rev1 binding review (fresh Claude flagship, Codex-substitute per Rule 18) = REQUEST_REVISION — crypto core SAFE (no fail-open/downgrade/oracle), but the fail-CLOSED/outage spec was incomplete. rev2 converts Q-E1..Q-E4 into normative requirements N1..N5 and widens activation validation. Advisory concurrence: Antigravity PASS, local Qwen logic-sound."
opens: "the enforce-side verifier that must exist before CAPABILITY_ASYMMETRIC_LEASE=1 can flip without a switchboard outage"
depends_on: "ALA rev4 BUILT + MINTER ACTIVATED (verify_authoritative + config/aqos/lease-signer-keys.json; confined authority live, canary-green 25/25)"
distinct_from: "C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806 (that issues C6 scheduler-context tokens; THIS makes enforce() admit Ed25519 first-party leases)"
unblocks: "ALA Phase 2 — flip CAPABILITY_ASYMMETRIC_LEASE=1 + live enforced-admission validation"
---

# enforce() asymmetric first-party verify

## Revision 2 — normative outage-prevention requirements (binding review folded)

The rev1 binding review confirmed the verifier's cryptographic semantics are safe (scheme-pin, OBLIG-1
layering, allowlist-rooted trust, byte-identical HMAC regression — all verified against the code) and
found NO fail-open, downgrade, or oracle. It returned REQUEST_REVISION solely because the parts that
PREVENT the outage (the slice's whole purpose) were phrased as open questions. rev2 pins them as MUST
requirements. The verifier semantics in §2 are unchanged; §2.1 adds the wiring contract, and §5 widens
the pre-flip validation.

- **N1 (MUST — keys_json load-site, was Q-E3/F1):** `enforce()` loads `config/aqos/lease-signer-keys.json`
  with `json.loads` into a **dict** (never the raw file text — a string denies-ALL) inside a LOCAL
  try/except whose failure yields a deny-all sentinel (`{}`), NOT a raised exception. A keys-file
  read/parse error must fail-closed to "Ed25519 denied" ONLY; it must never propagate to the S-c wrapper
  (`capability_lease_gate.py:736`), which would total-deny every tool including HMAC leases (a full
  outage, not the intended Ed25519-only fail-closed). If cached, a failed load caches the sentinel, never
  a raise-on-reuse. The HMAC path never reads keys_json, so its behavior is unaffected in all cases.
- **N2 (MUST — helper placement, was implied/F2):** `_admission_verify` MUST be called from INSIDE the
  existing `try/except` in BOTH branches (`:644-647` candidate, `:689-692` first-party). Rationale:
  `is_expired` calls `_parse_iso(data["expires_at"])`, which `verify_authoritative` does not pre-validate;
  a signed-but-malformed `expires_at` raises. Inside the try/except that raise maps to `VERIFY_MALFORMED`
  → DENY (fail-closed, one tool). Outside it, the raise escapes to the S-c wrapper and total-denies ALL
  tools. Placement is normative, not incidental.
- **N3 (MUST — full-enforce()-path pre-flip validation, was §5/F3, the most important):** the 25/25 mint
  canary proved only `verify_authoritative`. `enforce()`'s first-party branch applies THREE further gates
  that `verify_authoritative` never exercises, any of which DENIES an authentic Ed25519 lease → the very
  outage this slice prevents: (a) lease↔lookup-key match `tool in bound_actions` (`:681-688`); (b) the
  codex-3 tamper tripwire `_lease_bound_security_projection(lease) == _manifest_bound_security_projection(
  manifest_entry)` (`:704-713`) — the confined authority's minted projection (actions/resources/
  constraints/risk-block/trust_tier/zero_trust_behavior) MUST byte-equal the switchboard's live-manifest
  projection, so the authority and switchboard MUST load the SAME `config/first-party-tools.json` and the
  authority MUST stamp the risk block identically; (c) the layered expiry/epoch of N4. §5 MUST mandate a
  pre-flip dry-run of the ENTIRE `enforce()` path against a real authority-minted lease (all gates green),
  not just `verify_authoritative`.
- **N4 (MUST — epoch-source parity, was Q-E2/F4):** the confined authority stamps `revocation_epoch` and
  `enforce()` re-checks `epoch_stale(lease, resolve_current_epoch())`. Both MUST resolve the IDENTICAL
  epoch source (env `AQ_LEASE_POLICY_EPOCH` → `config/capability-lease-epoch` → 0). A mismatch either
  self-stales a fresh lease (authority-epoch < enforce-epoch → DENY outage) or over-lives a revocation
  (authority-epoch > enforce-epoch → survives a bump — a bounded fail-open requiring the two to disagree).
  Pin identical-source as an activation gate; the canary did not test it (`verify_authoritative` ignores
  epoch).
- **N5 (activation NOTE — HMAC secret stays provisioned, was F5):** `enforce()` resolves the HMAC key and,
  if `is_dev` (no production HMAC secret), degrades to `SAFE_READ_ALLOWLIST` for ALL tools BEFORE any lease
  logic (`:609-614`) — even under asymmetric mode. Do NOT de-provision the HMAC SOPS secret at flip time;
  keep it provisioned post-flip (a future slice may re-scope the `is_dev` gate when asymmetric is active).
  Not blocking; documented so the operator does not induce a read-only degrade outage.

Candidate-branch decision (Q-E1): use the SINGLE shared `_admission_verify` for BOTH branches. The
reviewer confirmed it opens no admit path (a caller can at most replay a genuine authority-signed lease,
gaining only what that lease already grants, still gated by expiry/epoch + zero-trust-strip), and the
shared helper GUARANTEES the N4 expiry/epoch layering is uniform (a candidate-only HMAC path that later
grew an ad-hoc ed25519 branch could forget it). The candidate branch correctly does NOT run the codex-3
manifest tripwire (first-party only) — a signed candidate lease's risk block is itself authenticated.

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

## 3. Resolved (was open questions) — see the rev2 normative requirements above

- Q-E1 (candidate-lease scheme) → RESOLVED: single shared `_admission_verify` for both branches (rev2
  candidate-branch decision). No admit path opened; guarantees uniform N4 layering.
- Q-E2 (epoch source) → **N4** (MUST: identical epoch source authority↔enforce; activation gate).
- Q-E3 (keys_json load site + failure) → **N1** (MUST: parsed dict, local try/except, deny-all sentinel,
  no exception escape to the S-c wrapper).
- Q-E4 (flag interaction) → RESOLVED: verify is flag-agnostic (per-lease `sig_scheme` dispatch); the flag
  stays mint-side only. The reviewer confirmed no hot cross-scheme cache window — the flag lives in
  `switchboard.nix`, so flipping it rebuilds+restarts, re-initializing `_FIRST_PARTY_LEASE_CACHE=None`
  (`:326`); there is no in-process hot-flip path.
- New wiring MUST from the review → **N2** (helper inside the existing try/except in BOTH branches).

## 4. Test vectors (offline, hermetic)

1. Ed25519 first-party lease (authority-minted, current epoch, unexpired) → ADMIT.
2. Ed25519 lease, `expires_at` in the past → DENY `first-party-lease-expired`.
3. Ed25519 lease, `revocation_epoch` < current → DENY `first-party-lease-epoch-stale`.
4. Ed25519 lease, signature byte-flipped → DENY `first-party-lease-auth-bad-signature`.
5. Ed25519 lease, `key_id` not in allowlist / `status:revoked` → DENY `auth-unknown-key-id` / `auth-key-not-active`.
6. Legacy HMAC first-party lease (no `sig_scheme`) → ADMIT via the byte-identical HMAC path (parity).
7. Malformed/missing `lease-signer-keys.json` → ALL ed25519 leases DENY; HMAC leases UNAFFECTED (N1).
8. Flag-OFF / sig_scheme-absent corpus → enforce() decisions byte-identical to pre-change (regression).
9. **(N2) Ed25519 lease with a signed-but-malformed `expires_at`** → DENY `first-party-lease-<malformed>`
   for THAT tool only; assert the exception does NOT escape the branch (other tools/HMAC leases still
   evaluate — no total-deny).
10. **(N1) keys-file read/parse raises** (simulated) → the load returns the deny-all sentinel; ed25519
    leases DENY, HMAC leases ADMIT; assert no exception reaches the S-c wrapper.
11. **(N4) epoch-source parity**: an authority-minted lease stamped at the enforce-resolved epoch → ADMIT;
    a lease stamped at authority-epoch < enforce-epoch → DENY epoch-stale (proves the mismatch-denies leg).

## 5. Path

Independent binding review (rev1 = REQUEST_REVISION, folded here) → **rev2 re-review** confirming N1–N5
are pinned normatively → hash-bound freeze → single-use owner build activation → default-OFF build
(scheme-dispatch inert until an Ed25519 lease appears) → independent code review → commit. THEN, as the
**N3 activation gate BEFORE the flip**: a pre-flip dry-run of the ENTIRE `enforce()` path (not just
`verify_authoritative`) against a real authority-minted lease — lease↔lookup-key match, the codex-3
projection-equality tripwire, AND layered expiry/epoch all GREEN — plus N4 epoch-source parity confirmed
and N5's HMAC secret kept provisioned. Only then flip `CAPABILITY_ASYMMETRIC_LEASE=1` +
`AQ_LEASE_SIGNING_SOCKET_PATH` in switchboard.nix + rebuild + the LIVE enforced-admission validation (a
real first-party tool admits on an Ed25519 lease; forged/expired/stale deny).

`RECORD: PREPARED_ONLY enforce-asymmetric-verify design. No implementation, key material, flag flip, or
activation authority.`
