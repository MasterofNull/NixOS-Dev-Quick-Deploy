# Evidence: QA phase 0 failures behind attn-9c6db03141754961 (2026-11-11)

## Objective
Diagnose the five failing phase 0 checks the health monitor reported as one CRITICAL alert, and fix the producers. Branch `fix/qa-phase0-failures`, based on 189c8b0d7.

## Per-check result

| Check | Root cause | Fix | Verification |
|---|---|---|---|
| 0.1.2 failed units | `ai-mcp-integrity-check.service`: baseline not refreshed after the manual rebuild that followed #733 (route_handler.py changed). `ai-sync-knowledge-sources`: DNS failure. | None here. The check is correct. Owner refreshes the baseline; retry for sync is another slice (8cd0c6af7). | Not re-run (needs live units, no systemctl). |
| 0.10.5 freshness | Live checkout is on 1b2c3111d, whose `config/model-profile.json` has `reviewed_at`/`probed_at` 2026-09-26: 46 days against a 45 day window. #741 (f064969e8) refreshed both to 2026-11-10, so the test passes at 189c8b0d7. Separately, the monitor mapped severity by failure count only, so a pure expiry signal joined real failures and pushed the alert to critical. | `scripts/health/ai-stack-health-monitor.py`: check ids in `_FRESHNESS_CHECK_IDS` (0.10.5) leave the outage alert and raise their own `severity=medium` maintenance alert (`dedup_key qa-phase-0-freshness`) with the action. Matched by id only, so a real failure whose text says "expired" is never hidden. Test added in `test-ai-stack-health-monitor.py`. | Test passes. Not hidden: failure still listed and still counted in phase results. |
| 0.10.48 worktree isolation | Not a product change. `git diff 1b2c3111d 189c8b0d7` of the test adds only the base-selection block; handback behaviour is unchanged. The assertion at ~201 follows a fixed 100 x 0.05 s = 5 s poll for the asynchronous background handback, which starved under phase 0 load (load average 8 to 10). | Poll until a 60 s monotonic deadline; the assertions are unchanged. | Passes at 189c8b0d7 (3 runs, 2 of them under 6 busy loops). The failure was not reproduced, so the load cause is inferred from the code, not proven. The 04:22Z monitor run no longer reports it. |
| 0.10.54 C6c | Hypothesis of an expired fixed date is refuted: `_build_signed_bump` builds `issued_at`/`expires_at` from `datetime.now()` with a 3600 s TTL, and there is no fixed date in the test or the authority. | None. | Passes 4 times, and under libfaketime `+40d` via `aq-tool libfaketime -f "+40d"` (clock confirmed shifted to 2026-12-21). Root cause of the one-off `bump-expired` is not determined; the 04:22Z monitor run no longer reports it. |
| 0.10.66 aq-confine | Already fixed on main by 189c8b0d7. The monitor runs with `TMPDIR=<repo>/.agents/tmp`; the old test created its scratch dir there, outside the `/tmp` tmpfs aq-confine mounts, so sandbox fixtures failed. | None needed (`dir="/tmp"`). | Old test on 1b2c3111d with `TMPDIR=.agents/tmp`: 8+ FAIL lines matching the alert. At 189c8b0d7 with the same TMPDIR: `SUMMARY: 213 checks ran, 0 failed`. |

Alert text lists 0.10.5, 0.10.48, 0.10.54, 0.10.66 and 0.1.2: that is the five.

## Extra finding
`test-ai-stack-health-monitor.py` already failed on main: it asserted the literal strings `490` and `768M` in the unit, but the Nix unit has `TimeoutStartSec = "765"` and (since 189c8b0d7) `MemoryMax = "1280M"`. It now parses the numbers and asserts `>= 490` and `>= 768`, the stated intent.

## Fixed-date scan of `scripts/testing/` (within 90 days of 2026-11-11)
Dates found: 2026-11-14 (ffmpeg, clock pinned via GRYPE_IGNORE_TODAY), 2026-11-15 (activation-signer deferral text, never compared to now), 2026-12-31 (state-authorities with pinned FIXED_DATE; capability-lease and asymmetric-lease with pinned clocks). Run at `+60d` under libfaketime: activation-signer, state-authorities, capability-lease, asymmetric-lease-authority and ffmpeg-cve-mitigations all rc=0. No clear next time bomb, nothing to fix. Intentional time-dependent: `test-model-catalog-freshness.py` fails at `+60d` by design (45 day window): the profile goes stale about 2026-12-25.

## Commands
```bash
python3 scripts/testing/test-model-catalog-freshness.py
python3 scripts/testing/test-worktree-isolation.py
python3 scripts/testing/test-c6c-owner-submission-service-coverage.py
AQ_CONFINE_REQUIRE=1 python3 scripts/testing/test-aq-confine.py
python3 scripts/testing/test-ai-stack-health-monitor.py
scripts/governance/tier0.d/check-ci-test-coverage.sh   # PASS (777 tests: 655 declared, 122 exempt)
```

## Owner actions
- Refresh the MCP integrity baseline (0.1.2).
- Re-probe and re-review the model profile before about 2026-12-25 (maintenance, now a medium alert).
- Merge this branch and deploy so the live checkout has 189c8b0d7 and #741.

## Not verified
Full `harness_qa` phase 0 and the monitor itself under systemd were not run; 0.10.48 and 0.10.54 failures were not reproduced.
