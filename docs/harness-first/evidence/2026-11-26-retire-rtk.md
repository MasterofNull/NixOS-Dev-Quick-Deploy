# Retire rtk from run_command and canonical docs

## Objective

Owner decision 2026-11-25: retire rtk. `rtk gain` measured 18,028 commands, 0.0% saved, "No hook installed"; lean-ctx already rewrites Bash. Remove the rtk wrapping path from `run_command` (no dormant flag, Rule 23) and the doc text that describes it.

## Workflow/Session IDs

- Implementer: Claude Sonnet 5.5 sub-agent (headless, worktree agent-af4b9ec6bcb5d841a). Orchestrator session id not supplied.

## Delegation Decision

Bounded single-file code change plus one doc section and one test; routed to a Claude Sonnet implementer by the orchestrator.

## Commands Executed

- `rg -n -i '\brtk\b|SWB_RTK'` across the repo (excluding archives)
- `python3 scripts/testing/test-local-shell-sandbox.py`
- `python3 scripts/governance/check-cross-surface-contract.py`
- `python3 scripts/governance/check-agent-instruction-parity.py`
- `nix-instantiate --parse`, `nix eval ...toplevel.drvPath`, `tier0.d/check-pm-tracker.sh`
- `ruff check`, `basedpyright` on touched files

## Validation Evidence

Nix: removed the `pkgs/rtk.nix` entry from `nix/modules/roles/ai-stack.nix`; the package file was `git mv`d to `.agent/archive/20261126-rtk.nix` (Rule 12). `nix-instantiate --parse` OK; no other `.nix`/flake reference; `nix eval .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel.drvPath` succeeds (eval only, no build). Python: removed `_RTK_BIN`/`_RTK_ENABLED`, the rtk branch in `run_command_handler` and the unused `shlex` import. The only response key set solely for rtk was `compressed: True`; `rg` found no reader, so the key is gone. New test `test_run_command_never_invokes_rtk` puts a fake `rtk` on PATH and sets `RTK_BIN`; it asserts the command ran plainly and the fake was never called. An initial `rg` without `--hidden` missed `.agent/`; a corrected `rg --hidden` pass found active rtk instructions in `.agent/WORKFLOW-CANON.md` (table row, env vars), `.agent/lanes/local-reference.md` (2 places) and `.agent/lanes/codex-reference.md`, now rewritten to point at lean-ctx (`ctx_shell` / Bash rewrite hook). WORKFLOW-CANON.md is hand-maintained (not generated from canon/blocks), so no generator was run. Remaining rtk mentions are historical (evidence, archives, plan trackers, issues-backlog history, baselines). Test outputs are in the implementer report.

Package-count baseline: `scripts/testing/check-package-count-drift.sh --write-baseline` lowered `hyperd-ai-dev` 391->390, `aqos-vm-ai-dev` 383->382, `aqos-install-vm-ai-dev` 385->384 (and the matching combined counts and summary max/avg). Only the three ai-stack-role targets changed, each by exactly -1 (rtk); home and non-ai-dev targets are unchanged.

## Rollback Plan

Revert the commit; rtk wrapping returns when `rtk` is on PATH.

## Residual Risk

`config/pm-tracker-unbacked-owner-acceptances*.json` still list `tool-rtk`; `tier0.d/check-pm-tracker.sh` PASSES with the package gone, so the hash-pinned baselines are untouched. The `.agents/plans/aqos-tools-inventory/tracker.json` `tool-rtk` item still says rtk is present on PATH (historical editorial note, not edited). The package leaves the system on the next rebuild.

## Hint Feedback

None.
