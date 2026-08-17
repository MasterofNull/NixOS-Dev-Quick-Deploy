---
doc_type: design-packet
id: acp-p3-design-20260816
title: ACP-P3 — runbook automation engine (the crypto the human never touches)
status: draft
parent_prd: approval-control-plane
slice: acp-p3
implementation_authority: cheapest-eligible-implementer-lane
runtime_authority: audited-aq-action-path
reviewer: pending
date: 2026-08-16
---

# ACP-P3 — runbook automation engine

Completes the approve-to-action arc: P0 record -> P1 signer -> P2 surface -> **P3 runs the whole
multi-step crypto sequence the human never sees**. A runbook is the named, idempotent workflow that a
single approval authorizes — activate-signer-service, rotate-key, epoch-revoke, emit-grant,
activate-foundation-c-slice — each wrapping the existing engine ATOMS (aq-provision-signer-key,
aq-epoch-bump, aq-event emit, nixos-rebuild) so the operator never runs them by hand. Ratified PRD R2;
builds on P0 (`dee72d38`) record + `RUNBOOK_REGISTRY` and the P1 signer contract.

## The inversion this delivers
Today an activation is N expert steps (keygen -> SOPS -> allowlist -> hash-bound grant -> bump-sign ->
rebuild -> validate). P3 makes that ONE approved runbook: the human approved a plain-language decision
(P2) with one WebAuthn tap (P1); the engine executes every step, audited, idempotent, resumable —
hidden. That is the whole point of the plane (memory feedback-beginner-friendly-human-control-surface).

## Runbook contract (extends P0's RUNBOOK_REGISTRY)
Each runbook is a registered, reviewed unit — NOT free-form (P0 bounded-action invariant). It declares:
- `name`, `risk_class` (-> summary.impact), `reversible`, typed `param_schema`, `declared_effects`,
  Layer-1 summary templates (all P0-owned, already there).
- `steps[]`: an ordered list of typed step specs, each naming an ATOM + typed args derived ONLY from the
  approved record's params (no runtime injection — P0/P1 hash binds params). Steps that need the owner
  key call the P1 signer (which requires the WebAuthn assertion that already gated this approval);
  no step ever handles private key material directly.
- `verify`: a post-condition check per step + an end-state check (the runbook is done only when its
  effect is real — ties to the Activation Gate / Definition of Done).

## Execution semantics (the hard requirements)
1. **Idempotent + resumable.** Each step records a durable outcome (event log); re-running a
   partially-applied runbook resumes from the first unfinished step, never double-applies. A crash mid
   -runbook leaves a resumable, inspectable state, not a half-broken system.
2. **Audited end to end.** Every step emits an `aq-event` through the existing audited AQ action path
   (integration contract #4). Nothing runs outside the audit log; the operator-context projection shows
   pending -> step k/n -> done/failed.
3. **Authorized once, bound throughout.** The runbook runs against the approved record's hashed params;
   a step cannot widen scope or add an effect not in `declared_effects`. One human approval authorizes
   exactly this runbook with exactly these params (P0 finding #7 + P1 invariant 6).
4. **Fail-closed + intervenable.** A failed step halts the runbook (no blind continue), records the
   failure plainly (P2 shows it), and exposes an operator intervention (retry / abort) — never a silent
   partial success (anti-gaming; ties Root-Cause Discipline).
5. **NixOS-declarative aware.** Runbooks whose effect includes a rebuild (activate-*) commit the Nix
   declaration + trigger the rebuild as a step, so a runtime change is never orphaned from its
   declaration (Rule 13).

## First real target (acceptance)
`activate-signer-service` end-to-end AND `epoch-revoke`: re-provision the C6 production owner key and
fire a revoke ENTIRELY as plain-language taps — the exact expert friction that motivated this plane
(the C6 validation used a throwaway key because the manual path was unusable). When P3 + P1 land, that
becomes: read a card, tap once, done — no SOPS, no age passphrase, no canonical-byte signing.

## Validation goals
- **idempotent-resume** — a runbook interrupted after step k, re-run, completes without double-applying
  (durable per-step outcome asserted).
- **scope-bound** — a runbook cannot execute an effect outside its `declared_effects` or params outside
  the approved hashed set (injection attempt rejected).
- **audit-chain** — a full run emits the complete ordered event chain; the projection reflects each step.
- **fail-closed** — a failing step halts, records a plain failure, offers retry/abort, never continues.
- **signer-gated step** — a step needing the owner key calls the P1 signer and cannot proceed without
  the assertion that gated the approval; no atom exposes private key material to the engine.
- **declaration-coupled** — an activate-* runbook that changes runtime also stages the Nix declaration
  (Rule 13 coupling asserted).

## Review fold — Antigravity (REQUEST REVISION) + local (`vnhp5g`)
Build authorized after these revisions land (orchestrator-verified):
- **[Atom-level idempotency — pre-check gates execution].** Resuming a failed step whose atom did a
  stateful mutate (append a key / a config line) could double-apply. REVISION: every atom implements a
  `verify` PRE-CHECK run BEFORE the action; if it reports the effect already present, the step is SKIPPED
  — independent of the local step log (so a stale/lost log never causes a double-apply). Idempotency is a
  property of the atom's pre-check, not just the engine's checkpoint. (Local `vnhp5g` concurred.)
- **[Parameter injection].** A too-broad param schema could pass a path-traversal or shell-metacharacter
  value through the hash to an atom. REVISION: strict param allowlists (regex + char bounds) in
  `validate_params` (P0 already patterns service names; extend per runbook); atoms NEVER spawn a shell
  (`shell=True` forbidden) and pass array args (`subprocess.run(["cmd", arg])`). No approved value reaches
  a shell string.
- **[Replay to a second run — ALREADY RESOLVED].** Antigravity flagged that a signature over
  canonical_hash unbound to `request_id` is replayable across identical-param requests. This is FIXED
  upstream (commit 117aeb66): `request_id` is now in `CANONICAL_FIELDS`, and P1 keeps a write-once
  executed-request-id ledger. One approval authorizes exactly one runbook run; a copied signature on a
  new request_id neither matches the hash nor passes the executed-id ledger. (Local `vnhp5g`: approval is
  consumed on completion/failure — reinforced.)
- **[Stale-authorization on retry].** A runbook retried hours later must NOT resume on a stale signature.
  REVISION: the retry path re-runs full authorization verification (`verify_execution_authorization`) and
  rejects an expired authorization (ties to P1's challenge/authorization TTL + clock). Resume applies to
  idempotent step progress, never to the authorization itself.
- **[Partial-state semantics] (local `vnhp5g` #4).** Fail-closed halts; because steps are
  idempotent-pre-checked (above), recovery is forward-retry (re-run skips completed steps), not blind
  rollback. Where a step is genuinely non-idempotent, it declares a compensating action; the engine never
  leaves a silent partial success — the operator sees exactly which step k/n halted and why.
- **[Declarative coupling reinforced].** `activate-*` steps update the declarative Nix files + stage +
  `nixos-rebuild switch` — never a transient `systemctl start` that drifts on reboot (Rule 13).

## Scope fence (NOT in P3)
No new UI (P2 renders state), no P1 service internals (calls its contract), no recovery/headless
(P1b/P4). P3 is the runbook registry extension + the idempotent audited executor that runs a runbook's
steps. The stub effects in P0's registry are replaced here by real atom calls, behind the same contract.

## Dispatch (Rule 17)
Architect: this packet (flagship). Build: cheapest healthy implementer whose capability satisfies a
multi-step idempotent orchestrator + atom-integration slice (NOT the orchestrator). Per never-go-down,
review routes to local + Antigravity now; Codex binding on return. Build is gated on P1 landing (signer)
and owner activation; each runbook's first real firing is an owner-approved single-use action.

## Review request (independent, per slice)
Assess: (1) is the idempotent/resumable model sufficient that a crash mid-runbook is always recoverable
without double-apply; (2) can any step widen scope beyond the approved hashed params/declared_effects;
(3) is the signer-gated-step model correct so no atom ever exposes private key material to the engine;
(4) is fail-closed + intervention complete (no silent partial success); (5) does declaration-coupling
fully satisfy Rule 13 for activate-* runbooks.
