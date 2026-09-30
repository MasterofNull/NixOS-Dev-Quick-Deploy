# Interim plan — AI Command Center "approve" button for the kill-lever

Owner decision 2026-09-26: for now, a simple APPROVE button inside the AI command center dashboard.
Defer WebAuthn/biometric, separate webpage, and other auth methods to a later slice. This supersedes the
full-R4 sequencing in this round for the interim; the ACP PRD R2/R3/R4 remains the target end state.

## What this delivers (interim)
- A plain-language **"Fire kill-switch (revoke all agent capabilities until re-approved)"** control in the
  existing command center (dashboard :8888/API :8889), NOT a new webpage.
- On press → backend endpoint runs the already-validated P-F4 flow server-side (allowlist active-key +
  signed epoch bump via the landed `submit --signed --socket`), crypto HIDDEN. No owner CLI, no offline
  keygen — the automation provisions + uses a TPM-held key.

## Security posture (interim — explicitly bounded)
- **Direction is fail-safe:** the button REVOKES (kills) capabilities. An agent pressing it causes at most
  a recoverable capability-revoke (DoS-ish), never an escalation. Acceptable interim risk for THIS button.
- **Guardrail 1 (HARD):** this ungated-button pattern is for the REVOKE/kill direction ONLY. Any
  GRANT / activate / widen-authority action MUST keep an un-forgeable gate (WebAuthn) — never a plain
  button. Enforce in code + review.
- **Guardrail 2:** the owner signing key is generated + held in the TPM (`/dev/tpm0`, active),
  non-exportable — host/service compromise ≠ key theft. (Free hardening; TPM present.)
- **Guardrail 3:** endpoint is fail-closed + audited (every press → `epoch.audit.jsonl` + dashboard
  surface), and rate-limited. The auto-revert guard (Stage 0) remains armed.
- **Tracked debt → ACP PRD:** the un-forgeable human-presence gate (WebAuthn/fingerprint — hardware is
  present, needs `services.fprintd.enable` + rebuild), the dedicated webpage, and grant-direction approvals
  are the deferred R2/R4 items. Log to issues-backlog as interim-limitation, upgrade later.

## Flow (reuses the verified C6c mechanism beneath — no new crypto)
1. One-time setup (automation, not owner CLI): generate the owner epoch key in the TPM; advance allowlist
   rev-4 → rev-5 with its public half (this is P-F4a, now automated + reversible via allowlist-rollback).
2. Command center shows the plain-language button (modal state: visible/enabled only when the lever is
   armed + authority reachable).
3. Press → backend endpoint: sign the canonical bump with the TPM key + submit over the control socket
   (P-F4b) → epoch +1 → leases re-mint → audit receipt + dashboard reflects new epoch.

## Implementation slices (bounded, review-gated)
- S1 (backend): endpoint `/api/aistack/revocation/fire` (fail-closed, audited, rate-limited) that runs the
  TPM-signed bump via the landed socket path. Security-tier → independent review REQUIRED.
- S2 (frontend): the plain-language button + confirm + live epoch/lever state in the command center.
- S3 (setup automation): TPM keygen + allowlist advance (P-F4a) as an idempotent engine atom.
- Route to cheapest-ELIGIBLE implementer. Note: security-enforcement tier → Gemini/Antigravity NOT yet
  eligible (graduated for non-critical tier only); local skipped. Candidate = Claude cheap-tier sub-agent
  (sonnet) with mandatory independent review, or Codex when free. Record the routing reason (Rule 17).

## Gate (unchanged)
Building is dormant/reversible. ACTUAL activation (arming the lever + first real fire) stays the owner's
explicit act, now via the button instead of the CLI. Cohort consensus already 2/2 on the mechanism; this
interim narrows the human process per owner direction.
