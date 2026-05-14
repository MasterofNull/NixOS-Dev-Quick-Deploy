# Command Center Dashboard Revamp PRD

## Problem
The command center dashboard has accumulated monitoring, operations, graph, testing, security, and AI harness widgets in one long page. It remains valuable because it exposes detailed system state, but operators need a clearer way to answer: "Is the stack healthy?", "What changed?", "What needs action?", and "Where is the evidence?"

## Goal
Preserve the cyberpunk command-center theme and detailed data depth while turning the dashboard into an operator cockpit with clear monitoring lanes, predictable navigation, and a maintainable full-stack contract.

## Scope
- Add an operator information architecture over the existing dashboard without removing detailed cards.
- Consolidate navigation around lenses: Overview, Stack, Operations, Intelligence, Security, and All Detail.
- Keep live metrics, deployment controls, testing, AI insights, graph views, security, and runtime inventory available.
- Document the longer-term full-stack split for frontend modules, API aggregation, and tests.

## Out Of Scope
- Removing current dashboard data surfaces.
- Replacing the FastAPI backend or changing service control permissions.
- Deploying a new framework before the existing static dashboard has a clean route and data inventory.

## Acceptance Criteria
- Operators can switch between focused dashboard lenses without losing access to full detail.
- The default first viewport emphasizes health, transport, runtime, stack posture, and refresh state.
- Existing dashboard tests that check UI/API snippets continue to pass.
- No new hardcoded secrets are introduced.
- Any ports or service URLs continue to come from the existing runtime config surfaces or current dashboard API base logic.

## Security Requirements
- Treat all API responses and generated graph content as untrusted before rendering.
- Avoid adding new remote script dependencies unless the CSP and vendoring strategy are updated intentionally.
- Keep operator write controls visibly separated from read-only monitoring.
- Preserve dashboard rate limiting, audit logging, and existing sudo command boundaries.

## Proposed Full-Stack Shape
- Frontend: keep `dashboard.html` stable for the current slice, then extract sections into `dashboard/public` modules once the lens taxonomy is proven.
- Backend: add a future `/api/dashboard/overview` aggregation endpoint only after endpoint ownership is mapped, to reduce page-load fanout.
- Tests: preserve static regression tests for legacy snippets, then add lens tests and one API aggregation test per lane.
- Design: keep dark cyberpunk, cyan/magenta/yellow signals, dense operator data, restrained motion, and compact cards.
