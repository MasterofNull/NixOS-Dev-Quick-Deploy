# Harness-First Task Evidence: required checks and token caps in slice briefs

Date: 2026-11-18
Task ID: HF-20261118-BRIEF-CHECKS-CAPS

## Objective
- Owner approved two frontier items on 2026-11-18: `yt-checks-over-plans-goal` (every brief carries a deterministic checks command with an end state, so done is test-proven) and `lanes-token-caps-in-brief` (per-task input/output token caps, turn cap and stop condition, with measurable savings).
- Delivered: `checks:` and `caps:` blocks in the slice-brief template (`.agent/skills/slice-authoring/SKILL.md` section 9), parser/validator/measurement in `scripts/ai/lib/brief_caps.py`, local-lane enforcement of the output cap, measurement log `brief-caps.jsonl`, and scoreboard counts.
- Baseline (2026-11-18): aq-land review rounds per branch mean 1.83, median 1 (n=63). Codex hit 1.5M tokens/24h for about 9 PRs on 2026-11-14/15. These are the numbers the change is measured against; no improvement is claimed yet.

- Portability (owner directive 2026-11-18, no hardwired limits; audit `.agents/delegation/outputs/hardwired-limits-audit-20261118.md`): the tier table (tokens and turns) now lives in `config/brief-caps-tiers.json` with `AQ_BRIEF_TIERS_FILE` as an override (built-in defaults if unreadable). Tier caps are clamped to the lane context (input to 50%, output to 25%) when it is known via `AQ_BRIEF_LANE_CTX` or `AQ_BRIEF_LANE_MODEL` (a `config/model-coordinator.json` model); unknown context means no clamp. `AQ_BRIEF_CHECKS_FAIL_FROM` (ISO date or `never`) overrides the 2026-12-02 FAIL date.

## Workflow/Session IDs
- Workflow ID: none (bounded implementer slice)
- Session ID: Simurg@claude/sonnet, dispatched by Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated bounded implementer (Claude sonnet override, Rule 17) by the orchestrator. Review is left to an independent lane; the implementer does not review, merge or open a PR.
- Canon: the brief contents are defined in the slice-authoring skill, not a `canon/` block, so no canon-compile run was made. If the orchestrator judges this a canonical contract change under Rule 16, a one-line pointer in `canon/blocks/headless-delegate-mode.md` plus `canon-compile --write` is the follow-up.

## Commands Executed
```bash
git -C /home/hyperd/Documents/NixOS-Dev-Quick-Deploy fetch origin
python3 scripts/testing/test-brief-caps.py
python3 scripts/testing/test-slice-authoring-lint.py
python3 scripts/ai/lib/brief_caps.py validate <brief-file>
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Enforced: (a) `brief_caps.py validate` returns FAIL for a bad tier or non-positive cap, and for a missing `checks.command` from 2026-12-02; (b) `delegate-to-local --prompt-file BRIEF` uses `caps.output_tokens` as `--max-tokens` when `--max-tokens` is not given (the existing max-tokens hook in dispatch).
- WARN only until 2026-12-02: missing `checks.command`, missing `checks.end_state`, missing `caps` block (tier defaults applied and recorded).
- Review fix (Codex REQUEST_CHANGES e3ba3bfb): validator failures now block delegation (`delegate-to-local` dies instead of `|| true`; invalid caps and missing checks after `AQ_BRIEF_CHECKS_FAIL_FROM` exit non-zero, WARN before); legacy `token_budget` <= 0 or non-integer is rejected like `input_tokens`; the brief path is resolved to absolute before export so measurement survives the isolated-worktree `cd`.
- Measured only (no clean enforcement hook): input tokens and turns for local; all caps for codex (its budget is a rolling daily total in `daily_budget_check`, not per task), gemini and claude. Prompt-char limits are not wired.
- Measurement: `dispatch.py` appends one record per brief-driven local run to `<delegation-dir>/brief-caps.jsonl` (schema `aq.brief-caps.v1`: caps, actual in/out/turns, within_caps, elapsed from `.timing.json`). Actual tokens come from the registry row, which already absorbs `.usage.json`. Unknown actuals are null, never zero. `aq-scoreboard` prints runs, no-checks-declared, over-cap and unknown counts. Turns are null for local runs today (the runner exposes no turn count); `brief_caps.py measure --turns N` records them for other lanes.
- Tests: `scripts/testing/test-brief-caps.py` 20/20 OK (adds tiers-file override, builtin fallback, lane-context clamp, coordinator-model lookup, fail-from env) (parser, legacy aliases, WARN before / FAIL after checkpoint, tiers 2k/500, 12k/4k, 24k/8k, measurement record, null-not-zero). Existing `test-slice-authoring-lint.py` 4/4 OK. Static gates and tier0 results are in the commit hand-off.

## Rollback Plan
- Config only: point `AQ_BRIEF_TIERS_FILE` at a file with the old values, or unset the lane/fail-from env vars to restore defaults.
- Revert the commit. `AQ_BRIEF_FILE` unset disables measurement; passing `--max-tokens` explicitly bypasses the derived cap. Trigger: delegate-to-local misbehaves on briefs with a `caps:` block, or the log grows without being read.

## Residual Risk
- Savings are unvalidated: the log must accumulate runs before the baseline (mean 1.83 review rounds, 1.5M codex tokens/24h) can be compared. Re-read `aq-scoreboard` after the 2026-12-02 checkpoint.
- Only the local lane is capped; codex, the larger spender, is measured only until a per-task hook exists.
- Brief validation runs only when a brief is passed with `--prompt-file`; briefs sent through other paths are unchecked until they adopt the CLI.
- delegate-to-local does not export `AQ_BRIEF_LANE_CTX` yet (no single runtime source of the served ctx); the static `llama-cpp-local.max_context_tokens` in model-coordinator.json (4096) is not auto-applied because it is stale against the real server. Set the env var per host to clamp.
- The parser is a small line parser for the documented format, not full YAML.

## Hint Feedback
- Hint IDs used: none (aq-hints not consulted for this bounded slice).
- Feedback: n/a.
