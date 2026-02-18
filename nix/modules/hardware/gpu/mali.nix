{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# ARM Mali GPU module (open-source driver stack)
#
# Covers: ARM Mali GPUs found on ARM-based SoCs.
# Examples by driver:
#   Panfrost (recommended, mainline):
#     - Mali-T860/T880 (Rockchip RK3399, e.g. Rock64, Pinebook Pro)
#     - Mali-G31/G52/G57/G72/G76 (Bifrost, e.g. Raspberry Pi 5 VideoCore VII is
#       actually different — see below; Amlogic S922X, Rockchip RK3568/RK3588)
#     - Mali-G610 (Valhall, e.g. Rockchip RK3588)
#   Lima (legacy, mainline):
#     - Mali-400/450 (Utgard, e.g. AllWinner H3/H5, old SBCs)
#
# Activation gate: mySystem.hardware.gpuVendor == "mali"
#
# IMPORTANT: Raspberry Pi GPU is NOT Mali.  The Pi 4 uses VideoCore VI
# (V3D — covered by vc4/v3d driver) and Pi 5 uses VideoCore VII.
# For Raspberry Pi, use the nixos-hardware raspberry-pi modules instead.
#
# Driver maturity (2026):
#   Panfrost:  OpenGL ES 3.1 / OpenGL 3.0 on Bifrost; Vulkan via experimental
#              PanVk (landing in Mesa 25+) on newer Bifrost/Valhall.
#   Lima:      OpenGL ES 2.0 (Utgard) — sufficient for most 2D use cases.
#   Proprietary Mali (arm-mali-blob): NOT included here.  Proprietary driver
#     requires downloading the binary DDK from ARM and manual wiring.
#     Use only when you specifically need OpenCL 2.x or Mali EGL extensions.
#
# Board-specific kernel config (DTB, clock rates, memory partitions) must be
# set via the appropriate nixos-hardware module for your board family.
# ---------------------------------------------------------------------------
let
  cfg     = config.mySystem;
  isMali  = cfg.hardware.gpuVendor == "mali";

  # Panfrost and Lima ship inside Mesa on NixOS.
  hasMesa = builtins.hasAttr "mesa" pkgs;
in
{
  config = lib.mkIf isMali {
    # ---- Mesa / Panfrost / Lima --------------------------------------------
    hardware.graphics = {
      enable      = lib.mkDefault true;
      enable32Bit  = lib.mkDefault false;  # Not applicable on aarch64

      # Mesa includes both panfrost (Midgard/Bifrost/Valhall) and lima (Utgard).
      # The correct driver is selected automatically from the DRM device node.
      extraPackages = lib.mkDefault (
        lib.optionals hasMesa [ pkgs.mesa ]
      );
    };

    # ---- Wayland / DRM ---------------------------------------------------
    # Panfrost and Lima expose a standard DRM/KMS interface.
    # Wayland compositors (Weston, sway, GNOME) work natively.

    # ---- Kernel modules --------------------------------------------------
    # panfrost and lima are built into the kernel as modules on most ARM configs.
    # They are loaded automatically via DTB device bindings — no explicit
    # boot.kernelModules entries needed for standard board kernels.

    # ---- Known limitations (as of 2026) ----------------------------------
    # - Vulkan: PanVk (Panfrost Vulkan) is experimental; disabled by default.
    #   To opt in: hardware.opengl.extraPackages = [ pkgs.mesa.drivers ];
    #   and set VK_ICD_FILENAMES to the panvk ICD.
    # - OpenCL: Not supported on open-source Mali stack (Panfrost/Lima).
    #   Requires proprietary ARM Compute Library / Mali DDK.
    # - Hardware video decode: Mali VPUs use codec-specific drivers
    #   (hantro, cedrus, rkvdec) — handled by the SoC kernel config.
    #   Set LIBVA_DRIVER_NAME in your host's default.nix when a VA-API
    #   backend (v4l2-request) is confirmed functional.

    # ---- Performance notes -----------------------------------------------
    # GPU devfreq (dynamic frequency scaling) is managed by the kernel.
    # On boards with a thermal limit, the kernel may throttle automatically.
    # No userspace governor tuning available in the mainline stack.
  };
}
