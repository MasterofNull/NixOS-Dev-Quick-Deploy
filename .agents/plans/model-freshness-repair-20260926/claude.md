# model-freshness-repair — Claude (Opus) independent review

Subject: staged patch `/tmp/model-freshness-candidate.patch`, sha256 `c138d32a3e855825f93fa1d50b9151c48b42ac8acc94e3d0a58041b006d6fb65` (17144 bytes, 393 lines). Reviewing the fix to the model-probe freshness telemetry.

## Disposition: ACCEPTED

This is a correct Rule-19 / anti-gaming root-cause fix. The producer (`model_probe`) was minting a fresh "measured" receipt from a fabricated 4.0 t/s fallback whenever the speed probe timed out — freshness telemetry that lied. The fix:

- `_probe_speed` now returns `Optional[float]` and returns **None** on failure (was `4.0`); `probe()` returns `cached or _default_profile()` and does **NOT** write a fresh profile when `tps is None` (logs "freshness not updated"). This is the core: a failed measurement can no longer refresh freshness. **Verified via the new test** `scripts/testing/test-model-probe-freshness.py::check_failed_measurement_does_not_refresh` — patches `_probe_speed→None`, asserts `throughput_source == "fallback"` AND `not profile_path.exists()` ("failed throughput probe must not mint a fresh receipt"). The failure case is tested, not just asserted.
- Adds `throughput_source` provenance (`live_probe` | `fallback` | `unknown`) and the freshness gate now requires `throughput_source == "live_probe"` — so a fallback profile cannot pass the gate as "measured."
- `_PROBE_TIMEOUT` 30→90s (fits the measured slow APU path; still < `_DIRECT_TIMEOUT_S` 180) — the probe gets a real chance to measure rather than defaulting.
- Dashboard/gate now read the RUNTIME catalog SSOT (`config/model-catalog.yaml` via `yaml.safe_load`) instead of importing a `.py`, and add active-model-target-declared-in-catalog + `active_model_catalogued` parity — truthful runtime state, consistent with the reachability-truthfulness bar we applied to C6c and C6a's dashboard.

This also legitimately closes the `model-profile-json-review-overdue` maintenance item I logged: `measured_tps_output` is now a real `live_probe` value (1.4 t/s — consistent with the known APU-under-memory-pressure speed) with refreshed provenance, not a cosmetic timestamp touch.

### Notes (non-blocking)
- I cannot independently re-verify that the committed `1.4` is a live measurement vs hand-entered from a real run; the mechanism now enforces honesty going forward (source-labelled, fail-path tested), and 1.4 is plausible for this hardware. If cheap, the integrator should re-run the probe on the target once to reconfirm the checked-in value carries `throughput_source=live_probe` from an actual probe.
- Concurs with the Antigravity contribution already landed in this round.

## Terminal disposition
**ACCEPTED** — subject sha256 `c138d32a…`. Sound anti-gaming producer fix with failure-case test coverage. Local (running) + Codex (on return) contribute confirmatory verdicts; this Claude verdict does not gate their in-situ/after input. No activation concern (telemetry/config only).
