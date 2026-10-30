# CI activation wave 1 (2026-10-29)

Plan: capability-integration. Items: ci-1 (usage logging), ci-10 (query expansion).

## ci-1: aq-* usage logging restored (ENABLED in code)

`scripts/testing/test-aq-usage-logging.py` failed its coverage check: 20 newer executable entrypoints in `scripts/ai/` lacked the hook.
The same hook idiom as `aq-hints` / `aq-capability-index` (python `try:  # aq-usage-hook` block) or `aq-session-start` (bash `. lib/aq-shim.sh` line) was added to each. No other behavior changed. For python scripts with `from __future__` the hook sits after that import.

Hooked: aq-agent-auth, aq-confine, aq-decide, aq-durable, aq-durable-sweeper, aq-help-center, aq-hermetic-eval, aq-hook-post-tool, aq-hook-session-start, aq-hook-stop, aq-human-intervention, aq-keep-awake, aq-llama-resume-gate (bash), aq-llm-speed-probe, aq-network-policy, aq-oncalld, aq-radar-ingest, aq-review-request, aq-skill-eval, aq-triage.

Validation: `python3 scripts/testing/test-aq-usage-logging.py` -> `PASS: aq-* usage logging (...coverage, audit preference)`; all python entrypoints `ast.parse` clean.

Verify live: run any hooked command (e.g. `aq-triage --status`), then `tail -1` the ledger (`AQ_USAGE_LEDGER`, default aq-usage.jsonl) and confirm a row with `tool":"aq-triage"`. Kill switch: `AQ_USAGE_TELEMETRY=0`.
Note: aq-hook-post-tool / -stop / -session-start fire per Claude event, so they add ledger rows at high frequency; the hook is non-fatal and stores no argument values.

Rollback: revert the hook lines (git revert of this change); the coverage test will fail again by design.

## ci-10: query expansion NOT enabled (decision)

Findings:
- `QUERY_EXPANSION_ENABLED` (core/config.py:239) has no consumer anywhere in ai-stack (rg confirms; consistent with 2026-10-08-mvp-activation-batch). A Nix option for it would be decorative (Rule 23), so none was added.
- The live expansion path is `AI_LLM_EXPANSION_ENABLED` (config.py:285, default false): route_handler.py ~1351-1423 launches `QueryExpander.expand_with_llm` (POST `/v1/completions` to local llama, max_tokens 150) on semantic/hybrid routes, awaited before search, bounded by `min(adaptive_timeout, AI_LLM_EXPANSION_TIMEOUT_S=4.0)`.
- On this machine (Qwen3.6-35B, ~5.3 tok/s gen, 8 tok/s prompt, single slot) 150 tokens takes ~30s, so the 4s timeout would nearly always fire: no benefit, plus an orphaned in-flight completion competing for the single llama slot with the real query. It is a per-query LLM call, so it was left OFF; no Nix wiring added, ai-dev.nix unchanged.
- Observability today: only `logger.info("query_expansions", count, route)` on success and a debug log on skip; no counter/latency metric. Not added since the feature stays off.

Path to ACTIVATED (follow-up, not done): gate expansion on a measured speed probe (aq-llm-speed-probe) or use a cheap non-LLM expander; add a hit/timeout counter; then add a typed Nix option for `AI_LLM_EXPANSION_ENABLED` and enable in ai-dev.nix; delete or wire the dead `QUERY_EXPANSION_ENABLED`.

tracker.json: editorial_note on ci-10 updated (detection signals unchanged; they are commit_match based).
