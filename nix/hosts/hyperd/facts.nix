{...}: {
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
      btrfsSubvolumes = ["@root" "@home" "@nix"];
    };
    secureboot.enable = false;

    # ── AI Stack model configuration (Phase 20.2) ──────────────────────
    # Switch models by changing activeModel to any key from the catalog.
    # Available chat models: gemma4-e4b, gemma4-e2b, qwen3-4b, qwen3-8b, phi4-mini
    # Available embedding models: bge-m3, jina-v3, nomic-embed
    aiStack = {
      llamaCpp = {
        activeModel = "gemma4-e4b"; # Gemma 4 E4B Instruct — 4.5B active, 128K ctx
        trackLatest = true; # Track latest llama.cpp for Gemma 4 support
      };
      embeddingServer = {
        activeModel = "bge-m3"; # BGE-M3 — 1024-dim, best for RAG retrieval
      };
    };
  };
}
