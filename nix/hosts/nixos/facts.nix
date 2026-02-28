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
    #
    # ── Local model (single source of truth) ──────────────────────────────
    # To swap the chat model: update llamaCpp.model + huggingFaceFile (+ sha256
    # once known) and redeploy. The service will auto-download on first boot.
    # ── Embedding model ────────────────────────────────────────────────────
    # To swap the embedding model: update embeddingServer.model +
    # embeddingServer.huggingFaceFile and redeploy.
    aiStack = {
      backend            = "llamacpp";
      acceleration       = "auto";
      llamaCpp = {
        model            = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
        huggingFaceRepo  = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
        huggingFaceFile  = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
        # sha256 = ""; # populate after first download with: sha256sum /var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
      };
      embeddingServer = {
        model  = "/var/lib/llama-cpp/models/nomic-embed-text-v1.5.Q8_0.gguf";
        sha256 = null; # add after first deploy
      };
      ui.enable          = true;
      vectorDb.enable    = false;
      listenOnLan        = false;
      rocmGfxOverride    = null;
    };
  };
}
