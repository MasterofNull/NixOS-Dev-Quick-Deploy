# Foundation C C3a-2 — Codex Depth Review

Review date: 2026-08-01 UTC  
Reviewer: `codex-orchestrator`  
Role: independent binding architecture/security/SRE reviewer  
Verdict: **REQUEST_REVISION**

## Exact subject

- Design: `.agents/plans/aqos-foundation-c/C3A-2-DESIGN-AND-AUTHORIZATION.md`
- Design SHA-256:
  `3ff34439944d660d49c11385840e71ef640df4738055e09e4af3f299f3741b92`
- Reviewed HEAD:
  `e7bf91deb4693a6667cd3c3ed10b0988b4143ef6`

This is a read-only design verdict. It grants no build, staging, commit,
deployment, flag, traffic, or activation authority.

## Blocking findings

### 1. The proposed child-grant operation does not exist

The design says the broker attenuates a `VerifiedGrant` through R1
`execution_grant` / `capability_lease.attenuate`. Those are different
artifacts. `scripts/ai/lib/execution_grant.py` has no grant-attenuation
operation, while `capability_lease.attenuate` produces a symmetric-HMAC
`CapabilityLease`, not an Ed25519 `ExecutionGrant`. The execution-grant schema
also denies the `delegate` effect and contains no signed `allowed_gap`, remote
principal, quarantine reference, or expected-output fields.

Required revision: define one closed, domain-separated child-delegation grant
schema and pure attenuation function that proves every authority-bearing
field is a subset of its parent. Pin signer/key IDs, issuer chronology,
resource/output bounds, lane eligibility, deadline, heartbeat policy, and
replay identity. Do not cast a `CapabilityLease` into an `ExecutionGrant`.

### 2. Heartbeat signing contradicts the stated trust model

The remote lane has no trusted local private key, yet the design requires
remote-execution heartbeats to be signed. A local broker signature made after
receipt proves only that the broker observed supplied values; it does not
prove remote liveness or origin. An untrusted transport writer could fabricate
or replay heartbeat sequences unless the submission is bound to an
authenticated dispatch session and a broker-issued challenge.

Required revision: either define authenticated remote response signatures
with provider/lane key identity and rotation, or explicitly classify
heartbeats as transport observations and derive acceptance only from a
locally supervised, nonce-bound session. Bind every heartbeat to the child
grant digest, dispatch receipt, nonce, remote principal, sequence, and trusted
receipt clock. Unknown or unavailable identity must deny.

### 3. Quarantine intake is not a complete safe transport contract

“Receives a quarantine drop path” does not define how a remote principal can
write without gaining a host path or authoritative filesystem access. It also
does not freeze byte/record size, file count, type, ownership, symlink/hardlink
policy, open semantics, partial-write completion, or replacement races. A
path-based read followed by a later commit permits TOCTOU unless verification
and import use the same immutable bytes or descriptor.

Required revision: define a bounded broker-owned inbound transport and
content-addressed blob protocol. Acquire with `openat2`-equivalent beneath / no
symlink semantics, require regular immutable completed input, hash and import
the same descriptor/bytes, and quarantine malformed/oversized/late inputs.
Never expose or trust an arbitrary host path from the remote lane.

### 4. Delegate authorization and cell-write authorization are conflated

R1 deliberately rejects the `delegate` effect, while the current R5 adapter
only mints a write-cell grant for `write_file`. A child grant authorizing
remote delegation cannot automatically become authority to write returned
bytes. Conversely, requiring the parent to include write authority may widen a
delegate-only request.

Required revision: define the two-step authority composition explicitly:
delegation authority permits remote computation and bounded return only; a
separate locally issued import grant permits exactly the verified output to an
already-authorized cell-relative path. Prove the import cannot exceed the
parent's declared output/path/effect envelope and cannot auto-merge.

### 5. The replay store cannot be an implicit extension of the inbox script

`aq-antigravity-inbox` is an advisory inbox CLI with task-ID receipt files.
Its private `_locked` helper is not a stable shared broker API, and the design
does not specify a closed reservation schema, lock filename derivation,
revision/CAS rules, durability, ownership, terminal idempotency, or recovery
ordering for the composite delegation key.

Required revision: define a versioned broker reservation API/store (it may
reuse the proven stable-lock + fsync + replace pattern) with one writer,
collision-resistant canonical key derivation, monotonic revisions, and
idempotent `reserved -> committed|failed` transitions. Advisory inbox receipts
remain transport projections, not delegation authority.

### 6. Prerequisites, exact inventory, and Service Coverage are incomplete

The live baseline has the R5 adapter and runner dormant after a failed shadow
deployment; runner-deployment-hardening and C4 are prerequisites, not optional
context. The ceiling omits exact hashes, names no receipt-schema path, and
contains no dashboard/API or integration `aq-qa` coverage. It also leaves Q5
lane-eligibility input unbound.

Required revision: gate C3a-2 behind independently accepted runner hardening,
a successful live cell exercise, C4 network-profile enforcement, and the
required R5 attach path. Freeze exact file hashes/absences and the immutable
lane-eligibility revision. Add same-release API, dashboard, and integration
`aq-qa` evidence for broker flag/effective state, denials, replay/heartbeat
states, quarantine/import outcomes, and operator intervention without paths,
prompts, content, keys, or high-cardinality labels.

## Open-question adjudication

- Q-C3a2-1: **Do not import the private inbox lock helper.** Reuse its durable
  algorithm only behind a versioned delegate-reservation module and schema.
- Q-C3a2-2: **Use the R3 runner / R5 adapter path only after runner hardening
  and live exercise.** Direct in-process R2 import is rejected because it
  bypasses the single confinement chokepoint.
- Q-C3a2-3: **Yes, deny unless the remote lane is currently eligible under a
  hash-bound registry snapshot and the authenticated response principal
  matches the dispatched principal.**

## Final verdict

**REQUEST_REVISION.** The intended quarantine → local verification → confined
cell → retained-for-review sequence is directionally correct, but the current
packet lacks a real child-grant attenuation contract, authentic heartbeat
semantics, race-safe inbound transport, separated import authority, a durable
reservation API, current prerequisites, and mandatory Service Coverage. No
build or activation may be derived from this review.
