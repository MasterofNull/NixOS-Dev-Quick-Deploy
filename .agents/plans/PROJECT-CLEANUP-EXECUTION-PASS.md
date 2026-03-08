# Project Cleanup Execution Pass

**Created:** 2026-03-08
**Status:** In progress; major cleanup slices executed
**Owner:** Codex
**Reviewer Gate:** Required at end of every phase
**Target Outcome:** Lower drift, smaller exposed surface area, stable declarative runtime, and a command-center dashboard backed only by live contract-validated data.

## Consolidated Status Update (2026-03-08)

### Completed Outcomes

- Established the declarative command center runtime as the single operator authority.
- Aligned health checks and dashboard service discovery with the actual runtime.
- Removed production mock masking from retained dashboard surfaces.
- Quarantined `dashboard/control-center.html` and clearly labeled static dashboard surfaces as legacy/historical.
- Normalized dashboard frontend/runtime data paths without changing the dashboard UI/themes.
- Updated active docs, operator guides, development roadmaps, and the root README to point to `command-center-dashboard-api.service` at `http://127.0.0.1:8889/`.
- Removed active hardcoded personal repo paths from `docs/`, `scripts/`, `dashboard/`, and `systemd/` non-archive surfaces.
- Redacted dashboard hostname exposure by default in the declarative runtime.

### Current Runtime Truth

- Canonical deployment path: `./scripts/deploy/deploy-clean.sh`
- Authoritative dashboard runtime: `command-center-dashboard-api.service`
- Operator URL: `http://127.0.0.1:8889/`
- Local dashboard development only: `cd dashboard && ./start-dashboard.sh`

### Evidence Highlights

- Dashboard/runtime commits executed across runtime authority, health alignment, contract normalization, mock fallback removal, legacy-surface quarantine, active-doc cleanup, privacy/path cleanup, and README refresh.
- Active non-archive scan for `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy`, `/home/hyperd/.nix-profile`, and absolute local markdown links is clean in `docs/`, `scripts/`, `dashboard/`, and `systemd/`.
- Dashboard hostname is now redacted by default through:
  - `DASHBOARD_EXPOSE_HOSTNAME=false`
  - `DASHBOARD_HOSTNAME_ALIAS=local-node`

### Security / Privacy Findings From This Pass

- No confirmed live API key or private key blob was found in active repo content from the local scans available during this pass.
- Expected references to `/run/secrets/*` remain and are intentional.
- Remaining machine-specific tracked content is mostly intentional host inventory/config, primarily under `nix/hosts/*`.

### Residual Follow-up

- Decide whether tracked host-specific files under `nix/hosts/*` and `nix/hosts/nixos/deploy-options.local.nix` should remain in-repo, be templated further, or move to local-only handling.
- If stronger assurance is required, run a detector-backed secret scan (`gitleaks` and/or `trufflehog`) in a later pass when those tools are available.
- Continue field-by-field dashboard contract tightening only if new retained surfaces or widgets are added.

## Scope Lock

### Objective

Clean up the repository and runtime so that:

- the declarative Nix/systemd path is the single operational authority,
- the command-center dashboard uses one backend/API contract for all fields,
- legacy scripts, shims, and docs stop competing with the authoritative path,
- health checks and service discovery reflect the actual runtime,
- mock/demo fallback does not mask production failures.

### Constraints

- No hardcoded secrets or new literal service URLs/ports.
- Prefer declarative Nix/module changes over imperative scripts.
- Do not remove compatibility shims until references are audited and gates pass.
- One logical change set per phase.

### Out of Scope

- New feature work unrelated to cleanup/stability.
- Re-platforming the dashboard stack.
- Container spin-off execution from `docs/development/AI-STACK-CONTAINER-SPINOFF.md`.

### Acceptance Checks

- `scripts/health/system-health-check.sh --detailed`
- `scripts/governance/repo-structure-lint.sh --all`
- dashboard smoke against live API data
- no production dashboard path depends on mock data or browser-side hardcoded ports
- health/unit checks match actual declarative runtime

## Execution Protocol

For each phase:

1. Change only the files listed for the phase.
2. Run the validation commands for the phase.
3. Record evidence: files changed, commands run, outputs, rollback note.
4. Reviewer decides `accept` or `reject`.
5. Do not start the next phase unless the current gate passes.

---

## Phase 1: Establish Runtime Authority

### Goal

Make the declarative Nix-managed dashboard/service path the only authoritative runtime path.

### Files To Change First

- `nix/modules/services/command-center-dashboard.nix`
- `config/service-endpoints.sh`
- `scripts/deploy/start-unified-dashboard.sh`
- `scripts/deploy/serve-dashboard.sh`
- `lib/dashboard.sh`
- `dashboard/README.md`

### Tasks

1. Confirm the intended runtime model in the Nix module and document it in one place.
2. Decide whether `scripts/deploy/start-unified-dashboard.sh` remains as:
   - a read-only compatibility shim that points users to systemd, or
   - a local-dev only helper with explicit non-production wording.
3. Remove any operational wording that implies a separate frontend/backend service model if the Nix module is serving a unified path.
4. Align `config/service-endpoints.sh` comments and defaults with the actual runtime authority.
5. Update dashboard docs so operators are told to use the declarative service, not ad hoc startup scripts.

### Expected Outcome

- One documented runtime authority.
- No ambiguity about whether dashboard startup is imperative or declarative.

### Validation

- `rg -n "start-unified-dashboard|serve-dashboard|command-center-dashboard" docs dashboard scripts nix`
- `bash scripts/health/system-health-check.sh --detailed`

### Rollback

Revert only the touched dashboard runtime/docs files for this phase.

### Reviewer Gate

Accept only if:

- the Nix service is clearly the production authority,
- helper scripts no longer imply a competing production path,
- operator docs point to one runtime path only.

---

## Phase 2: Lock Dashboard Data Contract

### Goal

Define a single source of truth for every dashboard field and route all UI data through backend APIs.

### Files To Change First

- `dashboard/backend/api/main.py`
- `dashboard/backend/api/routes/aistack.py`
- `dashboard/backend/api/routes/metrics.py`
- `dashboard/backend/api/routes/services.py`
- `dashboard/backend/api/config/service_endpoints.py`
- `dashboard/frontend/src/lib/api.ts`
- `dashboard/frontend/src/types/metrics.ts`
- `dashboard/frontend/src/stores/dashboardStore.ts`
- `dashboard/INTEGRATION-WITH-AI-STACK.md`

### Tasks

1. Inventory every visible dashboard field and map it to:
   - backend route,
   - upstream service or DB query,
   - freshness/refresh cadence,
   - nullable or required status.
2. Add or normalize backend endpoints where field coverage is incomplete.
3. Remove frontend assumptions about fixed ports and direct host-local socket URLs.
4. Make frontend HTTP and WebSocket base paths derive from current origin or injected config.
5. Add explicit response typing for dashboard payloads so the UI cannot silently accept partial/malformed data.

### Expected Outcome

- Every dashboard field is traceable.
- Frontend only consumes backend-defined contracts.

### Validation

- `rg -n "localhost:|127.0.0.1:|ws://.*8889" dashboard/frontend dashboard/control-center.html dashboard.html`
- frontend build/test command used by repo for dashboard frontend
- backend route smoke against `/api/health`, `/api/health/aggregate`, `/api/services`, `/api/metrics/system`

### Rollback

Revert dashboard backend/frontend contract changes if route compatibility breaks.

### Reviewer Gate

Accept only if:

- every retained field has a real backend source,
- frontend code no longer hardcodes operational ports,
- contract gaps are listed explicitly instead of hidden.

---

## Phase 3: Remove Mock Masking From Production

### Goal

Stop production dashboards from presenting synthetic success when live data is unavailable.

### Files To Change First

- `dashboard.html`
- `dashboard/control-center.html`
- `dashboard/frontend/src/App.tsx`
- `dashboard/frontend/src/components/SystemOverview.tsx`
- `dashboard/frontend/src/components/AIInternals.tsx`
- `dashboard/frontend/src/lib/api.ts`
- `dashboard/SETUP-ISSUES.md`

### Tasks

1. Identify all mock/demo fallback paths in legacy and current dashboard surfaces.
2. Gate demo fallback behind an explicit flag or dev-only mode.
3. Replace silent mock substitution with visible `degraded`, `unavailable`, or `mock` status badges.
4. Ensure aggregate health reflects backend truth, not inferred UI state.
5. Document the operator-visible meaning of `healthy`, `degraded`, `unavailable`, and `mock`.

### Expected Outcome

- Production failures become visible.
- Demo behavior remains available only when intentionally enabled.

### Validation

- `rg -n "mock|placeholder|sample|demo|fallback" dashboard.html dashboard/control-center.html dashboard/frontend/src`
- dashboard smoke with one upstream dependency intentionally unavailable

### Rollback

Revert UI-state changes if they make the dashboard unusable, but keep evidence of missing field coverage.

### Reviewer Gate

Accept only if:

- production mode never auto-fills operational cards with mock data,
- failure states are visible and specific,
- demo behavior is explicit, not default.

---

## Phase 4: Align Health Checks With Real Services

### Goal

Make health scripts and dashboard service discovery reflect the actual declarative unit set.

### Files To Change First

- `scripts/health/system-health-check.sh`
- `dashboard/backend/api/services/systemd_units.py`
- `dashboard/backend/api/routes/aistack.py`
- `scripts/ai/ai-stack-health.sh`
- `scripts/data/generate-dashboard-data.sh`
- `docs/operations/reference/QUICK-REFERENCE.md`

### Tasks

1. Remove checks for units that are no longer required or no longer exist.
2. Decide whether `command-center-dashboard-frontend.service` is real, optional, or retired.
3. Make service discovery derive from authoritative units/targets where possible.
4. Ensure dashboard aggregate health and CLI health scripts use the same unit inventory rules.
5. Update operator docs to match the corrected health model.

### Expected Outcome

- No false failures from stale unit names.
- CLI and dashboard health agree on what “up” means.

### Validation

- `bash scripts/health/system-health-check.sh --detailed`
- dashboard aggregate health endpoint check
- compare CLI unit inventory with backend-discovered unit inventory

### Rollback

Restore previous health-check logic if critical runtime checks were accidentally dropped.

### Reviewer Gate

Accept only if:

- health checks track the actual runtime,
- stale dashboard unit expectations are removed or explicitly justified,
- dashboard and CLI health outputs are consistent.

---

## Phase 5: Retire High-Drift Shims And Legacy Dashboard Surfaces

### Goal

Reduce repo surface area by retiring the most misleading compatibility layers and duplicate dashboard entry points.

### Files To Change First

- `docs/operations/REPO-CLEANUP-INVENTORY-PASS2.csv`
- `scripts/enhance-dashboard-with-controls.sh`
- `scripts/configure-podman-tcp.sh`
- `scripts/sync_docs_to_ai.sh`
- `scripts/skill-bundle-registry.py`
- `dashboard/control-center.html`
- `dashboard/MIGRATION.md`
- `docs/operations/reference/DASHBOARD-READY.md`

### Tasks

1. Use the cleanup inventory to rank root shims by reference count and operator confusion.
2. Retire or archive the highest-confusion shims first after call-site audit.
3. Decide whether `dashboard/control-center.html` remains:
   - archived,
   - dev-only,
   - or integrated into the single supported dashboard path.
4. Replace stale references in docs with the canonical dashboard/API entry point.
5. Update inventory status as each shim or legacy surface is removed or quarantined.

### Expected Outcome

- Fewer duplicate entry points.
- Lower operator confusion and smaller maintenance surface.

### Validation

- `rg -n "control-center.html|dashboard.html|enhance-dashboard-with-controls|sync_docs_to_ai.sh|skill-bundle-registry.py" docs scripts dashboard`
- `scripts/governance/repo-structure-lint.sh --all`

### Rollback

Restore specific shim/archive changes if hidden consumers are discovered.

### Reviewer Gate

Accept only if:

- the highest-confusion legacy entry points are retired or explicitly quarantined,
- call sites are updated,
- cleanup inventory reflects reality.

---

## Phase 6: Final Stabilization And Evidence Pack

### Goal

Verify that the cleaned runtime, dashboard, and documentation all converge on the same operational truth.

### Files To Change First

- `.agents/plans/PROJECT-CLEANUP-EXECUTION-PASS.md`
- `docs/operations/OPERATOR-RUNBOOK.md`
- `docs/operations/reference/QUICK-REFERENCE.md`
- `docs/development/AI-STACK-CONTAINER-SPINOFF.md`

### Tasks

1. Record the final authoritative runtime and dashboard architecture.
2. Capture before/after evidence:
   - files removed or demoted,
   - hardcoded endpoint references eliminated,
   - health checks corrected,
   - dashboard field coverage validated.
3. Add residual risks and deferred follow-ups.
4. Document deploy, verify, and rollback commands for operators.

### Expected Outcome

- Clean handoff package with evidence.
- Remaining debt is explicit and bounded.

### Validation

- `scripts/health/system-health-check.sh --detailed`
- `scripts/governance/repo-structure-lint.sh --all`
- any dashboard-specific smoke/QA command adopted during Phases 2-4

### Rollback

Use phase-level reverts; do not revert the full cleanup program at once unless runtime regression is confirmed.

### Reviewer Gate

Accept only if:

- evidence exists for every completed phase,
- no unresolved runtime ambiguity remains,
- the command-center dashboard is verifiably backed by live data for all retained fields.

---

## Recommended Phase Order

1. Phase 1
2. Phase 4
3. Phase 2
4. Phase 3
5. Phase 5
6. Phase 6

Reason:

- runtime authority and health alignment should be fixed before frontend cleanup,
- contract work should happen before mock-fallback removal,
- shim retirement should happen after the canonical path is stable.

## Phase Completion Snapshot

| Phase | Status | Notes |
| --- | --- | --- |
| 1. Establish Runtime Authority | Complete | Declarative command center runtime established as operator authority. |
| 2. Lock Dashboard Data Contract | Partial | Data-path normalization and dev-runtime parameterization completed; full field-by-field contract inventory remains optional follow-up. |
| 3. Remove Mock Masking From Production | Complete | Production mock masking removed; demo fallback explicit only. |
| 4. Align Health Checks With Real Services | Complete | CLI/backend/dashboard health expectations aligned with actual units/runtime. |
| 5. Retire High-Drift Shims And Legacy Dashboard Surfaces | Complete | Legacy surfaces quarantined; active docs/operator references updated. |
| 6. Final Stabilization And Evidence Pack | Partial | Evidence consolidated here and in README/operator docs; no separate evidence pack doc created. |

## Evidence Template Per Phase

- Files changed:
- Commands run:
- Tests run:
- Evidence output:
- Rollback note:
- Reviewer decision:
- Reviewer reason:
