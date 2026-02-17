{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  isAmd        = cfg.hardware.gpuVendor == "amd";
  isMobile     = cfg.hardware.isMobile;
  # Dual-AMD: APU + discrete AMD dGPU (e.g. Ryzen APU + RX 6700M on ASUS ROG G14).
  # igpuVendor = "amd" is set by hardware-detect.sh when two AMD PCI entries found.
  isDualAmd    = isAmd && cfg.hardware.igpuVendor == "amd";
  # Discrete AMD on a laptop (not APU-only): enable runtime PM.
  isMobileDiscreteAmd = isAmd && isMobile && isDualAmd;
  hasLact      = lib.versionAtLeast lib.version "26.05";
in
{
  # ---------------------------------------------------------------------------
  # AMD GPU: Mesa, Vulkan, VA-API, ROCm (gated on aiStack role), LACT.
  # ---------------------------------------------------------------------------

  hardware.graphics = lib.mkIf isAmd {
    enable      = lib.mkDefault true;
    enable32Bit = lib.mkDefault true;   # 32-bit games and Steam Proton

    # extraPackages are ADDITIONAL packages beyond the default Mesa install.
    # Do NOT add `mesa` here — NixOS includes it automatically.
    extraPackages = lib.mkAfter (
      # ROCm OpenCL: only installed when the AI stack role is active.
      # rocm-opencl-icd + rocm-opencl-runtime are several GB — do not pull them
      # for minimal or gaming profiles.
      lib.optionals cfg.roles.aiStack.enable (
        lib.optionals (pkgs ? rocm-opencl-icd)      [ pkgs.rocm-opencl-icd ]
        ++ lib.optionals (pkgs ? rocm-opencl-runtime) [ pkgs.rocm-opencl-runtime ]
      )
    );

    # 32-bit Mesa for Steam Proton / Wine. mesa here is the 32-bit variant.
    extraPackages32 = with pkgs.pkgsi686Linux; lib.mkAfter [ mesa ];
  };

  # Note: hardware.amdgpu.amdvlk was removed in newer NixOS releases.
  # RADV (Mesa Vulkan) is enabled by default and is the supported path.

  # amdgpu initrd: only load in initrd when earlyKmsPolicy = "force".
  # Default "auto" lets the driver initialise itself — correct for AMD APU.
  boot.initrd.kernelModules = lib.mkIf (isAmd && cfg.hardware.earlyKmsPolicy == "force")
    (lib.mkAfter [ "amdgpu" ]);

  boot.kernelParams = lib.mkIf isAmd (lib.mkAfter (
    [
      # GPU hang recovery: reset GPU on detected hang rather than requiring reboot.
      # Important for compute workloads (ROCm, Vulkan) and gaming sessions.
      "amdgpu.gpu_recovery=1"
    ]
    # Runtime power management for discrete AMD dGPU on laptops.
    # Allows the discrete GPU to enter low-power states when not rendering.
    # Only meaningful on dual-AMD systems (APU + dGPU); APU-only systems ignore it.
    ++ lib.optionals isMobileDiscreteAmd [
      "amdgpu.runpm=1"
    ]
  ));

  # VA-API: radeonsi is the Mesa-based VA-API backend for all AMD GPUs.
  environment.sessionVariables = lib.mkIf isAmd {
    LIBVA_DRIVER_NAME = "radeonsi";
    # On dual-AMD systems, DRI_PRIME=1 selects the discrete GPU.
    # Set it per-application rather than globally to preserve APU as default display.
  };

  # LACT: AMD GPU fan control, power limit, and OC daemon (26.05+ only).
  services.lact.enable = lib.mkIf (isAmd && hasLact) (lib.mkDefault true);
}
