# GLF OS Module Highlights

The GLF OS repository (`https://framagit.org/gaming-linux-fr/glf-os/glf-os`) exposes a modular NixOS layout with a focus on gaming and desktop polish. Key patterns to borrow when integrating its ideas into other systems include:

## Module Layout
* `modules/default/default.nix` ties together feature modules for boot tuning, branding, NVIDIA support, gaming packages, PipeWire, printing, standby behaviour, and bespoke tooling such as the MangoHud presets and welcome application. Options under `glf.*` enable or disable each slice so they can be imported as a bundle.  
* `modules/default/environment.nix` defines the `glf.environment` option set (type, edition, enable flag) and wires in per-desktop modules for GNOME, Plasma, and the "Studio" add-ons. Wallpapers are deployed via `/etc/wallpapers/glf/` entries when the desktop layer is enabled.

## Boot and Kernel Optimisations
* `modules/default/boot.nix` overlays the kernel configuration to force a 1000Hz scheduler tick, enable BFQ as the default I/O scheduler, and set additional device support (e.g., `V4L2_LOOPBACK`). The module pins `linuxPackages_6_17`, enables Plymouth with a custom theme, and sets BFQ through an extra udev rule.  
* The same module ships aggressive `sysctl` defaults for gaming workloads—low `vm.swappiness`, high `vm.max_map_count`, disabled split-lock mitigation, and other kernel toggles aimed at latency-sensitive applications.

## Desktop Experience
* The GNOME module (`modules/default/environments/gnome.nix`) enables GDM, fractional scaling, curated extensions, and applies GLF branding assets. It removes upstream GNOME apps such as Epiphany and Geary, replaces them with gaming-centric favourites, and sets wallpapers and theme defaults through `dconf`.
* `modules/default/packages.nix` enables Flatpak, seeds the Flathub remote, installs EasyFlatpak and Discord automatically, and turns on AppImage support. Package sets vary with the selected edition (`mini`, `standard`, etc.).
* `modules/default/glfos-environment-selection.nix` and `pkgs/glfos-environment-selection` deliver a Zenity-driven selector utility that can be bundled as a system package whenever the desktop environment is active. A welcome screen package is provided similarly.

## Gaming Stack
* `modules/default/gaming.nix` pulls software from both stable and unstable channels: Lutris with extra libraries, Heroic, UMU, Mangohud, Proton GE, and vendor-specific drivers (Fanatec, new-lg4ff). It enables Gamescope, sets MangoHud overlays via `MANGOHUD_CONFIG`, and configures Steam with Gamescope sessions and remote play firewall openings.  
* Hardware-specific options include udev rules to ignore DualSense touchpads, and toggles for OpenTabletDriver, Xbox controller stacks, and other accessories.

## System Services and Optimisation
* `modules/default/system.nix` enables `nix-ld`, configures ZRAM (25% of RAM using `zstd`), and adds 32-bit graphics support with validation tools from `pkgs-unstable`—handy for legacy games.
* `modules/default/nvidia.nix` exposes a `glf.nvidia_config` option set to activate the proprietary driver with PRIME offload support. It builds a fixed driver version (`580.95.05`) via `mkDriver`, toggling laptop-specific power options when requested.

## Automated Updates
* `modules/default/update.nix` ships a comprehensive `/etc/glfos/update.sh` script. The timer waits for network availability, updates Flatpaks, runs `nix flake update` with retries, optionally rewrites legacy autologin syntax, rebuilds the system, cleans generations, and notifies logged-in users via D-Bus. Systemd units (`glfos-update.service`/`.timer`) run the workflow every 12 hours by default.

These modules can be imported wholesale or used as references when crafting similar features for other flake-based deployments. Most behaviours are guarded behind `glf.*` options, allowing selective adoption depending on the host system's requirements.
