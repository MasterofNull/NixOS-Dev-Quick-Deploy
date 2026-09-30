# Vote — antigravity (Gemini 2.5 / IDE Lane), baseline: security + systems + reviewer

## Disposition: ACTIVATE_WITH_CONDITIONS

Antigravity concurs with `ACTIVATE_WITH_CONDITIONS`. The C6c offline socket-submit implementation is verified on `main`, but runtime activation must be bounded to the smallest verifiable blast radius (Stage 1a observable-only, followed by Stage 1b signer-live).

---

## Q1 — Boundary / Stagger Depth: SPLIT (Stage 1a → Stage 1b)
**Decision: Concur strongly with 1a → 1b split.**
- **Stage 1a (Service Enablement & DAC Verification, Zero Signers):** Enable `mySystem.aiStack.revocationEpochAuthority.enable = true` with allowlist pinned to rev-4 (`owner-mechtest-2026-08` revoked, 0 active signers). The authority service starts, binds the control socket, enforces socket DAC/AppArmor confinement, and illuminates the Command Center dashboard revocation surface. It cannot execute an epoch bump.
- **Stage 1b (Owner Offline Keygen & Verified Bump):** Once Stage 1a is confirmed green, the owner generates the Ed25519 keypair offline, advances the allowlist to rev-5, and performs a single signed test bump via control socket.
- **Systems/Security Rationale:** Isolates Unix socket ownership, systemd unit health, and telemetry ingestion from epoch-state mutation risk. Any permission or confinement failures are trapped at zero operational impact.

---

## Q2 — Ceremony Correctness: CONFIRMED (Enforce Offline-Only Socket Path)
- The activation ceremony MUST strictly follow `aq-epoch-bump submit --signed <file> --socket <control.sock>`.
- The owner's private key must remain strictly offline on the owner's air-gapped machine and NEVER touch `/run/secrets`, SOPS, environment variables, or host memory.
- Any attempt to invoke deprecated host-local key loading paths (e.g., `_load_owner_key`) fails the ceremony instantly.

---

## Q3 — Revert Adequacy: ADEQUATE via Allowlist Rollback
- The auto-revert guard timer runs in a non-interactive shell context and cannot trigger an imperative `nixos-rebuild switch`.
- Because `revocation_epoch.py` dynamically evaluates `config/aqos/c6-owner-public-keys.json` upon every invocation with no in-memory cache, restoring rev-4 immediately invalidates all active signers.
- A runtime file revert of `c6-owner-public-keys.json` from rev-5 to rev-4 immediately denies any further bumps with `status=="revoked"`, rendering the running daemon inert.
- Follow-up durable service teardown via `nixos-rebuild switch` can then be scheduled cleanly by the operator.

---

## Q4 — C4 Independence: CONFIRMED
- C6c / P-F4 operates on an independent architectural plane from the [AMEND-C4] freeze prerequisite.
- The owner-key kill-lever does not depend on the Codex C4 amendment review. Decoupling Stage 1 from the C4 amendment pipeline prevents cross-phase deadlocks.

---

## Q5 — Residual Blockers / Observability: PRE-ACTIVATION SMOKE REQUIRED
Before flipping the switch in Stage 1a:
1. **Dashboard Telemetry:** Verify that the Command Center dashboard reflects authority socket status and current epoch without blank (`--`) fields.
2. **Read-Epoch Probe:** Confirm `{"op":"read-epoch"}` over the socket returns HTTP/JSON 200 with the active epoch.
3. **Lease Mint Smoke:** Verify capability lease minting remains healthy at the current baseline epoch.
4. **Key Invalidation Check:** Assert `owner-mechtest-2026-08` remains revoked.

---

## Summary of Stated Conditions
1. **Two-Stage Execution:** Stage 1a (inert service) soak green before Stage 1b (active signer).
2. **Runtime Revert Armed:** Guard armed with allowlist rollback (`c6-owner-public-keys.json` rev-5 → rev-4).
3. **Strict Socket Protocol:** Offline keygen only; submission via `submit --signed --socket`.
4. **Smoke Gate:** Pre-activation smoke suite passing prior to Stage 1a switch.
5. **Consensus Quorum:** Claude concurring; Antigravity concurring; Codex binding confirmatory folded upon queue reset.
