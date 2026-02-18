{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Qualcomm Adreno GPU module
#
# Covers: Adreno GPUs found in Qualcomm Snapdragon SoCs running NixOS.
# Examples:
#   - Adreno 690 (Snapdragon 8cx Gen 3) — ThinkPad X13s
#   - Adreno 740 (Snapdragon 8 Gen 2)   — Reference boards
#   - Adreno X1 (Snapdragon X Elite)    — Next-gen Copilot+ PCs
#
# Activation gate: mySystem.hardware.gpuVendor == "adreno"
#
# Driver stack:
#   Kernel driver  : msm (mainline) — DRM/KMS driver for Qualcomm display/GPU
#   OpenGL/Vulkan  : Mesa freedreno (OpenGL) + Turnip (Vulkan) — fully open-source
#   Video decode   : V4L2 stateless API via Venus firmware (where supported)
#   Compute (OpenCL): clvk (OpenCL over Vulkan/Turnip) — experimental
#
# Maturity note (2026):
#   - ThinkPad X13s (Adreno 690): OpenGL 3.3 / Vulkan 1.3 via Turnip — GOOD
#   - Snapdragon X Elite (Adreno X1): Turnip Vulkan support landing in Mesa 25.x
#   - Hardware video decode (Venus): requires Qualcomm-signed firmware blobs
#
# Board firmware blobs (WiFi, GPU, modem) must be installed via the
# nixos-hardware Qualcomm / ThinkPad X13s module, which includes the
# linux-firmware package subset and extraction helpers.
# ---------------------------------------------------------------------------
let
  cfg       = config.mySystem;
  isAdreno  = cfg.hardware.gpuVendor == "adreno";

  # Turnip is Mesa's Adreno Vulkan driver — part of main Mesa since 21.0.
  # freedreno is the OpenGL driver (always part of Mesa).
  hasTurnip = builtins.hasAttr "mesa" pkgs;  # Turnip ships inside Mesa on NixOS
in
{
  config = lib.mkIf isAdreno {
    # ---- Mesa / Graphics stack ---------------------------------------------
    hardware.graphics = {
      enable     = lib.mkDefault true;
      enable32Bit = lib.mkDefault false;  # 32-bit not relevant on aarch64

      # freedreno (OpenGL) and Turnip (Vulkan) ship inside the standard Mesa
      # package on NixOS — no extra packages needed beyond enabling Mesa.
      extraPackages = lib.mkDefault (
        lib.optionals (pkgs ? mesa) [ pkgs.mesa ]
      );
    };

    # ---- DRM / display -----------------------------------------------------
    # msm driver is loaded by the kernel from DTB/ACPI entries.
    # On ACPI-based boards (ThinkPad X13s), no initrd module loading needed.
    # On DTB-based boards, the SoC-specific dtb provides the binding.

    # ---- VA-API / video decode ---------------------------------------------
    # Venus (firmware-assisted video decode) requires Qualcomm signed blobs.
    # When present, NixOS exposes VA-API via libva-v4l2-request.
    # Set LIBVA_DRIVER_NAME only when a VA-API backend is confirmed available.
    # Leave unset here; users can override in nix/hosts/<host>/default.nix.

    # ---- Wayland / display environment ------------------------------------
    # Adreno + DRM KMS works natively under Wayland (Weston, GNOME, KDE).
    # No special session variables needed beyond Mesa defaults.
    environment.sessionVariables = {
      # VK_ICD_FILENAMES is auto-set by Mesa when Turnip is the active driver.
      # EGL_PLATFORM is already "wayland" in a Wayland session.
    };

    # ---- Kernel modules ----------------------------------------------------
    # msm and related modules are loaded automatically from DTB/ACPI.
    # No explicit boot.kernelModules entries needed for standard setups.

    # ---- Performance tuning ------------------------------------------------
    # Adreno GPU performance scaling is managed by the msm driver and
    # devfreq framework.  No manual sysctl or boot param tuning available
    # in the mainline kernel as of 2026.
  };
}
