# Track S S0-A — Commit-Train Release Authorization AM3

Status: **PREPARED_ONLY — INDEPENDENT REVIEW AND OWNER ACTIVATION REQUIRED**
Prepared: 2026-07-29
Exact HEAD: `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`
Release operator: `codex-orchestrator`

## Supersession and second stop record

The parent release authorization
`b6c2cfc3d7f07f740682994b5622c6766e94b4dc20d1d01a35daa58741f19315`,
AM1 `343235e91c52ef4a6f59c770a3b9ec9238847ff703551084305924f67a99a438`,
and AM2 `d1c455764384c9fc4f4ffa37f9bff7b88165c3e69422d2d9aa985151a311e876`
are consumed and non-replayable.

AM2 passed its complete focused contract and reproduced the authorized
staged-isolated Tier-0 differential exactly: 25 checks, 24 passing, only gate 15
failing, only QA row `0.10.40`, and normalized focused tracker digest
`a54419d605f6fcc43233f6a081054a86659f0ffc0e36113e99efebef98e421c4`.
The subsequent normal `git commit` hook stopped before commit because focused CI
read the unrelated untracked
`.agent/PROJECT-AGENT-MODEL-CONFIGURATION-PARITY-PRD.md` from the primary dirty
worktree and rejected its frontmatter. No commit was created. HEAD, every S0-A
candidate byte, and every unrelated working-tree byte remain unchanged; the
primary index was restored to empty.

This is recorded as HIGH
`pre-commit-focused-ci-leaks-unstaged-subjects` in
`.agent/memory/issues-backlog.md`. Correcting that unrelated PRD is a separate
slice and is neither authorized nor required here.

## Purpose and isolation invariant

AM3 changes no accepted candidate byte and grants no hook or validation waiver.
It supplies the worktree boundary missing from the current hook: the unchanged
normal hook and normal `git commit` must run from a complete temporary projection
whose bytes equal the real candidate index, while the real Git directory, real
index, intended branch, and ordinary hooks remain authoritative.

The projection is not a second repository, branch, index, or commit authority.
It is an ephemeral worktree view built from exact HEAD and overlaid only with the
hash-bound release paths. The direct-hook dry run and ordinary commit must use
two separately constructed projections. A hook-mutated projection is never
reused. Before either hook invocation, an index-derived, NUL-safe manifest and a
Git worktree-versus-index comparison must independently prove the complete
projected tree equals the real index.

## Exact release inventory

The 15 path/hash rows frozen in
`S0-A-RELEASE-AUTHORIZATION-20260729.md` remain exact and unchanged. The release
commit may contain exactly:

1. those 15 frozen subject paths;
2. `S0-A-RELEASE-AUTHORIZATION-20260729.md` at
   `b6c2cfc3d7f07f740682994b5622c6766e94b4dc20d1d01a35daa58741f19315`;
3. `S0-A-RELEASE-AUTHORIZATION-AM1-20260729.md` at
   `343235e91c52ef4a6f59c770a3b9ec9238847ff703551084305924f67a99a438`;
4. `S0-A-RELEASE-AUTHORIZATION-AM2-20260729.md` at
   `d1c455764384c9fc4f4ffa37f9bff7b88165c3e69422d2d9aa985151a311e876`;
5. this AM3 authorization at its independently reviewed and owner-activated
   SHA-256.

Total ceiling: **19 paths**. Every earlier subject hash remains mandatory.

## Activation prerequisites

This document grants nothing until an independent eligible reviewer returns an
exact-hash `PASS` and the owner activates that hash, exact HEAD, release operator,
and a UTC window no longer than 24 hours.

Before activation or staging, the reviewer must verify that the proposed Git
invocation uses:

- the repository's existing `.git` directory and real index;
- an absolute `GIT_WORK_TREE` naming only the exact temporary projection;
- the existing absolute `core.hooksPath`;
- ordinary `git commit`, without alternate index, alternate object directory,
  detached branch, manual reference mutation, or commit-plumbing commands.

The invocation must reject inherited Git redirection or configuration variables,
including `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`,
`GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_COMMON_DIR`, `GIT_NAMESPACE`,
`GIT_CONFIG_COUNT`, every `GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*`, and
`GIT_CONFIG_SYSTEM`/`GIT_CONFIG_GLOBAL`. No skip or suppression variable may be
present.

## Authorized release procedure

After activation, the release operator must:

1. reverify exact HEAD, current branch, all 15 subject hashes, all three
   predecessor authorization hashes, this activated hash, an empty primary
   index, and absence of an overlapping writer;
2. capture a NUL-safe primary-worktree manifest for every unrelated changed,
   deleted, or untracked path, excluding only the 19 release paths. Each record
   must bind repository-relative path, presence/absence, filesystem type,
   permission/executable mode, and regular-file digest or symlink target.
   Inventory additions/removals and path-type changes are semantic drift;
3. stage exactly the 19-path ceiling in the real index without changing any
   working-tree byte;
4. retain all AM2 checks: scoped `git diff --cached --check`, JSON parse, Python
   compilation using `/tmp` bytecode, capability-intake focused tests, `list`,
   `audit`, documentation-link validation, exact staged inventory, exact
   staged-isolated Tier-0 structure, and exact normalized tracker-test digest;
5. derive an expected NUL-safe complete-tree manifest from the real index. It
   must include every repository-relative path, every parent directory, Git
   mode/executable bit, regular-file Git blob identity, and symlink target/blob
   identity. Create a fresh **dry-run projection** under `/tmp`, populate it from
   exact HEAD, and overlay exactly the 19 release paths from the hash-verified
   primary working tree. Generate the corresponding filesystem manifest over
   every projection entry, including ignored and untracked entries, and require
   exact equality with the index-derived manifest. Any extra directory, file,
   symlink, socket, device, or other entry is a stop;
6. reject every inherited Git locator/configuration variable listed above. Set
   only `GIT_DIR` to the repository's existing `.git` directory and
   `GIT_WORK_TREE` to the absolute dry-run projection; from the projection root,
   prove:
   - `git rev-parse HEAD` is the frozen HEAD;
   - `git symbolic-ref HEAD` is the intended branch;
   - `git rev-parse --git-path index` is the exact primary `.git/index`;
   - `git rev-parse --git-path objects` is the exact primary `.git/objects`;
   - `git rev-parse --git-common-dir` is the exact primary `.git`;
   - `git config --path --get core.hooksPath` is the existing absolute
     repository `.githooks`;
   - `git diff --cached --name-only` is exactly the 19-path ceiling;
   - `git diff --quiet` reports no projection-versus-index byte difference;
7. invoke the existing `.githooks/pre-commit` directly once from the projection
   as an exact dry run and require exit 0. Discard that projection from further
   release use regardless of result;
8. create a second fresh **commit projection** from exact HEAD plus the same 19
   hash-verified paths. Recompute and require the complete index-derived versus
   filesystem manifest equality, absence of every extra/ignored/untracked
   entry, all exact Git-path/config checks in step 6, and `git diff --quiet`.
   Then invoke ordinary `git commit` from the commit projection with the
   evidence-rich message. The normal hook must run again and return 0;
9. verify the intended branch advanced by exactly one commit, the commit tree
   contains exactly the 19-path delta, the real index equals new HEAD, and the
   primary working tree exactly matches the pre-release NUL-safe manifest for
   every unrelated path, including inventory, presence, type, mode, digest, and
   symlink target.

The commit must truthfully report the AM2 Tier-0 `RC=1` differential and must not
claim Tier-0 passed.

## Absolute stop conditions

Stop on HEAD/hash/branch/content drift, a twentieth path, overlap, projection
creation failure, projection/index difference, alternate-index use, any
additional or changed Tier-0/QA/focused-test failure, focused validation
failure, direct-hook failure, commit-hook failure, unexpected branch/index
movement, or unrelated-byte drift.

Any hook failure consumes AM3. Restore the primary index to empty without
changing working-tree bytes by applying an index-only
`git restore --staged -- <exact 19 paths>` operation. Reverify that the index is
empty and that the complete primary-worktree unrelated-path manifest is
unchanged. No unrelated index path may be modified.

Forbidden: hook edits, `--no-verify`, skip variables including
`SKIP_SECRET_SCAN`, check suppression, stashing, reset, checkout of primary
working-tree paths, synthetic `RESUME.json`, unrelated PRD edits, alternate
index/object directory, temporary branch or detached commit, `commit-tree`,
manual `update-ref`, cherry-pick, rebase, runtime/provider/network/scanner/install
activity, deployment, push, or later Track S work.
