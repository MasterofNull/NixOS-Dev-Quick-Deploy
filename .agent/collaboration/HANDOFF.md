# Handoff Memo - 2026-05-17

**Status:** DEPLOY-TIME MEMORY RELIEF SLICE COMPLETE
**Last Action:** Added configurable live-switch memory relief around activation.

## Findings
- Prior AppArmor reload failures were consistent with host memory pressure, not oversized policy.
- `llama-cpp.service` is the dominant live memory consumer during normal operation (~15 GiB), while the dashboard is materially smaller and worth keeping online.
- The smallest useful default pause set is therefore `llama-cpp.service` only.

## Change made
- Added deploy-time memory relief controls to `nixos-quick-deploy.sh`:
  - `ACTIVATION_MEMORY_RELIEF_ENABLED=true`
  - `ACTIVATION_MEMORY_RELIEF_UNITS="llama-cpp.service"`
- Live switch mode now:
  1. frees blocked AI ports,
  2. pauses configured active high-memory units,
  3. runs `nixos-rebuild switch`,
  4. resumes any units it actually paused.
- Cleanup also restores paused units if activation exits early.
- Added runtime-contract and roadmap-verifier coverage so the pause/resume path is guarded against accidental removal.

## Validation
- `bash -n nixos-quick-deploy.sh scripts/testing/verify-flake-first-roadmap-completion.sh` passed.
- `./nixos-quick-deploy.sh --self-check` passed.
- `bash scripts/testing/verify-flake-first-roadmap-completion.sh` passed: `603 pass, 0 fail`.
- `scripts/governance/tier0-validation-gate.sh --pre-commit` run for repo-required validation.

## Related stable state from prior slices
- Dashboard trace timeline remains live.
- Phase 55 superseder/crystallizer schema warnings are resolved.
- Identity kernel runtime permissions are repaired.
- Readiness analysis now warns on low activation memory headroom before deploy.

## Next recommended slice
Run one real live-switch deploy with the new relief path enabled, confirm the logs show `llama-cpp.service` pausing/resuming around activation, and compare whether AppArmor reloads complete cleanly under otherwise similar host pressure.
