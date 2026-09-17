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
# Fix: every implementer dispatch runs in its own retained `git worktree` on
# a private branch (delegate/<task-id>), NEVER in the shared REPO_ROOT index.
# On completion the caller hands the result back as a patch file
# (.agents/delegation/outputs/<task-id>.patch) and a commit on the
# delegate/<task-id> branch. The worktree is retained on both success and
# failure for recovery; cleanup is separately authorized. Only the
# orchestrator ever commits to main.
#
# Source this file from delegate-to-* scripts:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/worktree-isolation.sh"
#
# All functions are `set -e` safe (no bare failing command can kill the
# calling script). Callers refuse an editing delegation when isolation fails.
#
# Functions:
#   wt_create       <repo_root> <task_id>
#       Creates .agents/delegation/worktrees/<task_id> on branch
#       delegate/<task_id> from HEAD. Echoes the worktree path and returns 0
#       on success; returns 1 (nothing echoed) on failure so the caller refuses
#       the editing dispatch and preserves existing evidence.
#   wt_handback     <repo_root> <worktree_path> <task_id> <outputs_dir>
#       Stages all changes in the worktree, commits them to its own
#       delegate/<task_id> branch (never main), then exports the full binary
#       diff from its immutable dispatch base.
#   wt_teardown     <repo_root> <worktree_path>
#       Deliberately does nothing: the worktree, private branch and handed-back
#       patch are retained until separately authorized cleanup.
#   wt_tag_registry <registry_file> <task_id> <worktree_path> <branch> <patch_file>
#       Records worktree/branch/patch location on the matching registry.jsonl
#       entry (flock-guarded read-modify-write) so --status/--check reflect
#       where the isolated work landed. No-op if the entry isn't found yet.

# wt_create <repo_root> <task_id>
wt_create() {
    local repo_root="$1" task_id="$2"
    [[ "$task_id" =~ ^[a-z0-9][a-z0-9-]{0,127}$ ]] || return 1
    repo_root="$(cd "$repo_root" 2>/dev/null && pwd -P)" || return 1
    [[ -d "$repo_root/.git" || -f "$repo_root/.git" ]] || return 1
    local base wt_root
    base="$(git -C "$repo_root" rev-parse --verify HEAD 2>/dev/null)" || return 1
    wt_root="$repo_root/.agents/delegation/worktrees"
    local wt_path="$wt_root/$task_id"
    local branch="delegate/$task_id"
    mkdir -p "$wt_root" 2>/dev/null || true
    [[ ! -e "$wt_path" ]] || return 1
    if git -C "$repo_root" worktree add -q -b "$branch" "$wt_path" "$base" >/dev/null 2>&1 &&
       git -C "$repo_root" update-ref "refs/delegate-base/$task_id" "$base" &&
       wt_validate "$repo_root" "$wt_path" "$task_id"; then
        echo "$wt_path"
        return 0
    fi
    return 1
}

# wt_handback <repo_root> <worktree_path> <task_id> <outputs_dir>
wt_handback() {
    local repo_root="$1" wt_path="$2" task_id="$3" outputs_dir="$4"
    wt_validate "$repo_root" "$wt_path" "$task_id" || return 1
    mkdir -p "$outputs_dir" || return 1
    local patch_file="$outputs_dir/${task_id}.patch"
    git -C "$wt_path" add -A || return 1
    local base; base="$(git -C "$repo_root" rev-parse "refs/delegate-base/$task_id")" || return 1
    git -C "$wt_path" merge-base --is-ancestor "$base" HEAD || return 1
    if ! git -C "$wt_path" diff --cached --quiet; then
        git -C "$wt_path" \
            -c user.email="delegate-bot@harness.local" \
            -c user.name="delegate-bot" \
            commit -q -m "delegate: ${task_id}" || return 1
    fi
    git -C "$wt_path" diff --binary --full-index "$base" HEAD > "$patch_file" || return 1
    return 0
}

wt_validate() {
    local repo_root="$1" wt_path="$2" task_id="$3" branch="delegate/$3"
    [[ "$task_id" =~ ^[a-z0-9][a-z0-9-]{0,127}$ && -n "$wt_path" ]] || return 1
    local repo_real wt_real
    repo_real="$(cd "$repo_root" 2>/dev/null && pwd -P)" || return 1
    wt_real="$(cd "$wt_path" 2>/dev/null && pwd -P)" || return 1
    [[ "$wt_real" == "$repo_real/.agents/delegation/worktrees/$task_id" && "$wt_real" != "$repo_real" ]] || return 1
    git -C "$repo_real" worktree list --porcelain | grep -Fx "worktree $wt_real" >/dev/null || return 1
    [[ "$(git -C "$wt_real" branch --show-current 2>/dev/null)" == "$branch" ]] || return 1
}

# wt_teardown <repo_root> <worktree_path>
wt_teardown() {
    : # Retention is deliberate; cleanup needs separate authority.
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
