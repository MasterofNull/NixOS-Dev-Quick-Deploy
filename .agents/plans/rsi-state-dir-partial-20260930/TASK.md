ROLE: implementer, bounded slice (isolated worktree; hand back a patch). No service restarts, no /var/lib writes, no commit to the shared checkout.
SOURCE: your own binding review .agents/plans/rsi-pr353-binding-review-20260930/codex.md findings 2 and 3 (REQUEST_CHANGES).
GOAL: stop granting the ai-prsi-rsi-dispatch unit write access to the whole repo `.agent/collaboration` directory, and fix the rsi_lifecycle writability probe.
DESIGN (adjust if you find a smaller correct one, and say why):
- Dedicated mutable RSI state dir for the service (e.g. /var/lib/nixos-ai-stack/optimizer/prsi/rsi-state, already under the unit's writable mutableOptimizerDir). Make its location configurable by env (e.g. AQ_RSI_RUNTIME_DIR) used by scripts/ai/lib/rsi_lifecycle.py (_RUNTIME) and by prsi-orchestrator's _RSI_INCIDENTS reader; interactive/default behavior unchanged (repo .agent/collaboration) so existing agents keep working.
- For the delegation chain's a2a event appends, set A2A_EVENT_LOG for the unit to a file in the service state dir (scripts/ai/lib/event_log.py already supports it and isolates the fallback).
- Keep the two register file grants (issues-backlog.md, WORKAROUND-REGISTER.md) only if still needed; fix rsi_lifecycle.check() (~line 61) to probe the actual operation (append to the specific file / create in the runtime dir) instead of creating a temp file in .agent/memory.
- Update nix/modules/roles/ai-stack.nix (ai-prsi-rsi-dispatch Environment + ReadWritePaths) and scripts/testing/test-prsi-rsi-intake.py pins accordingly (it currently asserts the collaboration grant — replace with the new contract and assert `.agent/collaboration` is NOT writable).
- Consider ledger visibility: interactive agents read the repo ledger via aq-rsi-pending / aq-resume; make sure pending/sign-off still works for the service's ledger (e.g. aq-rsi-pending honours AQ_RSI_RUNTIME_DIR or reads both) — document the choice.
TESTS: focused tests for runtime-dir override, probe behavior, and the nix pin; run existing test-prsi-rsi-intake.py, test-rsi-repair-lane.py, test-aq-rsi-pending.py, test-rsi-lifecycle.py.
REPORT: diff summary, test output, migration note (how existing repo-ledger incidents reach the service ledger).

BASELINE: the lane switch (rsi.repair_lane, test-rsi-repair-lane.py) is now committed at 3a575757 on HEAD; your worktree includes it. Previous attempt codex-20260930-164233-0grbih stopped correctly on the baseline mismatch.
