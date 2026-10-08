# FT-4 brownfield retrofit / FT-5 factory-start evidence — 2026-10-08

## Objective
Verify the existing FT-4 corrective and FT-5 start prerequisite; complete missing canonical prerequisite instructions and parity documentation without changing passing implementation.

## Workflow/Session IDs
Bridge worktree: `codex-20261008-134912-lcapoy`.
Plan: `.agents/plans/factory-gate-templates`, items ft-4 and ft-5.
Headless delegate: no session-start, tier0, commit, or live-state writes.

## Delegation Decision
Codex bounded implementer; existing code already satisfies the named fixture tests. No additional implementation or duplicate tests needed. Independent review and integration belong to the orchestrator. This artifact does not grant owner acceptance.

## Commands Executed
From the isolated worktree:

- `python3 scripts/testing/test-factory-gate-retrofit.py`
- `python3 scripts/testing/test-factory-gate-install.py`
- `python3 scripts/testing/test-factory-start-enforcement.py`
- `python3 scripts/testing/test-factory-gate-readiness.py`
- `python3 scripts/testing/test-mcp-workflow-parity.py`
- `python3 scripts/governance/canon-compile.py --write`
- `python3 scripts/governance/canon-compile.py --check`
- `./scripts/ai/aq-pm-tracker /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/worktrees/codex-20261008-134912-lcapoy/.agents/plans/factory-gate-templates`

One command used the nonexistent filename `scripts/testing/test-factory-gate-start-enforcement.py` (exit 2); corrected to `scripts/testing/test-factory-start-enforcement.py`, which passed. This was a command-name error, not a failing test. A shell compression hook initially rejected a direct git inspection; repeating the explicit worktree git command through `lean-ctx` succeeded.

## Validation Evidence
All commands below exited 0. These are fixture results with temporary repositories, fake build/scan tools, and fake transport; they do not establish real toolchain/coordinator E2E activation.

Retrofit:
```text
AQ_QA_FACTORY_RETROFIT_FIXTURE={"preview_read_only":true,"confirmation_enforced":true,"originals_preserved":true,"hooks_composed":true,"layout_preserved":true,"collaboration_preserved":true,"unsafe_state_refused":true,"layout_confirmation_bound":true,"unsafe_receipt_refused":true,"existing_receipt_preserved":true,"upgrade_idempotent_preserves_user_files":true,"upgrade_preserves_local_gate_configuration":true,"overwrite_backups_lossless":true,"legacy_receipt_migrates_losslessly":true,"foreign_hookspath_still_refused":true,"upgrade_refuses_unsafe_receipt":true,"upgrade_succeeds_with_ordinary_receipt":true}
```
Install:
```text
AQ_QA_FACTORY_GATE_FIXTURE={"hooks_block_bad_commit":true,"tracker_discovered":true,"collision_preserved":true,"unconfigured_blocked":true,"collaboration_seeded":true,"layout_enforced":true,"agent_notice_safe":true}
```
Start enforcement:
```text
AQ_QA_FACTORY_START_ENFORCEMENT={"brownfield_blocked_before_write":true,"force_does_not_bypass":true,"ready_brownfield_progresses":true,"missing_runner_blocks_dispatch":true,"blocked_runner_blocks_dispatch":true,"ready_runner_dispatches":true}
```
Readiness:
```text
AQ_QA_FACTORY_READINESS_FIXTURE={"positive_ready":true,"case1_missing_installation":true,"case1_disabled_hooks":true,"case1_missing_execution_evidence":true,"case1_stale_execution_evidence":true,"case1_unconfigured_checks_fail_closed":true,"bad_repository_organization":true,"invalid_tracker":true,"absent_lane_informational_only":true,"target_side_gate_runner_preflight_parity":true,"checks_live_reflect_current_repo":true,"upgrade_refreshes_gate_runner_and_recovers_evidence":true,"external_scope_cannot_mint_evidence":true,"missing_canonical_inventory_blocked":true,"symlinked_canonical_check_blocked":true,"symlinked_manifest_blocked":true,"failed_execution_evidence_explicit_and_ignored":true,"receipt_provenance_blocks_deleted_check_and_manifest_entry":true,"injected_check_refused_before_execution":true,"malformed_failed_evidence_is_missing":true,"unsafe_git_info_refused_before_retrofit":true,"toctou_execution_uses_verified_snapshot":true,"umask_robust_mode_provenance":true,"special_and_group_write_mode_rejected":true,"boundary_mismatch_source_refused_before_execution":true,"boundary_snapshot_first_hook_proof":true}
```
MCP parity:
```text
AQ_QA_MCP_WORKFLOW_PARITY=pass
```
Canonical generation:
```text
wrote AGENTS.md [behavioral-rules]
wrote CLAUDE.md [behavioral-rules]
wrote .agent/CODEX.md [behavioral-rules]
wrote .agent/GEMINI.md [behavioral-rules]
wrote .agent/LOCAL-AGENT.md [behavioral-rules]
wrote .agent/WORKFLOW-CANON.md [behavioral-rules]
OK: compiled (6 file(s) updated)
```
Canonical check:
```text
OK: no canon drift
```
Tracker projection excerpts (unchanged owner acceptance, no hand-edited status):
```text
# Factory Gate/Check Template Reproduction — greenfield + brownfield injection  —  46%  (3/7 shipped)
## brownfield retrofit
  [IN-PROGRESS]   0%  brownfield retrofit (non-destructive)
## factory-start precondition + parity
  [IN-PROGRESS]   0%  factory-start precondition + parity + docs
```

## Rollback Plan
The staged change only adds canonical instructions and documentation/editorial evidence. If revision is needed, amend the canonical source and regenerate instructions. No runtime deployment or target retrofit was performed by this slice. Existing retrofit backups remain owned by their target repositories.

## Residual Risk
Independent review, orchestrator tier0, real target toolchains, live coordinator dispatch, and dashboard/health-spider/alert activation remain pending. Dated six-dimension deferral is recorded in `.agent/ACTIVATION-AUDIT.md`. FT-4 fixture evidence covers no-clobber, current-digest confirmation, lossless backup creation, local configuration retention, and idempotent re-run. FT-5 fixture evidence covers blocking before state creation/dispatch and no force bypass. Preflight validates execution evidence; it does not execute checks or install tools. No security/containment implementation changes were made.

## Hint Feedback
Task-provided handoff, corrective, advisory, acceptance, and tracker documents correctly pointed to existing fixture coverage. The remaining gap was canonical factory-start instruction parity. Headless scope excluded broad memory hydration; no MemoryBroker/AIDB closeout or live activation is claimed.
