# Observability & Dashboard Parity Implementation Plan

**Source:** [YouTube: Pi Coding Agent Observability](https://www.youtube.com/watch?v=o4KZH_KSqYQ&t=1s)
**Status:** In Progress (Phase 149)

## 1. Goal
Achieve full parity with the "Pi-style" observability stack, focusing on deep agentic introspection, useful-token metrics, and side-by-side comparison (Race Mode).

## 2. Parity Gaps Identified
| Feature | Status | Gap Description |
| --- | --- | --- |
| **Thought Visualization** | PENDING | Dashboard lacks a dedicated "Thought/Reasoning" block rendering. Agents do not consistently emit `<think>` tags in structured telemetry. |
| **Swimlane Timeline** | PARTIAL | Backend exists (`/agent-runs/swimlane`), but frontend rendering in `dashboard.html` is minimal and lacks deep-dive interactivity. |
| **Race Mode side-by-side** | PARTIAL | Backend exists (`/agent-runs/race`), but frontend comparison needs multimodal support (rendering HTML/Visual specs). |
| **Useful Token Tracking** | PARTIAL | Logic in `aq-report` and `aistack.py` exists, but telemetry data in `agent-run-events.jsonl` often has `null` for these fields. |
| **Performance/Speed/Cost Triangle** | MISSING | No unified visualization for cost-per-intelligence or efficiency metrics. |
| **System Prompt Visibility** | PENDING | No easy way to view the *actual* system prompt (including injected skills) used for a specific run in the replay UI. |

## 3. Implementation Phases

### Phase 1: Telemetry Enrichment (Backend & Agents)
- **Goal:** Ensure `agent-run-events.jsonl` contains the rich data needed for the dashboard.
- [ ] Update `agent_run_events.py` to include a `thought` event type or a `thought` field in `model_call` payloads.
- [ ] Instrument `Switchboard` and `Hybrid Coordinator` to extract content between `<think>` tags from local model responses and emit them as telemetry events.
- [ ] Fix `useful_ratio` calculation in `Switchboard` so it is emitted with every `token_usage` event.

### Phase 2: Dashboard Frontend Elevation
- **Goal:** Transform `dashboard.html` into a rich control surface.
- [ ] **Thought Block:** Update `loadAgentReplay` in `assets/dashboard.js` to detect and render `thought` events with distinct styling (e.g., dimmed, italic, or in a "Thinking..." box).
- [ ] **Multimodal Replay:** Add support for rendering HTML artifacts directly in the replay view using `<iframe>`.
- [ ] **Useful Token Gauge:** Add a visual "Useful Ratio" gauge to the run summary.
- [ ] **System Prompt Viewer:** Add a "View System Context" button to expand the full prompt used for the run.

### Phase 3: Advanced Visualizations
- [ ] **Swimlane Interactivity:** Allow clicking a bar in the swimlane to immediately focus the Replay panel on that run.
- [ ] **Race Benchmarking:** Implement side-by-side comparison of two runs (e.g., Gemini vs. Local) with diff-style highlighting for their outputs.

## 4. Acceptance Criteria
1. `aq-qa 0.10.2` (New Check) verifies that a "reasoning" run produces a `thought` event in the telemetry stream.
2. Dashboard Replay panel shows a "Thoughts" section for runs using reasoning models (e.g., local Qwen3-35B).
3. Useful-token ratio is non-null for 100% of successful `model_call` events.
4. "Race Mode" allows comparing two variants of the same task with rendered visual outputs.
