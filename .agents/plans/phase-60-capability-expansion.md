# Phase 60: Capability Expansion & Legacy Cleanup

**Date:** 2026-05-24
**Status:** In Progress (Scaffolding Complete)

## Objective
Formalize the AI Harness architecture by archiving legacy instructional debt and scaffolding three high-value emerging domains (`trading-agents`, `mlops-engineering`, `qa-automation`) for immediate autonomous research and implementation.

## Workstreams

### WS1: Legacy Cleanup (Complete)
- [x] Moved `CLOUD-OPERATIONS`, `CYBER-SECURITY`, `DATA-ENGINEERING`, `FRONTEND-UIUX`, and `ML-AI` instructions to `.agent/archive/legacy-instructions/`.
- [x] Reason: Replaced by compliant `systems-software`, `security-systems`, `mlops-engineering`, and `mobile-web` domains.

### WS2: Scaffold New Domains (Complete)
- [x] Drafted PRDs for Trading, MLOps, and QA.
- [x] Drafted Instruction Surfaces.
- [x] Registered in `capability-lifecycle-registry.json`.
- [x] Added intents to `intent-routing-map.json`.
- [x] Added health checks to `validation-check-registry.json`.

### WS3: Deep Research (Pending Fresh Agent)
- [ ] 12-pass research on automated trading architectures (yfinance, sentiment debate).
- [ ] Research on MLOps continuous learning pipelines.
- [ ] Research on Chaos Engineering & Playwright QA.

### WS4: Implementation (Pending Fresh Agent)
- [ ] Build OSINT/Trading/MLOps/QA MCP servers.
- [ ] Wire to local-agent runtime.
