# Context Boundary Meter Handoff

## Slice

Implemented a repository-local post-tool/drop context boundary meter.

## Changes

- `scripts/ai/lib/context_boundary.py` stores only numeric estimates in
  `.agent/collaboration/CONTEXT-BOUNDARY.json` and creates a compact
  `HANDOFF-CONTEXT-<timestamp>.md` at 80%/90% thresholds of the 50,000-token
  native estimate.
- `scripts/ai/aq-context-manage boundary` lets tool and MCP wrappers record
  character counts, file sizes, or explicit token estimates.
- `scripts/ai/aq-drop-daemon` records successful drop dispatch boundaries as a
  best-effort operation.
- `scripts/testing/test-context-boundary.py` covers accumulation, threshold
  handoff, session reset, and payload non-retention.

## Validation

`python3 -m py_compile scripts/ai/lib/context_boundary.py scripts/ai/aq-context-manage scripts/ai/aq-drop-daemon scripts/testing/test-context-boundary.py`

`python3 scripts/testing/test-context-boundary.py` — passed.

`AQ_CONTEXT_MANAGE_SKIP_CLM=1 aq-context-manage boundary --source tool --chars 100 --session-id context-boundary-smoke --native-limit 500 --task 'boundary smoke' --json` — passed.

## Limitation

`aq-event resume` and `aq-event pulse` were attempted but failed because
`.agents/events/a2a-events.jsonl` is mounted read-only. The writable `.agent`
PRD, intent lock, meter state, and this handoff remain available. This guard
cannot force native Codex compaction or alter the coordinator's separate CLM.

## Next step

Have future post-tool/MCP wrappers call `aq-context-manage boundary` with a
count before returning unusually large results; use the generated handoff to
start a fresh hydrated session.
