# Independent Advisory Code Review: Local Producer Timing (Candidate F2 Compatibility Fix)

**Task ID**: `local-timing-code-review-f2-20260917`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Target Document**: `.agents/plans/coordination-safety-worktree-isolation/LOCAL-TIMING-CODE-ANTIGRAVITY-REVIEW-F2-20260917.md`  
**Candidate Worktree**: `/tmp/aq-local-producer-timing-20260917`  
**Candidate Tip**: `c4bf94b32a27d903b518b951c15e51b5e428a994`  
**Diff Base**: `f9ab7e429874eb32f91c04889aa7189daa213787`  
**Prior Advisory Tip**: `bba5866cf17a76620dd3955daca55ad49ef15022`  
**Combined Binary Diff SHA-256**: `aa292cf1849d525dcdc976ac02b4d7514b1a3f502d9720ac519150034f28deeb` (verified exact binary patch match)  
**Expert Baseline**: Systems Measurement · Privacy · Runtime Reliability · SDET  
**Operational Mode**: Read-only advisory review (no candidate edits, no staging/commit, no branch switching, no service restart/deploy, no agent dispatches)

---

## 1. Executive Summary & Verification Scope

This advisory review evaluates the candidate compatibility commit [`c4bf94b3`](file:///tmp/aq-local-producer-timing-20260917) on top of [`bba5866c`](file:///tmp/aq-local-producer-timing-20260917) and [`80b04d95`](file:///tmp/aq-local-producer-timing-20260917). Commit `c4bf94b3` introduces a targeted compatibility fix in `LocalAgentExecutor._call_llama()` to tolerate lightweight test fixtures that instantiate `LocalAgentExecutor` via `object.__new__()` without invoking `__init__()`.

### Exact Patch & Test Verification
1. **Binary Diff Integrity**:
   - The combined binary diff between base `f9ab7e429874eb32f91c04889aa7189daa213787` and candidate tip `c4bf94b32a27d903b518b951c15e51b5e428a994` (generated via `git diff --binary --full-index --no-ext-diff`) produces the exact SHA-256 hash `aa292cf1849d525dcdc976ac02b4d7514b1a3f502d9720ac519150034f28deeb`.
2. **Hermetic Test Results** (executed directly in isolated worktree `/tmp/aq-local-producer-timing-20260917`):
   - `scripts/testing/test-local-delegation-artifact.py`: **23/23 PASS** (13 pre-existing cancellation-lifecycle skips preserved).
   - `scripts/testing/test-local-inference-l2b.py`: **16/16 PASS**.
   - `scripts/testing/test-noaction-intervention.py`: **50/50 PASS** (directly exercising lightweight `__new__` test fixtures that isolate the local executor transport path).

---

## 2. Technical Evaluation of F2 Compatibility Change

### A. Defensive Attribute Access in `LocalAgentExecutor._call_llama`
* **Code Location**: `ai-stack/local-agents/agent_executor.py:4003-4008`
* **Diff**:
  ```diff
          progress_file = os.getenv("AGENT_PROGRESS_FILE")
          timing_output = _timing_output_path(progress_file)
  -       self._timing_invocation_sequence += 1
  +       # A few focused harness fixtures construct executors via ``__new__`` to
  +       # isolate the transport path.  Preserve compatibility with those
  +       # lightweight instances while keeping retry correlation monotonic for
  +       # fully initialized executors.
  +       self._timing_invocation_sequence = getattr(self, "_timing_invocation_sequence", 0) + 1
          timing_invocation_sequence = self._timing_invocation_sequence
  ```
* **Analysis & Verification**:
  1. **Standard Instantiation via `__init__()`**:
     - `__init__()` initializes `self._timing_invocation_sequence = 0`.
     - When `_call_llama()` executes, `getattr(self, "_timing_invocation_sequence", 0)` reads `0`, evaluates `0 + 1 = 1`, and assigns `self._timing_invocation_sequence = 1`.
     - On any subsequent retry or call within the same executor instance, `getattr()` retrieves the current integer, incrementing monotonically (`1 -> 2 -> ...`).
  2. **Lightweight Test Fixtures via `object.__new__(LocalAgentExecutor)`**:
     - Several focused test suites (such as `scripts/testing/test-noaction-intervention.py:make_executor`) construct minimal mock executors by invoking `object.__new__(LocalAgentExecutor)` to bypass heavy environment, model, and system dependency bootstrapping.
     - Because `__init__()` is skipped in these fixtures, an unconditional `self._timing_invocation_sequence += 1` previously raised `AttributeError: 'LocalAgentExecutor' object has no attribute '_timing_invocation_sequence'`.
     - With `getattr(self, "_timing_invocation_sequence", 0) + 1`, the uninitialized attribute gracefully defaults to `0`, setting `self._timing_invocation_sequence = 1` on the first call and incrementing monotonically thereafter.
  3. **Concurrency & Thread Safety**:
     - `_call_llama()` is executed synchronously per task runner loop within a single OS process/thread context. In-place attribute assignment is atomic at the bytecode level for integer addition and attribute set.
  4. **Side Effects & Invariants**:
     - The change has zero side effects outside `LocalAgentExecutor._call_llama()`.
     - `timing_invocation_sequence` continues to be passed to `_record_timing()` as an integer sequence number.

---

## 3. Review of Invariants Across the Full Slice

1. **Zero-Content & Privacy Invariant**:
   - `scripts/ai/lib/producer_timing.py` serializes strictly scalar timing metrics (durations, UTC timestamps, sequence numbers, observation enums, categorical error tokens).
   - Prompt text, model output tokens, system instructions, reasoning scratchpads (`<think>`), and raw exception strings remain 100% excluded.
   - Atomic replacement via `os.replace` on PID-scoped tempfiles with fail-silent error handling (`except Exception: pass`) guarantees telemetry generation cannot abort inference.

2. **Identity & Disambiguation Invariants**:
   - Clean dual-key separation between `task_id` (`aq-NNN`) and `output_task_id` (`local-...`) is preserved.
   - Physical invocation sequence (`timing_invocation_sequence`) remains distinguished from logical turn number (`call_number`).

3. **Decoupled TTFT & Observation Truthfulness**:
   - The F1 corrective decoupling (`first_visible_content = time.monotonic()` independent of `wrote_tail`) remains fully intact.
   - Telemetry accurately records whether the stream tail file was also flushed (`"stream_tail_write"`), observed directly from the socket without write (`"stream_observed"`), or unavailable (`"output_file_flush"`, `"unavailable"`).

4. **Failure Modes & Replay Semantics**:
   - Replay mode strictly records `null` durations and TTFT (`terminal_state="replay"`).
   - Buffered mode strictly records `null` TTFT (`first_visible_content_observation="unavailable"`).
   - Categorical error tokens (`slot_wait_timeout`, `http_4xx`, `http_5xx`, `read_timeout`, `connect_error`) are recorded without leaking internal exception bodies.

5. **L2B Golden Manifest Integrity**:
   - Only the SHA-256 hash of `scripts/ai/lib/dispatch.py` is updated in `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`.
   - All 16 L2B payload vectors and model settings pass unmodified.

---

## 4. Conclusion & Advisory Disposition

Commit `c4bf94b3` cleanly and correctly addresses test fixture compatibility for `LocalAgentExecutor` without introducing any privacy, identity, retry, or runtime regressions. The complete candidate on branch `factory/local-producer-timing-20260917` (combined binary diff SHA-256 `aa292cf1849d525dcdc976ac02b4d7514b1a3f502d9720ac519150034f28deeb`) is verified sound, resilient, and ready for integration.

**ADVISORY DISPOSITION: PASS**  
*(Non-binding advisory review; final acceptance and promotion to `main` remain governed by independent cold review and canonical Tier-0 validation.)*
