# Evidence — tiered auto-update U3 (2026-10-01)

## Objective
Unattended, deterministic update pipeline per `.agents/plans/tiered-auto-update-prd-r3-20261001/FREEZE.md` (decisions 3-6), shipped disabled.

## Change
- `mySystem.autoUpdate.{enable=false, flakeAttr, stateDir}`; `nix/modules/core/auto-update.nix` (imported from base.nix): daily notify-only check timer; activation timer every 15 min inside Sun 02:00-04:00 UTC.
- `scripts/maintenance/aq-auto-update`: flock; 15-min idle admission lease (llama /slots, delegate registry, aq-loop state; unknown = defer); resource + baseline health preflight; records previous closure; flake update + aq-pin-watch apply; stops llama-cpp only inside the lease; builds and switches the exact closure; 300s / 3-pass health gate; rollback to the recorded closure + RSI incident; transient watchdog; pending-reboot on kernel change; status.json for U4.

## Security review (orchestrator)
Root executed the script from the user-writable checkout and called repo helpers as root (privilege escalation path). Fixed: ExecStart runs a Nix-store snapshot taken at rebuild; repo helpers (flake update, aq-pin-watch, aq-qa, aq-rsi) run via `runuser -u <primaryUser>` (`AQ_AUTO_UPDATE_RUN_AS`). nixos-rebuild build/switch stays root (same trust model as the owner's sudo rebuild).

## Validation
`scripts/testing/test-aq-auto-update.py` 7/7 (lease busy, unknown signal, window, health-fail rollback to recorded closure + incident, kernel pending-reboot, dry-run no side effects, helpers run as owner). `nix-instantiate --parse` on new/edited modules.

## Not done (pre-activation follow-ups)
Full flake eval with the option enabled; real switch + injected-failure recovery drill; watchdog survival proof; per-attr promotion (U2) and monthly stable cadence; restoring aq-pin-watch edits when a run aborts before switch.

## Rollback
Feature is off by default; remove `mySystem.autoUpdate.enable` (or leave false). Revert this commit to remove the module.

## Activation
ACTIVATION_BLOCKED until the follow-ups above pass and the owner enables the option.

## Agents
Implementer: Claude Sonnet (isolated worktree). Review + security fix: Claude Opus. Binding review queued (codex/local).

## U4 observability (2026-10-01)
- `scripts/ai/lib/auto_update_status.py`: read-only projection of `<state_dir>/status.json` + `halted` into not_enabled / unknown / attention / ok (unknown != healthy: corrupt or missing status is UNKNOWN).
- CLI-first: `aq-rsi status` prints last outcome/time, versions moved, rollback, halted, pending-reboot hours vs SLA (BREACH); `--json` carries `auto_update`.
- API: `GET /api/health/auto-update` (dashboard backend) returns the same projection. Dashboard card deferred.
- Tests: test-auto-update-observability (8 fixture cases, CLI text + JSON + API function agree); test-aq-rsi still passes.
