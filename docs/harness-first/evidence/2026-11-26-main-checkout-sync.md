# Declared safe sync of the live main checkout (aq-main-sync)

## Objective

Nine systemd units (ai-stack-health-monitor, fast-lane-staleness-monitor, identity-kernel, revocation-epoch-authority, durable-sweeper, aq-help-center, command-center-dashboard, agent-reap, auto-update) execute code from `mySystem.mcpServers.repoPath`, the owner's live main checkout. That checkout only advanced when the owner ran `aq-deploy-current`, so the units ran stale code for hours or days and raised false critical alerts on 2026-11-25/26. Declare a timer that fast-forwards the checkout to origin/main whenever that is provably safe.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5 sub-agent (headless, worktree agent-ac7bbe2dc48e50af1). Orchestrator session id not supplied.

## Delegation Decision

Bounded slice (one script, one Nix service/timer, one option, one manifest entry, one test) routed to a Claude Sonnet implementer by the orchestrator (Rule 17).

## Commands Executed

- `python3 scripts/testing/test-aq-main-sync.py`
- `shellcheck scripts/maintenance/aq-main-sync`, `ruff check scripts/testing/test-aq-main-sync.py`
- `nix-instantiate --parse` on the three touched `.nix` files
- `nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.systemd.services.aq-main-sync.serviceConfig.ExecStart`
- `check-activation-manifest.py --staged`, `check-cross-surface-contract.py`, `tier0.d/check-ci-test-coverage.sh`

## Validation Evidence

Design. `scripts/maintenance/aq-main-sync [--repo <dir>]` runs as the checkout owner (refuses root) and does `git fetch origin main`, then `git merge --ff-only origin/main` only if: branch is `main`; no MERGE_HEAD/CHERRY_PICK_HEAD/REVERT_HEAD/rebase/bisect marker; local main is a strict ancestor of origin/main; no build-affecting tracked file is dirty. "Build-affecting" uses the same rule as `aq-deploy-current`: the `inert_re` line read from `scripts/governance/check-deploy-source.sh` (inert = `.agent/**`, `.agents/**`, `docs/**`, `*.md` outside `nix/`), so `.agent/collaboration/*` and `issues-backlog.md` never block. The regex is read from that single source rather than copied; the 3-line dirty loop is repeated, not shared, because `aq-deploy-current` keeps it inline. It never stashes, resets, discards or autostashes; if git refuses the merge because an incoming change overlaps a local inert edit, it skips and leaves the edit. One journal line per run: `synced <before>..<after>` or `skip: <reason>`; skips (including offline fetch failure) exit 0, unexpected errors (not a repo, root, unreadable inert rule) exit 1. Kill switch: `AQ_MAIN_SYNC=0` or `AQ_MAIN_SYNC_DISABLE=1`.

Nix. Option `mySystem.deployment.mainSync.enable` (default false, `core/options.nix`), set `lib.mkDefault true` in `profiles/ai-dev.nix`. Service `aq-main-sync` and timer (`OnCalendar=*:0/15`, `RandomizedDelaySec=2min`, `Persistent=true`) sit beside `ai-stack-health-monitor` in `roles/ai-stack.nix`, run as `primaryUser`, with `ProtectSystem=strict`, `ProtectHome=read-only`, `NoNewPrivileges`, `PrivateTmp`, and `ReadWritePaths` limited to the repo path (fetch writes `.git`, the merge rewrites tracked files). `GIT_TERMINAL_PROMPT=0` so a missing credential fails fast. The timer-stagger module applies its values with `mkDefault`, so the explicit delay wins. Eval of the service resolves to the repoPath script.

Activation (Rule 15): integrated (service in `ai-stack.nix`, manifest entry in `config/activation-manifest.json`), ON (profile default), validated by the hermetic test below, observable (journal line per run), intervenable (kill switch env, or `mySystem.deployment.mainSync.enable = false`). Not live until the owner rebuilds.

Tests: `scripts/testing/test-aq-main-sync.py`, registered in `config/ci-checks.json`. Cases: clean and behind fast-forwards; dirty `app.py` skips; tracked-dirty `nix/x.md` skips (nix is never inert); only `.agent/collaboration/PULSE.log` dirty fast-forwards; not on main skips; diverged skips; MERGE_HEAD present skips; kill switch skips; dirty inert file overlapping an incoming change skips and keeps the local edit; no stash is ever created. Output: `OK: test-aq-main-sync`. shellcheck and ruff clean. Gate outputs are in the implementer report.

## Rollback Plan

Revert the commit, or set `mySystem.deployment.mainSync.enable = false` and rebuild. Immediate stop without a rebuild: `systemctl stop aq-main-sync.timer`, or set `AQ_MAIN_SYNC=0` in the unit environment.

## Residual Risk

- Origin is HTTPS with credential helper `!gh auth git-credential`, and gh keeps its token in the keyring, so the system service cannot fetch. The script therefore tries `git fetch` (30s timeout, `GIT_TERMINAL_PROMPT=0`) and on failure falls back to the existing local `refs/remotes/origin/main`, logging `fetch failed; using local origin/main <sha> (ref updated <N>m ago)`. Agents and aq-land fetch into this shared git dir constantly, so the ref is normally fresh, but it can be stale if nobody has fetched; the log line shows its age. Only a missing local ref skips. All other guards still apply. Test covers the bogus-remote fallback and the missing-ref skip.
- A fast-forward changes files that already-running long-lived units loaded; they pick up new code on their next restart. This sync removes staleness for timer-driven units, not for daemons; `aq-deploy-current` still restarts and verifies.
- The tracked-file check ignores untracked files; an untracked file colliding with an incoming path makes git refuse, and the run skips.
- The deploy path is unchanged: `aq-deploy-current` still verifies revision == HEAD and not dirty.

Owner steps (copy-paste):

```
cd ~/Documents/NixOS-Dev-Quick-Deploy && scripts/maintenance/aq-deploy-current
systemctl list-timers 'aq-main-sync*'
sudo systemctl start aq-main-sync.service   # optional: run once now
journalctl -u aq-main-sync -n 5
```

Expected: the timer is listed with a next run within 15 minutes; the journal shows `[aq-main-sync] synced <sha>..<sha>` or `skip: <reason>` per run.

## Hint Feedback

None.
