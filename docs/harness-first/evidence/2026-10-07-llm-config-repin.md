# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-017

## Objective
- Re-authorize stale pins of ai-stack/mcp-servers/shared/llm_config.py (changed in 116b5ae5, 2026-10-03, never re-pinned): chat-batch parity golden fixture (predecessor chain + manifest digest) and transport policy canonical_builder sha/revision.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f; Antigravity advisory antigravity-20261007-150822-tz0qt5 (RECOMMENDATION RE-PIN); delegate codex-20261007-222345-t0fo62

## Delegation Decision
- Investigation: Antigravity (author of the change) — CONTRACT-NEUTRAL; orchestrator verified the diff is exactly one added "rsi" role line. Re-authorization: Codex using the fixture's documented procedure (no hand-typed digests).

## Commands Executed
```bash
git show 116b5ae5 -- ai-stack/mcp-servers/shared/llm_config.py
python3 scripts/testing/test-local-inference-chat-batch-parity.py
python3 scripts/testing/test-local-inference-l2b.py
python3 scripts/testing/test-local-delegation-reliability.py
```

## Validation Evidence
- chat-batch parity EXIT 0 (12 pairs; 4 byte-equivalent, 8 typed-divergence evidence); L2B 16/16; policy canonical_builder sha == sha256(llm_config.py) 1901963582…, revision llm-config-20261003.
- test-local-delegation-reliability: 4 failures pre-existing on main and broader (6 frozen-source mismatches: aq-agent-loop, dispatch.py, task_registry.py, agent_executor.py, llm_config.py, switchboard.py) — NOT addressed here; tracked separately.

## Rollback Plan
- Revert commit.

## Residual Risk
- Delegation-reliability frozen-source drift remains open.

## Hint Feedback
- No aq-hints consulted.
