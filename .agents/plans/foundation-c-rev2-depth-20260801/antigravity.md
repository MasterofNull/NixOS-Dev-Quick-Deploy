# Foundation C Revision 2 — Antigravity Design Adjudication

**Date:** 2026-08-01 UTC  
**Reviewer:** `antigravity`  
**Role:** independent architecture, security, SRE, and compliance reviewer  
**Status:** `REVIEW_COMPLETE — PREPARED_ONLY; PREREQUISITES RETAINED`  
**Observed HEAD:** `17f899bf838973c755ab7a3e6095ec04a2e74220`

---

## 1. Executive Summary & Audit Posture

This review represents the formal independent design adjudication for the **Foundation C** (C6, C4, C3a-2, and Runner Hardening) Revision 2 architectural suite. 
All design subjects are adjudicated strictly in a **`PREPARED_ONLY`** status. This review does not grant build, activation, staging, commit, deployment, provider invocation, or live network traffic authority.

---

## 2. Subject Adjudication & Scoring Matrix

| Subject File | Target SHA-256 | Verdict | Freeze Eligible | Unresolved Prerequisites / Blockers |
|---|---|---|---|---|
| `RUNNER-DEPLOYMENT-HARDENING.md` | `48cae30d1c93ff9e76fdff0e3866f885b54e544de95c978c8286a1c8065f0c63` | `PASS_DESIGN` | `no` | Gated by missing/rejected companion freeze record (`RUNNER-DEPLOYMENT-HARDENING-FREEZE.md`). |
| `RUNNER-DEPLOYMENT-HARDENING-FREEZE.md` | `4b5f9b4b4da272da7411f95cf2e6aeed1ac0783412dc434f66ce2748b8c2093f` | `REQUEST_REVISION` | `no` | Outdated hash bindings, lack of default-OFF build boundaries/verification commands, and failure to capture Bug #6 (Nix unit client UID). |
| `C6-DESIGN-AND-AUTHORIZATION.md` | `927374039c17abe0103a262b24346d61afc6dc38e7fe6396f74812c17203703c` | `REQUEST_REVISION` | `no` | Durability transaction/WAL hole, unauthenticated event lane (`aq-event emit --agent owner`), and stale environment epoch override vulnerability. |
| `C4-DESIGN-AND-AUTHORIZATION.md` | `f535731e7fe1ad48c5c70d1f8ccc275ef9b61c731d35a265f876961ea5f14d5a` | `REQUEST_REVISION` | `no` | Unfrozen action catalog/limits, deferred Nix-import/schema inventory, lack of qualitative backpressure/saturation SLOs. |
| `C3A-2-DESIGN-AND-AUTHORIZATION.md` | `7792e8537ac48c95837e2aedfec6794120a0550f1d274c0a76f29cab36c6a290` | `REQUEST_REVISION` | `no` | Authority input mutation contradiction, late reservation key binding (pre-receive), lack of import-effect crash-linearization, deferred hashes. |

---

## 3. Detailed Subject Findings

### 3.1. `RUNNER-DEPLOYMENT-HARDENING.md`
*   **Verdict:** `PASS_DESIGN` (the proposed socket-activation fd-3 adoption and fallback logic addresses prior socket takeover defects).
*   **Freeze Eligibility:** `no` (cannot be frozen until its companion freeze record passes review).
*   **Prerequisites:** Requires a corrected, validated `RUNNER-DEPLOYMENT-HARDENING-FREEZE.md`.

### 3.2. `RUNNER-DEPLOYMENT-HARDENING-FREEZE.md`
*   **Verdict:** `REQUEST_REVISION`
*   **Freeze Eligibility:** `no`
*   **Blockers & Design Defects:**
    1.  **Stale Anchors:** Does not bind the exact SHA-256 of the passing design or the active Observed HEAD.
    2.  **Lack of Build Boundaries:** Fails to specify default-OFF compilation/wiring bounds and specific live-cell verification command lines.
    3.  **Authentication/Parity Defect (Bug #6):** Fails to address or capture the fact that the Nix unit does not set `AQ_EXECUTION_CELL_RUNNER_CLIENT_UID`. Consequently, `peer_authorized()` will reject all incoming switchboard socket connections.
*   **Prerequisites:** Re-review and re-freeze under a corrected Revision 3 ceiling.

### 3.3. `C6-DESIGN-AND-AUTHORIZATION.md`
*   **Verdict:** `REQUEST_REVISION`
*   **Freeze Eligibility:** `no`
*   **Blockers & Design Defects:**
    1.  **Lack of Crash-Consistency (Durability Hole):** No atomicity or transactional guarantees exist between epoch filesystem commits and receipt durability. A crash after epoch write but before receipt generation leads to an unrecoverable mismatch. *Required fix:* Write and fsync a WAL state `prepared -> epoch_committed -> receipt_committed -> audit_projected`.
    2.  **Stale Environment Override:** Enforcing paths evaluate `AQ_LEASE_POLICY_EPOCH` before config-file epochs, allowing process-local stales to bypass the global revocation lever.
    3.  **Unauthenticated Event Authority:** The event command `aq-event emit --agent owner` trusts caller-asserted agent parameters without verification, replay protection, or monotonic validation.
*   **Prerequisites:** Requires a validated C2 scheduler-context issuer, transport definitions, and owner allowlist Nix hardening.

### 3.4. `C4-DESIGN-AND-AUTHORIZATION.md`
*   **Verdict:** `REQUEST_REVISION`
*   **Freeze Eligibility:** `no`
*   **Blockers & Design Defects:**
    1.  **Unfrozen Profiles:** Action schemas, receiver identities, byte bounds, deadlines, and concurrency parameters for loopback channels are qualitative and not locked.
    2.  **Incomplete Inventory:** Reserves unnamed later paths for fixtures and schemas, violating the requirement for an exact file-path and digest inventory.
    3.  **Qualitative SLOs:** Backpressure, rollback budgets, and teardown states lack numeric bounds (e.g., specific millisecond limits and test-oracle assertions).
*   **Prerequisites:** Gated by accepted runner hardening, active C6 intervention levers, and gateway/health check hash preflight.

### 3.5. `C3A-2-DESIGN-AND-AUTHORIZATION.md`
*   **Verdict:** `REQUEST_REVISION`
*   **Freeze Eligibility:** `no`
*   **Blockers & Design Defects:**
    1.  **Authority Model Contradiction:** Marks `execution_grant.py` and the lane-eligibility registry as `MODIFY` when they must remain immutable authority input digests.
    2.  **Late Binding Identity:** Binds `blob_digest` into the reservation key, preventing session-deduplication prior to blob transfer. *Required fix:* Split into pre-receive session reservation and post-receive content-addressed storage (CAS) binding.
    3.  **Lack of Import-Effect Linearization:** Lacks intermediate states for R5/R3 import transitions, creating ambiguous recovery postures if a crash occurs mid-write.
    4.  **Self-Declared Incomplete Inventory:** Defers test, schema, fixture, and Nix-import digests to a future stage.
*   **Prerequisites:** Gated by accepted runner/C4/C6, R5 attach validation, and a real hash-pinned remote signing principal.

---

## 4. Evidence Integrity & Attribution

Commits `ec6fc69b80be4a213e8ad5d23fc1320cf3f2f2af` and `17f899bf838973c755ab7a3e6095ec04a2e74220` physically integrated drafts but do not supply acceptance. Their commit bodies attribute the review/authoring work to `claude-20260801-093407-umfyv7` (which produced zero review output).

Per the governing Agentic Reliability Engineering framework:
*   The actual design revision work is attributed solely to **`codex-subagents`** (specific subagent identities not established).
*   Credit for this depth review is attributed solely to **`antigravity`**.
*   Stale, parked, failed, or outputless tasks receive zero review or authoring credit, and their trailers must not be propagated.

---

**FINAL CONVERGED VERDICT: REQUEST_REVISION**
