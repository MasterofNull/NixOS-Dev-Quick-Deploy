# Track V (Verified Factory) — Slice VF-7 Evidence Path Implementation Authorization

**Date:** 2026-07-20  
**Author:** Antigravity Flagship Reviewer  
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**  
**Track:** Track V (Verified Factory Throughput Layer — Cross-Cutting)  
**Parent Architecture:** Codex-Fable Synthesis (`.agent/PROJECT-LOCAL-AI-FACTORY-CODEX-FABLE-SYNTHESIS.md`)  
**Base Commit:** `66391367`  

---

## 1. Executive Summary & Objective

This document defines the single-use implementation authorization for **Slice VF-7 (Guaranteed Unwrapped Evidence Execution Path)** under Track V of the AQ-OS Unified Program.

Currently, evidence collected during test runs can suffer from formatting distortion or truncation when passed through tool wrappers (e.g. lean-ctx stdout compression). Slice **VF-7** introduces a dedicated, unwrapped, raw binary evidence collector (`scripts/governance/aq-evidence-collector.py`) that writes immutable, hash-verified audit traces directly to `.agents/events/a2a-events.jsonl` without modifying tool wrappers or context compression layers.

This authorization packet is **PREPARED_ONLY**. It provides a pre-ratified, fail-closed contract for implementor agents. Implementation and code modifications remain unauthorized until an explicit hash-bound Owner Activation Record is issued.

---

## 2. Bound File Inventory & File Ceiling

The implementation of Slice VF-7 is strictly bound to a **maximum ceiling of 5 files**:

| Action | Relative File Path | SHA-256 Pre-State / Purpose |
|---|---|---|
| **NEW** | `scripts/governance/aq-evidence-collector.py` | Standalone, unwrapped evidence recording utility |
| **NEW** | `config/schemas/aq-evidence-record-v1.json` | Draft 2020-12 schema for unwrapped execution evidence records |
| **NEW** | `scripts/testing/test-aq-evidence-collector.py` | Focused unit & integration test suite for evidence hashing |
| **MODIFY** | `scripts/governance/tier0-validation-gate.sh` | Register evidence collector verification step |
| **NEW** | `.agents/plans/verified-factory/VF-7-FLAGSHIP-REVIEW.md` | Independent flagship review verdict record |

> [!CAUTION]
> Any edit to a 6th file or modification of core inference/database paths constitutes a **MANDATORY FAIL-STOP** and immediately voids this authorization.

---

## 3. Invariant Rules & Security Constraints

1. **Unwrapped Output Guarantee:** `aq-evidence-collector.py` MUST operate on raw stdout/stderr streams without passing through context compression or line-stripping filters.
2. **SHA-256 Digest Immutability:** Every recorded evidence block must compute an immutable SHA-256 digest of `(timestamp + payload_bytes + caller_agent_id)`.
3. **No Environment/Secret Logging:** The evidence collector MUST redact environment variables, bearer tokens, and private SSH/OAuth keys prior to writing records.
4. **Append-Only Event Ledger:** Writes to `.agents/events/a2a-events.jsonl` MUST be append-only with transactional file locking (`fcntl.flock`). Modifying or truncating historical event lines is prohibited.

---

## 4. Verification & Gate Criteria

Before a candidate implementation for VF-7 can be accepted, it must pass all 4 verification gates:

```bash
# 1. Evidence Collector Verification Suite
python3 scripts/testing/test-aq-evidence-collector.py

# 2. Syntax & Compilation Check
python3 -m py_compile scripts/governance/aq-evidence-collector.py

# 3. AQ-QA Phase 0 Machine Diagnostic
aq-qa 0 --machine

# 4. Tier-0 Validation Gate
scripts/governance/tier0-validation-gate.sh --pre-commit
```

---

## 5. Authorization Status

`RECORD (superseded): status = PREPARED_ONLY; implementation_authorized = FALSE; pending_owner_activation = TRUE`

## 6. Owner Activation Record (2026-07-22)

The contract in Sections 1–4 was independently re-reviewed for soundness by a fresh Opus flagship
against SHA-256 `71c5df38e736c48d86371c9aff294299e1c1dd0896adb80e4186b762547a1741`
(verdict: PASS — `.agents/plans/stream-auth-rereview/claude.md`; the original Antigravity review had
cited a non-matching hash). Non-blocking reviewer note carried to implementation: tag evidence records
with a `kind` discriminator since `.agents/events/a2a-events.jsonl` is shared with `aq-event`
pulse/resume, so existing consumers can filter. The owner has activated implementation under standing
authorization; the activation event is recorded in `.agent/collaboration/PULSE.log`
(`[owner] [implementation-activated]` naming this slice, implementer `claude-subagent-vf-7-implementer`).

`RECORD (active): status = ACTIVATED; implementation_authorized = TRUE; pending_owner_activation = FALSE;
implementer = claude-subagent-vf-7-implementer; contract_soundness_reviewed_hash = 71c5df38e736c48d86371c9aff294299e1c1dd0896adb80e4186b762547a1741; acceptance_lane = codex`

The 5-file ceiling, invariants, and verification gates in Sections 2–4 remain binding and unchanged.


## Owner Activation Record (reconciled 2026-07-23)
**Activation state: ACTIVATED** (record reconciled from the authoritative event ledger).
Owner activation recorded as a `pulse.append` in `.agents/events/*.jsonl` — subject `auth-verified-factory-vf-7`, event_id `6b738ae183f341dc8d6ae386ff6981cb`, ts `2026-07-22T16:44:07Z`. Any `PREPARED_ONLY / NOT ACTIVATED` status earlier in this record is a **stale header** predating the activation; the owner activation and any independently-accepted, committed candidate stand. Reconciled by fable-5 (no scope, ceiling, or hash change — header hygiene only).
