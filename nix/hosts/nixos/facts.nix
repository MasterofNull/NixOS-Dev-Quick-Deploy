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

    # AI stack configuration — consumed by nix/modules/roles/ai-stack.nix.
    # Only meaningful when roles.aiStack.enable = true.
    aiStack = {
      backend                          = "llamacpp";
      acceleration                     = "auto";
      # Qwen3.5-9B: 2.25x larger than Qwen3-4B with major agentic/tool-calling improvements
      # Q6_K quantization: ~7.5 GB model, leaves ~19 GB for context on 27 GB system
      llamaCpp.model                   = "/var/lib/llama-cpp/models/Qwen3.5-9B-Q6_K.gguf";
      llamaCpp.huggingFaceRepo         = "unsloth/Qwen3.5-9B-GGUF";
      llamaCpp.huggingFaceFile         = "Qwen3.5-9B-Q6_K.gguf";
      llamaCpp.sha256                  = "91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59";
      # Cezanne APU (Ryzen 5000U) uses gfx90c, which maps to ROCm gfx version 9.0.0
      rocmGfxOverride                  = "9.0.0";
      # llama.cpp extra args for stability and performance on AMD APU
      llamaCpp.extraArgs               = [
        # Disable auto memory fitting (crashes on APU with gfx900 override)
        "--fit" "off"
        # Prevent slot hangs: timeout after 120s
        "--timeout" "120"
        # Limit concurrent slots to prevent resource contention
        "--parallel" "2"
        # Optimize batch processing for interactive use
        "--batch-size" "512"
        "--ubatch-size" "64"
        # CPU threads: match physical cores for best latency
        "--threads" "8"
        "--threads-batch" "8"
        # Flash attention for faster prompt processing (ROCm)
        "--flash-attn" "on"
        # Memory mapping for faster model loading
        "--mlock"
        # Reasoning format for Qwen3-Instruct models
        "--reasoning-format" "deepseek"
      ];
      embeddingDimensions              = 2560;
      embeddingServer.enable           = true;
      embeddingServer.model            = "/var/lib/llama-cpp/models/Qwen3-Embedding-4B-q4_k_m.gguf";
      embeddingServer.huggingFaceRepo  = "Mungert/Qwen3-Embedding-4B-GGUF";
      embeddingServer.huggingFaceFile  = "Qwen3-Embedding-4B-q4_k_m.gguf";
      embeddingServer.sha256           = "2a91ec30c4c694af60cbedfc2f30d6aa5fd69a5286a8fb5544aa47868243054e";
      embeddingServer.pooling          = "last";
      embeddingServer.extraArgs        = [
        "--threads" "8"
        "--batch-size" "512"
        "--flash-attn" "on"
      ];
      ui.enable                        = true;
      vectorDb.enable                  = false;
      listenOnLan                      = false;
    };
  };
}
