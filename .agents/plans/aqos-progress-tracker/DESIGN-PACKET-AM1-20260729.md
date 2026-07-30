# AQ-OS Progress Tracker AM1 — Current-HEAD Truth Re-freeze

Status: `REVISION_1_FOR_INDEPENDENT_REVIEW`  
Prepared: 2026-07-29 UTC  
Base HEAD: `50d5630b87a235e72668fabc73205c92353b27c3`

## Objective

Re-freeze the user-facing AQ-OS progress projection after Track S S0-A shipped in
commit `50d5630b87a235e72668fabc73205c92353b27c3`. The existing dirty tracker
candidate predates that commit and therefore still reports S0-A as
`REQUEST_REVISION`, unaccepted, or uncommitted. QA must never certify that stale
state.

## Exact implementation ceiling

Only these four existing files may change:

1. `config/refactor-milestones.json`
2. `assets/aqos-progress-tracker.html`
3. `scripts/testing/test-dashboard-program-progress.py`
4. `scripts/testing/harness_qa/phases/phase0.py`

Current primary-worktree hashes (overlap detection only):

| Path | SHA-256 |
|---|---|
| `config/refactor-milestones.json` | `b61171063683628d999ecf6b50f74e9e7bb37affe492ad4005b43e1861cb7cb4` |
| `assets/aqos-progress-tracker.html` | `7aca33b7618b0aea780ae6720e844d5d88f47a9341e1cc5065dfbe147d1d44ab` |
| `scripts/testing/test-dashboard-program-progress.py` | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` |
| `scripts/testing/harness_qa/phases/phase0.py` | `aa74c5c3dd2c3d0121cc34a18246aa0127e8a953d10045dd0fb1f775f5c9f9a7` |

`assets/dashboard.js` is explicitly excluded. Its current dirty bytes belong to
the separate local-direct-health slice; clean HEAD already contains the Program
tab, sandbox, tab controller, and framing-header integration required here.

`phase0.py` is a shared dirty file. Its primary-worktree hash above is not the
release subject. The only authorized delta is the exact single replacement:

```text
-    if "FROZEN_IMPLEMENTATION_SNAPSHOT" not in body:
+    if "PROJECTED_CURRENT_STATE" not in body:
```

The independently reviewed release projection must be built from clean base
HEAD plus that one-line delta. Its expected whole-file SHA-256 is
`7bfc9119822c72493911d29d85c69d9ef1826974195c45e327a73f87152ed182`.
The primary worktree's unrelated `0.10.42`/`0.10.43` bytes must be preserved
before and after partial index materialization and must not enter the release
projection.

## Required changes

### Manifest and tracker projection

- Keep Track S `active` because S0-B through S5 remain queued.
- State that S0-A is accepted and shipped in `50d5630b…`.
- Add an exact case-insensitive `commit_match` for
  `feat(security): add defensive capability intake contract`; the shipped state
  must be machine-derived, not only editorial.
- Remove the resolved `capability-intake-registry-schema-missing` issue.
- Remove the resolved `program-progress-tests-pin-superseded-snapshot` issue
  from the final projected state after the focused oracle is corrected.
- Set the projected open High-severity issue count to three unless another
  authoritative source changes before implementation.
- Refresh `snapshot_at`, visible snapshot date, and the embedded manifest digest.
- Preserve the four provenance classes and exact source binding:
  `manifest_ssot`, `governing`, `frozen_design_gate`, and
  `activation_evidence`.

The provenance manifest must also contain a closed `projection_binding` object:

- `git_head`: `50d5630b87a235e72668fabc73205c92353b27c3`;
- `projector_sha256`:
  `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b`;
- `normalized_projection_sha256`: SHA-256 of canonical JSON for
  `refactor_status.project(...)` after removing only `updated`, computed in the
  exact release projection.

This binds the mutable `git --all`, activation-event, freeze-record, and
slice-claim inputs by their normalized result. Validation must run in an
isolated single-ref repository containing only base HEAD plus the candidate
tree; it must fail if the recomputed normalized digest differs. Additional Git
refs, untracked events, or worktree claims may not become implicit evidence.

Frozen non-manifest source hashes:

| Source | SHA-256 |
|---|---|
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `.agents/plans/aqos-foundation-c/C2-FREEZE-AND-ACTIVATION.md` | `f9cee73b5cb69d3a76554db7388f1ff0a1d62dc98837fa0bfef791930ed24579` |
| `.agents/plans/unified-program/ACTIVATION-AND-CLOSEOUT-WORKLIST.md` | `143a4909c3f0f1196c4e60e04b5658131ad2cbd9df66f602f6c4ebd2fd35a8f6` |

### Focused oracle

The test must derive ordered track statuses and counts from
`scripts/ai/lib/refactor_status.py` in the isolated single-ref release
projection rather than restore July 18 constants. It must validate all four
provenance classes, exact source digests, and the closed projection binding.

Required negative vectors:

1. stale July 18 track/count/status content is rejected;
2. a tampered provenance source or digest is rejected;
3. a false return to Foundation A `blocked` is rejected.

### Phase-0 coverage

Only `_check_dashboard_program_progress` / check `0.10.40` may change. Its live
asset contract must require `PROJECTED_CURRENT_STATE`, replacing
`FROZEN_IMPLEMENTATION_SNAPSHOT`.

The unrelated dirty checks `0.10.42` and `0.10.43` must remain byte-identical
and outside this slice's staged diff.

## Validation

Run from an exact four-file release projection:

```text
PYTHONPYCACHEPREFIX=/tmp/aq-tracker-pycache python3 scripts/testing/test-dashboard-program-progress.py --static-only
PYTHONPYCACHEPREFIX=/tmp/aq-tracker-pycache python3 scripts/testing/test-refactor-status.py
python3 -m py_compile scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py
git diff --check
scripts/governance/tier0-validation-gate.sh --pre-commit
```

Offline implementation acceptance requires the focused suites and ordinary
pre-commit hook to pass. The full Tier-0 result uses a differential contract:
the known live tracker check may remain the sole failure before deployment, but
no new failure is allowed and the exact failure identity/digest must be
recorded. A later deployment authorization owns runtime mutation; after deploy,
live check `0.10.40` and the full focused suite without `--static-only` must
pass before operational closeout. Static evidence is never relabeled as live.

## Stop conditions

Stop without staging or release if:

- HEAD or any frozen provenance source drifts;
- the isolated normalized projection digest differs from the embedded binding;
- validation observes extra Git refs, untracked events, or live slice claims;
- any fifth implementation file is required;
- `assets/dashboard.js` enters the candidate;
- Phase-0 changes outside `_check_dashboard_program_progress` / `0.10.40`;
- S0-A is still described as pending, rejected, or uncommitted;
- a required negative vector passes incorrectly;
- the four-file release projection cannot reproduce focused and normal-hook
  evidence without reading unrelated working-tree changes;
- deployment, runtime mutation, or network access becomes necessary.

## Next gate

An independent reviewer must PASS this revision and the exact four-file
boundary. After that PASS, the authorization must bind this design's exact
SHA-256 before owner activation.
Implementation, staging, commit, deployment, and push remain unauthorized.
