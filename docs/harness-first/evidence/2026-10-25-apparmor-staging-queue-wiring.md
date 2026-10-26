# Evidence: AppArmor Fix Agent Staging Queue and Operator Approval Wiring

## Objective
Enable headless/service execution of `apparmor-fix-agent.py` to gracefully stage rule proposals into the Attention Queue (`ATTENTION.json`) without failing on read-only checkouts or DAC permissions, and wire `aq-approve` (`--commit-staged`) to retrieve and apply the alert's payload rules to `nix/modules/services/mcp-servers.nix` before committing.

## Workflow/Session IDs
- Session ID: `57a807e7-c3e6-4e8e-833b-ce38fb8d47cd`
- PRD: `PRD-HEALTH-SPIDER-AUTONOMOUS-HEALING.md`
- Branch: `feat/autonomous-healing-staging-queue`

## Delegation Decision
- Implementer: Antigravity orchestrator under worktree-bound branch with direct test verification.
- Reviewer: Codex independent parity check.

## Commands Executed
- `python3 scripts/testing/test-apparmor-fix-agent-generalization.py`
- `bash scripts/governance/tier0-validation-gate.sh --pre-commit`

## Validation Evidence
- Unit test suite passed 5/5 tests cleanly including `test_insert_rules_for_profile_inserts_before_deny_home`.
- Tier 0 pre-commit gate passed (71/71 checks passed, 0 failed, 206 QA phase 0 checks passed).
- Re-verified that dry-run and live alert inspection correctly retrieves proposed rules and inserts them before the `deny /home/** wx,` profile anchor.

## Rollback Plan
- Revert commit on `feat/autonomous-healing-staging-queue` or checkout prior commit `54978586`.
- Profile file `nix/modules/services/mcp-servers.nix` remains untouched until operator approval.

## Residual Risk
- Operator approval via `aq-approve` modifies `mcp-servers.nix` in the live checkout, which requires subsequent `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` to load into the kernel AppArmor subsystem.

## Hint Feedback
- `attention_queue.get_by_id` provides direct access to alert payload records without requiring separate state databases.
