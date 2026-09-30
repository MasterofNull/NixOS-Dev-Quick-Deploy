---
round: acp-killswitch-enduser-process-review-20260926
type: "design-review (END-USER PROCESS, not mechanism)"
lens: "product + operator-experience + security (crypto-hidden) — NOT the systems/correctness lens"
disposition_options: [PLAN_READY, PLAN_READY_WITH_FOLLOWUPS, PLAN_BLOCKED, PLAN_REJECTED]
subject: ".agent/PROJECT-APPROVAL-CONTROL-PLANE-PRD.md (status: draft) + the C6 owner-key kill-lever (P-F4)"
gate: "Advisory design review. Nothing activates. Output = concrete end-user-process options + a
       recommended sequencing, for the owner to choose."
roster: "claude (now), antigravity/gemini (inbox). Codex queued (advisory). local skipped."
---

# Design-review — beginner-friendly end-user process for the C6 kill-lever (P-F4)

## Why this round exists (owner-raised 2026-09-26)
The agents planned + built the C6 kill-lever mechanism and reached activation-readiness consensus, but
the OWNER never had input on whether the END-USER PROCESS is acceptable for their design. It is not: the
current process makes the human perform expert crypto (offline Ed25519 keygen, air-gapped signing,
`aq-epoch-bump submit --signed --socket`), which violates the owner's HARD principle — humans act through
beginner-friendly CONTROL SURFACES (plain-language approve, crypto hidden), not expert CLI/keys.

## The subject is an EXISTING draft PRD (do not redesign from scratch — evaluate it)
`.agent/PROJECT-APPROVAL-CONTROL-PLANE-PRD.md` (status: draft) already diagnoses this exact gap and
proposes:
- **R2** one un-forgeable beginner-friendly approve, gated by WebAuthn/FIDO2 (hardware-key tap OR OS
  biometric); agent-un-forgeable (no biometric/hardware presence).
- **R3** automations perform ALL crypto on approve (keygen, provisioning, allowlist wiring, grant
  emission, bump signing, rebuild, validation) — hidden, idempotent, resumable.
- **R4** a WebAuthn-gated signing service holds owner keys (grant authority + epoch kill-switch), used
  ONLY on a fresh WebAuthn assertion; the agent can invoke it but cannot obtain a signature. Keys are
  generated inside the service. Strictly better than "offline key + manual signing."
- Demotes `aq-provision-signer-key`, `aq-epoch-bump bump`, `aq-event emit` to internal engine atoms.
- Explicitly states the C6 production owner-key custody is delivered HERE.
- Current build state: **no UI, no WebAuthn yet** — golden vectors + privacy tests only.

## Questions for each lane (evaluate from product + operator-experience + security)
1. **Is R2/R3/R4 the right end-user process** for operating the kill-lever — genuinely beginner-friendly
   (a non-expert can activate + fire it), and does it meet the owner's control-surface bar? Gaps?
2. **Sequencing decision.** Should P-F4 (kill-lever activation) WAIT for the ACP to deliver at least the
   R4 WebAuthn-gated signing path for the epoch switch — OR is a documented CLI interim acceptable, with
   the surface as a fast-follow? State the risk each way.
3. **Security equivalence/'better'.** Does "keys generated + held in a WebAuthn-gated confined service"
   actually preserve the no-standing-auth / agent-cannot-fire / no-API-key invariants at least as well as
   the offline-key model? Any weakening (service compromise, assertion replay, key-at-rest)?
4. **Smallest first slice.** What is the smallest ACP slice that makes P-F4 a beginner-friendly "approve"
   (e.g. R4 signing service for the epoch bump + a minimal approve surface), deferring the rest?
5. **Beginner reachability.** WebAuthn/biometric needs a browser/registered authenticator. Is that
   reachable for THIS owner/host, or is a fallback needed? Does it stay agent-un-forgeable?

## Output
Each lane writes `.agents/plans/acp-killswitch-enduser-process-review-20260926/<agent>.md`: a disposition
+ per-question reasoning + a concrete recommended end-user process + the smallest first slice. Orchestrator
aggregates into options + a recommendation for the owner to choose.
