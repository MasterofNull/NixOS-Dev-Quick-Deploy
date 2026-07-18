# Independent Implementation Acceptance — AQ-OS Program Progress Tracker

Review date: 2026-07-18 UTC
Reviewer: Codex sub-agent `/root/tracker_authorization_review`
Role: independent frontend, accessibility, security, and SRE acceptance reviewer
Authorization commit: `d9bdf965`
Verdict: **REQUEST_REVISION**

## Exact frozen subject

All six implementer-reported SHA-256 digests reproduce exactly:

1. `assets/aqos-progress-tracker.html`
   `b1176738885407268d3bf1250376454d4aa5ace4cc0a39aa82815c453d08c628`;
2. `dashboard.html`
   `70d32201d348408c0fb068d3f5af4b20354dd219b5e65b5221e29b4fc5579736`;
3. `assets/dashboard.js`
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
4. `dashboard/backend/api/main.py`
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
5. `scripts/testing/test-dashboard-program-progress.py`
   `a862cf9d510daee4207ee96fb0e4157e98991c444c9cae0c483ebcc938e0c0be`;
6. `scripts/testing/harness_qa/phases/phase0.py`
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

The candidate diff is restricted to those six files. Unrelated dirty/untracked worktree paths were not
included, modified, or treated as evidence. No candidate file was edited, staged, committed, or
deployed during review. `PULSE.log` was intentionally not mutated because it is frozen provenance.

## Passing evidence

- `python3 scripts/testing/test-dashboard-program-progress.py --static-only`: **10/10 PASS**.
- `python3 -m py_compile` for `main.py`, the focused test, and `phase0.py`: **PASS**.
- `node --check assets/dashboard.js`: **PASS**.
- Phase-0 check `0.10.40`, invoked with a `RunContext` bound to the ephemeral candidate port:
  **PASS** (`canonical tracker static contract + live asset/dashboard HTTP 200`).
- Candidate app launched without deployment on `127.0.0.1:18889`.
- Live candidate headers:
  - `/assets/aqos-progress-tracker.html`: HTTP 200, `X-Frame-Options: SAMEORIGIN`, CSP
    `frame-ancestors 'self'`;
  - `/`: HTTP 200, `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'`;
  - `/assets/dashboard.js`: HTTP 200, `X-Frame-Options: DENY`, CSP
    `frame-ancestors 'none'`.
- Real Chromium loaded the Command Center, selected the `Program` tab, and rendered the populated
  same-origin tracker iframe. Its accessibility snapshot exposed the selected Program tab, named
  Program tabpanel, focusable full-page link, populated tracker regions/tables, and focusable lane
  disclosures.
- Browser request evidence contained no off-origin request. Console inspection reported zero errors
  and zero warnings after tracker interaction.
- At a 360-pixel viewport, `document.documentElement.scrollWidth == clientWidth == 360`; no
  document-level horizontal overflow.
- With `prefers-reduced-motion: reduce`, the first progress bar computed both animation and transition
  duration as `0s`.

These observations show that the application/header implementation is viable on an undeployed
candidate server. They do not override a failing required focused gate.

## Blocking focused-test defects

`python3 scripts/testing/test-dashboard-program-progress.py` runs ten static tests successfully, then
fails `LiveHeaderTests.test_live_tracker_and_negative_headers` at line 134 with
`None != 'SAMEORIGIN'`.

Two independent defects cause the failure:

1. `LiveHeaderTests.base_url` is hardcoded to `http://127.0.0.1:8889` at line 125. Port 8889 is the
   deployed pre-candidate dashboard, so the required test cannot target the exact frozen candidate
   without deploying unaccepted code. The test must accept an explicit `--base-url` and bind the live
   test case to that parsed value. A safe production default may remain, but candidate acceptance must
   be able to name the ephemeral loopback origin explicitly.
2. `get()` converts the case-insensitive `HTTPMessage` to a plain dictionary at line 129, then the test
   looks up title-cased `X-Frame-Options`. Uvicorn emits lower-case field names, so the plain dict
   lookup returns `None` even when the response correctly contains `SAMEORIGIN`. Preserve the
   case-insensitive header object or normalize all header keys and query the normalized form. Keep the
   exact positive and two negative assertions.

## Bounded correction recommendation

A two-file AM1 is sufficient:

1. edit only `scripts/testing/test-dashboard-program-progress.py` to add explicit candidate base-URL
   selection and case-insensitive header handling; and
2. edit only `assets/aqos-progress-tracker.html` to refresh the embedded SHA-256 for that changed test
   file.

All other frozen source digests, counts, statuses, snapshot time, and candidate files must remain
unchanged. The revision must rerun the complete focused suite against the ephemeral candidate URL,
Phase-0 `0.10.40`, syntax checks, exact live positive/negative headers, the required browser checks,
and Tier 0 before a new independent exact-subject verdict. The current six-file grant must not be
committed as accepted.

VERDICT: REQUEST_REVISION — add explicit ephemeral `--base-url` support and case-insensitive HTTP header handling in the focused live test, then refresh only that test digest in the tracker manifest

## AM1 final exact-subject review — 2026-07-18 UTC

The preceding verdict remains historical evidence. AM1 corrected both named verifier defects, but a
cold embedded browser run exposed an additional mandatory acceptance failure described below.

### Exact AM1 subject and two-file boundary

All six final candidate digests reproduce exactly:

1. tracker asset:
   `238341c4fc804036b6e4404fc8ea4a24a0ca0219da88db311d2b904144116dc2`;
2. frozen `dashboard.html`:
   `70d32201d348408c0fb068d3f5af4b20354dd219b5e65b5221e29b4fc5579736`;
3. frozen `assets/dashboard.js`:
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
4. frozen `dashboard/backend/api/main.py`:
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
5. focused test:
   `4e15ff3878dabebdbfc8a68882c2e44baf77d531636c4396133e924bf79c72f8`;
6. frozen `scripts/testing/harness_qa/phases/phase0.py`:
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

Relative to the rejected predecessor, only the two AM1-authorized files changed. The four frozen
application/Phase-0 hashes are byte-identical. The asset refresh reconciles all eight manifest sources,
including focused-test and issue-backlog drift. `.agent/collaboration/PULSE.log` remains frozen at
`d67d06e59e6ef464d23ed8d593b2561a2fc829691f9c0c685b1aeaefab55516f`; this review did not mutate it.

### AM1 passing evidence

- `python3 scripts/testing/test-dashboard-program-progress.py --base-url
  http://127.0.0.1:18889`: **12/12 PASS**, including explicit-base-URL and lower-case-header
  regressions plus live positive/negative assertions.
- All eight embedded source digests independently reproduce current disk exactly; explicit-state
  counters and truth projections pass the focused reconciliation tests.
- `python3 -m py_compile` for `main.py`, the focused test, and `phase0.py`: **PASS**.
- `node --check assets/dashboard.js`: **PASS**.
- Candidate-bound Phase-0 `0.10.40`: **PASS**.
- Independent live headers at the candidate port: tracker asset is
  `SAMEORIGIN`/`frame-ancestors 'self'`; root and `dashboard.js` are
  `DENY`/`frame-ancestors 'none'`.
- Real Chromium exposes Program as a selected tab with `aria-controls="panel-program"` and
  roving `tabIndex=0`; Home moves focus to `tab-overview`, End returns it to `tab-program`, and Enter
  activates the Program panel. The panel is a visible `tabpanel` labelled by `tab-program`.
- The iframe is populated and has exactly `sandbox="allow-scripts"`, a non-empty title, and the
  same-origin tracker source. Console inspection reports zero errors and zero warnings.
- The prior 360-pixel no-overflow and computed reduced-motion `0s` evidence remains applicable because
  AM1 changed only verifier behavior and provenance digest bytes; no layout, style, script, dashboard,
  or middleware behavior changed.
- Tier 0 was launched after the focused gates passed. No final Tier-0 result is credited here because
  the independent browser origin gate already fails and acceptance cannot pass.

### Newly exposed blocking browser-origin failure

The earlier browser request listing omitted static resources. A cold rerun using
`playwright-cli requests --static` shows successful off-origin requests:

- `https://fonts.googleapis.com/css2?...`; and
- two font resources from `https://fonts.gstatic.com/...`.

They originate from the external preconnect and stylesheet links at `dashboard.html:9-11`. Program
activation itself adds only the same-origin tracker request, and the direct tracker asset is
self-contained, but the frozen PRD's mandatory browser criterion is broader: the direct **and
embedded** pass must prove that no request leaves the dashboard origin. A cold embedded load does not
satisfy that criterion. Omitting static requests from evidence would weaken the accepted gate and is
not permissible.

AM1 cannot correct this because `dashboard.html` is byte-frozen and only two files were writable.

### Bounded correction recommendation

Prepare a separately reviewed AM2 with exactly three writable files:

1. `dashboard.html` — remove the Google Fonts preconnect and remote stylesheet dependency, using the
   existing local/system font fallbacks rather than adding a new network or font asset;
2. `scripts/testing/test-dashboard-program-progress.py` — add a regression that rejects off-origin
   dashboard/tracker resource declarations so the cold-browser constraint cannot silently regress;
3. `assets/aqos-progress-tracker.html` — refresh only the changed focused-test digest in the frozen
   provenance manifest.

Keep `dashboard.js`, `main.py`, and `phase0.py` frozen. Do not weaken the browser test by blocking,
mocking, filtering, or ignoring parent-page requests. AM2 acceptance must repeat the complete focused,
manifest, Phase-0, header, cold-browser static-request, console, keyboard, narrow, reduced-motion, and
Tier-0 evidence against new exact hashes.

VERDICT: REQUEST_REVISION — cold embedded loading makes successful off-origin Google Fonts requests from `dashboard.html:9-11`; remove that network dependency under a new bounded authorization and add a regression that inspects static browser resources

## AM2 final exact-subject acceptance — 2026-07-18 UTC

The preceding revision verdicts remain historical defect evidence. AM2 closes the cold-browser
origin gap without weakening or filtering the accepted criterion.

### Exact final candidate and scope

All six final SHA-256 digests reproduce exactly:

1. frozen tracker asset:
   `238341c4fc804036b6e4404fc8ea4a24a0ca0219da88db311d2b904144116dc2`;
2. AM2 dashboard document:
   `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323`;
3. frozen dashboard JavaScript:
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
4. frozen `main.py`:
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
5. AM2 focused test:
   `c78749fccb8e42488759646212b27418200538d00b4d24887b8e05f55ba95b47`;
6. frozen Phase-0 projection:
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

Relative to the accepted AM2 predecessors, only `dashboard.html` and the focused test changed. The
tracker asset, dashboard JavaScript, middleware, and Phase-0 file remain byte-identical. The dashboard
change is limited to removing the two remote font elements and replacing the two font variables with
local/system fallback stacks. The test adds the required off-origin declaration regression while
retaining every AM1 assertion. No asset, route, CSP, service, deployment, or third implementation file
was added.

The frozen eight-source manifest independently reconciles current disk. `.agent/collaboration/PULSE.log`
remains `d67d06e59e6ef464d23ed8d593b2561a2fc829691f9c0c685b1aeaefab55516f`
through implementation and all three acceptance rounds.

### Final validation evidence

- Full focused command against `http://127.0.0.1:18889`: **12/12 PASS**.
- Python compilation for `main.py`, focused test, and Phase0: **PASS**.
- `node --check assets/dashboard.js`: **PASS**.
- All eight tracker provenance source digests: **exact match**.
- Candidate-bound Phase-0 `0.10.40`: **PASS**.
- Live response headers:
  - tracker: HTTP 200, `SAMEORIGIN`, `frame-ancestors 'self'`;
  - root and `dashboard.js`: HTTP 200, `DENY`, `frame-ancestors 'none'`.
- Fresh Chromium session with no request blocking, mocking, filtering, or cached prior session:
  `requests --static` after Program activation reported **68 requests, 0 off-origin**. Every URL used
  `http://127.0.0.1:18889`, including the embedded tracker and all parent static/API requests.
- Browser console: **0 errors, 0 warnings**.
- Program accessibility/state:
  - selected tab has `aria-selected="true"`, `aria-controls="panel-program"`, and `tabIndex=0`;
  - visible panel has `role="tabpanel"` and `aria-labelledby="tab-program"`;
  - Home moves focus to `tab-overview`; End returns it to `tab-program`; Enter activates it;
  - iframe is populated and has exactly `sandbox="allow-scripts"`, a non-empty title, and the
    same-origin tracker source.
- Narrow viewport: at 360 pixels, root document `scrollWidth == clientWidth == 360`.
- Reduced motion: tracker progress-bar animation and transition durations both compute to `0s`.
- Serialized Tier-0 terminal evidence: **exit 0, 23 passed, 0 failed**; QA Phase0 **170 checks**;
  focused CI, roadmap **609 checks**, environment contract, cross-surface, canon, configuration, and
  SOPS gates all PASS.

No candidate file, PULSE projection, deployment, or service was mutated by the reviewer. The exact
six-file candidate is accepted for orchestrator integration under the original authorization chain.

VERDICT: PASS — the exact six-file tracker candidate satisfies focused, provenance, Phase-0, security-header, cold same-origin browser, console, accessibility, responsive, reduced-motion, and Tier-0 acceptance gates

## AM3 exact-subject review — pending external Tier-0 gate

Review date: 2026-07-18 UTC
AM3 authorization: `auth-program-progress-tracker-r0-am3-20260718`
State: **CANDIDATE CHECKS PASS — FINAL ACCEPTANCE HELD**

### Exact subject and scope

All six AM3 candidate hashes reproduce exactly:

1. tracker asset:
   `6ad19ab128e45fd7340bb973ed4059cee732a06bb307bf7aa7a5c8e96ff6a1ff`;
2. frozen `dashboard.html`:
   `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323`;
3. frozen dashboard JavaScript:
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
4. frozen `main.py`:
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
5. focused test:
   `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7`;
6. frozen Phase-0 integration:
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

Only the AM3-authorized tracker asset and focused test changed. The dashboard document, dashboard
JavaScript, middleware, and Phase-0 integration retain their AM2 hashes exactly. Counts, track/status
records, decision rows, authority rows, issue cards, framing policy, and runtime behavior remain
unchanged.

### Provenance semantics

- The manifest has a closed eight-path mapping with exactly four `governing` and four
  `operational_snapshot` sources.
- Governing paths retain current-byte SHA-256 equality and fail closed on simulated drift.
- Operational paths retain unique, exact 64-hex historical snapshot commitments. A pure copied-input
  regression advances the simulated PULSE hash and remains valid without touching the repository.
- Relabelling or an unknown source class fails validation; path-to-class mapping is fixed in the test.
- Operational hashes reproduce their bytes at the candidate freeze, including issues backlog
  `50404205a540eeaf20cf47a33dc7a0ca4b0e319f3485de32eeb5320791b81957` and PULSE
  `d67d06e59e6ef464d23ed8d593b2561a2fc829691f9c0c685b1aeaefab55516f`.
- Later legitimate operational activity may advance those files without failing the tracker; it does
  not rewrite the recorded snapshot. The reviewer did not mutate PULSE or any subject file.

### Passing candidate evidence

- Full focused command against the candidate server: **13/13 PASS**.
- The focused suite proves closed class mapping, operational liveness, governing fail-closed drift,
  unchanged counts/statuses, manifest structure, same-origin declarations, AM1 verifier regressions,
  iframe/ARIA/tab contracts, and live positive/negative headers.
- Python compilation and JavaScript syntax: **PASS**.
- Candidate-bound Phase-0 `0.10.40`: **PASS**.
- Live headers remain exact: tracker `SAMEORIGIN/self`; root and control asset `DENY/none`.
- Fresh cold browser after Program activation: **31 static/dynamic requests, 0 off-origin**; console
  **0 errors, 0 warnings**.
- The four browser/runtime files are byte-frozen from AM2, whose independently accepted evidence proves
  populated iframe, exact sandbox/title/source, ARIA and Home/End/Enter behavior, 360-pixel no-overflow,
  and reduced-motion `0s`. AM3 changes only manifest data/provenance disclosure and its validator.

### External acceptance hold

Final AM3 PASS requires a serialized Tier-0 **23/23** after the separately authorized AppArmor live
Agent Ops monitor repair. That repair is outside this tracker lease and is not a tracker defect, but
the accepted gate does not permit a partial or pre-repair Tier-0 result. No final PASS or integration
authority is granted until the orchestrator supplies the post-repair exit-0 evidence and this exact
six-hash subject is reverified without drift.

VERDICT: BLOCKED — AM3 candidate-local evidence passes, but final acceptance awaits post-AppArmor-repair Tier-0 exit 0 with 23 passed and 0 failed

## AM3 external-gate closure and final acceptance

Review date: 2026-07-18 UTC
State: **FINAL PASS**

The separate AppArmor live-monitor repair is deployed at
`/nix/store/5q4v1fk46r1xymwqscvw6wwx61sngiqa-nixos-system-hyperd-26.05.20260714.8eeec93`;
`/run/current-system` resolves to that exact generation.

Independent post-deploy checks establish:

- live `GET /api/aistack/local-agent/monitor`: `ok=true`, `available=true`, `status=healthy`,
  `mode=read_only`, source
  `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/registry.jsonl`;
- kernel journal scan over the recent repair window: no `registry.jsonl` AppArmor denial;
- `aq-qa 0 --machine`: completed with exit 0;
- serialized full `scripts/governance/tier0-validation-gate.sh --pre-commit`: **exit 0, 23 passed,
  0 failed**, including QA Phase0, focused CI, roadmap, environment/cross-surface/canon/configuration,
  and SOPS gates.

The exact AM3 candidate was reverified after deployment with no subject drift:

1. tracker asset
   `6ad19ab128e45fd7340bb973ed4059cee732a06bb307bf7aa7a5c8e96ff6a1ff`;
2. dashboard document
   `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323`;
3. dashboard JavaScript
   `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6`;
4. middleware
   `bf1f4226054ed4076066a87f04460e82ba8a868ed83d67cb54154ee57872af22`;
5. focused test
   `c2251588563c775264d268f84abcda8fe6f9fc60cdd5f309f030d04bfccbb0a7`;
6. Phase-0 integration
   `ccee6268b0980f1d2fed1db6919107e1b4809447d9195461994ffb420f1f9a96`.

The complete focused suite against a freshly relaunched ephemeral candidate server passed **13/13**,
and candidate-bound Phase-0 `0.10.40` passed again. These reproduce the closed governing/operational
mapping, governing fail-closed drift, operational liveness, explicit counts/statuses, manifest,
same-origin, header, iframe, ARIA, keyboard, and runtime linkage contracts. The already-recorded cold
browser, console, narrow-layout, and reduced-motion evidence remains bound to these unchanged runtime
hashes.

The historical BLOCKED verdict is therefore resolved. No candidate file, staging area, deployment,
or project scope was changed by the acceptance reviewer.

VERDICT: PASS — exact AM3 tracker candidate accepted after deployed AppArmor monitor recovery, healthy live registry projection, aq-qa exit 0, and full Tier-0 23/23 with no subject drift
