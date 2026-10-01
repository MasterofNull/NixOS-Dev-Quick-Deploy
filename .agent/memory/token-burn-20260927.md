# Codex token-consumption root cause — 2026-09-27

All previous development tasks dropped from active scope by owner. Only token incident analysis active.

## Measured evidence
Source: /home/hyperd/.codex/sessions/2026/09/27/rollout-2026-09-27T00-31-19-01a0e1c6-88ea-7572-be93-3b83798e7fa4.jsonl
Window: 14:29:51–14:59:31 UTC. Account primary usage telemetry: 0% → 100%.
56 token_usage_record entries before 15:00: 6,320,393 input; 6,163,584 cached input (97.52%); 16,694 output including 1,903 reasoning output.
First request input 26,815; last 155,361. Model gpt-6-astra; effort medium; plan telemetry plus.
After owner reported 34% remaining: 19 requests, 2,816,778 input tokens.
No native compacted records in this session. Local config has no explicit model_auto_compact_token_limit.
Two audit agents were spawned with full-history forks; additional worker tasks used compact prompts. Child/account-wide usage attribution was not established; parent totals alone do not account for all quota consumers.

## Root cause
Repeated inference over growing context (context size × model-request count), amplified by a premium main model and full-history delegation. Oversized onboarding/recovery/skill/tool reads grew the history. Repeated polling continued to send the full accumulated context, even with short replies. Cached tokens are not equivalent to a compacted prompt or free subscription usage.

Memory and lean-ctx reduce newly retrieved content only when used correctly; they do not erase previously injected history. Existing custom transcript archiving was not native context compaction. Memory CLI write failures and working-memory HTTP 500 impaired recovery but do not explain the millions of repeated tokens by themselves.

## Corrections required before resuming development
- Start a fresh/actually compacted context using this short report and the specific task checkpoint, not historical HANDOFF dumps.
- Default to a lower-cost model for routine execution; reserve Astra for bounded hard reasoning/review. Do not change owner settings without direction.
- No full-history delegation; use path + objective + acceptance criteria only.
- Bound tool return sizes before returning them to the model. Read relevant spans, not whole logs/skill catalogs.
- Wait within tool/runtime between meaningful milestones instead of repeated model-driven polling.
- Measure per-response input/cached/output tokens and quota deltas; intervene before the context or request count balloons. A byte-count transcript watchdog is not enough.
- Compact minimal AGENTS/skill/tool discovery surface; current initial prompt was already 26.8k tokens.

Official usage explanation: https://learn.chatgpt.com/docs/pricing (usage varies by model, context, reasoning, tools, retrieval and caching; no exact subscription debit formula supplied).
Analysis is complete; no claim that quota safeguards are implemented or root cause fixed.

## 2026-09-30 measured follow-up (claude-opus)
- Headless Codex: 7 dispatches ~447k tokens in one day (37k-89k each) exhausted the shared plan quota and closed the owner's interactive Codex window. Cause: fresh-session re-hydration (auto-loaded AGENTS.md + canon/skill/whole-file reads), delegates running tier0, plus orchestrator dispatch errors (uncommitted baseline; round verdicts written into isolated worktrees).
- Fixes: headless DELEGATE MODE block in harness grounding; `delegate-to-codex --effort` and a daily headless token budget (default 250k, exit 3 when exhausted, `--force-budget`); collab rounds dispatch codex `--shared`; `aq-payload-audit` measures per-lane always-on/per-turn payload and dispatch overhead (`--fail-on high` for the RSI steward sweep).
- Claude: UserPromptSubmit mandate hook (1.1KB on every prompt and notification) moved to SessionStart (486B once); always-on instruction files slimmed via canon summary mode.
