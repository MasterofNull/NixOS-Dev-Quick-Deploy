# Power policy ordering cycle (P1.7 follow-up)

## Objective
Remove the systemd ordering cycle introduced by `power-policy-apply.service` (#646). Journal 2026-10-29 14:22 after the owner's rebuild: `power-profiles-daemon.service: Found ordering cycle: multi-user.target/start after power-policy-apply.service/start after power-profiles-daemon.service/start - after multi-user.target` -> "Transaction order is cyclic", nixos switch exit 4. Constraint: apply still runs after the daemon at boot and after resume.

## Workflow/Session IDs
Branch `fix/power-policy-ordering-cycle` (worktree `.agents/delegation/worktrees/power-policy-cycle`), bounded implementer under the orchestrator session 50391bdd. No commit/push by the implementer.

## Delegation Decision
Bounded single-file Nix change plus one test assertion, delegated to a Sonnet-tier implementer per Rule 17. Orchestrator reviews and commits.

## Commands Executed
- `nix-instantiate --parse nix/modules/core/power-policy.nix`
- `nix eval --json .#nixosConfigurations.hyperd-ai-dev.config.systemd.services.power-policy-apply.{wantedBy,after,wants}` and `systemd.defaultUnit`
- `nix build --no-link --print-out-paths '.#nixosConfigurations.hyperd-ai-dev.config.systemd.units."power-policy-apply.service".unit'`
- `systemd-analyze verify` (systemd 260.5) against an isolated unit dir (`SYSTEMD_UNIT_PATH` without trailing colon, so the host's /etc/systemd/system does not leak in) holding the built apply unit, upstream power-profiles-daemon-0.30 unit, real multi-user/graphical targets, stub dbus/display-manager units; old vs new WantedBy.
- `python3 scripts/testing/test-llm-speed-probe.py`, also with the Nix change stashed.

## Validation Evidence
- Change: `wantedBy = ["multi-user.target" "post-resume.target"]` -> `["graphical.target" "post-resume.target"]`; `after`/`wants` on the daemon unchanged.
- parse: OK. eval: wantedBy `["graphical.target","post-resume.target"]`, after `["power-profiles-daemon.service"]`, wants `["power-profiles-daemon.service"]`, defaultUnit `"graphical.target"`.
- Built unit [Unit]/[Install]: `After=power-profiles-daemon.service`, `Wants=power-profiles-daemon.service`, `WantedBy=graphical.target post-resume.target`.
- Upstream daemon unit: `After=multi-user.target display-manager.target` (WantedBy=graphical.target), untouched.
- verify, old WantedBy (multi-user): `Found ordering cycle: power-profiles-daemon.service/start after multi-user.target/start after power-policy-apply.service/start - after power-profiles-daemon.service` (reproduces the journal defect).
- verify, new WantedBy (graphical): no cycle output.
- Test: `test-llm-speed-probe.py` exit 0 with new assertions "not WantedBy multi-user.target" and "WantedBy graphical.target"; with the Nix change stashed both FAIL.
- Other units in the file: `aq-llm-speed-probe` (After llama-cpp, no wantedBy, started by timer in timers.target) and `aq-llm-speed-probe-resume` (After+WantedBy post-resume.target, no relation to the daemon) have no path back to the daemon or multi-user.target; no cycle.
- Not done: full-closure `systemd-analyze verify` of the whole toplevel (not built); the final proof is the owner's next `nixos-rebuild switch`.

## Rollback Plan
Revert the one-line wantedBy change (restores the cycle) or set `mySystem.deployment.powerPolicy.acAwareProfile.enable = false` to drop the unit entirely.

## Residual Risk
- A host booting to multi-user.target (no graphical default) would not run apply at boot; the udev Mains rule and post-resume.target still trigger it. hyperd-ai-dev default is graphical.target (roles/desktop.nix).
- Out of scope, unverified: `nix/modules/hardware/mobile.nix:67` `cosmic-battery-bridge` has both `wantedBy` and `after` containing `multi-user.target` (self-ordering after the target that wants it); not analysed here, worth a separate `systemd-analyze verify`.
- The new test is a source-level regex, not an eval; it guards this specific shape only.

## Hint Feedback
Facts only: the defect was found by live validation after enable + rebuild. Unit tests and two reviews of #646 missed it because neither evaluated the generated unit graph against upstream unit ordering. `systemd-analyze verify` with an isolated unit path reproduces it offline in seconds.
