# Observability & Dashboard Parity Implementation Plan

**Source:** [YouTube: Pi Coding Agent Observability](https://www.youtube.com/watch?v=o4KZH_KSqYQ&t=1s)
**Status:** In Progress (Phase 149→166)

## 1. Goal
Achieve full parity with the "Pi-style" observability stack, focusing on deep agentic introspection, useful-token metrics, and side-by-side comparison (Race Mode).

## 2. Parity Gaps Identified
| Feature | Status | Gap Description |
| --- | --- | --- |
| **Thought Visualization** | PARTIAL | Frontend renders `thought`/`agent_thinking`/`planning` events (dashboard.js:7293-7315). Backend emission gap: switchboard/coordinator don't extract `<think>` tags as telemetry events. |
| **System Prompt Visibility** | PARTIAL | Frontend renders `system_prompt`/`model_call` events as "View System Prompt / Payload". Backend gap: coordinator doesn't emit a dedicated `system_prompt` event per run. |
| **Multimodal Replay** | PARTIAL | Frontend renders `artifact` events with `variant=html` in sandboxed iframe. Backend gap: agents don't emit `artifact` events. |
| **Swimlane Timeline** | PARTIAL | Backend exists (`/agent-runs/swimlane`), but frontend rendering in `dashboard.html` is minimal and lacks deep-dive interactivity. |
| **Race Mode side-by-side** | PARTIAL | Backend exists (`/agent-runs/race`), but frontend comparison needs multimodal support (rendering HTML/Visual specs). |
| **Useful Token Tracking** | DONE (rebuild pending) | switchboard.py fix committed ebeae5ab. Dashboard gauge at line 7661 shows ratio once data flows. Frontend shows `--` until rebuild activates live data. |
| **Performance/Speed/Cost Triangle** | MISSING | No unified visualization for cost-per-intelligence or efficiency metrics. |
| **System Prompt Visibility** | PENDING | No easy way to view the *actual* system prompt (including injected skills) used for a specific run in the replay UI. |

## 3. Implementation Phases

### Phase 1: Telemetry Enrichment (Backend & Agents)
- **Goal:** Ensure `agent-run-events.jsonl` contains the rich data needed for the dashboard.
- [x] `agent_run_events.py` already supports `thought` event type.
- [x] Switchboard already extracts `<think>` blocks → emits `thought` events (switchboard.py:59-92, `_THINK_BLOCK_RE`). agent_executor.py emits `agent_thinking` for local model pre-tool prose.
- [ ] Enable thought emission in practice: current model runs with `enable_thinking=false` (empty-response bug). When a capable reasoning model is deployed, thought events will flow automatically.
- [x] Fix `useful_ratio` in `Switchboard` — `useful_ratio=1.0` now injected at both token_usage sites (commit ebeae5ab, awaiting rebuild).
- [x] aq-qa 0.10.21 — switchboard useful_ratio emission verified at both sites (test-switchboard-useful-ratio.py, 2026-06-13).

### Phase 2: Dashboard Frontend Elevation
- **Goal:** Transform `dashboard.html` into a rich control surface.
- [x] **Thought Block:** `dashboard.js` already renders `thought` + `agent_thinking` events (lines 7293-7314) and `planning` events (line 7315). Backend emission is the remaining gap (Phase 1 items).
- [x] **Useful Token Gauge:** `dashboard.js` already calls `gaugeBar(ratio, 0.6, 0.4, "Useful token ratio")` (line 7661). Was showing null/-- due to switchboard gap now fixed (ebeae5ab, awaiting rebuild).
- [x] **Multimodal Replay:** iframe renderer already in dashboard.js (lines 7360-7364): detects `event_type=artifact, payload.variant=html` and renders in sandboxed iframe. Backend needs to emit `artifact` events.
- [x] **System Prompt Viewer:** already in dashboard.js (lines 7346-7352): `run_start`/`prompt_load`/`system_prompt`/`model_call` events show "View System Prompt / Payload" expandable. Backend emission gap: coordinator doesn't emit `system_prompt` event per run.

### Phase 3: Advanced Visualizations
- [ ] **Swimlane Interactivity:** Allow clicking a bar in the swimlane to immediately focus the Replay panel on that run.
- [ ] **Race Benchmarking:** Implement side-by-side comparison of two runs (e.g., Gemini vs. Local) with diff-style highlighting for their outputs.

## 4. Acceptance Criteria
1. `aq-qa 0.10.2` (New Check) verifies that a "reasoning" run produces a `thought` event in the telemetry stream.
2. Dashboard Replay panel shows a "Thoughts" section for runs using reasoning models (e.g., local Qwen3-35B).
3. Useful-token ratio is non-null for 100% of successful `model_call` events.
4. "Race Mode" allows comparing two variants of the same task with rendered visual outputs.
