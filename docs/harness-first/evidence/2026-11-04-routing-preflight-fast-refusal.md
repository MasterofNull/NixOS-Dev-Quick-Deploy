# Routing preflight fast refusal (2026-11-04)

## Objective
Make local preflight refuse an impossible output budget fast. QA check 0.12.9 ran `local_preflight.py` with `--max-tokens 10000000` and took 16-50 s, failing intermittently under load against its 60 s timeout. Root cause: the refusal happened only after task classification (`aq_decide` retraining, about 10 s), the embedded-assist prefetch against a live switchboard (about 8 s) and heavy imports. When an explicit `--max-tokens` is already at or above the context limit, the prompt cannot matter, so the refusal now happens before any of that work. Backlog item: ROUTING-PREFLIGHT-SLOW-QA-0.12.9-FLAKY.

## Workflow/Session IDs
Branch `fix/routing-preflight-fast-refusal` (from origin/main), worktree `.agents/delegation/worktrees/preflight-fast-refusal`. Orchestrator session 06eebc53-2284-45b0-b12f-5fbdefb7d0e9.

## Delegation Decision
Implementer: Claude Sonnet (Rule 17, bounded single slice, cheapest eligible Claude lane). Orchestrator: claude-opus, 2026-11-04. No local inference was started.

## Commands Executed
- `python3 scripts/testing/test-dispatch-preflight.py`
- `python3 scripts/testing/test-worktree-isolation.py`
- `python3 -c "import ast; ast.parse(open('scripts/testing/harness_qa/phases/phase0.py').read())"`
- The exact 0.12.9 fixture command, timed 3 times against the HEAD version of the library and 3 times against the changed tree.

## Validation Evidence
- test-dispatch-preflight.py: 24 tests, OK (three new FastRefusalTests).
- test-worktree-isolation.py: PASS.
- phase0.py parses.
- Fixture timing before (HEAD code, default env, live switchboard): 8.74 s, 8.67 s, 8.69 s, rc 3.
- Fixture timing after (hermetic env): 0.33 s, 0.33 s, 0.36 s, rc 3, reason `output_budget_exceeds_context`.
- Exit code, stderr JSON shape, registry row fields and output file are unchanged. A missing context limit still refuses with `preflight_no_limit`.

## Rollback Plan
Revert the change to `scripts/ai/lib/local_preflight.py`, `scripts/ai/lib/dispatch_evidence.py`, `scripts/testing/harness_qa/phases/phase0.py` and the added tests. The normal measured path is untouched, so revert is safe at any time.

## Residual Risk
The aq_decide classifier retrain (about 10 s per call) is still on the normal path for prompts that do not hit the fast refusal. That is a separate follow-up. The fast path uses the caller's `--role` value as given (it may be `auto`) in the registry row, since role resolution runs after the fast path.

## Hint Feedback
No aq-hints were consulted for this slice. Useful context came from the profile of the slow run: classification, prefetch and imports dominate.
