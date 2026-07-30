# AQ-OS Progress Tracker — Focused Test Re-pin Authorization

**Status:** PREPARED_ONLY — single-use, inactive  
**Authorization key:** `aqos-progress-tracker:focused-test-repin:v1:20260727`  
**Build base:** `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`

## Authorized objective

After named owner activation, repair focused tracker test/Phase-0 parity only. The work validates current projector truth and exposes stale/tampered provenance; it must not restore the July 18 frozen state.

## Exact subject pins

| Subject | SHA-256 |
|---|---|
| design packet | `9883ad9a919152060cdae454d791b446b0191aadf4c9a6d5942cb591f7d29ed1` |
| tracker candidate | `7aca33b7618b0aea780ae6720e844d5d88f47a9341e1cc5065dfbe147d1d44ab` |
| manifest candidate | `b61171063683628d999ecf6b50f74e9e7bb37affe492ad4005b43e1861cb7cb4` |
| focused test | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` |
| Phase-0 module | `91979b59d7049f6cf1e5bc12a02115e315c33c89a1c3e09139303da30e6deee9` |

## Activation prerequisites

1. Owner binds this authorization's final hash, exact current HEAD, implementer, independent reviewer, and a window of at most 24 hours.
2. Implementer recomputes every pin before editing. Any drift voids the authorization; no partial rebase.
3. Implementer verifies every tracker provenance hash against current source bytes. The frozen candidate is exact at preparation time; any later mismatch is a stop with no partial rebase.
4. Confirm the C0.3 staged authorization-consumption record/index remains unchanged and excluded.

## Ceiling and exclusions

Allowed modifications exactly: `scripts/testing/test-dashboard-program-progress.py`; and `scripts/testing/harness_qa/phases/phase0.py`, only `_check_dashboard_program_progress`.

Forbidden: tracker HTML, milestone manifest, dashboard/runtime/header code, Service Coverage checks, C0.3 record/index/staged content, Nix, services, live calls, Tier0, deployment, staging, and commit.

## Required evidence

- Offline `--static-only` focused PASS including stale-snapshot, tampered-hash, and stale-Foundation-A negative vectors.
- Diff proves the two-file ceiling and Phase-0 token/description-only delta.
- Independent reviewer returns `VERDICT: PASS|FAIL|REQUEST_REVISION` against exact resulting hashes. A PASS does not commit or activate C0.3.
