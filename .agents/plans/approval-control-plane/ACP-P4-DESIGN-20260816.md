---
doc_type: design-packet
id: acp-p4-design-20260816
title: ACP-P4 — headless / rescue authorization (authorize without a browser)
status: draft
parent_prd: approval-control-plane
slice: acp-p4
implementation_authority: cheapest-eligible-implementer-lane
runtime_authority: confined-signing-service
reviewer: pending
date: 2026-08-16
---

# ACP-P4 — headless / rescue authorization

Refinement of ACP-P1/P2. Lets the owner authorize a critical action (above all: an epoch revoke / kill
-switch) when there is NO browser — a headless VT, an SSH session, or a NixOS recovery shell — using the
SAME security guarantees as the web path. Builds on P1's signer + challenge/ledger model. Ratified PRD
R2 (P4 slice).

## Why this exists
P2's approve flow is a browser WebAuthn ceremony. But the moment you most need to revoke (the GUI is
down, the box is in a bad state, you're on a rescue console) is exactly when no browser is available.
Without P4 the beginner-friendly control has a hole precisely at the emergency. P4 fills it WITHOUT a
crypto-by-hand fallback (which PRD R2 invariant forbids as an agent-forceable downgrade).

## Design — a CLI WebAuthn client, same ceremony minus the browser
1. **`aq-approve` CLI (owner-run, console).** Lists pending `aq.approval-request.v1` requests in plain
   language (same Layer-1 rendering as P2 — title/what/why/impact; NO hashes/keys in the default view,
   Details flag for Layer-3). `aq-approve <request_id>` runs the FIDO2 assertion locally via
   `fido2-assert`/python-fido2's hidraw client against the SAME challenge the P1 signer derives
   (canonical_hash + request_id + nonce), and hands the assertion back to the signer over the UDS.
2. **Identical signer path.** The signer does NOT branch for headless: it fetches the record itself,
   derives the same request-bound challenge, verifies the same registered-credential single-use
   assertion, and signs the same request_id-bound canonical_hash. P4 changes only WHERE the human factor
   ceremony runs (hidraw CLI vs browser), never the authorization semantics — so WYSIWYS, single-use,
   fail-closed, and no-downgrade all hold unchanged.
3. **Physical presence, not a stored secret.** The owner still taps a registered hardware authenticator
   (user_verification required). The CLI is a transport for the human factor, not a bypass: no
   passphrase, no key file, no offline signing — an agent running `aq-approve` still cannot produce the
   assertion (no hardware, no biometric, no user-verification).
4. **Rescue-console note.** In a NixOS recovery shell the confined signer may not be running; document
   the minimal bring-up (start the signer + epoch authority as a rescue target) so a revoke is possible
   from rescue — still gated by the hardware assertion, still audited.

## Invariants (same as P1 — P4 must not weaken them)
- No crypto-by-hand: `aq-approve` triggers the FIDO2 hardware ceremony; it never accepts a passphrase or
  a key file as a substitute for the assertion (that would be the agent-forceable downgrade PRD R2
  forbids).
- Same single-use request_id-keyed challenge + executed-id ledger — a headless approval is as
  replay-proof as a browser one.
- Same plain-language rendering + privacy boundary — the CLI shows Layer-1 by default, never dumps
  crypto to the terminal.
- Agent-invocable, not agent-forgeable: an agent may run `aq-approve` but cannot complete the hardware
  user-verification, so it gets no signature.

## Validation goals
- **headless-happy-path** — `aq-approve <id>` with a (software-authenticator, test-only) assertion over
  the real challenge yields a signature via the same signer path as the browser flow.
- **same-guarantees** — the headless path reuses the P1 single-use + executed-id ledgers; a replay or a
  tampered record is refused identically to the browser path (shared test vectors).
- **no-passphrase-fallback** — `aq-approve` offers NO passphrase/key-file mode; a static + behavioral
  check confirms the only path is the hardware assertion.
- **plain-language-cli** — the listing/approve output is Layer-1 plain language; no hex/key/path in the
  default view (Details flag only).
- **agent-cannot-complete** — an assertion attempt with no user-verification / no registered credential
  is refused.

## Scope fence (NOT in P4)
No new signing semantics (reuses P1), no web UI (P2), no recovery enrollment (P1b), no runbook engine
(P3). P4 is the `aq-approve` headless CLI client + the rescue bring-up doc, over the existing signer.

## Dispatch (Rule 17) + gate
Architect: this packet (flagship). Build: cheapest healthy implementer (NOT orchestrator). Owner directive
2026-08-16: Antigravity(+local+orchestrator) review completing authorizes the build; Codex confirmatory on
return. Build depends on P1 (the signer + ledgers it drives).

## Review request
Assess: (1) does the CLI truly reuse the identical signer path so headless has the same guarantees as the
browser; (2) is there ANY passphrase/key-file/offline path that would be an agent-forceable downgrade;
(3) is the rescue-console bring-up itself free of a crypto-by-hand step; (4) does the CLI keep the
plain-language/privacy boundary; (5) can an agent running aq-approve ever obtain a signature.
