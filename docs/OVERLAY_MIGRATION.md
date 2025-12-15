# Overlay Storage Migration Guide

## Overview

This guide documents the implementation of rootless podman overlay storage to prevent VFS bloat while maintaining system stability.

## Problem Statement

**VFS Storage Bloat**: The VFS storage driver creates full copies of container layers instead of using copy-on-write. This led to:
- 424GB of duplicate layer storage (17 x 25GB vLLM layers)
- Disk usage climbing to 86.7% (787GB / 907GB)
- "no space left on device" errors during container operations
- Repeated failures downloading large AI model containers

## Previous Overlay Removal

Overlay storage was previously removed from NixOS-Dev-Quick-Deploy due to critical boot failures:
- systemd mounted `/var/lib/containers/storage/overlay` entries during boot
- Stale overlay mounts caused "Device or resource busy" errors
- Systems failed to boot when overlay mounts were corrupt
- Manual intervention required to unmount and cleanup

See: [docs/ROOTLESS_PODMAN.md](ROOTLESS_PODMAN.md) for historical context.

## Solution Architecture

### Two-Tier Storage Strategy

1. **System-Level Podman** (root): Stays on VFS/btrfs/zfs
   - Rarely used (most containers run rootless)
   - Prevents systemd overlay mount issues during boot
   - No risk of boot failures from corrupt overlay mounts
   - Configured via: `virtualisation.containers.storage.settings` in configuration.nix

2. **User-Level Podman** (rootless): Uses overlay with fuse-overlayfs
   - Where AI-Optimizer and all user containers run
   - Prevents VFS bloat with copy-on-write efficiency
   - Storage in `~/.local/share/containers/storage` (no boot impact)
   - No systemd mounts (user-space only)
   - Configured via: Home Manager `xdg.configFile."containers/storage.conf"`

### Why This Is Safe

1. **No System Mounts**: User-level overlay storage lives entirely in `~/.local/share`
   - systemd doesn't manage these mounts
   - Boot process is unaffected
   - User can login and fix issues even if containers are broken

2. **fuse-overlayfs**: User-space overlay implementation
   - No kernel overlay mounts
   - Runs as regular user (no root privileges)
   - Automatically cleaned up when user logs out
   - More stable than kernel overlayfs for rootless containers

3. **Isolation**: System and user storage are completely separate
   - System issues don't affect user containers
   - User container issues don't affect boot
   - Can reset user storage without touching system

## Implementation Details

### Files Modified

#### 1. `/templates/configuration.nix`
**Line 695**: Added `fuse-overlayfs` package
```nix
fuse-overlayfs           # Required for rootless overlay storage driver
```

#### 2. `/templates/home.nix`
**Lines 1759-1787**: Added rootless podman storage configuration
```nix
xdg.configFile."containers/storage.conf".text = ''
  [storage]
  driver = "overlay"
  graphroot = "${config.home.homeDirectory}/.local/share/containers/storage"
  rootless_storage_path = "${config.home.homeDirectory}/.local/share/containers/storage"
  runroot = "/run/user/''${UID}/containers"

  [storage.options]
  # Use fuse-overlayfs for rootless overlay (safer than kernel overlay)
  mount_program = "${pkgs.fuse-overlayfs}/bin/fuse-overlayfs"
'';
```

#### 3. `/lib/config.sh`
**Lines 2832-2838**: Updated system storage comment to clarify two-tier approach
```bash
# NOTE: This configures system-level podman storage (root).
# User-level (rootless) podman uses overlay with fuse-overlayfs configured
# via Home Manager in home.nix to prevent VFS bloat while avoiding boot issues.
# System-level stays on VFS/btrfs/zfs to prevent systemd overlay mount failures.
```

#### 4. Created `/home/hyperd/Documents/AI-Optimizer/scripts/migrate_to_overlay.sh`
Safe migration script for AI-Optimizer users that:
- Verifies fuse-overlayfs is installed
- Stops all containers
- Backs up current VFS storage
- Resets podman storage
- Verifies overlay is active
- Tests with hello-world container

## Migration Steps

### Step 1: Rebuild NixOS Configuration

```bash
cd ~/Documents/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh --resume
```

This will:
- Install fuse-overlayfs system package
- Configure user-level overlay storage via Home Manager
- Keep system-level on VFS (safe)

### Step 2: Migrate AI-Optimizer

After successful NixOS rebuild:

```bash
cd ~/Documents/AI-Optimizer
./scripts/migrate_to_overlay.sh
```

The migration script will:
1. Verify fuse-overlayfs is installed
2. Show current storage driver
3. Ask for confirmation
4. Stop all containers
5. Create backup in `~/.local/share/containers/storage-backup-YYYYMMDD-HHMMSS`
6. Reset podman storage
7. Verify overlay is active
8. Test with hello-world container

### Step 3: Redeploy AI-Optimizer Stack

```bash
cd ~/Documents/AI-Optimizer
./RUN_DEPLOYMENT.sh
```

Images will be pulled fresh, but with overlay:
- Each layer downloaded once
- Shared across all containers
- Copy-on-write for container filesystems
- No VFS bloat

## Verification

### Check Storage Driver

```bash
podman info --format json | jq -r '.store.graphDriverName'
# Should output: overlay
```

### Check Mount Program

```bash
podman info --format json | jq -r '.store.graphOptions.mount_program'
# Should output: /nix/store/.../bin/fuse-overlayfs
```

### Monitor Storage Usage

```bash
cd ~/Documents/AI-Optimizer
./scripts/check_vfs_bloat.sh
```

With overlay, you should see:
- Stable storage size (no bloat from duplicate layers)
- Efficient layer sharing
- Lower overall disk usage

### Compare Before/After

**Before (VFS)**:
- vLLM image (25GB) x 17 failed downloads = 424GB bloat
- Total storage: 471GB
- Disk usage: 86.7%

**After (Overlay)**:
- vLLM image (25GB) x 1 = 25GB total
- Shared across containers
- Disk usage: ~40-50% (normal operating level)

## Troubleshooting

### Overlay Not Active After Migration

1. Check Home Manager configuration:
   ```bash
   cat ~/.config/containers/storage.conf
   ```
   Should show `driver = "overlay"` and `mount_program = "...fuse-overlayfs"`

2. Verify fuse-overlayfs is installed:
   ```bash
   which fuse-overlayfs
   # Should output: /run/current-system/sw/bin/fuse-overlayfs
   ```

3. Check for errors:
   ```bash
   podman info
   ```

### Storage Config Not Updating

Home Manager configurations are symlinked from nix store. If changes aren't applying:

```bash
# Rebuild home-manager
home-manager switch

# Or rebuild NixOS (includes home-manager)
sudo nixos-rebuild switch
```

### Container Pull Failures

If containers fail to pull with overlay:

```bash
# Check overlay is working
podman run --rm alpine echo "test"

# Check fuse-overlayfs logs
journalctl --user -u podman -n 50
```

### Reverting to VFS (Emergency)

If you need to revert quickly:

```bash
# Edit user storage config
mkdir -p ~/.config/containers
cat > ~/.config/containers/storage.conf << 'EOF'
[storage]
driver = "vfs"
graphroot = "/home/hyperd/.local/share/containers/storage"
rootless_storage_path = "/home/hyperd/.local/share/containers/storage"
runroot = "/run/user/1000/containers"
EOF

# Reset storage
podman system reset --force
```

Note: This overrides Home Manager config temporarily. Rebuild home-manager to restore overlay.

## Technical References

- [Rootless podman setup with Home Manager - NixOS Discourse](https://discourse.nixos.org/t/rootless-podman-setup-with-home-manager/57905)
- [Podman rootless overlay support - Red Hat Blog](https://www.redhat.com/en/blog/podman-rootless-overlay)
- [Podman - NixOS Wiki](https://nixos.wiki/wiki/Podman)
- [Why is fuse-overlayfs mounting layers as root? - NixOS Discourse](https://discourse.nixos.org/t/why-is-fuse-overlayfs-mounting-layers-as-root/42236)

## Benefits Summary

1. **Prevents VFS Bloat**: Copy-on-write efficiency, no duplicate 25GB layers
2. **Maintains Boot Safety**: No systemd overlay mounts, no boot failures
3. **Better Performance**: Faster image operations, less disk I/O
4. **Resource Efficiency**: One copy of shared layers across all containers
5. **User Isolation**: User storage issues don't affect system boot

## Notes for Future Maintenance

- **System storage driver**: Remains VFS/btrfs/zfs (controlled by [lib/config.sh](../lib/config.sh#L2812))
- **User storage driver**: Overlay via Home Manager (in [templates/home.nix](../templates/home.nix#L1777))
- **Migration required**: Yes, after NixOS rebuild (use `scripts/migrate_to_overlay.sh`)
- **Automatic**: Future installations will use overlay by default for rootless containers
