# Activate aq-oncalld: monitoring on, repairs off, separate-clone design

## Objective

`ai-oncalld.service` has been active since 2026-11-19 but skipped every incident: journal `Worktree creation failed for claim-<id>-1: [Errno 2] No such file or directory: 'git'`. Fix the unit declaratively (Rule 13/14) and correct the stale "never enabled" deferral in `config/activation-manifest.json` (the unit is enabled by `services.aiOncalld.enable` in `nix/hosts/hyperd/default.nix:52`).

Root cause: the unit PATH had no `git`. Behind it sat two more faults: with `ProtectHome=read-only` the engine's default worktree root (inside the owner checkout) is read-only, and `git worktree add` writes refs and metadata into the repo it runs in.

D1 (owner decision 2026-11-27, after independent Codex and Gemini review; both disagreed with the first design that granted `ReadWritePaths` on `<repo>/.git`): the daemon uses a SEPARATE CLONE. The owner checkout stays read-only to the unit; repair worktrees come from `/var/lib/aq-oncalld/repo`, a `git clone --no-hardlinks` of the owner repo refreshed by a local `git fetch` (no network, no token). Until that path is validated live, repairs are OFF (`services.aiOncalld.repairs.enable = false`): the daemon records incidents (monitoring) but attempts no repair worktree.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5 sub-agent (headless, worktree agent-ac184740a61e09f1d), reworked once per the 2026-11-27 owner decision. Orchestrator session id not supplied.

## Delegation Decision

Bounded Nix/engine/manifest change plus tests, routed to a Claude Sonnet implementer by the orchestrator (Rule 17). The design choice (D1, separate clone, repairs off) was made by the owner after cross-agent review and is not re-litigated here.

## Commands Executed

- `rg` over `scripts/ai/lib/oncalld_engine.py` and `scripts/ai/aq-oncalld` for subprocess/which calls: only `git worktree add` and `bwrap`/`bash -c`.
- `nix-instantiate --parse nix/modules/services/oncalld.nix`
- `nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.systemd.services.ai-oncalld.{path,serviceConfig.ReadWritePaths,environment,serviceConfig.ProtectHome}`
- `python3 scripts/testing/test-aq-oncalld.py`, `python3 scripts/testing/test-oncalld-nix-module.py`
- `python3 scripts/governance/check-activation-manifest.py --staged --repo-root <worktree>`
- `python3 scripts/governance/check-cross-surface-contract.py`, `scripts/testing/check-harness-first-pr-evidence-gate.sh`, `scripts/governance/tier0.d/check-ci-test-coverage.sh`

## Validation Evidence

Nix (`nix/modules/services/oncalld.nix`): `path = [ git bubblewrap bash ]`; new options `cloneDir` (default `/var/lib/aq-oncalld/repo`) and `repairs.enable` (default false); env `AQ_DELEGATION_DIR`, `AQ_ONCALL_CLONE_DIR`, `AQ_ONCALL_SOURCE_REPO`, `AQ_ONCALL_REPAIRS`; tmpfiles rule for the clone dir; AppArmor profile grants `rwk` on the clone, not on the owner repo (read only). Evaluated for `hyperd-ai-dev`:

- path: git-2.54.0, bubblewrap-0.12.0, bash-interactive-5.3p9, coreutils, findutils, gnugrep, gnused, systemd
- ReadWritePaths: `/var/lib/aq-oncalld`, `/var/lib/aq-oncalld/worktrees`, `/var/lib/aq-oncalld/repo` (no path under the owner repo)
- environment: `AQ_DELEGATION_DIR=/var/lib/aq-oncalld`, `AQ_ONCALL_CLONE_DIR=/var/lib/aq-oncalld/repo`, `AQ_ONCALL_SOURCE_REPO=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy`, `AQ_ONCALL_REPAIRS=0`
- ProtectHome: `read-only`

Engine (`scripts/ai/lib/oncalld_engine.py`): `OnCallDaemonEngine` gains `repairs_enabled` (env `AQ_ONCALL_REPAIRS`, default off), `clone_dir`, `source_repo` and `ensure_clone()` (clone `--no-hardlinks` if absent, then `git fetch origin <branch>` and detach at FETCH_HEAD; failures raise typed `WorktreeIsolationError`, the claim is recorded FAILED and the daemon logs "Skipping incident"). `create_isolated_worktree` runs `git worktree add` in the clone. `run_once` with repairs off admits and records the incident, logs an info line and makes no claim or worktree.

Manifest: entry state is now monitoring-on, repairs-off, with unblock criteria (clone created, one synthetic incident repaired in a worktree, no write to the owner repo) and review date 2026-12-11; `health_signal` is `scripts/ai/lib/oncalld_engine.py:health_summary`.

Tests: `test-aq-oncalld.py` 22/22 pass. New: `test_09b` (PATH without git raises typed `WorktreeIsolationError`, claim FAILED), `test_09c` (git on PATH creates a worktree), `test_09d` (clone created in a temp tree, worktree made from it, owner repo file mtimes unchanged across two incidents, i.e. refresh path too), `test_09e` (bad clone source gives typed error and FAILED claim), `test_09f` (repairs off: incident stored, no claim, `subprocess.run` never called). `test-oncalld-nix-module.py` 6/6 pass. Fails-without-the-fix: the new `test_no_write_path_into_owner_repo` and `test_repairs_default_off_and_wired` were checked against the previous staged module (first design): there `repoDir` is in ReadWritePaths (True), `cloneDir` is not, an AppArmor `repoDir/.git` rule exists, and no `repairs.enable` option exists, so both fail on it. `test_09b` documents the typed-failure contract and passes before and after the engine change (the engine already failed closed).

Review round 2 (Gemini REQUEST_CHANGES on 48aa2ec73, all verified and fixed): (HIGH) the daemon never configured logging, so the INFO "repairs disabled" line was dropped; `aq-oncalld` main now calls `configure_logging()` (INFO to stderr/journal, `AQ_ONCALL_LOG_LEVEL` override), test `test_09j`. (MEDIUM) `ensure_clone` fails closed when `clone_dir` equals or nests with `source_repo` (`test_09g`), the Nix module asserts `cloneDir != repoDir`, the branch name must match a safe pattern (`test_09h`), fetch uses the source path after `--` instead of the clone's stored `origin`, and clone/fetch/checkout all run with `-c core.hooksPath=/dev/null` (`test_09i`). (LOW) AppArmor read rule uses `${cfg.repoDir}` (nix test), setUp/tearDown save and clear all `AQ_ONCALL_*` env vars, `test_09d` starts from a pre-existing empty clone dir as tmpfiles creates it. With the four non-test files reverted to the reviewed commit, tests 09g, 09h, 09i, 09j and the new Nix test fail (5 failures); restored, 26/26 and 7/7 pass.

Post-rebuild validation (owner runs the rebuild; not yet run):
1. Monitoring: `journalctl -u ai-oncalld --since "-15min" | rg "recorded; repairs disabled"` shows incidents recorded; `journalctl -u ai-oncalld --since "-15min" | rg -c "No such file or directory: 'git'"` prints 0; `systemctl show ai-oncalld -p Environment` shows `AQ_ONCALL_REPAIRS=0`.
2. Repair path (only after setting `services.aiOncalld.repairs.enable = true` in a later rebuild): journal shows a `claim-*` worktree created and no ENOENT; `ls /var/lib/aq-oncalld/repo/.git` exists; `ls /var/lib/aq-oncalld/worktrees` lists `claim-*`; `git -C /home/hyperd/Documents/NixOS-Dev-Quick-Deploy status --short` unchanged and `git -C /home/hyperd/Documents/NixOS-Dev-Quick-Deploy worktree list` shows no `claim-*`.

## Rollback Plan

Revert the commit and rebuild. Stray clone and claim worktrees live only under `/var/lib/aq-oncalld`; archive them with `mv` (Rule 12) if needed. The owner repo is never modified by this design.

## Residual Risk

Repairs stay off until the clone path is validated live; review date 2026-12-11 (manifest). The clone is a snapshot of the owner repo's `main` (override `AQ_ONCALL_SOURCE_BRANCH`), so unpushed owner work is not visible to repairs. A local fetch from a repo the unit can only read relies on same-uid ownership (no `safe.directory` needed); if ownership changes the clone fails closed with a typed error. AppArmor is in complain mode, so its rules are advisory. Reproduction runs in bwrap; without a user namespace it returns a typed deferral rather than running unconfined.

## Hint Feedback

None.
