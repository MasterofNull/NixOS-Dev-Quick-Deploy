# Implementation Authorization AM1 — Tracker Candidate Live-Test Correction

Authorization ID: `auth-program-progress-tracker-r0-am1-20260718`
Parent: `auth-program-progress-tracker-r0-20260718` at commit `d9bdf965`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**

## Trigger and accepted evidence

Independent acceptance
`.agents/plans/program-progress-tracker/IMPLEMENTATION-ACCEPTANCE.md` SHA-256
`4c58816ead98724572d53a6f74e1298a3768a473bcfcd3a638c5f209f18341a0`
reproduced the complete six-file candidate and issued `REQUEST_REVISION` for exactly two focused-test
defects:

1. the live test hardcodes the deployed port, so it cannot name the undeployed candidate server; and
2. it converts case-insensitive HTTP headers to a case-sensitive dictionary before title-case lookup.

The review independently passed the candidate app, exact positive/negative headers, Phase-0 check,
populated same-origin iframe, zero browser warnings/errors, same-origin-only tracker requests,
360-pixel layout, and reduced-motion behavior. Those passing observations remain evidence, not an
acceptance override.

## Exact predecessor and two-file lease

Editable:

1. `scripts/testing/test-dashboard-program-progress.py`
   `a862cf9d510daee4207ee96fb0e4157e98991c444c9cae0c483ebcc938e0c0be`;
2. `assets/aqos-progress-tracker.html`
   `b1176738885407268d3bf1250376454d4aa5ace4cc0a39aa82815c453d08c628`.

Frozen and byte-immutable:

3. `dashboard.html`
   `70d32201d348408c0fb068d3f5af4b20354dd219b5e65b5221e29b4fc5579736`;
4. `assets/dashboard.js`
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
5. `dashboard/backend/api/main.py`
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
6. `scripts/testing/harness_qa/phases/phase0.py`
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

Any predecessor mismatch before the first write is a hard stop.

## Exact correction grant

One monitored implementer may:

- add an explicit `--base-url` option with a safe loopback production default and bind
  `LiveHeaderTests` to the parsed value;
- preserve case-insensitive header semantics or normalize keys to lowercase before assertions;
- keep exact `SAMEORIGIN`/`frame-ancestors 'self'` positive assertions and both
  `DENY`/`frame-ancestors 'none'` negative assertions;
- add focused regression assertions proving explicit candidate URL selection and lower-case Uvicorn
  response fields pass without weakening expected values; and
- refresh the asset's frozen provenance manifest only for source bytes that genuinely changed since
  the prior snapshot: the focused-test digest and the mandatory issue-backlog drift recording the
  provider-capacity and Playwright-wrapper defects. Every source digest must be regenerated and
  reconciled just before the candidate report; no status/count/content change is authorized.

The implementer may not modify any third file, stage, commit, deploy, subdelegate, or self-review.
The orchestrator must not mutate `PULSE.log` between the final provenance refresh and independent
acceptance.

## Acceptance and exclusions

Acceptance requires:

- complete focused suite against an explicitly named ephemeral candidate URL;
- Python/HTML/diff checks and full eight-source manifest reconciliation;
- Phase-0 `0.10.40` bound to the same candidate server;
- exact live positive/negative headers;
- retained browser, origin, console, responsive, keyboard, and reduced-motion evidence;
- Tier 0; and
- a new independent exact-subject `PASS` over all six candidate hashes.

No change to counts, statuses, snapshot meaning, dashboard integration, middleware, Phase0 code,
runtime service, Nix/deployment, API/database, CSP policy, Foundation B2, or any third file is
authorized. The first completed exact two-file report consumes AM1.

`RECORD: prepared two-file tracker live-test correction; inactive pending independent review.`
