# Project PRD — Canonical Program Progress Tracker

Status: `DRAFT — SIX-FILE IMPLEMENTATION FREEZE PENDING`
Owner direction: 2026-07-17
Parent program: `.agents/plans/UNIFIED-PROGRAM-PLAN.md`

## Objective

Make the AQ-OS refactor tracker the default human-facing project status surface and display it inside
the AI Command Center. The tracker must be durable, repository-versioned, truthful, and derived from
the same program, authority, decision, issue, and collaboration evidence that governs implementation.

The supplied prototype is currently ephemeral at:

`/tmp/claude-1000/-home-hyperd-Documents-NixOS-Dev-Quick-Deploy/6b22f540-d284-4347-ae04-89f4330ae059/scratchpad/aqos-progress-tracker.html`

An ephemeral artifact is not an authority. It becomes canonical only after it is copied into the
repository, independently reviewed, validated, committed, and linked from the Command Center.

## Source precedence

The tracker is a projection, never a second planning authority. When sources disagree, use:

1. explicit owner decisions and hash-bound authorizations;
2. `config/system-state-authorities.yaml` plus its accepted checker output;
3. `.agents/plans/UNIFIED-PROGRAM-PLAN.md` and its owner decision sheet;
4. accepted slice evidence and commits;
5. `.agent/memory/issues-backlog.md` for open operational debt;
6. collaboration registry/inbox state for lane availability and active work.

Unavailable, timed-out, orphaned, or abstaining lanes remain visible and never become approval.

## User experience contract

- Add a visible `Program` lens to the AI Command Center.
- Render the tracker inside a sandboxed iframe from a same-deployment static asset. The iframe
  sandbox is exactly `allow-scripts`: do not grant same-origin, forms, popups, downloads, top
  navigation, presentation, modals, pointer lock, storage access, or custom-protocol privileges.
- Preserve a visible, keyboard-focusable direct link to `/assets/aqos-progress-tracker.html` for
  full-page use. The `Program` tab must use the Command Center's existing tab role/state contract,
  be reachable in DOM order, expose selected state, and move focus into a named Program panel when
  activated by keyboard.
- Show update timestamp, evidence/source footer, track progress, active/blocked/not-started work,
  Q1–Q10 decisions, the ten Foundation-A authority decisions, and high-severity issues.
- Never show a blocked track as progress merely because discovery or code exists.
- Respect dark mode, reduced motion, keyboard navigation, narrow screens, and iframe sizing. Every
  hover-only disclosure in the prototype must also open on focus, close on blur or Escape, retain a
  visible focus indicator, and expose its detail through an accessible name/description. The iframe
  has a non-empty `title`, and the direct link makes the same content available if framing fails.
- No network dependency, third-party script, secret, prompt content, raw registry content, or inline
  ability to mutate program state.

## Exact implementation slice

1. `assets/aqos-progress-tracker.html` — durable canonical projection copied from the supplied design
   and updated to current evidence.
2. `dashboard.html` — `Program` tab, named panel, sandboxed embedded tracker, and direct link.
3. `assets/dashboard.js` — integrate `Program` into the existing tab controller with real
   `role="tab"` semantics, roving keyboard focus, `aria-selected`, `aria-controls`, matching
   `role="tabpanel"` visibility, and deterministic focus transfer. No tracker data lives here.
4. `dashboard/backend/api/main.py` — path-scoped response-header override for exactly
   `/assets/aqos-progress-tracker.html`: `Content-Security-Policy` retains the global policy except
   `frame-ancestors 'none'` becomes `frame-ancestors 'self'`, and `X-Frame-Options` becomes
   `SAMEORIGIN`. Every other response retains global `X-Frame-Options: DENY` and
   `frame-ancestors 'none'`.
5. `scripts/testing/test-dashboard-program-progress.py` — structure, sandbox, source-precedence,
   truthfulness, responsive, and privacy assertions.
6. `scripts/testing/harness_qa/phases/phase0.py` — one focused registered check for the tracker and
   Command Center linkage.

No backend route is required: the existing `/assets` StaticFiles mount serves the direct tracker URL.
The middleware-only header exception is necessary because the global deny framing policy correctly
blocks every page by default; it must not become a prefix, suffix, query-string, or content-type
exception.
No service, Nix, AppArmor, API, database, lifecycle store, or traffic-routing change is in scope.

## Deterministic evidence snapshot

Immediately before the six implementation predecessor hashes are frozen, generate a just-in-time
embedded provenance manifest containing each governing source's repository-relative path and full
SHA-256 digest. Do not reuse a planning-time manifest. At minimum it covers the unified plan, owner
decision sheet, state-authority registry, Foundation-A owner-adjudication record, issues backlog,
collaboration resume state, pulse log, and delegation registry. The manifest records one UTC snapshot
timestamp and the rendered counts for tracks, active tracks, Foundation-A blocking gates, pending Q
decisions, authority rows, and open high-severity issues.

The HTML is a deterministic projection of that frozen manifest. Every record that participates in a
counter has an explicit status field. Pending/open/active/blocked counts are filtered from those status
values; collection length is never used as a status proxy. The freeze procedure reconciles each
displayed counter against its governing records and fails on any mismatch before authorization. Later
source drift makes the tracker stale and fails the focused test; runtime code never silently fetches
mutable repo or registry content.

## Sequencing and acceptance

R0.1 is committed at `d4780ca5`. Before implementation begins, verify no active authorization leases
any of the six files, produce the just-in-time evidence manifest, and freeze fresh predecessor hashes.

Acceptance requires:

- the six-file inventory only;
- direct `/assets/aqos-progress-tracker.html` HTTP 200 from the running dashboard;
- direct response has `X-Frame-Options: SAMEORIGIN` and CSP `frame-ancestors 'self'`, while the
  dashboard root and a second asset retain `DENY`/`frame-ancestors 'none'`;
- Command Center Program tab renders the sandboxed tracker with exactly `sandbox="allow-scripts"`,
  a non-empty title, a direct link, and correct tab/panel semantics;
- keyboard tests prove the Program control participates in the existing tab set, reflects
  `aria-selected`, owns the correct `aria-controls`, hides/shows the matching tabpanel, supports the
  controller's Arrow/Home/End behavior, and transfers focus according to the declared contract;
- focused test and registered Phase-0 check pass;
- embedded provenance paths/digests and all displayed counts reconcile to the frozen snapshot;
- no stale claim that all ten owner decisions remain pending after recorded approvals;
- no XSS-capable unsanitized external data path;
- a real-browser pass at the direct and embedded URLs proves no network request leaves the dashboard
  origin, no browser-console error occurs, keyboard focus reaches and operates disclosures and the
  direct link, narrow layout does not create document-level horizontal overflow, and reduced-motion
  emulation suppresses animation and transition;
- independent frontend/accessibility and program-truth review;
- Tier-0 pass and atomic commit.

## Default tracker policy

All future program status updates must update this tracker in the same commit as the governing plan or
immediately consecutive evidence commit. Commentary and handoff summaries should link to the tracker
first, then to detailed source records. A stale tracker is a functional visibility defect.
