---
doc_type: design-review
id: antigravity-acp-p4-design-advisory-20260817
title: "Antigravity advisory — ACP-P4 headless/rescue authorization design review"
status: complete
parent_prd: approval-control-plane
reviewer: antigravity
verdict: PASS
owner: hyperd
date: 2026-08-17
---

# ANTIGRAVITY-ACP-P4-DESIGN-ADVISORY-20260817

**Document Type:** Security & Architectural Advisory (Independent Review)  
**Status:** Complete  
**Date:** 2026-08-17  
**Subject:** ACP-P4 Headless/Rescue Authorization Design  
**Target File:** `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P4-DESIGN-ADVISORY-20260817.md`  

---

## 1. Executive Verdict: PASS (With Hardening Recommendations)

The proposed design for the `ACP-P4` headless and rescue authorization client is architecturally sound and successfully maintains the security guarantees of the `ACP-P1` Approval Control Plane under headless execution environments. By using the `aq-approve` CLI purely as a transport for FIDO2 hardware assertions, the design avoids soft bypasses or agent-forceable downgrades.

To ensure robust deployment and prevent credential exposure, specific attention must be paid to device nodes, udev configurations, and terminal output sanitization.

---

## 2. Detailed Assessment & Security Analysis

### 2.1 Signer Path Identity & Guarantees
* **Assessment:** The design reuses the identical signer path for both the browser and CLI assertion flows. The signer derives the request challenge and validates the FIDO2 signature identically.
* **Security Standing:** Because the challenge derivation, single-use check, and executed-id ledger logic do not branch for headless clients, there is no risk of logic divergence or reduced security guarantees.

### 2.2 Downgrade Risks (Passphrase / Key-file / Offline paths)
* **Assessment:** The design states that no passphrase, key-file, or offline signing fallback will be supported.
* **Security Standing:** This is an essential security control. Any fallback to static credentials or soft files would immediately re-introduce an agent-forgeable path.
* **Hardening:** The `aq-approve` code must not include any hidden mock/testing credentials or file-based overrides in the production build. Verification of the assertion must fail-closed if hardware FIDO2 user verification (`uv=required`) is not present.

### 2.3 Rescue Console Bring-up Integrity
* **Assessment:** Starting the signer and epoch authority in a rescue target environment must be secure.
* **Hardware Interface:** For FIDO2 communication to function, the rescue target must mount `/dev/bus/usb/` and mount/initialize `/dev/hidraw*` devices. The kernel must be compiled with `CONFIG_HIDRAW=y`.
* **Hardening:** NixOS boot/rescue configurations must automatically include `python-fido2` dependencies and ensure the necessary HID driver stack is initialized in stage-1 or stage-2 recovery modes.

### 2.4 Agent Invocation and Signature Access
* **Assessment:** While the agent can execute the `aq-approve` command, it cannot tap the physical hardware key or satisfy User Verification (PIN/biometrics).
* **Security Standing:** Because the hardware-bound secret never leaves the FIDO2 device and requires human presence, agent execution of the CLI yields nothing but a timed-out request.

### 2.5 Plain-Language & Privacy Boundary
* **Assessment:** The CLI defaults to Layer-1 plain-language rendering (Markdown/text) and avoids printing cryptographic parameters.
* **Reasoning:** Screen-scraping, shell histories, and system telemetry must not leak challenge/signature internals. A `--details` flag is acceptable for Layer-3 debugging, but it must be explicitly triggered.

### 2.6 Udev Permissions Gap
* **Assessment:** A non-root console user running `aq-approve` needs read/write access to `/dev/hidraw*`.
* **Hardening:** The NixOS configuration must install `70-u2f.rules` or equivalent udev rules to grant appropriate permissions to the active console user session (using `TAG+="uaccess"`). Otherwise, the user would be forced to run the CLI via `sudo`, violating the principle of least privilege.

---

## 3. Implementation Checklist & Governance

- [ ] **No Overrides:** Audit the `aq-approve` client source to ensure no mock credentials or key-file signing paths exist in production code.
- [ ] **Udev Rules Integration:** Wire standard U2F/FIDO2 udev rules into the NixOS system profile.
- [ ] **Rescue Shell Validation:** Validate that hidraw drivers and Python dependencies are present in target NixOS rescue and recovery shell profiles.
- [ ] **Strict UV Enforcement:** The signer daemon must assert `User Verification (UV)` flag validation in the signature envelope.
