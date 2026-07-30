# AQ-OS Unified Program — Agent Lane Eligibility Matrix (Owner Decision Q5)

**Document Date:** 2026-07-20  
**Status:** RATIFIED POLICY SPECIFICATION  
**Governing Standard:** Owner Decision Q5 (Measured, Expiring Lane-Eligibility Registry)  
**Parent Architecture:** Codex-Fable Synthesis (`.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md`)  

---

## 1. Overview & Policy Objective

To prevent task timeouts, VRAM exhaustion, context truncation, and unauthorized multi-file mutations during autonomous operations, all task delegations MUST adhere to the **Measured Lane Eligibility Matrix**.

Tasks are matched to agents based on **measured empirical capacity**, model topology, and security authorization boundaries.

---

## 2. Agent Eligibility Matrix

| Agent Identity | Model / Family | Authorized Role | Max File Modification Ceiling | Max Execution Timeout | Permitted Operations |
|---|---|---|---|---|---|
| **Codex** | Remote / Orchestrator | Orchestrator / Reviewer / Lead | 10 Files | 3600s | Session management, slice delegation, PRD authoring, Tier0 gate execution, PR merges |
| **Antigravity** | Remote Flagship | Flagship Reviewer / Security Auditor | 5 Files (Plans/Docs only) | 1800s | Independent architecture review, PRD verification, audit reports, PASS/FAIL verdicts |
| **Qwen3 (Local)** | Qwen3-35B Local | Bounded Implementor | 1 File | 1800s | Single-file implementation, unit test creation, localized bug fixes |
| **Claude** | Remote Auxiliary | Secondary Reviewer / Writer | 5 Files | 1800s | Documentation compilation, test fixture authoring, secondary review |

---

## 3. Mandatory Task Shaping Rules

1. **Single-Edit Rule for Local Agent (Qwen3):** Local inference tasks MUST be scoped to a single file modification per slice. Multi-file refactors must be broken into single-file sub-tasks by the Orchestrator.
2. **Timeout Floor:** No local inference task may be dispatched with a timeout shorter than 1800 seconds under slot contention.
3. **No Self-Acceptance:** An agent that authors code within a slice is strictly prohibited from reviewing or accepting its own work.
4. **Expiry Enforcement:** Lane eligibility entries automatically expire after 14 days without empirical telemetry validation.
