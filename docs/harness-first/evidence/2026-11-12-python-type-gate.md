# Python is held to compile-time-like checks (basedpyright + ruff, baseline ratchet)

Date: 2026-11-12

## Objective

Python was only syntax-checked (`py_compile`); undefined names, unused imports and type errors landed unnoticed across
about 1,900 files. Owner policy 2026-11-12 (PRD language-by-role, section 4): basedpyright is the type checker and ruff
the linter; tier0 checks staged files, CI the whole tree, both against a baseline that only shrinks so a change fails
only for errors it introduces.

## Workflow/Session IDs

- Branch `feat/python-type-gate`, worktree `.agents/delegation/worktrees/python-type-gate`; slice L2 of wave F.
- Brief `.agents/delegation/outputs/wave-f/l2-python-type-gate.md`.

## Delegation Decision

Sonnet 5.5 implementer (Rule 17 default). The slice adds no flake outputs: tools are built with
`nix build --inputs-from <repo> nixpkgs#<tool>`, pinned by the repo's flake.lock. An earlier revision exported them as
flake `packages`; that made the CI runner lose communication during `nix flake check --all-systems` (twice), so it was dropped.

## Commands Executed

- `python3 scripts/governance/check-python-types.py --write-baseline` (full tree, from the flake-built tools)
- `python3 scripts/governance/check-python-types.py --all`, `--staged`
- `python3 scripts/testing/test-check-python-types.py`, `python3 scripts/testing/test-ci-checks-manifest.py`
- `nix build --no-link --print-out-paths --inputs-from . nixpkgs#basedpyright` (same store path as the pinned nixpkgs)

## Validation Evidence

- Baseline: 4,269 basedpyright errors + 2,037 ruff findings = 4,201 distinct fingerprints over 1,807 files
  (`config/python-check-baseline.json`). Full tree `--all` against it: PASS, about 150 s.
- `--staged` for a 5-file change: PASS in 8 to 10 s. A staged file with an undefined name FAILs with both tools
  naming it (basedpyright reportUndefinedVariable, ruff F821); the file was then removed.
- `test-check-python-types.py`: 9 tests OK (new undefined name fails; baselined diagnostic passes; moved diagnostic
  passes; a second occurrence of a baselined fingerprint fails; `--write-baseline` refuses growth without
  `--allow-growth`, may shrink; excluded archive paths skipped; missing tool with failing `nix build`, and with no nix,
  both FAIL).
- Fingerprint is (tool, path, rule, message) with no line or column. Only `error` severity counts for basedpyright.
- `pyrightconfig.json` already existed in `basic` mode with about 30 rules switched off (undefined variable, call and
  argument errors among them), which would have made the gate meaningless; it is now `standard` with only the two
  missing-import rules off, the old `nix`, `scripts/governance` and tests excludes dropped, `extraPaths` kept, and the
  `pythonPath` pointing at a garbage-collected store path removed.

## Rollback Plan

Revert the PR, or drop the `gate_python_types` call in tier0 and the `python-type-gate` entry in
`config/ci-checks.json`. The baseline file is data only.

## Residual Risk

- A full-tree run is about 150 s; `python-type-gate` carries Python path filters so `--changed` skips it otherwise.
- A tool absent from PATH is built from the repo's pinned nixpkgs via --inputs-from: first use downloads basedpyright (npm deps).
  Both tools are also added to the ai-dev system profile (`nix/data/profile-system-packages.nix`), live after the
  next rebuild.
- Staged mode checks the working-tree file, not the index blob.
- The 6,306 baselined findings are untouched here; shrinking them is future work and `--write-baseline` locks in each gain.

## Hint Feedback

`pyrightconfig.json` suppressing the very rules a gate needs was found by reading the file before writing config; the
brief assumed no config existed.
