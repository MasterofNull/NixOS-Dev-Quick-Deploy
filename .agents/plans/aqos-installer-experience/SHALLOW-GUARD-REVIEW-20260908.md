# Independent Review: Shallow-Clone Merge Guard

- Branch: `feat/shallow-merge-guard` @ `f96b8ac3`
- Worktree: `/tmp/shallow-guard`
- Reviewer role: non-author, adversarial, read-only (verdict file only write)
- Date: 2026-09-08

## Scope

`.githooks/pre-commit` (edited), `.githooks/pre-merge-commit` (new),
`scripts/governance/check-mergeable.sh` (new),
`scripts/governance/tier0.d/check-shallow-repo.sh` (new),
`scripts/testing/test-check-mergeable.sh` (new).

## 1. Normal commits unaffected (critical) — PASS

`git diff main...HEAD -- .githooks/pre-commit` shows **only** the added block
(7 new lines after the shebang/`set -euo pipefail`, nothing removed or
reordered elsewhere in the file):

```
+# Shallow-merge guard: a merge commit created on a shallow clone can be a garbage
+# disjoint merge. Block it (the --no-commit merge flow reaches pre-commit at commit time).
+if [ -f "$(git rev-parse --git-dir)/MERGE_HEAD" ] && [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
+    echo "pre-commit: refusing to create a merge commit on a SHALLOW clone — run 'git fetch --unshallow' first" >&2
+    exit 1
+fi
+
```
(`.githooks/pre-commit:4-9`)

Condition logic: short-circuit `&&` means `git rev-parse --is-shallow-repository`
is never even invoked unless `MERGE_HEAD` already exists — the common case
(no in-progress merge) exits the test at the first clause. `set -e` cannot
turn a failure of that shallow-check into a hard abort either, because it
sits inside an `if` condition (a documented `set -e` exception), so even an
old git lacking `--is-shallow-repository` would silently fail the condition
and fall through rather than aborting the commit.

Live-verified all four quadrants, not just read the code:
1. Normal commit, non-shallow repo, no `MERGE_HEAD` → hook runs to completion
   normally (secret scan → lint → structure → migration/focused-CI checks),
   **exit 0**.
2. Faked `MERGE_HEAD` present, but repo **not** shallow → guard block does
   NOT fire, hook falls through to the rest of the checks, **exit 0**.
3. Real shallow clone (`git clone --depth 1` of the worktree), **no**
   `MERGE_HEAD` → hook runs to completion, **exit 0** (shallow alone never
   blocks a normal commit).
4. Real shallow clone **with** faked `MERGE_HEAD` → guard fires with the
   exact expected message, **exit 1**.

No false-positive path found. Verdict: **PASS**.

## 2. Guard actually works — PASS

- `check-mergeable.sh:21-26` — fails (exit 1) when
  `is-shallow-repository` is `true`, prints the `git fetch --unshallow`
  remediation at line 24.
- `check-mergeable.sh:28-34` — with a branch arg, if `git merge-base HEAD
  <branch>` is empty, fails (exit 1) with "no common ancestor" and the same
  remediation line (`:32`).
- `pre-merge-commit:16-19` — invokes the guard (`"${GUARD}"`) and aborts the
  merge (exit 1) on failure; `:11-14` WARN+skip (exit 0) only if the guard
  script itself is missing from the tree (an integrity edge case, not a
  shallow-clone bypass — see note below).

Live-verified against a genuinely shallow clone (`git clone --depth 1` from
the reviewed worktree):
- `check-mergeable.sh` (no arg): FAIL, exit 1, remediation printed.
- `check-mergeable.sh main` (branch arg, still shallow): FAIL, exit 1 —
  correctly hits the shallow check before ever reaching merge-base.
- `.githooks/pre-merge-commit` directly: FAIL, exit 1, "aborting auto-merge".
- Faked `MERGE_HEAD` + `.githooks/pre-commit` on the shallow clone: FAIL,
  exit 1, matching message.

Also live-verified the merge-base/unrelated-histories branch independently,
in a scratch non-shallow repo with two orphan (unrelated) branches:
`check-mergeable.sh unrelated` → FAIL, exit 1, "no common ancestor
(unrelated histories) ... refusing merge".

Minor note (not a defect, informational): `pre-merge-commit` calls the
guard with no branch argument, so it only ever exercises the shallow-check
path, not the merge-base/unrelated-histories path — this is fine because
the shallow check alone unconditionally blocks every shallow merge (the
actual risk this guard exists to prevent), and git's own merge machinery
already refuses genuinely-unrelated-history merges on a healthy non-shallow
clone before this hook is reached. The only real gap is that a tree missing
`scripts/governance/check-mergeable.sh` entirely silently skips the merge
guard (`pre-merge-commit:11-14`, fail-open on missing artifact) — this
requires the guard script itself to have been deleted from the repo, not a
shallow-clone-specific bypass, so it does not undermine the guard's stated
purpose. Verdict: **PASS**.

## 3. Shell safety — PASS

- `bash -n` clean on all 5 files (ran together, zero errors).
- `set -euo pipefail` present: `pre-commit:2`, `pre-merge-commit:6`,
  `check-mergeable.sh:14`, `check-shallow-repo.sh:11`,
  `test-check-mergeable.sh:10`.
- Path resolution via `git rev-parse --show-toplevel`:
  `check-mergeable.sh:16`, `pre-merge-commit:8`, `check-shallow-repo.sh:13`
  — all correct; confirmed the git-dir resolution also works correctly
  under the worktree (`git rev-parse --git-dir` from the worktree resolved
  to `.git/worktrees/shallow-guard`, the worktree-local `MERGE_HEAD`
  location, not the shared main `.git`).
- All variable/command-substitution expansions are quoted
  (`"${GUARD}"`, `"${BRANCH}"`, `"$(git rev-parse --git-dir)/MERGE_HEAD"`,
  `"${merge_base}"`); no unquoted expansions found. `BRANCH` is only ever
  passed as a quoted argument to `git merge-base`, never eval'd or used in
  a glob/command context — no injection surface.

Verdict: **PASS**.

## 4. Tier0 check is non-blocking — PASS

- `check-shallow-repo.sh:16-19` — WARNs and **exit 0** when shallow.
- `check-shallow-repo.sh:21` — PASS, **exit 0** otherwise.
- No path in the file exits non-zero. Live-confirmed both branches: WARN+0
  on a real shallow clone, PASS+0 on this non-shallow repo.
- Header comment (`:1-10`) explicitly frames this as an environmental/
  freshness-class condition per Rule 19, matching the project's tier0.d
  WARN-don't-block convention; the actual hard block correctly lives only
  in the merge-specific hooks (`pre-merge-commit`, `pre-commit`'s
  `MERGE_HEAD` guard), not in tier0.

Verdict: **PASS**.

## 5. Test validity — PASS

`bash scripts/testing/test-check-mergeable.sh` → `PASS test-check-mergeable`.

Covers: `bash -n` on the guard, no-arg OK path on this (non-shallow) repo,
branch-arg (`main`) merge-base-present path, and static assertions that the
guard source contains the shallow-check, merge-base computation, the
`unshallow` remediation string, and the "unrelated histories" wording. The
test file's own header (`:1-9`) correctly acknowledges it can't force this
repo into a shallow state and documents why the FAIL paths are asserted via
grep instead.

I supplemented this during review with live execution of the actual FAIL
paths (real shallow clone, real orphan-branch unrelated-history repo) —
both behaved exactly as designed, so the logic the test only greps for is
also confirmed to work at runtime, not just present in source.

Verdict: **PASS**.

## Commands run

```
git diff main...HEAD -- .githooks/pre-commit
bash -n .githooks/pre-commit .githooks/pre-merge-commit \
  scripts/governance/check-mergeable.sh scripts/governance/tier0.d/check-shallow-repo.sh \
  scripts/testing/test-check-mergeable.sh
bash scripts/testing/test-check-mergeable.sh
scripts/governance/tier0.d/check-shallow-repo.sh
# plus: live simulation of MERGE_HEAD present/absent x shallow/non-shallow,
# a real --depth 1 clone, and a scratch repo with unrelated orphan branches.
```

## OVERALL: PASS
