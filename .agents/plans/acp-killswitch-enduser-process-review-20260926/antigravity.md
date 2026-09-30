# Design Contribution — Antigravity / Gemini (Google Lane)
**Round**: `acp-killswitch-enduser-process-review-20260926`  
**Lens**: Product + Operator-Experience + Security (Crypto-Hidden UX)

---

## 1. Disposition: `PLAN_READY_WITH_FOLLOWUPS`

Antigravity votes **PLAN_READY_WITH_FOLLOWUPS**. The owner's foundational UX principle must be honored: **humans govern via intuitive, beginner-friendly control surfaces; autonomous agents and background automations perform all cryptographic mechanics under the hood.** 

We strongly recommend **HOLDING** live P-F4 activation until the minimal WebAuthn-gated ACP signing slice is integrated. Shipping an emergency kill-switch that demands offline terminal cryptography is self-defeating: in a real runaway fleet incident, stress and friction will cause catastrophic delay or operator error.

---

## 2. Per-Question Evaluation

### Q1 — Is R2/R3/R4 the right end-user process?
**YES.** Genuinely beginner-friendly.
- **Cognitive Inversion**: Shifting from "operator acts as cryptographer" to "operator authorizes an intent via physical presence" aligns 100% with modern consumer-grade security (TouchID, YubiKey, Passkeys).
- **Blast Radius Transparency**: The control surface must display plain-English operational impacts (*"Kill-Switch: Revoking Epoch 4 → Epoch 5. All active sub-agents will be immediately severed."*), rather than raw hex keys or socket paths.
- **Identified UX Gaps**:
  1. **Transient Timeout Handling**: WebAuthn browser prompts can time out. The UI must cleanly handle user cancellation/timeout without putting the harness into a broken intermediate state.
  2. **Audit Telemetry**: The instant a kill assertion is submitted, both the Dashboard GUI (`dashboard.html`) and the terminal workspace (`aq-workspace` / `aq-cockpit-monitor`) must flash a global visual lockout banner confirming fleet cessation.

### Q2 — Sequencing Decision: HOLD P-F4 Until ACP Slice is Ready
**Recommendation: HOLD.**
- An emergency control must be operable by the human who owns the system in under 5 seconds under acute stress.
- A manual offline CLI ceremony is an expert mechanism, not an emergency brake. If deployed now, the owner will either fail to fire it when needed or will bypass it.
- Because the system is currently safe, dormant, and bounded in local dev, there is no active adversary forcing an immediate emergency deployment of the expert CLI procedure. We should land the beginner-friendly ACP slice first.

### Q3 — Security Equivalence / 'Better'
**STRONGER in practice, provided 3 architectural invariants are enforced:**
1. **Physical Presence Invariance**: An autonomous software agent running on the host cannot simulate physical capacitive touch on a hardware security key or OS biometric sensor.
2. **Payload-Bound Challenge**: The WebAuthn cryptographic challenge must be the SHA-256 digest of the exact epoch bump payload (`epoch_target`, `timestamp`, `initiator`). This makes assertion replay mathematically impossible across different epochs or actions.
3. **Confined Daemon Jail**: The signing key must reside in a dedicated systemd service (`ProtectSystem=strict`, `PrivateTmp=true`, `NoNewPrivileges=true`, `ProtectHome=read-only`) accessible only via an unprivileged local domain socket. Host agents cannot extract the raw private key from disk or memory.

### Q4 — Smallest First Slice (MVP)
Build only what is strictly required to replace manual CLI signing for the epoch bump:
1. **Engine Layer**: Confined signer service (`aq-acp-signer`) holding the single epoch-bump private key. It signs an epoch bump only upon receipt of a valid, challenge-verified WebAuthn assertion.
2. **UI Layer**: A prominent, protected "Emergency Fleet Revocation" button on `dashboard.html` (and mirrored in `aq-workspace` cockpit).
3. **Execution**: One-click browser WebAuthn prompt → signature generated in backend → existing verified C6c engine executes `aq-epoch-bump submit` over the socket.
*Defer*: Complex multi-tenant grant delegation, SOPS re-encryption cascades, and secondary operator quorum.

### Q5 — Beginner Reachability
- Standard Chromium / Firefox browsers on Linux provide native WebAuthn/FIDO2 support out of the box.
- The owner's ThinkPad hardware supports USB FIDO2 keys (YubiKey/SoloKey) and Linux-compatible platform authenticators.
- **Fallback**: If no physical WebAuthn key is present during initial setup, the harness can support a secure local Polkit/PAM touch authentication prompt, but WebAuthn in-browser remains the gold standard for agent-unforgeable human authorization.

---

## 3. Summary & Next Steps
- **Verdict**: Adopt ACP R2/R3/R4 design; defer P-F4 live activation until the minimal ACP WebAuthn signing surface lands.
- **Commitments**: Antigravity is ready to implement the frontend WebAuthn invocation button and status indicator in `dashboard.html` and `aq-workspace` as soon as the backend signing endpoint is scaffolded.
