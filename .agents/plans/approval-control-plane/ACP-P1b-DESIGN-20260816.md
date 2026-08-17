---
doc_type: design-packet
id: acp-p1b-design-20260816
title: ACP-P1b — lost-authenticator recovery (no single point of human-factor failure)
status: draft
parent_prd: approval-control-plane
slice: acp-p1b
implementation_authority: cheapest-eligible-implementer-lane
runtime_authority: confined-signing-service
reviewer: pending
date: 2026-08-16
---

# ACP-P1b — lost-authenticator recovery

Refinement of ACP-P1. Closes the single-point-of-failure the PRD R2 review flagged: if the owner's one
security key / biometric device is lost or breaks, they must not be locked out of their own factory —
without opening a soft backdoor an agent can exploit. Builds on P1's signing service + credential
allowlist. Ratified PRD R2 (P1b slice).

## The problem, stated precisely
P1 gates every owner action on a WebAuthn assertion from a registered authenticator. One registered
authenticator = one physical thing that can be lost, stolen, or fail. Recovery must restore the owner's
ability to authorize WITHOUT (a) an agent-forgeable path, (b) the owner performing crypto, or (c) a
long-lived secret sitting where an agent can read it.

## Design — enroll redundancy up front, recover by declaration
1. **Multiple authenticators at enrollment (primary).** P1 registration enrolls a PRIMARY plus at least
   one BACKUP hardware authenticator (both credential ids + public keys in the root-owned allowlist).
   Any registered authenticator can satisfy a `sign_request` assertion. Losing one leaves the others
   fully functional — this is the normal, no-drama recovery path and the default the surface guides the
   beginner to set up ("Add a backup key" during first-run, in plain language).
2. **Declarative recovery bootstrap (total loss).** If ALL authenticators are lost, recovery is a
   DECLARATIVE, physically-present operation, not a stored secret:
   - The owner, at the physical machine (console / boot), runs a recovery bootstrap that enrolls a fresh
     authenticator. Authorization for THIS operation is `sudo`/root on the host console — i.e. physical
     possession of the machine, which an autonomous agent does not have and cannot forge over the UDS.
   - The bootstrap is a NixOS-declarative + activation-script path (Rule 13): the new credential lands in
     the root-owned allowlist via a root-run, console-gated step; no long-lived recovery secret is stored
     anywhere an agent (sharing the primary UID, seeing `!` input) could read it.
   - The recovery enrollment is AUDITED (an event: who/when/which credential) and, ideally, itself
     surfaced for confirmation once a new authenticator is active.
3. **No recovery code / no offline secret.** Explicitly REJECTED: printed recovery codes, a stored
   "break-glass" key, or an SMS/email reset — each is an agent-readable or socially-forgeable secret
   that reintroduces exactly the standing-authorization risk Foundation C removes. Physical-presence
   (host root at the console) is the recovery factor.

## Invariants (preserve P1's guarantees)
- No recovery path is reachable over the signer UDS by an agent; recovery requires host-console root
  (physical presence).
- Recovery never yields a signature or a standing authorization — it only (re)enrolls an authenticator
  the human then uses normally.
- The owner does no crypto: "add a backup key" and "recover at the console" are guided plain-language
  flows; the engine does keygen/allowlist wiring.
- All allowlist mutations (enroll primary/backup/recovery) are audited and default to a state where at
  least one authenticator must always be present (you cannot remove the last one without enrolling a
  replacement in the same operation — no self-lockout, no empty allowlist that fails open).

## Validation goals
- **backup-works** — with primary + backup enrolled, an assertion from the backup satisfies
  `sign_request` identically to the primary.
- **lose-one-safe** — removing/disabling the primary leaves the backup fully functional; no lockout.
- **console-only-recovery** — the recovery bootstrap enrollment is reachable ONLY via host-console root,
  NOT over the UDS; an agent attempting it over the UDS is refused.
- **no-empty-allowlist** — the last authenticator cannot be removed except as part of enrolling a
  replacement (no fail-open empty state).
- **audited** — every enroll/recover emits an audited allowlist-mutation event.
- **no-stored-secret** — a static scan/asserts no printed code / stored break-glass secret exists.

## Scope fence (NOT in P1b)
No new signing logic (reuses P1), no web UI beyond the "add a backup key" + "recover" guided flows (P2
renders them), no headless CLI assertion (that is P4). P1b is the multi-authenticator allowlist model +
the console-gated declarative recovery bootstrap + their audit.

## Dispatch (Rule 17) + gate
Architect: this packet (flagship). Build: cheapest healthy implementer (NOT orchestrator). Owner directive
2026-08-16: Antigravity(+local+orchestrator) review completing authorizes the build; Codex confirmatory on
return. Build pairs with P1 (shares the allowlist + service).

## Review request
Assess: (1) is multi-authenticator + console-gated declarative recovery genuinely free of an
agent-forgeable path; (2) is "physical host root = recovery factor" sufficient and correctly
un-spoofable over the UDS; (3) does the no-empty-allowlist rule fully prevent both self-lockout AND a
fail-open empty state; (4) any recovery step that stores an agent-readable secret or lets recovery yield
a standing authorization.
