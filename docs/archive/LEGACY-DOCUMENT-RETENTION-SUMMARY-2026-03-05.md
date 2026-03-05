# Legacy Document Retention Summary (Pre-Deletion Record)

Generated: 2026-03-05 05:52 UTC

Purpose: preserve a searchable record of removed legacy assets so skipped or deferred features can be rediscovered and reevaluated later.

## Removed Legacy Documents (Current Working Tree)

| Legacy Path | Status | Current Location | Title | One-Line Summary |
|---|---|---|---|---|
| `AGENT_BOOTSTRAP_COMMAND.md` | archived/moved | `/docs/archive/root-docs/AGENT_BOOTSTRAP_COMMAND.md` | Agent Bootstrap Command Block | This document provides a comprehensive bootstrap command block for remote agents to quickly connect to and integrate with the NixOS AI Stack. |
| `AI-STACK-IMPROVEMENT-PLAN.md` | archived/moved | `/docs/archive/root-docs/AI-STACK-IMPROVEMENT-PLAN.md` | AI Stack & NixOS Improvement Plan | **Document Purpose:** Cross-session, multi-agent project tracking |
| `AI-STACK-QA-PLAN.md` | archived/moved | `/docs/archive/root-docs/AI-STACK-QA-PLAN.md` | AI Stack QA & Improvement Plan — Phase 20 | **Status:** ACTIVE — work in progress |
| `AI-STACK-STATUS-REPORT.md` | archived/moved | `/docs/archive/root-docs/AI-STACK-STATUS-REPORT.md` | AI Stack Status Report | **Date:** 2026-03-02 19:00 PST |
| `AIDB_SCHEMA_GUARANTEES.md` | archived/moved | `/docs/archive/root-docs/AIDB_SCHEMA_GUARANTEES.md` | AIDB Indexing and Telemetry Schema Guarantees | This document provides the guaranteed schemas for AIDB indexing and telemetry that agents can rely on for integration. |
| `DEPLOY-OPTIMIZATIONS.md` | archived/moved | `/docs/archive/root-docs/DEPLOY-OPTIMIZATIONS.md` | Deploy Llama-Server Optimizations | **Status:** ✅ Configuration files updated, ready to deploy |
| `KNOWN_ISSUES_TROUBLESHOOTING.md` | archived/moved | `/docs/archive/root-docs/KNOWN_ISSUES_TROUBLESHOOTING.md` | Known Issues and Troubleshooting | (no summary line found) |
| `LLAMA-CPP-OPTIMIZATION-CHANGES.md` | archived/moved | `/docs/archive/root-docs/LLAMA-CPP-OPTIMIZATION-CHANGES.md` | llama.cpp Optimization Changes for AMD Cezanne APU | The llama-server was experiencing stuck slots and hanging chat completion requests, causing Continue extension timeouts. |
| `MCP.md` | archived/moved | `/docs/archive/root-docs/MCP.md` | MCP Index | This repository documents MCP usage, setup, and inventory in: |
| `MCP_SERVICE_CONTRACTS.md` | archived/moved | `/docs/archive/root-docs/MCP_SERVICE_CONTRACTS.md` | MCP Service Contracts and Health Endpoints | This document defines the standardized Model Context Protocol (MCP) service contracts and health endpoints for all agents in the NixOS AI Stack. |
| `PROMETHEUS_SLO_RULES.md` | archived/moved | `/docs/archive/root-docs/PROMETHEUS_SLO_RULES.md` | Prometheus Rules for AI Stack SLOs | This document defines the Prometheus rules for monitoring AI stack Service Level Objectives (SLOs) and ensuring system reliability. |
| `REMOTE-AGENT-SETUP.md` | archived/moved | `/docs/archive/root-docs/REMOTE-AGENT-SETUP.md` | Remote Agent Setup Guide | This document provides the necessary information for remote agents to connect to the NixOS AI Stack. |
| `SECURITY-INCIDENT-2026-03-02.md` | archived/moved | `/docs/archive/root-docs/SECURITY-INCIDENT-2026-03-02.md` | Security Incident Report: Hardcoded Credentials Discovery | **Date:** 2026-03-02 |
| `SKILLS.md` | archived/moved | `/docs/archive/root-docs/SKILLS.md` | Skills Index | This repository uses a single source of truth for skills: |
| `SYSTEM-RECOVERY-PLAN.md` | archived/moved | `/docs/archive/root-docs/SYSTEM-RECOVERY-PLAN.md` | 🚨 SYSTEM RECOVERY PLAN | **Date:** 2026-03-02 19:50 PST |
| `TESTING-MANDATE.md` | archived/moved | `/docs/archive/root-docs/TESTING-MANDATE.md` | Testing Mandate - What You Asked For | **Created:** 2026-01-09 |
| `deprecated/README.md` | archived/moved | `/archive/deprecated/README.md` | Deprecated Files | This directory contains deprecated files from previous versions of the NixOS Dev Quick Deploy project. |
| `deprecated/docs/CODE_REVIEW.md` | archived/moved | `/docs/archive/deprecated/CODE_REVIEW.md` | NixOS Dev Quick Deploy - Code Review & Analysis | **Date:** 2025-10-31 |
| `deprecated/docs/CODE_REVIEW_FINDINGS.md` | archived/moved | `/docs/archive/deprecated/CODE_REVIEW_FINDINGS.md` | Code Review Findings - Priority 1 Fixes | **Date**: 2025-01-05 |
| `deprecated/docs/DEPENDENCY_CHART.md` | archived/moved | `/docs/archive/deprecated/DEPENDENCY_CHART.md` | NixOS Quick Deploy - Dependency Chart | **Version**: 3.2.0 (Proposed Modular Architecture) |
| `deprecated/docs/FIXES_AND_IMPROVEMENTS.md` | archived/moved | `/docs/archive/deprecated/FIXES_AND_IMPROVEMENTS.md` | NixOS Quick Deploy - Fixes and Improvements | This document describes the fixes applied to the NixOS Quick Deploy script to address errors, warnings, and improve the user experience. |
| `deprecated/docs/IMPROVEMENT_SUGGESTIONS.md` | archived/moved | `/docs/archive/deprecated/IMPROVEMENT_SUGGESTIONS.md` | Suggested Improvements for nixos-quick-deploy v3.2.0 | **Status**: Comprehensive Review |
| `deprecated/docs/MODULAR_ARCHITECTURE_PROPOSAL.md` | archived/moved | `/docs/archive/deprecated/MODULAR_ARCHITECTURE_PROPOSAL.md` | Modular Architecture Proposal for nixos-quick-deploy | **Version**: 3.2.0 (proposed) |
| `deprecated/docs/README-ORPHANED-PROCESS-CLEANUP.md` | archived/moved | `/docs/archive/deprecated/README-ORPHANED-PROCESS-CLEANUP.md` | Orphaned Process Cleanup | When AI stack containers using `network_mode: host` crash or are forcibly stopped, their processes can sometimes survive outside the container context. These **orphaned processes** continue to hold ports, preventing new containers from binding to the same ports. |
| `deprecated/docs/SAFE_IMPROVEMENTS.md` | archived/moved | `/docs/archive/deprecated/SAFE_IMPROVEMENTS.md` | Safe Improvements for NixOS-Dev-Quick-Deploy | **Purpose:** Non-breaking improvements that can be safely applied |
| `deprecated/docs/WORKFLOW_CHART.md` | archived/moved | `/docs/archive/deprecated/WORKFLOW_CHART.md` | NixOS Quick Deploy - Workflow Chart | **Version**: 3.2.0 (Proposed Modular Architecture) |

## Removed Non-Document Assets (Current Working Tree)

| Legacy Path | Type | Status | Current Location | One-Line Summary |
|---|---|---|---|---|
| `ai_stack_manager.py` | `py` | archived/moved | `/scripts/governance/ai_stack_manager.py` | Compatibility shim for ai-stack-manager.py. |
| `control-center.html` | `html` | archived/moved | `/dashboard/control-center.html` | <!DOCTYPE html> |
| `dashboard.html.backup-20260102-203205` | `backup-20260102-203205` | archived/moved | `/archive/backups/dashboard/dashboard.html.backup-20260102-203205` | <!DOCTYPE html> |
| `deprecated/lib/runtime-superseded/ai-stack-containers.sh` | `sh` | archived/moved | `/archive/deprecated/lib/runtime-superseded/ai-stack-containers.sh` | AI Stack Container Registry |
| `deprecated/lib/runtime-superseded/common.sh` | `sh` | archived/moved | `/archive/deprecated/lib/runtime-superseded/common.sh` | Common Utility Functions |
| `deprecated/lib/runtime-superseded/config.sh` | `sh` | archived/moved | `/archive/deprecated/lib/runtime-superseded/config.sh` | Configuration Generation |
| `deprecated/lib/runtime-superseded/reporting.sh` | `sh` | archived/moved | `/archive/deprecated/lib/runtime-superseded/reporting.sh` | Deployment Reporting |
| `deprecated/lib/runtime-superseded/service-conflict-resolution.sh` | `sh` | archived/moved | `/archive/deprecated/lib/runtime-superseded/service-conflict-resolution.sh` | Service Conflict Resolution Library |
| `deprecated/lib/runtime-superseded/tools.sh` | `sh` | archived/moved | `/archive/deprecated/lib/runtime-superseded/tools.sh` | Additional Tools Installation |
| `deprecated/lib/runtime-superseded/validation.sh` | `sh` | archived/moved | `/archive/deprecated/lib/runtime-superseded/validation.sh` | Validation Functions |
| `deprecated/nix/modules/services/mcp-servers-oci.nix` | `nix` | archived/moved | `/archive/deprecated/nix/modules/services/mcp-servers-oci.nix` | { lib, config, pkgs, ... }: |
| `deprecated/nixos-quick-deploy-v3.0.0.old` | `old` | archived/moved | `/archive/deprecated/nixos-quick-deploy-v3.0.0.old` | NixOS Quick Deploy for AIDB Development |
| `deprecated/nixos-quick-deploy.sh.backup-v3.0.0` | `0` | archived/moved | `/archive/deprecated/nixos-quick-deploy.sh.backup-v3.0.0` | NixOS Quick Deploy for AIDB Development |
| `deprecated/scripts/monitoring-bashware/generate-dashboard-data-lite.sh` | `sh` | archived/moved | `/archive/deprecated/scripts/monitoring-bashware/generate-dashboard-data-lite.sh` | Dashboard Data Generator - Lightweight Version |
| `deprecated/scripts/monitoring-bashware/run-dashboard-collector-full.sh` | `sh` | archived/moved | `/archive/deprecated/scripts/monitoring-bashware/run-dashboard-collector-full.sh` | Continuous Dashboard Data Collector - Full Version |
| `deprecated/scripts/monitoring-bashware/run-dashboard-collector-lite.sh` | `sh` | archived/moved | `/archive/deprecated/scripts/monitoring-bashware/run-dashboard-collector-lite.sh` | Continuous Dashboard Data Collector - Lite Version |
| `deprecated/systemd/telemetry-rotation.service` | `service` | archived/moved | `/archive/deprecated/systemd/telemetry-rotation.service` | Description=Telemetry Log Rotation |
| `deprecated/systemd/telemetry-rotation.timer` | `timer` | archived/moved | `/archive/deprecated/systemd/telemetry-rotation.timer` | Description=Daily Telemetry Log Rotation |
| `enable-cosmic-power-profiles.patch` | `patch` | archived/moved | `/archive/patches/enable-cosmic-power-profiles.patch` | --- /etc/nixos/nixos-improvements/mobile-workstation.nix.orig |
| `fix-llama-hang.sh` | `sh` | archived/moved | `/scripts/deploy/fix-llama-hang.sh` | Fix llama-server hanging and Continue extension issues |
| `generated_code.py` | `py` | archived/moved | `/scripts/testing/generated_code.py` | Compatibility shim for generated-code.py. |
| `launch-dashboard.sh` | `sh` | archived/moved | `/scripts/deploy/launch-dashboard.sh` | set -euo pipefail |
| `output.txt` | `txt` | archived/moved | `/archive/temp-artifacts/output.txt` | print("test") |
| `requirements.txt` | `txt` | archived/moved | `/archive/deprecated/requirements.txt` | AI Stack Python Requirements |
| `test-continuous-learning-demo.py` | `py` | archived/moved | `/scripts/testing/test-continuous-learning-demo.py` | Continuous Learning System Test |
| `test-learning-simple.sh` | `sh` | archived/moved | `/scripts/testing/test-learning-simple.sh` | Simple continuous learning test |
| `test_vim_yank.py` | `py` | archived/moved | `/scripts/testing/test_vim_yank.py` | Compatibility shim for test-vim-yank.py. |
| `verify-profile-cleanup.sh` | `sh` | archived/moved | `/scripts/governance/verify-profile-cleanup.sh` | Verification Script for Home Manager Profile Cleanup Fix |
| `vim_yank_implementation.py` | `py` | archived/moved | `/scripts/testing/vim_yank_implementation.py` | Compatibility shim for vim-yank-implementation.py. |

## Potentially Recoverable Features

### Deploy
- **Recovery and rollback runbooks** from `SYSTEM-RECOVERY-PLAN.md`, including operator-safe rollback and degraded-state handling.
- **Deploy optimization patterns** from `DEPLOY-OPTIMIZATIONS.md` and `LLAMA-CPP-OPTIMIZATION-CHANGES.md` that may still apply to model-serving bottlenecks.
- **Legacy modular orchestration ideas** from `MODULAR_ARCHITECTURE_PROPOSAL.md` and `WORKFLOW_CHART.md` that could inform future deploy script decomposition.

### Security
- **Incident-response and hardening playbooks** from `SECURITY-INCIDENT-2026-03-02.md` and `SAFE_IMPROVEMENTS.md`.
- **Schema/integrity guardrails** from `AIDB_SCHEMA_GUARANTEES.md` and `MCP_SERVICE_CONTRACTS.md` for strict interface validation.
- **Deprecated runtime-superseded security controls** in `/archive/deprecated/lib/runtime-superseded/` worth mining for edge-case handling.

### Dashboard
- **Collector and telemetry rotation patterns** from archived monitoring scripts under `/archive/deprecated/scripts/monitoring-bashware/`.
- **Operator control-center UX concepts** from `control-center.html` backup lineage and dashboard integration summaries.
- **Historic dashboard service/timer wiring** in archived unit files that may contain useful operational defaults.

### PRSI
- **QA and evaluation loop expansions** from `AI-STACK-QA-PLAN.md` and `TESTING-MANDATE.md`.
- **Failure and troubleshooting corpora** from `KNOWN_ISSUES_TROUBLESHOOTING.md` for future auto-remediation rule expansion.
- **Retention of legacy test artifacts** moved into `scripts/testing/` (e.g., continuous-learning and vim-yank experiments) for regression harness reuse.

### MCP
- **Service contract standardization** from `MCP.md` and `MCP_SERVICE_CONTRACTS.md` for endpoint and health consistency.
- **Remote-agent setup and bootstrap patterns** from `REMOTE-AGENT-SETUP.md` and `AGENT_BOOTSTRAP_COMMAND.md`.
- **Archived MCP service module variants** in `/archive/deprecated/nix/modules/services/` that may contain deployment fallback logic worth reevaluating.

## Notes
- This file records state before any final hard-deletion cleanup.
- `unresolved` entries should be reviewed manually before permanent removal.
- For implementation reevaluation, search this file by feature terms (e.g., `MCP`, `recovery`, `optimizer`, `workflow`, `security`, `telemetry`).
