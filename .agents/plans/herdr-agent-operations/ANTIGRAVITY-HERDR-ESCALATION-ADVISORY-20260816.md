---
doc_type: design-review
id: antigravity-herdr-escalation-advisory-20260816
title: "Antigravity advisory — herdr review-repair escalation adjudication"
status: complete
parent_prd: herdr-agent-operations
reviewer: antigravity
verdict: PASS
owner: hyperd
date: 2026-08-16
---

# Antigravity Advisory: HERDR Review-Repair Escalation Adjudication

**Author:** Antigravity (Advisory Lane)  
**Date:** 2026-08-16  
**Subject:** HERDR `review_repair_integration_coverage` Escalation Adjudication  
**Target File:** `.agents/plans/herdr-agent-operations/ANTIGRAVITY-HERDR-ESCALATION-ADVISORY-20260816.md`  

---

## 1. Adjudication Verdict

**Verdict:** (a) DEFER this redundant `UNKNOWN`-replay case explicitly and accept the slice.

---

## 2. Rationale & Analysis

### A. Strongest Single Reason
In `loop_state.py::consume_review_result`, any string verdict other than `"APPROVED"` or `"REJECTED"` (including `"UNKNOWN"` and `"CONCERNS"`) falls into the exact same code branch (lines 181–182) and returns the identical tuple `("escalated", {"reason": "unknown_or_concerns_review"})`. Because `test-aq-loop-review-repair-guard.py` already replays `{"verdict": "CONCERNS"}` through the real `run_loop` integration harness, testing `UNKNOWN` at the integration level is a redundant composition case that provides no new code coverage or state validation.

### B. Unit-Level Equivalence
Yes, the unit-level oracle rejection is genuinely equivalent to an integration-level replay for this case. The transition function is pure, and `aq-loop` processes all `"escalated"` outcomes via a uniform control path. Testing one representative of the invalid-string equivalence class (`CONCERNS`) in the integration loop is sufficient to prove the safety of the control path.

### C. Concrete Risk of Deferring
The only risk is future divergence: if a developer subsequently modifies `consume_review_result` to handle `"UNKNOWN"` differently from `"CONCERNS"` (e.g., adding custom retry or logging logic specific to unknown verdicts) and does so incorrectly, the integration test suite would fail to catch the regression. This risk is mitigated by the existing unit-level assertion in `test-aq-loop-review-repair-guard.py`, which would still fail immediately upon any such change.
