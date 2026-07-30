# AQ-OS Progress Tracker — Focused Test Re-pin Design

**Status:** PREPARED_ONLY — no implementation authority  
**Prepared at:** 2026-07-27 UTC  
**Build base:** `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`  
**Objective:** restore the focused tracker contract to current manifest/projector truth without reinstating the superseded 2026-07-18 frozen snapshot.

## Evidence and root cause

The worktree tracker is a July 27 projected-state candidate, but `scripts/testing/test-dashboard-program-progress.py` hard-codes the July 18 `FROZEN_IMPLEMENTATION_SNAPSHOT`: eight sources, `10/2/1/9/10/2` counts, a Foundation-A blocking gate, and `DIRECTION_RECORDED` rows.

`python3 scripts/testing/test-dashboard-program-progress.py --static-only` is red at 4 of 12 tests: `explicit_state_counts`, `frozen_manifest_is_current`, `operational_snapshot_liveness_boundary`, and `truthful_foundation_projection`. Phase-0 check `0.10.40` runs that static command and separately requires the retired `FROZEN_IMPLEMENTATION_SNAPSHOT` live-asset token. Thus one test-file alone cannot honestly repair the Phase-0 failure.

The tracker initially claimed `PROJECTED_CURRENT_STATE` with stale manifest/worklist hashes. The tracker owner corrected those pins before this design freeze; the re-pin must preserve and verify that equality rather than weakening provenance.

| File | Current SHA-256 | HEAD SHA-256 |
|---|---|---|
| `assets/aqos-progress-tracker.html` | `7aca33b7618b0aea780ae6720e844d5d88f47a9341e1cc5065dfbe147d1d44ab` | `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa` |
| `config/refactor-milestones.json` | `b61171063683628d999ecf6b50f74e9e7bb37affe492ad4005b43e1861cb7cb4` | `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe` |
| `scripts/testing/test-dashboard-program-progress.py` | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` | same |
| `scripts/testing/harness_qa/phases/phase0.py` | `91979b59d7049f6cf1e5bc12a02115e315c33c89a1c3e09139303da30e6deee9` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` |

The embedded manifest/worklist hashes and current bytes are now exactly `b6117106…`/`143a4909…`. The Local-Embed-Context acceptance record reports a resolved candidate, but the projector has no matching committed subject, freeze record, or open LEC slice claim; the manifest and tracker therefore fail closed to `notstarted`/0 while retaining the candidate detail as explicitly non-authoritative. Its remaining task-registry drift is a separate subject. Any later mismatch is a hard stop, not justification to revive July 18 state.

## Scope lock

**Exact implementation ceiling: two existing files only.**

1. `scripts/testing/test-dashboard-program-progress.py`
2. `scripts/testing/harness_qa/phases/phase0.py`

The Phase-0 edit is limited to `0.10.40` current-projector token/description alignment. It retains the focused static invocation and every live HTTP/linkage check.

Out of scope: tracker HTML, manifest, dashboard runtime/header code, Service Coverage checks, Nix/services/deploy, Tier0, staging, commits, and every C0.3 record/index or staged path. C0.3's exact staged authorization-consumption record remains untouched.

## Required test contract

- Load `config/refactor-milestones.json` and use `scripts/ai/lib/refactor_status.py::project` to derive ordered track codes/statuses and Foundation A = `done`; do not duplicate historical literals.
- Parse embedded provenance and require exactly `manifest_ssot`, `governing`, `frozen_design_gate`, and `activation_evidence`; every path is unique and every SHA-256 equals current bytes. `PROJECTED_CURRENT_STATE` cannot use historical-source hash semantics.
- Derive expected counts from parsed tracker structures plus the projection: 19 included tracks, 4 active, 1 blocked, 0 pending Q decisions, 10 ratified authority rows, and 4 open High issues for this exact subject. Do not author an independent July 27 snapshot tuple.
- Preserve static self-contained/embed/tab/accessibility/header tests. Preserve `LiveHeaderTests` and negative header assertions in meaning: no `allow-same-origin`, no broader exception path, no weaker CSP/X-Frame checks.
- Add negative vectors: synthetic July-18 frozen state/source layout rejected; one tampered current source hash rejected; Foundation-A `blocked`/old-gate projection rejected.
- `phase0.py::_check_dashboard_program_progress` must require `PROJECTED_CURRENT_STATE` when inspecting a live asset. No other Phase-0 function may change.

## Acceptance and stop conditions

Only `python3 scripts/testing/test-dashboard-program-progress.py --static-only` may run, and it must pass all static cases including the negative vectors. Stop without broadening scope if tracker provenance is not equal to current listed-source bytes; request a fresh owner-bound tracker/manifest candidate instead. No live verifier, `aq-qa`, Tier0, deploy, stage, or commit is authorized.

An independent eligible reviewer must check the two-file inventory, pins, offline pass, retained live-header/Service Coverage behavior, negative vectors, and absence of C0.3 staged/index changes. Implementer self-acceptance is prohibited.
