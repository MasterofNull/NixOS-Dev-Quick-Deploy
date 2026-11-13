# Codex headless cap raised to 1M; refusal names it a local cap (2026-11-13)

Owner directive 2026-11-13: raise the Codex cap permanently.

- `scripts/ai/delegate-to-codex`: `DELEGATE_CODEX_DAILY_TOKEN_BUDGET` default 250000 -> 1000000 (rolling 24h,
  headless only). The 40% review reserve (`DELEGATE_CODEX_REVIEW_RESERVE_PCT`) is unchanged. The env var still
  overrides.
- The refusal text changed from "daily headless budget exhausted" to "local headless cap reached (self-imposed, not
  provider quota; codex itself may still work)".

Why: the 250000 cap was hit repeatedly (325593 on 2026-11-06, 301424 on 2026-11-13), and agents relayed the old
message as "Codex is out" while the provider quota was fine. On 2026-11-13 a live `codex exec` probe returned OK,
and there was no `.agents/delegation/.codex-quota-cooldown`. Real provider exhaustion is still detected separately
by the quota precheck (cooldown file, parsed 429/usage-limit).

Evidence:
- `scripts/testing/test-delegate-headless-budget.py`: 7/7 passed.
- `scripts/testing/test-delegate-codex-quota-precheck.sh`: 22 passed, 0 failed.
- `delegate-to-codex --budget-check-only --role review` from the branch: review headroom 523780 (was 0).

Activation: the script runs from the checkout, so a main checkout sync applies it. No rebuild is needed.
Observable via `delegate-to-codex --budget-check-only`; intervenable via `DELEGATE_CODEX_DAILY_TOKEN_BUDGET`.
