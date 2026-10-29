# Flake lock refresh — 2026-10-29

## Objective

Commit the flake input update through a PR instead of leaving it uncommitted in the main checkout. The running system (`26.05.20261025`, built from an uncommitted lock) is ahead of `origin/main`, whose nixpkgs is pinned to 2026-10-14. Rebuilding from main without this refresh would roll packages back about 11 days.

## Workflow/Session IDs

- Claude session 50391bdd. Backlog: FLAKE-LOCK-UNCOMMITTED-UPDATE, DEPLOY-DRIFT-SSOT.
- The stray lock was archived by the owner at `.agents/archive/20261029-flake.lock` before `git restore`.

## Delegation Decision

Mechanical `nix flake update` in an isolated worktree, run by the orchestrator. There is no code to implement; the value is in the pre-build and the review. Independent review: local Qwen.

## Commands Executed

```
nix flake update      # in worktree chore/flake-refresh-20261029, based on origin/main
nix build --no-link --print-out-paths --max-jobs 2 \
  .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel \
  .#homeConfigurations.hyperd.activationPackage
```

## Validation Evidence

Inputs updated (8): nixpkgs 26f4107e (2026-10-14) -> 08d3a975 (2026-10-28); nixpkgs-unstable 55bfb4d7 -> 31ecbaca (2026-10-27); home-manager 32904dfe -> 24f21905 (2026-10-23); sops-nix 44931708 -> 60182817 (2026-10-26); disko, impermanence, nixified-ai, nixos-hardware to 2026-10-20..28. These are the same revisions as the stray uncommitted lock.

Pre-build result: see the PR body. It records the system and home-manager closure store paths, or the failure.

## Rollback Plan

Revert this commit and rebuild. The previous pins return. Note that the currently running system is already on 2026-10-25 nixpkgs, so a revert is itself a downgrade from what runs today.

## Residual Risk

- Package updates can change behavior at runtime. The pre-build proves evaluation and build only; validation happens after the owner's rebuild (delivery-workflow step 6).
- llama.cpp and nixified-ai moved; check the local model's speed with the speed probe after the rebuild.

## Hint Feedback

Lock updates done in place left the running system ahead of the source of truth with no signal. With `aq-deploy-current`, lock updates only arrive through PRs like this one.
