## Objective
Make aq-confine classify a cgroup OOM kill reliably. The check "allocating past MemoryMax is killed by the cgroup" failed intermittently in CI because the result was child-failed rc=-9 instead of oom-killed / 137.

## Workflow/Session IDs
Backlog item CONFINE-OOM-TEST-FLAKY. Branch fix/confine-oom-detection-race. Failing CI: GitHub job 126818672751 (passed 19:27Z, failed 19:41Z and on re-run with the same code). Main failed this suite once on 2026-10-30 (run 41039028094).

## Delegation Decision
Implementer: Claude Sonnet (Rule 17). Orchestrator: claude-opus. Date: 2026-11-04. The slice is bounded to confine.py and its test file.

## Commands Executed
- Read scripts/ai/lib/confine.py run path and _watch_oom.
- python3 scripts/testing/test-aq-confine.py
- python3 -c "import ast; ast.parse(open('scripts/ai/lib/confine.py').read())"

## Validation Evidence
Root cause: _watch_oom attaches to the scope's memory.events. If the kernel OOM-kills the child and systemd removes the scope before the watcher's last read, pread fails with an OSError and the watcher returns with oom_kill unset. The earlier fallback (F3, #663) only inferred an OOM when the watcher never attached, so an attached-but-too-late watcher was misreported as a plain SIGKILL.
Fix: the watcher now records scope-gone when its read fails. New helper _oom_by_inference infers oom-killed for an unissued SIGKILL when the watcher never attached or the scope vanished under it. An attached watcher that read oom_kill=0 from a live scope stays authoritative. Our own kills (timeout, egress, size) are never relabelled.
New test test_oom_detection_race_pure covers each case, including the failing-read watcher path. Full suite: 212 checks, 0 failed, 0 behavioral groups skipped (cgroups available locally).

## Rollback Plan
Revert the change to scripts/ai/lib/confine.py and scripts/testing/test-aq-confine.py. No data or config migration is involved.

## Residual Risk
A non-OOM SIGKILL of the launcher that also removes the scope before the watcher's final read is now labelled oom-killed. This is the same ambiguity the F3 fallback already accepted. The path stays fail-closed: the run is still a child-failed and nothing is promoted. The CI race itself cannot be reproduced on demand, so it is covered by the deterministic unit test only.

## Hint Feedback
No hints were consulted for this slice. The prior F3 commit message and comments in confine.py were the useful context.
