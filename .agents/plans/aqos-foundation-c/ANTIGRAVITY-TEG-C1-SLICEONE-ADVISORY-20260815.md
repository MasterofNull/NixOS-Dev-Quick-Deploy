---
doc_type: design-review
id: antigravity-teg-c1-sliceone-advisory-20260815
title: "Antigravity advisory — TEG C1 R2 Slice-One pre-build review"
status: complete
parent_prd: trusted-execution-gateway
reviewer: antigravity
verdict: PASS
owner: hyperd
date: 2026-08-16
---

# Antigravity Advisory: TEG C1 R2 Slice-One Pre-Build Review

**Author:** Antigravity (Advisory Lane)  
**Date:** 2026-08-16  
**Subject:** Trusted Execution Gateway C1 R2 Slice-One Pre-Build Advisory  
**Target File:** `.agents/plans/aqos-foundation-c/ANTIGRAVITY-TEG-C1-SLICEONE-ADVISORY-20260815.md`  

---

## 1. Executive Summary & Verdict

We have completed the pre-build architectural and security audit of the frozen Trusted Execution Gateway (TEG) C1 R2 design, focusing exclusively on the **Slice-One CORE broker** specification (§8). 

**Verdict: PASS (No Build-Blocking Gaps)**

The R2 design packet successfully closes the R1–R5 security findings and establishes a robust, fail-closed contract that prevents double-launch exploits, race conditions, and unauthorized record disclosures. The implementer may proceed with building Slice-One CORE once the owner elects to issue the build grant.

---

## 2. Scope-vs-Staging-Guard Compliance

* **Strict Alignment:** The proposed eventual build inventory (§8) is strictly confined to the CORE broker, submission sockets, lifecycle CAS, fencing, validation of cryptographic C2/ALA leases, and minimum observable health. 
* **Follow-Ons Excluded:** The cancellation authority service, ceiling-matrix tuning, and advanced dashboard/TUI surfaces are correctly deferred to future, independently hash-bound grants. This respects the minimal-code design ladder.

---

## 3. Build-Time Security Risks & Watch-Items (Implementer Advisories)

The implementer must pay close attention to the following implementation details to ensure the running code matches the frozen security properties:

### A. Directory Fsync on tmpfs/Virtual Filesystems (§5)
* **Hazard:** The state directory `/run/aq-teg/` will likely reside on a `tmpfs` mount. On some Linux kernels, calling `fsync()` on a directory file descriptor opened on `tmpfs` can raise `EINVAL` or `ENOTSUP`.
* **Advisory:** The Python implementation of the atomic parent-directory fsync must gracefully catch and tolerate `EINVAL`/`ENOTSUP` when running on filesystems that do not support directory syncs, while still failing closed on general IO errors.

### B. Reliable Terminal State Verification (§6)
* **Hazard:** The crash matrix (§6) mandates that the system *never infer terminal state from PID absence*. Under containerized environments (like `nsjail`), PIDs are isolated, and under high system load, PIDs can recycle.
* **Advisory:** The reconciler’s `launch_authorized -> failed` or `running -> failed` checks must rely on durable, out-of-band evidence (e.g., cgroup process list termination markers, systemd unit exit codes, or explicit signed provider receipts) rather than simple `os.kill(pid, 0)` checks.

### C. Epoch Synchronization & Clock-Skew Mitigation (§7)
* **Hazard:** The "launch-epoch == signed-C2-epoch" binding prevents epoch-bypass attacks, but a minor latency or propagation lag between the no-key epoch reader service and switchboard context signing could cause legitimate tasks to fail validation.
* **Advisory:** The UDS epoch resolver should implement a bounded retry-with-backoff loop (e.g., 3 attempts over 500ms) to allow the local epoch state to catch up before throwing a hard deny.

### D. Idempotency Envelope Canonicalization (§2)
* **Hazard:** SHA-256 hashing of arbitrary JSON envelopes can be bypassed if the JSON parser tolerates duplicate keys, floats with varying precision, or alternative Unicode normalization forms.
* **Advisory:** Implement strict JSON canonicalization (using a parser that rejects duplicate keys, enforces RFC 8259 compliance, and validates Unicode NFC normalization) *before* computing the `envelope_digest`.

### E. NixOS Declarative Group Configuration (§7)
* **Hazard:** The TEG service principal `aq-trusted-execution-gateway` requires access to upstream authority sockets.
* **Advisory:** In `trusted-execution-gateway.nix`, ensure the service systemd unit joins the `aq-lease-signing-clients` and `aq-revocation-epoch-clients` groups using `SupplementaryGroups` or systemd-level group additions, rather than replacing the primary service group.

---

## 4. Dependency & Rollback Isolation (§9)

* **Frozen Integrity:** The implementation must not alter the frozen-no-touch dependencies listed in §9. 
* **Predecessor Locking:** The `dispatch.py` and `switchboard.nix` integrations must remain pinned to commit `3d45e03ccea880ee22ab6022cdd730f98b0513d1`. Any changes to the ALA/C2 transport interfaces must trigger an immediate fail-stop.
