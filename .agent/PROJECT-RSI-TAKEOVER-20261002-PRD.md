# RSI backlog takeover — 2026-10-02

Owner: hyperd. Orchestrator/reviewer: Codex. Authority: owner request to finish Claude's RSI backlog with economical implementers.

## Objective and scope
Recover the current baseline, repair evidenced open defects in atomic slices, and establish what remains before resuming system development. Reuse the RSI steward and tiered-update freezes; this recovery does not expand those feature contracts. Historical triage counts and stale RESUME entries are not current failure evidence.

## Execution
1. Recover commit history, current backlog, delegation state, and live health. Preserve preexisting flake.lock edits and other agents' artifacts.
2. Diagnose and delegate the smallest confirmed repair: ralph-wiggum repository cwd configuration. Existing REPO_ROOT is preferred over new configuration or dependencies.
3. Diagnose OSI boot regression checks and delegation isolation against recent fixes; repair only reproduced defects, one commit each.
4. Reconcile additional open rows using fresh evidence; prioritize runtime, security, continuity and validation blockers. Record scope and acceptance before each additional slice.
5. Validate targeted regressions and actual integration paths, independent review, then tier0 through its serializing wrapper. Record activation evidence or dated deferrals.
6. Update backlog, workaround register, memory/RAG, activation audit and handoff, with truthful atomic commit evidence.

## Acceptance
Slice R1 owns server.py optimizer cwd calls, the ai-ralph-wiggum unit environment in mcp-servers.nix, and a focused handler regression test. Set REPO_ROOT from existing mcp.repoPath; honor it at both subprocess calls without a user-specific fallback. Test both calls using a temporary repository and missing configuration. Live activation requires the declarative unit environment before judging runtime readiness.

Slice R2 owns the boot aggregate and dedicated OSI probe tests: replace obsolete pending-token and running-field assertions with the producer's pending-in-progress and completed no-results/failure contracts; run both tests, preserving microSD and later checks. No health-spider behavior change.

R1 live-validation follow-up: authenticated sync reaches the handler but aq-optimizer's env-python3 shebang fails because Ralph's systemd PATH lacks Python. Declare the existing ralphPython runtime in the unit path and validate the evaluated service PATH plus an authenticated sync after activation. This operational repair does not authorize new local-inference transport adoption or action execution.

Slice R3 owns shared-state ownership in mcp-servers.nix and a focused regression. Preserve the core shared-parent 0711 root:root contract by excluding it from the user-owned bootstrap loop; provision the working-memory agent child as 0750 ai-hybrid:ai-stack using existing configured variables. The successful owner switch on 2026-10-02 restored parent traversal but left this child absent, and working-memory save still returned HTTP500. Acceptance requires declaration regression, Nix evaluation, independent review and a real save/read round trip after activation. Prior hyperd:nogroup ownership remains unattributed; the competing bootstrap producer is separately proven.

Each closure has producer-level evidence and a regression check where appropriate. Current system health is measured, not inferred from zero failed units. No clean-slate declaration while unresolved defects, unknown validation or activation gaps remain. Preserve owner-only approval identities and feature activation boundaries; owner verification is never impersonated.

## Risks and rollback
Shared checkout: assign exclusive source ownership and review scoped diffs. No destructive resets/deletions or unrelated lock changes. Revert a defective slice with a forward corrective commit after diagnosis. Runtime changes require their Nix declaration and live validation. No automatic-update activation under this repair plan.

## Initial evidence and continuity
HEAD at recovery: 6c341d28; Oct1 handoff predates several completed repairs. Live systemctl reports zero failed services. QA phase0 initially blocked by sandbox evidence-lock permissions and was rerun with escalation. Working-memory save returned HTTP500; token usage for the current Codex session is unknown. These are findings to register and diagnose, not successful memory/QA claims.
