# Phase 60 Local Agent Analysis Completion

Status: implementation validation in progress

## Problem

Broad local `aq-chat` analysis prompts can now fit the context window, but they still terminate too early when the local model spends the default 8 tool calls gathering evidence. The deeper root cause is that the runtime was treating total tool-call count as the primary control surface instead of leasing a small active tool set and pruning unused schemas. The forced tool-free finalization pass also capped synthesis output at 1024 tokens, which can cut off systems-analysis answers mid-thought.

## Fix

- Raise the local tool-call ceiling default from 8 to 16.
- Export `SWB_LOCAL_TOOL_CALL_LIMIT=16` from the NixOS switchboard service.
- Add `SWB_ACTIVE_TOOL_SCHEMA_LIMIT=7` so automatic intent bundles lease only a small current working set.
- Keep explicit tool requests and `tools=["*"]` as override paths for intentionally broad operations.
- Expose the active schema cap in `/health` working-set telemetry.
- Harden the local tool-calling profile card to gather bounded evidence and synthesize instead of chaining tools until the safety fuse trips.
- Make `aq-chat` default `--max-tools` match the service ceiling.
- Reserve up to 2048 tokens for forced tool-free finalization and explicitly require complete synthesis.
- Surface a CLI notice when the final answer was produced after local tool-budget exhaustion.

## Validation

- `python3 scripts/testing/test-aq-chat-local-tool-profile.py`
- `python3 scripts/testing/test-switchboard-local-tool-finalization.py`
- `python3 scripts/testing/test-switchboard-tool-working-set-gc.py`
- `scripts/governance/run-focused-ci-checks.sh`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

## Follow-Up

If local analysis still overuses tools after this change, the next slice should add a true mid-turn tool-lease broker: a narrow meta-tool that can request a different tool bundle, prune stale tool outputs, and continue without advertising the full registry.
