# Implementation Authorization — AQ-OS Program Progress Tracker

Authorization ID: `auth-program-progress-tracker-r0-20260718`
Idempotency key: `dashboard:program-progress-tracker:r0:20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: the owner explicitly required the supplied tracker to become the default project progress
display linked and embedded in AI Command Center, and preauthorized bounded slices needed to finish.

## Frozen design and content inputs

- PRD `204b2b473efe0da3a0d7e27c8b0c70c49f300f04af4ca57c6c916724f2e6e50c`;
- plan `5cd4b395719f3989b772ff2956ced8e9d509c338958ee7018454aac0736267c9`;
- independent design review `4733c245aab081dd96e9b59f033cb5552a28f55d605ec5194889a1c025d07e45`;
- supplied/revised prototype
  `/tmp/claude-1000/-home-hyperd-Documents-NixOS-Dev-Quick-Deploy/6b22f540-d284-4347-ae04-89f4330ae059/scratchpad/aqos-progress-tracker.html`
  SHA-256 `7a8699c1425d1c16f952b8c6d4de09ef972d8c66b6be3409cba3350c7d848050`.

The eight provenance hashes embedded in that prototype match current disk at authorization issuance.
Before writing the repo asset, the implementer must regenerate them and stop on any mismatch rather
than publishing stale counts/status.

Prior overlapping leases are released by
`.agents/plans/program-progress-tracker/PRIOR-LEASE-RELEASE-AUDIT.md`. The implementer must verify that
audit's exact hash from the independent authorization review before assignment and must stop if any
other writer or hash drift is present.

## Frozen six-file lease

1. `assets/aqos-progress-tracker.html` — **ABSENT**.
2. `dashboard.html`
   `3bf6301bfad997f473a02fcad82e5720b9ac902daf68736ddc92db13bbe797a9`.
3. `assets/dashboard.js`
   `6ce40c022b07f5e69d2e5748e2efd6492f547c5d04d80d23b1ef79a9b12ce4c2`.
4. `dashboard/backend/api/main.py`
   `9e0a35c568ba5dd174c6f13c6e7380c0b74a7109b737d64c1687715a12e5fd5a`.
5. `scripts/testing/test-dashboard-program-progress.py` — **ABSENT**.
6. `scripts/testing/harness_qa/phases/phase0.py`
   `63a0ae47b83e92556b93c3660f940d2b117b7074c178869db5a9c56274460dd3`.

Any mismatch or new lease is a hard stop.

## Exact grant

One bounded implementer may edit/create only the six files above to implement the accepted design:

- publish the revised tracker asset with just-in-time provenance and explicit-state counts;
- show Foundation owner adjudication/projection as complete while retaining ten convergence blockers,
  generic flake/package baseline as complete, and nine owner decisions pending after Q8 direction;
- add the Program tab/panel, exact `sandbox="allow-scripts"`, title, direct full-page link, responsive
  embed, ARIA roles/state/controls, roving focus, and keyboard navigation;
- add a path-exact response-header exception only for `/assets/aqos-progress-tracker.html`, using
  `SAMEORIGIN` and `frame-ancestors 'self'`, while every other response retains `DENY` and
  `frame-ancestors 'none'`;
- add focused deterministic provenance/header/DOM/accessibility/security tests; and
- register a Phase-0 integration check exercising the real asset and dashboard path.

Acceptance requires HTML/JS/Python syntax, focused tests, Phase0, Tier0, live dashboard/asset HTTP,
exact positive and negative headers, no off-origin browser requests, no console errors, populated
iframe, keyboard flow, narrow viewport, and reduced-motion checks. If the local browser runtime is
unavailable, implementation may finish but acceptance remains blocked until an independent reviewer
produces live browser evidence.

## Consumption and exclusions

The first completed exact six-file report consumes this grant. Interruption without completion does
not. The orchestrator may assign exactly one implementer through a monitored delegation route; that
implementer may not subdelegate, stage, commit, deploy, or self-review. Independent exact-subject
acceptance is mandatory.

No new API route/database, Nix/AppArmor/service, broad CSP relaxation, unsafe iframe token, external
network content, live system deployment, seventh file, or mutation of the temporary prototype is
authorized.

`RECORD: prepared single-use six-file program-tracker implementation lease.`
