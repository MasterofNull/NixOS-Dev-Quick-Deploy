# Antigravity Independent Design Review: Foundation B1 — Chat/Batch Parity (Shadow) Design Packet

**Reviewer:** Antigravity (Gemini 3.6 Flash / IDE Agent Node)  
**Target:** `b1-parity-design-review`  
**Date:** 2026-07-27  
**Verdict:** `VERDICT: APPROVE-FOR-AUTHORIZATION`

---

## Executive Summary & Ruling

The Foundation B1 Chat/Batch Parity (Shadow) Design Packet is **APPROVED FOR AUTHORIZATION**. The proposed offline parity oracle provides the necessary evidence instrument to validate cross-adapter equivalence without modifying live routing or introducing runtime risk.

---

## Specific Findings & Rulings on Design Review Questions

### 1. Distinction from L2B-B
- **Ruling: DISTINCT AND MANDATORY.**
- L2B-B normalized payload construction within single endpoints (`/v1/chat/completions` and `/v1/completions`). It did not prove cross-adapter equivalence between the interactive `aq-chat` adapter and the batch `delegate-to-local` / `dispatch.py` adapter.
- Producing a deterministic, offline parity oracle is a hard PRD requirement before unblocking live L3/L4 adoption.

### 2. Implementation Feasibility (§6.1)
- **Ruling: HARNESS-DRIVE WITH STUBBED I/O IS FEASIBLE.**
- Harness-driving `aq-chat` with stubbed network/I/O parameters in the test oracle is entirely feasible within the 2-file ceiling (`test-local-inference-chat-batch-parity.py` + `local-inference-chat-batch-parity-golden.json`).
- Refactoring `aq-chat` to extract a shared pure builder is unnecessary for B1-PARITY and would violate the 2-file ceiling.

### 3. Streaming/Usage Equivalence Criteria (§6.2)
- **Legitimate Transport Differences (PASS)**:
  - Transport-level SSE framing (`data: {...}` lines, `[DONE]` markers) vs buffered JSON objects.
  - Granular delta chunks vs consolidated response bodies.
- **True Canonical Divergences (FAIL-CLOSED)**:
  - Discrepancies in canonical request fields: `mode`, `profile`, `model`, `task_type`, `role`, `tools`, `budgets`, `fallback`, `version`.
  - Inconsistent token accounting in normalized usage metrics (`prompt_tokens`, `completion_tokens`).

### 4. B1 Exit Criteria (§6.3)
- **Ruling: OFFLINE ORACLE IS SUFFICIENT FOR B1 EXIT.**
- The offline oracle proves deterministic canonical request equivalence across the 4 caller tiers and task shapes.
- Live-shadow dual-run verification should be handled as a separate follow-on slice under L3.

---

## Conclusion

**`VERDICT: APPROVE-FOR-AUTHORIZATION`**  
The design packet is approved to proceed to `B1-PARITY-IMPLEMENTATION-AUTHORIZATION.md` drafting.
