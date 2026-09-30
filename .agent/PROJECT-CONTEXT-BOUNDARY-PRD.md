# Context Boundary Meter PRD

## Objective

Measure post-dispatch boundary activity and create a compact fresh-session handoff before the configured native context limit is reached.

## Scope

- Add a repository-local boundary meter with persistent numeric state.
- Estimate payload tokens from byte/character size without storing payload contents.
- Integrate the meter with successful drop dispatches.
- Expose a CLI for tool, MCP, and other wrappers to record boundaries explicitly.
- Emit a resumable handoff when safe or hard thresholds are crossed.

## Acceptance

- Repeated events accumulate estimates and survive process restarts.
- Crossing the safe threshold produces one handoff containing resume commands and no raw payload.
- A new session id resets accumulation.
- Drop dispatch remains best effort if metering fails.
- Python syntax and focused tests pass.

## Exclusions

- No attempt to force native Codex compaction from repository code.
- No coordinator memory-policy change.
- No new environment variables, service, dashboard panel, or destructive cleanup.
