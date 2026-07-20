# QPPR A2 dashboard-projection candidate — binding acceptance verdict

**Reviewer:** claude-subagent-qppr-a2-acceptance-reviewer (Claude Opus 4.8, model id `claude-opus-4-8`)
**Role:** independent flagship binding acceptance gate — fresh session; did not implement A2, did not
author the A2 rebind design reviews, not the orchestrator.
**Date:** 2026-07-20
**Authority:** owner `[acceptance-lane-directive]` PULSE.log 2026-07-20T08:14:39-0700 (redirects binding
acceptance of the staged QPPR A2 5-file candidate from codex-wait to a fresh Claude flagship reviewer,
executed now; reviewer-agnostic frozen criteria unchanged). Criteria SSOT:
`A2-CANDIDATE-CODEX-ACCEPTANCE-AUTHORIZATION.md`.

## VERDICT: REQUEST_REVISION — JS poller cadence deviates from frozen design §4.2 (idle/stale poll at 1s, spec mandates 2s); criterion 3 not attestable

All other criteria (1, 2, 4, 5, 6, 7) pass cleanly. The single blocking finding is a bounded,
one-predicate frontend deviation in `assets/dashboard.js`. This returns A2 to a bounded revision cycle
with fresh hashes, exactly per the authorization's REQUEST_REVISION path.

---

## Recomputed candidate hashes (criterion 1) — ALL MATCH

| Op | Path | Frozen SHA-256 | Recomputed | Match |
|---|---|---|---|---|
| MODIFY | `dashboard/backend/api/services/qa_runner.py` | `8e49fa82…6326cbb7` | `8e49fa8296ed882a71a94b185f814085a44d16879dab804521ad026e6326cbb7` | ✅ |
| MODIFY | `dashboard/backend/api/routes/aistack.py` | `8b96ffdf…2db8aa46` | `8b96ffdf5ec0ba275dc32fcf4e4aa703bb1db8a4e19326f15352cd2b38dbaa46` | ✅ |
| MODIFY | `dashboard.html` | `af9d8c81…8f84beae` | `af9d8c81e30f63321f01efd189416a6d4786489932485f889d82484e8f84beae` | ✅ |
| MODIFY | `assets/dashboard.js` | `dcc17d8d…de709a29` | `dcc17d8d1477d3a5f40f6ca5a8fd390cf1bcce3cca0fbd8151d1226ade709a29` | ✅ |
| NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | `fe749576…f6ef91e254` | `fe749576fd3abfcbbba17cf2625174a13ecf210b9436acba89f2ff7efb91e254` | ✅ |

A2 candidate set = exactly these five. The `.gitignore` staged change (adds
`.agents/delegation/.codex-quota-cooldown`) and `scripts/ai/delegate-to-codex` +
`test-delegate-codex-quota-precheck.sh` belong to the SEPARATE delegate-codex quota slice (3 files) —
not conflated with A2. **Criterion 1: PASS.**

## Per-criterion evidence

**Criterion 2 — runtime-surface adjacency (PASS).** `git log 3396f9df..HEAD` = two commits
(`30f3f70b` docs(qa): A2 adjacency rebind…, `28bff4a4` docs(governance): Rule 17…). `git diff --stat`
over that range touches only agent `.md` files, `issues-backlog.md`, A2/C1C plan docs, and
`.claude/CLAUDE.md` — zero of the five A2 runtime targets and no A1 heartbeat runtime surface
(`qa-provider-probe.py`). Governance/doc exempt. No drift.

**Criterion 3 — design §4.1/§4.2 in the bytes (FAIL — cadence).**
- §4.1 backend reader (`qa_runner.py`): CONFORMS. `_read_probe_active_raw` opens with
  `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, `fstat` rejects non-regular/symlink, rejects `size<=0` or
  `>16384`, over-reads `16384+1` and rejects if exceeded, strict `schema_version` check, exact
  required-keyset match (rejects unknown/extra fields), enum validation for
  provider/lifecycle/failure-class, UUID regex, `deadline_ms==45000`, `elapsed_ms` bounded int, and
  future-dated rejection → `None` → `availability=unavailable`. Bound only to
  `.agent/qa/provider-probe-active.json` + `qa.provider-probe-active.v1`; **never imports
  `qa-provider-probe.py`** (verified in staged diff). Stale (>5000ms) still returns last-known values
  with `availability="stale"` (§4.2 last-known requirement met; test line 191 confirms).
- §4.1 route (`aistack.py`): CONFORMS. `projection_only && phase=="0"` early-returns
  `{phase, projection_only:True, provider_probe, timestamp}` before `_VALID_QA_PHASES` validation,
  QA cache lookup, background admission, `run_phase_json`, and evidence access. No-op on other phases
  (test line 235). No mutation of `_AQ_QA_CACHE`/`_AQ_QA_RUNNING`/`_RUNNING_TASKS` in the added lines
  (verified; only `os.open` in the bounded reader).
- §4.2 card (`dashboard.html`): CONFORMS. Exactly six new `fw-row` rows on the existing QA Phase-0
  card (Active Provider, Probe State, Probe Elapsed, Last Failure Class, Heartbeat Freshness, Evidence
  Invocation) with unique IDs and text labels. No new card/route/control; existing Refresh button
  untouched. Test asserts 5 pre-existing + 6 new = 11 `fw-row`, no `innerHTML`.
- §4.2 poller (`dashboard.js`): **DEVIATES.** Single-flight (`_qaProbeInFlight`), own
  `AbortController` with 750ms abort, visibility+lens gated (`!document.hidden && activeLens ===
  "operations"`), `setText`-only (no `innerHTML`), never calls `loadQA()` — all conform. **But the
  cadence predicate does not implement the frozen §4.2 table.** Design §4.2 (line 256):
  *"polls every 1 second while state is active, and every 2 seconds while idle, terminal, stale, or
  unavailable."* Implementation:
  `_qaProbeActive = !["terminal", "unavailable"].includes(p.lifecycle_state ?? "unavailable")`,
  feeding `setTimeout(_qaProbePollOnce, _qaProbeActive ? 1000 : 2000)`. Consequences:
  - `lifecycle_state === "idle"` → `_qaProbeActive = true` → **1s** (design mandates **2s**).
  - `availability === "stale"` with a non-terminal lifecycle (e.g. `running`) → **1s** (design
    mandates **2s**; the predicate ignores `availability` entirely).
  The code's own inline comment lists "idle … stale …" under the *2s* branch, contradicting its own
  predicate — this is a latent defect, not a disclosed judgment call. Everything else in §4.1/§4.2
  conforms; this cadence table is the sole non-conformance.

**Criterion 4 — projection never authority (PASS).** The `projection_only` branch returns only the
`provider_probe` object and cannot reach `run_phase_json`, the cache, or evidence; the immutable QA
result path is untouched. `host_execution` reports `dashboard_confined_skip` (never PASS) when
confined. Poller renders into six dedicated rows and never writes the card's PASS/FAIL badge/counts.

**Criterion 5(a) — host_execution derivation (ACCEPTED).** Design §4.1 line 233 enumerates the four
values (`active|terminal|dashboard_confined_skip|unavailable`) but pins no formula; a grep across all
A2 sibling docs found no other host_execution mention — no pinned formula exists to contradict. The
implementer's derivation — confined→`dashboard_confined_skip`; else terminal-lifecycle→`terminal`;
else→`active`; on `None`+confined→`dashboard_confined_skip`, else→`unavailable` — yields exactly the
four enumerated values and honors §4.1's "confinement reports dashboard_confined_skip, never PASS." No
new env var (`AQ_QA_DASHBOARD_SAFE` pre-exists). Consistent with the design; ACCEPTED.

**Criterion 5(b) — governance-ordering deviation (ACCEPTED).** Implementer ran the pre-edit
`aq-event resume` + `pending-update add` post-hoc and self-disclosed. Subject bytes are hash-frozen and
independently re-verified here, so post-hoc governance calls cannot alter the subject. Same class as
the A1-AM3 rev1 deviation accepted there; no integrity impact. ACCEPTED.

**Criterion 6 — fresh validation (PASS, with coverage gap noted).**
- `python3 scripts/testing/test-dashboard-qa-provider-probe.py` → `PASS`, 18/18 test functions,
  offline (no live provider/network/browser). rc=0.
- `py_compile` on `qa_runner.py`, `aistack.py`, and the test → OK.
- `git diff --cached --check` on the four MODIFY → clean.
- Regression suites: `test-dashboard-qa-singleflight.py` rc=0, `test-dashboard-qa-runner-runtime-env.py`
  rc=0, `test-dashboard-compat-routes.py` rc=0 (21 compat routes) — no regression.
- Secret scan on the five staged files' added lines → no secret patterns.
- **Coverage gap:** the poller test (line 282) asserts only the literal presence of the string
  `"? 1000 : 2000"`, not the semantics of which states map to each branch. It therefore does not catch
  the idle/stale→1s deviation. The passing suite does not contradict the criterion-3 finding.

**Criterion 7 — no prohibited action (PASS).** No sixth A2 file; no new route/card/store/dependency/env
var; no live provider/network/API/browser; no QA/cache/evidence mutation; no unbounded/symlink read
(bounded 16KB `O_NOFOLLOW` reader); no Nix/service/deploy; nothing staged beyond the five (+ the
separate quota entry).

## Required revision (bounded)

Fix the `dashboard.js` cadence predicate so idle, terminal, stale, and unavailable poll at 2s and only
truly active lifecycle states (starting/running/terminating/reaping) poll at 1s — e.g. treat a probe as
"active" only when `availability === "current"` AND `lifecycle_state` is not in
`{idle, terminal, unavailable}`. Align the inline comment with the predicate. Re-run the offline test
suite and re-freeze all affected hashes (`assets/dashboard.js` at minimum; the test if a semantic
cadence assertion is added). Consider strengthening the poller test to assert idle/stale map to the 2s
branch, closing the coverage gap. Everything else in the candidate is accepted as-is; a revised
candidate need only re-verify this slice.

---

VERDICT: REQUEST_REVISION — JS poller cadence deviates from frozen design §4.2: `idle` and `stale`
states poll at 1s where the spec mandates 2s (predicate keys only on `lifecycle_state ∉ {terminal,
unavailable}` and ignores `availability`, contradicting the code's own comment); criterion 3 (§4.2 in
the bytes) is therefore not attestable. Criteria 1, 2, 4, 5(a/b), 6, 7 PASS. No PASS authorization for
Tier-0/stage/commit; return A2 to a bounded revision cycle with fresh hashes.
