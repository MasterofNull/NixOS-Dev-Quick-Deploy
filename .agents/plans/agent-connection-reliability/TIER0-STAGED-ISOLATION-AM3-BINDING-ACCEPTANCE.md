# Independent Acceptance — Tier0 Staged Isolation AM3 Binding

Review date: 2026-07-22
Reviewer: `codex-subagent-tier0-isolation-am3-acceptance`
Role: independent security, SRE, concurrency, and governance reviewer
Mode: exact-byte read-only acceptance; no candidate edits, staging, commit, live service, provider,
network, Nix, or deployment authority

## Exact subjects

- HEAD: `c286169a90c7a22e6bd163d1bbcf3b065fed79cd`
- `scripts/governance/tier0-validation-gate.sh`
  - SHA-256: `98387619c3507982b8a95567d60c9600dcc6f59854fc23eb3b40e3507166f5d6`
- `scripts/testing/test-tier0-staged-isolation.sh`
  - SHA-256: `cf90f5eda6b9e7ebfc9245836ed12f1b79fcdf4bcaff7d8b554b69862cd54a2f`

Both file hashes and HEAD matched before and after validation. The gate remained one modified unstaged
path and the focused test one untracked path; this review did not alter the candidate or shared
index.

## Production isolation boundary

PASS. `--staged-isolated` is explicit and pre-commit-only. Its operational overlay is a closed
four-path constant containing only:

1. `.agent/collaboration/PULSE.log`
2. `.agent/collaboration/RESUME.json`
3. `.agents/improvement/candidates.json`
4. `.agents/delegation/registry.jsonl`

Each source must exist as a regular non-symlink and be no larger than 4 MiB. Each path must be ignored
inside the clean snapshot, and any staged add/change/rename/delete of an operational path is rejected
before hydration. Because tracked paths do not satisfy the snapshot's `check-ignore` test, the
overlay cannot replace tracked content; copied files remain ignored and never enter the isolated
index.

Copying is bounded to two attempts. For every attempt, the gate records source size and hash, copies
exactly that size to a temporary file, computes the destination hash, rechecks source type, size, and
hash, and accepts only when source-before, destination, and source-after hashes plus both sizes agree.
Instability exhausts the bounded retry and hard-fails. Temporary and final overlay files are forced
to mode 0600. The only additional writable runtime surface created intentionally is the checked,
non-symlink `.agent/qa` directory at mode 0700 for QA locking. No arbitrary live file, directory,
environment override, or caller-selected path enters the snapshot.

## Fail-closed execution and unchanged default

PASS. Explicit staged isolation accepts only `--pre-commit`. Failure of temporary-directory creation,
worktree creation, staged-diff capture/application, operational hydration, type/size/hash validation,
ignore checks, or QA-directory validation propagates through `setup_staged_isolation`, prints the
explicit failure diagnostic, and exits 1 before any gate. There is no fallback to the dirty working
tree. Repository root and script root are repointed only after the complete snapshot succeeds.

Without `--staged-isolated`, `STAGED_ISOLATED` remains zero and the new setup branch is not entered;
the pre-existing gate functions, changed-file selection, mode handling, and validation sequence are
unchanged. Cleanup is limited to the temporary isolation worktree and patch path captured by this
invocation.

## Focused test safety and evidence

PASS. The focused test clones committed objects locally with `--no-hardlinks` into a unique temporary
directory. It overlays the exact candidate gate only inside that disposable clone, populates only the
four ignored operational projections there, and performs all fixture adds, resets, restores, and
removals against the clone's independent index and worktree. It never stashes, resets, stages,
restores, or otherwise mutates the shared source repository. Its trap removes only its unique
temporary parent.

The test captures each real gate exit code using a bounded `set +e` region and does not mask the
command with `|| true`. It proved:

- missing required operational input: nonzero, expected diagnostic, and no fall-through to Python or
  later gates;
- unrelated dirty whole-tree violation: nonzero with the expected SSOT finding;
- valid staged change plus unrelated dirty violation under `--staged-isolated`: exit 0, isolation-mode
  diagnostic present, dirty-tree finding absent;
- genuinely staged violation under `--staged-isolated`: nonzero with the expected SSOT finding.

The successful isolated case therefore cannot be attributed to an empty staged diff or silent
fallback, and the bad staged case proves that isolation does not weaken the gate.

## Validation performed

```text
bash -n scripts/governance/tier0-validation-gate.sh
  PASS
bash -n scripts/testing/test-tier0-staged-isolation.sh
  PASS
git diff --check -- scripts/governance/tier0-validation-gate.sh
  PASS
timeout 360 bash scripts/testing/test-tier0-staged-isolation.sh
  PASS (exit 0; all four scenarios passed)
```

No live service, network, provider, local inference, Nix, deployment, broad repository gate,
candidate edit, staging, or commit occurred.

VERDICT: PASS — exact AM3 binding closes the operational-overlay and hard-fail blockers without weakening default Tier0 behavior or mutating shared Git state
