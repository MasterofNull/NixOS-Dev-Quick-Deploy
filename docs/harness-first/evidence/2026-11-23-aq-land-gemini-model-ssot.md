# Gemini reviewer quota fallback in `aq-land`

## Root cause

`scripts/ai/aq-land` hardcoded `GEMINI_MODEL = "gemini-3.8-flash-high"` and `GEMINI_FALLBACK_MODEL = "gemini-3.8-flash-medium"`. Both models used the same quota pool, and the Gemini lane stopped after one retry. In `gemini-20261123-224556-skksqz` (`BINDING-REVIEW-FALLBACK-QUOTA`), the retry therefore stayed in the exhausted pool.

The hardcoded pair bypassed `tiers.google.gemini_lane` in `config/model-coordinator.json`, which specifies `gemini-4-neon-high` as `role_map.reviewer`, `gemini-4-hydrogen` as `fallback`, and `gemini-3.8-flash-medium` as `baseline_fallback`.

## Fix

`_gemini_model_chain()` reads and validates the configured model IDs. It uses Neon, Hydrogen, and Flash in that order if the config is unavailable or yields no valid candidates. `_run_lane()` tries up to three distinct models in order and retries only on a quota error. `AQ_LAND_GEMINI_MODEL` overrides the primary and `AQ_LAND_GEMINI_FALLBACK_MODELS` overrides the fallback list.

## Verification

- `python3 -m py_compile scripts/ai/aq-land scripts/testing/test-aq-land.py` passed.
- `TMPDIR=. python3 scripts/testing/test-aq-land.py` passed all 108 tests across eight shards. The tests verify third-pool success, fallthrough to `local-direct` after all three quota errors, both environment overrides, and retry notes in the PR body.

## Rule 15 activation attestation

The retry chain is integrated into the normal Gemini review path and takes effect whenever this version of `aq-land` runs. The landing tests exercised the end-to-end CLI path with stubbed reviewers. Each retry is observable in CLI output and PR notes, and operators can intervene through the two environment overrides. Live Gemini verification and PM tracker confirmation are deferred as of 2026-11-24 to the orchestrator at integration.

After landing, roll back with `git revert <landed-commit>`.
