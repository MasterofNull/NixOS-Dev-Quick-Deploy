# Handoff Memo - 2026-05-17

**Status:** APPARMOR ACTIVATION RELIABILITY SLICE COMPLETE
**Last Action:** Added deploy-readiness visibility for low activation memory headroom.

## Findings
- Intermittent `apparmor.service` reload failures are not profile-size driven.
- AppArmor profiles are small and usually reload successfully.
- Failed reloads report `Out of memory` and occurred while the host was under severe RAM pressure.
- Current runtime snapshot during investigation: ~27 GiB total RAM, ~26 GiB used, very low available memory, swap active.

## Change made
- Added `Activation Headroom` readiness analysis to `scripts/governance/analyze-clean-deploy-readiness.sh`.
- New env override: `MIN_ACTIVATION_MEM_AVAILABLE_MB` (default `1024`).
- Readiness now warns when `MemAvailable` is below the configured threshold and explicitly calls out AppArmor reload risk.
- Documented the override in `nixos-quick-deploy.sh --help` output.

## Validation
- `bash -n scripts/governance/analyze-clean-deploy-readiness.sh nixos-quick-deploy.sh` passed.
- Forced-threshold smoke run emitted the expected low-headroom warning.

## Related stable state from prior slices
- Dashboard trace timeline remains live.
- Phase 55 superseder/crystallizer schema warnings are resolved.
- Identity kernel runtime permissions are repaired.

## Next recommended slice
If AppArmor reload failures recur despite operator awareness, investigate deploy-time memory relief strategies separately (for example pausing high-memory local inference workloads before live activation). Do not weaken AppArmor policy as a first response.
