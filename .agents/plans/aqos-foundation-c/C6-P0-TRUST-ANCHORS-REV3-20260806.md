---
title: "Foundation C — C6-P0 Trust Anchors, Revision 3 (NARROWED to declarative anchors)"
slice: "C6-P0"
revision: 3
kind: "design-only (PREPARED_ONLY; DEFAULT-OFF; authorizes nothing)"
date: "2026-08-06"
author: "Claude Opus 4.8 (analysis)"
supersedes: "C6-P0-TRUST-ANCHORS-DESIGN-20260801.md (which conflated issuer/transport with the declarative anchors)"
closes_review: "C6-P0-REV2-INDEPENDENT-REVIEW-20260801.md (REQUEST_REVISION) — via the reviewer's offered first option: NARROW"
base_head_anchor: "verify at freeze"
---

# C6-P0 Trust Anchors — Revision 3

## 0. Decision: take the reviewer's NARROW option

The rev2 independent review (`REQUEST_REVISION`) gave an explicit either/or: **either** narrow
C6-P0 to pure schemas/manifests with no claim that it closes the issuer/transport prerequisite,
**or** add the complete secret/principal/service authority inventory. Rev3 takes the **first
option**. It removes the C2 issuer, the authenticated transport, and every signer/principal claim
from C6-P0. Those move in full to a dedicated sibling slice,
`C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md`.

C6-P0 rev3 is therefore ONLY the immutable **declarative trust anchors** two later slices consume:
the owner public-key allowlist and the two closed JSON schemas. It introduces no executable trust
decision, no service, no socket, no key material, and no dispatch edit — so the two rev2 findings
(unspecified signer, deferred transport peer) are not present to answer: **C6-P0 makes no issuer or
transport claim.**

## 1. Objective and non-goal

C6-P0 rev3 establishes, as repository-declared public data + schemas, the trust anchors that the
epoch authority (owner-signed bumps) and the C2 scheduler-context issuer (audience-bound handoff)
will later verify against. It closes neither gate, hosts no process, and enables nothing. There is
no epoch bump, reservation, scheduler enablement, signer key, transport, issuer, provider call,
service, deployment, or activation in this slice.

## 2. Exact inventory (declarative-only)

| Operation | Path | Role |
|---|---|---|
| NEW | `config/aqos/c6-owner-public-keys.json` | Owner epoch-bump public-key allowlist: schema_version, monotonically-named key revision, per-key `{key_id, ed25519_public_key, status∈{active,revoked}, not_before?, not_after?}`. **Public data only** — no private material, path override, URL, env indirection, or runtime enrollment. |
| NEW | `config/schemas/revocation-epoch-bump.schema.json` | Closed `aq.revocation-epoch-bump/1` request+receipt schema (§ parent C6 2.1 fields). Declarative; no verifier code. |
| NEW | `config/schemas/scheduler-lease-context.schema.json` | Closed `aq.scheduler-lease-context/1` schema (§ parent C6 3.1 / issuer-slice fields). Declarative; no verifier code. |
| NEW | `scripts/testing/test-c6-p0-trust-anchors.py` | Offline validation: both schemas are well-formed JSON Schema; the allowlist is public-only (rejects any field that could carry private material), revisioned, duplicate-key-free, status-enum-bounded; negative vectors (private-material present, revision non-monotonic, symlink/writable key file, unknown status). Pure file/parse assertions — no signature, no socket, no service. |

**Removed from rev2 (moved to the issuer slice):** `dispatch.py`, `capability_lease_gate.py`,
`c2_scheduler_context_issuer.py`, `scheduler_context_transport.py`,
`c6-scheduler-context-issuer.json`, `revocation-epoch-authority.nix`, and the signed golden
vectors. **Excluded:** every service, socket, signer, private key, dispatch/gate edit, Nix service
module, `phase0.py`, dashboard, deployment, and activation.

## 3. Immutability and consumption contract

`config/aqos/c6-owner-public-keys.json` is consumed read-only by later slices from a pinned
evaluated copy; its file is root-owned and not writable by switchboard, the C2 issuer, or the epoch
authority. Changing any key revision requires a new hash-bound design/review/owner authorization —
no runtime reload, enrollment, or mutation. The two schemas are versioned; a field change is a new
schema version, never an in-place edit. Consumers must fail closed if an anchor is unreadable,
malformed, symlinked, or of an unexpected revision (that fail-closed behavior is specified and
tested in the consuming slices, not here).

## 4. Service Coverage

Not applicable and explicitly not claimed: C6-P0 rev3 ships no enabled service, endpoint, or runtime
capability. It is a hard stop if interpreted as service activation or as satisfying any later
coverage gate. The epoch authority and the issuer each ship their own live-backed dashboard
projection + registered integration AQ-QA in their own slices.

## 5. Freeze prerequisites and blockers

- Independent review of the exact rev3 candidate bytes (schemas + allowlist + test), verifying the
  allowlist truly carries public data only and the schemas match the field lists the two consuming
  slices will enforce.
- A fresh single-use owner authorization to build.
- No signer, principal, transport, UID/GID, or service claim is made or required here — those are
  the issuer slice's blockers (Q-C6-1), not C6-P0's.

`RECORD: PREPARED_ONLY C6-P0 rev3 (narrowed). No implementation, key material, service, epoch bump,
scheduling, provider traffic, deployment, or activation authority is granted.`
