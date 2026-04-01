# Pre-Deploy Summary — 2026-03-31

**Status:** Ready for deployment
**Unpushed Commits:** 24
**QA Status:** 36/36 checks passed

---

## Completed Before Redeploy

### Phase 4: End-to-End Workflows (100%)
- ✅ All smoke tests passing (4.1, 4.2, 4.3)
- ✅ Security audit integrated into deploy pipeline
- ✅ ADK discovery workflow active
- ✅ Feature flag audit complete
- ✅ Dashboard workflow visibility implemented

### Phase 5: Performance Optimization (100%)
- ✅ Query P95: ~1.3ms (target: <500ms)
- ✅ Dashboard load: ~5ms (target: <2s)
- ✅ Parallel health checks: `deploy health --parallel`
- ✅ Quality cache integrated in `/query` endpoint
- ✅ Parallel collection searches (60-75% latency reduction)

### Recent Fixes
- Fixed COSMIC greeter builder file cleanup
- Fixed AMD GPU overdrive disabled for stability
- Fixed missing asyncio import for parallel searches
- Fixed structlog compatibility in route_handler.py
- Added captive-portal CLI for wifi login bypass
- Added local agent offline resilience config
- Codified upstream PR lessons into tool-recommendations-seed.yaml

---

## Gated By System Redeploy

The following require `nixos-rebuild switch` to take effect:

### Kernel Upgrade (Optional)
```nix
# In nix/hosts/hyperd/default.nix:
mySystem.kernel.track = "6.19-latest";
```
Benefits: AMD GPU boost, HDR improvements, ext4 enhancements

### Maximum Kernel Hardening (Optional)
```nix
mySystem.kernel.hardening = {
  enable = true;
  level = "maximum";  # CFI, shadow call stack, lockdown
};
```
Benefits: Protection against 67% of kernel CVEs (memory safety class)

### CrowdSec IPS (Optional)
```nix
mySystem.security.crowdsec = {
  enable = true;
  watchSshd = true;
  # enableFirewallBouncer = true;  # Requires apiKeyFile setup first
};
```
Benefits: Community-shared threat intelligence, auto-ban attackers

### Secure Boot (Optional - Requires Manual Steps)
```nix
mySystem.secureboot.enable = true;  # Uses lanzaboote
```
Requires: Manual key enrollment in firmware

---

## Post-Deploy Verification Queue

1. Verify crash-mitigation changes activated cleanly
2. Confirm no audit storm patterns (`audit_log_subj_ctx`)
3. Confirm COSMIC greeter starts without config churn
4. Confirm hybrid coordinator has no checkpoint resume errors
5. Run `aq-report` and `aq-qa 0` to validate harness state
6. If stable, resume: hint anti-dominance, synthetic-gap suppression

---

## Service Restart Required

After deploy, these services will auto-restart with new code:
- `ai-hybrid-coordinator.service` (parallel search, structlog fixes)
- `command-center-dashboard-api.service` (workflow visibility)

---

## Deploy Command

```bash
# Quick deploy
./deploy system

# Or full rebuild
nixos-rebuild switch --flake .#hyperd
```

---

## Commits Ready to Push

24 commits including:
- Performance optimizations (route-search, classifier, reporting)
- Bug fixes (prewarm, reporting, continue editor)
- Documentation updates (roadmap completion)

Push with: `git push origin main`
