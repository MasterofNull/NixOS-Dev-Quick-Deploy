# Harness-First Task Evidence

Date: 2026-10-07
Task ID: HF-20261007-009

## Objective
- Crystallizer live run after #386/#387 failed at distillation: coordinator local LLM client hardcodes httpx timeout=120s; APU prefill+generation for a ~6k-token transcript exceeds it (httpx.ReadTimeout, retried with full re-prefill). Add per-client timeout (crystallizer 900s, env CRYSTALLIZER_LLM_TIMEOUT_S) and a 6000-char history budget.

## Workflow/Session IDs
- Workflow ID: wf-crystallizer-local-timeout-20261007
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f; failing request_id c01a2874e6e94268aa2d4ff26069ad02

## Delegation Decision
- Implemented by Claude Opus 5.5 directly (Rule 17 exception: ~10-line change with live diagnosis context; delegation overhead >> change). Review: Antigravity (autonomous lane) before merge.

## Commands Executed
```bash
python3 -m pytest -q tests/test_memory_crystallizer_sessions.py tests/test_memory_crystallizer.py tests/test_llm_client.py tests/test_cognitive_intelligence_l5_l6.py
# live replay of the exact distillation request (budgeted prompt, max_tokens 500) via switchboard, client timeout 1200s
```

## Validation Evidence
- Live failure: coordinator log `Local switchboard API error: ReadTimeout('')` → `distillation failed` (request c01a2874…).
- 44/44 tests PASS (incl. timeout override default 120 / custom 900; prompt budget).
- Live replay through switchboard completed within the 1200s window and returned 8 bulleted facts (7 accurate, 1 inaccurate — local model quality caveat). Exact elapsed not captured.

## Rollback Plan
- Revert; rebuild + restart coordinator.

## Residual Risk
- Retry-on-timeout in LLMClient re-prefills; with 900s timeout a stuck slot can hold a crystallize task up to ~45 min (3 tries) — bounded by nightly ≤10 sessions, background task. Fact accuracy depends on local model (no verification step yet).

## Hint Feedback
- No aq-hints consulted.
