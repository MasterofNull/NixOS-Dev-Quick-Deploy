# AI Stack Workflow Consolidation Plan
**Created:** 2025-12-22
**Status:** Implemented
**Owner:** Codex

---

## Summary
Consolidate overlapping AI stack workflows in the NixOS quick deploy system to reduce duplicated prompts, inconsistent startup paths, and fragile container dependencies. This focuses on a single source of truth for model selection, stack start/stop, health checks, and logging.

## Evidence
- Repeated AI stack startup paths (phase-08 inline starts, post-deploy start script, helper scripts).
- Repeated model selection prompts (user settings + optional AI deployment).
- Podman dependency errors when starting a single service without existing dependency containers.

## Proposed Change
Create one canonical workflow for AI stack activation and health checks, and route all call sites through it. Reduce model selection to a single prompt in `lib/user.sh` and propagate it consistently.

### In Scope
- AI stack start/stop entry points and logging.
- Model selection and preference storage.
- Health-check consolidation.
- Runtime selection (podman/podman-compose/docker compose) consistency.

### Out of Scope
- Changing container images or service topology.
- Removing services (AIDB, Qdrant, etc.).

## Plan (Step-by-Step)
1. **Define canonical entry points**
   - Designate `scripts/hybrid-ai-stack.sh` as the only stack start/stop CLI.
   - Make `scripts/podman-ai-stack.sh` and `scripts/ai-stack-manage.sh` thin wrappers or document-only helpers.

2. **Model selection single source**
   - Keep model selection in `lib/user.sh` only.
   - Remove any remaining prompts from optional phases and consume cached preference.
   - Consolidate to one preference file and keep backward compatibility readers.

3. **Startup flow simplification**
   - Phase 8 becomes report-only; stack startup happens post-deploy.
   - `scripts/start-ai-stack-and-dashboard.sh` becomes the only place that starts the stack.

4. **Health checks consolidation**
   - Create a single health check entry point that calls subchecks.
   - Update references to use the unified health check script.

5. **Logging normalization**
   - All AI stack starts log to `~/.cache/nixos-quick-deploy/logs/ai-stack-start-*.log`.
   - Health checks log to `~/.cache/nixos-quick-deploy/logs/ai-stack-health-*.log`.

6. **Docs updates**
   - Update quick start docs to refer to the canonical scripts.
   - Remove or de-emphasize alternative start paths.

## Impact
- **Performance:** Fewer redundant checks; shorter deploy time.
- **Reliability:** Eliminates dependency-related podman-compose failures.
- **Maintenance:** Less duplicated logic to keep in sync.
- **Security:** No change expected.

## Risks & Mitigations
- **Risk:** Users rely on legacy scripts.
  - **Mitigation:** Keep wrappers and provide deprecation notes.
- **Risk:** Preference migration edge cases.
  - **Mitigation:** Read old preferences for one release cycle.

## Rollback Plan
- Restore previous start logic in phase 8 and post-deploy scripts.
- Re-enable standalone stack management scripts if needed.
- Verify with a single run of quick deploy and `hybrid-ai-stack.sh status`.

## Approval Required
- Confirm the canonical entry point choice and permission to remove/reduce alternate paths.

## Sources & References
- `nixos-quick-deploy.sh`
- `phases/phase-08-finalization-and-report.sh`
- `scripts/hybrid-ai-stack.sh`
- `scripts/podman-ai-stack.sh`
- `scripts/start-ai-stack-and-dashboard.sh`

---

## Decision
**Approved by:**  
**Date:** 2025-12-22  
**Notes:** Implemented consolidation: single stack entrypoint, unified health checks, consolidated preferences, updated docs.  
