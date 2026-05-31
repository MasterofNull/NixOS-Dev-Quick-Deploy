# Phase — System Stability Recovery Slice 4

## Objective
Advance the stable nixpkgs lock just far enough to restore Redis reader compatibility with state already written by Redis 8.6.x, without importing unrelated kernel-track or ROCm experiments.

## Scope Lock
### In
- `flake.lock` stable nixpkgs lock refresh only

### Out
- kernel policy changes
- host profile changes
- ROCm target automation
- destructive Redis state repair

## Workstreams
1. Reuse the minimal stable nixpkgs lock refresh already present in the worktree.
2. Verify the target Redis package resolves to a compatible 8.6.x version.
3. Keep broader experimental changes unstaged.

## Validation
- `nix eval --raw '.#nixosConfigurations.hyperd-ai-dev.pkgs.redis.version'`
- `nix flake check --no-build`
- focused validation remains green

## Rollback
Revert the lock refresh only if Redis state has first been migrated or rebuilt into a version readable by the older package.
