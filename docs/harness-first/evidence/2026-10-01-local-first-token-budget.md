# Evidence — local first-token budget scales with prompt size (2026-10-01)

## Objective
Fix RSI incident e5d253ff: local tasks failed on a fixed first-token timeout while prompt processing scaled with prompt size.

## Root cause
`scripts/ai/aq-agent-loop` sets a fixed `LLAMA_FIRST_TOKEN_TIMEOUT`; `ai-stack/local-agents/agent_executor.py` `_call_llama` enforced it regardless of prompt length. A 4.7k-token prompt needed 930s at ~5 tok/s (swap-drift) and was cancelled 30s before its first token; `_execute_with_tools` then retried the identical prompt with max_tokens=512, re-processing it in full (no cache reuse on this hybrid/SWA model).

## Change
Budget = max(floor, min(cap, est_prompt_tokens / prompt_eval_rate x 2)); rate from llama.cpp `/metrics` (`llamacpp:prompt_tokens_seconds`), fixed value on any failure. Env: `LLAMA_FIRST_TOKEN_SAFETY`, `LLAMA_FIRST_TOKEN_CAP` (3600), `LLAMA_FIRST_TOKEN_ADAPTIVE=0` to disable. A first-token timeout now fails fast instead of the same-prompt retry; other errors keep the one retry.

## Validation
test-agent-loop-first-token-budget 21 checks; existing agent-loop suites (bounds 16/16, event-streaming, result-quality, task-id-collision, first-token-timeout) pass.

## Rollback
`LLAMA_FIRST_TOKEN_ADAPTIVE=0` or revert the commit.

## Limits
Rate is the server's last measured value (may be stale right after restart; falls back to the fixed value when 0/absent). chars/4 token estimate (no client tokenizer in the codebase).

## Agents
Implementer: Claude Sonnet (worktree). Review: Claude Opus.
