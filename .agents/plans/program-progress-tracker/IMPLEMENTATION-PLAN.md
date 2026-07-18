# Program Progress Tracker — Implementation Plan

Status: `PREPARED_ONLY`

1. Confirm committed R0.1 (`d4780ca5`) and verify that no active authorization leases any of the six
   implementation files.
2. Immediately before authorization, generate the evidence manifest from current sources and freeze
   all six predecessor hashes, including `assets/dashboard.js` and the path-scoped security-header
   middleware surface in `dashboard/backend/api/main.py`. A planning-time digest list is not reusable.
3. Reconcile Q1–Q10 and the ten Foundation-A rows into a reviewed tracker-data snapshot. Generate an
   embedded provenance manifest with repository-relative source paths, full SHA-256 hashes, one UTC
   snapshot time, and explicit per-record statuses. Include the Foundation-A owner-adjudication record.
   Derive all pending/open/active/blocked counters by filtering explicit status fields, never by array
   length, and fail the freeze if any rendered count differs.
4. Copy the supplied HTML into `assets/aqos-progress-tracker.html` and update only evidence-backed
   statuses, decisions, issues, timestamps, and source links.
5. Add a `Program` Command Center tab and named tab panel. Use an iframe with a non-empty `title` and
   exactly `sandbox="allow-scripts"`, plus a visible direct link to the same asset. Preserve the
   existing tab keyboard/state contract and focus order; do not grant any additional sandbox token.
6. Extend the existing controller in `assets/dashboard.js` so Program is a real member of the tab set:
   role, `aria-selected`, `aria-controls`, roving tabindex, matching panel visibility, Arrow/Home/End
   traversal, activation, and the declared focus destination must remain synchronized.
7. In the existing security-header middleware, special-case only the exact tracker asset path so its
   CSP uses `frame-ancestors 'self'` and X-Frame-Options uses `SAMEORIGIN`. Preserve global
   `DENY`/`frame-ancestors 'none'` for the root, all other assets, APIs, and unmatched paths.
8. Fix the prototype's lane-name structure so each lane has one semantic name; make bar disclosures
   focusable and operable by focus/blur/Escape with visible focus and accessible descriptions.
9. Add focused tests and one registered Phase-0 check. Static tests assert the exact six-file
   contract, exact sandbox token set, title/link/tab semantics, source hashes, count reconciliation,
   path-scoped headers, privacy, and absence of external resources.
   Browser tests additionally exercise Program tab selection state, `aria-controls` ownership,
   panel visibility, roving focus, Arrow/Home/End traversal, activation, and focus transfer.
10. Run the tracker directly and embedded in the live dashboard. Capture response headers for the
   tracker, dashboard root, and a control asset. In a real browser, fail on off-origin requests or
   console errors; exercise keyboard-only tab/disclosure/direct-link flow; test light and dark;
   verify no document-level overflow at a narrow viewport; emulate reduced motion and assert computed
   animation/transition durations are zero.
11. Obtain an independent program-truth/frontend review, run Tier 0, and commit the exact six files.
12. Make the tracker the primary link in future project status handoffs and update it with every
   accepted program-state transition.

Hard stop: any dashboard backend surface other than the exact path-scoped middleware change in
`dashboard/backend/api/main.py`, any tracker-unrelated behavior in `assets/dashboard.js`, runtime
services, or a seventh implementation file requires a new design/review.
