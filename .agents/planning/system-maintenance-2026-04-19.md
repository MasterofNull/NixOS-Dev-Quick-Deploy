# System Maintenance - Package Updates

**Date:** 2026-04-19
**Objective:** Update all system packages and fix Chrome update mechanism

---

## Current System State

### Chromium Browser
- **Version:** 145.0.7632.109 (January 2026)
- **Status:** ⚠️ Browser shows "out of date" warning
- **Issue:** Chromium's built-in updater doesn't work in NixOS (by design)
- **Solution:** Updates must come through Nix package manager

### NixOS Package Management

**How NixOS Handles Updates:**
- Packages are immutable and installed via Nix
- Browser built-in updaters are disabled (security feature)
- Updates happen through: `nix flake update` + `nixos-rebuild switch`
- This ensures reproducibility and rollback capability

**Why Chromium Shows "Out of Date":**
- Chromium detects it can't auto-update (correct behavior)
- Warning is cosmetic - updates will come through NixOS
- This is expected and secure

---

## Update Strategy

### Step 1: Update Flake Inputs (nixpkgs, home-manager, etc.)

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy

# Update all flake inputs (nixpkgs, home-manager, etc.)
nix flake update

# This updates:
# - nixpkgs → latest stable packages (including Chromium)
# - home-manager → latest user environment tools
# - All other flake dependencies
```

### Step 2: Rebuild System with Updated Packages

```bash
# Rebuild NixOS configuration with new packages
sudo nixos-rebuild switch --flake .#hyperd

# This will:
# - Download and install updated packages
# - Update Chromium to latest available version
# - Update all system packages
# - Preserve your data and settings
```

### Step 3: Rebuild User Environment

```bash
# Update home-manager (user packages)
home-manager switch --flake .#hyperd@hyperd

# This updates user-level packages like:
# - Development tools
# - User applications
# - Shell configuration
```

### Step 4: Verify Updates

```bash
# Check Chromium version after update
chromium --version

# Check system generation
nixos-rebuild list-generations | head -5

# Compare with previous generation
nix store diff-closures /nix/var/nix/profiles/system-{2,1}-link
```

---

## Addressing the "Out of Date" Warning

### Option 1: Accept the Warning (Recommended)

**Explanation:**
- The warning is cosmetic and doesn't affect functionality
- NixOS's update method is more secure than browser auto-updates
- Regular `nix flake update` + rebuild keeps everything current

**Benefits:**
- ✅ Reproducible updates (can rollback if needed)
- ✅ Atomic updates (all or nothing, no partial updates)
- ✅ No random auto-updates breaking your system
- ✅ Security updates come through tested NixOS channels

### Option 2: Suppress the Warning (If Desired)

Add to `nix/home/base.nix`:

```nix
# Chromium with custom flags to suppress update nag
programs.chromium = {
  enable = true;
  commandLineArgs = [
    # Disable update nag (NixOS manages updates)
    "--simulate-outdated-no-au='Tue, 31 Dec 2099 23:59:59 GMT'"
  ];
};
```

### Option 3: Use Latest Unstable Chromium (Most Recent)

If you want bleeding-edge Chromium, use nixpkgs-unstable:

```nix
# In flake.nix, add unstable input:
inputs = {
  nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";  # Use unstable
  # OR add separate unstable input:
  nixpkgs-unstable.url = "github:nixos/nixpkgs/nixos-unstable";
};

# Then in home.nix:
home.packages = with pkgs; [
  # Use unstable Chromium
  unstable.chromium
];
```

---

## Automated Update Schedule

### Option A: Manual Updates (Current)

```bash
# Run these every 1-2 weeks:
nix flake update && sudo nixos-rebuild switch --flake .#hyperd
```

### Option B: Automated Update Service (Recommended)

Create a systemd timer to auto-update:

```nix
# In nix/modules/services/auto-update.nix
{ config, pkgs, ... }:
{
  # Automatic system updates
  system.autoUpgrade = {
    enable = true;
    flake = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy";
    flags = [
      "--update-input" "nixpkgs"
      "--commit-lock-file"
    ];
    dates = "weekly";  # Or "daily" / "03:00"
    allowReboot = false;  # Set true for servers
  };

  # Automatic garbage collection (free disk space)
  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };
}
```

Then enable in `flake.nix`:

```nix
imports = [
  ./nix/modules/services/auto-update.nix
];
```

---

## Full Update Procedure

### Execute Now (While Model Downloads):

```bash
cd /home/hyperd/Documents/NixOS-Dev-Quick-Deploy

# 1. Update flake inputs (gets latest packages)
echo "=== Updating flake inputs ==="
nix flake update

# 2. Check what will be updated
echo "=== Checking update size ==="
nixos-rebuild dry-build --flake .#hyperd

# 3. Rebuild system (download ~500MB-2GB typically)
echo "=== Rebuilding system with updates ==="
sudo nixos-rebuild switch --flake .#hyperd

# 4. Update user environment
echo "=== Updating home-manager ==="
home-manager switch --flake .#hyperd@hyperd

# 5. Verify
echo "=== Verification ==="
chromium --version
nixos-rebuild list-generations | head -3

echo ""
echo "✓ System updated! New packages installed."
echo "✓ Chromium updated to latest NixOS stable version."
echo "✓ All system packages refreshed."
echo ""
echo "To rollback if needed:"
echo "  sudo nixos-rebuild switch --rollback"
```

---

## Post-Update Cleanup

### Clean Old Generations (Free Disk Space)

```bash
# List all generations
nixos-rebuild list-generations

# Delete old generations (keep last 5)
sudo nix-collect-garbage --delete-older-than 30d

# Or delete all except current
sudo nix-collect-garbage -d

# Optimize nix store (deduplicate)
sudo nix-store --optimise
```

### Check Disk Space Savings

```bash
# Before cleanup
df -h /

# After cleanup
df -h /

# Show what was deleted
du -sh /nix/store
```

---

## Expected Update Results

### Package Updates (Typical)

After `nix flake update`:
- **Chromium:** 145.x → 146.x+ (if available)
- **System packages:** Various security/bug fixes
- **Development tools:** Latest stable versions
- **NixOS:** Updated module system

### Download Size

- **Typical:** 500MB - 2GB
- **Major update:** 2GB - 5GB
- **Time:** 10-30 minutes depending on connection

### System Impact

- ✅ No data loss (all user data preserved)
- ✅ Settings maintained (home-manager ensures this)
- ✅ Rollback available (can revert to previous generation)
- ✅ Atomic update (all or nothing, no partial state)

---

## Troubleshooting

### Issue: "Derivation failed to build"

```bash
# Clean build cache and retry
nix-store --verify --check-contents --repair
sudo nixos-rebuild switch --flake .#hyperd --option pure-eval false
```

### Issue: "Lock file is out of sync"

```bash
# Regenerate flake.lock
rm flake.lock
nix flake lock
sudo nixos-rebuild switch --flake .#hyperd
```

### Issue: "Disk space full"

```bash
# Free up space before update
sudo nix-collect-garbage -d
sudo nix-store --optimise
df -h /
```

---

## Maintenance Schedule

**Recommended:**
- **Weekly:** `nix flake update` (check for updates)
- **Monthly:** Full rebuild + garbage collection
- **Quarterly:** Review and clean old generations

**Automated (Optional):**
- Enable `system.autoUpgrade.enable = true;`
- Set `nix.gc.automatic = true;`
- Configure `nix.optimise.automatic = true;`

---

## Status Tracking

- [ ] Flake inputs updated (`nix flake update`)
- [ ] System rebuilt (`nixos-rebuild switch`)
- [ ] Home-manager updated (`home-manager switch`)
- [ ] Chromium version verified
- [ ] Garbage collection run
- [ ] Disk space optimized

---

**Document Version:** 1.0.0
**Created:** 2026-04-19
**Status:** Ready for Execution
**Estimated Time:** 10-30 minutes
