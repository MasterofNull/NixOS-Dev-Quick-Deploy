---
title: "Foundation C — C2 Scheduler-Lease-Context Issuer + Authenticated Ingress (Q-C6-1)"
slice: "C2-SCI (C6 prerequisite)"
revision: 4
kind: "design-only (PREPARED_ONLY; DEFAULT-OFF; authorizes nothing)"
date: "2026-08-06 (rev4 re-anchor 2026-08-07)"
author: "Claude Opus 4.8 (analysis)"
opens: "the missing C2 issuer that C6 §3.1 names as a stop condition"
depends_on: "C6-P0-TRUST-ANCHORS-REV3 (declarative schemas) + ALA rev4 now ACTIVATED (asymmetric lease + verify_authoritative + config/aqos/lease-signer-keys.json; CAPABILITY_ASYMMETRIC_LEASE=1 live)"
unblocks: "C6 main freeze → C6 activation → C4 freeze"
closes_review: "rev1 REQUEST_REVISION → rev2; rev2 FAIL (assumed asymmetric lease that did not exist) → rev3 (ALA built) → rev4 (ALA now ACTIVATED + baseline re-anchored). rev1/rev2 superseded."
---

# C2 Scheduler-Lease-Context Issuer + Authenticated Ingress

## Revision 4 — baseline re-anchor after ALA activation (2026-08-07)

Between rev3 and now, the ALA asymmetric lease spine went from BUILT to fully ACTIVATED:
`CAPABILITY_ASYMMETRIC_LEASE=1` is live (86ec204e), `enforce()` now verifies Ed25519 first-party leases
via `verify_authoritative` (`a4c496ec`, independently code-reviewed, N3 dry-run 25/25 admit), and
`switchboard.nix` carries the flip env. rev4 changes ONLY the §1 anchored baseline hashes to the current
truth (`capability_lease_gate.py` now holds the enforce-verify code — the C2 outbound-client edit layers
on top; `default.nix` gained the ALA + auto-wake imports; `switchboard.nix` is now the post-flip state and
STILL not edited by this slice). The rev3 trust model, signer authority, transport, and single-use ledger
(§2–§6) are UNCHANGED and stand. `dispatch.py` did not drift. Route this rev4 for binding review; the
rev3 open questions Q-R3-1/Q-R3-2 already answered by the advisory round carry forward for the binding
reviewer to confirm.

**rev4 binding review = PASS** (fresh Claude flagship, Codex-substitute; `.agents/plans/c2-scheduler-context-issuer-rev4-review/fresh-flagship.md`). All 4 re-anchored hashes match byte-for-byte, all NEW files absent by design, all 7 assessment points SOUND (trust model correctly rooted in the un-forgeable Ed25519 signed lease neutralizing the human-uid peer gap; OBLIG-1 mirrors the live `_admission_verify`; issuer-side single-use ledger the correct layer; epoch source confirmed; signer authority + two-flag independence + no switchboard.nix edit hold; no fail-open/oracle/fail-closed-breakage). Two LOW notes folded: the peer-uid line ref corrected to `switchboard.nix:552`; and §Rev3.3's "slot_queue single-use is on the context digest" is forward-looking (slot_queue.py has no such surface today) — which makes the ISSUER-side `{lease_id, grant_digest}` 1:1 ledger the authoritative single-use point, MORE necessary not less (no design change). Advisory lanes (local Qwen, Antigravity) fold on return, non-gating.

## Revision 3 — the assumed asymmetric lease now EXISTS (ALA built); layer OBLIG-1 + single-use

rev2's trust model ("authority is the SIGNED C2 lease; the issuer verifies it against the lease-issuer
public key") was correct in shape but FAILed re-review because, at the time, the C2 lease was symmetric
HMAC with a dev key — no asymmetric lease-issuer public key existed (verify == forge). **That primitive
is now BUILT:** the Asymmetric Lease Authority (ALA rev4, commits `65d6f507`/`28c836c0`/`51795389`,
default-OFF) provides `capability_lease.verify_authoritative(lease, keys_json)` (Ed25519, scheme-pinned,
no HMAC/dev-key fallback) + the sole-source public verifier `config/aqos/lease-signer-keys.json`. rev3
realizes the rev2 trust model on that built foundation, with the integration obligations the ALA code
review surfaced:

1. **Verify the presented lease via ALA (not a bespoke verifier):** the issuer calls
   `capability_lease.verify_authoritative(presented_lease, config/aqos/lease-signer-keys.json)`. A
   shell caller cannot forge an Ed25519 lease minted only by the confined `aq-lease-signing-authority`
   → the switchboard-runs-as-human-uid fact is fully neutralized (rev2's central claim, now real).
2. **Layer expiry + epoch on top (ALA OBLIG-1 — MANDATORY):** `verify_authoritative` returns "authentically
   signed by an active key," NOT "currently valid." The issuer MUST independently reject the presented
   lease if `expires_at` is past OR its `revocation_epoch` != the current authoritative epoch, and
   re-derive the admission tuple (tool, action_class from `permissions.actions`, trust_tier) from the
   lease's OWN signed fields — never from caller input. Absent this, a stale/expired lease could mint a
   context (fail-open).
3. **Single-use consumed-lease ledger (closes the one-lease-many-contexts finding — flagship + local
   Qwen):** the issuer durably records `{lease_id, grant_digest}` and refuses a second scheduler-context
   mint for the same lease. `slot_queue`'s single-use is on the CONTEXT digest (many context_ids from
   one lease would each pass it); the 1:1 must be enforced HERE, at the issuer, before minting.
4. **Bind context validity to the lease:** `context.expires_at = min(lease.expires_at, issued_at +
   context_TTL_cap)` (never extend beyond the lease), and `context.revocation_epoch` = the same
   authority-resolved epoch checked in (2).

(rev2 mandates stand: the context SIGNER is the issuer's own confined Ed25519 key (SOPS, dedicated
`aq-c2-scheduler-context-issuer` principal), verified downstream via the sole-source
`config/aqos/c6-scheduler-signer-keys.json`; the bare public-key file is dropped. §1 lease-verify
anchor now points at the BUILT ALA `lease-signer-keys.json`, not a "verify at freeze" placeholder.)

**Open questions for the independent reviewer (rev3):**
- Q-R3-1: the scheduler-context needs `{task_id, principal, dispatch_mode}` which the first-party lease
  (issued_to = a constant, per-tool) does NOT carry. These are DISPATCH-correlation, not authority —
  confirm they can be caller-supplied as correlation-only (authority = the lease) WITHOUT widening what
  the context authorizes, and that the single-use ledger keys on `{lease_id, grant_digest}` (one context
  per lease) NOT per-task (else one lease → many contexts returns).
- Q-R3-2: name the exact "current authoritative epoch" source for (2)/(4) pre-C6 (the epoch file today;
  the C6 epoch authority once activated) and that a mismatch denies.

## Revision 2 — closes the binding-review findings (rev1 must not be frozen)

A fresh-flagship binding review (2026-08-06) returned REQUEST_REVISION on rev1 with a
CONFIRMED HIGH defect: the switchboard that hosts the C2 gate runs as `cfg.primaryUser`
(`nix/modules/services/switchboard.nix:552`) — the **human owner uid**. So `SO_PEERCRED` +
group membership on the issuer socket **cannot distinguish the legitimate switchboard caller
from any other owner-uid process** (a shell, `delegate-to-local`, a compromised tool), and a
caller could present a fabricated `{ALLOW, principal, task}` that the issuer would sign. Rev1's
"authenticate the caller by peer-uid" was not authority. Rev2 fixes the **trust model**:

1. **Authority is the SIGNED C2 LEASE, not the caller or the peer-uid** (closes HIGH findings 1+2).
   The issuer NEVER trusts a caller-asserted ALLOW. The caller must present the existing
   Ed25519-signed C2 capability lease (already minted + signed by the C2 lease issuer,
   `capability_lease.py`/`capability_lease_issuance.py`). The issuer independently VERIFIES that
   lease signature against the tracked lease-issuer public key, re-checks freshness + the
   authoritative epoch, **re-derives** the admission tuple from the lease's own signed fields, and
   mints the scheduler-context bound to those. A shell caller cannot forge a signed lease, so it
   cannot obtain a context. `SO_PEERCRED` + group are retained only as **defense-in-depth**,
   explicitly NOT the authority — so the switchboard-runs-as-human-uid fact no longer matters.
2. **The JSON allowlist is the SOLE signer-verifier source** (closes LOW-MED finding 3):
   `config/aqos/c6-scheduler-signer-keys.json` (key-id → public + `status`) is authoritative;
   the bare `config/scheduler-context-signing-public-key` is DROPPED (a revoked key must not
   verify via a status-less bare file).
3. **Parent-C6 schema-ownership** (Doc-1 MEDIUM, handled in a parent amendment): the two schemas
   are created by C6-P0 rev3; parent C6 §1/§4 must mark them verify-only/no-create. Tracked as a
   C6-main freeze amendment, not a defect in these bytes.

The sections below are rev2 as amended; where rev1 said "authenticate the caller / trust the
admission ALLOW," read the rev2 trust model above.

## 0. Why this slice exists

C6's scheduler revocation gate is only meaningful if `dispatch.py` receives a **signed,
audience-bound** `aq.scheduler-lease-context/1` produced by the C2 admission authority — never from
a shell caller. That issuer does not exist today (`capability_lease_gate.py` returns admission
decisions but exposes no such handoff; grep confirms no producer). C6 §3.1 makes this an explicit
**stop condition** requiring a separately reviewed slice. This is that slice. It is design-only,
default-OFF, and authorizes nothing.

It answers the two open C6-P0 rev2 findings that were scoped out of C6-P0 rev3: (1) the
scheduler-context **signer's** private-key provisioning, principal, rotation/revocation, and
fail-closed path; and (2) the **transport peer** canonical identity and its Nix ownership source.

## 1. Anchored baseline (verify at freeze; drift ⇒ re-freeze)

| Operation | Path | SHA-256 (2026-08-06) | Role |
|---|---|---|---|
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` | `0686c6faa5a33306e0037f7f32a1b317ec76e2a2fcd33a6ada03d5ee85ed8cc8` (rev4 re-anchor: now contains the LIVE enforce-asymmetric-verify code — `_admission_verify` etc. — from a4c496ec; the C2 issuer's outbound-client edit layers on top) | On an admission ALLOW, hand the decision to the issuer over an outbound authenticated UDS client call. No signing key here. |
| EDIT | `scripts/ai/lib/dispatch.py` | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92` | Authenticated ingress adapter: accept only a verified immutable context, verify with the tracked PUBLIC key, never deserialize a caller argument as a context. |
| EDIT | `nix/modules/services/default.nix` | `c3b6d18e26f303b4f58aabc3869ed30bb95a20c274d9badb1b4813bccdec7ce4` (rev4 re-anchor: ALA + antigravity-auto-wake imports since landed) | Import the new issuer service module. |
| NO EDIT | `nix/modules/services/switchboard.nix` | `9b090af1c662cc9aa1e52b5d9a270e197461140b8c7c8e0ff9cec5627c93dfba` (rev4 re-anchor: now the POST-ALA-flip state — CAPABILITY_ASYMMETRIC_LEASE=1 landed in 86ec204e; the C2 issuer STILL does not edit switchboard.nix, it only makes an outbound UDS client call from capability_lease_gate.py) | Byte-parity hardening anchor. The issuer is a SEPARATE service; switchboard.nix stays untouched by this slice. |
| NEW | `scripts/ai/lib/scheduler_context_issuer.py` | absent | Sole issuer: after a verified C2 admission ALLOW, mints + Ed25519-signs one closed context bound to that exact decision. Private key read from `/run/secrets/` via the service principal; never held by switchboard or dispatch. |
| NEW | `scripts/ai/lib/scheduler_context_transport.py` | absent | Local authenticated UDS: switchboard-caller ⇄ issuer (issuer authenticates the caller via `SO_PEERCRED` against the declared principal); one immutable signed frame; typed deny on ambiguity. |
| NEW | `nix/modules/services/c2-scheduler-context-issuer.nix` | absent | Dedicated default-OFF service `aq-c2-scheduler-context-issuer`: own unprivileged user/group, SOPS private-key read-only mount, UDS group-restricted socket, StateDirectory, `NoNewPrivileges`, empty `CapabilityBoundingSet`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, no network. `enable=false`. |
| NEW | `config/aqos/c6-scheduler-signer-keys.json` | absent | **SOLE** scheduler-context signer-verifier source (rev2, finding 3): key-id → Ed25519 public + `status∈{active,revoked}` + monotonic revision. `dispatch.py` verifies the context signature ONLY through this status-bearing allowlist — a revoked key never verifies. The bare `config/scheduler-context-signing-public-key` of rev1 is DROPPED (a status-less bare file could accept a revoked key). Distinct key family from C6-P0's owner allowlist. |
| ANCHOR (BUILT — ALA rev4) | `scripts/ai/lib/capability_lease.py` `verify_authoritative` + `config/aqos/lease-signer-keys.json` | present (ALA build) | rev3: the issuer verifies the PRESENTED lease via the BUILT ALA `verify_authoritative` (Ed25519, scheme-pinned, no HMAC fallback) against the sole-source `lease-signer-keys.json`, THEN layers expiry + epoch (OBLIG-1). No bespoke verifier. |
| NEW | `config/schemas/scheduler-lease-gate-decision.schema.json` | absent | Low-cardinality typed issue/deny/audit record. |
| NEW | `scripts/testing/test-scheduler-context-issuer.py` | absent | Offline: admission-bound issuance, key-unavailable fail-closed, SO_PEERCRED peer bind, replay/context-id, flag-OFF byte-parity, negative vectors. |
| NEW | `scripts/testing/test-c2-sci-service-coverage.py` | absent | Integration fixture: issuer health + AQ-QA registration + dashboard projection. |
| EDIT | `scripts/testing/harness_qa/phases/phase0.py` | (hash at freeze) | Register the integration AQ-QA check. |
| EDIT | `dashboard/backend/api/routes/aistack.py` + `assets/dashboard.js` | (hashes at freeze) | Live-backed issuer state card. |

SOPS: add `c6-scheduler-context-signing-key` (Ed25519 private) to `secrets/` and `secrets.nix`,
decrypted to `/run/secrets/…` owned by the issuer principal, mode `0400`. **Pattern reminder
(HARD):** adding a key to `secrets.nix` MUST be followed by `sops <file>` re-encryption or the
whole stack cascades; never place private material in a tracked Nix file.

## 2. Signer authority (closes rev2 finding 1)

- **Key family:** a dedicated scheduler-context signer key, domain-separated
  (`aq.scheduler-lease-context/1`), distinct from the owner epoch-bump key family in C6-P0.
- **Provisioning:** SOPS-managed Ed25519 private key → `/run/secrets/c6-scheduler-context-signing-key`,
  readable ONLY by the `aq-c2-scheduler-context-issuer` service principal (`0400`, owned by that
  user). The public verifier is tracked (`config/scheduler-context-signing-public-key`); dispatch
  and any verifier use public-only material.
- **Execution principal:** the issuer runs solely as `aq-c2-scheduler-context-issuer` (a Nix
  `users.users` declaration in the issuer module) — never as switchboard, never as a shell caller.
  A Python module is not the sole issuer; the *service + its confined principal + its read-only key
  mount* is.
- **Rotation/revocation:** rotation = new SOPS private key + new tracked public + new monotonic
  key-id revision in `c6-scheduler-signer-keys.json`, all hash-bound (design/review/owner act).
  Revocation = set the key-id `status: revoked`; verifiers reject a revoked/unknown key-id.
- **Fail-closed:** if the private key is unreadable/malformed/replaced, the issuer mints NOTHING and
  returns a typed `signer-unavailable` deny; downstream `dispatch.py`/`slot_queue` deny on absent
  context. No environment fallback, no bootstrap, no unsigned compatibility path.

## 3. Transport peer authority (closes rev2 finding 2)

- **Authority is the signed lease, not the peer (rev2):** because the switchboard client runs as
  `cfg.primaryUser` (the human owner uid, indistinguishable from shell callers), `SO_PEERCRED` +
  group membership are treated as **defense-in-depth only, never authority**. The gate on minting is
  the independently-verified Ed25519-signed C2 lease (§4). The server (issuer) identity is still
  canonical via `users.users.aq-c2-scheduler-context-issuer` resolved by NixOS; the UDS is
  group-restricted (`0660`) — but a caller that passes peer/group checks still cannot mint without a
  valid signed lease it cannot forge.
- **Hosting while the epoch authority is disabled:** the issuer is its **own** default-OFF service
  (not hosted in switchboard, preserving the switchboard.nix anchor; not dependent on the
  still-disabled epoch-authority service). It can therefore ship and be reviewed independently of
  the epoch-authority enablement.
- **Direction:** `capability_lease_gate.py` (switchboard) is the CLIENT on an admission ALLOW; the
  issuer is the SERVER that authenticates the caller, mints, and returns the signed context. The
  context then reaches `dispatch.py` through the ingress adapter, which re-verifies signature,
  audience (`aq-f2.5-slot-queue`), principal/task/mode/action binding, freshness, and the
  authoritative epoch before handing an immutable object to `slot_queue`.

## 4. Admission binding and default-OFF boundary

The issuer mints **only** against a presented, independently-VERIFIED Ed25519-signed C2 capability
lease (rev2 trust model). It verifies the lease signature against the tracked lease-issuer public
key, re-checks freshness + the authoritative epoch, and **re-derives** the bound tuple
`{principal, task_id, dispatch_mode, action_class, lease_id, grant_digest, revocation_epoch,
policy_revision}` FROM the lease's own signed fields — never from a caller-asserted ALLOW or a
caller-selected tuple. It cannot mint for an unverifiable lease, an expired/stale-epoch lease, or a
tuple not present in the signed lease. `SO_PEERCRED` peer identity is checked as defense-in-depth
only and is never the authority.
Flag `CAPABILITY_SCHEDULER_CONTEXT_ISSUER=0` (default): switchboard makes no issuer call, the issuer
service is not enabled, `dispatch.py`/`slot_queue` preserve byte-parity for every legacy request. ON
is a later, separate owner act; it does not itself enable C6's scheduler gate
(`CAPABILITY_SCHEDULER_LEASE_GATE`) — the two flags are independently owner-gated.

## 5. Service Coverage (mandatory in this slice — it ships an enabled-capable service)

1. Integration AQ-QA (`phase0.py`-registered, hermetic, no provider): admission ALLOW → issuer sign
   → transport → `dispatch.py` verify → immutable context, plus every deny path (signer-unavailable,
   revoked key, peer mismatch, replay, wrong audience/principal/mode, flag-OFF parity).
2. Dashboard API + card: issuer health (`healthy|degraded|unavailable`), signer-key availability,
   issued/denied counters by reason, last redacted decision reference, bounded latency buckets —
   low-cardinality only; no lease id, grant, prompt, path, or signature.
3. health-spider/alert: signer-unavailable, invalid signature rate, unexpected issuance while
   flag-OFF, service failure.

No hard-coded healthy state, flag-only status, or `--` placeholder.

## 6. Open blockers for the independent reviewer

1. **Lease-presentation interface (rev2):** confirm the caller presents the full Ed25519-signed C2
   lease over the UDS and the issuer re-derives + re-verifies admission from it (never a
   caller-asserted ALLOW) — the caller-indistinguishability gap (switchboard = human uid) is
   resolved by making the signed lease the authority, not the peer. Verify the lease-issuer public
   key the issuer must hold, and that no switchboard.nix edit is needed (outbound client call +
   issuer-granted client group only).
2. **Issuer→dispatch transport exactness:** name precisely how the signed context reaches
   `dispatch.py` (direct issuer↔dispatch UDS vs. carried on the verified task record) such that
   `dispatch.py` never accepts a caller-supplied context; both ends default-OFF with no fallback.
3. **SOPS/secret ceiling:** the exact `secrets.nix` entry, `/run/secrets` owner/mode, and proof the
   key is unreadable by switchboard, dispatch, and the epoch authority.
4. **Two-flag independence:** verify `CAPABILITY_SCHEDULER_CONTEXT_ISSUER` and
   `CAPABILITY_SCHEDULER_LEASE_GATE` cannot be conflated into a single enable.

## 7. Path

C6-P0 rev3 PASS → this slice: independent review of exact bytes → hash-bound freeze → single-use
owner build activation → default-OFF build + Service Coverage → independent code review → commit →
separate owner flag-on. Then C6 main freeze can bind this slice's accepted commit as its Q-C6-1
closure, and the C6→C4 chain proceeds.

`RECORD: PREPARED_ONLY C2 scheduler-context issuer design. No implementation, key material, service
enablement, epoch bump, scheduling, provider traffic, deployment, or activation authority.`
