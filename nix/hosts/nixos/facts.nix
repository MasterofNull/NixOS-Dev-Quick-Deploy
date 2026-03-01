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
    roles.virtualization.enable  = false;

    # AI stack configuration — consumed by nix/modules/roles/ai-stack.nix.
    # Only meaningful when roles.aiStack.enable = true.
    aiStack = {
      backend                          = "llamacpp";
      acceleration                     = "auto";
      llamaCpp.model                   = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      llamaCpp.huggingFaceRepo         = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
      llamaCpp.huggingFaceFile         = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      llamaCpp.sha256                  = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597";
      embeddingDimensions              = 2560;
      embeddingServer.enable           = true;
      embeddingServer.model            = "/var/lib/llama-cpp/models/Qwen3-Embedding-4B-q4_k_m.gguf";
      embeddingServer.huggingFaceRepo  = "Mungert/Qwen3-Embedding-4B-GGUF";
      embeddingServer.huggingFaceFile  = "Qwen3-Embedding-4B-q4_k_m.gguf";
      embeddingServer.sha256           = "2a91ec30c4c694af60cbedfc2f30d6aa5fd69a5286a8fb5544aa47868243054e";
      embeddingServer.pooling          = "last";
      embeddingServer.ctxSize          = 8192;
      ui.enable                        = true;
      vectorDb.enable                  = false;
      listenOnLan                      = false;
      rocmGfxOverride                  = null;
    };
  };
}
