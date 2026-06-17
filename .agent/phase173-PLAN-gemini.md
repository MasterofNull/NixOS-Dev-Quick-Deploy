# Phase 173 Implementation Plan — SLICE 173-B & 173-E

## Overview
This plan covers the implementation of the RAGAS gate, checkpoint tuning, and dashboard health coverage for Phase 173.

## SLICE 173-B — continuous_learning.py RAGAS gate + checkpoint tuning
**Target File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py`

### Tasks
1. **(a) Add RAGAS_MIN_SAMPLES=20 Constant & Mark PRELIMINARY**
   - **Location:** Around line 50 (with other constants).
   - **Change:** Add `RAGAS_MIN_SAMPLES = 20`.
   - **Logic:** In `generate_optimization_proposals` (approx. line 1300+), check the sample count.
   - **Code Snippet:**
     ```python
     if sample_count < RAGAS_MIN_SAMPLES:
         proposal.status = "PRELIMINARY"
         # Suppress submission if needed or mark clearly
     ```
2. **(b) Reduce checkpoint_interval**
   - **Location:** `__init__` at line 292.
   - **Change:** Change `self.checkpoint_interval = 100` to `self.checkpoint_interval = 50`.
3. **(c) Answer Open Question 1: is FinetuningExample output path active or dead code?**
   - **Answer:** **Active.** It is used in `_save_finetuning_examples` (approx. line 1180) to append examples to `self.dataset_path`. It is also the return type of `generate_finetuning_examples`.
4. **(d) Answer Open Question 3: is fine-tuning trigger threshold in config or hardcoded?**
   - **Answer:** **Hardcoded.** In `should_trigger_finetuning` (approx. line 1459), the threshold `1000` is hardcoded.

## SLICE 173-E — aq-qa + dashboard coverage
**Target Files:** 
- `scripts/testing/harness_qa/phases/phase0.py`
- `dashboard.html`
- `assets/dashboard.js`
- `dashboard/backend/api/routes/aistack.py`

### Tasks
1. **(a) Add GET /api/aistack/training/health route**
   - **Location:** `dashboard/backend/api/routes/aistack.py`
   - **Implementation:** Extend `get_training_dataset_health` or add a new route `/training/health`.
   - **Schema:** 
     ```json
     {
       "dataset_size": int,
       "ingest_rate_24h": float,
       "rejection_rate_24h": float,
       "ragas_sample_count": int,
       "ragas_status": str,
       "last_ingest_ts": str,
       "tool_result_samples": int
     }
     ```
2. **(b) Add aq-qa checks 0.13.1-0.13.4**
   - **Location:** `scripts/testing/harness_qa/phases/phase0.py`
   - **Checks:** 
     - 0.13.1: Training telemetry path writable.
     - 0.13.2: RAGAS score non-zero.
     - 0.13.3: Dataset line count > 0.
     - 0.13.4: Continuous learning loop active (via PID file or timestamp).
3. **(c) Add Training Pipeline card to dashboard**
   - **Location:** `dashboard.html` (UI structure) and `assets/dashboard.js` (data fetching/rendering).
   - **UI:** A new `.card` in the Operations panel.

## Integration Contract Proposal (173-A -- 173-E)
**Path:** `.agent/collaboration/integration-contracts/173-A--173-E.md`
**Status:** PROPOSED

```markdown
# Integration Contract: Training Pipeline Health API

## Endpoint: GET /api/aistack/training/health

### Response Schema
| Field | Type | Description |
|-------|------|-------------|
| dataset_size | integer | Total lines in fine-tuning dataset JSONL |
| ingest_rate_24h | float | Samples/hour processed in last 24h |
| rejection_rate_24h | float | % of telemetry rejected by quality filter |
| ragas_sample_count | integer | Number of samples currently in RAGAS buffer |
| ragas_status | string | [OK, PRELIMINARY, INSUFFICIENT] |
| last_ingest_ts | string (ISO) | Timestamp of last processed telemetry event |
| tool_result_samples | integer | Count of tool interaction patterns extracted |
```

## Validation Plan
1. **Unit Test:** `pytest tests/unit/test_continuous_learning.py` (if exists) or mock the telemetry batch.
2. **Integration Test:** Run `aq-qa --phase 0` and verify checks 0.13.x pass.
3. **Manual Check:** Refresh dashboard and confirm "Training Pipeline" card displays live data.
4. **Compile Check:** `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py`
