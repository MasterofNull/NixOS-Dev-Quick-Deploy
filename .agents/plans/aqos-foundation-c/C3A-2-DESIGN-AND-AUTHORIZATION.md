---
title: "Foundation C C3a-2: Delegate Broker + Signed-A2A Verify-before-write — Design Packet"
slice: "C3a-2"
status: "PREPARED_FOR_INDEPENDENT_REVIEW"
revision: 1
kind: "design-only"
implementation_authorization: "NONE — enforcement-tier: requires single-use owner activation before build"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C3b R1 grant (attenuate), R2 cell+quarantine, R3 runner (all shipped)"
  - "C2 gate (97131faa); antigravity-inbox atomic claim/receipt (aq-antigravity-inbox)"
supersedes:
  - "C3A-2-DESIGN-FORWARD-SCOPE.md (stub) — this is the full design"
successors:
  - "R5 switchboard adapter (routes admitted effects incl. delegate into cells)"
---

# Foundation C — C3a-2: Delegate Broker + Signed-A2A Verify-before-write

## 0. Provenance & authority
Authored by Opus (codex-substitution). Independent review → antigravity/gemini + codex-on-return.
**DESIGN-ONLY.** **C3a-2 is ENFORCEMENT-TIER** (it accepts remote-produced work into the tree) —
build requires **single-use owner activation**, ships flag-default-OFF, deny-closed. Promotes the
`C3A-2-DESIGN-FORWARD-SCOPE.md` stub to a full design now that the C3b substrate (R1 attenuate, R2
cell+quarantine, R3 runner) and the antigravity-inbox atomic lock exist to build on.

## 1. Scope
The **delegate** effect (the one C3b/R1 classifies deny-until-C3a-2): `delegate_to_remote` +
**inbound A2A acceptance**. The delegate broker (a) issues an **attenuated child grant** to a
remote-lane principal, and (b) accepts the returned work ONLY through **signed verify-before-write**
into a C3b cell. **Out of scope:** write/secret/exec (C3b cells), network egress (C4), the
scheduler (C6), the switchboard routing (R5). No API key ever handled (standing rule).

## 2. Child-grant issuance (attenuated, monotonic)
On a `delegate_to_remote` admitted by C2, the delegate broker mints an **attenuated child grant**
from the parent's `VerifiedGrant` via R1 `execution_grant`/`capability_lease.attenuate` (child ⊆
parent over every field — proven complete in C0): narrowed `effect_set`, `logical_paths`,
`exec_class`, a fresh `grant_id`, current `revocation_epoch`, a bounded `deadline`, and the
**signed** `allowed_gap` (SHOULD-2 — heartbeat interval bound into the child authority, not free
config). The child grant is Ed25519-signed by the gate/issuer's PRIVATE key (R1 SF-1; SOPS
`/run/secrets`); the remote principal receives only the grant + a quarantine drop path — never a
key, never write access to the authoritative tree.

## 3. Signer chronology — the local broker attests (folds BLOCKING-4)
The remote lane has **no local key**, yet acceptance must bind `output_digest` + heartbeat values
that exist only *after* remote execution. Resolution: **the LOCAL delegate broker signs after
reading the quarantine blob**, attesting the broker's **locally recomputed** digest of what landed
— NOT remote identity. So the trust chain is: gate signs the child grant (authorizes the task);
remote produces bytes into an untrusted quarantine; **local broker recomputes + signs the
acceptance record** (attesting "these exact bytes, this digest, within this grant"). Remote
authenticity is NOT asserted (the watched folder/inbox is untrusted transport); if it is ever
required, that is a SEPARATE remote-verification mechanism — the local HMAC/Ed25519 key is NEVER
handed to a remote principal.

## 4. Verify-before-write + atomic replay (folds BLOCKING-5)
Remote work writes ONLY an untrusted **quarantine blob** (never the authoritative tree). The broker
then, in fixed order:
1. safely reads the quarantine blob (R2's quarantine dir discipline);
2. **verifies**: child-grant signature (R1) + `output_digest` (locally recomputed) + `deadline`
   not blown + `expected_output_path` ⊆ the child grant's `logical_paths` + schema-valid;
3. **atomically reserves** the idempotency token on a **collision-resistant digest of a signed
   canonical request identity** `(child_lease_id, idempotency_token)` — NOT the inbox's task-ID-only
   lock — using the `aq-antigravity-inbox` `_locked(_task_lock(...))` atomic primitive extended to
   this composite key, with a `reserved → committed | failed` state so a reserved token can never
   leave an ambiguous acceptance (crash recovery: a `reserved` with no terminal record is reclaimed
   as `failed` by an idempotent reconciler, mirroring R2);
4. **commits** the verified bytes into a **C3b cell** (the R3 runner path) — the write lands only in
   the confined cell worktree, validated by the out-of-cell validator, retained-for-review on GREEN
   (never auto-merged). No remote principal writes the authoritative path directly.

## 5. Deterministic heartbeat (folds BLOCKING-6, SHOULD-2)
Signed **monotonic `heartbeat_seq`** + trusted receipt time; state machine
`live → pending-late (seq gap within signed allowed_gap) → dead (deadline blown OR gap > allowed_gap)`
— transitions irreversible + append-only; replayed/duplicate seq rejected; `dead` → acceptance
DENIED (no partial write). `allowed_gap` is read from the SIGNED child grant (§2), never a mutable
config. Heartbeat records extend the inbox receipt protocol (signed, append-only).

## 6. Composition + flag
NEW flag `CAPABILITY_DELEGATE_BROKER` (default "0"); OFF ⇒ `delegate_to_remote` stays deny-closed
exactly as C3b classifies it today (byte-parity). ON ⇒ the delegate broker mints child grants +
runs the verify-before-write acceptance. Deny-closed on any failure (bad sig / stale epoch / past
deadline / replayed token / path escape / schema-invalid / dead heartbeat / key-unavailable) — the
delegated work is simply not accepted; never a bypass. Authority-degrade: signer/policy unavailable
⇒ no child grant minted ⇒ delegate denied. Antigravity/remote stays untrusted-advisory: the inbox
is transport only; the signed acceptance record is the authority (consistent with the standing
Antigravity posture).

## 7. Ceiling (frozen at C3a-2 freeze; enforcement-tier)
- NEW `ai-stack/switchboard/delegate_broker.py` — child-grant attenuation (R1), quarantine read,
  verify (R1 sig + local digest), atomic composite-key reservation, commit-via-C3b-cell, heartbeat
  state machine. Deny-closed, never raises.
- NEW A2A envelope schema (`config/schemas/a2a-delegate-envelope.schema.json`) signing all
  authority-bearing fields (§3/§4) + `heartbeat_seq`/`allowed_gap`/`idempotency_token`.
- EDIT `scripts/ai/aq-antigravity-inbox` (+ receipt schema) — atomic reservation on the composite
  `(child_lease_id, idempotency_token)` digest + signed heartbeat records (extend, don't weaken, the
  existing locked append-only protocol).
- EDIT `config/env-contract.yaml` — `CAPABILITY_DELEGATE_BROKER` (default "0").
- NEW `scripts/testing/test-delegate-broker.py` — offline: child ⊆ parent attenuation; quarantine→
  verify→reserve→commit-to-cell happy path; each reject (bad sig / stale epoch / past deadline /
  replayed token / path outside child paths / schema-invalid / dead heartbeat / key-unavailable) →
  NOT accepted, no authoritative write; atomic reservation under contention + crash recovery
  (reserved→failed); flag-OFF byte-parity (delegate stays deny); no key handled/forwarded.
- **MUST NOT:** hand any key to a remote principal; let remote write the authoritative tree; accept
  on the inbox/watched-folder alone (envelope is authority); auto-reissue on epoch bump; weaken the
  C3b cell/validator path; touch R1/R2/R3 frozen enforcement code (consume only).

## 8. Acceptance bar
- child grant is a strict monotonic attenuation of the parent (subset every field); signed; bounded deadline+allowed_gap.
- remote never writes the authoritative path; all bytes land in quarantine → verified → committed via a C3b cell → validator → retained-for-review (never auto-merged).
- every reject class denies with no authoritative write; deny-closed on key/policy unavailable.
- idempotency reservation is atomic on the signed composite key with reserved→committed|failed crash recovery; replay denied.
- heartbeat deterministic (signed monotonic seq, signed allowed_gap, irreversible transitions); dead → denied.
- flag-OFF byte-parity (delegate stays deny-closed); NO key handled/forwarded; inbox is transport-only.

## 9. Review obligations
1. no fail-open: every reject class → no authoritative write; deny-closed on unavailability.
2. signer chronology sound (local broker attests locally-recomputed digest; no remote key; no remote-identity claim smuggled in).
3. verify-before-write real (remote → quarantine only → verify → commit-via-cell; authoritative path never remote-written).
4. replay uniqueness on the SIGNED composite key (not inbox task-ID); atomic; crash-recoverable.
5. heartbeat deterministic + signed allowed_gap; dead denies.
6. child ⊆ parent monotonic attenuation; flag-OFF byte-parity; no key handled; anchors real (R1 attenuate, R2 quarantine, inbox _locked).

## 10. Ceremony (enforcement-tier)
design → independent review → freeze (subject = this doc; predecessor hashes R1/R2/R3 code + gate +
aq-antigravity-inbox + the A2A envelope schema) → **single-use owner activation** → build
flag-default-OFF → review → commit. Turning `CAPABILITY_DELEGATE_BROKER` ON is a further separate
act. Standing authorization does NOT activate C3a-2.

## 11. Open questions for review
- Q-C3a2-1: reuse the aq-antigravity-inbox lock for the composite-key reservation vs a dedicated
  reservation store — recommend reuse (proven atomic primitive) with the composite-key extension.
- Q-C3a2-2: should the delegate broker's commit-to-cell reuse the R3 runner UDS (C3b) directly, or a
  thin in-process R2 create_cell for the accept path? Recommend the R3 runner path once R5 exists (one
  confinement chokepoint); until R5, a direct R2 create_cell accept is acceptable (still cell-confined).
- Q-C3a2-3: confirm the remote principal set is limited to registry-eligible lanes (Q5 lane-eligibility)
  — the delegate broker issues a child grant ONLY to a role-eligible lane (compose with Q5).

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against C3a-2 scope + §9. Build
additionally requires single-use owner activation.
