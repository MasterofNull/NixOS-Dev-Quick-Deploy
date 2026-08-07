---
title: "Foundation C — enforce-asymmetric-verify FREEZE (ALA activation Phase 2 verifier)"
slice: "ALA-ENFORCE"
kind: "FREEZE (hash-bound; build gated on owner activation)"
date: "2026-08-07"
frozen_design_sha256: "6a2e5f84423ac67d3987fdc3b6c0ddbfb58010734859a222a4a556be80fb9cd5"
build_head: "3a98594336ef172046715ac190fc78c493c3a1d7"
---

# enforce-asymmetric-verify — FREEZE

Frozen at design **rev2** (SHA-256 `6a2e5f84423ac67d3987fdc3b6c0ddbfb58010734859a222a4a556be80fb9cd5`),
verified against the code. Build is gated on a single-use OWNER build-activation grant (below). Any drift
of the frozen design bytes or the anchored baseline ⇒ re-freeze.

## Review chain (all independent; Rule 18)
- **rev1 binding review** (fresh Claude flagship, Codex-substitute) = REQUEST_REVISION — crypto core SAFE
  (no fail-open / downgrade / oracle; scheme-pin, OBLIG-1 layering, allowlist trust, HMAC regression all
  verified against code); fail-closed/outage spec incomplete. `fresh-flagship.md`.
- **rev2** folded F1–F5 into normative requirements N1–N5 (verifier semantics byte-unchanged).
- **rev2 re-review** (fresh Claude flagship) = **PASS** — N1–N5 all pinned + verified against design AND
  code; no new defect, no regression; one non-blocking note (V11 covers only N4's deny direction, milder
  over-live direction rests on the pinned source-parity activation gate). `fresh-flagship-rev2.md`.
- Advisory concurrence (non-gating): Antigravity PASS (+ caught the real C2 baseline drift); local Qwen
  logic-sound.

## Frozen scope (anchored baseline — verify at build; drift ⇒ re-freeze)
| Op | Path | Pre-build SHA-256 | Contract |
|---|---|---|---|
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` | `6d4ca1a0a1959332fb4af0fbe1997d11dcb15fbaa7049139a0e03db129259131` | Add `_admission_verify` (scheme-dispatch); call it from INSIDE the existing try/except in BOTH the candidate (`~:644-647`) and first-party (`~:689-692`) branches (N2); load `lease-signer-keys.json` as a parsed dict, locally fail-closed to a `{}` sentinel, no exception escape (N1). Legacy HMAC path byte-identical. |
| NO EDIT | `scripts/ai/lib/capability_lease.py` | (consumed as-is; `verify_authoritative`, `cl.verify`, `is_expired`, `epoch_stale`) | — |
| NO EDIT | `nix/modules/services/switchboard.nix` | (byte-parity anchor; the flag flip is a separate later edit) | — |
| NEW | `scripts/testing/test-enforce-asymmetric-verify.py` | (absent) | The 11 offline admission vectors incl. V9 (malformed `expires_at` → one-tool deny, no escape / N2), V10 (keys-file raise → sentinel, no escape / N1), V11 (epoch parity + mismatch-denies / N4). |

Default-OFF: scheme-dispatch is INERT until an Ed25519 lease appears (i.e. until the mint flag
`CAPABILITY_ASYMMETRIC_LEASE=1` flips) — this build changes NO behavior for existing HMAC leases.

## Build → activation path (after the owner grant)
1. Build default-OFF per the frozen scope (cheapest-eligible implementer, Rule 17).
2. Independent code review of the exact bytes.
3. Commit.
4. **N3 activation gate BEFORE the flag flip**: a pre-flip dry-run of the ENTIRE `enforce()` path against a
   real authority-minted lease (lease↔lookup-key match + codex-3 projection-equality tripwire + layered
   expiry/epoch all GREEN), N4 epoch-source parity confirmed, N5 HMAC secret kept provisioned.
5. Only then flip `CAPABILITY_ASYMMETRIC_LEASE=1` + `AQ_LEASE_SIGNING_SOCKET_PATH` in `switchboard.nix` +
   rebuild + LIVE enforced-admission validation.

## Owner build-activation grant (single-use; OWNER emits — the orchestrator MUST NOT self-emit)
The build begins only after the owner emits:
```
scripts/ai/aq-event emit --agent owner --type activation.grant \
  --subject enforce-asymmetric-verify-build \
  --payload '{"idempotency_key":"enforce-asymmetric-verify-build-20260807","subject_design_sha256":"6a2e5f84423ac67d3987fdc3b6c0ddbfb58010734859a222a4a556be80fb9cd5","build_head":"3a98594336ef172046715ac190fc78c493c3a1d7","predecessors":["ala-rev4-minter-activated"],"implementer":"sonnet","window_hours":24}'
```
`implementer: sonnet` — cheapest tier whose capability satisfies this security-critical bounded admission
change (N1/N2 fail-closed subtleties exceed the trivial envelope); substitute Codex on its Aug-8 return or
local Qwen if eligible (Rule 17). This grant is hash-bound to the frozen design + build head; it is a
deliberate single-use owner act, NOT standing authority.

`RECORD: FROZEN. No implementation, flag flip, or activation authority until the owner grant above is emitted.`
