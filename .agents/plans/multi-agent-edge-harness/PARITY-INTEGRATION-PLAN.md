---
doc_type: plan
id: parity-integration-plan
title: Multi-Agent Edge Harness Parity Integration Plan
status: active
owner: AI Stack Maintainers
parent_prd: multi-agent-edge-harness-combined-prd
last_updated: "2026-05-31"
---

# Multi-Agent Edge Harness — Parity Integration Plan

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-31

## Purpose

This plan tracks the integration steps to achieve parity between the multi-agent edge
harness (MAEAH) runtime and the canonical kernel declaration. It is the execution
companion to `COMBINED-PRD.md`.

## Parity Targets

| Priority | Capability | Status |
|----------|------------|--------|
| P0 | Agent identity envelope (source + role + boundary) | In progress |
| P1 | Runtime bounded delegation envelopes for agent identity/delegation | Partial |
| P1 | MCP tool-boundary profile enforcement | Partial |
| P1 | Trace path view: prompt → route → memory → tools → response → review | Partial |
| P1 | Agent run event stream with replayable single-agent, swimlane, and race views | Planned |
| P1 | Controlled spec-format race: Markdown vs HTML vs enhanced visual HTML | Planned |
| P1 | Useful-token accounting tied to accepted outcome and reviewer/eval verdict | Planned |
| P2 | Cross-agent contradiction detection and escalation | Planned |
| P2 | Attention queue integration for all agent boundaries | Planned |

## Integration Slices

### Slice 1: Identity Envelope
- Wire `source`, `role`, and `autonomy_boundary` into every agent dispatch call.
- Validate at switchboard ingress; reject missing-identity requests.

### Slice 2: Delegation Envelopes
- Scope each delegation to a bounded context window (max 4k tokens for sub-agents).
- Registry enforces ceiling; orchestrator owns context allocation.

### Slice 3: Tool Boundary Enforcement
- MCP tool profiles define per-role allowed tool sets.
- Switchboard rejects tool calls outside role profile.

### Slice 4: Trace Path Logging
- Each agent turn emits a structured trace event to `hybrid-events.jsonl`.
- Dashboard Gantt panel consumes trace events.

### Slice 5: Agent Run Event Stream
- Normalize prompt/spec, system prompt metadata, memory recall, skill load, model call, tool call, token usage, artifact, validation, review, human-control, and final-outcome events.
- Persist events so a run can be replayed after refresh.

### Slice 6: Spec-Variant Race Harness
- Run the same task across Markdown, HTML, and enhanced visual HTML derived spec variants.
- Compare accepted result, review burden, useful-token ratio, latency, cost, and validation outcome.
- Markdown/YAML remains canonical; HTML/visual HTML artifacts are derived and source-hash checked.

### Slice 7: Swimlane/Race Dashboard
- Single-agent replay view: instructions, loaded context/skills, tools, tokens, artifacts, validation, review.
- Swimlane view: one lane per agent/session/spec variant.
- Race mode: compare agents/profiles/spec variants on the same prompt.

## References

- `docs/architecture/canonical-kernel-declaration.md`
- `docs/architecture/role-matrix.md`
- `.agents/plans/multi-agent-edge-harness/COMBINED-PRD.md`
- `docs/architecture/agent-behavior-parity-index.md`
