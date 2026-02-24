# Known Issues & Troubleshooting

## Phase 30 — Virtualization Stack

#### NIX-ISSUE-024: `virtualisation.libvirtd.qemu.ovmf` removed in NixOS 25.11 (Fixed)
- **Date**: 2026-02-20
- **Status**: ✅ Fixed in `nix/modules/roles/virtualization.nix`
- **Symptom**: Enabling `roles.virtualization.enable = true` fails evaluation with:
  ```
  Failed assertions:
  - The 'virtualisation.libvirtd.qemu.ovmf' submodule has been removed.
    All OVMF images distributed with QEMU are now available by default.
  ```
- **Root Cause**: `virtualization.nix` set `virtualisation.libvirtd.qemu.ovmf.enable = lib.mkDefault true`. This submodule was removed in NixOS 25.11; OVMF firmware is now bundled automatically with the libvirt QEMU driver and no longer requires opt-in.
- **Fix**: Removed `ovmf.enable = lib.mkDefault true;` from the `qemu {}` block. The submodule must not appear at all in NixOS 25.11+.
- **Tracking**: NIX-ISSUE-024, Phase 30

---

## Phase 7 - Documentation Verification

### Known Issues

#### 0a. thermald Priority Conflict — mkDefault Collision (Fixed)
- **Date**: 2026-02-15
- **Status**: ✅ Fixed in `templates/nixos-improvements/mobile-workstation.nix`
- **Symptom**: Phase 3 dry-build fails with:
  ```
  error: The option `services.thermald.enable' has conflicting definition values:
  - In '.../nixos-improvements/mobile-workstation.nix': true
  - In '.../configuration.nix': false
  ```
- **Root Cause**: The NIX-ISSUE-011 fix added `services.thermald.enable = lib.mkDefault (config.hardware.cpu.intel.updateMicrocode or false)` (evaluates to `lib.mkDefault false` on AMD) to `configuration.nix`. But `mobile-workstation.nix` already had `services.thermald.enable = lib.mkDefault true`. Both at priority 1000 — NixOS module system cannot reconcile two `lib.mkDefault` values for the same boolean option.
- **Fix**: Removed `services.thermald.enable = lib.mkDefault true` from `mobile-workstation.nix`. `configuration.nix` now owns this setting exclusively with the CPU vendor guard.
- **Rule**: Two modules must never set the same non-list option to different values at the same `lib.mkDefault`/`lib.mkOverride` priority. Use `lib.mkForce` in one module to establish a clear winner, or consolidate into one module.
- **Tracking**: NIX-ISSUE-014, Phase 25.6

#### 0b. xdg-desktop-portal-gnome in COSMIC Setup — Portal D-Bus Errors (Fixed)
- **Date**: 2026-02-15
- **Status**: ✅ Fixed in `templates/configuration.nix`
- **Symptom**: COSMIC app file pickers, screenshots, and screen share fail silently or produce errors. `journalctl` shows repeated D-Bus errors from `xdg-desktop-portal` trying to connect to `org.gnome.Shell`.
- **Root Cause**: `xdg-desktop-portal-gnome` was in `xdg.portal.extraPortals`. This portal implementation requires `gnome-shell` to be running on D-Bus. In a COSMIC session gnome-shell is not present, so every portal request from COSMIC or Hyprland apps that gets routed to the GNOME backend fails.
- **Fix**: Removed `pkgs.xdg-desktop-portal-gnome` from `extraPortals`. Portal list is now:
  ```nix
  lib.optionals (pkgs ? xdg-desktop-portal-cosmic) [ pkgs.xdg-desktop-portal-cosmic ]
  ++ [ pkgs.xdg-desktop-portal-hyprland ]
  ```
- **Tracking**: NIX-ISSUE-015, Phase 25.7

#### 0. Phase 3 Dry-Build Infinite Recursion (Fixed)
- **Date**: 2026-02-13
- **Status**: ✅ Fixed in templates and validated against `~/.dotfiles/home-manager`
- **Symptom**: `nixos-rebuild dry-build` fails with `error: infinite recursion encountered`
- **Root Cause**: Recursive `options` access in `configuration.nix` module guard (`gcr-ssh-agent`), plus cross-version module option mismatches
- **Fix**:
  - Updated `templates/configuration.nix` to use `lib.versionAtLeast` guard instead of `options` lookup
  - Removed unstable logind/systemd override paths in `templates/nixos-improvements/*.nix` to avoid option-path churn across pinned nixpkgs revisions
  - Updated generator output in `lib/config.sh` to keep user-unit swap limits and drop host-level systemd Manager/extraConfig swap block
- **Resolved Error Chain**:
  - `error: infinite recursion encountered` (`options.services.gnome ? gcr-ssh-agent`)
  - `services.logind.settings does not exist` / `services.logind.extraConfig no longer has any effect` (resolved by removing module-level logind override)
  - `systemd.settings does not exist` / `systemd.extraConfig no longer has any effect` (resolved by removing module-level systemd timeout override)
  - `systemd.settings.Manager does not exist` in generated swap block (resolved by dropping host-level systemd swap Manager injection)
  - `undefined variable 'perf'` (guarded `pkgs.linuxPackages.perf`)
  - insecure package block from Heroic (`electron-36.9.5`) removed from defaults
  - duplicate unique sysctl (`fs.inotify.max_user_instances`) removed from optimizations overrides
  - unsupported `users.users.<name>.forceInitialPassword` removed from generator defaults
  - Phase 3 now treats `/etc/nixos/nixos-improvements` sync as best-effort in non-interactive sudo contexts (prevents partially rendered configs)
- **Recovery Commands**:
  ```bash
  # Regenerate config files from templates (without applying switch)
  ./nixos-quick-deploy.sh --start-from-phase 3 --skip-switch

  # Fast evaluation check
  nix --extra-experimental-features nix-command \
      --extra-experimental-features flakes \
      flake check ~/.dotfiles/home-manager --no-build
  ```

#### 1. thermald Crashes on AMD CPU — Intel-Only Service (Fixed)
- **Date**: 2026-02-15
- **Status**: ✅ Fixed in `templates/configuration.nix`
- **Symptom**: On every boot: `thermald: Unsupported cpu model or platform` followed by `thermald.service: Deactivated successfully`. Fans run at 3300 RPM via ACPI hardware but NixOS thermal policy is never applied. This can appear as "fan not working" since the software thermal management daemon is inactive.
- **Root Cause**: `services.thermald.enable = true` was unconditional. `thermald` is an Intel-only daemon and immediately quits on AMD processors. The ThinkPad P14s Gen 2a uses AMD Ryzen, so thermald fails every boot.
- **Fix**:
  ```nix
  # Before:
  services.thermald.enable = true;
  # After — Intel-only guard:
  services.thermald.enable = lib.mkDefault (config.hardware.cpu.intel.updateMicrocode or false);
  ```
  On AMD systems `hardware.cpu.intel.updateMicrocode` is not set, so the expression evaluates to `false`. On Intel systems it evaluates to `true`, preserving the original behaviour.
- **Tracking**: NIX-ISSUE-011, Phase 25.1
- **Note**: AMD systems get thermal management via ACPI hardware (always active). `k10temp` driver is already loaded by the kernel. `auto-cpufreq` can be added to `mobile-workstation.nix` for more aggressive AMD power management.

#### 2. WirePlumber SIGABRT Crash — libcamera UVC Pipeline (Fixed)
- **Date**: 2026-02-15
- **Status**: ✅ Fixed in `templates/configuration.nix`
- **Symptom**: On every boot: `wireplumber.service: Failed with result 'core-dump'`. A core dump is generated. WirePlumber auto-restarts but audio initialization is delayed and the journal is flooded with a full stack trace on each boot.
- **Root Cause**: wireplumber's `monitor.libcamera` plugin starts camera enumeration at startup. libcamera's `PipelineHandlerUVC::match` calls `LOG(Fatal)` when it encounters a V4L2 device it cannot register, which triggers `abort()` in the `LogMessage` destructor — killing wireplumber. Happens on systems where the UVC device list does not match libcamera's expectations.
- **Fix**: Disabled the libcamera monitor in wireplumber via extraConfig:
  ```nix
  services.pipewire.wireplumber.extraConfig."10-disable-libcamera" = {
    "wireplumber.profiles".main."monitor.libcamera" = "disabled";
  };
  ```
  Systems with USB cameras can re-enable by overriding this key in a local NixOS module.
- **Tracking**: NIX-ISSUE-012, Phase 25.2

#### 3. No EFI Graceful Mode — Non-Fatal EFI Errors Abort Boot Install (Fixed)
- **Date**: 2026-02-15
- **Status**: ✅ Fixed in `templates/configuration.nix`
- **Symptom**: `nixos-rebuild switch` can abort during the systemd-boot EFI installation step when non-fatal EFI variable write errors occur, leaving the system without a new bootloader entry even when the NixOS config built successfully.
- **Root Cause**: `boot.loader.systemd-boot.graceful` was not set (defaults to `false`), making all EFI errors fatal to the install step. Triggered by FAT32 dirty bit on ESP after dirty shutdown, firmware EFI quirks, or read-only EFI variable stores.
- **Fix**:
  ```nix
  boot.loader.systemd-boot.graceful = lib.mkDefault true;
  ```
  Non-fatal EFI errors become warnings; the install completes and the system remains bootable.
- **Tracking**: NIX-ISSUE-013, Phase 25.3

#### 4. Silent I/O Scheduler Config Loss — `//` Shallow Merge (Fixed)
- **Date**: 2026-02-15
- **Status**: ✅ Fixed in `templates/nixos-improvements/optimizations.nix`
- **Symptom**: I/O scheduler udev rules (`services.udev.extraRules`) silently absent from evaluated NixOS config on nixos-25.11 — NVMe/SSD/HDD scheduler optimizations not applied, no error raised
- **Root Cause**: `optimizations.nix` used Nix `//` (shallow merge) to add version-gated options at end of file:
  ```nix
  } // lib.optionalAttrs hasNixosInit { services.userborn.enable = ...; }
  ```
  Nix `//` replaces the entire top-level `services` key, so the `services.udev.extraRules` I/O scheduler rules from the main block were silently discarded. On nixos-25.11 `hasNixosInit = true`, so this affected every deployment.
- **Fix**: Removed all `// lib.optionalAttrs` blocks; moved `system.nixos-init.enable`, `system.etc.overlay.enable`, `services.userborn.enable`, and `services.lact.enable` inline inside the main `{ }` block using `lib.mkIf`:
  ```nix
  system.nixos-init.enable = lib.mkIf hasNixosInit (lib.mkDefault true);
  services.userborn.enable = lib.mkIf hasNixosInit (lib.mkDefault true);
  services.lact.enable = lib.mkIf hasLact (lib.mkDefault true);
  ```
  The NixOS module system deep-merges `lib.mkIf`-wrapped option declarations, preserving all `services.*` from every module.
- **Tracking**: NIX-ISSUE-010, Phase 24.5

#### 2. Open WebUI CrashLoopBackOff
- **Status**: ⚠️ Optional service in CrashLoopBackOff state
- **Impact**: Does not affect core AI stack functionality
- **Resolution**: This is an optional service and does not impact core functionality
- **Tracking**: Issue acknowledged in test results

#### 2. Registry Push Flow
- **Status**: Pending documentation for immutable image tagging
- **Workaround**: Current workflow uses `localhost:5000` local registry
- **Commands**:
  ```bash
  # Tag and push images
  skopeo copy docker://source/image docker://localhost:5000/target/image:tag
  
  # Or use buildah for building and pushing
  buildah bud -t localhost:5000/service-name:tag .
  buildah push localhost:5000/service-name:tag
  ```

#### 3. Portainer Initial Setup
- **Status**: Pending validation of login and initial wizard reset
- **Default Access**:
  - URL: http://localhost:9000 or configured port
  - Default user: admin
  - Default password: prompted on first login

### Troubleshooting Commands

#### Service Health Checks
```bash
# Check all services health
curl http://localhost:8091/health  # AIDB
curl http://localhost:8092/health  # Hybrid Coordinator  
curl http://localhost:8098/health  # Ralph Wiggum
curl http://localhost:8081/health  # Embeddings
```

#### Kubernetes Status
```bash
# Check all pods in ai-stack namespace
kubectl get pods -n ai-stack

# Check services
kubectl get svc -n ai-stack

# Check deployments
kubectl get deployments -n ai-stack
```

#### Common Fixes
```bash
# Restart problematic deployments
kubectl rollout restart deployment/DEPLOYMENT_NAME -n ai-stack

# Check logs
kubectl logs -f deployment/DEPLOYMENT_NAME -n ai-stack

# Scale deployment if needed
kubectl scale deployment/DEPLOYMENT_NAME --replicas=1 -n ai-stack
```

### Testing Commands
```bash
# Run the full E2E test suite
python -m pytest tests/test_hospital_e2e.py -v

# Run API contract tests
python -m pytest ai-stack/tests/test_api_contracts.py -v

# Run individual service tests
python -m pytest ai-stack/tests/ -k "service_name"
```
