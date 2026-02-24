{ ... }:
{
  mySystem = {
    hostName = "nixos";
    primaryUser = "hyperd";
    profile = "ai-dev";
    system = "x86_64-linux";
    hardware = {
      gpuVendor = "amd";
      igpuVendor = "none";
      cpuVendor = "amd";
      storageType = "nvme";
      systemRamGb = 27;
      isMobile = true;
      firmwareType = "efi";
      earlyKmsPolicy = "off";
      nixosHardwareModule = "lenovo-thinkpad-p14s-amd-gen2";
    };
    kernel = {
      track = "latest-stable";
    };
    deployment = {
      enableHibernation = false;
      swapSizeGb = 0;
      rootFsckMode = "check";
      initrdEmergencyAccess = true;
    };
    disk = {
      layout = "none";
      device = "/dev/disk/by-id/CHANGE-ME";
      luks.enable = false;
      btrfsSubvolumes = [ "@root" "@home" "@nix" ];
    };
    secureboot.enable = false;

    # Role enables — profiles set desktop/gaming/aiStack via lib.mkDefault.
    # Override any of these in nix/hosts/<host>/default.nix with lib.mkForce.
    roles.aiStack.enable         = true;
    roles.server.enable          = false;
    roles.mobile.enable          = true;
    roles.virtualization.enable  = true;
    localhostIsolation.enable    = true;

    # AI stack configuration — consumed by nix/modules/roles/ai-stack.nix.
    # Only meaningful when roles.aiStack.enable = true.
    aiStack = {
      backend            = "llamacpp";
      acceleration       = "auto";
      llamaCpp.model     = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      ui.enable          = true;
      vectorDb.enable       = true;
      embeddingServer.enable = true;
      listenOnLan           = false;
      rocmGfxOverride    = null;
    };
  };
}
