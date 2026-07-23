# Foundation B1 — Local Inference L2B-B Implementation Authorization

**Date:** 2026-07-20  
**Author:** Antigravity Flagship Reviewer  
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**  
**Track:** AQ-OS Unified Program — Foundation B1 (L-Series Completion)  
**Parent Architecture:** Codex-Fable Synthesis (`.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md`)  
**Base Commit:** `66391367`  

---

## 1. Executive Summary & Objective

This document defines the single-use implementation authorization contract for **Slice L2B-B** (Live Payload Normalization & Adoption for Local Inference). 

Slice L2B-A (`fbeffbab` / `66391367`) established the shadow transport kernel and dashboard parity fields. Slice **L2B-B** completes Foundation B1 by enforcing pure, deterministic payload normalization across both `/v1/chat/completions` and `/v1/completions` (batch) local endpoints, enforcing RFC 8259 UTF-8 canonical forms, and validating schema signatures prior to dispatch.

This authorization packet is **PREPARED_ONLY**. It provides a pre-ratified, fail-closed contract for implementor agents (Codex, Qwen3, Claude). Implementation, staging, or code commits remain unauthorized until an explicit hash-bound Owner Activation Record is issued.

---

## 2. Bound File Inventory & File Ceiling

The implementation of Slice L2B-B is strictly bound to a **maximum ceiling of 6 files** (3 modified shared files, 3 new test/schema files):

| Action | Relative File Path | SHA-256 Pre-State / Purpose |
|---|---|---|
| **MODIFY** | `scripts/ai/lib/local_inference_transport.py` | Inject pure payload normalization & canonical transformer (corrected 2026-07-20: prior path `ai-stack/local-agents/lib/...` was a phantom; this is the real L2B-A module the bound test loads) |
| **MODIFY** | `scripts/testing/test-local-inference-l2b.py` | Expand golden vectors from 8 to 14 checks (chat + batch payloads) |
| **MODIFY** | `assets/dashboard.js` | Render live payload health & normalization status in AI Services panel |
| **NEW** | `config/schemas/local-inference-payload-v1.json` | Draft 2020-12 JSON Schema for normalized local inference payloads |
| **NEW** | `scripts/testing/fixtures/l2b_b_golden_payloads.json` | Canonical request/response test vectors for Qwen3-35B and Llama endpoints |
| **NEW** | `.agents/plans/local-inference-l2b-b/L2B-B-FLAGSHIP-REVIEW.md` | Independent flagship review verdict record |

> [!CAUTION]
> Any edit to a 7th file, or modification of un-bound files (e.g. `nix/`, `scripts/ai/aq-chat`, or database schemas), constitutes a **MANDATORY FAIL-STOP** and immediately voids this authorization.

---

## 3. Invariant Rules & Security Constraints

1. **VRAM Pool Rule (Strict Concurrent Lock):** Concurrency between 35B and 8B models in VRAM is strictly prohibited. Normalization logic must reject concurrent allocations exceeding the 27 GB resident budget.
2. **Deterministic Canonical Normalization:** All local inference payloads must undergo NFC UTF-8 normalization, key sorting, and removal of non-finite floats prior to dispatch.
3. **No Environment API Key Leaks:** Local transport MUST NEVER inject, read, or forward external API keys or cloud bearer tokens.
4. **Opaque Error Mapping:** Payload validation failures must return standardized, non-leaking error responses without exposing internal process stack traces or file system paths.
5. **Fail-Closed Execution:** If `local-inference-payload-v1.json` validation fails, dispatch must abort with status `REJECTED_SCHEMA_INVALID` and emit a structured audit trace.

---

## 4. Verification & Gate Criteria

Before a candidate implementation for L2B-B can be accepted by the orchestrator, it must pass all 4 verification gates:

```bash
# 1. Golden Payload Test Suite (Must pass 14/14 checks)
python3 scripts/testing/test-local-inference-l2b.py

# 2. Syntax & Compilation Check
python3 -m py_compile scripts/ai/lib/local_inference_transport.py

# 3. AQ-QA Phase 0 Machine Diagnostic
aq-qa 0 --machine

# 4. Tier-0 Validation Gate (Pre-Commit Enforcement)
scripts/governance/tier0-validation-gate.sh --pre-commit
```

---

## 5. Authorization Status

`RECORD (superseded): status = PREPARED_ONLY; implementation_authorized = FALSE; pending_owner_activation = TRUE`

## 6. Owner Activation Record (2026-07-22)

The contract in Sections 1–4 was independently re-reviewed for soundness by a fresh Opus flagship
(`.agents/plans/stream-auth-rereview/claude.md`), which found the ORIGINAL bound path
`ai-stack/local-agents/lib/local_inference_transport.py` was a phantom and prescribed repointing the
MODIFY target to the real module `scripts/ai/lib/local_inference_transport.py` — that correction is
applied in Section 2 (corrected authorization SHA-256 `468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe`).
The owner has activated implementation under standing authorization; the activation event is recorded
in `.agent/collaboration/PULSE.log` (`[owner] [implementation-activated]: auth-local-inference-l2b-b-corrected-reactivate`,
implementer `claude-subagent-l2b-b-implementer`, window 2026-07-22T04:20:00Z→2026-07-23T04:20:00Z).

`RECORD (active): status = ACTIVATED; implementation_authorized = TRUE; pending_owner_activation = FALSE;
implementer = claude-subagent-l2b-b-implementer; corrected_contract_hash = 468899d47fa107d87db10f3d45491d395472a46071116aa8fb9a66a142b651fe; acceptance_lane = codex`

The 6-file ceiling, invariants, and verification gates in Sections 2–4 remain binding and unchanged.


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-local-inference-l2b-b`, event_id `8293337f1915426cbf9557afbceedf2a`, ts `2026-07-21T01:41:57Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
