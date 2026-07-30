---
title: Pre-commit Subject Boundary H0 Design Packet
doc_type: plan
id: precommit-subject-boundary-h0
status: draft
owner: codex-orchestrator
last_updated: 2026-07-29
parent_prd: .agent/PROJECT-PRECOMMIT-SUBJECT-BOUNDARY-PRD.md
---

# H0 Design Packet — Whole-hook Staged Subject Boundary

**Status:** `PREPARED_ONLY` — design review requested; no implementation,
staging, commit, deployment, or live mutation authority.

**Build base:** `50d5630b87a235e72668fabc73205c92353b27c3`

## 1. Evidence and decision

Track S S0-A reproduced a subject-boundary defect: the normal pre-commit hook
ran `doc-frontmatter --all` in the primary dirty worktree and rejected an exact
accepted staged subject because of an unrelated untracked PRD. Two isolated
`HEAD + index` normal-hook projections passed without bypassing the hook or
altering its gates.

The architectural boundary belongs at the whole hook, not only at focused CI.
Otherwise other content-reading governance commands can repeat the same leak.
The focused runner also remains independently safe when developers invoke it
directly.

Current control-plane hashes at freeze:

| Path | SHA-256 |
|---|---|
| `.githooks/pre-commit` | `fbae8d72b2e23598128266af2c03ff43dcc7a6d13dd9fc9732ce932d418db0ee` |
| `scripts/governance/run-focused-ci-checks.sh` | `5c7589c6b41e3364bb6c316bcd73d622511183b7de3a8d61ba6492801da5cb8e` |
| `scripts/testing/test-doc-frontmatter-staged-files.py` | `6d9ed799b8eaa3b320231108a9e310eadba2966d8a48c87def4d1e5de13cbf37` |
| `config/validation-check-registry.json` | `a7870d07091ba15d947ee6712b50fe6b0f8d779060f98a0dd4d9c3af23304a8d` |
| `.agent/memory/issues-backlog.md` | `391e641308fdd9ef59b1bce936ac21144fbbdee9123afb0b5f59d33353d9bec9` |

The issues backlog is already modified by the open
`pre-commit-focused-ci-leaks-unstaged-subjects` record. An implementation
authorization must freeze the then-current complete file hash and may only mark
that existing issue `DONE` after independent acceptance; it must not overwrite
other concurrent backlog entries.

## 2. Exact candidate inventory

The H0 implementation ceiling is exactly seven paths:

1. `.githooks/pre-commit`
2. `scripts/governance/run-focused-ci-checks.sh`
3. `scripts/governance/lib/staged-index-projection.sh` (new)
4. `scripts/testing/test-pre-commit-staged-subject.sh` (new)
5. `scripts/testing/test-doc-frontmatter-staged-files.py`
6. `config/validation-check-registry.json`
7. `.agent/memory/issues-backlog.md`

The registry path is mandatory. Inspection proves the existing
`doc-frontmatter-staged-files` and `focused-ci-diagnostic-json` entries trigger
on the runner and existing test only; neither discovers the new shared helper,
whole-hook test, nor hook entrypoint. H0 adds exactly one focused behavioral
entry for the new whole-hook test. No existing entry is weakened or removed.

## 3. Component design

### H0.1 Shared projection helper

The new shell library exposes a narrow callable interface used by the hook and
runner. It:

- resolves real repository/Git/index paths before changing directories;
- requires stage-0-only index state and rejects gitlinks;
- validates control-plane hook/helper worktree bytes against index blobs before
  sourcing or executing mixed code;
- creates a private temporary root and installs cleanup traps;
- executes `git checkout-index --all --force --prefix="$projection/"`;
- builds canonical, NUL-delimited expected and observed manifests containing
  path, Git mode, and blob identity;
- requires exact manifest equality and emits a bounded manifest digest/count;
- invokes a caller-specified projected entrypoint with absolute `GIT_DIR`,
  projected `GIT_WORK_TREE`, and one private positional recursion sentinel;
- returns the child status after cleanup without changing the real index,
  worktree, refs, stash, configuration, or hooks.

All arrays and NUL-delimited records remain data. No `eval`, `bash -c` built
from variables, generated script, word-splitting path loop, or environment dump
is allowed.

### H0.2 Hook adoption

Before any content-reading gate, `.githooks/pre-commit` verifies its own and the
helper's worktree bytes against their index blobs and enters the projection. A
projected invocation consumes its private sentinel, shifts it, and runs the
existing functions in their existing order.

The projected hook calls focused CI as:

```text
run-focused-ci-checks.sh --pre-commit <private-projected-sentinel>
```

Secret scanning continues to use `git diff --cached` against the real index.
Syntax, structure, migration-governance, and focused checks read projected
bytes. Existing skip controls and messages are not expanded or renamed.

### H0.3 Direct focused-runner adoption

For `--pre-commit` without the private sentinel, the runner enters the same
projection and invokes its staged copy. With the sentinel it executes once.
For `--pre-deploy`, it follows the current code path unchanged.

An unset `REGISTRY` is resolved after projection entry. A caller-supplied
registry must be absolute, is preserved, and must exist under the existing
missing-registry contract. `FOCUSED_CI_JSON`, when set, is normalized to an
absolute output path before projection and remains writable outside the
ephemeral tree. The runner does not add a new environment variable.

### H0.4 Regression coverage

`test-pre-commit-staged-subject.sh` creates isolated temporary repositories and
uses the actual normal hook path. It asserts exact exit status, checker marker
presence/absence, projection count/digest shape, primary-worktree immutability,
index immutability, and cleanup.

`test-doc-frontmatter-staged-files.py` retains all five current cases and adds
direct-runner coverage for projection, default/custom registry selection,
non-recursion, output-path survival, and safe arguments. It may not replace
live/predeploy semantics with mocks.

The new registry entry triggers on the hook, runner, helper, both tests, and the
registry itself, executes only the new hook-level test, and uses a bounded
timeout.

### H0.5 Issue closure

After exact-subject acceptance, update only the existing
`pre-commit-focused-ci-leaks-unstaged-subjects` record from `OPEN` to `DONE`,
record the root fix and acceptance evidence, and preserve every unrelated
backlog byte. If acceptance is not `PASS`, leave it open.

## 4. Required A–F vectors

| Vector | Setup | Required result |
|---|---|---|
| A | valid staged document; invalid unrelated untracked document | normal hook passes; untracked file absent from projection |
| B | invalid staged document; primary-worktree version repaired but not staged | normal hook fails on staged byte |
| C | valid staged document; another tracked document invalid only in worktree | normal hook passes; unrelated unstaged byte absent |
| D | Vector A primary worktree under direct `--pre-deploy` | fails under unchanged all-document behavior |
| E | absolute custom `REGISTRY`; explicit `FOCUSED_CI_JSON` | custom registry used once; JSON survives cleanup at original path |
| F | checkout/equality failure, unmerged entry, gitlink, or partial hook/helper staging | fail closed before checker marker; index/worktree unchanged |

Additional mandatory controls:

- paths containing spaces, leading dashes, Unicode, and shell metacharacters;
- regular executable and symlink mode preservation;
- staged deletion absent from projection;
- no extra projected file;
- cleanup after pass, child failure, and signal;
- private sentinel supplied by an external caller cannot bypass the bootstrap:
  it is accepted only when the current worktree is already the verified
  projection established by the helper's invocation contract.

## 5. Staged-hash and partial-index caveats

Git selects the worktree hook before the helper can establish isolation. The
bootstrap trust root is therefore limited and explicit:

1. obtain the index blob IDs for `.githooks/pre-commit` and the helper;
2. hash the corresponding worktree bytes without filters;
3. fail if either differs, is absent, is a symlink, or is not stage 0;
4. only then source the helper and materialize the projection.

This intentionally blocks commits while hook/helper edits are partially staged.
The projected runner and tests are loaded from the index, so their unstaged
worktree variants cannot affect the result. The implementation review must
specifically reject any design that sources an unverified worktree helper,
copies the worktree runner, or validates only the list of staged paths instead
of the complete index.

The acceptance hash binds the complete seven-path candidate. The issues backlog
is a shared dirty file, so any byte drift after freeze is a stop, not permission
to reconstruct or discard concurrent entries.

## 6. Compatibility, telemetry, and coverage

`--pre-deploy` retains its current changed-file union and current-worktree
semantics. Existing focused-CI JSON fields and check exit conventions remain
compatible. H0 may add bounded projection fields/category only if the existing
diagnostic regression proves old consumers still pass.

The projection helper is a short-lived local validation primitive, not a
service. No endpoint, route, daemon, Nix unit, runtime configuration, or
operator control is introduced, so dashboard/Phase-0 Service Coverage is
**not applicable**. Required visibility is the bounded terminal category plus
manifest digest/count in hook/focused-CI evidence. Never emit staged paths,
temporary paths, file content, environment, usernames, or repository absolute
paths.

## 7. Offline validation plan

An eventual H0 authorization may allow only:

```text
bash -n .githooks/pre-commit
bash -n scripts/governance/run-focused-ci-checks.sh
bash -n scripts/governance/lib/staged-index-projection.sh
bash -n scripts/testing/test-pre-commit-staged-subject.sh
python3 scripts/testing/test-doc-frontmatter-staged-files.py
python3 scripts/testing/test-focused-ci-diagnostic-json.py
bash scripts/testing/test-pre-commit-staged-subject.sh
python3 -m json.tool config/validation-check-registry.json
```

Tests must use temporary repositories and must not stage or mutate the primary
repository. Tier0, the live normal hook against the primary index, staging,
commit, deployment, provider calls, and network access require a later
release/acceptance authorization.

## 8. Stop conditions and exclusions

Stop on any:

- eighth-path requirement or registry change beyond the one new entry;
- primary index/worktree/ref/stash/config mutation;
- hook bypass, skip-variable addition, or validation weakening;
- inability to prove complete index/projection mode+blob equality;
- silent copying of ignored/untracked operational inputs;
- new environment variable or secret/high-cardinality telemetry;
- changed `--pre-deploy` result;
- network, provider, live traffic, Phase-0, dashboard, Nix, service, deployment,
  staging, commit, push, or destructive operation;
- candidate drift, overlapping writer, or implementer self-acceptance.

## 9. Next gate

This packet is `PREPARED_ONLY`. Obtain an independent flagship architecture,
security, SRE, Git-index, and test-design review over its exact bytes. A `PASS`
may permit preparation of a single-use, hash-bound H0 implementation
authorization against the then-current HEAD and exact seven-path ceiling.
Implementation remains unauthorized until the owner explicitly activates that
authorization. A separately assigned reviewer must issue the binding
exact-subject acceptance verdict before any release authorization is prepared.
