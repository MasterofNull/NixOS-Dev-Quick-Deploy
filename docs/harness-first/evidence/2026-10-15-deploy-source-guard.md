# Deploy-source guard + deployed-revision record (2026-10-15)

## Objective
Root-cause fix for the 2026-10-15 incident: PRs #517-#526 were merged, the owner ran
`sudo nixos-rebuild switch --flake .#hyperd-ai-dev` from the primary checkout while it was still on
`feat/durable-mesh-dp3-oncall-daemon @ 7f9ef0f4`, so none of the merged work deployed and nothing warned.
Contributing cause: `core.hooksPath` is an ABSOLUTE path to the primary checkout's `.githooks`, so every
worktree runs the hooks of whatever branch the primary checkout has checked out. Also the system did not record
its source revision (`nixos-version --json` showed only nixpkgs).

Timeline: PRs #517-#526 merged -> owner ran `nrs` from primary checkout on the old feature branch -> build
succeeded from stale source -> merged work absent from the running system, no warning anywhere.

## Workflow/Session IDs
Worktree `.agents/delegation/worktrees/deploy-guard`, branch `fix/deploy-source-guard` (from origin/main 12e92bee).
Implementer lane: Claude Sonnet 5.5 (delegated by orchestrator). Staged, not committed.

## Delegation Decision
Bounded implementer slice dispatched by the orchestrator (Rule 17: balanced tier, explicit override). No sub-delegation.

## Commands Executed
- `git worktree add -b fix/deploy-source-guard .agents/delegation/worktrees/deploy-guard origin/main`
- New: `scripts/governance/check-deploy-source.sh` (shared guard), `scripts/governance/primary-checkout-warn.sh`,
  `scripts/testing/test-deploy-source-guard.py`.
- Entry points wired (all call the guard BEFORE building): `nrs`, `nrb`, `nrs-force()`, `hms()` in
  `nix/home/base.nix`; `nixos-quick-deploy.sh` (all modes except `build`, right after arg parsing, before
  `nixos-rebuild`). `nrd` (dry-build) is intentionally unguarded. `pre-rebuild-preflight.sh` and
  `check-checkout-fresh.sh` are unchanged (the latter still fast-forwards a clean main).
- `flake.nix` mkHost: `system.configurationRevision = lib.mkDefault (self.rev or self.dirtyRev or "unknown")`.
- `scripts/ai/aq-health-spider`: `_deployed_revision_check` (+ `deployed_revision_stale` handler, advisory).
- `scripts/ai/aq-resume`, `scripts/ai/aq-session-start`: print WARN when the primary checkout is not on main.
- `scripts/deploy/install-git-hooks.sh`: now sets relative `core.hooksPath .githooks`.
- `scripts/governance/tier0.d/check-lane-hook-parity.sh`: requires the relative form, GAPs on absolute, and verifies
  each worktree resolves hooks to its own `.githooks` (`git rev-parse --git-path hooks`). Test extended.

Guard semantics (exit 4 = blocked): (a) HEAD not on `main`; (b) HEAD != origin/main after a 15 s `git fetch`
(fetch failure => BLOCK, see offline policy); (c) dirty tracked files: inert paths (`.agent/**`, `.agents/**`,
`docs/**`, `*.md` outside `nix/`) only WARN, everything else (flake.nix, flake.lock, nix/**, ai-stack/**, scripts/**,
config/**, dashboard/**, assets/**, ...) BLOCKS. The allowlist is deliberately conservative: `nixos-rebuild --flake path:`
copies the whole tree and modules read repo files at eval/build time (e.g. `mySystem.mcpServers.flakeRepoPath = self`),
so anything not known-inert is treated as build-affecting. `AQ_DEPLOY_ALLOW_BRANCH=1` overrides with a loud banner and
appends a line to `.agent/collaboration/PULSE.log` (or `$AQ_DEPLOY_GUARD_LOG`). Under sudo, git runs as `$SUDO_USER`
via `runuser` (no root-owned files in `.git`, no safe.directory problem); otherwise `-c safe.directory=<dir>`.

dirtyRev: a flake built from a dirty tree records `system.configurationRevision = "<sha>-dirty"` (verified:
`12e92beedc94...-dirty`). Because inert files (agent logs) are routinely dirty in the owner's checkout, the guard allows
the deploy but the revision is recorded as dirty; the health-spider treats `-dirty` (and `unknown`) as a WARNING, as it
does a revision that is not an ancestor of origin/main or lags it by more than `HS_DEPLOY_LAG_HOURS` (24) /
`HS_DEPLOY_LAG_COMMITS` (50). Local git only (cached origin/main), no network.

PULSE-style notes (orchestrator to transcribe): `[2026-10-15] [claude-implementer] [deploy-guard]: check-deploy-source.sh + configurationRevision + spider check + hooksPath relative — staged on fix/deploy-source-guard`.

## Validation Evidence
- `python3 scripts/testing/test-deploy-source-guard.py`: 9/9 ok, PASS (main+clean+in-sync pass; inert-dirty warn+pass;
  build-dirty block; override pass+log; feature branch fail with fix commands; override pass; behind origin fail; offline
  fetch blocks and prints the fetch error; offline + AQ_DEPLOY_OFFLINE=1 pass with banner + log; offline + dirty build
  blocked; offline + ALLOW_BRANCH pass). 11/11 after review follow-up.
- `python3 scripts/testing/test-lane-hook-parity.py`: PASS (includes new absolute-path GAP case).
- `bash scripts/governance/tier0.d/check-lane-hook-parity.sh` from the worktree: reports the two expected GAPs
  (absolute hooksPath in the primary checkout / worktrees resolving to it) until the owner runs the one-time command below.
- `nix-instantiate --parse flake.nix nix/home/base.nix`: OK.
- `nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.system.configurationRevision` (dirty staged tree): `12e92beedc94ac641bb58b9150f2783a3e5b431c-dirty` (4 s).
- `_deployed_revision_check` exercised manually: empty/unknown -> warn, `-dirty` -> warn, unknown sha -> warn, `HEAD~300` -> lag warn, `origin/main` -> clean.
- Unverified: a real `sudo nrs` through the new alias (needs home-manager switch to pick up `base.nix`), the runuser path under
  real sudo, and `nixos-version --configuration-revision` output on the live host after the first rebuild. On this host, with no
  revision recorded, that command prints to stderr and exits rc=1; the spider maps that (None) to "no revision recorded" (warning).

## Offline policy decision (review follow-up)
A failed fetch (network, auth, timeout) cannot prove the source is current, so the guard FAILS and prints git's fetch error
text for diagnosis. `AQ_DEPLOY_OFFLINE=1` is the deliberate escape: loud banner "cannot prove up to date; deploying cached
origin/main <sha> from <date>" plus a log line; branch/dirty-build/HEAD-vs-cached-origin checks still apply.
`AQ_DEPLOY_ALLOW_BRANCH=1` also overrides.

## Hooks caveat
With relative `core.hooksPath=.githooks`, a worktree on an old branch that lacks `.githooks/` runs NO hooks (git skips a missing
hooks dir). `check-lane-hook-parity.sh` flags such worktrees as GAP (pre-commit not found in their own tree); rebase them onto main.

## Rollback Plan
`git revert` the commit; hooks: `git config core.hooksPath "$(git rev-parse --show-toplevel)/.githooks"`. Emergency bypass
without revert: `AQ_DEPLOY_ALLOW_BRANCH=1 nrs`.

## Residual Risk
- Aliases take effect only after `home-manager switch` (itself guarded) from main; until then `nrs` is unguarded.
- Guard covers the known entry points; a raw `sudo nixos-rebuild switch` typed by hand bypasses it (revision record + spider warning still detect it afterwards).
- The inert allowlist could hide a `.md` that something reads at eval time; keep eval-time inputs out of docs/.
- `.githooks/pre-commit` main-checkout guard behavior not changed here.

## One-time owner commands and activation
```
git -C /home/hyperd/Documents/NixOS-Dev-Quick-Deploy switch main
git -C /home/hyperd/Documents/NixOS-Dev-Quick-Deploy pull --ff-only origin main
git -C /home/hyperd/Documents/NixOS-Dev-Quick-Deploy config core.hooksPath .githooks
```
Activation (after this PR merges to main): from the primary checkout on clean main, `nrs` (system, records the revision;
`nixos-version --configuration-revision` should then print the main sha) and `hms` (installs the guarded aliases).

## Hint Feedback
No aq-hints consulted for this slice; existing `check-checkout-fresh.sh` was found and left in place (it handles the
fast-forward case; the new guard adds branch/dirty classification).
