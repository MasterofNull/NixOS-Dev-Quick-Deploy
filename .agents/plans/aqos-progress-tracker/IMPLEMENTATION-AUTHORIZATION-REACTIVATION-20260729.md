# AQ-OS Progress Tracker — Focused Test Re-pin Reactivation

**Status:** PREPARED_ONLY — single-use, inactive  
**Authorization ID:** `aqos-progress-tracker:focused-test-repin:reactivation:20260729`  
**Exact HEAD:** `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`  
**Superseded expired authorization:** `9d3e4cf717a63ddfedc543046e6fdbbabead9da5efc9638c856ac56252c50e2c`

This document reactivates no work by itself. It preserves the reviewed focused
tracker test re-pin and rebinds only the Phase-0 input changed by independently
accepted C0.6 candidate work.

## Exact subject pins

| Subject | SHA-256 |
|---|---|
| design packet | `9883ad9a919152060cdae454d791b446b0191aadf4c9a6d5942cb591f7d29ed1` |
| tracker candidate | `7aca33b7618b0aea780ae6720e844d5d88f47a9341e1cc5065dfbe147d1d44ab` |
| manifest candidate | `b61171063683628d999ecf6b50f74e9e7bb37affe492ad4005b43e1861cb7cb4` |
| focused test input | `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7` |
| Phase-0 input | `aa74c5c3dd2c3d0121cc34a18246aa0127e8a953d10045dd0fb1f775f5c9f9a7` |

## Activation contract

Activation requires an independent exact-subject `PASS`, followed by an owner
statement binding this document's final SHA-256, the exact HEAD above, one
implementer identity, one independent reviewer identity, and a UTC activation
window no longer than 24 hours. Any subject, HEAD, identity, or time-window
drift voids this authorization; no partial rebase or replay is allowed.

## Exact ceiling and retained obligations

Only these two existing files may change:

1. `scripts/testing/test-dashboard-program-progress.py`
2. `scripts/testing/harness_qa/phases/phase0.py`, limited strictly to
   `_check_dashboard_program_progress`

The implementation must retain the reviewed current-projector provenance,
negative-vector, live-header, and Service Coverage requirements. It must stop
if current source hashes do not match the pinned tracker provenance or if the
repair requires any broader change.

Only the focused `--static-only` suite, Python syntax using `/tmp` bytecode,
exact hashes, inventory, and `git diff --check` are permitted. Independent
acceptance of the final exact candidate hashes is required; the implementer
may not self-accept.

Forbidden: edits to tracker HTML, milestone manifest, dashboard/runtime/header
code, Service Coverage behavior, any C0.3 record/index/staged content, any
other Phase-0 function, Nix, services, live calls, browser/provider/network or
database/process actions, `aq-qa`, Tier0, deployment, staging, or commit.
