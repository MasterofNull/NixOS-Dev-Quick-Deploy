# NixOS Quick Deploy - Fixes and Improvements

## Date: 2025-11-02

## Summary

This document describes the fixes applied to the NixOS Quick Deploy script to address errors, warnings, and improve the user experience.

- Added default disk management utilities (GNOME Disks and `parted`) so newly provisioned environments include user-friendly formatting and partitioning tools.
- Retained the full observability stack (Glances, Grafana, Prometheus, Loki, Promtail, Vector, Cockpit) while keeping AMD-specific monitors (`radeontop`, `amdgpu_top`) conditional on detected hardware.
- Updated the Home Manager Git module configuration to the new `programs.git.settings` structure (with nested `alias`) required by the latest unstable release.
- Replaced the deprecated `du-dust` package name with the upstream-supported `dust` derivation to keep the toolkit compatible with nixos-unstable.

## Critical Fixes

### 1. System Rebuild Prompt Timing (CRITICAL)

**Problem:**
- The system rebuild prompt occurred AFTER backups and deletions of home-manager, flake, and flatpak files
- Users couldn't cancel without losing configuration data
- This violated the principle of asking before destructive operations

**Solution:**
- Split `update_nixos_system_config()` into two functions:
  - `generate_nixos_system_config()` - Generates configuration without prompting
  - `apply_nixos_system_config()` - Prompts user and applies configuration

**New Flow:**
```bash
main() {
    # 1. Generate system configuration (non-destructive)
    generate_nixos_system_config

    # 2. PROMPT for system rebuild (BEFORE backups)
    apply_nixos_system_config

    # 3. Backup and apply home manager (backups happen here)
    create_home_manager_config
    apply_home_manager_config
}
```

**Benefits:**
- Users can now cancel BEFORE any files are backed up or deleted
- Improved user safety and control
- Better adherence to Unix philosophy (ask before destructive operations)

### 2. Flatpak Repository Corruption

**Problem:**
- Script removed entire `~/.local/share/flatpak` directory
- Did not properly re-initialize repository structure
- Caused errors: `opening repo: opendir(objects): No such file or directory`

**Solution:**
Added proper repository initialization after removal:

```bash
# Re-initialize Flatpak repository structure
mkdir -p "$flatpak_dir/repo"
mkdir -p "$flatpak_config"

# Add Flathub remote to prevent repository corruption
run_as_primary_user flatpak remote-add --user --if-not-exists flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true
```

**Location:** `force_clean_environment_setup()` function, lines 4108-4123

**Benefits:**
- Prevents flatpak repository corruption
- Ensures Flathub remote is properly configured
- Eliminates "No such file or directory" errors

### 3. flatpak-managed-install.service Timeout

**Problem:**
- Service was timing out after 4 minutes during large Flatpak installations
- Caused service failures and incomplete installations

**Status:** Already fixed in templates/home.nix

**Configuration:**
```nix
TimeoutStartSec = 600  # 10 minutes
```

**Location:** Line 2562 in `templates/home.nix`

**Benefits:**
- Allows large Flatpak applications (like Firefox, Obsidian) to install completely
- Prevents timeout-related service failures
- More reliable Flatpak installation process

### 4. PAM Authentication Failure (chsh)

**Problem:**
- Script called `chsh` without sudo
- Caused PAM authentication failures
- Users couldn't set ZSH as default shell

**Solution:**
Wrapped chsh with sudo and proper error handling:

```bash
if [ "$SHELL" != "$(which zsh)" ]; then
    print_info "Setting ZSH as default shell (configured in NixOS)"
    # Use sudo to avoid PAM authentication failure
    if sudo chsh -s "$(which zsh)" "$USER" 2>/dev/null; then
        print_success "Default shell set to ZSH (restart terminal to apply)"
    else
        print_warning "Could not set ZSH as default shell automatically"
        print_info "Set it manually later with: sudo chsh -s \$(which zsh) $USER"
    fi
fi
```

**Location:** `apply_system_changes()` function, lines 4155-4163

**Benefits:**
- ZSH properly set as default shell
- No PAM authentication errors
- Graceful fallback with user instructions

## COSMIC Desktop Environment

### Declarative Configuration

The COSMIC desktop is configured declaratively in NixOS using the following components:

#### Core Desktop Configuration

```nix
# Enable COSMIC Desktop (Wayland-native)
services.desktopManager.cosmic = {
  enable = true;
  # Hardware acceleration is auto-configured based on GPU detection
  @COSMIC_GPU_BLOCK@
};

# Enable COSMIC Greeter (login screen)
services.displayManager.cosmic-greeter.enable = true;
```

#### Wayland Environment Variables

```nix
environment.sessionVariables = {
  # Force Wayland for Qt applications
  QT_QPA_PLATFORM = "wayland";

  # Force Wayland for SDL2 applications
  SDL_VIDEODRIVER = "wayland";

  # Firefox Wayland support
  MOZ_ENABLE_WAYLAND = "1";

  # Electron apps (VSCodium, etc.) Wayland support
  NIXOS_OZONE_WL = "1";

  # COSMIC-specific: Enable clipboard functionality
  COSMIC_DATA_CONTROL_ENABLED = "1";
};
```

#### Hardware Acceleration

Hardware acceleration is automatically configured based on GPU detection:

**Intel GPUs:**
```nix
hardware.graphics = {
  enable = true;
  enable32Bit = true;
  extraPackages = with pkgs; [
    intel-media-driver  # VAAPI driver for Broadwell+ (>= 5th gen)
    vaapiIntel          # Older VAAPI driver for Haswell and older
    vaapiVdpau
    libvdpau-va-gl
    intel-compute-runtime  # OpenCL support
  ];
};

# In COSMIC config:
extraSessionCommands = ''
  export LIBVA_DRIVER_NAME=iHD
'';
```

**AMD GPUs:**
```nix
hardware.graphics = {
  enable = true;
  enable32Bit = true;
  extraPackages = with pkgs; [
    mesa              # Open-source AMD drivers
    amdvlk            # AMD Vulkan driver
    rocm-opencl-icd   # AMD OpenCL support
  ];
};

# In COSMIC config:
extraSessionCommands = ''
  export LIBVA_DRIVER_NAME=radeonsi
'';
```

**NVIDIA GPUs:**
```nix
services.xserver.videoDrivers = [ "nvidia" ];
hardware.nvidia = {
  modesetting.enable = true;  # Required for Wayland
  open = false;  # Use proprietary driver
  nvidiaSettings = true;
};
hardware.graphics = {
  enable = true;
  enable32Bit = true;
};
```

#### Audio Configuration (PipeWire)

```nix
# Disable legacy PulseAudio
services.pulseaudio.enable = false;

# Enable real-time audio scheduling
security.rtkit.enable = true;

# Enable PipeWire
services.pipewire = {
  enable = true;
  alsa = {
    enable = true;
    support32Bit = true;
  };
  pulse.enable = true;  # PulseAudio compatibility
  jack.enable = true;   # JACK audio support
  wireplumber.enable = true;  # Modern session manager
};
```

#### System Services

```nix
# D-Bus (Required for desktop communication)
services.dbus.enable = true;

# Power management
services.upower.enable = true;

# Bluetooth
services.blueman.enable = true;

# Thermal management (Intel systems)
services.thermald.enable = true;

# Flatpak (for COSMIC App Store)
services.flatpak.enable = true;

# Printing
services.printing.enable = true;

# Geolocation (for auto day/night theme)
services.geoclue2 = {
  enable = true;
  enableWifi = true;
  geoProviderUrl = "https://api.beacondb.net/v1/geolocate";
  submitData = false;
};
```

#### System Packages

```nix
environment.systemPackages = with pkgs;
  [
    # COSMIC App Store (not auto-included)
    cosmic-store

    # COSMIC Settings (explicitly included)
    # Ensures settings daemon is available
  ]
  ++ lib.optionals (pkgs ? cosmic-settings) [ pkgs.cosmic-settings ]
  ++ lib.optional (lib.hasAttr "default" nixAiToolsPackages)
    nixAiToolsPackages.default
  ++ [
    # Container tools
    podman
    podman (legacy)
    buildah
    skopeo
    crun
    slirp4netns
  ];
```

**Note:** COSMIC desktop applications (cosmic-edit, cosmic-files, cosmic-term, etc.) are automatically included when `services.desktopManager.cosmic.enable = true`. Do NOT add them to systemPackages - it creates duplicates!

#### Fonts

```nix
fonts.packages = with pkgs; [
  nerd-fonts.meslo-lg
  nerd-fonts.fira-code
  nerd-fonts.jetbrains-mono
  nerd-fonts.hack
  font-awesome
  powerline-fonts
];
```

### COSMIC Best Practices

1. **Keep it Declarative:**
   - All COSMIC configuration should be in `configuration.nix`
   - Don't manually install COSMIC apps - they're included automatically
   - Use home-manager for user-specific applications

2. **Hardware Acceleration:**
   - The script auto-detects GPU and configures acceleration
   - Intel: Uses iHD driver (intel-media-driver)
   - AMD: Uses radeonsi (mesa)
   - NVIDIA: Uses proprietary driver

3. **Wayland-Native:**
   - COSMIC is 100% Wayland-native
   - XWayland is optional and disabled by default
   - Only enable XWayland if you need legacy X11 apps

4. **Flatpak Integration:**
   - COSMIC App Store uses Flatpak
   - Flatpak is enabled system-wide
   - User-level Flatpak configuration in home-manager

5. **Audio:**
   - PipeWire is the only audio system enabled
   - PulseAudio compatibility layer is active
   - JACK support for professional audio

## Python Package Configuration

### Verified Packages

All requested Python packages are already configured in `templates/home.nix`:

```nix
pythonAiEnv = pythonAi.withPackages (ps: let
  base = with ps; [
    # Code Quality Tools (lines 707-710)
    black
    ruff        # ✓ Line 708
    mypy        # ✓ Line 709
    pylint

    # Data Processing (line 723)
    polars      # ✓ Line 723 - Fast DataFrame library

    # LLM & AI APIs (lines 725-726)
    openai
    anthropic   # ✓ Line 726 - Anthropic API client
  ];
```

**Status:** All packages are in the `base` list, NOT in conditional `aiExtras` list. This ensures they're always built.

### Why Some Packages Show as Missing

Even though packages are in `home.nix`, they might not appear in PATH due to:

1. **Build failures:** Some packages may fail to build on certain nixpkgs versions
2. **Shell not reloaded:** After home-manager switch, run `exec zsh` to reload
3. **Session variables not sourced:** Run `source ~/.nix-profile/etc/profile.d/hm-session-vars.sh`

### Recommended Post-Install

```bash
# After running nixos-quick-deploy.sh:
exec zsh

# Verify packages:
python3 -c "import anthropic, polars, ruff, mypy; print('All packages available')"
```

## Concurrent Execution Analysis

The user mentioned potential concurrent execution issues. Analysis of the script shows:

### No True Concurrency Issues

The script is **single-threaded** and executes operations sequentially:

1. Generate system config
2. Prompt user
3. Apply system config (if confirmed)
4. Create home-manager config
5. Prompt user
6. Apply home-manager config (if confirmed)

### Perceived Concurrency

The appearance of concurrent execution comes from:

1. **Nix builds:** Multiple packages building simultaneously (this is normal and expected)
2. **Flatpak service:** Runs in background as systemd service while script continues
3. **Home-manager switch:** Builds multiple packages in parallel

This is **intentional behavior** and not a bug. Nix is designed to build packages in parallel for performance.

### Actual Issue: Service Timeout

The real issue wasn't concurrency but **timeout**:
- `flatpak-managed-install.service` timing out after 4 minutes
- Already fixed by increasing `TimeoutStartSec` to 600 seconds (10 minutes)

## Testing Recommendations

### 1. Test System Rebuild Prompt Timing

```bash
cd ~/NixOS-Dev-Quick-Deploy
./nixos-quick-deploy.sh
```

**Expected behavior:**
1. Script generates configuration
2. Shows dry-run results
3. **PROMPTS: "Proceed with 'sudo nixos-rebuild switch'?"**
4. If you answer "n" (no), script should exit WITHOUT backing up or deleting anything
5. If you answer "y" (yes), script continues and THEN backs up files

### 2. Test Flatpak Repository

After reboot:

```bash
# Verify repository is initialized
ls -la ~/.local/share/flatpak/repo

# Verify Flathub remote exists
flatpak remotes --user

# Test installing an app
flatpak install --user flathub org.gnome.FileRoller
```

### 3. Test ZSH Shell

```bash
# Check default shell
echo $SHELL

# Should output: /run/current-system/sw/bin/zsh
```

### 4. Test Python Packages

```bash
# Verify all packages
python3 -c "import anthropic, polars; import ruff; import mypy; print('All packages available')"

# Check versions
python3 -c "import anthropic; print(f'anthropic: {anthropic.__version__}')"
python3 -c "import polars; print(f'polars: {polars.__version__}')"
```

### 5. Monitor Flatpak Service

```bash
# Check service status
systemctl --user status flatpak-managed-install.service

# View service logs
journalctl --user -u flatpak-managed-install.service -f
```

## Known Limitations

### 1. Some Flatpak Apps Not Available

The following apps are not available on Flathub for x86_64:
- `ai.cursor.Cursor`
- `com.lmstudio.LMStudio`
- `io.gitea.Gitea`

**Workaround:** Install these apps using alternative methods (AppImage, native packages, etc.)

### 2. Multiple Freedesktop Platform Runtimes

After multiple home-manager switches, you may accumulate multiple versions of the Freedesktop Platform runtime.

**Cleanup:**
```bash
flatpak uninstall --unused
```

### 3. PATH Not Updated After home-manager Switch

Sometimes PATH doesn't update immediately after home-manager switch.

**Solution:**
```bash
# Reload shell
exec zsh

# Or source session variables manually
source ~/.nix-profile/etc/profile.d/hm-session-vars.sh
```

## Success Criteria

After running the fixed script and rebooting:

✅ System boots into COSMIC desktop
✅ All Python packages available (anthropic, polars, ruff, mypy)
✅ Flatpak repository functional (no corruption errors)
✅ ZSH is default shell
✅ No PAM authentication errors
✅ flatpak-managed-install.service completes successfully
✅ No timeout errors in systemd services

## Files Modified

1. `/home/user/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh`
   - Split `update_nixos_system_config()` into two functions
   - Reorganized `main()` flow
   - Added Flatpak repository re-initialization
   - Fixed chsh PAM authentication

2. `/home/user/NixOS-Dev-Quick-Deploy/templates/home.nix`
   - Already includes all required Python packages
   - flatpak-managed-install.service timeout already set to 600s

3. `/home/user/NixOS-Dev-Quick-Deploy/templates/configuration.nix`
   - Already includes complete COSMIC configuration
   - No changes needed

## Support

If you encounter issues:

1. **Run system health check:**
   ```bash
   ~/NixOS-Dev-Quick-Deploy/scripts/system-health-check.sh
   ```

2. **Check logs:**
   ```bash
   journalctl --user -u flatpak-managed-install.service
   journalctl -u home-manager-$USER.service
   ```

3. **Verify Nix profile:**
   ```bash
   nix-store --verify-path ~/.nix-profile
   ```

4. **Re-apply home-manager:**
   ```bash
   cd ~/.dotfiles/home-manager
   home-manager switch --flake .
   ```

## Conclusion

All reported issues have been fixed:

✅ System rebuild prompt now appears BEFORE backups
✅ Flatpak repository properly initialized
✅ Service timeout increased to 10 minutes
✅ ZSH chsh PAM authentication fixed
✅ Python packages verified in configuration
✅ COSMIC desktop properly configured

The script is now more user-friendly, safer, and more reliable.
