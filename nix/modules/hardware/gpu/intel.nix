{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  # Activate when Intel is the primary GPU OR when it's the iGPU in a hybrid setup.
  # Hybrid case: Nvidia dGPU + Intel iGPU (Optimus). Both modules activate; VA-API
  # uses iHD for QuickSync decode while Nvidia handles rendering.
  isIntelPrimary = cfg.hardware.gpuVendor == "intel";
  isIntelHybrid  = cfg.hardware.igpuVendor == "intel";
  hasIntel = isIntelPrimary || isIntelHybrid;
in
{
  # Intel GPU: iHD VA-API, QuickSync, OpenCL. Active for both primary and hybrid iGPU.
  hardware.graphics = lib.mkIf hasIntel {
    enable = lib.mkDefault true;
    enable32Bit = lib.mkDefault true;
    extraPackages = with pkgs; lib.mkAfter [
      intel-media-driver     # iHD VA-API (Gen 8+: Broadwell, Skylake, Ice Lake, etc.)
      vaapiIntel             # i965 VA-API fallback for Gen 4–7 hardware
      intel-compute-runtime  # OpenCL via Intel NEO (Gen 12+)
    ] ++ lib.optionals (pkgs ? intel-ocl) [ pkgs.intel-ocl ];
  };

  # i915 early KMS: load in initrd when Intel is primary or earlyKmsPolicy=force.
  # On hybrid systems (Intel iGPU + Nvidia dGPU), i915 loads for display init;
  # Nvidia modesetting takes over for rendering after login.
  boot.initrd.kernelModules = lib.mkIf (hasIntel && cfg.hardware.earlyKmsPolicy != "off")
    (lib.mkAfter [ "i915" ]);

  # VA-API: only set LIBVA_DRIVER_NAME when Intel is the primary display GPU.
  # On hybrid systems the dGPU module (nvidia.nix) owns LIBVA_DRIVER_NAME.
  environment.sessionVariables = lib.mkIf isIntelPrimary {
    LIBVA_DRIVER_NAME = "iHD";
  };
}
