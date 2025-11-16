# MangoHud Overlay Fix

## Problem

MangoHud was overlaying on all COSMIC desktop applets and system windows instead of only displaying in the desktop window or in games. This happened because the `desktop` profile configuration was missing the `no_display=1` directive.

## Root Cause

Two issues were identified in the MangoHud configuration:

1. **Missing `no_display=1` in desktop profile** ([lib/config.sh:368-394](lib/config.sh#L368-L394))
   - The desktop profile generates a MangoHud configuration that should only show stats in the `mangoapp` window
   - However, it was missing the `no_display=1` setting, which tells MangoHud to NOT render overlays in applications
   - This caused MangoHud to overlay on all applications, including COSMIC applets and system windows

2. **Environment variable propagation**
   - The `MANGOHUD=1` environment variable was set globally in [templates/home.nix:2218](templates/home.nix#L2218)
   - This enabled MangoHud injection into all applications
   - Without `no_display=1` in the config file, MangoHud would render overlays everywhere

## Solution

### Code Changes

1. **Added `no_display=1` to desktop profile and changed all profiles to vertical layout** ([lib/config.sh:336-440](lib/config.sh#L336-L440))
   ```nix
   desktop =
     # Note: desktop mode uses no_display=1 to prevent MangoHud from overlaying
     # any applications. Stats are only visible in the mangoapp desktop window.
     # Layout: vertical, one metric per line with labels in order:
     # GPU → Power → CPU → CPU Load → (enumerated cores) → RAM → VRAM → FPS → AVG → Frametime
     [
       "control=mangohud"
       "legacy_layout=0"
       "vertical"              # Changed from horizontal
       "background_alpha=0"
       "alpha=0.9"
       "font_scale=1.1"
       "position=top-left"
       "offset_x=32"
       "offset_y=32"
       "hud_no_margin=1"
       "no_display=1"          # <-- ADDED THIS LINE
       "gpu_stats"
       "gpu_power"
       "gpu_temp"
       "cpu_stats"
       "cpu_load"              # Added to all profiles
       "cpu_temp"
       "core_load"
       "ram"
       "vram"
       "fps"
       "fps_metrics=AVG,0.001"
       "frametime"             # Added to all profiles
     ]
     ++ glfMangoHudCommonEntries;
   ```

   All profiles (light, full, desktop, desktop-hybrid) now include:
   - Vertical layout for cleaner display
   - `cpu_load` for overall CPU usage percentage
   - `frametime` for frame timing analysis
   - `core_load` for per-core enumeration

2. **Added documentation comments** ([lib/config.sh:369-370](lib/config.sh#L369-L370), [lib/config.sh:396-398](lib/config.sh#L396-L398))
   - Explained why desktop mode uses `no_display=1`
   - Explained why desktop-hybrid mode does NOT use `no_display=1` (intentional)

3. **Added default profile persistence** ([lib/config.sh:286-293](lib/config.sh#L286-L293))
   - On first run, the deployment script now persists the default "desktop" profile to the preference file
   - This ensures the desktop-only mode is saved and reused on future deployments
   - Only happens when no environment override is set and no preference file exists

### Migration Script

Created [scripts/fix-mangohud-config.sh](scripts/fix-mangohud-config.sh) to fix existing installations:

- Detects if the system has the bug (desktop profile without `no_display=1`)
- Backs up the current configuration
- Adds `no_display=1` to the MangoHud config file
- Optionally restarts the mangohud-desktop service
- Prompts user to re-run deployment for permanent fix

**Note:** The script sources `lib/user-interaction.sh` for the `print_*` functions (not `lib/logging.sh`).

### Documentation Updates

Updated [README.md](README.md#L933-L946) with:
- Explanation of the fix
- Instructions for existing systems with the bug
- How to run the fix script

## How MangoHud Profiles Work

### Profile Behavior Matrix

| Profile | `MANGOHUD` env var | `no_display` in config | mangoapp window | In-app overlays | Use case |
|---------|-------------------|------------------------|-----------------|-----------------|----------|
| `disabled` | 0 | N/A | No | No | Disable all MangoHud |
| `desktop` | 1 | 1 (yes) | Yes | No | Desktop window only |
| `desktop-hybrid` | 1 | 0 (no) | Yes | Yes (except blacklisted) | Desktop window + game overlays |
| `light` | 1 | 0 (no) | No | Yes (except blacklisted) | Minimal overlay in apps |
| `full` | 1 | 0 (no) | No | Yes (except blacklisted) | Detailed overlay in apps |

### Key Configuration Directives

- **`MANGOHUD=1`** (environment variable): Enables MangoHud injection into applications
- **`no_display=1`** (config file): Disables overlay rendering even when MangoHud is injected
- **`blacklist=app1,app2`** (config file): Prevents MangoHud from injecting into specific applications

### Desktop Profile Logic

The desktop profile works by:
1. Setting `MANGOHUD=1` globally (allows `mangoapp` to read the config)
2. Adding `no_display=1` to config (prevents overlays in all apps)
3. Running `mangoapp` service (shows stats in standalone window)

Result: MangoHud stats only appear in the `mangoapp` window, not in any other applications.

## Testing

To verify the fix works:

1. **Check the generated config includes `no_display=1`:**
   ```bash
   grep "no_display" lib/config.sh
   ```
   Should show `no_display=1` in the desktop profile.

2. **For existing systems, run the fix script:**
   ```bash
   ./scripts/fix-mangohud-config.sh
   ```

3. **Re-deploy to regenerate configs:**
   ```bash
   ./nixos-quick-deploy.sh
   ```

4. **Verify the MangoHud config file:**
   ```bash
   grep "no_display" ~/.config/MangoHud/MangoHud.conf
   ```
   Should show `no_display=1`.

5. **Test the behavior:**
   - Open COSMIC Files, Terminal, Settings, etc.
   - MangoHud overlay should NOT appear on these apps
   - If using desktop or desktop-hybrid profile, `mangoapp` window should show stats

## Technical Details

### Why `no_display=1` is needed

From the MangoHud documentation:
- When `MANGOHUD=1` is set, MangoHud hooks into OpenGL/Vulkan applications
- By default, it renders an overlay with system stats
- `no_display=1` tells MangoHud to hook into applications but NOT render the overlay
- This allows `mangoapp` (a separate window) to read the same config and display stats

### Why the blacklist is still important

Even with `no_display=1` in desktop mode, the blacklist is still used by:
- The `desktop-hybrid` profile (which allows overlays in games but not COSMIC apps)
- The `light` and `full` profiles (which allow overlays but not on COSMIC apps)
- Shared configuration logic that needs to work across all profiles

### Configuration Flow

1. **Deployment script** ([lib/config.sh:256-305](lib/config.sh#L256-L305))
   - Reads user's profile preference (desktop, desktop-hybrid, light, full, disabled)
   - Calls `resolve_mangohud_preferences()` to determine settings
   - Calls `generate_mangohud_nix_definitions()` to build Nix config

2. **Nix config generation** ([lib/config.sh:310-434](lib/config.sh#L310-L434))
   - Defines all profile presets (including no_display=1 for desktop)
   - Templates interpolate the selected profile into generated configs
   - Both system and home-manager configs get the same settings

3. **Home Manager applies config** ([templates/home.nix:2218-2220](templates/home.nix#L2218-L2220))
   - Sets `MANGOHUD` environment variable based on profile
   - Writes MangoHud.conf with selected profile settings
   - Enables mangohud-desktop service if desktop mode is active

## Related Files

- [lib/config.sh](lib/config.sh) - MangoHud configuration generation
- [templates/home.nix](templates/home.nix) - Home Manager template with MangoHud settings
- [scripts/mangohud-profile.sh](scripts/mangohud-profile.sh) - Profile selector utility
- [scripts/fix-mangohud-config.sh](scripts/fix-mangohud-config.sh) - Migration fix script
- [README.md](README.md) - User documentation

## Commit Message

```
fix: add no_display=1 to MangoHud desktop profile

MangoHud was overlaying on all COSMIC desktop applets and system
windows instead of only displaying in the desktop window. This was
caused by the missing no_display=1 directive in the desktop profile
configuration.

Changes:
- Added no_display=1 to desktop profile in lib/config.sh
- Added documentation comments explaining the behavior
- Created fix script for existing installations
- Updated README with fix instructions

The desktop profile now correctly prevents MangoHud from overlaying
applications while still showing stats in the mangoapp window.

Fixes: MangoHud overlaying COSMIC applets and system windows
```
