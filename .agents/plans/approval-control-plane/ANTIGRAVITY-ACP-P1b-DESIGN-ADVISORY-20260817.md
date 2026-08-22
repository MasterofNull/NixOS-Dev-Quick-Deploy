---
doc_type: design-review
id: antigravity-acp-p1b-design-advisory-20260817
title: "Antigravity advisory — ACP-P1b lost-authenticator recovery design review"
status: complete
parent_prd: approval-control-plane
reviewer: antigravity
verdict: PASS
owner: hyperd
date: 2026-08-17
---

# ANTIGRAVITY-ACP-P1b-DESIGN-ADVISORY-20260817

**Document Type:** Security & Architectural Advisory (Independent Review)  
**Status:** Complete  
**Date:** 2026-08-17  
**Subject:** ACP-P1b Lost-Authenticator Recovery Design  
**Target File:** `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P1b-DESIGN-ADVISORY-20260817.md`  

---

## 1. Executive Verdict: PASS (With Hardening Recommendations)

The proposed design for the `ACP-P1b` lost-authenticator recovery protocol is architecturally sound and successfully eliminates human-factor single points of failure without introducing soft backdoors or agent-forgeable paths. The use of physical machine access (gated by console root privilege) as the primary recovery factor is highly effective. 

However, to guarantee that the agent cannot subvert this recovery loop, specific safeguards must be enforced in the NixOS module and the signing service implementation.

---

## 2. Detailed Assessment & Security Analysis

### 2.1 Agent-Forgeability of the Recovery Bootstrap
* **Assessment:** The design relies on a console-gated, root-run recovery bootstrap to enroll a new key. Because the agent runs as a low-privileged primary UID in a sandboxed/confined environment, it has no access to physical virtual terminals (VTs) or the console serial ports.
* **Potential Risk:** If the agent is allowed to write to the declarative NixOS configuration files (e.g., `configuration.nix` or modules) or system-wide script paths, it could inject its own public key/credential ID into the allowlist, then trigger a rebuild.
* **Hardening:** NixOS module configuration files that define the authenticator allowlist must be owned by `root`, have permissions `0644` or `0600`, and be write-restricted against the primary UID. Any configuration changes to the allowlist must require out-of-band human confirmation.

### 2.2 Un-spoofability of Host Root over Signer UDS
* **Assessment:** The signer service must verify caller identity over the Unix Domain Socket (UDS). The "host root" check relies on the kernel's socket peer credentials (`SO_PEERCRED`).
* **Security Standing:** In Linux, peer credential retrieval via `getsockopt(..., SO_PEERCRED, ...)` is performed by the kernel and is completely tamper-proof from non-root processes. Therefore, the agent (sharing the primary UID) cannot spoof `UID 0`.
* **Hardening:** The signing daemon must explicitly reject any recovery payload or allowlist mutation request over the UDS if the peer UID is not `0`. The peer GID should also be validated to match the root group.

### 2.3 Prevention of Lockout and Fail-Open States
* **Assessment:** The "no-empty-allowlist" invariant is critical. 
* **Self-Lockout:** Enforcing that a key removal must be accompanied by a replacement enrollment prevents accidental human lockout.
* **Fail-Closed Default:** If the system is initialized or reaches an empty allowlist state, the signing service must **fail-closed** (block all approvals). There must be no code paths that interpret an empty allowlist as "no authentication required."
* **Recommendation:** The schema and parsing logic for the allowlist must throw an error and refuse to start the daemon if the allowlist is empty or corrupted, ensuring the system remains in a locked down, secure state.

### 2.4 Absence of Stored Secrets or Standing Authorizations
* **Assessment:** The design correctly rejects printed recovery codes, SMS/email links, and offline recovery keys, which are classic target surfaces for agent exfiltration.
* **Operational Scope:** The recovery mechanism does not grant signatures or authorizations directly. It only registers the public key of the new physical authenticator. The owner must still perform the standard live FIDO2 ceremony to sign any request. This ensures that recovery cannot be abused to perform a single-use stealth action.

### 2.5 Race Conditions in Key Re-enrollment
* **Assessment:** During key rotation or replacement, there is a risk of a race condition if a key removal is processed before the new key is validated and committed.
* **Hardening:** Implement atomic write transactions. The allowlist mutation must be written to a temporary file on the same filesystem and renamed (`os.replace`) to ensure atomic replacement. The validation logic must confirm the new key is readable and well-formatted before deleting the old key's record.

---

## 3. Implementation Checklist & Governance

- [ ] **Egress & Peer Validation:** Wire `SO_PEERCRED` checks on the recovery socket endpoints to enforce `UID == 0`.
- [ ] **Declarative Restrictions:** Ensure the allowlist store file (e.g., `/etc/approval/allowlist.json` or equivalent) is owned by `root:root` with `0600` permissions.
- [ ] **Unit Testing:** Implement a negative test case asserting that an empty allowlist causes the signer daemon to fail-closed.
- [ ] **Audit Logs:** Log recovery events directly to the system journal using `systemd-journald` (which prevents low-privileged log manipulation).
