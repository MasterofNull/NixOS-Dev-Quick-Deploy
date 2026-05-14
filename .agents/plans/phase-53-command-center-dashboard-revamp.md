# Phase 53: Command Center Dashboard Revamp

## Objective
Turn the current dashboard from a long monitoring junkdrawer into a focused command center while preserving detailed system monitoring and the cyberpunk visual language.

## Scope Lock
In scope:
- Add operator lens controls to group existing cards.
- Document the UX and full-stack revamp path.
- Keep current API calls and section IDs intact.

Out of scope:
- Removing widgets.
- Replacing the static dashboard with a framework.
- Changing privileged operator control semantics.

## Workstreams
- Design / IA: define Overview, Stack, Operations, Intelligence, Security, and All Detail lenses.
- Frontend: add lens controls, section classification, counts, and safe fallback behavior.
- Full-stack: map existing API fanout and defer aggregation endpoint until route ownership is reviewed.
- Validation: run dashboard static tests and Python syntax checks for touched backend files if any.

## Review Findings To Carry Forward
- The current surface is a single long static app; preserve the data but stop treating every panel as primary.
- The old Security nav targeted Agentic Readiness; Security should land on Network & Firewall / Security Monitor surfaces.
- CSP and asset sourcing need a dedicated hardening slice. This slice aligns CSP with current assets; the preferred end-state is vendored local assets.
- `Makefile`, Nix comments, `dashboard/public`, and route-family docs are stale relative to the single FastAPI UI/API service.
- Topology endpoints need follow-up tests and should use endpoint SSOT names for embeddings/dashboard ports.
- Card inventory and consolidation matrix: `.agents/plans/phase-53-command-center-card-inventory.md`.

## Slice 1 Plan
1. Add PRD and this phase plan.
2. Add dashboard lens controls above the card grid.
3. Classify existing sections client-side from stable titles and IDs, so current markup and tests remain compatible.
4. Validate static dashboard regressions and syntax where applicable.

## Acceptance
- Default view remains detailed enough for live monitoring.
- Operators can narrow the page by lane in one click.
- The All Detail lens restores every section.
- Existing `dashboard.html` IDs and endpoint strings stay available for tests.
- Security anchor lands on the actual security monitoring lane.

## Rollback
Revert `.agent/PROJECT-COMMAND-CENTER-DASHBOARD-REVAMP-PRD.md`, this plan, and the `dashboard.html` lens-control additions.

## Security Notes
- This slice is presentation-only.
- No new service URLs, ports, secrets, or operator write endpoints are introduced.
- Future remote script/CSP cleanup should be handled as a separate hardening slice.

## Next Slice
Annotate existing dashboard cards with semantic metadata:
- `data-layer`: `l1` through `l7`, comma-separated for cross-layer cards.
- `data-module`: command-deck, layer-explorer, runtime-operations, data-memory, intelligence-workbench, validation-release, security-network, recovery-admin, event-spine.
- `data-criticality`: critical, high, normal, low.

Then update lens filtering to use metadata rather than card-title matching.

## Slice 2: Command Deck
Implemented a first-viewport Command Deck in `dashboard.html`:
- Critical live tiles: CPU, GPU, memory, disk, network, stack.
- Layer rail placeholder wired to `/api/health/layered` results when available.
- Active alert list derived from hardware thresholds, runtime transport, stack health, refresh state, and layer failures.
- Recovery/admin shortcuts: refresh, layer detail, security, deployments, validation, data/memory.

Validation evidence:
- `python3 scripts/testing/test-dashboard-command-lenses-ui.py`
- `python3 scripts/testing/test-dashboard-operator-links-api-base.py`
- `python3 scripts/testing/test-dashboard-deployment-ui.py`
- `python3 -m py_compile dashboard/backend/api/main.py dashboard/backend/api/routes/topology.py`
- Browser smoke on `127.0.0.1:8891`: 0 console errors, Command Deck populated live CPU/GPU/memory/disk/network/stack values.
