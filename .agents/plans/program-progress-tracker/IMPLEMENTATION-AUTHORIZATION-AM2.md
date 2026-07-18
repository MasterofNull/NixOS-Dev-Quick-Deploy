# Implementation Authorization AM2 — Same-Origin Dashboard Closure

Authorization ID: `auth-program-progress-tracker-r0-am2-20260718`
Parent: `auth-program-progress-tracker-r0-am1-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**

## Trigger

Final cold-browser review of the AM1 candidate found that the tracker itself is self-contained, but
embedding it in the Command Center triggers successful off-origin Google Fonts requests sourced by
`dashboard.html`. Earlier browser evidence omitted static resources, so the literal accepted gate—no
request leaves the dashboard origin at either direct or embedded tracker URL—remains unsatisfied.

This amendment closes the pre-existing dashboard privacy gap. It does not reinterpret or weaken the
accepted criterion.

## Exact predecessor and two-file lease

Editable:

1. `dashboard.html`
   `70d32201d348408c0fb068d3f5af4b20354dd219b5e65b5221e29b4fc5579736`;
2. `scripts/testing/test-dashboard-program-progress.py`
   `4e15ff3878dabebdbfc8a68882c2e44baf77d531636c4396133e924bf79c72f8`.

Frozen and byte-immutable:

3. `assets/aqos-progress-tracker.html`
   `238341c4fc804036b6e4404fc8ea4a24a0ca0219da88db311d2b904144116dc2`;
4. `assets/dashboard.js`
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
5. `dashboard/backend/api/main.py`
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
6. `scripts/testing/harness_qa/phases/phase0.py`
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

Any predecessor mismatch before the first write is a hard stop.

## Exact correction grant

One monitored implementer may:

- remove the two remote Google Fonts link elements from `dashboard.html`;
- use explicit local system font stacks for the existing `--font` and `--hud` variables, preserving
  legibility without adding a font asset or network dependency;
- add focused static regressions proving the dashboard contains no off-origin `src`, `href`, CSS
  import, or font URL; and
- retain every existing AM1 base-URL, header, manifest, iframe, ARIA, keyboard, and state assertion.

The frozen tracker provenance manifest does not contain the focused-test digest, so no tracker refresh
is necessary or authorized. The implementer must not edit the tracker asset, dashboard JavaScript,
`main.py`, Phase0, any vendor asset, or any third file; must not fetch or vendor a font; and must not
stage, commit, deploy, subdelegate, or
self-review. `PULSE.log` remains frozen throughout candidate and acceptance review.

## Acceptance

Acceptance requires:

- all six final hashes and exact two-file AM2 diff;
- complete focused suite against `http://127.0.0.1:18889`;
- Python/HTML/JavaScript/diff and frozen eight-source manifest checks;
- Phase-0 `0.10.40` on the candidate server;
- exact tracker `SAMEORIGIN/self` and non-tracker `DENY/none` headers;
- a cold real-browser load of the embedded Program tab with `requests --static` proving every request
  uses the candidate dashboard origin;
- zero console errors/warnings, populated iframe, keyboard/ARIA behavior, 360-pixel no-overflow, and
  reduced-motion `0s`;
- Tier 0; and
- independent exact-subject `PASS`.

No dashboard redesign, new asset, CSP change, route/API/database/service/Nix/deployment change,
tracker content/count/status update, Foundation B2 activity, or third file is authorized. The first
completed exact two-file report consumes AM2.

`RECORD: prepared same-origin dashboard closure; inactive pending independent review.`
