---
title: "Phase 173: Training Pipeline Review — Qwen3 Code Analyst (PROXY)"
expert_roles: ["Code Analyst", "Training Signal Implementation Engineer"]
agent: qwen3-35b
proxy_filled_by: claude-sonnet-4-6
proxy_reason: "Qwen3 dispatch failed with provider_request_error (llama.cpp connection refused). Orchestrator fills proxy per WORKFLOW-CANON §Step 3 Extension Key Rules. Code was read directly from repo."
phase: "Phase 2 — Independent PRD Draft (proxy)"
date: 2026-06-17
status: proxy
---

# Phase 173: Training Pipeline Review — Code Analyst PRD (Qwen3 Proxy)

*NOTE: Qwen3 agent failed during dispatch (provider_request_error — same root cause as Phase 172:
llama.cpp connection refused). Orchestrator reads the code directly and fills this slot as proxy.
All file:line references are from direct code reading, not model analysis.*

## Executive Summary

Direct code reading of `training_ingest.py` and `continuous_learning.py` reveals that the
quality scoring calibration is correct (agent_step_complete floor is already 0.40 as intended),
the rotation detection fix from Phase 108.1 is present and correct, and the `is_structured`
detection covers the main cases. The primary code-level gap is the missing `tool_result` event
type in the accepted event list — this is a one-line omission that blocks the highest-signal
training data entirely. A secondary gap is that `continuous_learning.py` processes the same
files as `training_ingest.py` with no coordination.

## Mission

Find and document every code-level bug, miscalibration, and stub in the training pipeline.
Provide file:line:what references for each finding.

## Scope

### In Scope
- `ai-stack/local-agents/training_ingest.py` — full read
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py` — rotation logic, event processing
- `scripts/data/seed-rag-knowledge.py` — collections and schema

### Out of Scope
- Architecture redesign (see Claude PRD for that)
- Hardware changes
- RAGAS evaluator internals

## Current State Architecture (Code-Level)

### training_ingest.py constants (verified from code)
```python
# Line 30-37
MIN_LATENCY_MS = 500.0          # events below 500ms are filtered
DEFAULT_MIN_QUALITY = 0.65      # default floor
MIN_RESPONSE_TOKENS = 20        # ~80 chars minimum
MAX_SAFE_LIMIT_MULTIPLIER = 1.5 # auto-approve proposals up to 1.5x

# Line 46-55 — _STRUCTURED_MARKERS tuple
_STRUCTURED_MARKERS = (
    "```", "def ", "class ", "import ", "return ", "function ",
    "## ", "### ", "1. ", "2. ", "- [", "* ", "| ",
    '"function"', '"arguments"',  # JSON tool-call blobs
    "COMPLETED:",                 # agent synthesis guard output
)
```

### _quality_score() logic (training_ingest.py lines 57-89)
```python
# Non-structured: coverage * 0.7 + length_bonus
# Structured:     0.50 + length_bonus + coverage * 0.30
# length_bonus = min(0.3, len(response) / 6000.0)
#
# agent_step_complete floor: 0.40  (line ~243-244)
# default floor: DEFAULT_MIN_QUALITY = 0.65
```

**Floor status confirmed**: `agent_step_complete` uses `floor = 0.40`. This is CORRECT per
the Phase 162 fix. No recalibration needed here.

### _is_useful_hybrid_event() accepted types (lines 111-120)
```python
etype not in ("inference_complete", "chat_completion", "hybrid_completion",
              "local_inference", "agent_step_complete")
```
**MISSING**: `tool_result` — this is a one-line omission.
**MISSING**: `system_prompt` — system prompt injection events not captured.
**MISSING**: `delegation_feedback` processed separately, not as positive training signal.

### Rotation detection in continuous_learning.py (lines 872-885) — CONFIRMED CORRECT
```python
try:
    file_size = os.path.getsize(telemetry_path)
    if last_pos > file_size:       # stale checkpoint > actual file size
        last_pos = 0
        self.last_positions[str(telemetry_path)] = 0
except OSError:
    last_pos = 0
```
Phase 108.1 fix is present. `getsize` check before seek. Rotation resets to 0. **No regression.**

### Checkpointing interval
```python
# Periodic checkpoint every self.checkpoint_interval events
if events_since_checkpoint % self.checkpoint_interval == 0:
    self.last_positions[str(telemetry_path)] = f.tell()
    self.checkpointer.save({...})
```
`self.checkpoint_interval` — not visible in the read section; likely set in `__init__`.
If this is a large number (e.g., 1000), long files may lose position on crash between checkpoints.

### Event processing in continuous_learning.py
Both pipelines read the same files (`hybrid-events.jsonl`, user spool). `continuous_learning.py`
processes events via `_extract_pattern_from_event()`. It is unknown from this read whether
`agent_step_complete` events are handled there — `_event_type()` at line 330 reads
`event.get("event") or event.get("event_type")`, suggesting it may handle both field names.

## Failure Modes Found (Code-Level)

### F1: tool_result missing from accepted event types
- **File**: `ai-stack/local-agents/training_ingest.py`, `_is_useful_hybrid_event()`, line ~113
- **Bug**: `tool_result` not in the accepted `etype` set
- **Impact**: Every tool execution result (the highest-signal agent feedback) is silently dropped
- **Fix**: Add `"tool_result"` to the accepted types tuple; add a `success == True` guard

### F2: is_structured misses short successful tool calls
- **File**: `training_ingest.py`, `_quality_score()`, line ~78
- **Bug**: `response.count("\n") > 5` gate misses single-line successful tool returns (e.g., `{"success": true, "result": "..."}`)
- **Impact**: Short successful tool results score `coverage * 0.7` (prose path) instead of structured path → score ~0.1, rejected
- **Fix**: Add `response.startswith("{") and "success" in response` to `is_structured` conditions

### F3: No checkpoint_interval value visible in init path examined
- **File**: `continuous_learning.py`, `__init__`, line ~290s
- **Risk**: If checkpoint_interval is large (e.g., 1000 events), a crash mid-file loses up to 1000 events of position progress
- **Verification needed**: grep `checkpoint_interval` in __init__ to confirm default value

### F4: dataset.jsonl synchronous open in main ingest loop
- **File**: `training_ingest.py`, `_ingest_hybrid_events()`, line ~216
- **Code**: `with open(self.dataset_path, "a", encoding="utf-8") as fh:`
- **Context**: Called from `run()` which is called from `_cli()` — standalone script, not async
- **Risk**: If training_ingest.py is ever called from an async context (e.g., coordinator handler),
  this synchronous open blocks the event loop. Low risk today; high risk if wired into coordinator.

### F5: generate_prompt_extensions reads extensions file twice (minor)
- **File**: `training_ingest.py`, `generate_prompt_extensions()`, lines ~285 and ~310
- **Bug**: File is read once for `existing` dict and once for `_existing_routing_rules`. Two
  separate open/parse cycles on the same file. Minor efficiency issue, not a correctness bug.

### F6: _mark_proposal() rewrites entire optimization_proposals.jsonl on each approval
- **File**: `training_ingest.py`, `_mark_proposal()`, lines ~280-294
- **Bug**: Full file rewrite for every proposal status update. With many proposals, this is O(n)
  writes per approval. Not a bug today at low volume, but a time bomb at scale.

## Proposed Architecture (Code-Level Fixes)

### Fix F1 (critical — one line):
```python
# training_ingest.py, _is_useful_hybrid_event(), add to accepted types:
if etype not in ("inference_complete", "chat_completion", "hybrid_completion",
                 "local_inference", "agent_step_complete", "tool_result"):
```
Add guard: `if etype == "tool_result" and not event.get("success", True): return False`

### Fix F2 (one line, _STRUCTURED_MARKERS):
```python
_STRUCTURED_MARKERS = (
    ...existing...,
    '{"success"',   # short successful tool returns
    '{"result"',    # tool result JSON
)
```

### Fix F3 (verify first):
```bash
grep -n "checkpoint_interval" ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py
```
If > 100: reduce to 50 for finer position granularity.

## Security & Configuration
- No security implications from adding `tool_result` to accepted types — existing
  `scrub_telemetry_payload` already applied in continuous_learning.py
- training_ingest.py does NOT call `scrub_telemetry_payload` — **potential PII gap** if
  tool results contain user-provided content. Should add scrub call before quality scoring.

## Implementation Phases (High-Level)
- **Slice 173-A**: Fix F1 + F2 in training_ingest.py (one-line changes, no architecture impact)
- **Slice 173-B**: Add scrub_telemetry_payload call in training_ingest.py before quality gate
- **Slice 173-C**: Verify checkpoint_interval value; reduce if > 100

## Validation & Success Criteria
- `python3 training_ingest.py --dry-run --hours 24 --json | jq .positive_samples_added` increases
  after Fix F1+F2 vs current baseline
- `grep "tool_result" /var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl | wc -l` > 0 after fix
- No PII leak: `grep -i "password\|token\|secret" dataset.jsonl` returns 0

## Risks & Mitigations
- **Risk**: tool_result events contain raw tool output which may be large.
  **Mitigation**: `MIN_RESPONSE_TOKENS = 20` and `_token_count()` truncation guards already present.
- **Risk**: Adding `'{"success"'` to _STRUCTURED_MARKERS false-positives on error JSON.
  **Mitigation**: Use `'"success": true'` or `'"success":true'` as marker (more specific).

## Open Questions
1. What is the default value of `self.checkpoint_interval` in ContinuousLearningPipeline?
2. Does `_extract_pattern_from_event()` in continuous_learning.py accept `agent_step_complete`
   events? If yes, those events are being processed by both pipelines simultaneously.
3. Is `scrub_telemetry_payload` available as an import in training_ingest.py's current dependency path?

## Team Sign-off
- **Code Analyst**: APPROVED — F1 and F2 are one-line fixes with immediate measurable impact.
  F4 (sync I/O risk) and F6 (O(n) rewrite) are low-risk today but should be tracked.
- **Training Signal Implementation Engineer**: CONCERNS — PII gap (no scrub in training_ingest.py)
  must be fixed before expanding the accepted event types. Adding tool_result without scrubbing
  could leak user-provided content into the training dataset.

---
*PROXY — filled by Claude Sonnet 4.6 acting as Qwen3 Code Analyst proxy*
*Qwen3 dispatch failed: provider_request_error (llama.cpp connection refused — Phase 172 root cause still active during agent load window)*
*Per WORKFLOW-CANON §Step 3 Extension: "If an agent is unavailable, the orchestrator fills that agent's role and marks it as proxy sign-off. Never skip a sign-off slot silently."*
*Date: 2026-06-17*

## Addendum: Local Agent/Inference Failure Assessment (Code Analyst)

*Produced by Qwen3-35B via --mode direct (no agent loop, no stagnation guard). Direct mode confirmed working. Task completed in ~3 minutes.*

**1. Root Cause: Exploration Stagnation (confirmed)**
The failure stems from a rigid global counter (`_reads_without_edit`) at `agent_executor.py:852-854`.
- Soft nudge at `_MAX_READS_WITHOUT_EDIT = 8`
- Hard abort at `_READS_HARD_LIMIT = 12`
- PRD drafting read files 1-12 without writing → hard abort before synthesis began.
The counter penalizes legitimate research workflows. It assumes immediate execution, ignoring tasks requiring extensive context ingestion.

**2. Code Fix: Dynamic Read Limits via Task Typing**
Decouple read limits from global constants. Introduce `task_type` parameter in agent invocation:
- Modify `agent_executor.py` to accept `max_reads_without_edit` as optional override at init
- Default to 8 (implementation tasks); set to 25+ for `"research"` or `"analysis"` types
- Reset `_reads_without_edit` only on write/edit OR when task-specific limit reached
- `delegate-to-local --task-type research` → `aq-agent-loop --task-type research` → agent_executor receives override

**3. Research Mode Nudge Strategy**
At `_MAX_READS_WITHOUT_EDIT` threshold, if `task_type == "research"`, inject:
*"You are in research mode. Continue gathering necessary context before synthesizing your output. Begin writing by read 20."*
This reinforces confidence to continue reading rather than forcing premature writes.

**4. Gemini Sign-off: Output Contract Mismatch**
The 428-byte output (warnings only) on the addendum dispatch likely resulted from either:
(a) Per-minute rate limiting immediately after a prior Gemini call
(b) The task prompt size triggering a silent context limit in Gemini CLI
Gemini DOES produce content when given adequate time between dispatches — the sign-off log confirmed APPROVED with full reasoning. The issue is the dispatcher has no minimum-content check before marking a task completed.

**Fix:** Add `GEMINI_MIN_CONTENT_BYTES = 500` check in `delegate-to-gemini`. If output ≤ YOLO_HEADER_SIZE + 500 bytes, mark as `partial-success` and push to attention queue.

*Qwen3-35B direct mode analysis — 2026-06-17*
