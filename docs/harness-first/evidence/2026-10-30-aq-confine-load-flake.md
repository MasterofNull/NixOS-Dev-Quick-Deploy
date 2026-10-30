# aq-confine acceptance (0.10.66) load flake

## Objective
Find and fix the intermittent tier0/aq-qa 0.10.66 failure under host load (F3); improve failure diagnosability.

## Workflow/Session IDs
Delegated bounded slice, branch fix/aq-confine-load-flake (worktree .agents/delegation/worktrees/aq-confine-flake). No commit.

## Delegation Decision
Implemented directly by the delegated sub-agent (Sonnet tier) on an assigned slice; no further delegation.

## Commands Executed
- 6 busy-loop python processes plus pre-existing llama load (load avg ~10); AQ_CONFINE_REQUIRE=1 python3 scripts/testing/test-aq-confine.py x5 (before), x8 (after), 1 lighter run.
- Logs: .agents/delegation/outputs/aq-confine-flake/{before,after}-N.log

## Validation Evidence
Before (loaded): 4/5 pass, 1/5 fail (before-2.log): "FAIL: allocating past MemoryMax (rlimit-as removed) is killed by the cgroup, never completes  child-failed rc=-9". All other 203 checks passed.
Root cause: real product race in scripts/ai/lib/confine.py. The OOM is detected by _watch_oom, which must open the scope memory.events within a poll window; under load the scope is created and OOM-reaped before the thread attaches (or the thread is starved), so oom_kill is never observed and the SIGKILL (rc -9) was classified "killed" instead of "oom-killed". The test assertion (reason == oom-killed) was correct.
Fix: record whether the watcher attached; if it never attached, the run is in an OOMPolicy=kill scope, none of our own kill paths (timeout, egress, size) fired, and rc is SIGKILL, classify as oom-killed. Still fail-closed (child-failed, not promoted) either way. Test unchanged (no weakening).
After (loaded): 8/8 pass, each "SUMMARY: 204 checks ran, 0 failed". Lighter/standalone run: see report (204 checks, 0 failed).
Diagnosability: phase0.py 0.10.66 failure detail now lists rc and all FAIL assertion names (70 chars each, bounded 240) instead of the last 3 lines.

## Rollback Plan
git checkout -- scripts/ai/lib/confine.py scripts/testing/harness_qa/phases/phase0.py and delete this evidence file (archive per Rule 12).

## Residual Risk
Flake reproduced 1/5 before, so 8/8 after is supportive, not proof. Inference can mislabel a sandbox-internal self SIGKILL as oom-killed only when the watcher missed attach; outcome (child-failed, unpromoted) is identical.

## Hint Feedback
No aq-hints used. A tier0-level re-run of 0.10.66 under load is still advisable after merge.
