---
doc_type: design-review
id: antigravity-acp-p3-design-advisory-20260816
title: "Antigravity advisory — ACP-P3 runbook automation engine design review"
status: complete
parent_prd: approval-control-plane
reviewer: antigravity
verdict: CONCERNS
owner: hyperd
date: 2026-08-16
---

# ANTIGRAVITY-ACP-P3-DESIGN-ADVISORY-20260816

**Document Type:** Security & Systems-Integrity Advisory (Independent Review)  
**Status:** Complete  
**Date:** 2026-08-16  
**Subject:** ACP-P3 Runbook Automation Engine Design  
**Target File:** `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P3-DESIGN-ADVISORY-20260816.md`  

---

## 1. Executive Verdict: REQUEST REVISION (Gated)

The runbook engine's design correctly establishes a sandboxed, parameter-bound model that keeps private key material isolated. However, it lacks robust guarantees for ATOM-level idempotency and is vulnerable to replay attacks if the signature verification does not bind the unique `request_id`.

Build authorization is deferred until the findings below are addressed.

---

## 2. Technical Findings & Assessment

### Assessment (1): Idempotency & Recovery Mid-Runbook
*   **Analysis:** The step-log resuming mechanism is sound. However, resuming after a crash is only safe if every constituent execution ATOM is strictly idempotent.
*   **Vulnerability:** If an ATOM performs a stateful mutate (e.g. appending a key or appending a line to a configuration file), resuming a failed step will result in duplicate mutations.
*   **Mitigation:** The runbook engine contract must require that every ATOM implements a pre-check (`verify`) that is run *prior* to executing the action. If the verify check indicates the action is already completed, the step must be skipped, independent of the local step log.

### Assessment (2): Scope Creep & Parameter Injection
*   **Analysis:** Gating parameter resolution to the hashed record prevents runtime command/argument injection.
*   **Vulnerability:** If parameter validation schemas in the registry are too broad, valid but malicious inputs (e.g. path traversal or command separator characters in a parameter) can still pass hashing and be executed by the ATOMs.
*   **Mitigation:** Implement strict allowlists (regex, character bounds) for all parameters in `validate_params`. Ensure ATOM implementations avoid shell spawning (`shell=True` in Python) and use array-based argument passing (`subprocess.run(["cmd", "arg"])`).

### Assessment (3): Signer Gating & Single-Use runbook Run
*   **Analysis:** Isolating the private key behind the P1 UDS signing service is structurally correct.
*   **Vulnerability (Replay to a Second Run):** If the cryptographic signature over `canonical_hash` is not bound to a unique `request_id` (see P1 Advisory), the signature remains valid across multiple requests with identical parameters. The engine could be forced to re-run the same action multiple times by creating new request IDs and copying the signature.
*   **Mitigation:** Include the unique `request_id` in the `canonicalize` hash definition. The executor must also query a write-once ledger of executed request IDs before starting any runbook run.

### Assessment (4): Fail-Closed & Operator Intervention
*   **Analysis:** Halting on step failure and exposing retry/abort options prevents silent partial success.
*   **Vulnerability (Expired Credentials on Retry):** If a runbook fails mid-execution and the operator retries it hours later, the original signature or session credentials might be stale or expired, but the engine might resume without re-validating the core lease/signature.
*   **Mitigation:** The retry path must re-run the entire signature validation and check that the authorization signature has not expired relative to the system clock.

### Assessment (5): NixOS-Declarative Rule Coupling
*   **Analysis:** Rule 13 mandates that runtime state modifications must not be decoupled from their declarations.
*   **Vulnerability (State Drift):** If an `activate-*` runbook performs system changes using transient commands (e.g., `systemctl start`), the change will drift upon reboot.
*   **Mitigation:** `activate-*` runbook steps must be implemented by updating the target declarative Nix configuration files, staging the change in the local repository, and executing `nixos-rebuild switch`. 

### Assessment (6): Step Outcome Verification Integrity
*   **Analysis:** The post-condition `verify` check is a critical security boundary to prevent spoofing.
*   **Vulnerability (Audit Forgery):** If the verification checks rely on easily spoofable attributes (like process name or file existence), a compromised agent could simulate success.
*   **Mitigation:** Step verification must rely on cryptographic or state-backed proof (e.g. verifying a signature from the started service or reading a signed telemetry metric).

---

## 3. Hardening Action Items

1.  **Mandate ATOM Idempotency:** Require every runbook step's execution handler to be self-verifying and idempotent.
2.  **Bind Request ID in Signature:** Enforce signature binding to the unique `request_id` to prevent multi-run replays.
3.  **Strict Shell Sanitation:** Ensure no step executor uses shell-expansion interpreters.
4.  **Enforce Declarative Commits:** Tie all system activation steps to Nix configuration commits in the Git history.
