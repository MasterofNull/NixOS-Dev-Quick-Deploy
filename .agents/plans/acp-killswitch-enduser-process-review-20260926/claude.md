# Design contribution — claude (Opus 4.8), lens: product + operator-experience + security

## Disposition: PLAN_READY_WITH_FOLLOWUPS
The ACP R2/R3/R4 approach IS the right end-user process. Recommend HOLDING P-F4 activation until the
smallest ACP slice (WebAuthn-gated epoch-switch signing + a minimal approve surface) is built — do NOT
ship the CLI ceremony as the operator UX. Three security followups must be nailed in that slice.

## Q1 — Is R2/R3/R4 the right end-user process? YES.
It correctly inverts the broken model ("human authorizes = human performs crypto") into "human approves a
plain-language decision; automations do all crypto." WebAuthn/biometric is genuinely beginner-friendly
(everyone knows "tap"/"use your fingerprint") AND agent-un-forgeable (an autonomous agent has no
biometric/hardware presence). Gaps to close, all operator-experience:
- **Enrollment** — first-time authenticator registration is itself a step; it must be beginner-friendly
  and one-time, not a new incantation.
- **Recovery** — a kill-switch you cannot fire because you lost your security key is a SAFETY failure.
  Needs a recovery path (a second registered authenticator / backup) that stays agent-un-forgeable.
- **Informed consent** — the approve surface must state in plain language WHAT is being approved
  ("Fire the fleet kill-switch: revokes all agent capabilities until re-approved"), not an opaque "Approve".

## Q2 — Sequencing: HOLD. Build the slice before P-F4.
Activating via the CLI ceremony now ships exactly the UX this PRD calls "WRONG," creates a kill-switch
only the owner-as-cryptographer can fire (fragile in a real incident — the moment you MOST need it, you
are hunting for an offline key and hand-signing), and would be re-cut later anyway. The lever is not
urgent — the system is safe/inert, no live threat. CLI-interim is only justified if we needed the lever
LIVE imminently; we do not. So hold. (This also aligns with commit-non-perfect / gate-activation: the
mechanism is committed + dormant; we simply do not switch on the wrong human process.)

## Q3 — Security: can be EQUAL-OR-BETTER, only with 3 conditions.
On the agent-cannot-fire axis the confined WebAuthn-gated service is STRONGER (agent has no assertion →
cannot sign) AND removes the human-crypto burden. But it moves the key ONTO the host, which the offline
model deliberately avoided. Equivalence holds ONLY if:
1. **Hardware-backed, non-exportable key** — key generated + held in TPM/secure-enclave (or a confined
   0700 non-exportable store), so host/service compromise ≠ key theft. This is THE critical tradeoff vs.
   the air-gapped offline key; without it, service-held is weaker at-rest.
2. **Action-bound assertion** — the WebAuthn challenge = hash of the EXACT decision/bump bytes, so a
   captured assertion cannot be replayed for a different action.
3. **Fail-closed** — no assertion → no signature, ever; no passphrase/fallback signing path the agent
   could drive.

## Q4 — Smallest first slice
Reuse the entire verified C6c mechanism underneath; the ACP becomes only the human front-door:
1. A WebAuthn-gated signing service holding ONE key (the epoch-bump owner key), generated in-service,
   hardware-backed where available.
2. A minimal approve surface (a single local dashboard page) showing the plain-language decision + an
   approve button that triggers the WebAuthn assertion.
3. One engine atom: on a valid action-bound assertion, run the already-landed P-F4a/b internally
   (allowlist advance rev-4→rev-5 + `submit --signed --socket`). No new crypto for the human.
Defer: grant-authority signing, SOPS-provisioning automation, the full R3 multi-step sequence — after the
epoch-switch slice proves the pattern.

## Q5 — Beginner reachability (owner-input needed)
WebAuthn needs a browser + a registered authenticator (platform biometric OR roaming key). MUST confirm
THIS host/owner has a usable one — does the machine have a fingerprint reader / TPM platform
authenticator, or does the owner hold a security key? If neither, "beginner-friendly" needs a fallback
that stays agent-un-forgeable (hard — a passphrase is forgeable by an agent with host access). Verify with
the owner before committing WebAuthn as THE gate.

## Net recommendation
Adopt ACP R2/R3/R4 as the end-user process; HOLD the CLI P-F4 activation; build the smallest slice
(epoch-switch WebAuthn signing service + minimal approve surface, reusing C6c beneath); close the 3
security conditions in that slice; confirm authenticator availability with the owner first.
