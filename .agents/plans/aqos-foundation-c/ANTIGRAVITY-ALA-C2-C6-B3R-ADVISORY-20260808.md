# ALA→C2 Contract Repair & C6-B3 Live Seam Reconciliation — Independent Advisory Review

- **Reviewer:** Antigravity (Advisory Lane)
- **Date:** 2026-08-08
- **Subjects under review:**
  - Subject 1: `.agents/plans/aqos-foundation-c/ALA-C2-CONTRACT-REPAIR-DESIGN-20260808.md`
    - Hash: `3c7c0e7f672b8a55e65ed37a7cea0dd87ae189af6e352fc7fb09ea88032dc497`
  - Subject 2: `.agents/plans/aqos-foundation-c/C6-B3-LIVE-SEAM-RECONCILIATION-20260808.md`
    - Hash: `0523b4c275d5abf13178eaae6d72603f12325e88a73f2d95a03d37e3b7116ea4`
- **Verdicts:** 
  - Subject 1 (ALA-C2 Repair): **PASS**
  - Subject 2 (C6-B3 Reconciliation): **PASS**

---

## 1. Subject 1 Audit: ALA→C2 Contract Repair Design

### 1.1 Signed Policy Digest and Revision Verification (§2.1, §2.2)
- **Soundness:** The addition of `policy_revision` and `grant_digest` inside the Ed25519-signed lease is architecturally robust. By constructing the policy-binding digest over static properties (excluding variable fields like `lease_id`, clocks, and signature bytes), policy identity is cleanly separated from transient transaction state. 
- **Integrity:** The digest is covered by the lease signature, preventing tamper-risk. Strict parsing of `policy_revision` (denying floats, booleans, or <=0 values) prevents type-coercion bypasses.

### 1.2 Epoch-Authority Fail-Closed Paths (§2.4)
- **Decommissioning Fallbacks:** Eliminating both genesis-file and environment fallbacks is a critical security improvement. Any unresolvable response over the Unix domain socket is mapped to a typed deny rather than defaulting to `0` or `1`.
- **Exact-Comparison Enforcement:** `mint_scheduler_context()` enforces `revocation_epoch == current_epoch` exactly. This strict comparison successfully mitigates epoch-skew replays.
- **Timeout Durability:** Verification of the live `revocation_epoch_transport.py` codebase confirms that socket calls set a strict 5.0s timeout (`RECV_TIMEOUT_S` at line 42) and catch timeouts fail-closed (line 100), ensuring that network hanging does not stall the execution gate indefinitely.

### 1.3 Schema Parity (§2.3)
- The schema updates in `config/schemas/scheduler-lease-context.schema.json` enforce the required signed metadata without widening the grammar to accept legacy or malformed formats.

### 1.4 Recommendations & Minor Gaps
- **Connection Hanging:** While `RECV_TIMEOUT_S` is set to 5.0s, this is still relatively high for hot-path scheduler evaluation. Consider reducing the transport timeout for read-epoch calls to 1.0s or lower.

---

## 2. Subject 2 Audit: C6-B3 Live Seam Reconciliation Plan

### 2.1 Trusted Execution Gateway (TEG) Separation (§2, §3 B3R-P0)
- **UID Separation:** Running the TEG as a separate service principal completely mitigates same-UID authority confusion. Since human users and agent processes run under the same UID on the NixOS system, gating access via public/untrusted socket inputs while restricting authority-client groups to the TEG principal is the correct trust-boundary separation.
- **Envelope Validation:** Gating execution on the verified lease/context fetched by the TEG itself, rather than accepting caller-supplied leases, prevents local bypasses.

### 2.2 CAS State Machine and Ordering (§3 B3R-P0)
- **Monotonicity:** The transition chain (`submitted → admitted → queued → held → launch_authorized → running`) is strictly monotonic.
- **Fail-Closed Sequence:** Creating the single-use permit marker using `O_EXCL` and forcing an `fsync` before committing CAS transitions ensures file-system backed atomicity across gateway restarts.

### 2.3 One-Use Launch Token and Linearization (§3 B3R-P1)
- **Revocation Race Mitigation:** Performing the `pre_execute()` fence immediately before provider I/O closes the time-of-check to time-of-use (TOCTOU) vulnerability.
- **Sealed Token Lifetime:** The 250 ms lifespan for the one-use launch token is highly restrictive and secure.
- **Linearization Point:** Defining the transition to `launch_authorized` as the explicit linearization point prevents epoch bumps occurring after launch from falsely claiming safety violations, while ensuring bumps prior to launch result in slot revocation.

### 2.4 Recommendations & Minor Gaps
- **Orphaned Token Cleanup:** If the gateway crashes or fails to execute *after* transitioning to `launch_authorized` but *before* token consumption, the reservation will be orphaned. The TEG must implement a reaper daemon to garbage-collect expired launch tokens and transition them to `failed`/`revoked`.
- **Descriptor-Binding Specification:** The method for descriptor-binding (e.g., standard pipe, Unix domain socket credential checks, or `/proc/self/fd/` check) should be explicitly detailed in the B3R-P1 implementation specification to guarantee that the token cannot be read/intercepted by external processes.

---

## 3. Final Verdicts

- **Subject 1 (ALA-C2 Contract Repair):** **PASS**
- **Subject 2 (C6-B3 Live Seam Reconciliation):** **PASS**
