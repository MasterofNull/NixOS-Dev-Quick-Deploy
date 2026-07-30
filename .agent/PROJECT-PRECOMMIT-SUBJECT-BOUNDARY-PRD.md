---
title: Pre-commit Staged Subject Boundary
doc_type: prd
id: precommit-subject-boundary
status: draft
owner: codex-orchestrator
last_updated: 2026-07-29
---

# Pre-commit Staged Subject Boundary PRD

## 1. Problem and evidence

The normal `.githooks/pre-commit` hook identifies staged paths, but it executes
content-reading governance and focused-CI commands in the dirty primary
worktree. The focused runner's `doc-frontmatter` registry entry is
`always_run=true` and invokes `check-doc-frontmatter.py --all`. During the Track
S S0-A release, an exact accepted staged subject was blocked by invalid metadata
in an unrelated untracked PRD. The hook therefore validated more than the
proposed commit and made an independently accepted atomic commit depend on
another in-flight slice.

The temporary release procedure proved that the unchanged normal hook succeeds
when its complete execution view is an exact projection of the Git index. That
procedure was deliberately release-local; this project establishes the durable
boundary.

## 2. Objective

For normal pre-commit execution, run every content-reading gate against one
ephemeral, verified `HEAD + index` projection while retaining the real absolute
Git directory and index. A valid staged subject must be independent of unrelated
tracked modifications and untracked or ignored files in the primary worktree.
Invalid staged bytes must still fail even when the primary worktree contains a
later valid version.

This is subject isolation, not validation reduction. The ordinary hook, all
enabled gates, the validation registry, timeouts, failure codes, secret scan,
and diagnostic output remain active.

## 3. Required behavior

### 3.1 Whole-hook boundary

On normal pre-commit entry, the hook must:

1. resolve and retain the absolute real `GIT_DIR`, index path, repository root,
   original working directory, and any explicit diagnostic output path;
2. reject an unmerged index, gitlinks, unsafe control-plane paths, a missing
   staged helper, or a hook/helper worktree byte mismatch with the index;
3. create a mode-0700 temporary directory outside the repository;
4. materialize every stage-0 index entry with
   `git checkout-index --all --force --prefix=<projection>/`;
5. verify a deterministic manifest of path, Git mode, and blob SHA-1/SHA-256
   equivalence between the complete index and the projection;
6. invoke the projected hook with absolute `GIT_DIR`, projected
   `GIT_WORK_TREE`, projected working directory, and a private positional
   recursion sentinel;
7. preserve the child exit code, remove the temporary projection on every
   ordinary exit/signal, and fail closed if materialization, equality checking,
   invocation, or cleanup setup fails.

No file may be copied from the primary worktree after index materialization.
Untracked and ignored operational inputs are absent unless a gate receives an
already-supported explicit absolute input. This absence must not be silently
converted to a pass: a gate that requires an unavailable input retains its
existing fail/skip contract.

### 3.2 Focused-runner direct use

`run-focused-ci-checks.sh --pre-commit` is also a public developer entrypoint.
When invoked directly outside the projected hook, it must use the same helper
and exact-index projection. When invoked by the projected hook with the private
positional sentinel, it must not project recursively.

The runner must recompute its default
`config/validation-check-registry.json` path inside the projection. An explicit
custom `REGISTRY` must be an absolute path and remain unchanged. An explicit
`FOCUSED_CI_JSON` path must be canonicalized before projection and remain an
external output path so the receipt survives projection cleanup. Neither value
may be interpreted as shell text.

`--pre-deploy` behavior is unchanged: it continues to inspect its current
working tree and the existing deploy diff union. It must never inherit the
pre-commit recursion sentinel implicitly.

### 3.3 Index/projection equality

The shared helper owns one deterministic algorithm:

- obtain stage-0 entries from `git ls-files --stage -z`;
- reject any non-zero stage, gitlink (`160000`), duplicate path, absolute path,
  traversal component, or path that cannot be represented losslessly;
- materialize the complete index, including executable files and symbolic links;
- for each projected path, compare the expected Git mode and Git blob identity
  with the index; reject missing, extra, type-changed, or content-changed paths;
- hash the canonical NUL-delimited manifest and report only bounded counts,
  mode, and manifest digest.

The projection must not use `git archive HEAD`, a partial staged-path copy, a
stash, `git reset`, `git checkout` of the primary worktree, or a second mutable
index. Deleted index paths remain absent. The real index is read-only to the
helper.

### 3.4 Staged-control-plane caveat

Git launches the hook from the primary worktree before isolation exists.
Accordingly, the bootstrap must perform no content gate before it verifies that
the worktree hook and helper bytes equal their stage-0 index blobs. A partially
staged hook/helper update is a hard failure with remediation guidance; it may
not run mixed worktree/index control-plane code. After bootstrap, the projected
runner and tests are necessarily the staged bytes.

This protects correctness against accidental partial staging. It is not a
defense against a malicious staged hook approved for commit; code review and
the independent acceptance gate remain the authority for control-plane changes.

## 4. Exact H0 implementation ceiling

H0 may change exactly these seven paths:

1. `.githooks/pre-commit`
2. `scripts/governance/run-focused-ci-checks.sh`
3. `scripts/governance/lib/staged-index-projection.sh` (new)
4. `scripts/testing/test-pre-commit-staged-subject.sh` (new)
5. `scripts/testing/test-doc-frontmatter-staged-files.py`
6. `config/validation-check-registry.json`
7. `.agent/memory/issues-backlog.md`

The registry is required, not optional: no current entry names the new helper,
hook-level test, or `.githooks/pre-commit`. Existing entries triggered by the
runner would not execute the new whole-hook negative vectors. The one registry
change is limited to a single enabled behavioral entry for the new test with
the five control-plane/test trigger paths and a bounded timeout.

No other hook, checker, registry entry, schema, environment contract, Phase-0
check, dashboard file, Nix module, service, deployment surface, or collaboration
state is in scope.

## 5. Acceptance vectors

The hermetic test must create a temporary Git repository with the real hook,
runner, helper, minimal registry/checker fixtures, and normal `core.hooksPath`.
It must exercise:

- **A — unrelated untracked isolation:** valid staged document plus invalid
  untracked document; normal pre-commit passes.
- **B — staged truth wins:** invalid staged document, then valid replacement in
  the primary worktree without re-staging; normal pre-commit fails.
- **C — unrelated tracked-worktree isolation:** valid staged document plus an
  invalid unstaged modification to another tracked document; normal pre-commit
  passes.
- **D — predeploy compatibility:** the Vector A worktree run with
  `--pre-deploy` sees the invalid untracked document and fails under the
  existing all-document check.
- **E — explicit outputs/registry:** an absolute custom `REGISTRY` and explicit
  `FOCUSED_CI_JSON` remain bound to their original paths, produce the expected
  receipt, and are not replaced by projection defaults.
- **F — bootstrap/equality fail closure:** projection creation failure,
  manifest mismatch, unmerged index, gitlink, and partial hook/helper staging
  each fail before any checker command executes.

Existing doc-frontmatter tests must additionally prove direct runner
pre-commit projection, private-sentinel non-recursion, default projected
registry selection, argument safety, and unchanged no-matching-path skip
behavior. Existing focused diagnostic JSON tests must remain green.

## 6. Security and reliability requirements

- Temporary directories are private, randomly named, and removed by a trap.
- Paths are handled as NUL-delimited data or arrays; no `eval`, shell
  re-parsing, generated supervisor script, or prompt-like string interpolation.
- Absolute custom paths are data, never commands. Symlinks cannot escape the
  projection through a parent component.
- Failure to inspect the index, hash a file, preserve modes, create cleanup
  handling, or execute a required tool fails closed.
- The helper never mutates the index, primary worktree, refs, stash, or Git
  configuration.
- Recursive direct-runner invocation is bounded by a private positional token,
  not a new environment variable or a user-facing bypass.

## 7. Observability and Service Coverage

The helper is an in-process commit-validation primitive, not a resident service,
API, route, background worker, or configurable runtime feature. The
three-part Service Coverage Contract (live `aq-qa` integration check, dashboard
panel, adjacent service commit) is therefore **not applicable to H0**.

It must still be measurable. Human output and focused-CI JSON record projection
mode, bounded entry count, manifest digest, and terminal pass/fail category.
They must not expose temporary paths, user paths, file contents, staged names,
environment contents, or other high-cardinality identifiers. The registry
entry makes the whole-hook contract continuously discoverable by focused CI.

## 8. Non-goals and stop conditions

H0 does not alter validation policy, weaken `always_run`, repair unrelated
documents, bypass hooks, stash changes, deploy, push, change live traffic, or
introduce a daemon. Stop and request a new design if implementation requires:

- any eighth path;
- an environment-contract addition;
- copying ignored/untracked runtime data;
- modifying the primary worktree or index;
- changing `--pre-deploy` semantics;
- weakening a gate, timeout, exit status, or diagnostic field;
- network, provider, Nix, service, dashboard, Phase-0, deployment, staging, or
  commit operations.

## 9. Delivery gates

H0 begins only after an independent architecture/security/SRE review issues
`PASS` on the exact design packet. Implementation requires a later, hash-bound,
single-use owner activation against an exact HEAD and seven-path ceiling.
Acceptance requires the A–F vectors, existing focused-CI/doc-frontmatter
regressions, shell syntax/static analysis, an exact candidate manifest, and an
independent reviewer who did not implement the candidate. `PREPARED_ONLY`
documents do not authorize edits, staging, commit, deployment, or adoption.
