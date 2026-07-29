# Track S S0-A — Commit-Train Release Authorization AM2

Status: **PREPARED_ONLY — INDEPENDENT REVIEW AND OWNER ACTIVATION REQUIRED**
Prepared: 2026-07-29
Exact HEAD: `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`
Release operator: `codex-orchestrator`

## Supersession and stop record

Parent release authorization
`b6c2cfc3d7f07f740682994b5622c6766e94b4dc20d1d01a35daa58741f19315`
and AM1 release authorization
`343235e91c52ef4a6f59c770a3b9ec9238847ff703551084305924f67a99a438`
are consumed and non-replayable. AM1 stopped before commit after its staged-isolated
Tier-0 run returned 1. The index was restored to empty without changing working-tree
bytes. No release commit, deployment, push, runtime action, provider call, scanner,
installation, or network action occurred.

AM1 passed every hash, inventory, scoped whitespace, JSON, Python, focused
capability-intake, list, audit, documentation-link, roadmap, focused-CI, config,
and Service Coverage check. Tier-0 reported exactly 25 checks: 24 passed and only
gate 15, `QA phase 0`, failed because QA check `0.10.40 program progress tracker`
failed.

## Frozen differential evidence

Both commands used the same executable, environment, exact HEAD, timeout, flags,
and staged-isolation implementation:

```text
scripts/governance/tier0-validation-gate.sh --pre-commit --staged-isolated --tap
```

| Subject | RC | Tier-0 log SHA-256 | TAP outcome vector |
|---|---:|---|---|
| exact clean HEAD, empty index | 1 | `a354ceded268c9e2505176b63b60511af733872c77b7b11d17bfa338a0cf93b9` | `ok 1..14; not ok 15; ok 16..25` |
| exact HEAD plus frozen 17-path AM1 subject | 1 | `e0bce95dab7ffe2ba92e84a4a9a8bbaf872899d086b6664de7a8671d008c802d` | `ok 1..14; not ok 15; ok 16..25` |

Expected descriptions differ only where the staged subject truthfully changes a
gate from “no changed files” to validation of the staged Python/JSON/docs inputs.
No pass becomes a failure. Both runs have the same sole failed gate and the same
24 successful gate numbers.

The focused command was also run from two clean archive projections: exact HEAD,
and exact HEAD overlaid with all 17 frozen S0-A paths:

```text
python3 scripts/testing/test-dashboard-program-progress.py --static-only
```

Both return 1 after 12 tests with exactly one error:

- test: `StaticContractTests.test_operational_snapshot_liveness_boundary`;
- source line: `scripts/testing/test-dashboard-program-progress.py:134`;
- exception: `FileNotFoundError`;
- missing repository-relative path: `.agent/collaboration/RESUME.json`;
- normalized output SHA-256 after replacing only the temporary root and elapsed
  test duration: `a54419d605f6fcc43233f6a081054a86659f0ffc0e36113e99efebef98e421c4`.

This is a pre-existing clean-HEAD validation defect. The focused test requires an
intentionally untracked operational projection inside a clean repository snapshot.
None of the frozen 17 paths is the focused tracker test, `phase0.py`, tracker HTML,
dashboard code, `RESUME.json`, or a source consumed by check `0.10.40`.

**HIGH defect record:** clean-snapshot QA currently confuses ephemeral operational
state with committed contract state. The already-designed progress-tracker repair
must remain the immediate follow-up and must add a missing-operational-projection
negative vector. This AM2 differential is single-use bootstrap evidence, not a
standing baseline allowance.

## Exact release inventory

The 15 path/hash rows frozen in
`S0-A-RELEASE-AUTHORIZATION-20260729.md` remain exact and unchanged. The release
commit may contain exactly:

1. those 15 frozen subject paths;
2. `S0-A-RELEASE-AUTHORIZATION-20260729.md` at
   `b6c2cfc3d7f07f740682994b5622c6766e94b4dc20d1d01a35daa58741f19315`;
3. `S0-A-RELEASE-AUTHORIZATION-AM1-20260729.md` at
   `343235e91c52ef4a6f59c770a3b9ec9238847ff703551084305924f67a99a438`;
4. this AM2 authorization at its independently reviewed and owner-activated
   SHA-256.

Total ceiling: **18 paths**. Every earlier subject hash remains mandatory.

## Activation and release contract

This document grants nothing until an independent eligible reviewer returns an
exact-hash `PASS` and the owner activates that hash, exact HEAD, release operator,
and a UTC window no longer than 24 hours.

After activation, the release operator must:

1. reverify exact HEAD, all 15 parent subject hashes, both predecessor
   authorization hashes, this activated hash, and absence of an overlapping writer;
2. stage exactly the 18-path ceiling without changing any working-tree byte;
3. retain all AM1 checks: scoped `git diff --cached --check`, JSON parse, Python
   compilation using `/tmp` bytecode, capability-intake focused tests, `list`,
   `audit`, documentation-link validation, and exact staged inventory;
4. rerun staged-isolated Tier-0 and require the exact structural result frozen
   above: 25 checks, 24 pass, only gate 15 fails, and only QA check `0.10.40`
   fails for the same focused-test exception tuple;
5. run the focused tracker test in an exact staged snapshot and require normalized
   digest `a54419d605f6fcc43233f6a081054a86659f0ffc0e36113e99efebef98e421c4`;
6. inspect the staged diff and run normal commit hooks;
7. create one evidence-rich atomic commit only if every result is exact.

The commit must truthfully state that Tier-0 returned 1 due to the exact inherited
baseline defect. It must not claim Tier-0 passed.

## Absolute stop conditions

Stop on HEAD/hash/content drift, a nineteenth path, overlap, any additional or
changed Tier-0/QA/focused-test failure, any pass-to-fail regression, a changed
exception class/test/source line/repository-relative path, focused validation
failure, hook failure, or candidate semantic drift.

Forbidden: `--no-verify`, skip variables, check suppression, synthetic
`RESUME.json`, tracker/test/Phase-0 edits, blanket baseline allowances, standing
nonzero-Tier-0 policy, runtime/provider/network/scanner/install activity,
deployment, push, or later Track S work.
