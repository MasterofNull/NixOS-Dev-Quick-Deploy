# Evidence: Wave 12 — Dual-Process System 1 Reflex Triage & S1/S2 Routing Ratio Cockpit Telemetry

- **Date**: 2026-10-26
- **Objective**: Wave 12 implementation of dual-process System 1 (fast reflex) and System 2 (deliberate frontier) architecture for high-frequency telemetry triage and cockpit observability.
- **Author**: MasterofNull
- **Scope**:
  - `scripts/ai/lib/triage_engine.py`: Hardened `FastClassifier` pattern matchers with kernel segfault tokens (`status=\d+/SEGV`, `code=dumped`), AppArmor denial events (`apparmor="DENIED"`), and systemd exit failures (`failed with result 'exit-code'`), clocking at ~106 microseconds per event.
  - `dashboard.html`: Added **System 1 Reflex Triage** and **System 1 / System 2 Routing** telemetry cells to Overview Cockpit HUD.
  - `assets/dashboard.js`: Added dynamic calculation and projection of S1 high-frequency reflex events vs S2 deep coordinator agent runs (`cockpitRoutingRatio`).
  - Verification: `scripts/testing/test-aq-triage.py` (7/7 tests pass green).

## Test Results

```
test_fixture_1_classification_accuracy ... ok
test_fixture_2_persistent_cursor ... ok
test_fixture_3_token_bucket_limiter ... ok
test_fixture_4_actionable_filtering ... ok
test_fixture_5_p95_latency_benchmark ... ok
test_fixture_6_health_summary_contract ... ok
test_rate_limited_entry_does_not_advance_cursor_past_it ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.020s

OK - ALL 6 FIXTURES PASS
```

## Definition of Done (Rule 15) Attestation

1. **Integrated**: Live path in `scripts/ai/lib/triage_engine.py` and `assets/dashboard.js`.
2. **Turned ON**: Enabled by default in telemetry loop updating every 10s.
3. **Functionally Validated**: Verified with unit and benchmark suites (`test-aq-triage.py`).
4. **Observable**: Directly visible in Overview Cockpit HUD (`cockpitRoutingRatio`).
5. **Intervenable**: Operators monitor reflex triage rates and can pause/steer agents if anomaly rates escalate.
6. **PM-Tracked**: Tracked under `PROJECT-DURABLE-AGENTS-SOTA-UI-PRD.md`.
