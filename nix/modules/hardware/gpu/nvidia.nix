{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  isNvidia = cfg.hardware.gpuVendor == "nvidia";
  # Hybrid: Intel iGPU + Nvidia dGPU (Optimus). Enables PRIME render offload.
  # Bus IDs must still be set manually in local-overrides.nix for PRIME sync.
  isNvidiaHybrid = isNvidia && cfg.hardware.igpuVendor != "none";
in
{
  # NVIDIA GPU: proprietary driver, power management, NVENC/NVDEC.
  hardware.nvidia = lib.mkIf isNvidia {
    modesetting.enable = lib.mkDefault true;
    powerManagement.enable = lib.mkDefault true;
    # open=true requires Turing (RTX 20xx) or newer. Set true in local-overrides.nix
    # for Turing+ cards to use the open-source kernel module.
    open = lib.mkDefault false;
    nvidiaSettings = lib.mkDefault true;

    # PRIME render offload for hybrid systems (Intel iGPU + Nvidia dGPU).
    # offload.enable allows running specific apps on the Nvidia GPU while
    # the Intel iGPU handles the display server (saves battery).
    # To also use sync mode (lower latency), set prime.sync.enable = true
    # in local-overrides.nix and provide prime.intelBusId / prime.nvidiaBusId.
    prime.offload = lib.mkIf isNvidiaHybrid {
      enable = lib.mkDefault true;
      enableOffloadCmd = lib.mkDefault true;  # installs `nvidia-offload` helper
    };
  };

  services.xserver.videoDrivers = lib.mkIf isNvidia (lib.mkDefault [ "nvidia" ]);

  hardware.graphics = lib.mkIf isNvidia {
    enable = lib.mkDefault true;
    enable32Bit = lib.mkDefault true;
    extraPackages = lib.mkAfter (
      lib.optionals (pkgs ? nvidia-vaapi-driver) [ pkgs.nvidia-vaapi-driver ]
    );
  };

  environment.sessionVariables = lib.mkIf isNvidia {
    LIBVA_DRIVER_NAME = "nvidia";
    # Required for NVENC/NVDEC hardware video decode via nvidia-vaapi-driver
    NVD_BACKEND = "direct";
  };
}
