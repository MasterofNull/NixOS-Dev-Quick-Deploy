{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Intel Arc discrete GPU module (Xe / Arc A-series, B-series)
#
# Covers: Intel Arc A-series and B-series discrete GPUs.
# Examples:
#   Arc A-series (Alchemist, DG2):   A310, A380, A530M, A550M, A570M, A730M, A770
#   Arc B-series (Battlemage, BMG):  B580, B770
#
# Activation gate: mySystem.hardware.gpuVendor == "intel-arc"
#
# Key difference from gpu/intel.nix (integrated GPUs):
#   - Integrated Intel GPUs (HD/Iris/UHD/Xe-LP) use the i915 driver.
#   - Intel Arc discrete GPUs (A/B-series) use the xe driver (kernel 6.8+)
#     or i915 in legacy mode (kernel <6.8, limited support).
#   - This module sets gpu/intel.nix settings PLUS Arc-specific options.
#
# For Intel hybrid systems (Intel iGPU + Arc dGPU):
#   - Set gpuVendor = "intel-arc"   (the discrete Arc GPU)
#   - Set igpuVendor = "intel"      (the integrated GPU for display output)
#   - gpu/intel.nix activates for the iGPU; this module for the Arc dGPU.
#
# Driver stack:
#   Kernel   : xe (6.8+, preferred) or i915 (legacy mode)
#   OpenGL   : Mesa Intel ANV (Vulkan) + iris (OpenGL) — unified for Arc + iGPU
#   Vulkan   : Intel ANV (Arc A/B fully supported in Mesa 24+)
#   Video    : Intel MEDIA (iHD VA-API driver, Arc A/B fully supported)
#   Compute  : Intel NEO (OpenCL, Arc fully supported)
#   Ray trace: DXR/Vulkan RT on Arc A770/B580/B770
#
# Firmware: Intel GuC/HuC firmware required for Arc.
#   - Provided by linux-firmware (included in hardware.enableAllFirmware or
#     manually via hardware.firmware).
# ---------------------------------------------------------------------------
let
  cfg    = config.mySystem;
  isArc  = cfg.hardware.gpuVendor == "intel-arc";

  # Detect xe driver availability (kernel 6.8+, NixOS 25.11 uses ≥6.6).
  # On NixOS 25.11, xe may be present but experimental; i915 handles Arc in compat mode.
  # On NixOS 26.05+, xe is the preferred driver for Arc.
  hasXeDriver = lib.versionAtLeast lib.version "26.05";

  # intel-compute-runtime (Intel NEO) provides OpenCL for Arc.
  hasNEO = builtins.hasAttr "intel-compute-runtime" pkgs;

  # intel-media-driver (iHD) VA-API backend for Arc hardware decode.
  hasIHD = builtins.hasAttr "intel-media-driver" pkgs;

  # intel-vaapi-driver (i965) — legacy, NOT needed for Arc.
in
{
  config = lib.mkIf isArc {
    # ---- Mesa / Vulkan / OpenGL --------------------------------------------
    hardware.graphics = {
      enable      = lib.mkDefault true;
      enable32Bit  = lib.mkDefault true;  # Steam Proton / 32-bit Wine support

      extraPackages = lib.mkDefault (
        lib.optionals hasIHD  [ pkgs.intel-media-driver ]  # VA-API (iHD)
        ++ lib.optionals hasNEO [ pkgs.intel-compute-runtime ]  # OpenCL NEO
        ++ lib.optionals (pkgs ? intel-ocl) [ pkgs.intel-ocl ]
      );

      extraPackages32 = lib.mkDefault (
        lib.optionals (pkgs ? pkgsi686Linux && pkgs.pkgsi686Linux ? mesa)
          [ pkgs.pkgsi686Linux.mesa ]
      );
    };

    # ---- VA-API (hardware video decode/encode) ----------------------------
    environment.sessionVariables = {
      # iHD is the VA-API driver for Arc A/B (and modern Intel iGPUs).
      LIBVA_DRIVER_NAME = lib.mkDefault "iHD";
    };

    # ---- Kernel driver selection -------------------------------------------
    # xe is the new unified Xe driver for Intel Arc (discrete) and Meteor Lake+
    # (integrated).  On NixOS 25.11, xe is experimental; i915 handles Arc via
    # the DGFX compatibility path.
    #
    # Force xe on 26.05+ where it is stable; on 25.11, i915 compat mode is used.
    boot.kernelModules = lib.optionals hasXeDriver [ "xe" ];

    # GuC/HuC firmware: required for Arc command submission and video decode.
    # linux-firmware includes the Intel GuC/HuC blobs.
    hardware.enableAllFirmware = lib.mkDefault false;  # too broad; prefer selective
    hardware.firmware = lib.mkDefault (
      lib.optionals (pkgs ? linux-firmware) [ pkgs.linux-firmware ]
    );

    # ---- Performance / power tuning ----------------------------------------
    # Arc A-series (Alchemist) has known PCI power management issues on Linux;
    # runtime PM (ASPM) can cause hangs.  Disable ASPM on Arc A-series:
    # (This is a known errata; Arc B-series does not have this issue.)
    # Uncomment if you hit GPU hangs on A-series cards:
    # boot.kernelParams = lib.mkAfter [ "pcie_aspm=off" ];

    # ---- Arc-specific notes ------------------------------------------------
    # GuC HW scheduling (default in xe driver) improves multi-GPU workload
    # scheduling.  No userspace config needed.
    #
    # Ray tracing on Arc A770/B580/B770: Vulkan RT is supported via Mesa ANV.
    # No extra configuration needed; Vulkan RT extensions are exposed
    # automatically when the ANV driver is active.
    #
    # XeSS (Arc super sampling): requires Intel XeSS library (proprietary).
    # Not included here; opt in per-game via the game's settings.
  };
}
