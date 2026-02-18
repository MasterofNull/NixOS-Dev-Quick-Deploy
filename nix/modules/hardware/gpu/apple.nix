{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Apple Silicon GPU module (AGX / Apple Graphics Accelerator)
#
# Covers: Apple M-series integrated GPU running NixOS via Asahi Linux.
# GPU generations:
#   AGX G13G / G13S  — M1, M1 Pro/Max/Ultra
#   AGX G14G / G14S  — M2, M2 Pro/Max/Ultra
#   AGX G15G          — M3, M3 Pro/Max/Ultra
#   AGX G16G          — M4, M4 Pro/Max/Ultra (NixOS support TBD)
#
# Activation gate: mySystem.hardware.gpuVendor == "apple"
#
# CRITICAL — Asahi requirements:
#   This module enables standard NixOS GPU options for Apple AGX.
#   The actual AGX kernel driver (drm/asahi), Mesa AGX backend (honeykrisp),
#   and GPU firmware blobs MUST be provided by the Asahi Linux kernel package
#   and the Mesa Asahi edge overlay.  Without those, this module has no effect.
#
#   Required — choose ONE of:
#     a) nixos-hardware apple modules (when merged):
#          inputs.nixos-hardware.nixosModules."apple-m1"
#     b) nixos-apple-silicon community flake:
#          inputs.apple-silicon.nixosModules.apple-silicon-support
#
#   Set mySystem.hardware.nixosHardwareModule = "apple-m1" (or m2/m3/m4) in
#   facts.nix so the root flake.nix imports the module automatically.
#
# Mesa Asahi edge (2026 status):
#   - OpenGL 4.6 via Zink (OpenGL over Vulkan)
#   - Vulkan 1.3 via honeykrisp AGX driver
#   - Metal-level GPU features accessible via Vulkan extensions
#   - Hardware video decode: via AVD (Apple Video Decoder) — partial support
#   - OpenCL: via clvk (OpenCL over Vulkan) — experimental
#
# Architecture: aarch64-linux — set mySystem.system = "aarch64-linux" in facts.nix.
# ---------------------------------------------------------------------------
let
  cfg     = config.mySystem;
  isApple = cfg.hardware.gpuVendor == "apple";

  # mesa-asahi-edge provides the AGX Vulkan driver (honeykrisp).
  # On standard nixpkgs, only the standard Mesa (without AGX) is available.
  # The Asahi flake provides mesa-asahi-edge as an overlay package.
  hasMesaAsahi = builtins.hasAttr "mesa-asahi-edge" pkgs;
  hasMesa      = builtins.hasAttr "mesa" pkgs;
in
{
  config = lib.mkIf isApple {
    # ---- Mesa / AGX graphics stack ----------------------------------------
    hardware.graphics = {
      enable      = lib.mkDefault true;
      enable32Bit  = lib.mkDefault false;  # Not applicable on aarch64

      extraPackages = lib.mkDefault (
        # Prefer mesa-asahi-edge (Asahi overlay) when available;
        # fall back to standard Mesa (limited AGX support).
        if hasMesaAsahi then [ pkgs.mesa-asahi-edge ]
        else if hasMesa then [ pkgs.mesa ]
        else [ ]
      );
    };

    # ---- Wayland / display ------------------------------------------------
    # AGX DRM/KMS exposes a standard DRM interface.
    # Wayland compositors work natively once the AGX driver is loaded.
    # GNOME 47+, KDE Plasma 6, and sway all tested on Asahi (2026).

    # ---- Session variables -------------------------------------------------
    # Asahi Mesa sets VK_ICD_FILENAMES automatically via the Mesa package.
    # No manual LIBVA_DRIVER_NAME needed — AGX VA-API backend is not yet stable.

    # ---- Kernel module -------------------------------------------------------
    # The Asahi kernel includes drm/asahi as a built-in or loadable module.
    # It is loaded automatically by the DRM subsystem from firmware data.
    # No boot.kernelModules entries needed.

    # ---- Known limitations (Asahi, 2026) ------------------------------------
    # - External GPU (eGPU via Thunderbolt): not supported by Asahi kernel yet.
    # - DisplayPort over USB-C: supported on M1 (Thunderbolt 3); M2/M3 improving.
    # - Hardware video encode: not yet exposed via VA-API; use software encode.
    # - Pro Display XDR: works at native resolution; HDR mapping may differ.
    # - Sleep/wake with multiple external displays: occasional regression.

    # ---- Performance notes -------------------------------------------------
    # GPU devfreq is managed by the Asahi kernel's pmgr driver.
    # AGX performance is on par with the Apple GPU (within driver limitations).
    # For AI/ML inference, use CPU (excellent on M-series) or wait for
    # Metal-equivalent compute shaders via Vulkan compute + honeykrisp.

    # ---- Privacy / location / sensors -------------------------------------
    # Apple embedded sensors (ALS, accelerometer, lid sensor) are exposed via
    # iio-sensor-proxy in newer Asahi kernels.  Not enabled here; opt in per-host.
  };
}
