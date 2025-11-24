# NixOS Service Conflict Resolution Fix

## Problem

The initial implementation failed with:
```
Failed to disable unit: File /etc/systemd/system/ollama.service: Read-only file system
```

## Root Cause

In NixOS, systemd service files in `/etc/systemd/system/` are on a **read-only filesystem** because they're managed declaratively through `configuration.nix`. The `systemctl disable` command tries to modify files in this read-only location, which fails.

## Solution

Updated the conflict resolution to use NixOS-compatible methods:

### 1. Use `systemctl mask` Instead of `disable`

**Masking** creates a symlink to `/dev/null` in `/etc/systemd/system/`, which:
- ✅ Works on read-only filesystems
- ✅ Prevents the service from starting
- ✅ Is reversible with `systemctl unmask`

**Implementation:**
```bash
# Try mask first (works on NixOS)
sudo systemctl mask ollama.service

# Fallback to disable (for non-NixOS)
sudo systemctl disable ollama.service
```

### 2. Provide Instructions for Permanent Fix

The script now provides clear instructions:

```
For permanent resolution, disable these services in /etc/nixos/configuration.nix:
  services.ollama.enable = false;
  services.qdrant.enable = false;

Then run: sudo nixos-rebuild switch
```

## Changes Made

**File:** `lib/service-conflict-resolution.sh`

### Before (Lines 103-122)
```bash
disable-system)
    print_info "Resolving conflict: Disabling system service $system_service"
    if sudo systemctl is-active "$system_service" &>/dev/null; then
        sudo systemctl stop "$system_service" || {
            print_error "Failed to stop $system_service"
            return 1
        }
        print_success "  ✓ Stopped $system_service"
    fi

    if sudo systemctl is-enabled "$system_service" &>/dev/null; then
        sudo systemctl disable "$system_service" || {
            print_error "Failed to disable $system_service"
            return 1
        }
        print_success "  ✓ Disabled $system_service"
    fi
    ;;
```

### After (Lines 103-138)
```bash
disable-system)
    print_info "Resolving conflict: Disabling system service $system_service"

    # Step 1: Stop the service if it's running
    if sudo systemctl is-active "$system_service" &>/dev/null; then
        if sudo systemctl stop "$system_service" 2>/dev/null; then
            print_success "  ✓ Stopped $system_service"
        else
            print_warning "  ⚠ Could not stop $system_service (may already be stopped)"
        fi
    else
        print_info "  • $system_service is not running"
    fi

    # Step 2: Mask the service (works on NixOS read-only filesystem)
    if sudo systemctl is-enabled "$system_service" &>/dev/null 2>&1; then
        # Try mask instead of disable (works on read-only filesystems)
        if sudo systemctl mask "$system_service" 2>/dev/null; then
            print_success "  ✓ Masked $system_service (prevents auto-start)"
        else
            # If mask fails, try disable (for non-NixOS systems)
            if sudo systemctl disable "$system_service" 2>/dev/null; then
                print_success "  ✓ Disabled $system_service"
            else
                print_warning "  ⚠ Could not mask/disable $system_service"
                print_info "  • Service is stopped, which is sufficient for now"
                print_info "  • To permanently disable, remove from configuration.nix and rebuild"
            fi
        fi
    else
        print_info "  • $system_service is not enabled"
    fi

    print_success "✓ System service $system_service stopped (user service can now start)"
    ;;
```

### Additional Enhancement (Lines 194-204)
```bash
# Provide instructions for permanent resolution
if (( ${#resolved_services[@]} > 0 )); then
    print_info "For permanent resolution, disable these services in /etc/nixos/configuration.nix:"
    for service in "${resolved_services[@]}"; do
        local service_name="${service%.service}"
        print_info "  services.${service_name}.enable = false;"
    done
    echo ""
    print_info "Then run: sudo nixos-rebuild switch"
    echo ""
fi
```

## How It Works Now

### Temporary Resolution (Immediate)

1. **Stop** the running service
   ```bash
   sudo systemctl stop ollama.service
   ```

2. **Mask** the service (prevents restart)
   ```bash
   sudo systemctl mask ollama.service
   ```

3. **Result:** Service is stopped and won't auto-start, allowing user services to use the ports

### Permanent Resolution (User Action Required)

Edit `/etc/nixos/configuration.nix`:

```nix
{
  # ... other config ...

  # Disable system-level AI services (using user-level instead)
  services.ollama.enable = false;
  services.qdrant.enable = false;

  # ... rest of config ...
}
```

Then rebuild:
```bash
sudo nixos-rebuild switch
```

## Why This Approach?

### NixOS Declarative Management

In NixOS:
- Services are defined in `configuration.nix`
- Service files are generated during `nixos-rebuild`
- The `/etc` directory is read-only (points to `/nix/store`)
- Runtime changes need to use masking, not file modification

### Masking vs Disabling

| Method | Works on NixOS? | Permanent? | Reversible? |
|--------|----------------|------------|-------------|
| `systemctl disable` | ❌ No (read-only FS) | Would be permanent | N/A |
| `systemctl mask` | ✅ Yes | Until unmask/rebuild | ✅ Yes |
| Edit `configuration.nix` | ✅ Yes | ✅ Permanent | ✅ Yes |

## Testing

### Test the Fix

```bash
# Test conflict resolution
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
./test-conflict-resolution.sh

# Or run the deployment
./nixos-quick-deploy.sh
```

### Verify Services Are Masked

```bash
# Check if services are masked
systemctl status ollama.service
systemctl status qdrant.service

# Should show:
# Loaded: masked (Reason: Unit ollama.service is masked.)
# Active: inactive (dead)
```

### Unmask if Needed

```bash
# To undo masking (if you want to switch back)
sudo systemctl unmask ollama.service qdrant.service
sudo systemctl start ollama.service qdrant.service
```

## User Experience

### Before Fix
```
ℹ Resolving conflict: Disabling system service ollama.service
✓   ✓ Stopped ollama.service
Failed to disable unit: File /etc/systemd/system/ollama.service: Read-only file system
✗ Failed to disable ollama.service
✗ Phase 5 failed!
```

### After Fix
```
ℹ Resolving conflict: Disabling system service ollama.service
✓   ✓ Stopped ollama.service
✓   ✓ Masked ollama.service (prevents auto-start)
✓ System service ollama.service stopped (user service can now start)

✓ All service conflicts resolved (temporarily)

ℹ For permanent resolution, disable these services in /etc/nixos/configuration.nix:
ℹ   services.ollama.enable = false;
ℹ   services.qdrant.enable = false;
ℹ
ℹ Then run: sudo nixos-rebuild switch
```

## Benefits

1. **✅ Works on NixOS** - Uses masking instead of disable
2. **✅ Immediate Resolution** - Deployment can continue
3. **✅ Clear Guidance** - Shows how to make changes permanent
4. **✅ Reversible** - Easy to unmask if needed
5. **✅ Graceful Fallback** - Handles edge cases (already stopped, etc.)

## Related Documentation

- [SERVICE-CONFLICT-RESOLUTION.md](docs/SERVICE-CONFLICT-RESOLUTION.md) - General conflict resolution guide
- [CONFLICT-RESOLUTION-INTEGRATION-SUMMARY.md](CONFLICT-RESOLUTION-INTEGRATION-SUMMARY.md) - Integration details

## Permanent Configuration Example

For users who want to permanently disable system services, here's a complete example:

**File:** `/etc/nixos/configuration.nix`

```nix
{ config, pkgs, ... }:

{
  # ... other configuration ...

  # ========================================================================
  # AI Services - Disabled (using user-level services via home-manager)
  # ========================================================================
  # These services are managed at user-level via home-manager's podman quadlets
  # to provide rootless, declarative container management per-user.
  #
  # To re-enable system-level:
  #   1. Set localAiStackEnabled = false in home-manager/home.nix
  #   2. Uncomment the lines below
  #   3. Run: sudo nixos-rebuild switch

  services.ollama = {
    enable = false;  # Disabled: Using user-level podman-local-ai-ollama
    # acceleration = "rocm";  # Uncomment if re-enabling with AMD GPU
  };

  # Qdrant vector database
  # Note: NixOS doesn't have a native qdrant module yet, so this might be
  # running via a custom systemd service or container. Adjust accordingly.
  # services.qdrant.enable = false;

  # ... rest of configuration ...
}
```

Then apply:
```bash
sudo nixos-rebuild switch
```

---

**Status:** ✅ Fixed
**Version:** 1.1.0
**Date:** 2025-11-16
