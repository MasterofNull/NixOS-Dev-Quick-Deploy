# Independent Review — Program Tracker AM1 Authorization

Review date: 2026-07-18 UTC
Reviewer: Codex sub-agent `/root/tracker_authorization_review`
Role: independent architecture, security, SRE, and test-contract reviewer
Subject: `.agents/plans/program-progress-tracker/IMPLEMENTATION-AUTHORIZATION-AM1.md`
Subject SHA-256: `7f54339687660d4c56545beac3853d56090fb3cb665f07c6c79a5f2764de5a80`

## Trigger and predecessor verification

The trigger binds the exact independent `REQUEST_REVISION` artifact:

- `.agents/plans/program-progress-tracker/IMPLEMENTATION-ACCEPTANCE.md`
  `4c58816ead98724572d53a6f74e1298a3768a473bcfcd3a638c5f209f18341a0` — match.

All six candidate predecessor hashes reproduce exactly:

1. editable focused test:
   `a862cf9d510daee4207ee96fb0e4157e98991c444c9cae0c483ebcc938e0c0be`;
2. editable tracker asset:
   `b1176738885407268d3bf1250376454d4aa5ace4cc0a39aa82815c453d08c628`;
3. frozen `dashboard.html`:
   `70d32201d348408c0fb068d3f5af4b20354dd219b5e65b5221e29b4fc5579736`;
4. frozen `assets/dashboard.js`:
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
5. frozen `dashboard/backend/api/main.py`:
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
6. frozen `scripts/testing/harness_qa/phases/phase0.py`:
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

Any drift still suspends the grant before its first write.

## Contract adjudication

- **Two-file lease:** PASS. Only the focused test and tracker asset are writable. The other four
  candidate files are byte-frozen, and a third file is an explicit stop condition.
- **Exact defect correction:** PASS. The grant requires an explicit candidate `--base-url`, binds the
  live test to the parsed value, and preserves case-insensitive HTTP header semantics. It retains the
  exact positive `SAMEORIGIN`/`frame-ancestors 'self'` assertions and both global-deny negatives.
- **Regression strength:** PASS. The implementer must prove explicit ephemeral URL selection and
  lower-case Uvicorn response fields while leaving expected security values unchanged. This corrects
  the verifier rather than weakening the middleware contract.
- **Provenance refresh:** PASS. The current issue backlog is
  `078061ca76817b2f78554fafa6604c9ddd3be2e6b5427912a36fc32b86811b57` and contains both required
  `provider-capacity-reset-not-scheduled` and `playwright-cli-wrapper-config-version-skew` records.
  The asset still carries the earlier issue-backlog digest, so AM1 correctly requires a just-in-time
  refresh. It permits only genuine source-byte digest changes—the focused test and issue backlog—and
  prohibits changes to status, count, timestamp meaning, or tracker content.
- **PULSE freeze:** PASS. Current `.agent/collaboration/PULSE.log` is
  `d67d06e59e6ef464d23ed8d593b2561a2fc829691f9c0c685b1aeaefab55516f`, matching the digest already
  embedded in the asset. The authorization prohibits orchestrator mutation between final provenance
  refresh and independent acceptance. This review does not mutate PULSE.
- **Acceptance preservation:** PASS. Complete focused live tests against the named candidate, all
  eight provenance digests, Phase-0 `0.10.40`, exact positive/negative headers, browser origin and
  console checks, responsive/keyboard/reduced-motion checks, Tier 0, and a new independent six-hash
  PASS remain mandatory.
- **No weakening or scope expansion:** PASS. Middleware, CSP, dashboard integration, Phase0,
  services, deployment, Nix, API/database, counts/statuses, and Foundation B2 remain excluded. The
  implementer cannot stage, commit, deploy, subdelegate, or self-review.

The grant is a minimal verifier correction and provenance consequence, not a reopening of the
application implementation. No candidate file or collaboration projection was edited during review.

VERDICT: PASS — AM1 is an exact two-file recovery lease that corrects candidate targeting and header-case handling without weakening security, provenance, browser, Phase-0, or Tier-0 acceptance gates
