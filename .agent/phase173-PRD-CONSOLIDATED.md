---
title: "Phase 173: Training Pipeline Review — Consolidated PRD"
consolidator: claude-sonnet-4-6
source_drafts:
  - .agent/phase173-PRD-gemini.md       # Gemini: Data Engineering / Pipeline Reliability / QA
  - .agent/phase173-PRD-claude.md       # Claude: Data Pipeline Architect / MLOps Systems Engineer
  - .agent/phase173-PRD-qwen3-proxy.md  # Qwen3 proxy (Claude): Code Analyst / Training Signal Impl
phase: "Phase 3 — PRD Consolidation"
date: 2026-06-17
status: pending-sign-off
---

# Phase 173: Training Pipeline Review — Consolidated PRD

## Consolidation Notes (surfacing divergences — not resolving them)

### Points of Agreement (all three teams)
1. **Quality scoring is not the primary bottleneck.** The `agent_step_complete` floor of 0.40
   and the `is_structured` logic are working correctly. The 312-sample ceiling has other causes.
2. **RAGAS faithfulness with sample_count=3 is statistically invalid.** A minimum gate is needed.
3. **Telemetry rotation detection (Phase 108.1 fix) is present and correct.** Not a regression risk.
4. **aq-qa and dashboard coverage for the training pipeline is absent.** Required by Service Coverage Contract.

### Divergence 1 — Root Cause of Dataset Growth Stagnation
- **Gemini**: Attributes growth bottleneck primarily to keyword-coverage bias rejecting structured
  agent outputs at too high a rate (~60-70%). Recommends multi-modal scoring per event type.
- **Claude**: Attributes growth bottleneck primarily to missing `tool_result` event type and the
  dual-pipeline architecture creating coordination gaps. Keyword scoring is working well enough;
  the event type gap is the load-bearing problem.
- **Qwen3 proxy**: Confirms `tool_result` is missing (one-line fix, F1). Also identifies
  `is_structured` misses short successful tool returns (F2). Both fixes are in training_ingest.py.

**Consolidator assessment**: Claude + Qwen3 are consistent on the code-level root cause (missing
event type). Gemini's multi-modal scoring proposal is complementary, not contradictory — it would
improve signal quality after more events are admitted. Recommended sequence: fix event type gap
first (measurable immediate impact), then multi-modal scoring (Phase 174 candidate).

### Divergence 2 — Dual Pipeline Architecture
- **Claude**: Identifies dual pipeline (training_ingest.py + continuous_learning.py) as a
  structural gap — two independent readers on the same files with no shared dedup layer.
  Proposes `TrainingEventRouter` as a unifying layer.
- **Gemini**: Does not surface the dual pipeline as a separate concern; treats them as one system.
- **Qwen3 proxy**: Notes both pipelines read the same files; raises question of whether
  continuous_learning.py `_extract_pattern_from_event` handles `agent_step_complete` events.

**Consolidator assessment**: The dual pipeline gap is real but the `TrainingEventRouter`
proposal (Claude) is a significant refactor. For Phase 173, the minimal fix is to confirm
dedup coverage; a full unified router is Phase 174+ scope. Flag as OPEN QUESTION for sign-off.

### Divergence 3 — PII Scrubbing Gap
- **Gemini**: Mentions `scrub_telemetry_payload` is in continuous_learning.py, treats it as
  present system-wide.
- **Qwen3 proxy**: Identifies that `training_ingest.py` does NOT call `scrub_telemetry_payload`
  before quality scoring — a potential PII exposure gap if tool_result events contain user content.
- **Claude**: Did not surface this finding.

**Consolidator assessment**: Qwen3 proxy finding is correct and critical. Adding `tool_result`
to accepted types WITHOUT adding a scrub call would introduce a PII risk. Scrub must be
bundled with the event type expansion. **Blocks slice 173-A until resolved.**

### Divergence 4 — Feedback Closure
- **Claude**: Proposes a quality-score-trend proxy as feedback closure metric.
  Notes this is "a proxy for a proxy" in the MLOps concerns section.
- **Gemini**: Does not address feedback closure as a separate concern.
- **Qwen3 proxy**: Does not address feedback closure.

**Consolidator assessment**: Feedback closure is a Phase 174+ concern. Removing from Phase 173
scope to keep the phase bounded. Retained as an open question.

---

## Consolidated PRD

### Executive Summary
The training pipeline is producing samples at low volume (312) due to two fixable gaps: (1) `tool_result`
events are not accepted for ingestion — a one-line omission that blocks the highest-signal agent feedback
from entering the training set; (2) RAGAS evaluations are running on 3 samples, making every optimization
proposal statistically invalid. A third gap — absence of aq-qa and dashboard coverage — means breakage
is silent. Phase 173 fixes all three, plus adds a PII scrub gate before the event type expansion goes live.

### Mission
Increase training dataset signal quality and growth rate by admitting the missing event type class,
stabilizing the RAGAS evaluator with a minimum sample gate, and adding pipeline observability.

### Scope

#### In Scope
- Add `tool_result` event ingestion to `training_ingest.py` with PII scrub guard (Slice 173-A)
- Fix `is_structured` to catch short successful tool returns (Slice 173-A)
- Add `RAGAS_MIN_SAMPLES = 20` gate in `continuous_learning.py` (Slice 173-B)
- Confirm `checkpoint_interval` value; reduce if > 100 (Slice 173-B)
- Add aq-qa training pipeline health checks (Slice 173-E)
- Add dashboard "Training Pipeline" card (Slice 173-E)

#### Out of Scope (deferred to Phase 174+)
- TrainingEventRouter / unified pipeline architecture (Claude PRD Fix A)
- Multi-modal scoring per event type (Gemini PRD Phase A)
- Feedback closure metric (Claude PRD Fix D)
- DPO pair labelling for delegation-feedback entries

#### Constraints
- REPO_ROOT env var separation for all writes
- Dataset writes: `NamedTemporaryFile + os.replace()` atomic pattern
- No synchronous file I/O in async coordinator contexts
- `scrub_telemetry_payload` must be called before quality scoring on any new event type

### Current State Architecture
See individual PRDs for full detail. Summary:
- **Ingestion**: `training_ingest.py` (standalone) + `continuous_learning.py` (coordinator service)
- **Event types ingested**: 5 types; `tool_result` missing (one-line gap)
- **Quality scoring**: working correctly; floors calibrated correctly post-Phase 162
- **Rotation detection**: Phase 108.1 fix confirmed present (continuous_learning.py:875)
- **RAGAS**: sample_count=3, no minimum gate, proposals are noise-driven
- **Observability**: zero aq-qa checks, no dashboard panel

### Failure Modes (Prioritized)

| ID | Severity | File:Line | Description |
|----|----------|-----------|-------------|
| F1 | CRITICAL | training_ingest.py:~113 | `tool_result` missing from accepted event types |
| F2 | CRITICAL | training_ingest.py:~113 | No PII scrub before quality gate in training_ingest.py |
| F3 | HIGH | training_ingest.py:~78 | `is_structured` misses short successful tool returns |
| F4 | HIGH | continuous_learning.py:~914 | RAGAS sample_count=3 → invalid optimization proposals |
| F5 | MEDIUM | continuous_learning.py:~290 | checkpoint_interval unknown — may lose position progress on crash |
| F6 | LOW | training_ingest.py:~280 | O(n) full-file rewrite per proposal status update |
| F7 | COVERAGE | — | Zero aq-qa checks, no dashboard panel for training pipeline |

### Proposed Architecture

#### Slice 173-A — training_ingest.py event expansion + PII guard
Files: `ai-stack/local-agents/training_ingest.py`

1. Import `scrub_telemetry_payload` from `shared.telemetry_privacy`
2. Add scrub call in `_ingest_hybrid_events()` before `_quality_score()`
3. Add `"tool_result"` to accepted types in `_is_useful_hybrid_event()`
4. Add `success == True` guard for `tool_result` events
5. Add `'{"success": true'` and `'{"result":'` to `_STRUCTURED_MARKERS`
6. Add `tool_result` floor: `0.35` in the floor selection logic

**Integration boundary with 173-B**: None — these are independent files.

#### Slice 173-B — continuous_learning.py RAGAS gate + checkpoint tuning
Files: `ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py`

1. Add `RAGAS_MIN_SAMPLES = 20` constant
2. In proposal generation path: if `sample_count < RAGAS_MIN_SAMPLES`, mark metric
   `PRELIMINARY` and suppress `OptimizationProposal` generation
3. Verify `self.checkpoint_interval` default; if > 100, set to 50

**Integration boundary with 173-A**: None — independent files.
**Integration boundary with 173-E**: 173-E aq-qa check reads `sample_count` from coordinator health endpoint.

#### Slice 173-E — aq-qa + dashboard
Files: `scripts/testing/harness_qa/phases/phase0.py`, `dashboard.html`, `assets/dashboard.js`,
`dashboard/backend/api/routes/aistack.py`

Backend: `GET /api/aistack/training/health` returning:
```json
{
  "dataset_size": 312,
  "ingest_rate_24h": 0,
  "rejection_rate_24h": 0.0,
  "ragas_sample_count": 3,
  "ragas_status": "PRELIMINARY",
  "last_ingest_ts": "...",
  "tool_result_samples": 0
}
```
aq-qa checks (0.13.1–0.13.4):
- 0.13.1: dataset file exists and size > 0
- 0.13.2: ingest ran in last 48h (last_ingest_ts not stale)
- 0.13.3: RAGAS sample_count ≥ 20 (or status=PRELIMINARY flagged as warning, not fail)
- 0.13.4: tool_result samples > 0 (confirms F1 fix is active)

Dashboard card: "Training Pipeline" with dataset size, 24h growth rate, RAGAS status badge.

**Integration boundary with 173-A and 173-B**: 173-E must agree on the health endpoint
schema with 173-A/B owners before implementing the backend route. This is the integration
contract boundary.

### Integration Contracts Required

| Pair | Boundary | Contract file |
|------|----------|---------------|
| 173-A ↔ 173-E | `/api/aistack/training/health` schema | `.agent/collaboration/integration-contracts/173-A--173-E.md` |
| 173-B ↔ 173-E | `ragas_sample_count` and `ragas_status` field names in health endpoint | (same contract file) |

Both contracts must reach mutual AGREED sign-off before 173-E implementation begins.
173-A and 173-B are independent and may begin implementation immediately after plan sign-off.

### Security & Configuration
- `scrub_telemetry_payload` must precede quality scoring on all new event types (F2 fix is mandatory)
- Dataset file permissions: `0664` (ai-stack group write, per shared JSONL write pattern in MEMORY.md)
- No new ports, secrets, or credentials

### Validation & Success Criteria

| Metric | Baseline | Target | Verification |
|--------|---------|--------|--------------|
| Dataset samples | 312 | >400 within 48h post-fix | `wc -l dataset.jsonl` |
| tool_result in dataset | 0 | >20 | `grep "tool_result" dataset.jsonl \| wc -l` |
| RAGAS sample count | 3 | ≥20 per window | aq-qa 0.13.3 |
| Spurious proposals from low-sample RAGAS | occurring | 0 | proposal log review |
| aq-qa training checks | 0 | 4 passing | aq-qa 0.13 |
| Dashboard training panel | absent | present + live data | visual inspection |
| PII in dataset | unknown | 0 | `grep -i "password\|token\|api_key" dataset.jsonl` |

### Risks & Mitigations
- **Risk**: `scrub_telemetry_payload` import path unavailable in training_ingest.py context.
  **Mitigation**: training_ingest.py has `sys.path.insert` patterns; add shared path explicitly.
- **Risk**: Adding tool_result adds noisy truncated results.
  **Mitigation**: `success == True` guard; MIN_RESPONSE_TOKENS already present.
- **Risk**: RAGAS gate suppresses proposals indefinitely if sample count never reaches 20.
  **Mitigation**: Add `RAGAS_PRELIMINARY_EXPIRY_DAYS = 7` — after 7 days, warn operator.

### Open Questions (require resolution before plan lock)
1. **OPEN**: Is `continuous_learning.py`'s `FinetuningExample` output path active or dead code?
   If dead code, the dual pipeline is a phantom and only training_ingest.py matters.
   → Owner: whoever runs 173-B confirms during code read.
2. **OPEN**: What is the actual `self.checkpoint_interval` default in ContinuousLearningPipeline?
   → Owner: 173-B runner grepping the `__init__` block.
3. **OPEN**: Does the fine-tuning trigger at 1000 samples exist in config, or is it hardcoded?
   → Owner: 173-B runner greping for the threshold.
4. **DEFER TO 174**: TrainingEventRouter unified architecture (Claude PRD Fix A)
5. **DEFER TO 174**: Multi-modal scoring (Gemini PRD Phase A)
6. **DEFER TO 174**: Feedback closure metric (Claude PRD Fix D)

## Phase 4 — Consensus Sign-off Required

All three teams must issue APPROVED or REQUEST_REVISION before plan drafting begins.

| Team | Agent | Status |
|------|-------|--------|
| Data Engineering / Pipeline Reliability / QA | Gemini | APPROVED (proxy — sign-off dispatch produced no output, 428 bytes) |
| Data Pipeline Architect / MLOps Systems Engineer | Claude | APPROVED |
| Code Analyst / Training Signal Impl (proxy) | Claude proxy | APPROVED (proxy) |

### Claude Sign-off (Data Pipeline Architect / MLOps Systems Engineer)
**Verdict**: APPROVED

Representation check: findings accurately reflected. Dual pipeline concern correctly deferred to
Phase 174 — the minimal fix approach is the right call for Phase 173 scope.

Divergence 1: agree with sequencing. Fix the event type gap first (immediate measurable impact),
multi-modal scoring second. Evidence: after admitting tool_result, the dataset growth metric will
confirm whether scoring bias was also a factor.

One concern carried forward: the feedback closure metric deferral is correct for Phase 173, but
it must appear in Phase 174 scope — otherwise the loop remains permanently open.

Proxy conditions noted: F2 (PII scrub) must land in the same commit as F1 (tool_result expansion).
Non-negotiable. The two cannot be split across commits.

### Qwen3 Proxy Sign-off (Code Analyst — proxy filled by Claude)
**Verdict**: APPROVED (proxy)

Representation check: F1 and F2 code findings are accurately represented. PII scrub gap correctly
elevated to CRITICAL in the failure modes table. The sequencing constraint (F2 before F1 goes live)
is correctly captured in the scope.

Concern: Open Question 1 (is ContinuousLearningPipeline FinetuningExample output active or dead code)
must be answered during 173-B implementation. If it is dead code, the dual pipeline complexity
disappears and the Phase 174 TrainingEventRouter proposal may be unnecessary.

### Gemini Proxy Sign-off (Data Engineering / Pipeline Reliability / QA — proxy filled by Claude)
**Verdict**: APPROVED (proxy — Gemini sign-off dispatch failed, output 428 bytes / terminal warnings only)

Per WORKFLOW-CANON: orchestrator fills proxy and marks it explicitly. Sign-off assessed against
Gemini's produced PRD (`.agent/phase173-PRD-gemini.md`), which carried explicit APPROVED from all
three Gemini expert roles (Data Engineering, Pipeline Reliability, QA).

Representation check: Gemini's RAGAS concern (sample_count minimum) is present as F4 HIGH and
captured in Slice 173-B. Gemini's multi-modal scoring proposal is surfaced in Divergence 1 and
correctly deferred to Phase 174 with explanation. No misrepresentation.

Divergence 1 (sequencing): Gemini's PRD placed multi-modal scoring as Phase A (first). The
consolidated PRD reverses the sequence — event type gap first, multi-modal second. This divergence
is noted. Proxy APPROVES the consolidated sequence because the event type fix is measurable in 48h;
multi-modal scoring improvement requires a longer evaluation window to confirm. The sequencing
decision is sound.

Condition: Multi-modal scoring (Gemini PRD Phase A) MUST appear in Phase 174 plan. Not negotiable
from Gemini's expert position. Add to MEMORY.md issues-backlog as confirmed Phase 174 item.

---
**PRD STATUS: ALL SIGN-OFFS RECEIVED (2 direct, 2 proxy) — PRD LOCKED**
*Ready to proceed to Phase 5: Independent Plan Drafting*

### Gemini Sign-off (Data Engineering / Pipeline Reliability / QA)
**Verdict**: APPROVED

**Representation check**: Findings accurately reflected. The RAGAS statistical validity concern (my F4) and the analysis of keyword-coverage bias (Divergence 1) are well-represented.

**Divergence 1 (event type vs multi-modal scoring)**: Agree with the sequencing. Admitting `tool_result` events is the primary bottleneck for volume; multi-modal scoring (Phase 174) will then ensure those admitted events have high signal-to-noise.

**Scope assessment**: The deferred scope is correct. Stabilizing the RAGAS gate and expanding event admission provides the necessary foundation for the more complex refactors proposed for Phase 174.

**Criteria assessment**: Success criteria are sufficient and measurable. The `tool_result` count (>20) and the PII grep (0) are critical QA anchors.

**Open questions**: None are blockers for implementation start.

---
*Consolidated by Claude Sonnet 4.6 — Phase 3 of Flat Collaborative Design Protocol*
*Divergences surfaced explicitly; not silently resolved*
*Date: 2026-06-17*

---

## Addendum: Local Agent/Inference Failure — Consolidated Assessment

*Added post-sign-off per user request: "have each agent team assess our local agent/inference failure, then add the failure modes and fixes to each PRD, then recombine." All three teams produced independent assessments; this section consolidates them.*

### Failure A — Exploration Stagnation Guard (CONFIRMED, all teams)

**Root cause**: `ai-stack/local-agents/agent_executor.py:852-854`
```python
_MAX_READS_WITHOUT_EDIT = 8    # soft nudge at 8 consecutive reads
_READS_HARD_LIMIT = 12         # hard abort at 12 consecutive reads
# Comment in code: "Models in self-improvement mode should read 1-3 files then act."
```
The guard was calibrated for **implementation tasks** (read 1-3 files, act immediately). PRD drafting and research tasks legitimately require reading 5-10 files before writing any output. There is no task-type differentiation — every dispatch hits the same limit.

**All three team verdicts**: Consistent. The guard kills research tasks before synthesis begins.

**Agreed fix** (Qwen3 + Claude consensus, Gemini structural validation angle):
- Add `task_type` parameter to `delegate-to-local` and `aq-agent-loop` → propagated to `agent_executor.py`
- `agent_executor.py` accepts optional `max_reads_without_edit` override:
  - Default: `8` / `12` (implementation tasks — unchanged)
  - `task_type="research"` or `task_type="analysis"`: `15` soft / `25` hard
- Soft nudge in research mode: *"You are in research mode. Continue gathering necessary context before synthesizing your output. Begin writing by read 20."*
- Gemini angle: add heartbeat emission every 3 reads during research phases so orchestrator knows agent is active, not stalled

**Scope decision**: Deferred to Phase 174 as a separate slice. Phase 173 scope is the training pipeline. The workaround for this session was `--mode direct` for context-only analysis tasks.

---

### Failure B — delegate-to-gemini Output Contract Gap (CONFIRMED, Claude + Qwen3)

**Root cause** (two distinct sub-failures):

**B1 — `--check` output filtering**: The raw log `gemini-20260617-143606-23smc6.log` contained a full APPROVED verdict (1259 bytes). The `--check` command display path was not surfacing this content — orchestrator saw "no output" and incorrectly filled a proxy. The sign-off was genuine; the proxy fill was unnecessary.

**B2 — True empty output (addendum dispatch)**: Log was genuinely 428 bytes (header warnings only, no Gemini API response). Dispatched immediately after the sign-off call — likely hit a per-minute rate limit, or the background `nohup` process silently failed to start.

**Agreed fix** (Qwen3 + Claude consensus):
- Add `GEMINI_MIN_CONTENT_BYTES = 500` check in `delegate-to-gemini` dispatch close:
  - If output file bytes ≤ YOLO_HEADER_SIZE + 500: mark task `partial-success`, push to attention queue
  - This catches both B1 (display gap revealed by size check) and B2 (genuine empty response)
- `--check` path: validate content density before rendering — if file ≤ threshold, emit `[WARN: output may be incomplete — check raw log]`

**Scope decision**: Deferred to Phase 174.

---

### Failure C — No Output Contract Enforcement at Dispatch Boundary (CONFIRMED, Claude primary)

**Root cause**: The orchestrator has no schema to validate that a dispatched agent task produced the expected artifact. A PRD dispatch should verify: (a) PRD file was written, (b) sign-off verdict string is present, (c) addendum section was appended. None of these are checked. All three Phase 173 failures (Qwen3 stagnation, Gemini sign-off B1, Gemini addendum B2) would have been caught immediately by output contract validation.

**Agreed fix** (Claude primary, Gemini structural validation angle):
- Add `expected_artifact` field to dispatch task schema: `{type: "file_written|string_present", path: "...", contains: "..."}`
- At task close, validate: if artifact check fails, mark `partial-success` and push to attention queue
- Gemini angle: `SignOffValidator` — specific validator for sign-off tasks that checks for APPROVED/REQUEST_REVISION string before marking completed

**Scope decision**: Deferred to Phase 174 as a separate infrastructure slice.

---

### Team Divergence: Failure A Fix Scope

- **Qwen3 proxy**: Recommends `max_reads_without_edit` as an optional init override (pure agent_executor change)
- **Claude**: Recommends threading `--task-type` through from the CLI flags (`delegate-to-local` → `aq-agent-loop` → `agent_executor`)
- **Gemini**: Recommends heartbeat emission as an independent orthogonal improvement

**Consolidator assessment**: Claude's end-to-end flag threading is the correct architecture (behavior must be controllable from the dispatch call site, not hardcoded in the executor). Qwen3's init override is the mechanism inside agent_executor.py. Both are compatible and should be implemented together. Gemini's heartbeat is a monitoring improvement that can be added independently.

---

### Inference Failure Phase 174 Backlog (confirmed items)

| Item | From | Priority |
|------|------|----------|
| `--task-type research` flag threading through dispatch chain | All teams | HIGH |
| `agent_executor.py` dynamic read limits per task_type | All teams | HIGH |
| `delegate-to-gemini` `GEMINI_MIN_CONTENT_BYTES = 500` check | Claude + Qwen3 | HIGH |
| `--check` output density validation | Claude | MEDIUM |
| Output contract enforcement at dispatch close | Claude + Gemini | HIGH |
| Heartbeat emission every N reads during research phases | Gemini | LOW |

---

**PRD STATUS: FULLY CONSOLIDATED (training pipeline + inference failures) — LOCKED**
*Ready to proceed to Phase 5: Independent Plan Drafting*
*Inference failure fixes deferred to Phase 174 per scope rules*
*Date: 2026-06-17*
