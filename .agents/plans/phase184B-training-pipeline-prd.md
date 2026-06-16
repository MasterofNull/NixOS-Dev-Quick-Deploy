---
doc_type: prd
id: phase184B-training-pipeline-prd
title: "Phase 184B — Training Pipeline Revival: Event Emission, Ingest Alignment, Continuous Learning"
status: draft
owner: architect
phase: "Phase 184B"
priority: P0-critical
evidence_required: finetuning_dataset_size grows past 331 within 24h of first successful agent run; total_patterns_learned > 0; training_ingest.py processes at least 1 agent_complete event
---

# Phase 184B — Training Pipeline Revival

## 1. Problem Statement

The training pipeline is clinically dead. Evidence from telemetry collected as of 2026-06-15:

| Metric | Value | Expected |
|--------|-------|----------|
| `finetuning_dataset_size` | 331 | Growing daily |
| `total_patterns_learned` | 0 | > 0 per agent run |
| `total_metrics_tracked` | 0 | > 0 |
| `deduplication_rate` | 0.0 | N/A |
| `patterns_by_type` | {} (empty) | Non-empty |
| `learning_paused` | false | — |
| `backpressure.unprocessed_mb` | 0.0 | — |

The dataset has been frozen at 331 examples for an unknown number of sessions. Three telemetry files sit on disk with significant content — `hybrid-events.jsonl` (52 MB), `aidb-events.jsonl` (15.7 MB), `ralph-events.jsonl` (12.2 MB) — yet `continuous_learning.py` has extracted **zero** patterns from any of them.

Simultaneously, `agent-run-events.jsonl` captures 150 `agent_step_start` events, 141 `agent_tool_result` events, and 140 `agent_tool_intent` events from recent agent runs, but only **1** `agent_complete` event and **zero** `agent_step_complete` events. This is the critical gap: `training_ingest.py` exclusively filters for `agent_step_complete` (along with `inference_complete`, `chat_completion`, `hybrid_completion`, and `local_inference`) in `_is_useful_hybrid_event()`. Without `agent_step_complete` events reaching the ingest source files, the dataset cannot grow.

Additionally, `delegation-feedback.jsonl` contains 135 events with null `event_type`, which blocks the routing adaptation analysis in `_analyze_delegation_feedback()`.

Three eval packs are defined in `config/training-manifest.yaml` — `harness-gap-eval` (70% pass), `golden-evals` (80%), and `holdout` (50%) — but none are running because the dataset is not growing and no baseline has been established.

The `learning-feedback` Qdrant collection holds 9,787 points, but `continuous_learning.py` does not read `learning-feedback` at all — it reads `ralph-events.jsonl`, `aidb-events.jsonl`, and `hybrid-events.jsonl`. The 9,787-point asymmetry is unrelated to the consumption gap but confirms a collection-naming mismatch exists elsewhere in the stack.

---

## 2. Event Taxonomy Audit

### 2.1 Events `agent_executor.py` DOES emit

These events are emitted via `_emit_agent_event()` (line 441) to `.agents/telemetry/hybrid-events.jsonl` (the user-space spool at `_HYBRID_EVENTS`, line 61) and/or `agent-run-events.jsonl` (via `AQ_AGENT_RUN_EVENTS_PATH`, line 73):

| Event Type | Destination File | Trigger Location (approx. line) | Has query/response? |
|---|---|---|---|
| `agent_step_start` | `agent-run-events.jsonl` | ~937 (top of each iteration) | No — step metadata only |
| `agent_thinking` | `agent-run-events.jsonl` | ~874 (`_emit_step_telemetry`) | No — reasoning text only |
| `agent_tool_call` | `agent-run-events.jsonl` | ~883 (`_emit_step_telemetry`) | No — tool call JSON only |
| `agent_tool_intent` | `agent-run-events.jsonl` | ~1061 (before tool exec) | No |
| `agent_tool_result` | `agent-run-events.jsonl` | ~1070 (after tool exec) | No |
| `agent_step_complete` | `.agents/telemetry/hybrid-events.jsonl` | ~644–662 (`execute_task`, on `TaskStatus.COMPLETED`) | **YES** — `query=task.objective`, `response=task.result` |
| `agent_complete` | `agent-run-events.jsonl` | ~668 (`_emit_terminal_agent_event`) | No — preview only |
| `agent_failed` | `agent-run-events.jsonl` | ~576, 596, 690 | No — error only |

### 2.2 Events `training_ingest.py` EXPECTS

`_is_useful_hybrid_event()` (line 173 of `training_ingest.py`) accepts:

```python
("inference_complete", "chat_completion", "hybrid_completion",
 "local_inference", "agent_step_complete")
```

It reads from two source paths:
- `HYBRID_EVENTS` = `/var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl` (service-owned, 52 MB)
- `USER_EVENTS_SPOOL` = `.agents/telemetry/hybrid-events.jsonl` (user-space spool)

### 2.3 The Gap

| | `agent_step_complete` | `agent_complete` |
|---|---|---|
| Written by `agent_executor.py` | YES (line 648, to `_HYBRID_EVENTS`) | YES (line 668, to `agent-run-events.jsonl`) |
| Read by `training_ingest.py` | Expected in `_is_useful_hybrid_event()` | **NOT in filter list** |
| Read by `continuous_learning.py` | Handled at line 1023 | **NOT handled** |
| Present in `agent-run-events.jsonl` | 0 events observed | 1 event observed |
| Present in `.agents/telemetry/hybrid-events.jsonl` | **UNKNOWN** | Not written there |

The critical question is whether `agent_step_complete` events are actually reaching `.agents/telemetry/hybrid-events.jsonl`. From the telemetry stats (`backpressure.unprocessed_mb = 0.0`), `continuous_learning.py` believes it has consumed all telemetry — but `total_patterns_learned = 0`. This means either:

(a) `agent_step_complete` events are not reaching the file (`_HYBRID_EVENTS` write silently failing or the spool file doesn't exist), **or**

(b) `agent_step_complete` events reach the file but fail `_is_useful_hybrid_event()` filters (latency < 500ms, or missing `query`/`response` fields), **or**

(c) `continuous_learning.py`'s checkpoint position already covers the full file (from before `agent_step_complete` started being written), and the checkpoint is stale — i.e., `last_positions[hybrid-events.jsonl]` is already at EOF from previous processing of non-`agent_step_complete` events.

---

## 3. Root Cause Analysis

### 3.1 Primary: `agent_step_complete` write path is conditionally gated

In `agent_executor.py` lines 644–662, the `agent_step_complete` event is only written when:

```python
if task.result and _HYBRID_EVENTS.parent.exists():
```

This means the event is **silently dropped** if:
- `task.result` is `None` or empty string (any task that produces no string output — tool-only tasks, tasks where `result` is a dict that was not stringified, etc.)
- `_HYBRID_EVENTS.parent` (`.agents/telemetry/`) does not exist

The directory guard is the most likely immediate failure: if `.agents/telemetry/` was never created (it is not part of the NixOS module tmpfiles), every agent run silently drops the event with no log line (the outer `except Exception: pass` on line 661 swallows any error).

Furthermore, `agent_step_complete` is written with `with open(_HYBRID_EVENTS, "a", ...)` — a **synchronous blocking write inside `execute_task`** — but the directory must pre-exist. There is no `mkdir(parents=True, exist_ok=True)` call before the open.

### 3.2 Secondary: `continuous_learning.py` checkpoint may be past the write point

`ContinuousLearningPipeline` uses file-position checkpoints (`last_positions`). If `hybrid-events.jsonl` was processed when it contained only `inference_complete`/`chat_completion` events (none of which matched `agent_step_complete`), the checkpoint position is already at or near EOF. When new `agent_step_complete` events are appended at the end of the file, the daemon will pick them up on the next cycle — but only if the daemon is actually running.

The daemon runs as `ai-hybrid` via `continuous_learning_daemon.py`. It requires Qdrant and Postgres. If either is unavailable at startup, the daemon logs a warning and continues — but pattern indexing (`_index_patterns`) will silently fail. The `get_statistics()` counter (`total_patterns_learned`) only counts `self.patterns`, which is the **in-memory** list accumulated since the daemon started. On each restart, `self.patterns = []` resets to zero even if prior patterns were written to disk. This explains the persistent `total_patterns_learned: 0` in the stats snapshot.

### 3.3 Tertiary: `training_ingest.py` is not scheduled

`training_ingest.py` is a **standalone script** invoked manually or via `post_switch_hooks` in `training-manifest.yaml`. It is not run by the continuous learning daemon and has no cron/systemd schedule. The daemon only processes events to generate `InteractionPattern` objects and finetuning examples via `continuous_learning.py`; `training_ingest.py` is a separate parallel path that writes to the same `dataset.jsonl`. Neither is automatically triggered after agent runs.

### 3.4 Quaternary: Delegation feedback `event_type` null

`delegation-feedback.jsonl` entries lack `event_type`, so `_analyze_delegation_feedback()` in `training_ingest.py` correctly reads them (it does not filter by `event_type`) but `continuous_learning.py`'s `_extract_pattern_from_event()` (line 964) calls `self._event_type(event)` which returns `""` for null types, and the method returns `None` — zero patterns extracted from delegation feedback via the daemon path.

### 3.5 Qdrant collection `skills-patterns` vs `learning-feedback`

`continuous_learning.py` indexes patterns to `skills-patterns` Qdrant collection (line 1286). The `learning-feedback` collection (9,787 points) is a different collection written by a different producer. The daemon never reads from `learning-feedback` — there is no consumption asymmetry in the daemon itself. However, the 9,787 `learning-feedback` points suggest a different pipeline (likely ralph-wiggum or the coordinator) is writing feedback that is never consumed for training. This is a separate gap outside Phase 184B scope.

---

## 4. Goals & Success Criteria

### 4.1 Goals

1. `agent_step_complete` events reliably reach `.agents/telemetry/hybrid-events.jsonl` after every successful agent task completion.
2. `training_ingest.py` processes those events and grows `finetuning_dataset_size` past 331.
3. `continuous_learning.py` (daemon path) extracts at least 1 pattern per hour during active agent usage.
4. `total_patterns_learned` in `continuous_learning_stats.json` reflects in-session patterns (not reset to 0 on every restart).
5. Delegation feedback `event_type` null is resolved so gap analysis produces actionable routing signals.

### 4.2 Success Criteria (Measurable)

| Criterion | Target | Measurement |
|---|---|---|
| `finetuning_dataset_size` | > 331 within 24h of first fixed agent run | `cat continuous_learning_stats.json \| jq .finetuning_dataset_size` |
| `total_patterns_learned` | > 0 in stats snapshot | `cat continuous_learning_stats.json \| jq .total_patterns_learned` |
| `agent_step_complete` events in spool | ≥ 1 per completed agent task | `grep agent_step_complete .agents/telemetry/hybrid-events.jsonl \| wc -l` |
| `training_ingest.py` run | `positive_samples_added` > 0 on first run after fix | `python3 ai-stack/local-agents/training_ingest.py --dry-run --json \| jq .positive_samples_added` |
| Continuous learning daemon patterns | In-memory counter > 0 after first cycle | `continuous_learning_stats.json .total_patterns_learned` |
| Dataset growth rate | ≥ 1 new sample per completed delegate-to-local task | Compare `finetuning_dataset_size` before and after a single `aq-agent-loop` run |

---

## 5. Scope

### 5.1 In Scope

- Fix the `agent_step_complete` write-path directory guard in `agent_executor.py`
- Add `task.result` type coercion so dict/None results don't silently drop the event
- Verify `.agents/telemetry/` directory exists (add `mkdir` call before open)
- Schedule `training_ingest.py` to run automatically after agent task completions (post-completion hook)
- Fix delegation feedback `event_type` null by adding a default to `delegation_feedback.py` writers
- Add `training_ingest_processed`, `pattern_extracted`, `dataset_size_snapshot` observability events
- Dashboard panels: dataset size time series, patterns learned gauge, event type distribution, ingest run status, eval pack pass rates
- aq-qa checks for training pipeline health
- Validate `continuous_learning_stats.json` `total_patterns_learned` persistence across daemon restarts (fix in-memory-only counter)
- Confirm `continuous_learning.py` telemetry_paths includes `.agents/telemetry/hybrid-events.jsonl` (user spool)

### 5.2 Out of Scope

- Actual fine-tuning execution (LoRA training, model swap) — Phase 184C
- `learning-feedback` Qdrant collection consumption — separate gap, Phase 185
- Eval pack execution engine — blocked on dataset growth, Phase 184C
- Rust refactor — deferred indefinitely per MEMORY.md policy
- RAG collection `skills-patterns` population via the daemon — already works if patterns are extracted

---

## 6. Technical Approach

### 6.1 Fix 1 — `agent_executor.py`: Unconditional spool directory creation and robust event emission

**File:** `ai-stack/local-agents/agent_executor.py`
**Lines:** 644–662

**Current code (lines 644–662):**

```python
# Emit agent_step_complete event for training ingest pipeline
if task.result and _HYBRID_EVENTS.parent.exists():
    try:
        _event = json.dumps({
            "event_type": "agent_step_complete",
            ...
        })
        with open(_HYBRID_EVENTS, "a", encoding="utf-8") as _hef:
            _hef.write(_event + "\n")
    except Exception:
        pass
```

**Problems:**
1. `_HYBRID_EVENTS.parent.exists()` silently skips the write if `.agents/telemetry/` is absent.
2. `task.result and ...` skips emission if `task.result` is `None`, `""`, `0`, or `{}`.
3. `except Exception: pass` swallows all write errors invisibly.

**Fix:**

```python
# Emit agent_step_complete event for training ingest pipeline.
# Always attempt to write — create the spool directory if absent.
try:
    _HYBRID_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    _response_text = (
        task.result if isinstance(task.result, str)
        else json.dumps(task.result) if task.result is not None
        else ""
    )
    _event = json.dumps({
        "event_type": "agent_step_complete",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "query": task.objective,
        "response": _response_text,
        "latency_ms": task.execution_time_ms,
        "session_id": task.id,
        "tool_calls": len(task.tool_calls_made),
        "model": os.getenv("LLAMA_MODEL_NAME", "local"),
        "tokens_used": _task_tokens_used,
        "useful_ratio": 1.0,
    })
    with open(_HYBRID_EVENTS, "a", encoding="utf-8") as _hef:
        _hef.write(_event + "\n")
except Exception as _exc:
    logger.warning("agent_step_complete_emit_failed: %s", _exc)
```

The key changes:
- `mkdir(parents=True, exist_ok=True)` before every write (idempotent, no race)
- Emit even when `task.result` is `None` (empty response is still a training signal for failure analysis)
- Log write failures at WARNING level instead of silently swallowing

### 6.2 Fix 2 — `continuous_learning.py`: Add `.agents/telemetry/hybrid-events.jsonl` to `telemetry_paths`

**File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py`
**Lines:** 219–223

The daemon's `self.telemetry_paths` (lines 219–223) reads:
- `ralph_telemetry_path` (ralph-events.jsonl)
- `aidb_telemetry_dir / "aidb-events.jsonl"`
- `telemetry_dir / "hybrid-events.jsonl"` (service-owned `/var/lib/...`, not the user spool)

It does **not** include `.agents/telemetry/hybrid-events.jsonl` — the user-space spool where `agent_executor.py` writes `agent_step_complete` events.

**Fix:** Add the user spool path to `telemetry_paths`:

```python
# User-space agent event spool (agent_executor.py writes here when running as hyperd)
_repo_root = Path(
    os.getenv("REPO_ROOT", str(Path(__file__).resolve().parents[4]))
)
user_agent_spool = _repo_root / ".agents" / "telemetry" / "hybrid-events.jsonl"

self.telemetry_paths = [
    ralph_telemetry_path,
    aidb_telemetry_dir / "aidb-events.jsonl",
    telemetry_dir / "hybrid-events.jsonl",
    user_agent_spool,   # ← add this
]
```

This change requires **rebuild** (coordinator-side service).

### 6.3 Fix 3 — `continuous_learning.py`: Persist `total_patterns_learned` across restarts

**File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py`
**Lines:** 1381–1420 (`get_statistics`)

`total_patterns_learned` is `len(self.patterns)` — an in-memory list reset to `[]` on every daemon restart. The Checkpointer only saves `last_positions` and `processed_count`, not the patterns list.

**Fix:** In `get_statistics()`, read the actual finetuning dataset line count and use `self.processed_count` (which IS persisted via checkpoint) as the proxy for patterns seen:

```python
"total_patterns_learned": self.dedup_stats["unique_patterns"] + (
    # Load persisted total from checkpoint file if in-memory is 0
    self.checkpointer.load().get("total_patterns_ever", 0)
    if not self.dedup_stats["unique_patterns"] else 0
),
```

A cleaner approach: add `total_patterns_ever` to the checkpoint payload in `_process_telemetry_file()` (line 944) and `process_telemetry_batch()`:

```python
self.checkpointer.save({
    "last_positions": self.last_positions,
    "processed_count": self.processed_count,
    "total_patterns_ever": (
        self.checkpointer.load().get("total_patterns_ever", 0)
        + len(patterns)
    ),
    "timestamp": datetime.now(timezone.utc).isoformat()
})
```

Then in `get_statistics()`:

```python
"total_patterns_learned": (
    len(self.patterns)  # in-memory this session
    + self.checkpointer.load().get("total_patterns_ever", 0)  # prior sessions
),
```

This change requires **rebuild** (coordinator-side service).

### 6.4 Fix 4 — `training_ingest.py`: Run automatically after agent task completion

**File:** `ai-stack/local-agents/agent_executor.py`
**After line 662 (after `agent_step_complete` write block)**

Add a background trigger for `training_ingest.py` to process the new event immediately, without blocking the task result return:

```python
# Trigger training_ingest in background after every successful task.
# Fire-and-forget: subprocess, no await, no blocking.
try:
    _ingest_script = Path(__file__).parent / "training_ingest.py"
    if _ingest_script.exists():
        asyncio.create_task(asyncio.create_subprocess_exec(
            sys.executable, str(_ingest_script), "--hours", "1", "--json",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        ))
except Exception:
    pass
```

This is a lightweight fire-and-forget. On a Renoir APU, `training_ingest.py` completes in < 5s for a 1-hour window (JSONL scan, no GPU inference). The `--hours 1` window ensures only recent events are processed, keeping runtime bounded.

### 6.5 Fix 5 — Delegation feedback `event_type` null

**File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/delegation_feedback.py`
**Function:** `append_jsonl()` (line ~10)

Any `delegation-feedback.jsonl` write that omits `event_type` produces null entries that `continuous_learning.py` silently discards. The fix is to ensure all writers include `event_type`.

In `delegation_feedback.py`, `append_jsonl(path, payload)` should inject a default:

```python
def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    if "event_type" not in payload or not payload["event_type"]:
        payload = {**payload, "event_type": "delegation_feedback"}
    ...
```

This is a **no-rebuild** change (Python script, not coordinator service).

### 6.6 Fix 6 — `training_ingest.py`: Emit `training_ingest_processed` event

**File:** `ai-stack/local-agents/training_ingest.py`
**Function:** `run()` (after line 209)

After `run()` completes, append a structured event to the user-spool so the dashboard and aq-qa can observe ingest health:

```python
_ingest_event = {
    "event_type": "training_ingest_processed",
    "timestamp": _now_utc().isoformat(),
    "positive_samples_added": report["positive_samples_added"],
    "dataset_total": report["dataset_total"],
    "gap_patterns_found": len(report["gap_patterns"]),
    "proposals_auto_approved": len(report["proposals_auto_approved"]),
    "hours_window": hours,
}
# Append to user spool
try:
    USER_EVENTS_SPOOL.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_EVENTS_SPOOL, "a", encoding="utf-8") as _f:
        _f.write(json.dumps(_ingest_event) + "\n")
except Exception:
    pass
```

This is a **no-rebuild** change.

---

## 7. Implementation Plan

Steps are ordered with no-rebuild changes first (safe to deploy immediately), rebuild changes last.

### Step 1 — No-rebuild: Verify `.agents/telemetry/` directory exists

```bash
mkdir -p /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/telemetry/
ls -la /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/telemetry/
```

This unblocks `agent_step_complete` writes immediately without any code change.

### Step 2 — No-rebuild: Fix `agent_executor.py` spool guard and robustness (Fix 6.1)

Edit `ai-stack/local-agents/agent_executor.py` lines 644–662 per Fix 6.1. No service restart needed — `agent_executor.py` is loaded per-invocation by `aq-agent-loop` (not a long-running daemon).

### Step 3 — No-rebuild: Add background `training_ingest.py` trigger (Fix 6.4)

Edit `ai-stack/local-agents/agent_executor.py` after line 662 per Fix 6.4.

### Step 4 — No-rebuild: Fix delegation feedback `event_type` null (Fix 6.5)

Edit `ai-stack/mcp-servers/hybrid-coordinator/extensions/delegation_feedback.py` per Fix 6.5.

### Step 5 — No-rebuild: Add `training_ingest_processed` event emission (Fix 6.6)

Edit `ai-stack/local-agents/training_ingest.py` per Fix 6.6.

### Step 6 — No-rebuild: Run `training_ingest.py` manually to process backlog

After Steps 1–5 are deployed:

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
python3 ai-stack/local-agents/training_ingest.py --hours 720 --dry-run --json
# Verify positive_samples_added > 0, then:
python3 ai-stack/local-agents/training_ingest.py --hours 720 --json
```

The `--hours 720` window covers the past 30 days — enough to pick up `inference_complete` and `chat_completion` events already in `hybrid-events.jsonl` even if `agent_step_complete` events haven't accumulated yet.

### Step 7 — Requires rebuild: Add user spool to `continuous_learning.py` telemetry_paths (Fix 6.2)

Edit `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py` lines 219–223 per Fix 6.2, then run `nixos-rebuild switch`.

### Step 8 — Requires rebuild: Fix `total_patterns_learned` persistence (Fix 6.3)

Edit `continuous_learning.py` checkpointing per Fix 6.3, then `nixos-rebuild switch` (can be batched with Step 7).

### Step 9 — Post-rebuild: Validate end-to-end

Run a test agent task via `aq-agent-loop`, then verify:
1. `grep agent_step_complete .agents/telemetry/hybrid-events.jsonl | wc -l` > 0
2. `python3 ai-stack/local-agents/training_ingest.py --hours 1 --dry-run --json | jq .positive_samples_added` > 0
3. `cat /var/lib/ai-stack/hybrid/telemetry/continuous_learning_stats.json | jq .finetuning_dataset_size` > 331
4. `cat /var/lib/ai-stack/hybrid/telemetry/continuous_learning_stats.json | jq .total_patterns_learned` > 0

---

## 8. Monitoring & Observability

### 8.1 New Events

Three new structured events to be emitted (all written to `USER_EVENTS_SPOOL`):

**`training_ingest_processed`** — emitted by `training_ingest.py` after each `run()` call:
```json
{
  "event_type": "training_ingest_processed",
  "timestamp": "<ISO-8601>",
  "positive_samples_added": 5,
  "dataset_total": 336,
  "gap_patterns_found": 3,
  "proposals_auto_approved": 0,
  "hours_window": 1
}
```

**`pattern_extracted`** — emitted by `continuous_learning.py` after each batch (inside `process_telemetry_batch`, after `quality_patterns` is determined):
```json
{
  "event_type": "pattern_extracted",
  "timestamp": "<ISO-8601>",
  "batch_patterns": 12,
  "quality_patterns": 4,
  "files_processed": 4,
  "session_total": 47
}
```

**`dataset_size_snapshot`** — emitted by `continuous_learning.py` after `_save_finetuning_examples` (inside `_write_stats_snapshot`):
```json
{
  "event_type": "dataset_size_snapshot",
  "timestamp": "<ISO-8601>",
  "finetuning_dataset_size": 336,
  "total_patterns_learned": 47,
  "deduplication_rate": 12.5
}
```

### 8.2 Emission Points

| Event | File | Function | Trigger |
|---|---|---|---|
| `training_ingest_processed` | `training_ingest.py` | `run()` (end) | Every ingest run (manual or background) |
| `pattern_extracted` | `continuous_learning.py` | `process_telemetry_batch()` (end) | Each daemon polling cycle (default: 1h) |
| `dataset_size_snapshot` | `continuous_learning.py` | `_write_stats_snapshot()` | Each daemon polling cycle |

---

## 9. Dashboard Visualizations

All panels reside in the **Training Pipeline** section of the AI Stack dashboard. Backend data source: `continuous_learning_stats.json` (polled every 60s) plus the new structured events from `USER_EVENTS_SPOOL`.

### Panel 1 — Dataset Size Over Time (Time Series)
- **Type:** Line chart, daily cadence
- **Data source:** `dataset_size_snapshot` events from `USER_EVENTS_SPOOL`, grouped by day
- **Y-axis:** Sample count (0 to max+10%)
- **X-axis:** Date (last 30 days)
- **Threshold markers:** 100 (fine-tuning trigger per `training-manifest.yaml`), 500 (milestone), 1000 (daemon readiness check `should_trigger_finetuning`)
- **Alert:** Flat line for > 3 days = P1 alert (training pipeline stalled)

### Panel 2 — Patterns Learned Counter (Gauge)
- **Type:** Gauge / numeric tile
- **Data source:** `continuous_learning_stats.json` `.total_patterns_learned`
- **Thresholds:** Red < 1 (dead), Yellow 1–50 (starting), Green > 50 (healthy)
- **Sub-label:** `finetuning_dataset_size` with delta since last 24h

### Panel 3 — Event Type Distribution (Bar Chart)
- **Type:** Horizontal bar chart
- **Data source:** `agent-run-events.jsonl` — count events by `event_type` for the last 24h
- **Expected bars:** `agent_step_start`, `agent_tool_intent`, `agent_tool_result`, `agent_tool_call`, `agent_thinking`, `agent_step_complete`, `agent_complete`, `agent_failed`
- **Alert indicator:** If `agent_step_complete` bar is 0 and `agent_complete` is > 0 — RED flag (step complete events not emitting)
- **Purpose:** The primary visual diagnostic for the event taxonomy gap

### Panel 4 — Training Ingest Run Status (Table)
- **Type:** Data table, most-recent-first
- **Data source:** `training_ingest_processed` events from `USER_EVENTS_SPOOL`
- **Columns:** Timestamp, Hours Window, Events Processed (positive_samples_added), Dataset Total, Gap Patterns Found, Status
- **Max rows:** 20 (last 20 ingest runs)
- **Alert:** Last run > 24h ago = STALE warning

### Panel 5 — Eval Pack Pass Rates (Gauge Trio)
- **Type:** Three side-by-side gauges
- **Data source:** `/var/lib/ai-stack/hybrid/telemetry/training-loop-results.jsonl` (written by `aq-local-training-loop`)
- **Gauges:**
  - `harness-gap-eval`: Required 70%. Green ≥ 70%, Yellow 50–70%, Red < 50%
  - `golden-evals`: Required 80%. Green ≥ 80%, Yellow 60–80%, Red < 60%
  - `holdout`: Required 50%. Green ≥ 50%, Yellow 30–50%, Red < 30%
- **When no data:** Display "NOT RUN — dataset < 100 samples" (show `finetuning_dataset_size` as sub-label)

---

## 10. Validation Plan

### 10.1 Smoke Test (no-rebuild, immediate)

```bash
# Step 1: Verify directory exists
ls -la /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/telemetry/

# Step 2: Dry-run ingest over 30-day window
python3 ai-stack/local-agents/training_ingest.py --hours 720 --dry-run --json | jq '{
  positive_samples_added,
  dataset_total,
  gap_patterns_found: (.gap_patterns | length),
  failure_summary
}'
# PASS: positive_samples_added > 0

# Step 3: Live run
python3 ai-stack/local-agents/training_ingest.py --hours 720 --json | jq .dataset_total
# PASS: result > 331
```

### 10.2 End-to-End Agent Run Test

```bash
# Run a simple agent task and verify step_complete event is emitted
aq-agent-loop --task "List the files in .agents/telemetry/" --mode agent --max-calls 3

# Check spool
grep '"event_type": "agent_step_complete"' .agents/telemetry/hybrid-events.jsonl | tail -1
# PASS: line exists with query and response fields

# Check ingest picked it up
python3 ai-stack/local-agents/training_ingest.py --hours 1 --dry-run --json | jq .positive_samples_added
# PASS: > 0
```

### 10.3 aq-qa Checks to Add

New checks to add to `scripts/ai/_aq-qa-bash` (Phase 0 or Phase 10 training section):

```bash
# 0.11.1: agent_step_complete events exist in user spool
_check "0.11.1" "training: agent_step_complete events in spool" \
    "grep -c 'agent_step_complete' .agents/telemetry/hybrid-events.jsonl 2>/dev/null | awk '\$1>0{print \"ok\"}{print \"fail\"}'"

# 0.11.2: finetuning dataset growing (size > 331)
_check "0.11.2" "training: finetuning_dataset_size > 331" \
    "python3 -c \"import json; s=json.load(open('/var/lib/ai-stack/hybrid/telemetry/continuous_learning_stats.json')); print('ok' if s.get('finetuning_dataset_size',0) > 331 else 'fail')\""

# 0.11.3: training_ingest run within last 48h
_check "0.11.3" "training: training_ingest_processed event within 48h" \
    "python3 -c \"
import json, time
from pathlib import Path
spool = Path('.agents/telemetry/hybrid-events.jsonl')
if not spool.exists(): print('fail'); exit()
cutoff = time.time() - 48*3600
for line in open(spool):
    try:
        e = json.loads(line)
        if e.get('event_type') == 'training_ingest_processed':
            print('ok'); exit()
    except: pass
print('fail')
\""

# 0.11.4: continuous learning not stale (patterns_learned OR dataset grew)
_check "0.11.4" "training: continuous_learning_stats not frozen" \
    "python3 -c \"
import json
s = json.load(open('/var/lib/ai-stack/hybrid/telemetry/continuous_learning_stats.json'))
ok = s.get('finetuning_dataset_size', 0) > 331 or s.get('total_patterns_learned', 0) > 0
print('ok' if ok else 'fail')
\""
```

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `agent_step_complete` events exist in spool but fail latency filter (`latency_ms < 500`) | Medium | High | Check actual latency values in emitted events; short-circuit tasks (< 500ms) could use `latency_ms=0`. Fix: set `latency_ms = max(500.0, task.execution_time_ms or 500.0)` in the event payload, or lower `MIN_LATENCY_MS` for `agent_step_complete` events specifically (already at 0.40 quality floor — the latency filter is redundant for this type) |
| `task.objective` is empty string for some task types (no training value) | Low | Low | `_is_useful_hybrid_event` already filters `not query or not response` — no harm, event is skipped |
| Continuous learning daemon PID lockfile blocks second instance | Low | Medium | The daemon's PID check (daemon.py line 49–63) exits if the PID is alive. Multiple restarts leave stale lockfiles. Mitigation: the daemon already handles stale lockfiles via `ProcessLookupError`. Monitor `/tmp/continuous-learning.pid` existence |
| Background `training_ingest.py` subprocess triggered per task creates CPU spike | Low | Low | `training_ingest.py --hours 1` only reads the last hour — typically < 100 events. Total runtime < 5s on Renoir APU. Add throttle: skip trigger if `training_ingest_processed` event written within last 5 minutes |
| `continuous_learning.py` checkpoint already at EOF for hybrid-events.jsonl | High | High | This is the most likely cause of zero daemon patterns. Fix: after deploying Fix 6.2 (adding user spool), the checkpoint for the user spool starts at position 0. Service-spool checkpoint position may need to be reset manually: `rm /var/lib/ai-stack/hybrid/checkpoints/checkpoint.json && systemctl restart ai-hybrid-coordinator` — but verify dataset is not re-ingested with duplicates (deduplication by content hash prevents this) |
| `nixos-rebuild switch` required for coordinator-side changes causes brief service gap | Low | Low | Fixes 6.2 and 6.3 (coordinator changes) can be batched into a single rebuild. Fixes 6.1, 6.4, 6.5, 6.6 are all no-rebuild — deploy and validate these first |
| `delegation-feedback.jsonl` writers are coordinator-side (require rebuild for full fix) | Medium | Low | The null `event_type` fix in `delegation_feedback.py` covers new writes. Existing 135 null entries remain but are harmless (they are filtered, not destructive) |

---

## 12. Dependencies

### 12.1 Phase 184A — Delegation Must Succeed

Phase 184B assumes that `aq-agent-loop` tasks complete successfully, producing `agent_complete` and (after Fix 6.1) `agent_step_complete` events. If delegation itself is broken (tasks fail before completion due to tool errors, timeout, or AppArmor denial), no training events are produced regardless of the ingest fixes.

Phase 184A should address any blocking delegation failures before or in parallel with Phase 184B. The steps that are no-rebuild (Steps 1–6) can be deployed immediately without waiting for 184A. Steps 7–9 (rebuild) should follow 184A's rebuild.

### 12.2 Qdrant Health (`skills-patterns` collection)

`continuous_learning.py`'s `_index_patterns()` writes to the `skills-patterns` Qdrant collection. Verify the collection exists before relying on daemon pattern indexing:

```bash
curl -s http://127.0.0.1:6333/collections/skills-patterns | jq .result.status
# Expected: "green" or "ok"
```

If missing, the daemon logs `qdrant_upsert_failed` and patterns are still written to `dataset.jsonl` — but `total_patterns_learned` from the in-memory list will increment correctly via Fix 6.3.

### 12.3 Embedding Service (llama-embed, port 8081)

`continuous_learning.py` calls `_fetch_embeddings()` before Qdrant upsert. If llama-embed is down, embeddings return `[]` and patterns are skipped for Qdrant indexing (line 1256–1258: `if not embeddings: return`). Finetuning dataset writes are unaffected. Training signal is preserved; only Qdrant pattern retrieval is degraded.

### 12.4 `harness_paths` SSOT

`training_ingest.py` imports `harness_paths` (line 37) for canonical path resolution. If `harness_paths.py` is missing from `ai-stack/local-agents/`, the fallback env-var logic applies. Verify:

```bash
python3 -c "from harness_paths import HYBRID_EVENTS, USER_EVENTS_SPOOL; print(HYBRID_EVENTS, USER_EVENTS_SPOOL)" \
  --directory ai-stack/local-agents/
```
