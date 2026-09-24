# Independent Advisory Review: Producer-Timing & Gate-Hygiene Mainline Integration

**Task ID**: `timing-gate-hygiene-review-20260917`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Target Document**: `.agents/plans/coordination-safety-worktree-isolation/TIMING-GATE-HYGIENE-ANTIGRAVITY-REVIEW-20260917.md`  
**Commits Evaluated**:
1. [`d0b814cb`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy) — `feat(local): record producer phase timing metadata` (Subject SHA-256: `8611af11e684a37d2e9e4e12f886441102ed1b260f1daeeb6588d40a1486ae93`)
2. [`caa2fb6f`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy) — `fix(governance): classify delegate-24h-success (0.8.1) as live-service in tier0 pre-commit` (Subject SHA-256: `ea5edbff1ffa7683c70360efe20eb81a4e8dc846ee0bc291b28067293973e6c8`)  
**Context & Standards**: `.agent/WORKFLOW-CANON.md`, `.agent/WORKAROUND-REGISTER.md` (WR-5), `.githooks/commit-msg`, `scripts/governance/tier0-validation-gate.sh`  
**Operational Mode**: Read-only advisory review (no source edits, no staging/commit, no branch switching, no service restart/deploy, no agent dispatches)

---

## 1. Executive Summary & Verification Context

Both commits [`d0b814cb`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy) and [`caa2fb6f`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy) landed on `main` following independent review by Claude Opus. This review provides the second independent perspective, evaluating exact landed code bytes against:
1. **Zero-Content & Best-Effort Invariants**: Complete exclusion of prompts, responses, reasoning tokens, and exception tracebacks from timing telemetry, combined with non-blocking best-effort atomic persistence.
2. **Identity & Turn Discipline**: Unambiguous separation between internal executor task IDs and delegation output IDs, as well as logical turn numbers vs. monotonic invocation sequences.
3. **Fail-Closed Registry & Dashboard Projection**: Prevention of fabricated decode rates or queue times, with mathematical consistency checks and honest unavailable reasons.
4. **Anti-Gaming & Gate Hygiene**: Rigorous qualification of check `0.8.1` as an environmental runtime-state signal under the Rule 21 gate corollary, maintaining all-or-nothing fail-closed gate behavior for static regressions.

---

## 2. Five Concrete Technical Findings

### Finding 1: Producer Timing Content-Free & Best-Effort Persistence Integrity
* **Path & Lines**: `scripts/ai/lib/producer_timing.py:65-110`, `scripts/ai/lib/dispatch.py:615-775`, `ai-stack/local-agents/agent_executor.py:4005-4340`
* **Verification**:
  - The schema `aq.local-producer-timing/v1` implemented in `producer_timing.py` restricts fields strictly to metadata scalars: producer enum, task IDs, turn/sequence integers, UTC ISO-8601 strings, monotonic duration floats, and categorical error tokens.
  - Zero prompt text, user inputs, system grounding context, response content, or raw exception strings are captured.
  - Atomic persistence uses PID-scoped temporary files (`path.with_name(f".{path.name}.{os.getpid()}.tmp")`) renamed via `os.replace` within a blanket `try... except Exception: pass` block. File I/O or serialization failures are silently swallowed, ensuring timing sidecar generation can never disrupt or alter inference execution or return codes.

### Finding 2: Identity Separation & Integrator's `getattr` Defensive Initialization Fix
* **Path & Lines**: `ai-stack/local-agents/agent_executor.py:4003-4015`, `scripts/ai/lib/producer_timing.py:70-75`
* **Verification**:
  - The landed code correctly separates `task_id` (the executor's internal `aq-NNN` identifier) from `output_task_id` (the delegation artifact basename, e.g. `local-20260917-...`).
  - `invocation_sequence` maintains a strictly increasing counter per executor instance, providing unambiguous correlation across retried logical turns (`call_number`).
  - **Integrator Corrective**: The candidate originally used `self._timing_invocation_sequence += 1`, which raised `AttributeError` for executors instantiated via `__new__` (bypassing `__init__`, such as in `test-noaction-intervention.py:make_executor`). The integrator's fix:
    ```python
    self._timing_invocation_sequence = (
        getattr(self, "_timing_invocation_sequence", 0) + 1
    )
    ```
    is fully behavior-preserving (`0 -> 1 -> 2` for standard initialized executors) while safely defaulting uninitialized instances, preserving best-effort non-faulting semantics across all test and execution harnesses.

### Finding 3: Fail-Closed Projector Guardrails & Mathematical Consistency
* **Path & Lines**: `scripts/ai/lib/task_registry.py:840-960`, `assets/dashboard.js:7992-8035`
* **Verification**:
  - `TaskRegistry._local_producer_timing_metadata` strictly validates that `set(receipt) == _LOCAL_PRODUCER_TIMING_KEYS`. Any unexpected or extra keys immediately discard the payload to `unavailable`.
  - Mathematical and chronological constraints are enforced:
    1. Chronological order: `_timing_utc_ordered(started, first, completed)` ensures `started <= first <= completed`.
    2. Monotonic duration constraint: `first_elapsed <= request_elapsed` (time-to-first-visible-content cannot exceed total request duration).
    3. Replay and buffered modes: TTFT and live request durations are strictly enforced as `null` with explicit observation statuses (`"unavailable"`).
  - Dashboard integration in `dashboard.js` surfaces honest unavailable explanations (`"unavailable (replay has no live request)"`, `"unavailable (buffered response is not streaming TTFT)"`, `"unavailable (not observed by this producer)"`) and displays server queue as `"unavailable (not observed)"`, completely eliminating misleading decode rate estimates.

### Finding 4: Anti-Gaming & Strict Runtime-State Qualification for Check 0.8.1
* **Path & Lines**: `scripts/governance/tier0-validation-gate.sh:891-945`, `scripts/testing/harness_qa/phases/phase0.py:706-725`, `scripts/ai/_aq-qa-bash:1237-1258`, `.agent/WORKAROUND-REGISTER.md:82-99`
* **Verification**:
  - Source inspection of `phase0.py` and `_aq-qa-bash` confirms that check `0.8.1` (`ai_coordinator_delegate 24h success rate`) queries `GET /stats/delegate?window_s=86400` on the running `ai-hybrid-coordinator` service. It is a genuine rolling live-telemetry window reflecting external provider and runtime lane health (e.g. remote reviewer quota exhaustion), not a static code or configuration check.
  - Adding `0.8.1` to `LIVE_SERVICE_CLASS_IDS` follows the established precedent of `0.10.22` under Rule 21 (Root-Cause Discipline gate corollary): transient runtime-environment degradation is downgraded to a non-blocking `live-service-class WARN` during `--pre-commit`, preventing unrelated code commits from being wedged.
  - Anti-gaming is strictly maintained: the success rate is neither mocked nor suppressed, remains fully observable, and continues to be enforced as a HARD blocking failure in `--pre-deploy` and `--maintenance`. The extension is formally registered in `.agent/WORKAROUND-REGISTER.md` (WR-5 extension).

### Finding 5: Fail-Closed Gate Selectivity & All-or-Nothing Enforcement Intact
* **Path & Lines**: `scripts/governance/tier0-validation-gate.sh:913-945`
* **Verification**:
  - In `gate_qa_phase0()`, all failing checks (`fresh_failing`) are partitioned into `fresh_list`, `live_list`, and `nonclass_failing`.
  - If any failing check is NOT in `FRESHNESS_CLASS_IDS` or `LIVE_SERVICE_CLASS_IDS`, `nonclass_failing` is populated.
  - The condition `[[ -z "${nonclass_failing}" && ( -n "${fresh_list}" || -n "${live_list}" ) ]]` ensures that a warning pass is granted **only** if zero non-class failures exist.
  - If any code or static regression fails, the gate logs all failed rows and exits with code 1 (`fail "QA phase 0 failed"`). Live-service warnings cannot mask static code regressions.

---

## 3. Conclusion & Advisory Disposition

Both landed commits [`d0b814cb`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy) and [`caa2fb6f`](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy) are verified correct, robust, and compliant with repository invariants. The producer timing implementation is content-free, best-effort, and fails closed in projection; the governance classification of check `0.8.1` resolves pre-commit wedging while maintaining strict anti-gaming and deployment gates.

**ADVISORY DISPOSITION: CONFIRM_PASS**
