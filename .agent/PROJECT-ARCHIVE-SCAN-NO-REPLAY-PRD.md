# Scan staged archival deletions without reviving tasks

## Evidence and scope

Worktree reconciliation found completed task files already moved from a watched
Antigravity inbox into preserved archives. The commit hook currently reconstructs
staged-deleted files from HEAD at their original path, scans references, then
removes them. A watcher can interpret that temporary creation as a fresh task.

Reuse the existing scanner and hook. Owned paths are pre-archive-scan.sh,
pre-archive-scan-hook.sh and test-pre-archive-no-materialization.py. No watcher,
inbox lifecycle, credentials, runtime service, archive policy or task ownership
changes. This fix is required to safely commit the existing archival evidence.

## Acceptance

Add an explicit mode permitting a missing file only when Git confirms the exact
path is staged for deletion. Keep ordinary missing/outside-repo checks intact.
Scan tracked inbound links and plain path mentions without writing, reviving or
removing the original target. Referenced deletion fails; unreferenced deletion
passes; unverified missing targets fail. Both hook outcomes must emit zero target
creation events. Prove these behaviors with a disposable Git fixture.

Root independently reviews the worker's source, runs syntax/fixture and stable
Tier-0, then commits a separate bounded fix with exact subject evidence. Do not
stage other slices. Subsequent archive commits must retain matching task bytes
and completion receipts and pass the scanner. No original task is redispatched.
