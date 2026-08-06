---
title: "Foundation C — C2 Scheduler-Lease-Context Issuer + Authenticated Ingress (Q-C6-1)"
slice: "C2-SCI (C6 prerequisite)"
revision: 1
kind: "design-only (PREPARED_ONLY; DEFAULT-OFF; authorizes nothing)"
date: "2026-08-06"
author: "Claude Opus 4.8 (analysis)"
opens: "the missing C2 issuer that C6 §3.1 names as a stop condition"
depends_on: "C6-P0-TRUST-ANCHORS-REV3 (declarative schemas + owner allowlist)"
unblocks: "C6 main freeze → C6 activation → C4 freeze"
---

# C2 Scheduler-Lease-Context Issuer + Authenticated Ingress

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
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` | `3e92d2fe97a1ea8b18fef82848f11f502de5171bab6b297f810ffd021997e424` | On an admission ALLOW, hand the decision to the issuer over an outbound authenticated UDS client call. No signing key here. |
| EDIT | `scripts/ai/lib/dispatch.py` | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92` | Authenticated ingress adapter: accept only a verified immutable context, verify with the tracked PUBLIC key, never deserialize a caller argument as a context. |
| EDIT | `nix/modules/services/default.nix` | `a36d0b21013ff3352c91443c4a6ca39c4e81a3c992d6b8e1dd871aba2c38d32b` | Import the new issuer service module. |
| NO EDIT | `nix/modules/services/switchboard.nix` | `f25dc43fd5f8f346ef6199156fa8ae9b0510c34486f363e55ee744b03149c31f` | Byte-parity hardening anchor. The issuer is a SEPARATE service; the switchboard only makes an outbound UDS client call (code-level, in `capability_lease_gate.py`), so switchboard.nix is untouched. |
| NEW | `scripts/ai/lib/scheduler_context_issuer.py` | absent | Sole issuer: after a verified C2 admission ALLOW, mints + Ed25519-signs one closed context bound to that exact decision. Private key read from `/run/secrets/` via the service principal; never held by switchboard or dispatch. |
| NEW | `scripts/ai/lib/scheduler_context_transport.py` | absent | Local authenticated UDS: switchboard-caller ⇄ issuer (issuer authenticates the caller via `SO_PEERCRED` against the declared principal); one immutable signed frame; typed deny on ambiguity. |
| NEW | `nix/modules/services/c2-scheduler-context-issuer.nix` | absent | Dedicated default-OFF service `aq-c2-scheduler-context-issuer`: own unprivileged user/group, SOPS private-key read-only mount, UDS group-restricted socket, StateDirectory, `NoNewPrivileges`, empty `CapabilityBoundingSet`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, no network. `enable=false`. |
| NEW | `config/scheduler-context-signing-public-key` | absent | Tracked Ed25519 PUBLIC verifier key (non-secret), key-id-selected, mirroring the `config/grant-signing-public-key` precedent. Consumed by `dispatch.py` to verify — dispatch never holds the private key. |
| NEW | `config/aqos/c6-scheduler-signer-keys.json` | absent | key-id → public-verifier + `status∈{active,revoked}` + monotonic revision, for signer rotation/revocation (distinct key family from C6-P0's owner allowlist). |
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

- **Canonical identity via Nix, not a manifest value:** the receiving peer principal is the
  `users.users.aq-c2-scheduler-context-issuer` UID/GID **resolved by NixOS**, not a hard-coded
  numeric UID and not a caller-writable JSON. The UDS is group-restricted (`0660`, a dedicated
  client group the switchboard user joins) and additionally validated with `SO_PEERCRED`;
  membership alone is never authority.
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

The issuer signs **only** after `capability_lease_gate.py` returns an ALLOW, and **only** for the
exact `{principal, task_id, dispatch_mode, action_class, lease_id, grant_digest, revocation_epoch,
policy_revision}` of that decision — it cannot mint for an unaccepted or caller-selected tuple.
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

1. **Admission→issuer interface exactness:** confirm `capability_lease_gate.py` can hand the
   ALLOW decision to the issuer over the outbound UDS without any caller-controlled field crossing
   the boundary, and that this needs no switchboard.nix change (only a client-group membership the
   issuer module grants).
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
