---
doc_type: design-review
id: herdr-escalation-adjudication-20260816
title: "Orchestrator adjudication — herdr review_repair_integration_coverage escalation"
status: complete
parent_prd: herdr-agent-operations
reviewer: claude-opus-4-8
verdict: PASS
owner: hyperd
date: 2026-08-16
---

# Orchestrator adjudication — herdr `review_repair_integration_coverage` escalation

## Decision
**DEFER the redundant structured-`UNKNOWN` integration-replay case; ACCEPT the slice.**

The convergence review (REVIEW-CONVERGENCE-REV2-INDEPENDENT-REVIEW-20260815.md) escalated with all
material behaviors proven through the real `run_loop` and one residual: a structured `UNKNOWN` verdict
is rejected by the pure consumer oracle but not separately replayed through the integration harness.
Per the convergence stop, the orchestrator must defer-explicitly or reject. This adjudication defers it,
which earns the slice its acceptance trailer.

## Basis — 3-way convergence, orchestrator-VERIFIED (not asserted)
- **Local Qwen** (`local-20260816-112609-kpz157`): DEFER — redundant composition case, no functional
  risk to integrated state, low technical debt.
- **Antigravity** (ANTIGRAVITY-HERDR-ESCALATION-ADVISORY-20260816.md): DEFER/accept, with two code
  claims — now independently verified against source by the orchestrator:
  1. **Same equivalence class — VERIFIED.** `ai-stack/local-agents/loop_state.py:181-182`:
     `if verdict not in {"APPROVED","REJECTED"} ... : return "escalated", {"reason":
     "unknown_or_concerns_review"}`. Every non-APPROVED/REJECTED verdict — `UNKNOWN` AND `CONCERNS`
     — falls into the identical branch and returns the identical tuple. There is no `UNKNOWN`-specific
     code to exercise.
  2. **`CONCERNS` already replayed through the real `run_loop` — VERIFIED.**
     `scripts/testing/test-aq-loop-review-repair-guard.py:52-54`: `for bad in (None, {"verdict":
     "CONCERNS",...}): terminal_case([bad]); assert rc==1 and phases[-1]=="ESCALATED" and "COMPLETE"
     not in phases and len(escalations)==1`. `terminal_case` feeds the verdict through
     `fanout_verify` into `aq_loop.run_loop` (line 49) — the real integration harness — proving
     nonzero ESCALATED, no false COMPLETE, exactly one durable escalation for a representative of the
     invalid-verdict equivalence class.
- **Orchestrator conclusion:** replaying `UNKNOWN` through `run_loop` exercises the same code path with
  the same asserted outcome as the existing `CONCERNS` replay → genuinely redundant, no new coverage.

## Residual risk + mitigation (documented, accepted)
If a future change makes `consume_review_result` handle `UNKNOWN` differently from `CONCERNS` (separate
branch/logic), the integration suite would not catch a regression specific to `UNKNOWN`. Mitigated by
the existing unit-level oracle assertion (test line 21 replays `CONCERNS`/invalid verdicts through
`consume_review_result` directly), which fails immediately on any such divergence. If such a change is
ever made, add the integration replay in that same slice (bounded follow-up), not now.

## Rule 18 substitution + catch-up
Codex is the usual herdr owner and is quota-down until ~Aug 21. Per the never-go-down model this
adjudication was routed to local + Antigravity and decided by the Claude flagship orchestrator
(independent of herdr — did not implement it). Recorded as catch-up C7 for Codex to MODIFY/confirm
against current bytes on return: advisory unless it surfaces a real defect → bounded follow-up, never a
history rewrite. This defer decision does not rewrite herdr code and grants no runtime activation.
