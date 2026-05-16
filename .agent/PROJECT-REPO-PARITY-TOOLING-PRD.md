# PROJECT-REPO-PARITY-TOOLING-PRD

## Problem
The current repo parity tooling collapses several different concepts into one signal:
- repositories that are actual flake inputs,
- integrated or referenced repositories that are intentionally not flake inputs,
- upstream fetch failures,
- and repositories that are merely future evaluation targets.

That makes the parity database noisy (`unknown`/`error` heavy) and makes `repo-parity-check.py` report many expected non-input repositories as apparent gaps.

## Goal
Make parity output trustworthy enough to guide follow-up decisions by:
1. classifying library repositories by section/role,
2. distinguishing tracked-input parity from reference-only repositories,
3. recording richer fetch failure metadata,
4. keeping the output useful for operators without changing the library's broad discovery purpose.

## Scope
### In scope
- `scripts/maintenance/repo-parity-check.py`
- `scripts/maintenance/update-repo-parity.py`
- `docs/REPO-LIBRARY.md`
- validation of generated parity output

### Out of scope
- updating flake inputs themselves,
- changing the overall repo-library contents,
- redesigning the advanced parity suite,
- adding new external dependencies.

## Acceptance Criteria
- The parity checker reports only core flake-input coverage as hard parity gaps.
- Reference-only repositories are reported separately from flake-input parity.
- The update script writes a clear classification for each repo and stores explicit error reasons when upstream fetches fail.
- A refreshed parity database is materially easier to interpret than the current `unknown`/`error`-heavy output.
- Python syntax validation passes for changed scripts.

## Security / Safety
- No secrets, ports, or URLs are hardcoded beyond already-public GitHub repository references.
- External fetches continue to use `git ls-remote` without shell interpolation.
- No destructive git or deployment actions are part of this slice.

## Rollback
Revert the changed scripts/docs and regenerate `data/parity/repo-parity-db.json` with the prior script version if the new semantics prove less useful.
