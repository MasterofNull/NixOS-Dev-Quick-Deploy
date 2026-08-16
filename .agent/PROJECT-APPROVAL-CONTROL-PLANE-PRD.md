---
doc_type: prd
id: approval-control-plane
title: Approval Control Plane PRD — beginner-friendly human-in-the-loop
revision: R2
status: draft
owner: hyperd
date: 2026-08-15
---

# Approval Control Plane PRD

## 1. Problem + requirement (owner-directed 2026-08-15)
The Foundation C security backend (capability leases, activation grants, SOPS-provisioned signer keys,
offline-signed epoch kill-switch) raced ahead while the HUMAN interface lagged. The current human-in-the-loop
is the WRONG implementation: it makes the human PERFORM cryptography — SOPS edits, age passphrases, Ed25519
keygen, canonical-byte offline signing, hash-bound grant payloads, epoch expected-values. Every activation
this session taught the owner a new incantation, and the last step (find your offline C6 key and sign these
bytes) was flatly unusable. That violates a HARD requirement: **the system must be beginner-friendly, operated
through its own secure automations and control surfaces.** Gates exist to constrain AGENTS, not to impose
cryptographic prerequisites on the human. SSOT: memory `feedback-beginner-friendly-human-control-surface`.

## 2. The inversion
Today: "human authorizes" == "human performs cryptography." Correct: **the human authorizes a plain-language
decision; the system's automations perform ALL cryptography, invisibly.** The security invariants are
PRESERVED (the human authorizes; an autonomous agent cannot forge authorization) but delivered through a
surface a beginner can use with zero system knowledge and zero coaching.

## 3. Requirements
- R1 **Plain-language approvals.** Pending owner authorizations appear in a surface (Command Center / HERDR
  web) as human-readable cards: what, why, impact — no hash, key, path, or CLId shown. A "Details" affordance
  reveals the technical trail for the curious; a beginner never needs it.
- R2 **One un-forgeable, beginner-friendly approve.** The approve action is gated by WebAuthn/FIDO2 (hardware
  security-key tap OR OS biometric — fingerprint/face). Beginner-friendly (everyone knows "tap"/"use your
  fingerprint"); agent-un-forgeable (an autonomous agent has no biometric/hardware presence, needs no TTY,
  and cannot read a secret — unlike a host passphrase, which shares the UID and is visible in `!` input).
- R3 **Automations perform the crypto.** On approve, the engine executes the WHOLE sequence that is today N
  manual expert steps: keygen, SOPS provisioning, allowlist wiring, hash-bound grant emission, bump signing,
  rebuild trigger, validation. Hidden. Idempotent + resumable.
- R4 **WebAuthn-gated signing service.** Owner signing keys (grant authority, epoch kill-switch) are HELD by
  a confined service and used ONLY on a fresh WebAuthn assertion from the human. The agent can invoke the
  service and still cannot obtain a signature (no assertion). Strictly better than "offline key + manual
  signing": the agent cannot fire it AND the human does no crypto. Keys are generated inside the service;
  no agent ever sees private material.
- R5 **Audited + observable.** Every approval + automated action routes through the existing audited AQ paths
  (integration contract #4: human-controls -> audited AQ actions). State is surfaced in the operator-context
  projection (contract #1) — the operator sees pending, in-progress, done, and any drift.
- R6 **No teaching required.** A beginner can operate every control (activate, rotate, revoke, grant) safely.
  Expert CLIs (aq-provision-signer-key, aq-epoch-bump bump, aq-event emit) DEMOTE to internal engine atoms the
  automations call — never the human's interface.

## 4. Architecture (this is the ACTION side of the operator-context / HERDR H2 work — not a new silo)
```
owner (browser/HERDR)  --WebAuthn approve-->  Approval Control Plane
                                                |  (pending queue + audited action router, contract #4)
                                                v
                        Automation engine (runbooks: activate-service / rotate-key / epoch-revoke / grant)
                                                |
                        WebAuthn-gated signing service   +   the existing engine atoms
                        (holds owner keys; signs only        (aq-provision-signer-key, aq-epoch-bump,
                         on a fresh human assertion)          aq-event emit) called internally
                                                |
                        canonical AQ records / activation.grants / epoch authority  (unchanged invariants)
```
- Operator-context projection (contract #1, already ratified) SHOWS the pending/authorized/done state.
- This plane EXECUTES; it never becomes a second authority — canonical AQ records stay authoritative.

## 5. Proposed slices (design -> review -> freeze -> build, per slice)
1. **ACP-P0 — approval record + audited action contract.** The `aq.approval-request.v1` closed schema
   (plain-language summary + technical trail + required-authority + a bounded action manifest) and the
   audited path that executes an approved request. No UI, no WebAuthn yet. Golden vectors + privacy tests.
2. **ACP-P1 — WebAuthn-gated signing service.** Confined service; registers the owner authenticator; holds/
   generates owner keys; signs a bounded request ONLY on a verified fresh assertion; no private material to
   any caller. Hermetic proof: agent-with-no-assertion cannot obtain a signature; wrong/stale assertion denies.
3. **ACP-P2 — the surface.** The Command Center / HERDR web approval queue: plain-language cards, Approve/Deny,
   the WebAuthn prompt, Details drill-in. DOM/accessibility + "a beginner can identify and approve the right
   thing" usability vectors.
4. **ACP-P3 — runbooks.** Named idempotent workflows wrapping the existing atoms: activate-signer-service,
   rotate-key, epoch-revoke, emit-grant, activate-foundation-c-slice. First real test: re-provision the C6
   production owner key + fire a revoke — entirely as plain-language taps.

## 6. Non-negotiable invariants (preserved)
verify != forge; the human authorizes (WebAuthn assertion is the human factor); no autonomous agent can forge
authorization or obtain a signing key; canonical AQ records remain the sole authority; default-OFF + reviewed
+ owner-granted per slice like all Foundation C work.

## 7. Predecessors / relation
Builds on the ratified operator-context contract-zero + integration contract #4 (human-controls). The C6
validation exposed the exact friction this closes; the C6 production owner-key custody is delivered here
(ACP-P1/P3). Immediate blocked-on: independent design review + owner ratification of this PRD before ACP-P0.

## 8. Revision R2 — folds the ACP PRD advisory review (Antigravity, verified)
The R1 review confirmed "RIGHT shape to build" and surfaced real security holes + missing pieces, folded here.

- **WYSIWYS / payload-substitution (HIGH) — R4 tightened.** The signing service must NOT accept
  agent-supplied bytes/hash to sign. It fetches the canonical `aq.approval-request.v1` record ITSELF by
  request-id from a root-owned, agent-inaccessible state directory, parses the plain-language content, and
  derives the WebAuthn challenge FROM that record — so a compromised agent cannot show "approve X" while
  submitting "sign Y". What the human approves in the surface is provably what gets signed.
- **Assertion replay / challenge reuse (MED) — R4.** Every request gets a fresh, single-use, request-bound
  challenge; an assertion is valid for exactly one request-id and is burned on use (durable single-use
  ledger, same pattern as the C2-SCI/epoch replay guards). No assertion can be replayed for another action.
- **NO agent-forceable downgrade/override (HIGH) — invariant added.** There is NO manual offline-signing /
  SOPS-CLI fallback that an agent can force by disrupting the WebAuthn service. The engine atoms
  (aq-provision-signer-key, aq-epoch-bump, aq-event emit) are internal-only, never an operator "emergency
  override" the agent can push the human into. If WebAuthn is unavailable, the system FAILS CLOSED (no
  authorization), never falls back to a crypto-by-hand path.
- **Setup friction (beginner-friendly at step ONE) — ACP-P1.** WebAuthn/FIDO2 device access must be shipped
  DECLARATIVELY in the baseline ai-stack module (udev/pam/`hardware`-level FIDO2 defaults) so the owner never
  configures certs, udev rules, or CLI enrollment. Enrollment is itself a plain-language flow, not a lesson.
- **NEW slice — ACP-P1b lost-authenticator recovery.** Enrollment registers a PRIMARY + at least one BACKUP
  hardware authenticator; a declarative Nix-level recovery bootstrap covers total loss. No single point of
  human-authenticator failure locks the owner out of their own factory.
- **NEW slice — ACP-P4 headless / rescue authorization.** WebAuthn needs a browser; a headless VT / NixOS
  recovery shell cannot show a prompt. Ship a CLI WebAuthn assertion client (`fido2-assert`-based) so the
  owner can authorize a revoke/recover from a rescue console — same request-bound single-use challenge, no
  crypto-by-hand.

Revised slice order: ACP-P0 -> P1 (+P1b recovery) -> P2 surface -> P3 runbooks -> P4 headless rescue.

RECORD: PREPARED_ONLY; independent review + owner ratification required before build. R2 folds the
Antigravity advisory (verified); local review failed transiently (llama.cpp connection drop, model now
healthy) and Codex's binding design review is queued for its return (Aug 21).
