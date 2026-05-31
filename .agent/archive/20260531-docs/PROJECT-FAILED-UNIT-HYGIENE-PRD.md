# PROJECT FAILED UNIT HYGIENE PRD

## Goal
Remove the current recurring Phase 0 failures caused by timer-driven maintenance services that cannot complete under the hardened runtime layout.

## Problems observed
1. `ai-npm-security-monitor.service` runs as `ai-audit` but executes from a repo path under `/home/hyperd`, which is not traversable by that service account.
2. `ai-aidb-reindex.service` writes `aidb-reindex-latest.json` into the hybrid telemetry directory, which is not writable by the service user.

## Recommended direction
- Run the npm monitor against an immutable repo snapshot in the Nix store instead of the mutable home checkout.
- Pre-create the AIDB reindex summary file via tmpfiles with group-write permissions so the service can update it without broadening directory permissions.
- Keep the existing hardened service posture (`ProtectHome`, `ProtectSystem`, narrow `ReadWritePaths`) intact.

## Scope
- Update `nix/modules/services/mcp-servers.nix`
- Update dry-run verification if it asserts the old mutable repo path
- Validate with targeted checks, `nix flake check --no-build`, and Tier0 gate

## Out of scope
- Redesigning AIDB retry semantics or changing partial-ingest policy
- Changing npm monitor behavior beyond making the existing timer executable under the intended confinement model
