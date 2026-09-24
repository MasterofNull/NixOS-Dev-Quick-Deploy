# Independent Advisory Design Review: Local Producer Timing Observability

**Task ID**: `local-producer-timing-design-20260917`  
**Reviewer Lane**: Antigravity IDE (Independent Advisory Node)  
**Target Document**: `.agents/plans/coordination-safety-worktree-isolation/LOCAL-TIMING-ANTIGRAVITY-ADVISORY-20260917.md`  
**Subject Under Review**: `/tmp/aq-local-producer-timing-20260917/.agents/plans/coordination-safety-worktree-isolation/LOCAL-PRODUCER-TIMING-EXECUTION-20260917.md`  
**Parent PRD**: `.agent/PROJECT-LOCAL-LATENCY-OBSERVABILITY-PRD.md`  
**Expert Baseline**: Systems Engineer · Privacy Reviewer · Measurement / SDET  
**Operational Mode**: Read-only advisory review (no source modifications, no staging/commit, no branch switching, no service restart/deploy, no agent dispatches)

---

## 1. Context, Scope & Governance Boundaries

This review evaluates the execution packet for local producer timing instrumentation across the two native inference producers:
1. `DirectRunner` in [scripts/ai/lib/dispatch.py](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/dispatch.py#L506-L660) (streaming single-prompt direct inference).
2. `AgentRunner` / `AgentExecutor` in [ai-stack/local-agents/agent_executor.py](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/local-agents/agent_executor.py#L3931-L4180) (multi-step tool-augmented agent inference).

The owner has explicitly authorized a metadata-only timing slice in the frozen dispatcher, subject to independent review. This authorization is strictly limited:
- **Zero Content / Privacy Invariant**: No prompt text, response output, reasoning traces (`<think>`), or raw exception bodies may be captured or projected.
- **Model & Budget Invariants**: No model swapping, sampling hyperparameter adjustments, budget ceiling modifications, or timeout changes.
- **Minimal Dependency Invariant**: No new services, database registries, REST endpoints, external dependencies, or environment variables. All persistence reuses existing `.progress.json` sidecars and [TaskRegistry.monitor_payload](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/task_registry.py#L795-L831).

---

## 2. Five Concrete Technical Findings

### Finding 1 (Systems Engineering): Boundary Truthfulness — Strict Separation of Local Slot Admission Wait from Server-Side Queue & Prefill
* **Code Locations Verified**:
  - `scripts/ai/lib/dispatch.py:521-550` (`DirectRunner.run()` slot acquisition via `_slot_queue.acquire()` or `wait_for_slot()`).
  - `scripts/ai/lib/dispatch.py:584-594` (HTTP POST initialization to `config.llama_url/v1/chat/completions`).
  - `ai-stack/local-agents/agent_executor.py:3977-3991` (Prompt length prefill-wedge guard) and lines `4117-4127` (Streaming HTTP POST).
* **Assessment**:
  In `DirectRunner`, the duration from start until `_slot_queue.acquire()` succeeds represents **client-side slot admission wait** (the process waiting for a lock on the single local APU slot). Once `urllib.request.urlopen()` is invoked, the request transitions to the llama.cpp server. Llama.cpp does not expose internal thread-pool queue delays via standard headers; server queue time and initial prompt KV-prefill duration are unobserved from the client socket until bytes arrive.
* **Requirements**:
  1. The schema must explicitly label client slot delay as `local_admission_wait_seconds` (or `slot_acquisition_wait_seconds`). It must **never** be labeled `server_queue_seconds` or conflated with prompt prefill.
  2. For `AgentExecutor` (where slot locking is handled differently or multi-turn), the unobserved server queue must remain explicitly `null` with `decomposition: "server_queue_unobserved"`.
  3. Attempting to estimate server queue time without server-emitted telemetry violates measurement truthfulness and would corrupt downstream scheduling models.

---

### Finding 2 (Measurement / SDET): Turn Granularity vs Aggregate Masking — Per-Call Agent Lifecycle vs Whole-Task Elapsed
* **Code Locations Verified**:
  - `scripts/ai/lib/dispatch.py:848-910` (`AgentRunner.run()` wall-clock loop wrapping `aq-agent-loop`).
  - `ai-stack/local-agents/agent_executor.py:3931-3942, 4073-4087` (`AgentExecutor._call_llama` multi-step invocation with `call_number`).
  - `scripts/ai/lib/task_registry.py:470-501` (`_local_direct_latency_metadata` in TaskRegistry).
* **Assessment**:
  An agent task often involves multiple sequential LLM calls (`call_number = 0, 1, 2, ...`) interleaved with tool executions (e.g. bash commands, file searches, AST parsing). A whole task taking 300 seconds might consist of three 20-second LLM calls separated by 80-second tool executions.
* **Requirements**:
  1. **No Whole-Task TTFT**: The system must never calculate a single aggregate "TTFT" for a multi-call task, nor divide total tokens across the entire task duration to produce an aggregate token rate.
  2. **Per-Call Correlation**: Per-call timings must be strictly indexed by `task_id` and `call_number`.
  3. **Monitor Projection**: In [TaskRegistry.monitor_payload](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/task_registry.py#L795-L831), expose `latest_call_number`, `latest_call_request_start_utc`, `latest_call_first_visible_duration_seconds`, and `latest_call_completion_duration_seconds`, keeping `whole_task_elapsed_seconds` separate.

---

### Finding 3 (Measurement / SDET): First-Visible Definition & Degradation Modes (Replay, Buffered, Failed Streams)
* **Code Locations Verified**:
  - `scripts/ai/lib/dispatch.py:601-630` (DirectRunner SSE stream line parser).
  - `ai-stack/local-agents/agent_executor.py:4013-4015, 4054-4056` (Cassette replay mode bypassing HTTP).
  - `ai-stack/local-agents/agent_executor.py:4148-4164` (Delta parsing: role deltas, empty content, thinking tokens, usage-only chunks).
* **Assessment**:
  Calculating time-to-first-visible-content (TTFT) requires strict parsing discipline across multiple edge cases.
* **Requirements**:
  1. **First-Visible Content Definition**: llama.cpp emits initial metadata deltas (e.g. `{"role": "assistant"}`), empty chunks during KV prefill keepalive, and final usage chunks (`choices: []`). TTFT must be timestamped **only** upon the arrival of the first chunk where `delta.get("content")` is a non-empty string (`bool(content.strip())`). Non-visible tokens (role pings, empty chunks, keepalive whitespace) must be ignored.
  2. **Replay Cassette Mode**: When `AQ_LLM_CASSETTE_MODE` replays a response from disk, live network inference is bypassed. Reporting instantaneous live TTFT in replay mode would forge performance metrics. The timing sidecar must record `timing_mode: "replay"` and set live timing fields (`local_admission_wait_seconds`, `ttft_seconds`) to `null`.
  3. **Buffered / Non-Streaming Fallback**: When `LLAMA_USE_STREAMING=false`, the entire completion arrives in one batch. Time-to-first-token is unobservable and must be set to `null` with `ttft_status: "unavailable_buffered"`. It must not be backfilled with the total request duration.
  4. **Failed & Aborted Requests**: If a request fails prior to the first visible token (e.g. HTTP 500, connect error, or `LLAMA_FIRST_TOKEN_TIMEOUT`), `first_visible_duration_seconds` must remain `null`, while `terminal_error` records the failure class and `elapsed_seconds` records the time to failure.

---

### Finding 4 (Privacy & Security Review): Zero-Content Invariant & Bounded Categorical Failure Representations
* **Code Locations Verified**:
  - `.agent/PROJECT-LOCAL-LATENCY-OBSERVABILITY-PRD.md:20` ("Never include receipt content, prompts or arbitrary keys in the new projection.")
  - `/tmp/aq-local-producer-timing-20260917/.../LOCAL-PRODUCER-TIMING-EXECUTION-20260917.md:10-12, 59` ("metadata only... No prompt, response, exception body, arbitrary metadata or hidden reasoning leaks.")
  - `scripts/ai/lib/task_registry.py:481-501` (`_read_bounded_regular_file` bounded deserialization).
* **Assessment**:
  The timing sidecar and monitor projection exist solely for operational visibility. If exception handlers or progress dumps inadvertently capture prompt text, model output, or system error messages, sensitive code or keys could be exposed in unprivileged dashboard panels.
* **Requirements**:
  1. **Strict Type Schema**: Allow only numeric floats/integers, ISO-8601 UTC strings, and bounded enumeration strings in `.progress.json` / `.timing.json`.
  2. **Error Message Sanitization**: Never serialize raw exception strings (`str(e)`), HTTP error response bodies, or tracebacks into the timing sidecar. Map all failures to fixed categorical tokens: `slot_wait_timeout`, `http_4xx`, `http_5xx`, `connect_error`, `first_token_timeout`, `read_timeout`, `prefill_wedge_refusal`.
  3. **Projection Boundedness**: [TaskRegistry.monitor_payload](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/task_registry.py#L795) must enforce an explicit key allowlist. Any unexpected keys in the sidecar must be silently discarded.

---

### Finding 5 (Systems & Governance): Monotonic Clock Discipline, Suspend Semantics, and L2B Golden Fixture Re-binding
* **Code Locations Verified**:
  - `scripts/ai/lib/dispatch.py:522, 624, 634` (`time.monotonic()` delta calculations).
  - `scripts/testing/test-local-inference-l2b.py:151, 295` & [scripts/testing/fixtures/local-inference-l2b-payload-golden.json](file:///home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/fixtures/local-inference-l2b-payload-golden.json).
* **Assessment**:
  1. **Clock Semantics**: Event occurrence timestamps (`request_start_utc`, `completed_utc`) should use ISO-8601 UTC strings for log correlation. All duration deltas (`admission_wait_seconds`, `ttft_seconds`, `generation_seconds`) must be calculated using a single continuous `time.monotonic()` clock within the executing process. On Linux, `CLOCK_MONOTONIC` pauses during system suspend, cleanly excluding host sleep from active inference durations.
  2. **Manifest Gate Hygiene**: `scripts/testing/fixtures/local-inference-l2b-payload-golden.json` strictly pins the SHA-256 hash of `scripts/ai/lib/dispatch.py`. Modifying `DirectRunner` or `AgentRunner` will legitimately alter `dispatch.py`'s hash. The execution packet correctly requires that the golden fixture hash re-binding occurs *only after* verifying that payload vectors and stream behavior pass unchanged. Old and new source hashes must be recorded explicitly in the commit evidence.

---

## 3. Recommended Follow-Up Actions

During implementation in the isolated worktree (`/tmp/aq-local-producer-timing-20260917`):

1. **Implement `TimingHelper` (or inline record helper)**: Ensure timing writes use atomic replacement (`.tmp` to `.progress.json`) so concurrent monitor readers never encounter partially flushed JSON.
2. **Add Negative/Degraded Fixture Cases**: In `scripts/testing/test-local-delegation-artifact.py`, explicitly verify:
   - Replay mode produces `null` live timing fields with `timing_mode: "replay"`.
   - Buffered mode produces `null` TTFT with `ttft_status: "unavailable_buffered"`.
   - Error states map to categorical tokens without raw error bodies.
3. **Preserve L2B Golden Hash Integrity**: Re-bind the hash in `local-inference-l2b-payload-golden.json` cleanly, providing both the prior SHA-256 and the new SHA-256 in the slice handoff memo.

---

## 4. Advisory Disposition

**`ADVISORY DISPOSITION: PLAN_READY_WITH_FOLLOWUPS`**

The execution packet is well-scoped, rigorously bounded, and adheres strictly to owner authorization and repository governance. It addresses a critical blind spot in local model observability while maintaining complete isolation from model configurations, budget limits, and prompt contents.
