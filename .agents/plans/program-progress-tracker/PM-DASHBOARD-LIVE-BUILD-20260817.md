# PM Dashboard — from frozen mockup to live git-projected board (2026-08-17)

## Problem
`assets/aqos-progress-tracker.html` was a FROZEN_IMPLEMENTATION_SNAPSHOT: 11
hand-typed JS arrays (`tracks`, `columns`, `gateRows`, `issues`,
`authorityTargets`) baked into the page at 2026-07-18, 04:01 UTC, with zero
`fetch()` calls. It could never reflect what actually shipped afterward.
Meanwhile `scripts/ai/aq-pm-tracker` already PROJECTS real per-plan status
from git commits + `aq-event` activation grants + freeze records (the
PM-tracker-standard engine, `.agents/plans/pm-tracker-standard/DESIGN.md`) —
but only per single plan-dir, and nothing consumed it in the dashboard.

## Build (3 parts, this cycle)
1. **`scripts/ai/aq-pm-tracker` aggregate mode** — added `discover_tracked_plans()`
   (globs `.agents/plans/*/tracker.json`) and `project_all()` (reuses the
   existing `project_item()` ground-truth logic; one shared `_git_log()`/
   `_aq_grants()` read across all plans, not one per plan). Wired into
   `main()` as `--all` (human summary) / `--all-json`
   (`{generated_at, plans[{id,title,rollup_pct,shipped,total,phases,items[]}],
   program_rollup_pct}`, weighted by per-plan item count). Existing
   single-plan `--json`/`--check`/`--summary` modes untouched; `_ensure_deep()`
   shallow-clone guard behavior preserved (still called via `_git_log()`).

2. **`dashboard/backend/api/routes/pm.py`** (new) — `GET /api/pm/progress`.
   Shells out to `scripts/ai/aq-pm-tracker --all-json` via
   `asyncio.create_subprocess_exec` (30s timeout) rather than importing the
   CLI's `project()` functions — same BARE-python posture as
   `approvals.py`'s fixture wiring (module docstring: "avoid importing
   anything at module load that needs deps absent from the dashboard's BARE
   python"). Registered in `dashboard/backend/api/main.py` next to the
   approvals wiring: `from .routes import pm as pm_mod; app.include_router(
   pm_mod.router, prefix="/api", tags=["pm"])`.

3. **`assets/aqos-progress-tracker.html`** — full rewrite. `load()` fetches
   `/api/pm/progress` on page load and every 30s (`cache: 'no-store'`,
   in-flight guard against overlapping fetches), renders 4 live stat tiles
   (program rollup %, tracked plans, shipped/total, blocked-item count), a
   per-plan card per tracked plan (title, rollup % bar, phase-grouped item
   chips colored by status: SHIPPED/ACTIVATED=good, IN-PROGRESS=active,
   BLOCKED=blocked, FROZEN/DESIGNED=new muted hues, NOT-STARTED=faint), a
   loading spinner state, an error state with a Retry button, and a status
   legend. All 11 old hardcoded arrays + the frozen-provenance
   reconciliation script are gone. Zero external URLs (still self-contained
   per CSP); exactly one `fetch()` call, to the same-origin relative path.

## Validation
- `scripts/ai/aq-pm-tracker --all-json` → valid JSON;
  `approval-control-plane` projects **90%** (9/10 shipped) as expected.
  `python3 -c "import json,subprocess; json.loads(subprocess.run([...,
  '--all-json'], capture_output=True, text=True).stdout)"` parses clean.
- End-to-end smoke test (not part of the committed suite — throwaway
  harness only): a minimal FastAPI app mounting `pm.router` + the `assets/`
  static dir, driven headless via `chromium --headless --dump-dom` and
  `--screenshot`. Confirmed: 3 plan-cards, 24 item-chips (matches
  10+9+5 tracker items), status counts sum correctly (14 shipped / 24
  total, matching the stat tile), loading panel replaced by live content,
  status chip flips to "Live". Screenshot reviewed — clean dark-mode
  rendering, phase grouping and status colors read correctly.
- `scripts/testing/test-dashboard-program-progress.py` — REWRITTEN (the old
  suite asserted the frozen-snapshot shape: exact hardcoded track/gate/
  issue counts, an 8-source sha256-pinned provenance manifest, "no fetch()"
  as a hard requirement). New suite asserts the live-fetch contract instead:
  exactly one same-origin `fetch('/api/pm/progress')`, no hardcoded
  arrays/FROZEN marker, loading/error states present, status legend
  present, `pm.py` registered in `main.py`, `pm.py` shells out (never
  imports the CLI), `aq-pm-tracker` exposes the aggregate functions. Kept
  unchanged (still valid, untouched by this build): dashboard embed
  contract, tab-controller contract, the CSP frame-ancestors exception in
  `main.py`, phase0 registration markers. `--static-only` run: **15/15
  pass**. Live-mode run against the throwaway smoke server: 16/17 pass —
  the one failure (`x-frame-options` header assertion) is the smoke
  server lacking `main.py`'s security-headers middleware (a fixture gap,
  not a regression); that middleware itself is unchanged and separately
  covered by `test_exact_path_header_exception` (passed).
- `scripts/testing/harness_qa/phases/phase0.py` check `0.10.40` — updated
  its live-asset marker string from `FROZEN_IMPLEMENTATION_SNAPSHOT` (now
  gone from the page) to `/api/pm/progress` (the page's live-fetch
  fingerprint). Check ID unchanged (same check, updated assertion — no
  renumbering needed).

## Deferred / not done here
- **The running `command-center-dashboard-api` service was NOT restarted**
  (no perms in this session) — `/api/pm/progress` will 404 on the live
  dashboard until an operator restarts it. `phase0.py` 0.10.40 will
  correctly `failed` (not `skipped`) once the dashboard is reachable but
  still serving the old route table — that is the expected/honest signal
  that a restart is owed, not a bug in this check.
- **Iframe-embedded panel + CORS**: `dashboard.html` embeds the tracker via
  `<iframe sandbox="allow-scripts" ...>` (deliberately, per an existing
  test, without `allow-same-origin`). A sandboxed frame without
  `allow-same-origin` has an OPAQUE origin, so its `fetch()` calls carry
  `Origin: null` and are cross-origin even against the same host/port.
  `main.py`'s `CORSMiddleware` only allows an explicit origin list (no
  `"null"`), so the embedded copy's fetch will likely be blocked by CORS
  in-browser (request reaches the server; the browser withholds the
  response from JS) — degrading to the page's error state with a Retry
  button and no crash. The full-page route
  (`/assets/aqos-progress-tracker.html`, linked directly from the
  dashboard's Program tab as "Open full-page tracker") is unaffected —
  same-origin navigation, no CORS involved. Not fixed here (would mean
  loosening CORS to allow `null` or moving to a postMessage bridge —
  either is a scope decision beyond "wire fetch to the API"); logged to
  `.agent/memory/issues-backlog.md` for a follow-up decision.
