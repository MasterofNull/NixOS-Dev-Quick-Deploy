# PROJECT-KERNEL-TRACK-MIGRATION-PRD

## Problem
The repo encodes short-lived kernel versions as long-lived policy names (`6.19-latest`, `6.18-lts`). After the `nixos-25.11` nixpkgs update, upstream removed Linux 6.19 as EOL, causing evaluation to fail anywhere the repo still selects that track.

## Goal
Replace version-specific kernel policy names with durable semantic tracks so host intent survives upstream kernel churn:
- `latest-stable`
- `lts`
- `default`

## Scope
### In scope
- Update kernel option schema, docs, and selection logic.
- Migrate current `ai-dev` and `hyperd` selections away from `6.19-latest`.
- Replace the remaining `6.18-lts` policy with semantic `lts` resolution.
- Add warnings/assertions that surface unavailable tracks cleanly.
- Finish validating the pending `nixpkgs` refresh after the policy migration.

### Out of scope
- Changing unrelated hardware facts.
- Deploying the system.
- Pinning a custom kernel package outside supported nixpkgs tracks.

## Acceptance Criteria
- No active config references `6.19-latest` or `6.18-lts`.
- `latest-stable`, `lts`, and `default` all resolve to supported package sets under current nixpkgs.
- `nix flake check --no-build` passes with the refreshed `nixpkgs` input.
- Tier 0 validation passes.

## Security / Safety
- No bootloader or secure-boot settings are changed.
- Only kernel selection policy is altered.
- Keep `latest-stable` as the performance-oriented ai-dev default and `lts` as the conservative stable path.

## Rollback
- Revert the semantic-track migration and the pending nixpkgs lockfile update together if the new policy fails validation.
