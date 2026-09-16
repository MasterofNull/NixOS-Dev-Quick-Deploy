#!/usr/bin/env bash
# lib/worktree-isolation.sh — CS-1 coordination-safety: per-dispatch git
# worktree isolation for delegate-to-codex / delegate-to-local.
#
# Root cause fixed (.agents/plans/coordination-safety-worktree-isolation/DESIGN.md):
# both delegate scripts used to run the implementer agent directly in the
# SHARED checkout (REPO_ROOT), so it staged/committed into the same git index
# as the orchestrator and every other concurrent lane -> recurring
# concurrent-index contention (Rule 19 root-cause, observed 3x).
#
# Fix: every implementer dispatch runs in its own throwaway `git worktree` on
# a private branch (delegate/<task-id>), NEVER in the shared REPO_ROOT index.
# On completion the caller hands the result back as a patch file
# (.agents/delegation/outputs/<task-id>.patch) and a commit on the
# delegate/<task-id> branch, then tears the worktree down (Rule 12: the
# worktree directory is disposable scratch — the patch + branch are the
# preserved evidence, so `git worktree remove` here is the designed teardown
# primitive, not a content deletion). Only the orchestrator ever commits to
# main.
#
# Source this file from delegate-to-* scripts:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/worktree-isolation.sh"
#
# All functions are `set -e` safe (no bare failing command can kill the
# calling script) and degrade to "no worktree info" rather than aborting a
# delegation — worktree isolation is a safety improvement, not a new single
# point of failure.
#
# Functions:
#   wt_create       <repo_root> <task_id>
#       Creates .agents/delegation/worktrees/<task_id> on branch
#       delegate/<task_id> from HEAD. Echoes the worktree path and returns 0
#       on success; returns 1 (nothing echoed) on failure so the caller can
#       fall back to the shared checkout.
#   wt_handback     <repo_root> <worktree_path> <task_id> <outputs_dir>
#       Stages all changes in the worktree, writes the staged diff to
#       <outputs_dir>/<task_id>.patch (empty file if no changes), and commits
#       them to the worktree's own delegate/<task_id> branch (never main).
#   wt_teardown     <repo_root> <worktree_path>
#       Removes the worktree working directory via `git worktree remove`.
#       The delegate/<task_id> branch and the handed-back patch file are
#       preserved.
#   wt_tag_registry <registry_file> <task_id> <worktree_path> <branch> <patch_file>
#       Records worktree/branch/patch location on the matching registry.jsonl
#       entry (flock-guarded read-modify-write) so --status/--check reflect
#       where the isolated work landed. No-op if the entry isn't found yet.

# wt_create <repo_root> <task_id>
wt_create() {
    local repo_root="$1" task_id="$2"
    local wt_root="$repo_root/.agents/delegation/worktrees"
    local wt_path="$wt_root/$task_id"
    local branch="delegate/$task_id"
    mkdir -p "$wt_root" 2>/dev/null || true
    if git -C "$repo_root" worktree add -q -b "$branch" "$wt_path" HEAD >/dev/null 2>&1; then
        echo "$wt_path"
        return 0
    fi
    return 1
}

# wt_handback <repo_root> <worktree_path> <task_id> <outputs_dir>
wt_handback() {
    local repo_root="$1" wt_path="$2" task_id="$3" outputs_dir="$4"
    [[ -n "$wt_path" && -d "$wt_path" ]] || return 0
    mkdir -p "$outputs_dir" 2>/dev/null || true
    local patch_file="$outputs_dir/${task_id}.patch"
    git -C "$wt_path" add -A >/dev/null 2>&1 || true
    if git -C "$wt_path" diff --cached --quiet 2>/dev/null; then
        # No changes — still write an (empty) patch as evidence the dispatch
        # ran cleanly in isolation with nothing to hand back.
        : > "$patch_file" 2>/dev/null || true
        return 0
    fi
    git -C "$wt_path" diff --cached > "$patch_file" 2>/dev/null || true
    # Commit to the worktree's OWN delegate/<task-id> branch only — this is
    # never `main` and never the shared REPO_ROOT index (a separate git
    # worktree has its own index). The orchestrator reviews the patch/branch
    # and performs the single main commit.
    git -C "$wt_path" \
        -c user.email="delegate-bot@harness.local" \
        -c user.name="delegate-bot" \
        commit -q -m "delegate: ${task_id}" >/dev/null 2>&1 || true
    return 0
}

# wt_teardown <repo_root> <worktree_path>
wt_teardown() {
    local repo_root="$1" wt_path="$2"
    [[ -n "$wt_path" ]] || return 0
    git -C "$repo_root" worktree remove --force "$wt_path" >/dev/null 2>&1 || true
    git -C "$repo_root" worktree prune >/dev/null 2>&1 || true
}

# wt_tag_registry <registry_file> <task_id> <worktree_path> <branch> <patch_file>
wt_tag_registry() {
    local registry="$1" tid="$2" wt="$3" branch="$4" patch="$5"
    [[ -f "$registry" ]] || return 0
    python3 - "$registry" "$tid" "$wt" "$branch" "$patch" <<'PYEOF' 2>/dev/null || true
import fcntl, json, sys
rf, tid, wt, branch, patch = sys.argv[1:6]
with open(rf, "r+") as fh:
    fcntl.flock(fh, fcntl.LOCK_EX)
    try:
        fh.seek(0)
        raw = fh.read()
        lines_out = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("id") == tid:
                    e["worktree"] = wt
                    e["worktree_branch"] = branch
                    if patch:
                        e["patch_file"] = patch
                lines_out.append(json.dumps(e))
            except Exception:
                lines_out.append(line)
        fh.seek(0)
        fh.truncate()
        fh.write("\n".join(lines_out) + ("\n" if lines_out else ""))
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
PYEOF
}
