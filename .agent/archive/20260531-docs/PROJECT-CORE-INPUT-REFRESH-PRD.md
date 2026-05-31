# PROJECT-CORE-INPUT-REFRESH-PRD

## Problem
Repo-parity cleanup now shows six genuinely outdated core flake inputs. They should be refreshed deliberately rather than as one broad lockfile jump so regressions can be attributed and rolled back cleanly.

## Goal
Refresh core inputs in controlled slices, beginning with the lowest-risk infrastructure inputs, and validate each step before advancing.

## Scope
### In scope for this first slice
- Refresh exactly one core input: `nixos-hardware`
- Validate lockfile movement and relevant repo checks

### Out of scope for this first slice
- Updating `disko`, `home-manager`, `lanzaboote`, `sops-nix`, or `nixpkgs`
- Deploying the system
- Fixing unrelated Continue/editor QA failures

## Acceptance Criteria
- `flake.lock` updates only the intended `nixos-hardware` node for this slice.
- The lockfile remains parseable.
- Validation commands complete, with unrelated pre-existing failures clearly separated from any new failures.

## Security / Safety
- No secrets or host-specific policy changes.
- No destructive git operations.
- Keep the broadest blast-radius input (`nixpkgs`) for a later slice.

## Rollback
- Revert the isolated `flake.lock` change for `nixos-hardware` if validation reveals regression.
