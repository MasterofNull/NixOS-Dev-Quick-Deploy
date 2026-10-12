# PROJECT-FRONTIER-FE2B-GEPA-COMPILE-PRD.md

## 1. Executive Summary & Objective
Implement **Frontier FE-2b: GEPA build-time prompt compile** (DSPy / GEPA prompt compilation, ICLR 2026).
Building directly upon FE-2a's executable functional eval benchmark (`FUNCTIONAL_TASKS`), FE-2b provides an offline, build-time gradient-free reflective prompt optimizer engine (`gepa_optimizer.py`) and CLI (`aq-prompt-compile`).
The optimizer evaluates prompt mutations, extracts reflective feedback traces from assertion/execution failures, synthesizes targeted constraints, and adopts compiled prompts **only if** the compiled score strictly beats the measured baseline pass rate on `FUNCTIONAL_TASKS` while preserving zero runtime overhead and satisfying all Tier-0 gates.

## 2. Architecture & Components
1. **Compilation Engine (`scripts/ai/lib/gepa_optimizer.py`)**:
   - `GepaOptimizer`:
     - Loads base prompt from registry (`ai-stack/prompts/registry.yaml`).
     - Evaluates baseline against `FUNCTIONAL_TASKS` via `functional_eval.py`.
     - Reflects on failed task runs (error messages, assertion failure text).
     - Synthesizes concrete prompt directives targeting verified failure modes (empty inputs, order preservation, floating point types, systemd security directives).
     - Evaluates refined candidate prompt.
     - Strict gating rule: adoption refused unless candidate score > baseline score (`score_lift > 0.0`).
     - Compiles and persists artifact to `ai-stack/prompts/compiled/{prompt_id}.gepa.json`.
     - Read-only bounded `health_summary()` for dashboard and QA.
2. **CLI (`scripts/ai/aq-prompt-compile`)**:
   - Commands/flags: `--prompt ID`, `--dry-run`, `--verbose`, `--json`, `--adopt`, `--check-only`, `--verify`.
   - In dry-run mode: exercises deterministic baseline vs compiled lift with reflection traces.
   - Enforces fail-closed exit codes on compile refusal.
3. **Dashboard Integration**:
   - `dashboard/backend/api/routes/aistack.py`: expose `prompt_compile` in capability enforcement stats (`_prompt_compile_health_summary`).
   - `assets/dashboard.js`: add `· prompt compiler (GEPA)` row to capability gap card.
4. **QA Check (`0.10.65`)**:
   - Registered in `scripts/testing/harness_qa/phases/phase0.py` and `scripts/ai/_aq-qa-bash`.
   - Validates that `aq-prompt-compile --check-only` passes and health summary reports ready.
5. **Test Suite (`scripts/testing/test-gepa-prompt-compile.py`)**:
   - Tests baseline scoring, reflection synthesis, candidate refinement, strict gate enforcement (refusal on non-improving candidates), artifact serialization, and CLI execution semantics.
6. **Plan Tracker**:
   - Update `.agents/plans/frontier-evidence-intake/tracker.json` marking `fe-2-gepa` as 100% shipped.

## 3. Activation Gate & Definition of Done
1. **Integrated**: Pure engine in `scripts/ai/lib/gepa_optimizer.py`, CLI in `scripts/ai/aq-prompt-compile`.
2. **Turned ON**: Enabled offline/build-time and verified via CLI and QA check.
3. **Functionally Validated Real-World**: 6/6 test fixtures in `scripts/testing/test-gepa-prompt-compile.py` passing.
4. **Observable**: Exposed in dashboard route `/stats/capability-enforcement` and visible in `assets/dashboard.js`.
5. **Intervenable**: Operators can recompile, dry-run, verify, or force-check via `aq-prompt-compile`.
6. **PM-Tracked**: Tracked in `.agents/plans/frontier-evidence-intake/tracker.json` advancing FE-2 to 100%.
