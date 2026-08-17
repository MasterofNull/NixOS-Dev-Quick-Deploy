---
doc_type: design-review
id: antigravity-acp-p2-design-advisory-20260816
title: "Antigravity advisory — ACP-P2 approval surface design review"
status: complete
parent_prd: approval-control-plane
reviewer: antigravity
verdict: CONCERNS
owner: hyperd
date: 2026-08-16
---

# ANTIGRAVITY-ACP-P2-DESIGN-ADVISORY-20260816

**Document Type:** Security, Usability, & Accessibility Advisory (Independent Review)  
**Status:** Complete  
**Date:** 2026-08-16  
**Subject:** ACP-P2 Human-Friendly Approval Surface Design  
**Target File:** `.agents/plans/approval-control-plane/ANTIGRAVITY-ACP-P2-DESIGN-ADVISORY-20260816.md`  

---

## 1. Executive Verdict: CONDITIONAL PASS

The ACP-P2 design successfully addresses the friction of the manual cryptographic signing pipeline by presenting authorizations as plain-language cards. However, the surface is vulnerable to DOM-tampering (clickjacking) attacks by a local compromised agent unless strict sandbox and origin controls are enforced. 

Build authorization is granted subject to resolving the findings below.

---

## 2. Technical Findings & Assessment

### Assessment (1): Plain-Language Security vs. WYSIWYS
*   **Analysis:** Splitting the display into Layer-1 (beginner summary) and Layer-3 (details) makes the system approachable. However, the cryptographic signature is computed over the entire record (including `action_manifest` and `technical_trail`).
*   **Vulnerability (Render-vs-Sign Mismatch):** If a compromised agent creates a request with a benign `summary` (Layer-1) but a malicious `action_manifest` payload (Layer-3), a beginner human will only see the safe summary and approve the action. 
*   **Mitigation:** The template rendering engine must be trusted and locked. The signer service (P1) must programmatically verify that the Layer-1 `summary` is *exactly* the output of rendering the specified template with the `action_manifest` parameters. Any parameter not represented in the template must trigger an automatic signature abort.

### Assessment (2): Browser-Mediated WebAuthn Flow
*   **Analysis:** The flow is clean. By offloading the credential request to `navigator.credentials.get` and transmitting the assertion back to the local service, the browser never handles raw private keys.
*   **Vulnerability (DOM-Tampering / Clickjacking):** A local compromised agent running in the user session could inject scripts, hijack the DOM, and display a card saying "Enable timezone sync" while calling the signer for a request to "Revoke production key". The native WebAuthn prompt only displays the RP ID and a raw challenge hash, which does not help the human detect the swap.
*   **Mitigation:** The dashboard interface must run inside an isolated browser session (e.g., kiosk-mode Chromium launched via a dedicated systemd-run container) with a strict Content Security Policy (CSP) that disables inline scripts, eval, and third-party extensions.

### Assessment (3): State Honesty & Connection Integrity
*   **Analysis:** Real-time state projection is correct, but a connection drop can cause the UI to display stale status information.
*   **Vulnerability (Silent Staleness & Repetitive Taps):** If the WebSocket/polling connection fails silently, a user might see a stuck "Awaiting Tap" status, leading them to refresh the page or tap "Approve" repeatedly on retries, potentially resulting in unintended double-executions.
*   **Mitigation:** The UI must feature a prominent "Live Sync" connection status indicator. If connection to the backend drops, the UI must immediately overlay a warning block and disable all interaction buttons.

### Assessment (4): Technical Jargon Leakage
*   **Analysis:** The card default path successfully isolates the operator from raw hex64 hashes and key IDs.
*   **Vulnerability (Error-Path Leakage):** Cryptographic errors (e.g. `InvalidSignatureError`, `UP-not-satisfied`) could leak into the UI and confuse a non-technical user.
*   **Mitigation:** Map all WebAuthn and execution exceptions to plain-language error cards with clear physical recovery steps (e.g., "Please re-insert your security key and touch the blinking light").

### Assessment (5): Accessibility (a11y) & Usability
*   **Analysis:** Keyboard navigation and focus order requirements are correctly specified.
*   **Usability Gap:** A beginner user might not understand that clicking "Approve" triggers an external OS/browser dialog.
*   **Mitigation:** Provide clear, inline micro-copy beneath the Approve button explaining the physical action required (e.g. "Tapping Approve will prompt you to scan your fingerprint or touch your security key").

---

## 3. Hardening Action Items

1.  **Enforce Strict CSP:** Configure the dashboard server to send strict security headers (`Content-Security-Policy: default-src 'self'`).
2.  **Verify Summary Congruence:** The P1 signer must execute a strict template validation check to confirm `summary` content matches the action parameters.
3.  **Connection Health Gating:** Disable interaction buttons automatically if connection latency exceeds 1.5 seconds or drops entirely.
