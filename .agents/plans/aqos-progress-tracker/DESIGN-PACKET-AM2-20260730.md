# AQ-OS Progress Tracker AM2 — C2-Aware Current-Head Re-freeze

Status: `PREPARED_FOR_INDEPENDENT_REVIEW`  
Prepared: 2026-07-30 UTC  
Base HEAD: `97131faac372e89273f14372edbfa5e52b816d64`

## Objective

Restore the user-facing progress tracker and live Phase-0 check to current
project truth after:

- Track S S0-A shipped in `50d5630b87a235e72668fabc73205c92353b27c3`;
- Foundation C2 shipped default-OFF in
  `97131faac372e89273f14372edbfa5e52b816d64`; and
- the prior AM1 design became stale before activation.

AM2 replaces, rather than replays, AM1. It does not authorize implementation,
staging, commit, deployment, flag activation, Nix changes, or runtime mutation.

## Exact four-file ceiling

Only these existing implementation files may change under a later exact
authorization:

1. `config/refactor-milestones.json`
2. `assets/aqos-progress-tracker.html`
3. `scripts/testing/test-dashboard-program-progress.py`
4. `scripts/testing/harness_qa/phases/phase0.py`

Current primary-worktree hashes:

| Path | SHA-256 |
|---|---|
| `config/refactor-milestones.json` | `b61171063683628d999ecf6b50f74e9e7bb37affe492ad4005b43e1861cb7cb4` |
| `assets/aqos-progress-tracker.html` | `7aca33b7618b0aea780ae6720e844d5d88f47a9341e1cc5065dfbe147d1d44ab` |
| `scripts/testing/test-dashboard-program-progress.py` | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` |
| `scripts/testing/harness_qa/phases/phase0.py` | `aa74c5c3dd2c3d0121cc34a18246aa0127e8a953d10045dd0fb1f775f5c9f9a7` |

Clean-HEAD baselines:

| Path | SHA-256 |
|---|---|
| manifest | `42e9780e639f593b15c7b7a1bc22a13e5bffbad87051909add6ae0f84def3cbe` |
| tracker | `afb4630d790eeba75b839e36da7b1feee270935597bcc8d9a22127f1d8b6d0fa` |
| focused test | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` |
| Phase-0 | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` |

`assets/dashboard.js` and all external dirty plan/worklist files are excluded.

## Shared Phase-0 release projection

The primary `phase0.py` contains unrelated checks `0.10.42` and `0.10.43`.
Those bytes are foreign and must be preserved but excluded from the release.
The only authorized Phase-0 delta is inside
`_check_dashboard_program_progress` / check `0.10.40`:

```text
-    if "FROZEN_IMPLEMENTATION_SNAPSHOT" not in body:
+    if "PROJECTED_CURRENT_STATE" not in body:
```

Clean HEAD plus only that replacement must hash to:

`7bfc9119822c72493911d29d85c69d9ef1826974195c45e327a73f87152ed182`

Acceptance and release operate on this clean-HEAD projection, never the whole
dirty Phase-0 file.

## Required projected truth

### Track S

- Keep Track S `active`, because S0-B through S5 remain queued.
- Add an exact case-insensitive commit matcher for
  `feat(security): add defensive capability intake contract`.
- State that S0-A is independently accepted and shipped in `50d5630b`.
- Remove the resolved capability-intake-schema and stale-tracker-test issues.

### Foundation C2

- Add an exact case-insensitive commit matcher for
  `feat(foundation-c): C2 tool-lease enforcement gate`.
- Project C2 as `done/100`, not active or “implementation not started”.
- State that C2 shipped in `97131faa` with
  `CAPABILITY_LEASE_ENFORCEMENT=0` default-OFF.
- State explicitly that no flag, Nix, live-traffic, or cutover activation is
  authorized.
- Preserve a High issue named
  `foundation-c2-post-release-contract-gaps`, covering:
  - missing Env SSOT declarations for `CAPABILITY_LEASE_ENFORCEMENT` and
    `AQ_LEASE_POLICY_EPOCH`;
  - missing aq-qa integration and dashboard Service Coverage;
  - degraded safe-read classification of network-backed/sensitive tools; and
  - reconciliation of the seven-path release with the original five-path
    implementation ceiling.

Expected counts after projection:

| Field | Value |
|---|---:|
| tracks | 19 |
| active tracks | 3 (`C`, `S`, `AAF`) |
| blocked tracks | 1 (`V`) |
| pending Q decisions | 0 |
| authority rows | 10 |
| open High issues | 4 |

## Provenance and hermetic binding

Preserve the four source classes and their exact current pins:

| Source | Class | SHA-256 |
|---|---|---|
| `config/refactor-milestones.json` | `manifest_ssot` | recompute after AM2 edit |
| `.agents/plans/unified-program/OWNER-DECISION-SHEET.md` | `governing` | `502df009ac486ab514351105a57d2a75ab21efd747a95f2c92bf36ea37c633b1` |
| `.agents/plans/aqos-foundation-c/C2-FREEZE-AND-ACTIVATION.md` | `frozen_design_gate` | `f9cee73b5cb69d3a76554db7388f1ff0a1d62dc98837fa0bfef791930ed24579` |
| `.agents/plans/unified-program/ACTIVATION-AND-CLOSEOUT-WORKLIST.md` | `activation_evidence` | `0ceeaa31537d5ebd9c6b3e25576de888de98fa93f7242e8cca1c720700d5fb34` |

The `activation_evidence` pin is the clean-HEAD byte source. The AM2 candidate
must not read, summarize, or derive state from the excluded dirty worktree copy
whose digest is `143a4909c3f0f1196c4e60e04b5658131ad2cbd9df66f602f6c4ebd2fd35a8f6`.

The closed `projection_binding` must contain:

- `git_head`: `97131faac372e89273f14372edbfa5e52b816d64`;
- `projector_sha256`:
  `edc6ee248b0f09d6552a064a040b9545b279f8772889c64d5c7989297641599b`;
- `normalized_projection_sha256`: SHA-256 of canonical JSON for
  `strip_updated(refactor_status.project(...))`, computed after the manifest
  edit in an isolated single-ref candidate repository.

The final digest must be computed, never guessed. Validation fails on any
additional Git ref, untracked event/claim input, source drift, or normalized
projection mismatch.

## Focused oracle

The focused test must:

- derive ordered track state and counts from the bound projector result;
- validate all source classes, exact pins, and projection binding;
- reject stale July-18 state;
- reject tampered source pins or normalized projection;
- reject a false return to Foundation A blocked;
- reject C2 as non-shipped, active, flag-on, or activation-authorized;
- reject missing C2 residual High issue; and
- reject S0-A as pending/uncommitted.

## Validation and Service Coverage

Offline candidate acceptance requires:

```text
PYTHONPYCACHEPREFIX=/tmp/aq-tracker-am2-pycache python3 scripts/testing/test-dashboard-program-progress.py --static-only
PYTHONPYCACHEPREFIX=/tmp/aq-tracker-am2-pycache python3 scripts/testing/test-refactor-status.py
python3 -m py_compile scripts/testing/test-dashboard-program-progress.py scripts/testing/harness_qa/phases/phase0.py
git diff --check
scripts/governance/tier0-validation-gate.sh --pre-commit
```

The focused tests and ordinary hook must pass in the exact release projection.
Before deployment, Tier-0 may still report the existing live `0.10.40` failure;
it must introduce no new failure and must not be represented as a full PASS.

A separately authorized deployment then must make both commands exit `0`:

```text
python3 scripts/testing/test-dashboard-program-progress.py
aq-qa 0 --machine
```

The live gate is required before tracker operational closeout and before the
C0.3 Stage-2 recovery commit, whose reviewed authorization permits no Tier-0
waiver.

## Stop conditions

Stop on any HEAD/source/projector drift, fifth implementation path, dashboard
JavaScript edit, Phase-0 edit outside `0.10.40`, lost foreign bytes, incorrect
C2 or S0-A state, missing residual issue, C2 flag-on implication, unbound
dynamic projection, failed negative vector, new Tier-0 failure, or need for
deployment/network/runtime mutation during implementation acceptance.

## Next gate

An independent reviewer must PASS this exact design. Only then may a
single-use, design-hash-bound AM2 implementation authorization be prepared for
owner activation. Implementation, staging, commit, deployment, and push remain
unauthorized.
