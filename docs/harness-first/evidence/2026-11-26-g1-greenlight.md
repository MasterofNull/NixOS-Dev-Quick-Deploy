# G1 greenlight gating evidence — 2026-11-26

## 1. Objective

Implement G1 of `.agents/plans/greenlight-gating-20261119/DESIGN.md`, including
Revision 1 F1/F2/F6/F12 and Revision 2 P1/J6. The CLI validates an exact staged
snapshot merged with a pinned base without committing on the user's branch.

## 2. Harness-first discovery

Consulted the frozen G1 design, existing `aq-baseline` usage hook,
`test-aq-usage-logging.py`, CI registration and activation-manifest checker.
The AIDB error-solutions query returned no relevant greenlight precedent.
The implementation uses Python's standard library and existing Git/gate tools.

## 3. Scope and contracts

Owned surfaces are the greenlight library, executable CLI, executable acceptance
suite, CI manifest, activation manifest and this evidence file. No branch hooks,
merge enforcement, deployment or later greenlight slices are introduced.
Unstaged tracked changes and untracked non-ignored files are refused.

## 4. Implementation

A detached throwaway commit captures the staged tree and exact parent. The pinned
base is merged there, its tree recorded, then a soft reset stages the entire
merged slice against that base. Default checks run tier0 pre-commit, numbered
evidence sections and CI coverage; PR body headings are checked only when supplied.
Explicit command overrides support isolated acceptance fixtures.
Records are atomically replaced outside the worktree, with private directory/file
permissions and percent-encoded branch names. Show/verify compare exact staged
tree, parent, branch and current base, and retain failure diagnostics.

## 5. Validation and results

Seven acceptance tests passed using real temporary repositories and real shellcheck:
J1 missing sections 7/8, J2 conflicting paths, J6 committed shell error exposed to
staged-only checking, dirty/untracked refusal, optional/ordered PR body headings,
private exact-content records and verification, and clean incoming-main integration.
Every invocation checks preservation of user HEAD, branch, index tree and status,
and removal of the throwaway worktree, including failure cases.

`py_compile` passed for all three Python files. Ruff passed. Basedpyright reported
zero errors and warnings. The existing usage-logging suite passed. CI test coverage
passed (817 tests: 725 declared, 92 exempt). Activation-manifest validation passed
with nine entries, zero failures and zero warnings; existing dated deferrals remain.
JSON parsing of the activation manifest passed.

## 6. Security and failure modes

No credentials, service ports, network endpoints or dependencies were added.
Git and gate arguments use subprocess argument lists. Command overrides are explicit
operator input parsed with shlex. Merge conflicts and gate errors produce FAIL
records; cleanup runs in finally. Evidence/body failures include missing headings.
Temporary merge signing and hooks are disabled so unrelated hooks cannot mutate
the merged snapshot or prevent the subsequent soft reset.

## 7. Activation and observability

The executable is available on demand. Its live acceptance caller and named health
signal are registered in the activation manifest; --show/--verify inspect records.
The new suite and both implementation paths are registered in tests-aq.
Validation used injected gate commands in disposable repositories; the full tier0
wrapper was deliberately not run by this headless slice. This is G1 validation,
not an attestation that later slices or mandatory merge enforcement are active.

## 8. Handoff and rollback

Leave all six files unstaged for orchestrator review, tier0 and commit. No deployment,
commit or production branch mutation occurred. To withdraw the CLI, revert the six
owned changes through the normal reviewed workflow; existing private records can
be archived separately. The clean-merge test caught that Git rejects soft reset
while a no-commit merge is pending; completing the detached merge first fixes the
producer rather than bypassing the gate. No unresolved test failures remain.
