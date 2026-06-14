# Security Audit Report: Edge AI Stack
**Date:** June 14, 2026
**Status:** ACTIVE DEV CYCLE SLICE TEST

## 1. Overview
This audit evaluates the current security posture of the local AI stack, focusing on the hybrid-coordinator's defensive layers following the event-driven timeout refactor.

## 2. Component Analysis
### 2.1 Access Control (zero_trust.py)
*   **Status:** Framework established.
*   **Findings:** Implements RBAC with ServiceRoles (COORDINATOR, AGENT, STORAGE, etc.). Provides mTLS and request signing.
*   **Gap:** Integration into the global middleware stack in `router.py` appears partial. While `api_key_middleware` exists, full mTLS enforcement is currently optional.

### 2.2 Content Sanitization (context_sanitizer.py)
*   **Status:** Active.
*   **Findings:** Correctly filters tool results and RAG documents for hard injection patterns (e.g., `[INST]`, `SYSTEM OVERRIDE`).
*   **Improvement:** The 3000/4000 character hard caps are strictly enforced, which is good for stability but may need "progressive disclosure" bypasses for authorized agents.

### 2.3 Rate Limiting (router.py)
*   **Status:** Active, but underspecified.
*   **Findings:** The `RateLimiterMiddleware` is enabled. 
*   **Critical Gaps (Vulnerabilities):**
    *   **Delegation Overload:** `/control/ai-coordinator/delegate` lacks an explicit RPM limit, defaulting to 100 RPM. This is far too high for local GPU resources and could lead to system lockup.
    *   **Research Egress:** `/research/web/fetch` is unthrottled (defaults to 100 RPM). Malicious or buggy agents could cause excessive egress or trigger SSRF protections at the network level.
    *   **Event Flooding:** `/api/agent-events` is unthrottled, allowing for disk/database exhaustion via log flooding.

## 3. Implementation Plan: Enhanced Throttling
1.  **Extend Configuration:** Add `RATE_LIMIT_DELEGATE_RPM` and `RATE_LIMIT_RESEARCH_RPM` to environment variables.
2.  **Update router.py:** Explicitly add these endpoints to the `endpoint_limits` mapping.
3.  **Nix Integration:** Expose these limits in `options.nix` for declarative workstation-level tuning.

## 4. Verification Strategy
*   [ ] Rebuild system with new limits.
*   [ ] Run stress test against `/delegate` endpoint to confirm 429 Too Many Requests response.
*   [ ] Verify `aq-llm-monitor` tracks 429 events correctly.
