---
doc_type: design-review
id: antigravity-acp-p1-design-advisory-20260816
title: "Antigravity advisory — ACP-P1 WebAuthn signing service design review"
status: complete
parent_prd: approval-control-plane
reviewer: antigravity
verdict: CONCERNS
owner: hyperd
date: 2026-08-16
---

# ANTIGRAVITY-ACP-P1-DESIGN-ADVISORY-20260816

**Document Type:** Security & Architectural Advisory (Independent Review)  
**Status:** Complete  
**Date:** 2026-08-16  
**Subject:** ACP-P1 WebAuthn Signing Service Design  
**Target File:** `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P1-DESIGN-ADVISORY-20260816.md`  

---

## 1. Executive Verdict: REQUEST REVISION (Gated)

While the core WebAuthn-based signing flow is conceptually sound and provides strong defenses against autonomous agent forgeability, the design contains a critical vulnerability regarding **cross-request signature reuse (replay)** due to the exclusion of the `request_id` from the canonicalized content hash. 

Implementation must be halted until the findings below—specifically Finding 1 (Signature Reuse) and Finding 3 (Software-Authenticator Runtime Bypasses)—are resolved in the design.

---

## 2. Technical Findings & Assessment

### Assessment (1): WYSIWYS Integrity & Caller Influence
*   **Analysis:** The fetch-by-id + recompute pattern correctly isolates the signer from caller-supplied payload tampering. Since the signer reads from a root-owned, agent-inaccessible directory and computes the hash itself, the agent cannot manipulate the bytes after request creation.
*   **Vulnerability:** A mismatch can still exist between the **visual prompt shown to the user** and the **fields hashed in `canonicalize`**. If the presentation layer (CLI or Web UI) displays only a truncated text description (`summary`), a compromised agent could register a request containing a benign summary but a malicious payload in `action_manifest` or `technical_trail`.
*   **Mitigation:** The user-review interface must strictly render/validate the *entirety* of the fields that compose the `canonical_hash` (or the hash definition must be constrained strictly to the visual elements presented to the user).

### Assessment (2): Replay & Content-Hash Collisions
*   **Analysis:** **CRITICAL SEVERITY.** The proposed single-use ledger is keyed on `request_id` to prevent assertion replay, but the Ed25519 signature is computed over the `canonical_hash` which *excludes* the `request_id`.
*   **Vulnerability (Cross-Request Signature Reuse):** If two distinct requests have identical content (e.g., executing the same command on the same file), they share a content hash. If the user signs Request A, the resulting Ed25519 signature is valid for Request B. A compromised agent can copy the signature from Request A's completed record, inject it into Request B's record, and execute Request B without ever triggering a WebAuthn prompt.
*   **Mitigation:** The `request_id` (which is immutable after creation) must be included in `CANONICAL_FIELDS` for hashing and signing. This binds the cryptographic signature uniquely to that specific request instance and prevents signature reuse.

### Assessment (3): Confinement Model
*   **Analysis:** The systemd service jail (ProtectSystem=strict, ProtectHome, private tmp, UDS 0660 with dedicated user/group) is robust. The agent cannot read key material or forge assertions.
*   **Vulnerability (Prompt Fatigue DoS):** An untrusted agent with access to the UDS can flood the signer with `sign(request_id)` requests, resulting in continuous interactive authenticator prompts that spam the operator.
*   **Mitigation:** Enforce strict rate-limiting and a maximum queue size of 1 concurrent active signing session on the signer's UDS.

### Assessment (4): Downgrade & Fallback Paths
*   **Analysis:** The design correctly enforces a "fail closed" behavior upon WebAuthn unavailability, with no manual bypass options.
*   **Vulnerability (Software-Authenticator Runtime Hijack):** If the service environment contains virtual/software authenticator code (intended for CI/testing) that is toggleable via environment variables or runtime configuration, a compromised agent could inject variables to force the signer to accept a simulated, agent-controlled software key.
*   **Mitigation:** The virtual authenticator test code must be entirely compiled/built out of production builds or guarded by strict conditional compilation/module flags, never by runtime environment flags.

### Assessment (5): Authorization-by-Signature Verification
*   **Analysis:** The transition from status-based to signature-based execution is correct.
*   **Vulnerability (State Rewriting):** Although the executor gates on `status == "approved"`, if a compromised agent can delete or rewrite the execution history log or overwrite an executed record back to "approved", they can reuse the valid signature to execute the action multiple times.
*   **Mitigation:** The executor must maintain a root-owned, write-once/append-only execution ledger that logs every executed `request_id`. Overwriting a record or re-submitting an already executed `request_id` must abort before signature verification.

### Assessment (6): Hermetic Test Strategy Faithfulness
*   **Analysis:** The `python-fido2` virtual client is a faithful representation of the CBOR serialization and cryptographic validation logic.
*   **Vulnerability:** The test suite operates entirely in-memory and does not validate the udev/hidraw permission boundaries necessary for real hardware device communication.
*   **Mitigation:** Supplement the virtual test suite with a post-deployment diagnostic test that verifies the systemd unit has the correct udev tags and hidraw device group permissions.

---

## 3. Hardening Action Items

1.  **Bind Request ID to Signature:** Include `request_id` in `CANONICAL_FIELDS` in `scripts/ai/lib/approval_request.py`.
2.  **Separate Test and Production signer entrypoints:** Ensure that virtual/software authenticator classes from `fido2.mock` are completely absent from the production package imports.
3.  **Implement Rate-Limiting:** Restrict the signer UDS to a single concurrent session to prevent operator prompt flooding.
4.  **Enforce Append-Only History:** Ensure the request store strictly rejects file modifications (write-once semantics) at the filesystem level.
