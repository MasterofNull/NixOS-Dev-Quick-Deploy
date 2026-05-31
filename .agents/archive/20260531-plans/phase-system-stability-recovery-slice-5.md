# Phase — System Stability Recovery Slice 5

## Objective
Move the workstation off the retired 6.19 kernel family only as far as required for the refreshed stable package set to evaluate, while keeping the change explicit and reviewable.

## Scope Lock
### In
- `nix/hosts/hyperd/default.nix`

### Out
- broader kernel policy refactors
- profile-wide kernel defaults
- custom kernel module redesign

## Workstreams
1. Replace the host-only `6.19-latest` pin with `latest-stable` after upstream removal of 6.19 from the refreshed stable channel.
2. Validate the resolved kernel and Redis versions together before deployment.

## Validation
- `nix eval --raw '.#nixosConfigurations.hyperd-ai-dev.config.mySystem.kernel.track'`
- `nix eval --raw '.#nixosConfigurations.hyperd-ai-dev.config.boot.kernelPackages.kernel.version'`
- `nix eval --raw '.#nixosConfigurations.hyperd-ai-dev.pkgs.redis.version'`
- `nixos-rebuild build --flake .#hyperd-ai-dev`

## Rollback
Revert the host pin only if the selected package set again exposes a supported alternative kernel track and the replacement generation passes health checks.
