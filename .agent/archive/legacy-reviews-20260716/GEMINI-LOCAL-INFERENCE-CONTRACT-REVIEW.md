# Gemini Architect Review — Canonical Local Inference Contract PRD
**Date**: 2026-07-12  **Agent**: Antigravity/Gemini  **Role**: Designated Independent Reviewer

## Verdict
REQUEST_REVISION (Requires Contract/Schema Enhancements for Streaming, Cancellation, and Privacy Filters)

---

## 1. Architectural & Design Assessment

We have evaluated `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md` for architectural integrity, protocol robustness, and potential integration friction.

### A. Shared Python Control Plane
*   **Assessment:** Extracting a shared library under `scripts/ai/lib/` is **approved**.
*   **Rationale:** Having `delegate-to-local` (batch) and `aq-chat` (interactive) call a single Python API prevents configuration drift, duplicate prompting logic, and payload divergence. It eliminates the need for `aq-chat` to execute shell processes to run local models.

### B. Contract Completeness
*   **Assessment:** The request, result, and progress event contracts are structurally comprehensive but have minor gaps regarding streaming protocols and cancellation mechanics.

---

## 2. Identified Gaps & Missing Requirements (Revision Items)

We request that the PRD be updated to address the following omissions before implementation authorization is granted:

### A. Streaming & Cancellation Protocols
*   **Omission:** The `aq.local-inference-request/1.0` schema lack a `stream: boolean` option. Furthermore, the cancellation interface is not defined.
*   **Requirement:**
    1. Add `"stream": "boolean"` to the request schema.
    2. Define the callback/generator interface for streaming content chunks, token counts, and tool invocation status.
    3. Specify the cancellation mechanism (e.g. process signal handling or tracking request IDs to local PID mappings so that calling `aq-chat` can instantly abort active Llama.cpp generation without leaking subprocesses).

### B. Context Privacy Filter
*   **Omission:** Local models may ingest files containing secrets, PII, or credentials during context loading.
*   **Requirement:** Mandate a lightweight, offline regex/rule scanner in the context builder (`scripts/ai/lib/`) that scrubs potential credentials, tokens, and private keys from the context before constructing the final Llama payload.

### C. Explicit Fallback Toggle
*   **Omission:** Rollback procedures are described but lack a concrete, testable mechanism.
*   **Requirement:** Require the implementation of a standard environment variable (e.g., `AQ_LEGACY_LOCAL=1`) that makes `aq-chat` and the dispatch system instantly fallback to the legacy shell-based pipeline if unforeseen drift or runtime failures occur in the consolidated Python adapters.

### D. History Truncation Policy
*   **Omission:** The prompt context adapter's behavior for chat history is underspecified.
*   **Requirement:** Specify a clear truncation algorithm (e.g., sliding window capped at 4 messages plus a semantic summary) to ensure conversation history doesn't exhaust local VRAM budgets.

---

## 3. Risk Assessment by Caller Tier

| Caller Tier | Risk Level | Specific Risk | Mitigation |
|---|---|---|---|
| **Flagship** | **Medium** | Low-quality or semantic drift in local tool validation results corrupting the main orchestration state. | All local validation outputs must be treated as untrusted; the flagship must perform high-level schema checks and sanity audits before integrating local evidence. |
| **Standard** | **Low** | Queue congestion on concurrent local execution blocking standard implementation steps. | Enforce strict priority queueing (interactive first) and a mandatory queue-wait timeout in the dispatch layer. |
| **Budget** | **High** | Token budget exhaustion or process timeouts on large files. | The eligibility engine must reject undecomposed task shapes for budget callers immediately before scheduling. |

---

## 4. Delivery and Validation Plan

The proposed delivery slices (**L1 → L2 → L2b → L3 → L4 → L5**) are logically ordered and approved.

### Proposed Acceptance Tests:
1.  **Schema Enforcement Test:** Submit request objects missing required fields, containing invalid paths, or with escalated tool authorities to verify that the validation library fails closed before reaching the Llama runtime.
2.  **Parity Test:** Create a script that generates identical request envelopes from `aq-chat` and `delegate-to-local` for a set of mock tasks, verifying that the selected lane, prompt template, and token limits are identical.
3.  **Cancellation Test:** Trigger a long local-agent task and send a cancel event to verify that the Llama subprocess terminates within 200ms and resource metrics are recorded accurately.
