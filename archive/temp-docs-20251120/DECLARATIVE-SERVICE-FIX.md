# Declarative Service Conflict Fix ✅

**Date**: 2025-11-16
**Status**: ✅ **FIXED - Pure Declarative Solution**
**Impact**: Eliminates port conflicts through proper conditional logic

---

## Problem

Port conflicts occurred between system-level and user-level AI services:
- System qdrant.service running on ports 6333/6334
- User podman-local-ai-qdrant.service trying to use same ports
- Result: `Error: bind: address already in use`

### Root Cause

The configuration template had **inverted logic** for the qdrant service:

**Before** (templates/configuration.nix:603):
```nix
systemd.services.qdrant = lib.mkIf localAiStackEnabled {
  # This ENABLED system qdrant when user stack was enabled!
  # Creating a port conflict with user-level qdrant
}
```

This meant:
- When `localAiStackEnabled = true`: Both system AND user qdrant services would try to start
- Result: Port conflict, user service fails

### Comparison with Ollama

The ollama service had **correct logic**:

```nix
services.ollama = lib.mkIf (!localAiStackEnabled) {
  # Correctly DISABLED when user stack enabled
}
```

---

## The Fix (Declarative & Permanent)

### Change: Fix Conditional Logic

**File**: [templates/configuration.nix:604](templates/configuration.nix#L604)

**Before**:
```nix
systemd.services.qdrant = lib.mkIf localAiStackEnabled {
```

**After**:
```nix
systemd.services.qdrant = lib.mkIf (!localAiStackEnabled) {
```

**Impact**: System qdrant now properly disables when user-level AI stack is enabled

---

## How It Works Now

### Service Selection Matrix

| `localAiStackEnabled` | System Ollama | System Qdrant | User Podman Stack |
|----------------------|---------------|---------------|-------------------|
| `false` | ✅ **Enabled** | ✅ **Enabled** | ❌ Disabled |
| `true` | ❌ **Disabled** | ❌ **Disabled** | ✅ Enabled |

**Key**: Only ONE level of services runs at a time - no conflicts!

### Configuration Flow

```
User sets in home.nix:
  localAiStackEnabled = true;
        ↓
        ├─→ System Config (configuration.nix)
        │   ├─ services.ollama = lib.mkIf (!localAiStackEnabled)
        │   │  Result: DISABLED ✓
        │   └─ systemd.services.qdrant = lib.mkIf (!localAiStackEnabled)
        │      Result: DISABLED ✓
        │
        └─→ User Config (home.nix)
            └─ services.podman = lib.mkIf localAiStackEnabled
               ├─ containers.ollama
               │  Result: ENABLED on port 11434 ✓
               └─ containers.qdrant
                  Result: ENABLED on ports 6333/6334 ✓

No Port Conflicts! ✅
```

---

## Benefits of Declarative Fix

### Before (Runtime Conflict Resolution)
- ❌ Required detecting conflicts at runtime (Phase 5)
- ❌ Needed to stop/mask system services manually
- ❌ Required sudo access during deployment
- ❌ Post-deployment patches needed
- ❌ Services would restart and conflict again

### After (Declarative Prevention)
- ✅ Conflicts prevented at configuration generation (Phase 3)
- ✅ No runtime detection needed
- ✅ No sudo operations required
- ✅ No post-deployment patches
- ✅ System rebuilds correctly every time
- ✅ **Pure declarative solution**

---

## Verification

### Check Template Logic
```bash
$ grep -A 1 "systemd.services.qdrant" templates/configuration.nix
systemd.services.qdrant = lib.mkIf (!localAiStackEnabled) {
  description = "Qdrant Vector Database";
```
✅ Condition is `!localAiStackEnabled` (correct!)

### Check Generated Config
```bash
$ grep -A 1 "systemd.services.qdrant" ~/.dotfiles/home-manager/configuration.nix
systemd.services.qdrant = lib.mkIf (!localAiStackEnabled) {
```
✅ Generated config has correct logic

### Test Deployment
```bash
$ ./nixos-quick-deploy.sh --start-from-phase 3

# With localAiStackEnabled = true:
# - System qdrant will NOT be defined
# - User qdrant will be enabled
# - No port conflicts!
```

---

## Complete Service Logic

### System-Level Services (configuration.nix)

```nix
# Ollama - AI inference
services.ollama = lib.mkIf (!localAiStackEnabled) {
  enable = true;
  # ... configuration ...
};

# Qdrant - Vector database
systemd.services.qdrant = lib.mkIf (!localAiStackEnabled) {
  # ... systemd service definition ...
};
```

### User-Level Services (home.nix)

```nix
services.podman = lib.mkIf localAiStackEnabled {
  enable = true;

  containers = {
    # Ollama container
    "local-ai-ollama" = {
      image = "docker.io/ollama/ollama:latest";
      ports = [ "11434:11434" ];
      # ... container config ...
    };

    # Qdrant container
    "local-ai-qdrant" = {
      image = "docker.io/qdrant/qdrant:latest";
      ports = [ "6333:6333" "6334:6334" ];
      # ... container config ...
    };
  };
};
```

**Logic**: The `!` in `!localAiStackEnabled` ensures mutual exclusion!

---

## Migration Notes

### For Existing Deployments

If you already have a system with the old (broken) logic:

1. **Regenerate configurations**:
   ```bash
   ./nixos-quick-deploy.sh --start-from-phase 3
   ```

2. **Rebuild system**:
   ```bash
   sudo nixos-rebuild switch --flake ~/.dotfiles/home-manager#$(hostname)
   ```

3. **Verify no conflicts**:
   ```bash
   sudo systemctl status qdrant.service
   # Should show: Loaded: loaded ... inactive (dead)

   systemctl --user status podman-local-ai-qdrant.service
   # Should show: Active: active (running)
   ```

### For New Deployments

No action needed! The fix is automatic:
```bash
./nixos-quick-deploy.sh
```

---

## What This Eliminates

### No Longer Needed

1. ❌ **Service conflict detection** (Phase 5, Step 6.5)
   - Can be removed or kept as safety check

2. ❌ **Runtime service masking**
   - Services never start in first place

3. ❌ **Manual port conflict resolution**
   - Conflicts prevented declaratively

4. ❌ **Post-deployment patches**
   - System configured correctly from start

### Still Useful (Optional Safety)

The conflict detection in Phase 5 can remain as a **safety check** but should never trigger with correct configuration:

```bash
# In phase-05-declarative-deployment.sh:296-309
# This should now always pass:
if ! pre_home_manager_conflict_check; then
    print_warning "Unexpected conflict detected - configuration may be incorrect"
fi
```

---

## Testing the Fix

### Test 1: Template Logic
```bash
$ grep "systemd.services.qdrant.*mkIf" templates/configuration.nix
systemd.services.qdrant = lib.mkIf (!localAiStackEnabled) {
```
✅ Has negation operator `!`

### Test 2: Configuration Generation
```bash
$ rm ~/.local/share/nixos-quick-deploy/state/phase-03-*.completed
$ ./nixos-quick-deploy.sh --test-phase 3
✓ Phase 3: Configuration Generation - COMPLETE
```

### Test 3: Service Status After Rebuild
```bash
# With localAiStackEnabled = true:
$ sudo systemctl list-unit-files | grep -E "ollama|qdrant"
# Should show: (none) or disabled

$ systemctl --user list-unit-files | grep "local-ai"
podman-local-ai-ollama.service    enabled
podman-local-ai-qdrant.service    enabled
```

### Test 4: Port Check
```bash
$ ss -tlnp | grep -E ":(6333|6334|11434)"
# Should show user-level services only (in user's uid namespace)
```

---

## Comparison: Before vs After

### Before Fix (Runtime Resolution)
```
Phase 3: Generate configs
Phase 4: Validation
Phase 5: Deploy
  ├─ Step 6.5: Detect conflicts ← CONFLICT FOUND!
  ├─ Stop system qdrant ← Requires sudo
  ├─ Mask system qdrant ← Runtime patch
  └─ Start user qdrant ← Finally works
```
**Result**: Works but requires runtime intervention

### After Fix (Declarative)
```
Phase 3: Generate configs
  ├─ localAiStackEnabled = true
  ├─ systemd.services.qdrant = lib.mkIf (!localAiStackEnabled)
  └─ Result: Service NOT defined ← Conflict prevented!
Phase 4: Validation ← No conflicts
Phase 5: Deploy
  ├─ Step 6.5: Check conflicts ← Should pass
  └─ Start services ← Works immediately
```
**Result**: Pure declarative solution

---

## Documentation Links

- [PORT-CONFLICT-SOLUTION.md](PORT-CONFLICT-SOLUTION.md) - Original runtime solution
- [NIXOS-SERVICE-CONFLICT-FIX.md](NIXOS-SERVICE-CONFLICT-FIX.md) - Service masking approach
- [templates/configuration.nix](templates/configuration.nix#L604) - Fixed template
- [templates/home.nix](templates/home.nix#L3570) - User-level config

---

## Summary

**Issue**: Port conflicts due to incorrect conditional logic in configuration template
**Root Cause**: `systemd.services.qdrant = lib.mkIf localAiStackEnabled` enabled BOTH levels
**Fix**: Changed to `lib.mkIf (!localAiStackEnabled)` - negation operator added
**Impact**: Pure declarative solution - no runtime patches needed
**Status**: ✅ **FIXED - One line change, permanent solution**

This is the NixOS way - **declarative, reproducible, conflict-free!** 🎉

---

**Resolution**: ✅ COMPLETE
**Type**: Declarative configuration fix
**Lines Changed**: 1 line in templates/configuration.nix
**Deployment**: Automatic on next configuration generation
