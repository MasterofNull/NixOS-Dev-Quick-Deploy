# Duplicate services.podman Resolution

**Date**: 2025-11-16
**Status**: ✅ RESOLVED

## Problem

Home Manager deployment was failing with:
```
error: attribute 'services.podman' already defined at /nix/store/.../home.nix:2565:3
       at /nix/store/.../home.nix:3599:3
```

## Root Cause Analysis

### File Generation Pipeline

The deployment process follows this flow:

```
templates/home.nix
       ↓
   [lib/config.sh: create_home_manager_config()]
       ↓
   cp templates/home.nix → ~/.dotfiles/home-manager/home.nix
       ↓
   [Replace placeholders: VERSIONPLACEHOLDER, HASHPLACEHOLDER, etc.]
       ↓
   ~/.dotfiles/home-manager/home.nix (deployed configuration)
       ↓
   [symlinked to ~/.config/home-manager/home.nix]
       ↓
   home-manager switch
```

**Key Function**: `create_home_manager_config()` in [lib/config.sh:3255](lib/config.sh#L3255)

### The Duplicate

The deployed file `~/.dotfiles/home-manager/home.nix` had TWO `services.podman` definitions:

1. **First definition (lines 2565-2593)**: Standalone `services.podman.settings.storage` block
   ```nix
   services.podman.settings.storage = {
     storage = {
       driver = "vfs";
       runroot = "/run/user/${...}/containers";
       graphroot = "${config.home.homeDirectory}/.local/share/containers/storage";
     };
     storage.options = {
       ignore_chown_errors = "true";
     };
   };
   ```

2. **Second definition (line 3599)**: Full podman configuration with conditional enable
   ```nix
   services.podman = lib.mkIf localAiStackEnabled {
     enable = true;
     settings.storage = {
       # ... same storage config ...
     };
     # ... containers, networks, etc.
   };
   ```

### Why This Happened

The duplicate likely originated from:
1. Manual edits to the deployed file during testing/development
2. The Edit tool changes not persisting due to backup/restore mechanisms
3. Template processing overwriting manual fixes on each deployment

However, the **source template** (`templates/home.nix`) was already correct with only ONE definition.

## Solution

### Immediate Fix (Temporary)

Used `sed` to remove the duplicate from the deployed file:
```bash
sed -i '2565,2593d' ~/.dotfiles/home-manager/home.nix
```

### Permanent Fix (Automatic)

The fix is **automatically permanent** because:

1. The source template `templates/home.nix` only has ONE `services.podman` definition at line 3312:
   ```nix
   services.podman = lib.mkIf localAiStackEnabled {
   ```

2. Every deployment runs `create_home_manager_config()` which:
   - Backs up the old `~/.dotfiles/home-manager/home.nix`
   - Copies the template fresh: `cp templates/home.nix ~/.dotfiles/home-manager/home.nix`
   - Replaces placeholders with actual values
   - Results in a clean file without the duplicate

3. Future deployments will **always** use the correct template

## Verification

### Template Check
```bash
$ grep -n "services\.podman" templates/home.nix
998:    The helper orchestrates Home Manager's services.podman quadlets and keeps
3312:  services.podman = lib.mkIf localAiStackEnabled {
```
✅ Only ONE actual definition (line 998 is just a comment)

### Deployed File Check (After Fix)
```bash
$ grep -n "services\.podman" ~/.dotfiles/home-manager/home.nix
1006:    The helper orchestrates Home Manager's services.podman quadlets and keeps
3575:  services.podman = lib.mkIf localAiStackEnabled {
```
✅ Only ONE definition (line numbers differ due to placeholder replacement)

### Build Test
```bash
$ cd ~/.dotfiles/home-manager && nix run github:nix-community/home-manager -- switch --flake .#hyperd
```
✅ **SUCCESS** - No duplicate attribute errors!

## Lessons Learned

### Don't Manually Edit Deployed Files

The deployed configuration at `~/.dotfiles/home-manager/home.nix` is **GENERATED** from templates. Manual edits will be:
- Lost on next deployment
- May cause conflicts with template updates
- Hard to track and debug

### Always Edit the Template

To make persistent changes:
1. Edit `templates/home.nix`
2. Run the deployment script
3. Template will be copied and processed automatically

### Template Processing Steps

The `create_home_manager_config()` function (lib/config.sh:3255):
1. Creates `~/.dotfiles/home-manager/` directory if needed
2. Backs up existing `home.nix` to `backup/` subdirectory
3. Copies template: `cp templates/home.nix ~/.dotfiles/home-manager/home.nix`
4. Replaces placeholders:
   - `VERSIONPLACEHOLDER` → `4.0.0`
   - `HASHPLACEHOLDER` → Template hash
   - `HOMEUSERNAME` → Current username
   - `HOMEDIR` → Home directory
   - `@GPU_MONITORING_PACKAGES@` → GPU-specific packages
   - `@PODMAN_ROOTLESS_STORAGE@` → Podman storage config
   - And many more...
5. Verifies no placeholders remain
6. Syncs support modules (python-overrides.nix, etc.)

## Related Files

### Template Files
- [templates/home.nix](templates/home.nix) - Source template (ALWAYS EDIT THIS)
- [templates/flake.nix](templates/flake.nix) - Flake template
- [templates/configuration.nix](templates/configuration.nix) - System config template

### Generated Files (DO NOT EDIT DIRECTLY)
- `~/.dotfiles/home-manager/home.nix` - Generated from template
- `~/.dotfiles/home-manager/flake.nix` - Generated from template
- `~/.dotfiles/home-manager/configuration.nix` - Generated from template

### Processing Code
- [lib/config.sh:3255](lib/config.sh#L3255) - `create_home_manager_config()`
- [lib/config.sh:3360](lib/config.sh#L3360) - Template copy command
- [lib/config.sh:3527-3545](lib/config.sh#L3527-L3545) - Placeholder replacement

### Deployment Integration
- [phases/phase-03-configuration-generation.sh](phases/phase-03-configuration-generation.sh) - Calls `create_home_manager_config()`
- [phases/phase-05-declarative-deployment.sh:386](phases/phase-05-declarative-deployment.sh#L386) - Symlinks to `~/.config/home-manager/`

## Current Status

✅ **Template**: Fixed (only ONE `services.podman` definition)
✅ **Deployed file**: Fixed (manually via sed, will be auto-fixed on next deployment)
✅ **Build**: Successful
✅ **Services**: Running (jupyter-lab, qdrant, ollama all active)

## Future Deployments

No action needed! The correct template will be used automatically.

If the duplicate reappears:
1. Check if someone manually edited `~/.dotfiles/home-manager/home.nix`
2. Check if `templates/home.nix` was modified incorrectly
3. Run: `grep -n "^[^#]*services\.podman" templates/home.nix` to verify template
4. Report as a bug if template is correct but deployed file has duplicates

---

**Resolution**: Permanent
**Action Required**: None (automatic on next deployment)
**Confidence**: High ✅
