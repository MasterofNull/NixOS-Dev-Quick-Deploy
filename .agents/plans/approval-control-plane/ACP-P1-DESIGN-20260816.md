---
doc_type: design-packet
id: acp-p1-design-20260816
title: ACP-P1 — WebAuthn-gated signing service
status: draft
parent_prd: approval-control-plane
slice: acp-p1
implementation_authority: cheapest-eligible-implementer-lane
runtime_authority: confined-signing-service
reviewer: pending
date: 2026-08-16
---

# ACP-P1 — WebAuthn-gated signing service

Second slice of the Approval Control Plane. Builds on ACP-P0's `aq.approval-request.v1` record
(`scripts/ai/lib/approval_request.py`, committed `dee72d38`). Delivers the confined service that turns a
human's WebAuthn tap into a signature over a bounded request — so the human authorizes a plain-language
decision and does NO crypto, while an autonomous agent (no hardware, no biometric, no TTY) cannot forge
authorization. Ratified PRD: `.agent/PROJECT-APPROVAL-CONTROL-PLANE-PRD.md` (R2).

## The one job
An agent submits a `request_id`. A human taps their security key / uses biometric. The service returns
an Ed25519 signature over that request's canonical hash — and ONLY then. No assertion → no signature.
Wrong/replayed/stale assertion → no signature. Agent-substituted payload → impossible (the service
fetches the canonical record itself).

## Architecture
```
agent  --sign(request_id)-->  acp-signer.service (confined; holds owner key)
                                  1. fetch aq.approval-request.v1 record BY request_id from the
                                     root-owned, agent-inaccessible request store
                                  2. re-validate() + recompute canonical_hash (P0 lib); abort on drift
                                  3. derive a fresh WebAuthn challenge from canonical_hash + a nonce
                                  4. prompt the human authenticator (P2 surface / CLI in P4) -> assertion
                                  5. verify the assertion: registered credential, our challenge, one-time
                                  6. burn the challenge in a durable single-use ledger keyed on request_id
                                  7. sign canonical_hash with the held owner Ed25519 key -> return sig
```
The owner signing key (grant authority / epoch kill-switch key) is HELD by this service and used ONLY
inside step 7, only after step 5 passes. No caller ever receives private material.

## Non-negotiable invariants (from PRD R2, made concrete)
1. **WYSIWYS — the service fetches the canonical record itself.** It NEVER signs caller-supplied bytes
   or a caller-supplied hash. Input is a `request_id` only; the bytes signed are `canonicalize(record)`
   recomputed from the record the service loaded from the root-owned store. A compromised agent showing
   "approve X" cannot make the service sign "Y".
2. **Challenge bound to the request + single-use.** The WebAuthn challenge is derived from
   `canonical_hash` + a per-request server nonce; the assertion is valid for exactly one `request_id`
   and is BURNED on use in a durable ledger (same fail-closed single-use pattern as
   `revocation_epoch`/C2-SCI). Keyed on `request_id` (NOT `canonical_hash` — P0 note: two distinct
   requests with identical content share a content-hash, so the replay guard must key on the id).
3. **No agent-forceable downgrade.** There is NO manual/offline/SOPS-CLI signing fallback the agent can
   force by disrupting the service. If WebAuthn verification is unavailable or fails, the service
   returns a typed denial and signs NOTHING (fail closed). The engine atoms
   (aq-provision-signer-key/aq-epoch-bump) remain internal, never an operator "override".
4. **Confinement.** Dedicated system user, key material SOPS -> `/run/secrets` mode 0400 owned by the
   service user, UDS 0660 + a client group, NoNewPrivileges, ProtectSystem=strict, ProtectHome, private
   tmp, default `enable=false`. The request store is root/service-owned; the requesting agent can APPEND
   a request but cannot mutate one or read the authority's view (P0 invariant 6).
5. **Agent-invocable, not agent-forgeable.** The agent may call `sign(request_id)`; without a human
   assertion it provably cannot obtain a signature. Hermetic proof required (below).
6. **`status` is NOT an authorization signal — the signature is** (folds ACP-P0 confirmatory review,
   local Qwen `qopywx`). The canonical_hash deliberately excludes `status`, so `status` is bookkeeping,
   not integrity-protected content. P0's executor gates on `status == "approved"` as a trusted stub
   (approval_executor.py:123), relying on the record store being authority-only-writable. P1 makes the
   gate cryptographic: **the executor requires a valid owner signature over `canonical_hash` (produced
   by this WebAuthn-gated service) as the authorization to execute — it MUST NOT execute on `status`
   alone.** A forged `pending->approved` flip in the store therefore grants nothing without the
   signature the agent cannot obtain. `status` integrity is still defended in depth by the append-only
   root-owned store (invariant 4), but authorization no longer depends on it. This closes the
   status-forgery concern cryptographically rather than by store ACLs alone. P1 adds a
   `verify_execution_authorization(record, signature)` step to the executor contract; `status` becomes
   a derived reflection of "a valid signature exists", never the source of truth.

## WebAuthn specifics
- Library: `python-fido2` (server-side assertion verification) — add to the service's Nix python env
  (declarative, per the tier0 dep lesson). Registration (P1) stores the credential public key + id in a
  root-owned allowlist (mirrors the signer-key allowlists); relying-party id is the local origin.
- `user_verification=required` (biometric/PIN), so a mere touch without the user factor is insufficient.
- Declarative FIDO2 device access (PRD R2 setup-friction fold): ship the udev/pam FIDO2 defaults in the
  ai-stack module so the owner does not configure device access by hand.

## Test / validation strategy (no physical key in CI)
WebAuthn crypto is exercised with a SOFTWARE authenticator (`python-fido2` provides a software
`Fido2Client`/virtual authenticator) — a real assertion over our real challenge, verified by the real
server code. Validation goals:
- **wysiwys-fetch** — service signs `canonicalize(loaded_record)`; a caller passing bytes/hash that
  differ from the stored record's cannot influence what is signed (input is only `request_id`).
- **no-assertion-no-signature** — `sign(request_id)` with no/absent assertion returns a typed denial,
  signs nothing.
- **wrong-credential / wrong-challenge** — an assertion from an unregistered credential, or bound to a
  different request's challenge, is rejected.
- **single-use replay** — a valid assertion replayed for a second `sign` (same or different request) is
  rejected; ledger burn is durable across a service restart.
- **tamper-abort** — a request whose stored `binding.canonical_hash` ≠ recompute aborts before any
  challenge is issued (reuses P0 `validate`/`compute_hash`).
- **no-downgrade** — with WebAuthn verification forced unavailable, the service fails closed (no
  fallback signing path exists to exercise).
- **confinement** — the agent user cannot read the key file or the request store's authority view
  (DAC + namespace), only the UDS.

## Review fold — local Qwen (`6so7v7`, verdict: WYSIWYS/replay/downgrade sound; 3 hardenings)
- **`request_id` must be high-entropy + unpredictable (finding 4a).** The single-use replay ledger keys
  on `request_id`, so it MUST be a cryptographically strong, non-guessable id (ULIDv... or UUIDv4, ≥122
  bits), server/authority-assigned at request creation, never caller-chosen. A predictable id would let
  an agent pre-burn or collide ledger slots. The owner Ed25519 key stays inside the confined service and
  is never extractable; a signature is only ever produced under a fresh human assertion.
- **Challenge validity window + clock-skew (finding 4b).** Each WebAuthn challenge carries a short TTL
  (e.g. 120s) with a bounded clock-skew tolerance; an assertion presented after the window is rejected
  (fail closed) and the challenge is burned. Time is monotonic-server-authoritative, not client-supplied.
- **Attestation posture is an explicit registration control (finding 3).** The python-fido2 software
  authenticator proves the PROTOCOL logic (challenge binding, single-use, signature) hermetically, but
  NOT hardware isolation / device-identity binding. Registration (P1) records the decision: for the
  local single-user factory, verify attestation where the authenticator provides it and bind the
  credential id + public key in the root-owned allowlist; document accepted residual risk where
  self-attestation is used. The test suite asserts protocol correctness; hardware-attestation strength
  is a registration-time control, called out so it is a conscious choice, not an unexamined gap.

## Review fold — Antigravity (verdict REQUEST-REVISION; 1 CRITICAL fixed + 4 hardenings)
Independent security review, orchestrator-verified. Findings folded:
- **[CRITICAL — FIXED in P0 code] Cross-request signature reuse.** The signature was over
  `canonical_hash`, which excluded `request_id`, while the single-use ledger keyed on `request_id` — so
  a signature from one approval was replayable against a content-identical sibling request (different
  id, never itself approved). FIX (applied to `scripts/ai/lib/approval_request.py`): `request_id` added
  to `CANONICAL_FIELDS` (it is immutable → no recompute-drift; only `status` stays excluded). Signature
  is now bound to the request instance; golden hash re-pinned; regression test `test_request_id_binding`
  added. Invariant 2 updated: the signed material is now inherently per-`request_id`.
- **[HARDENING] Executor-side append-only executed-request ledger.** Beyond the assertion single-use
  ledger, the executor keeps a root-owned append-only ledger of executed `request_id`s; re-submitting an
  already-executed id (or a record rewritten back to `approved`) ABORTS before signature verification.
  Defends against execution-history rewrite → signature reuse.
- **[HARDENING] Prompt-fatigue DoS.** An agent with UDS access could flood `sign(request_id)` and spam
  the operator with authenticator prompts. Enforce strict rate-limiting + max ONE concurrent active
  signing session on the signer UDS.
- **[HARDENING] No software-authenticator in production (sharpens local #3 + invariant 3).** The
  python-fido2 software/virtual authenticator used by the test suite MUST be excluded from the
  production build entirely (build-time/module guard) — NEVER reachable via a runtime env/config flag,
  or a compromised agent could force acceptance of a simulated key. Downgrade stays impossible.
- **[HARDENING] Post-deploy hardware-boundary diagnostic.** The in-memory suite proves protocol/crypto;
  add a post-deploy diagnostic asserting the systemd unit has the correct udev tags + hidraw device
  group permissions (pairs with the declarative FIDO2 setup).
- **[NOTE] WYSIWYS completeness.** Layer-1 `summary` is already a deterministic projection of
  `action_manifest` params (P0 #7), so the executed action cannot diverge from the shown text;
  `technical_trail` is hashed but non-executed metadata. The surface (P2) still renders/attests the full
  set of hashed fields on the confirmation path so nothing hashed is unseen.

## Scope fence (NOT in P1)
No web UI (P2), no lost-authenticator recovery / backup keys (P1b), no headless `fido2-assert` CLI
(P4), no runbook automation engine (P3). P1 is the signing service + registration + WebAuthn verify +
single-use ledger + confinement, with the software-authenticator test suite.

## Dispatch (Rule 17)
Architect: this packet (flagship). Build: cheapest healthy implementer lane whose capability satisfies
a confined-service + crypto slice (NOT the orchestrator). Per never-go-down, design review routes to
local + Antigravity now; Codex binding on return. Build follows an owner-granted, single-use activation
of the confined service (default-OFF until then), like all Foundation C confined services.

## Review request (independent, per slice)
Assess: (1) does step 1-2 (fetch-by-id + recompute) fully close WYSIWYS, or can a caller still influence
the signed bytes; (2) is challenge-derivation-from-canonical_hash + request_id-keyed single-use ledger
sound against replay AND against the content-hash-collision note; (3) is the confinement model
sufficient that a compromised agent user cannot reach the key or forge an assertion; (4) any downgrade
path that an agent could force; (5) is the software-authenticator test strategy a faithful proof.
