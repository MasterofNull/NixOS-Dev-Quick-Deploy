## Objective
frontier item lanes-owned-scope-gate (owner approved 2026-11-18): `aq-land` refuses a branch whose changed files fall outside the slice's declared owned paths, so parallel lanes (Claude, Codex, Gemini) no longer have to avoid overlap by hand.

## Workflow/Session IDs
Branch feat/aq-land-owned-path-gate, worktree .agents/delegation/worktrees/owned-path-gate. Orchestrator Simurg@claude/opus-5.5#da0ef470; implementer Simurg@claude/sonnet.

## Delegation Decision
Implementer on Claude Sonnet (Rule 17, explicit `sonnet` override); bounded to scripts/ai/aq-land, its test, one line in the slice-authoring skill and this file. The skill edit is a single separated paragraph so it merges with the parallel slice feat/slice-brief-checks-and-caps.

## Commands Executed
- `python3 scripts/testing/test-aq-land.py` (full suite, new class OwnedPaths).
- `bash scripts/testing/check-harness-first-static-gates.sh`.
- `scripts/governance/tier0-validation-gate.sh --pre-commit`.

## Validation Evidence
Design: `--owned PATHFILE`, else `.agents/delegation/owned/<branch-slug>.txt` in the worktree (smallest option: aq-land already takes file arguments and keeps branch-slug state). One glob per line, `#` comments, trailing `/` = directory prefix, otherwise fnmatch (`*` crosses `/`). Changed files come from the existing `changed_paths()` (three-dot diff against origin/main, i.e. from the merge-base), so files that arrived by merging main are not counted. A violation stops in preflight before the lock, the review or the push, naming up to 20 files, and appends `{ts, branch, files}` to `<state>/owned-path-refusals.jsonl`. With no declaration it prints `WARN no owned-path declaration` and continues; the checkpoint records `owned_paths: declared|undeclared` so VERIFY.md can count declared vs undeclared lands.
Always allowed, each justified: the declaration file itself (it is part of the diff when committed) and `docs/harness-first/evidence/` (every slice must ship an evidence file whose name is not known in advance). Plan dirs and config/ci-checks.json are deliberately NOT allowed; slices declare them.
Tests (OwnedPaths): in-scope passes; out-of-scope stops with no gemini call, file listed, refusal row written; declaration file and evidence always allowed; undeclared warns, does not block, checkpoint says undeclared; missing --owned file stops; merging main into the branch does not count main's files.

## Rollback Plan
Revert the commit. Undeclared lands are unaffected by the gate, so no landing depends on it.

## Residual Risk
Declarations are hand-written; a too-narrow glob causes a false refusal (visible in the jsonl, fixed by adding the glob). Adoption is opt-in, so undeclared lands stay unchecked until the WARN count prompts declaring. The refusal log counts refusals only; deciding which were false remains a human call.

## Hint Feedback
No aq-hints were consulted for this slice; none to rate.

## Follow-up: Codex review fixes
Renames: changed_paths() now uses `git diff --name-only --no-renames` (committed and staged), so a rename lists both the removed unowned source and the added destination; it has no other caller. `--owned` is normalized to an absolute path before the chdir into --worktree. Tests added: committed rename, staged rename, relative --owned from another cwd (OwnedPaths, 9 tests; full suite 70 tests OK).

## Follow-up: second Codex review
Ownership is re-checked after every HEAD read in locked() (before each review) and immediately before stage_push, so a commit added during review that leaves the scope stops the landing. changed_paths() now reads `git diff --name-only -z --no-renames`, so non-ASCII and tab names are matched as real paths, not quoted. Tests added: late out-of-scope commit stops with one review and nothing published; non-ASCII and tab names pass under an owned dir and stop under an unowned dir (OwnedPaths, 11 tests).
