# Branch sediment triage — 2026-09-23

Coordinator: Claude Opus 4.8. Method: `git cherry main <branch>` (patch-equivalence) + ahead/behind.
Rule 12 (archive, never delete): archived branches were **renamed** to `archive/20260923/<name>` —
refs preserved, reversible (`git branch -m archive/20260923/<name> <name>`), nothing deleted. Local-only;
origin refs untouched. No branch with a unique (unmerged) commit was archived.

## Archived (59) — `unmerged=0`, every commit already patch-equivalent in main
These represent work that already landed on main (or points at main). Moved to `archive/20260923/`.
Full list captured in git; categories:
- **delegate/**: antigravity-aqos-system1-selfcompact, aq-tool (4017e5d9), ft-5, local-20260916, router-health (bdb7fa63)
- **factory/**: deployment-contract, lifecycle-authority, mcp-workflow-parity, receipt-destination-safety (030da8ac), remote-dispatch-payload-safety, slice-claim-v2, start-precondition-enforcement, upgrade-lossless (f35b2ea3)
- **feat/aqos-installer-p0-***: ai-fit-policy, execution-verifier, hardware-detector, module-catalog, mysystem-fieldset, resolver, schema, verifier-v2 (all landed)
- **feat/aqos-p1..p3**: guided-tui, p2a-proposal-schema, p2b-ai-propose, p2c-approve, p2d-parity, p3-rollback
- **feat/**: aqos-vm-dogfood, aqwiki-bodyhash-cache, ctx-freshness-automation, graft-bodyhash-cache, shallow-merge-guard, suspend-resume-contract-v1
- **fix/**: antigravity-health-real-lane, aqos-golden-ai-off-leak, local-benchmark-thinking-calibration
- **integrate/**: frontier-to-main, security-center-sc1-v3, sr1-suspend-resume; **merge/**: sr1-suspend-resume
- **local-agent/** (12): behavioral-verify-and-runner-leak, behavioral-verify-shlex, coach-antigaming-checks, coach-events-observability, deleted-def-guard, dogfood-target-scaffold, edit-file-kwarg-unblock, failure-observability, required-arg-grammar, session-start-machine-mode, training-loop-deadcode-cleanup, training-loop-service-dispatch-fix
- **local-inference/**: qwen35b-q5-resource-tuning, ram-tuning-zram-observability
- **other**: docs/readme-aqos-refresh, handoff/claude-to-codex-resumed, plan/aqos-installer-experience, remove-llm-from-base-system, system-update/cosmic-vscodium-quiet-automations

## Kept — has unmerged commits, needs a per-branch disposition (19)
NOT archived (would lose unique work). Each needs: **rebase+review** if genuinely forward, or
**archive-after-confirm** if its content already landed but the commit isn't patch-identical (extra file
touches). Quick read:
- **Genuinely forward / deferred — keep:** delegate/shared-toolchain (+1, ST-1 baseline default-off, real future activation); checkpoint/paused-work-20260917 (+3) & holding/factory-restore-paused-20260917 (+2) (paused snapshots).
- **Likely superseded, confirm then archive:** feat/aqos-security-center-v1 (+1), integrate/security-center-sc1 (+1), integrate/security-center-sc1-v2 (+1) — the credential-center feature files are byte-identical on main; the commits aren't patch-equivalent only because they also touch PRD/memory/dashboard differently. factory/execution-evidence-scope (+1) & -current (+1) — older evidence-scope variants superseded by the -lossless + preexec-hardening fix lineage. delegate/capability-manifest (+1), delegate/cs-4 (+1), factory/local-producer-timing-20260917 (+3), factory/reflection-metrics (+1) — landed-equivalent work with a stray non-identical commit.
- **Stale, low value — verify:** factory/slice-claim (+1, behind 95), feat/aq-agents-live (+1, behind 70), feat/herdr-discoverability (+1, behind 70), research/graft-parity (+2, behind 73), fix/p14s-gl9750-microsd (+1, behind 114), local-agent/coach-bulk-stamp (+1, behind 167).

## Skipped — in-flight (worktree-held), do not touch (9)
delegate/codex-20260921-150616, delegate/factory-idempotency, delegate/local-20260921-150628,
factory/evidence-scope-preexec-hardening (the active fix), factory/execution-evidence-scope-lossless,
factory/project-payload-manifest, factory/st1-installer-contract, factory/upgrade-lossless-current,
fix/agent-config-parity.

## Follow-up recommendation (not done here)
~18 `worktree-agent-*` branches are stale prior-session agent worktrees (behind 45–54). These are
harness-managed — clean via `git worktree prune` + `git worktree remove` once confirmed abandoned, NOT
via branch archive. Left untouched to avoid disrupting active agent worktree tracking.
