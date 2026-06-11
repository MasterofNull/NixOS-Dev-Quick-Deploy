---
phase: 150
candidate_id: delegation-reduce-delegated-prompt-failure-provider-http-er-4831c4de2f50
category: delegation-quality
priority: 2
trust_score: 0.8
relevance_score: 0.91
status: draft
created: 2026-06-11
---

# Phase 150 — Reduce delegated prompt failure: provider_http_error

## Origin
Adopted candidate from discovery pipeline (trust=0.8, relevance=0.91).
Source: candidate ID `delegation-reduce-delegated-prompt-failure-provider-http-er-4831c4de2f50`.

## Problem Statement
failure_class=provider_http_error; aq-qa probe 71.4: respond with the word OK only

## Proposed Action
Investigate evidence and implement fix for: Reduce delegated prompt failure: provider_http_error

## Acceptance Criteria
- [ ] Implementation matches proposed_action scope
- [ ] Tier0 validation gate passes
- [ ] QA phase 0 passes (all checks green)
- [ ] RAG seeded with bug/fix pattern if applicable
- [ ] PULSE.log updated

## Implementation Notes
_Fill in during implementation._

## Out of Scope
_Fill in during planning._

## References
- Candidate pipeline: `.agents/improvement/candidates.json`
- Trust scoring: `ai-stack/local-agents/trust_scoring.py`
- Eval sandbox: `ai-stack/local-agents/eval_sandbox.py`
