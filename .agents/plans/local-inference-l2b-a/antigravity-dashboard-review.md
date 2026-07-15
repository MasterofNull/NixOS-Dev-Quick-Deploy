# Antigravity Design Review: Local Inference L2B-A.1 Dashboard Parity

**Date**: 2026-07-15
**Reviewer**: Antigravity (Flagship Architecture, Security, and SRE Reviewer)
**Status**: `PASS` (Implementation Grant Authorized)

---

## 1. Executive Summary & Verdict

We issue a formal **`PASS`** for the **Local Inference L2B-A.1 Dashboard Parity** plan.

One single-use implementation grant may be activated for the exact four-file inventory defined in `.agent/PROJECT-LOCAL-INFERENCE-L2B-A1-DASHBOARD-PARITY-PLAN.md` to expose, sanitize, test, and render `source_shape_parity` and `actual_ssot_parity`.

### Scope & Authorization Constraints
> [!IMPORTANT]
> * This authorization is strictly limited to the four-file inventory.
> * No edits are permitted to the core transport module, policy, schemas, routing, inference, lifecycle, service topology, or any fifth file.
> * L2B-B (live payload normalization), M2–M3, and R1–R4 remain strictly **UNAUTHORIZED**.

---

## 2. Threat Modeling & Design Adjudication

We have evaluated the security and reliability footprint of the proposed integration and established the following design mandates:

### A. Missing/Malformed/Unknown Parity Values
* **Sanitization Constraint**: The backend endpoint (`dashboard/backend/api/routes/aistack.py`) and UI sanitizer (`assets/dashboard.js`) must strictly coerce any missing, malformed, or unrecognized values to `unavailable` or `fail`.
* **Value Constraint**: The exposed fields must strictly belong to the enum set: `["pass", "fail", "unavailable"]`. No other strings are permitted to bubble up.

### B. Information Exposure & Sandboxing
* **No Path/Exception Exposure**: The backend route must not propagate raw traceback text, local paths (e.g. Nix store paths), prompts, parameters, headers, or secrets.
* **Fail-Closed Semantics**: If the underlying `transport_health()` check raises an exception or the status file is unreadable, the API endpoint must fail-closed, returning `fail`/`unavailable` states rather than crashing or returning stale/invalid `pass` flags.

### C. UI Ambiguity & Presentation
* **Visual Clarity**: The dashboard Javascript card must display all four status indicators (`payload_parity`, `stream_parity`, `source_shape_parity`, `actual_ssot_parity`) using distinct visual markers (e.g., green/red/gray badges or dots) to represent `pass`/`fail`/`unavailable` states unambiguously.

### D. Regression Testing
* **Focused Parity Verification**: `scripts/testing/test-local-inference-l2b.py` must be updated to test this new contract. The tests must dynamically inject mutated data mockups (missing keys, invalid strings, error exceptions) and assert that the sanitizer correctly maps them to `fail` or `unavailable` without exposing internal state.

---

## 3. Verification & Execution Sequence

1. **Staging**: Modify only the four files in the inventory.
2. **Verification Command**:
   ```bash
   python3 scripts/testing/test-local-inference-l2b.py
   python3 -m py_compile dashboard/backend/api/routes/aistack.py
   node --check assets/dashboard.js
   scripts/governance/tier0-validation-gate.sh --pre-commit
   ```
3. **Commit**: Verify that no other files are edited before commit.
