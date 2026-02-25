{ ... }:
{
  mySystem = {
    hostName = "hyperd";
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
    secrets.enable = true;

    compliance.hospitalClassified = {
      enable = true;
    };

    # Role enables — profiles set desktop/gaming/aiStack via lib.mkDefault.
    # Override any of these in nix/hosts/<host>/default.nix with lib.mkForce.
    roles.aiStack.enable         = true;
    roles.server.enable          = false;
    roles.mobile.enable          = true;
    roles.virtualization.enable  = false;
    localhostIsolation.enable    = true;

    mcpServers = {
      enable   = true;
      repoPath = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy";
    };

    # AI stack configuration — consumed by nix/modules/roles/ai-stack.nix.
    # Only meaningful when roles.aiStack.enable = true.
    aiStack = {
      backend            = "llamacpp";
      acceleration       = "auto";
      llamaCpp.model           = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      llamaCpp.huggingFaceRepo = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
      llamaCpp.huggingFaceFile = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      llamaCpp.sha256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597";
      ui.enable          = true;
      vectorDb.enable    = false;
      listenOnLan        = false;
      rocmGfxOverride    = null;
      embeddingDimensions = 768;
      embeddingServer = {
        enable          = true;
        port            = 8081;
        model           = "/var/lib/llama-cpp/models/nomic-embed-text-v1.5.Q8_0.gguf";
        huggingFaceRepo = "nomic-ai/nomic-embed-text-v1.5-GGUF";
        huggingFaceFile = "nomic-embed-text-v1.5.Q8_0.gguf";
        sha256 = "3e24342164b3d94991ba9692fdc0dd08e3fd7362e0aacc396a9a5c54a544c3b7";
      };
      switchboard = {
        enable = true;
        routingMode = "auto";
        defaultProvider = "local";
      };
    };
  };
}
