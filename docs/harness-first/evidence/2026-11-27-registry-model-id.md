# Registry model_id: record the model that served each delegation run

## Objective
aq-baseline day-0 (2026-11-27) reported `registry_model_known_share` = 0.025: 1033 of 1060 delegation registry rows carry no model id. Per-model routing (Rule 18) and experience-capture comparisons need the model that actually served each run. Registry rows now carry additive `model_id` (the served model, after any fallback), `model_source` (`cli_flag`, `cli_output`, `codex_config`, `fallback`, `llama_response`, or `unknown`) and, when it differs, `model_requested`. Unknown is `model_id: null` + `model_source: "unknown"`, never inferred. `model_effective` mirrors `model_id` when known so existing readers (aq-baseline, aq-review-receipt, dispatch evidence) keep working. aq-baseline's `registry_model_known_share` now also counts `model_id`.

## Workflow/Session IDs
Headless activation slice, 2026-11-27, Simurg@claude/sonnet-5.5, worktree branch worktree-agent-a53e94db3008695b8.

## Delegation Decision
Bounded activation slice across one shared writer and four wrappers with a checkable result (new tests). Implemented directly by the delegated sub-agent per the dispatch brief; no further sub-delegation. Independent review to follow via aq-land.

## Commands Executed
- `python3 scripts/testing/test-registry-model-id.py` (post-change and against a pre-change export of HEAD)
- `python3 scripts/testing/test-delegate-claude-model-routing.py`, `test-gemini-quota-fallback.py`, `test-delegate-sleep-inhibit.py`, `test-aq-baseline.py`, `test-delegate-codex-shared-writable.py`, `test-delegate-wrapper-shell-safety.py`
- `ruff check`, `basedpyright` on touched Python
- `python3 scripts/testing/check-cross-surface-contract.py`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`
- `bash scripts/testing/check-harness-first-pr-evidence-gate.sh`

## Validation Evidence
Per lane, the model comes from what the wrapper already holds:
- codex: `-m` flag, else the `model:` header codex prints in its output, else `~/.codex/config.toml` (`CODEX_HOME`); recorded at run end in both blocking and background paths (`registry-update.py model-codex`).
- gemini: `gemini-quota-fallback.sh` writes a `{model, source, requested}` report (`AQ_MODEL_REPORT`) that the wrapper/background worker folds into the row. A fallback success records `model_id: gemini-4-hydrogen`, `model_source: fallback`, `model_requested: gemini-4-argon`. A CLI-default success stays `null`/`unknown` because the CLI does not expose which id served it.
- claude: the tier-resolved `--model` id (`cli_flag`); no `--model-tier` stays `null`/`unknown`.
- local: the `model` field of llama.cpp's streamed/JSON response, carried in the usage sidecar and written by `dispatch_task`; absent means `null`/`unknown`.

Tests (`scripts/testing/test-registry-model-id.py`, 15 cases, registered as `registry-model-id-tests` in config/ci-checks.json): shared writer (known, unknown, requested-equals-served, existing keys preserved), codex wrapper stub runs (flag, output header, unknown), gemini wrapper stub runs (fallback served+requested, pinned, default-unknown, both exhausted), claude wrapper (tier and no tier), local `dispatch_task` against a stub SSE server (reported and unreported), and baseline eligibility.
Fails-without-the-fix: against a pre-change export of HEAD, all 15 new tests fail (8 failures, 7 errors); after the change all 15 pass. Full command output is in the slice report.

## Rollback Plan
Revert the commit. The fields are additive; rows already written keep extra keys that no reader requires, and old readers ignore them.

## Residual Risk
Historical rows (1033 without a model) are not backfilled; the share rises only as new runs land. Gemini runs on the CLI default and Claude runs without `--model-tier` remain unknown by design until the CLIs expose the served id. Codex's `model:` header parse depends on the CLI keeping that line format; a miss falls through to config.toml, then unknown. Codex `codex_config` records the configured model, which is the served one unless the CLI overrides it silently. Live ON/observable attestation needs a post-merge run (Rule 15): expect `registry_model_known_share` to rise in the next aq-baseline snapshot.

## Hint Feedback
No aq-hints used for this slice; none to report.

## L2B manifest pin generator

`scripts/ai/lib/dispatch.py` changed in this slice, so the `live_source_manifest` pin in
`scripts/testing/fixtures/local-inference-l2b-payload-golden.json` drifted. The pin is now
regenerated with `python3 scripts/testing/test-local-inference-l2b.py --write-golden`
(rewrites only the manifest hashes; checked by `scripts/testing/test-l2b-write-golden.py`).
Root cause: manifest pins were hand-edited on each source change; now generated.
