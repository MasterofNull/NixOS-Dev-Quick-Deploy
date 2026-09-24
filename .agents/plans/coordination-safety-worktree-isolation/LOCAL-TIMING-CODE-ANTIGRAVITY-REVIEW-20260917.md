# Independent Advisory Code Review: Local Producer Timing Candidate

**Task ID**: `local-producer-timing-code-review-20260917`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Target Document**: `.agents/plans/coordination-safety-worktree-isolation/LOCAL-TIMING-CODE-ANTIGRAVITY-REVIEW-20260917.md`  
**Candidate Subject**: Commit [`80b04d95c0137a7f43510668e6c4cea8c960a8fa`](file:///tmp/aq-local-producer-timing-20260917) on branch `factory/local-producer-timing-20260917`  
**Parent Commit**: `f9ab7e429874eb32f91c04889aa7189daa213787`  
**Subject SHA-256**: `01ff6ff281f3877433f8ba0440959d14128aed54f18045a2f985015d63a26963` (verified exact binary patch match)  
**Expert Baseline**: Systems Measurement · Privacy · Runtime Reliability · SDET  
**Reviewed Paths (8)**:
1. `.agents/plans/coordination-safety-worktree-isolation/LOCAL-PRODUCER-TIMING-EXECUTION-20260917.md`
2. `scripts/ai/lib/dispatch.py`
3. `ai-stack/local-agents/agent_executor.py`
4. `scripts/ai/lib/task_registry.py`
5. `scripts/ai/lib/producer_timing.py`
6. `assets/dashboard.js`
7. `scripts/testing/fixtures/local-inference-l2b-payload-golden.json`
8. `scripts/testing/test-local-delegation-artifact.py`

---

## 1. Review Scope & Baseline Verification

This review evaluates the candidate implementation against owner authorization, canonical workflow rules, and the design recommendations established in the prior advisory pass.

### Hash & Subject Verification
* The candidate commit `80b04d95c0137a7f43510668e6c4cea8c960a8fa` produces the exact subject SHA-256 `01ff6ff281f3877433f8ba0440959d14128aed54f18045a2f985015d63a26963` against parent `f9ab7e429874eb32f91c04889aa7189daa213787`.
* Verified test execution in the isolated candidate worktree:
  - `scripts/testing/test-local-delegation-artifact.py`: **23/23 PASS** (13 pre-existing cancellation-lifecycle tests cleanly skipped).
  - `scripts/testing/test-local-inference-l2b.py`: **16/16 PASS**.
* Candidate commit metadata declares:
  - `Review-Disposition: ACTIVATION_BLOCKED`
  - `Safe-At-Rest: true`
  - `Activation-Authority: false`
  - `Next-Slice: independent exact-subject review, canonical Tier-0, and live metadata probe`

---

## 2. Five Concrete Technical Findings

### Finding 1 (Measurement Accuracy & SDET): Stream Tail Write Throttling Couples and Skews `first_visible_content` in `AgentExecutor`
* **Path & Lines**: `ai-stack/local-agents/agent_executor.py:4199-4208` and lines `4282-4295`
* **Analysis**:
  In `_call_llama`, `_write_stream_tail()` throttles disk writes to the live stream tail (`.agents/delegation/streams/<id>.txt`) at a minimum interval of 0.7 seconds:
  ```python
  def _write_stream_tail(final: bool = False) -> bool:
      now = time.time()
      if not final and now - _last_stream_write[0] < 0.7:
          return False
      ...
  ```
  On line 4282, the check for the first visible content chunk is gated on `wrote_tail`:
  ```python
  wrote_tail = _write_stream_tail()
  if first_visible_content is None and token.strip() and wrote_tail:
      first_visible_content = time.monotonic()
      ...
  ```
  If an initial token (such as a leading newline `\n` or whitespace emitted during prefill transition) arrives, `token.strip()` is empty, but `_write_stream_tail()` executes, sets `_last_stream_write[0] = now`, and returns `True`. If the first substantive non-empty word arrives 100ms later, `now - _last_stream_write[0] < 0.7` is true, so `_write_stream_tail()` returns `False`. Consequently, the `if ... and wrote_tail:` condition evaluates to `False`, and `first_visible_content` is **not recorded** on the first visible word. It is delayed until the next token that arrives after the 0.7s throttle window expires, artificially inflating TTFT by up to 700ms. Furthermore, if `_stream_dir` experiences an `OSError`, `wrote_tail` is permanently `False`, causing `first_visible_content` to be completely lost.
* **Recommendation**:
  Decouple the monotonic timestamp capture from the stream tail disk write. The arrival of the first non-empty token (`if first_visible_content is None and token.strip():`) should immediately stamp `first_visible_content = time.monotonic()` and `first_visible_content_utc = _timing_utc_now()`. If the stream tail must be flushed on first token, call `_write_stream_tail(final=True)` or pass a force flag, rather than conditioning the metric on the throttled return value.

---

### Finding 2 (Systems & Protocol Strictness): Strict `aq-[0-9]{1,20}` Task ID Regex Limits Telemetry to `aq-agent-loop`
* **Path & Lines**: `scripts/ai/lib/task_registry.py:875-885`
* **Analysis**:
  When projecting timing metadata for `local-agent`, `TaskRegistry._local_producer_timing_metadata` validates:
  ```python
  elif (
      ...
      or not isinstance(receipt.get("task_id"), str)
      or not _re.fullmatch(r"aq-[0-9]{1,20}", receipt["task_id"])
  ):
      return unavailable
  ```
  This matches tasks spawned via `scripts/ai/aq-agent-loop:430`, where `task_id = f"aq-{int(time.time())}"`. However, if `LocalAgentExecutor` is executed in sub-agent, collaborative, or test contexts where `task.id` is formatted differently (e.g. alphanumeric strings, UUIDs, or `task-*`), the receipt fails validation and is marked `unavailable`.
* **Recommendation**:
  For the current bounded slice, this strictness is safe and conforms to the `AgentRunner` -> `aq-agent-loop` boundary. However, in future slices that generalize producer timing to all agent invocation contexts, relax the regex to allow canonical task ID patterns (e.g. `r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"`), while preserving the dual-key distinction between executor `task_id` and delegation `output_task_id`.

---

### Finding 3 (Privacy & Security Verification): Strict Schema Key Matching and Sanitized Categorical Errors Guarantee Zero-Content Invariant
* **Path & Lines**: `scripts/ai/lib/producer_timing.py:65-98` and `scripts/ai/lib/task_registry.py:848-865`
* **Analysis**:
  The candidate adheres stringently to the zero-content privacy invariant:
  1. `producer_timing.py` accepts only scalar numbers, ISO-8601 UTC strings, booleans, and categorical strings.
  2. `_LOCAL_PRODUCER_TIMING_KEYS` in `task_registry.py` enforces exact set equality: `set(receipt) != _LOCAL_PRODUCER_TIMING_KEYS` immediately returns `unavailable`. Any extraneous key injected into the sidecar causes it to be discarded.
  3. Exception handlers in `dispatch.py` (lines 722-790) and `agent_executor.py` (lines 4030-4060, 4296-4350) sanitize all error states into fixed categorical strings (`slot_wait_timeout`, `http_4xx`, `http_5xx`, `read_timeout`, `connect_error`, `network_error`, `first_token_timeout`, `request_error`). No raw exception bodies, stack traces, prompt text, or generated reasoning are ever serialized into `.timing.json`.

---

### Finding 4 (Systems Architecture & Traceability): Dual-Key Identity and Invocation Sequence Disambiguate Retried Turns
* **Path & Lines**: `scripts/ai/lib/producer_timing.py:70-75`, `ai-stack/local-agents/agent_executor.py:4005-4015`, and `assets/dashboard.js:7998-8002`
* **Analysis**:
  In multi-turn local agent workflows, two common ambiguities occur:
  1. Internal agent epoch ID (`aq-...`) vs orchestrator delegation run ID (`local-20260917-...`).
  2. Logical turn number (`call_number`) repeating across grammar repair retries or tool re-invocations.
  The candidate cleanly resolves both:
  - `task_id` preserves the executor's internal task identity, while `output_task_id` binds to the delegation artifact basename.
  - `invocation_sequence` maintains a strictly monotonic attempt counter per executor instance, while `call_number` reflects the logical agent turn.
  - `assets/dashboard.js` surfaces both clearly: `${latestCall.producer} logical turn #${latestCall.call_number} · attempt #${latestCall.invocation_sequence} (executor-local)`.

---

### Finding 5 (Governance & Delivery Gate): Clean L2B Manifest Re-binding and Truthful Safe-At-Rest Disposition
* **Path & Lines**: `scripts/testing/fixtures/local-inference-l2b-payload-golden.json:9` and Commit Message
* **Analysis**:
  - `scripts/testing/fixtures/local-inference-l2b-payload-golden.json` was updated exclusively at line 9 to re-bind the SHA-256 hash of `scripts/ai/lib/dispatch.py` (`41bd3fcb...` -> `be687dbe...`). All payload vectors, test assertions, and builder settings were preserved intact.
  - `test-local-inference-l2b.py` verified 16/16 checks passing against the updated hash.
  - The commit message truthfully records `Review-Disposition: ACTIVATION_BLOCKED` and `Safe-At-Rest: true`. No premature claims of production activation or live UI exposure are made.

---

## 3. Recommended Follow-Up Actions

1. **Decouple `first_visible_content` from `_write_stream_tail()`** in `agent_executor.py`: Stamp the monotonic timestamp immediately upon observing the first non-empty content token, rather than conditioning it on the throttled return value of the stream tail writer.
2. **Conduct Live Read-Only Probe**: Execute a single read-only probe (`aq-hints "test"` or `aq-qa 0`) on an unchanged local model profile to confirm end-to-end receipt generation in the running environment prior to lifting `ACTIVATION_BLOCKED`.
3. **Submit to Independent Cold Reviewer**: Per repo governance, this advisory review provides non-binding guidance; formal promotion to `main` requires exact-subject acceptance from an independent flagship lane.

---

## 4. Advisory Disposition

**`ADVISORY DISPOSITION: PLAN_READY_WITH_FOLLOWUPS`**

The candidate implementation is clean, robust, and maintains strict adherence to the zero-content privacy invariant and minimal-code guidelines. Finding 1 represents a straightforward timing decoupling that can be refined in a follow-up polish slice or addressed prior to mainline integration.
