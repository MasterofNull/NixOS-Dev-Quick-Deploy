---
title: "Phase 103 — Cross-agent contradiction detection → attention archive"
status: Complete
phase: 103
priority: P2
---

## Objective
Surface memory contradictions and consensus divergence to the operator attention archive
(ATTENTION_ARCHIVE.jsonl) so silent failures become passively observable.

## Current gap
- `memory_broker.check_contradiction()` detects conflicts but only emits to event bus (dashboard)
- `ConsensusArbiter` escalates low-consensus to synthesis but never records divergence
- Operators learn about contradictions only via dashboard Tool Heatmap, not attention archive

## Scope (2 files, auto_ok boundary only)
1. `ai-stack/mcp-servers/hybrid-coordinator/memory_broker.py`
   - In `_emit_contradiction_event(blocked=True)`: push to attention archive (auto_ok, medium)
2. `ai-stack/mcp-servers/hybrid-coordinator/consensus_arbiter.py`
   - In `resolve()`, when `consensus_score < 0.5`: push to attention archive (auto_ok, medium)

## Non-scope
- No human_gate alerts (no alert fatigue until pattern established)
- No changes to heuristic logic or threshold values
- No new attention queue items requiring approval

## Validation
- `scripts/testing/test-cross-agent-contradiction-detection.py`
  - 4 tests: memory blocked push, memory unblocked no push, low consensus push, high consensus no push
- Register in `config/validation-check-registry.json`

## Requires
- nixos-rebuild switch (coordinator Python change)
- PYTHONPATH already includes `scripts/ai/lib` (Phase 101.1 ✓)
