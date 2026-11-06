## Objective
Retire the Antigravity IDE lane and route its seat to the headless Gemini CLI (scripts/ai/delegate-to-gemini). Owner directive 2026-11-05: RSI was triggering the Antigravity IDE, which is retired in favour of the headless Gemini CLI tooling.

## Workflow/Session IDs
Branch fix/retire-antigravity-lane (worktree .agents/delegation/worktrees/retire-antigravity, from origin/main). Working notes and scripts: .agents/delegation/outputs/retire-antigravity/ (REPORT.md).

## Delegation Decision
Implementer: Claude Sonnet (Rule 17). Orchestrator: claude. Date: 2026-11-05. Staged, not committed.

## Commands Executed
- rg -il antigravity over scripts, nix, config, ai-stack, canon to enumerate every trigger.
- Edits applied through scripts in .agents/delegation/outputs/retire-antigravity/ (s1..s9).
- git mv of retired artifacts to .agents/archive/20261105-antigravity-lane/ (Rule 12).
- python3 scripts/governance/canon-compile.py --write, then --check (Rule 16 parity).
- nix-instantiate --parse on changed .nix; nix eval of the hyperd-ai-dev toplevel drvPath.
- scripts/governance/tier0.d/check-ci-test-coverage.sh; scripts/testing/test-no-antigravity-ide-trigger.py; ./scripts/governance/run-ci-checks.sh --changed --base refs/remotes/origin/main.

## Validation Evidence
- Triggers removed: ai-dev.nix antigravityAutoWake.enable and the module import (module archived), aq-collab-round inbox drop + `aq-antigravity-inbox wake`, prsi-orchestrator `antigravity` lane (now `gemini`, plan-only), every `gemini` dispatch map that pointed at delegate-to-antigravity (aq-agent-window, aq-subagent-interactive, aq-coordinator-repl, agents_task_handlers, delegate-fanout, aq-loop, aq-cascade, aq-knowledge-import.sh, aq-gap-import).
- nix-instantiate --parse: ok on default.nix, ai-dev.nix, ai-stack.nix, fast-lane.nix.
- nix eval toplevel drvPath: /nix/store/f7blhxi174bpjkz52iiql30w4p84aj2x-nixos-system-hyperd-26.05.20261102.7dcdd87.drv
- check-ci-test-coverage.sh: PASS (758 tests: 608 declared, 150 exempt).
- test-no-antigravity-ide-trigger.py: 8 tests OK (no live reference to the IDE wake/inbox; gemini seat dispatches delegate-to-gemini --role reviewer --mode plan with an `antigravity` stub on PATH never run; legacy antigravity.md seat still loads).
- Updated and passing: test-rsi-repair-lane.py, test-rsi-sweep.py, test-lane-hook-parity.py, test-agent-dispatch-contract.py, test-local-surface-scan.py, test-agent-ops-projection.py.
- run-ci-checks.sh --changed result: see REPORT.md (final line recorded there).
- Home Manager activationPackage eval: not applicable, the retired user path unit was defined by the NixOS module only; nix/home has no reference.

## Rollback Plan
git revert the commit; archived files are restored by moving them back from .agents/archive/20261105-antigravity-lane/. Re-enable the wake by restoring antigravity-auto-wake.nix and `mySystem.aiStack.antigravityAutoWake.enable = true`.

## Residual Risk
- After the rebuild, the already-installed user units aq-antigravity-auto-wake.path/.service and the drain-verify timer are removed by the switch; owner should confirm with systemctl --user list-units 'aq-antigravity*'.
- The IDE package (nix/modules/roles/antigravity.nix, pkgs.antigravity in base.nix, fast-lane overlay) is untouched; owner decides removal separately.
- Gemini RSI lane is read-only (plan mode): it diagnoses and proposes, it cannot apply repairs until worktree isolation exists for it.
- Left for follow-up (observability/enum only, no trigger): agent-ops-projection lane enum and inbox reader, aq-tui-dashboard inbox reader, lane-eligibility-registry antigravity entry, aq-role-route antigravity alias, switchboard antigravity-collective profile names, remote-lane-egress/aq-decide lane labels.

## Hint Feedback
No aq-hints used; rg over the repo was sufficient.
