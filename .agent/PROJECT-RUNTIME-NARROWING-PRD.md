# Runtime Narrowing PRD

Updated: 2026-05-24T16:11:46Z

## Objective

Extend switchboard runtime narrowing beyond tool schema GC by reducing repeated tool execution and large raw tool observations inside local tool-calling loops.

## Problem

Tool working-set GC reduces prompt schema bloat, but long local-agent tasks can still fail by accumulating raw command/search/MCP outputs in chat history. Repeated tool calls also waste wall time and context.

## Scope

- Add per-request local tool-result deduplication.
- Add local tool-output GC that stores large raw observations as artifacts and keeps compact summaries in model context.
- Emit response and health telemetry for output GC, dedupe, and artifact storage.
- Add regression coverage for GC and dedupe behavior.
- Preserve explicit tool behavior and existing finalization-on-tool-budget-exhaustion behavior.

## Out Of Scope

- Full workflow phase executor.
- Cross-request semantic cache for arbitrary tool outputs.
- Dashboard panel wiring.
- Systematic orphan-handler remediation.

## Acceptance

- Repeated identical local tool calls reuse a cached observation instead of re-executing.
- Large tool observations are written to a configured artifact directory with a compact JSON pointer in context.
- Response headers expose artifact count, pruned characters, and duplicate tool-call count.
- `/health` reports context-output GC policy.
- Focused regressions and tier0 pass.
