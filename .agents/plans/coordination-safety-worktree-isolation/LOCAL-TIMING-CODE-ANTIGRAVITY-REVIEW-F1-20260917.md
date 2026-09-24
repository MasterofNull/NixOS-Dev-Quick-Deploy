# Independent Advisory Code Review: Local Producer Timing (Candidate F1 Corrective)

**Task ID**: `local-timing-code-review-f1-20260917`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Target Document**: `.agents/plans/coordination-safety-worktree-isolation/LOCAL-TIMING-CODE-ANTIGRAVITY-REVIEW-F1-20260917.md`  
**Candidate Worktree**: `/tmp/aq-local-producer-timing-20260917`  
**Candidate Tip**: `bba5866cf17a76620dd3955daca55ad49ef15022`  
**Diff Base**: `f9ab7e429874eb32f91c04889aa7189daa213787`  
**Combined Diff SHA-256**: `4a014fd134635a316ccefb9abe62cbcbb688bf7a7ae057376323c8110b665db2` (verified exact binary patch match)  
**Expert Baseline**: Systems Measurement · Privacy · Runtime Reliability · SDET  
**Operational Mode**: Read-only advisory review (no candidate edits, no staging/commit, no branch switching, no service restart/deploy, no agent dispatches)

---

## 1. Executive Summary & Verification Scope

This review evaluates the candidate corrective commit [`bba5866c`](file:///tmp/aq-local-producer-timing-20260917) on top of the initial candidate [`80b04d95`](file:///tmp/aq-local-producer-timing-20260917). The corrective specifically addresses **Finding 1** of Antigravity's prior advisory review: decoupling time-to-first-visible-content (TTFT) measurement from the rate-limited (0.7s) stream-tail file writer.

### Exact Patch & Test Verification
1. **Binary Diff Integrity**:
   - The combined diff between base `f9ab7e42` and candidate tip `bba5866c` produces the exact SHA-256 hash `4a014fd134635a316ccefb9abe62cbcbb688bf7a7ae057376323c8110b665db2`.
2. **Hermetic Test Results** (executed directly in `/tmp/aq-local-producer-timing-20260917`):
   - `scripts/testing/test-local-delegation-artifact.py`: **23/23 PASS** (13 pre-existing cancellation-lifecycle skips preserved).
   - `scripts/testing/test-local-inference-l2b.py`: **16/16 PASS**.

---

## 2. Technical Evaluation of F1 Corrective Changes

### A. Decoupled First-Visible Content Observation
* **Code Location**: `ai-stack/local-agents/agent_executor.py:4280-4296`
* **Analysis**:
  In the initial candidate `80b04d95`, the capture condition evaluated:
  `if first_visible_content is None and token.strip() and wrote_tail:`
  Because `_write_stream_tail()` throttles disk writes to once per 0.7s, any initial whitespace or rapid subsequent token stream caused `wrote_tail` to return `False`, delaying the TTFT timestamp until a later chunk or dropping it on `OSError`.
* **Verification in F1**:
  Commit `bba5866c` cleanly decouples the in-memory socket event from disk I/O:
  ```python
  wrote_tail = _write_stream_tail()
  if first_visible_content is None and token.strip():
      first_visible_content = time.monotonic()
      first_visible_content_utc = _timing_utc_now()
      _record_timing(
          ...
          first_visible_content=first_visible_content,
          first_visible_content_utc=first_visible_content_utc,
          first_visible_content_observation=(
              "stream_tail_write" if wrote_tail else "stream_observed"
          ),
      )
  ```
  - `first_visible_content` is stamped immediately upon arrival of the first non-empty content token (`token.strip()`), preserving accurate sub-millisecond socket observation.
  - The telemetry truthfully records whether the stream tail file was also flushed (`"stream_tail_write"`) or bypassed due to throttling (`"stream_observed"`).

### B. Projector & Schema Accommodation
* **Code Location**: `scripts/ai/lib/task_registry.py:635-645`
* **Verification**:
  `TaskRegistry._local_producer_timing_metadata` was updated to accept `"stream_observed"`:
  ```python
  if observation not in {"output_file_flush", "stream_tail_write", "stream_observed", "unavailable"}:
      return unavailable
  ```
  This preserves the fail-closed invariant: any unrecognized observation string continues to reject the receipt to `unavailable`.

### C. Source Contract Test Assertion
* **Code Location**: `scripts/testing/test-local-delegation-artifact.py:1480-1487`
* **Verification**:
  A regression guard was explicitly added to `test_agent_executor_timing_is_per_call_and_never_claims_replay_ttft`:
  ```python
  assert_true(
      "if first_visible_content is None and token.strip():" in source
      and "and wrote_tail:" not in source,
      "first-visible timing must not depend on throttled stream-tail writes",
  )
  ```
  This ensures future refactorings cannot re-introduce the coupling.

---

## 3. Review of Invariants Across the Full Slice

1. **Zero-Content & Privacy Invariant**:
   - `scripts/ai/lib/producer_timing.py` continues to serialize strictly scalar metadata (durations, UTC timestamps, sequence numbers, enum strings).
   - Zero prompt text, response content, reasoning scratchpads (`<think>`), or raw exception strings are stored or projected.
   - Atomic replacement via `os.replace` on PID-scoped tempfiles with fail-silent error handling (`except Exception: pass`) guarantees that telemetry generation cannot disrupt inference.

2. **Identity & Turn Disambiguation**:
   - Clean separation of `task_id` (`aq-NNN`) from `output_task_id` (`local-...`).
   - Monotonic `invocation_sequence` per executor instance distinguishes retries from logical `call_number`.

3. **Failure Modes & Replay Semantics**:
   - Replay mode strictly records `null` durations and TTFT (`terminal_state="replay"`).
   - Buffered mode strictly records `null` TTFT (`first_visible_content_observation="unavailable"`).
   - Direct runner measures client-side slot lock acquisition; server queue remains explicitly `None`.
   - Categorical error tokens (`slot_wait_timeout`, `http_4xx`, `http_5xx`, `read_timeout`, `connect_error`, etc.) are recorded without leaking exception bodies.

4. **L2B Golden Manifest Integrity**:
   - Only the SHA-256 hash of `scripts/ai/lib/dispatch.py` is re-bound in `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`.
   - All 16 L2B payload vectors and model settings pass unmodified.

---

## 4. Conclusion & Advisory Disposition

The F1 corrective commit `bba5866c` resolves the timing distortion identified in the initial review with minimal, targeted changes. The full candidate on branch `factory/local-producer-timing-20260917` (combined SHA-256 `4a014fd134635a316ccefb9abe62cbcbb688bf7a7ae057376323c8110b665db2`) is verified sound, mathematically consistent, privacy-preserving, and safe at rest.

**ADVISORY DISPOSITION: PASS**  
(Non-binding advisory recommendation; final acceptance and promotion to `main` remain governed by independent cold review and canonical Tier-0 validation.)
