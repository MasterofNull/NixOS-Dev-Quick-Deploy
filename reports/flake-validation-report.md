# Flake Validation Report

- Timestamp: 2026-02-18T00:52:11Z
- Flake ref: `path:.`
- Lock file: `./flake.lock`

## Summary

- Errors: 0
- Warnings: 2
- Passed checks: 12

## Errors

## Warnings
- Floating branch ref detected (consider release/tag pin): nixpkgs: nixpkgs-unstable
- Floating branch ref detected (consider release/tag pin): nixpkgs_2: nixos-unstable

## Passed Checks
- Dependency graph check passed (all input references resolve to lock nodes).
- Integrity hash check passed (narHash present for all non-root inputs).
- Immutable revision check passed for git-based inputs.
- Source transport check passed (no HTTP flake input URLs detected).
- Local path input check passed.
- Root nixpkgs lock ref: nixos-25.11
- Home Manager lock ref: release-25.11
- Home Manager follows root nixpkgs input.
- Declared nixpkgs ref matches lock (nixos-25.11).
- Declared home-manager ref matches lock (release-25.11).
- home-manager.inputs.nixpkgs.follows is correctly set to 'nixpkgs'.
- nix flake metadata probe succeeded.
