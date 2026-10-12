# PRD: Frontier Autopilot FE-2a Functional Eval Metric Baseline

## 1. Problem & Context
In `frontier-evidence-intake`, the candidate `FE-2` (GEPA build-time prompt compilation) aims to reflectively optimize the local-agent prompt against a defined performance metric. However, during the initial measurement on 2026-09-07 (recorded in `.agents/plans/frontier-evidence-intake/FE-2-GEPA-BASELINE-20260907.md`), `aq-prompt-eval` scored `aider_task_systems_code` at 100.0% (1/1 pass).

Investigation revealed that `aq-prompt-eval` evaluated `code_generation`-tagged prompts using a **meta-quality probe**:
```python
probe = f"Below is a task prompt for an AI coding assistant. Rate whether it is clear, specific, and complete (yes/no):\n\n{rendered}"
```
This produced:
1. **Zero functional signal**: No code is generated, applied, executed, or tested against assertions.
2. **Zero headroom**: A static 100% self-assessment provides no gradient or reflective guidance for GEPA or prompt engineers.

Per the measure-first intake loop, GEPA cannot be scheduled until a real, checkable functional eval metric is established.

## 2. Objective & Scope (FE-2a)
Build a functional evaluation engine and metric baseline for code generation prompts:
1. **Functional Evaluation Mode**: Extend `aq-prompt-eval` with `--functional` (and support in `aq-functional-eval` / `CANONICAL_TESTS`) to evaluate code generation prompts against executable functional tasks.
2. **Task Substrate**: Provide representative tasks (e.g., `clamp`, `slugify`, `evens`, `mean`, `dedupe`, plus systems-code constraints) with concrete inputs and automated assertions.
3. **Execution Sandbox**: Extract Python code from model responses (handling fenced code blocks, leading indentation, and docstrings), execute tests in an isolated context with timeout protection, and capture exact failure traces.
4. **Reproducible Metric with Headroom**: Compute genuine pass-rate in `[0.0, 1.0]`, latency metrics, and error classifications, establishing an actionable baseline with measured headroom.
5. **Dashboard Visibility & Service Coverage**:
   - Expose functional eval baseline in `/stats/capability-enforcement` and `/stats/prompt-eval`.
   - Render `· Functional eval baseline` row in `assets/dashboard.js`.
   - Register Phase 0 QA check `0.10.64` in `scripts/testing/harness_qa/phases/phase0.py` and `scripts/ai/_aq-qa-bash`.
6. **Plan Tracking**:
   - Update `.agents/plans/frontier-evidence-intake/tracker.json` marking FE-2a accepted / active.
   - Update `FE-2-GEPA-BASELINE-20260907.md` with the new functional metric baseline.

## 3. Architecture & Contracts
- **CLI**:
  - `scripts/ai/aq-prompt-eval --functional [--id aider_task_systems_code] [--dry-run] [--json]`
  - `scripts/ai/aq-functional-eval` (convenience entrypoint)
- **Data Model**:
  - `FunctionalTestCase`: description, variables, task_code, test_assertion, reference_solution.
  - `FunctionalEvalResult`: task_name, passed, error, output, latency_ms.
- **Two-Axis Safety**:
  - Mock/offline verification (`--dry-run` or test fixture) passes deterministically without requiring a live llama.cpp instance during Tier-0 / CI gates.
  - Live execution calls the local model with bounded timeouts and sandboxed test execution.

## 4. Acceptance Criteria
1. `scripts/testing/test-functional-prompt-eval.py` passes all unit and integration assertions.
2. `aq-prompt-eval --functional --dry-run` returns cleanly and outputs functional task results with headroom.
3. Dashboard API `/stats/capability-enforcement` includes `functional_eval` metrics.
4. Frontend `assets/dashboard.js` renders `· Functional eval baseline`.
5. QA check `0.10.64` passes in Phase 0.
6. All 56 Tier-0 gates pass before commit.
