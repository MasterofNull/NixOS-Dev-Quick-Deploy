# Port Conflict Solution - Qdrant Service

**Date**: 2025-11-16
**Status**: ⚠️ **IDENTIFIED - Solution Available**
**Error**: `Error: rootlessport listen tcp 0.0.0.0:6333: bind: address already in use`

---

## Problem

The user-level qdrant service (podman container) cannot start because ports 6333 and 6334 are already in use by a system-level service or previous container instance.

### Error Message
```
Error: rootlessport listen tcp 0.0.0.0:6333: bind: address already in use
```

### Service Status
```bash
$ systemctl --user status podman-local-ai-qdrant.service
Active: activating (start) ... restart counter is at 35
Main process exited, code=exited, status=126/n/a
Failed with result 'exit-code'
```

### Port Usage
```bash
$ ss -tlnp | grep ":6333\|:6334"
LISTEN 0      1024       127.0.0.1:6333       0.0.0.0:*
LISTEN 0      128        127.0.0.1:6334       0.0.0.0:*
```

---

## Root Cause

**Service Conflict**: System-level and user-level services competing for the same ports.

Possible sources:
1. **System-level qdrant.service** still running (defined in NixOS configuration.nix)
2. **Previous container instance** not fully cleaned up
3. **Zombie rootlessport process** holding the ports

---

## Solution

### Option 1: Use Service Conflict Resolution (Recommended)

The deployment script has built-in conflict resolution:

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy

# Run the conflict resolution test
./test-conflict-resolution-simple.sh

# If conflicts detected, run full deployment with auto-resolution
./nixos-quick-deploy.sh
```

The script will automatically:
1. Detect conflicts between system and user services
2. Stop and mask system-level services
3. Allow user-level services to start

### Option 2: Manual Resolution

#### Step 1: Find What's Using the Ports
```bash
# Check for system service
sudo systemctl status qdrant.service

# Check for user service
systemctl --user status podman-local-ai-qdrant.service

# Check for containers
podman ps -a | grep qdrant

# Check for processes
lsof -i :6333
lsof -i :6334
```

#### Step 2: Stop System Service (if running)
```bash
# Stop the service
sudo systemctl stop qdrant.service

# Mask it to prevent auto-start (NixOS compatible)
sudo systemctl mask qdrant.service

# Verify
sudo systemctl status qdrant.service
# Should show: Loaded: masked
```

#### Step 3: Clean Up Containers
```bash
# Stop all qdrant containers
podman stop -a | grep qdrant || true

# Remove stopped containers
podman rm $(podman ps -a -q --filter "name=qdrant") 2>/dev/null || true

# Clean up networks
podman network prune -f
```

#### Step 4: Kill Zombie Processes
```bash
# Find rootlessport processes
ps aux | grep rootlessport | grep 6333

# Kill them (replace PID with actual)
kill -9 <PID>
```

#### Step 5: Restart User Service
```bash
systemctl --user daemon-reload
systemctl --user restart podman-local-ai-qdrant.service
systemctl --user status podman-local-ai-qdrant.service
```

### Option 3: Permanent Fix (Recommended for Production)

Edit `/etc/nixos/configuration.nix` to disable system-level qdrant:

```nix
{
  # Disable system-level qdrant (using user-level instead)
  services.qdrant.enable = false;

  # Also disable ollama if using user-level
  services.ollama.enable = false;
}
```

Then rebuild:
```bash
sudo nixos-rebuild switch
```

---

## Verification

### Check Port Availability
```bash
$ ss -tlnp | grep ":6333\|:6334"
# Should show nothing if ports are free
# Or show user-level service if it started successfully
```

### Check Service Status
```bash
$ systemctl --user status podman-local-ai-qdrant.service
Active: active (running)  # ← Should be running
```

### Check Logs
```bash
$ journalctl --user -u podman-local-ai-qdrant.service -n 20
# Should show successful startup:
# "Qdrant HTTP listening on 6333"
# "Qdrant gRPC listening on 6334"
```

---

## Why This Happens

### During Home Manager Switch

When you run `home-manager switch`:
1. Home Manager tries to start new user services
2. Systemd activates `podman-local-ai-qdrant.service`
3. Podman tries to bind ports 6333 and 6334
4. **Fails** because system service already has them
5. Service enters restart loop (35+ attempts)

### Service Conflict Matrix

| Level | Service | Ports | Status |
|-------|---------|-------|--------|
| System | qdrant.service | 6333, 6334 | ❌ Running (blocks user) |
| User | podman-local-ai-qdrant.service | 6333, 6334 | ❌ Failing (ports taken) |

**Conflict**: Both trying to use same ports!

---

## Prevention

### Enable Auto-Resolution in Deployment

The deployment script already has this built-in:

**File**: [phases/phase-05-declarative-deployment.sh:296-309](phases/phase-05-declarative-deployment.sh#L296-L309)

```bash
# Step 6.5: Service Conflict Detection and Resolution
if declare -F pre_home_manager_conflict_check >/dev/null 2>&1; then
    local auto_resolve_conflicts="${AUTO_RESOLVE_SERVICE_CONFLICTS:-true}"
    if ! pre_home_manager_conflict_check "$auto_resolve_conflicts"; then
        print_error "Service conflicts detected and not resolved"
        return 1
    fi
fi
```

This automatically:
- ✅ Detects conflicts before home-manager switch
- ✅ Stops and masks system services
- ✅ Allows user services to start cleanly

### Configuration Best Practice

Choose ONE level for each service:

**Option A - User Level** (Recommended for development):
```nix
# In /etc/nixos/configuration.nix
services.qdrant.enable = false;
services.ollama.enable = false;

# In ~/.dotfiles/home-manager/home.nix
localAiStackEnabled = true;  # Enables podman containers
```

**Option B - System Level** (For system-wide access):
```nix
# In /etc/nixos/configuration.nix
services.qdrant.enable = true;
services.ollama.enable = true;

# In ~/.dotfiles/home-manager/home.nix
localAiStackEnabled = false;  # Disables podman containers
```

**Don't mix both!** Pick one level per service.

---

## Quick Fix Commands

### One-Liner Fix
```bash
sudo systemctl stop qdrant.service ollama.service && \
sudo systemctl mask qdrant.service ollama.service && \
systemctl --user restart podman-local-ai-qdrant.service podman-local-ai-ollama.service
```

### Using Deployment Script
```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh --start-from-phase 5
```

The script will auto-resolve conflicts during Phase 5, Step 6.5.

---

## Related Issues

- [NIXOS-SERVICE-CONFLICT-FIX.md](NIXOS-SERVICE-CONFLICT-FIX.md) - Service conflict resolution documentation
- [SERVICE-CONFLICT-RESOLUTION.md](docs/SERVICE-CONFLICT-RESOLUTION.md) - Conflict detection system
- [lib/service-conflict-resolution.sh](lib/service-conflict-resolution.sh) - Conflict resolution library

---

## Diagnostic Commands

### Full Service Status Check
```bash
# Check both levels
echo "=== System Level ==="
sudo systemctl status qdrant.service ollama.service 2>&1 | head -20

echo "=== User Level ==="
systemctl --user status podman-local-ai-qdrant.service podman-local-ai-ollama.service

echo "=== Port Usage ==="
ss -tlnp | grep -E ":(6333|6334|11434)"

echo "=== Containers ==="
podman ps -a
```

### Run Conflict Detector
```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
./test-conflict-resolution-simple.sh
```

---

## Summary

**Issue**: Port 6333/6334 already in use - qdrant service cannot start
**Cause**: System-level service competing with user-level service
**Solution**: Stop/mask system service OR disable in configuration.nix
**Prevention**: Use deployment script's auto-resolution feature

**Status**: ⚠️ Fixable - Solution implemented in deployment script
**Action**: Run `./nixos-quick-deploy.sh` to auto-resolve

---

**Resolution Status**: Known issue with automated solution available
**Confidence**: High - service conflict resolution system is already in place
**Next Step**: Enable conflict auto-resolution in deployment
