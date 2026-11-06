# Full flake refresh for the rebuild; nixified-ai hold removed (2026-11-05)

## Objective
Owner directive: every rebuild includes all new packages and updates. Refresh every flake input right before the rebuild, and stop holding nixified-ai at 58a84491.

## Workflow/Session IDs
- Branch: `chore/full-refresh-20261105`, from origin/main.
- Register: FLAKE-NIXIFIED-AI-HELD-58A84491 closed.

## Delegation Decision
Orchestrator: claude-opus, directly. The edit is one flake input override plus a generated lock, under the owner's rebuild request.

## Commands Executed
- `nix flake update`
- `nix flake show --no-write-lock-file .`
- `nix flake check --all-systems --no-build --no-write-lock-file .`
- `nix build --dry-run .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel`
- `scripts/maintenance/aq-pin-watch check` and `apply --dry-run --allow-major`

## Validation Evidence
- nixified-ai moves to c21dc161 (2026-11-05). Its `enable-container-tests` input is locked as a github node, and no node in the lock is unlocked.
- `nix flake show` and `nix flake check` both exit 0.
- Dry run: 88 derivations to build, 330 paths and 717 MiB to fetch.
- `scripts/maintenance/aq-deploy-current` applies both the system and Home Manager, so both get these updates.
- `aq-pin-watch apply --dry-run --allow-major` applies 0 updates. trivy and osv-scanner come from nixpkgs; the versions in its check output are stale registry records.

## Rollback Plan
Revert the commit to return to the previous lock.

## Residual Risk
The override tracks upstream's flag path. If upstream moves or removes that directory, `nix flake update` fails at lock time, which is loud rather than silent.

## Hint Feedback
No hints were consulted.
