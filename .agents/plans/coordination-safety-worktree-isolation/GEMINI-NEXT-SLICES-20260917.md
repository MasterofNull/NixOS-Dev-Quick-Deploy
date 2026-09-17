# Gemini Advisory Pass: Coordination Safety Next Slices (CS-1 Hardening, CS-2 Parity, CS-3 Trunk Integration)

**Task ID**: `coordination-safety-next-slices-20260917`  
**Output Target**: `.agents/plans/coordination-safety-worktree-isolation/GEMINI-NEXT-SLICES-20260917.md`  
**Landed Anchor**: `e8a905e867bc03f1c8045519bc1917efca01a667` (CS-1 worktree-isolate delegation lanes)  
**Perspectives**: Systems Architect · Security Engineer · Implementation Engineer · SDET/QA  
**Verdict**: `PLAN_READY_WITH_FOLLOWUPS`  

---

## 1. Executive Summary & Verdict

CS-1 successfully eliminates root-level git index contention for `delegate-to-codex` and `delegate-to-local` by spawning isolated git worktrees (`.agents/delegation/worktrees/<task-id>`) on private branches (`delegate/<task-id>`). This is a massive step forward for multi-agent reliability.

However, source inspection of `scripts/ai/lib/worktree-isolation.sh` and the delegator scripts reveals two critical edge-case risks that must be corrected before rolling out CS-2 and CS-3:
1. **Silent Shared-Checkout Fallback Risk**: When `wt_create` returns 1 (e.g. branch collision, path conflict), the caller silently falls back to running in `REPO_ROOT`. This re-introduces the shared-index hazard without warning the caller or tagging the failure in `registry.jsonl`.
2. **Handback Evidence Loss Risk**: `wt_handback` generates `<task_id>.patch` via stdout redirect (`> "$patch_file"`). If disk space is exhausted, permissions fail, or uncommitted untracked binaries exceed git diff buffers, `patch_file` is either empty or partial, yet the worktree is left retained without atomic verification of patch integrity.

**Verdict**: `PLAN_READY_WITH_FOLLOWUPS`. The core architecture is sound and should proceed directly into the corrective slice (CS-1.1), followed by CS-2 and CS-3.

---

## 2. In-Depth Analysis of Landed CS-1 Implementation

### A. Systems Architecture & Correctness
* **Isolation Boundary**: Good. `wt_create` binds each dispatch to an immutable base reference `refs/delegate-base/<task-id>`, ensuring diffs are generated against the exact commit at dispatch time, not a moving `HEAD`.
* **Path Traversal & Validation**: `wt_validate` strictly checks that `wt_real` matches `$repo_real/.agents/delegation/worktrees/$task_id` and verifies porcelain worktree membership.
* **Flock Concurrency on Registry**: `wt_tag_registry` correctly uses Python `fcntl.flock(LOCK_EX)` on `registry.jsonl` to avoid corrupting concurrent append/status updates.

### B. Vulnerability & Risk Points (What Needs Immediate Hardening)

#### 1. The "Fail-Open" Fallback Trap
In `delegate-to-codex`:
```bash
if [[ -n "$wt_path" && -d "$wt_path" ]]; then
    # isolated mode
else
    # SILENT FALLBACK TO REPO_ROOT!
    run_dir="$REPO_ROOT"
fi
```
* **Risk**: If `wt_create` fails (e.g. leftover branch `delegate/<task-id>` from a previous crashed run, or dirty filesystem entry), the agent executes in `REPO_ROOT` without an explicit `--shared` or `--no-worktree` flag.
* **Correction**: Fail-closed by default. If worktree creation fails, the dispatch must abort with exit code 75 (`EX_TEMPFAIL`) and write `worktree_creation_failed` to `registry.jsonl`, UNLESS the user/orchestrator explicitly passed `--shared`.

#### 2. Handback Patch Integrity & Atomicity
In `wt_handback`:
```bash
git -C "$wt_path" diff --binary --full-index "$base" HEAD > "$patch_file" || return 1
```
* **Risk**: Non-atomic write. If the agent process is killed or interrupted during diff generation, a truncated patch remains on disk.
* **Correction**: Write to `.tmp` first, verify non-empty/valid header, then atomically `mv` to `$outputs_dir/${task_id}.patch`. Additionally, record `patch_sha256` in `registry.jsonl`.

---

## 3. Recommended Phased Execution Plan

### Slice CS-1.1: Worktree Hardening & Fail-Closed Guards (Smallest Corrective Slice)
* **Files**: `scripts/ai/lib/worktree-isolation.sh`, `scripts/ai/delegate-to-codex`, `scripts/ai/delegate-to-local`
* **Changes**:
  1. **Strict Stale Cleanup**: In `wt_create`, if branch `delegate/<task-id>` exists from an abandoned dispatch, prune and recreate cleanly if the previous worktree is detached.
  2. **Fail-Closed Default**: Disallow silent fallback to `REPO_ROOT`. Fallback requires `--shared`.
  3. **Atomic Patch Handback**: Write patch to `${patch_file}.tmp.$$` and rename atomically. Verify patch matches `git apply --check` against base.
  4. **Failure Tagging**: In `wt_tag_registry`, record error reason (`worktree_err`) if isolation or handback aborts.

### Slice CS-2: Isolation Parity Across All Lanes
* **Files**: `scripts/ai/delegate-to-gemini` (or Antigravity IDE lane wrapper), `scripts/ai/aq-drop-daemon`, `scripts/ai/aq-loop-fanout`
* **Changes**:
  1. Ensure every autonomous delegation runner uses `worktree-isolation.sh`.
  2. In `aq-drop-daemon`, dispatch tasks into dedicated worktrees under `.agents/delegation/worktrees/drop-<id>`.
  3. Parity documentation: Update `.agent/CODEX.md`, `CLAUDE.md`, `.agent/LOCAL-AGENT.md`, and `.agent/GEMINI.md` to reflect that implementers run in isolated worktrees and return patches.

### Slice CS-3: Enforced Trunk Integration (Serialize Main Commits)
* **Objective**: Prevent two concurrent orchestrator/agent lanes from racing on `git commit` / `git push` to `main`.
* **Design (Lightweight, No New Hub)**:
  1. Implement `wt_acquire_trunk_lease` and `wt_release_trunk_lease` in `worktree-isolation.sh` using a file lock on `.git/aq-trunk.lock`.
  2. Timeout: 30 seconds max lease duration.
  3. Orchestrator acquires trunk lease -> tests patch with `tier0-validation-gate.sh` -> commits to `main` -> releases lease.
  4. Avoids complex database locks or external consensus services.

---

## 4. Test Fixtures & QA Indicators

1. **Hermetic Test (`tests/test-worktree-isolation.sh`)**:
   - Test 1: Successful creation, branch naming, base ref recording, commit, and patch handback.
   - Test 2: Concurrent dispatches for tasks `task-a` and `task-b` modifying the same file; confirm both produce independent patches without index collision.
   - Test 3: Attempted creation with an invalid or colliding task ID; confirm fail-closed exit when `--shared` is absent.
2. **Dashboard Indicator**:
   - Expose active worktree count and active delegation branches in the AQ-OS Dashboard (`dashboard.html` / `assets/dashboard.js`).
   - Add status tile: `Active Worktrees: N` with branch names and task IDs.

---

## 5. Conclusion

Proceed with **CS-1.1 hardening** immediately to eliminate the fail-open fallback trap, then roll out **CS-2 parity** and **CS-3 trunk lease serialization**.
