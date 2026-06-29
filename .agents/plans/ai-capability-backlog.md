# AI Capability Backlog Plan

Status: In progress
Owner: codex
Date: 2026-06-29

## Checklist

- [x] Hydrate session context.
- [x] Review existing system and suggested repo catalogs.
- [x] Add machine-readable backlog for missing/high-value capability domains.
- [x] Add schema and validator.
- [x] Wire backlog into system catalog and validation registry.
- [x] Validate focused checks and tier0.
- [x] Commit the slice.

## Implementation Boundaries

- This slice records and governs candidates only.
- First implementation slices must be repo-local pattern extraction, tests, wrappers, or telemetry wiring.
- Runtime enablement requires a later `capability-intake` admission slice with pinned versions, sandboxing, observability, and rollback.
