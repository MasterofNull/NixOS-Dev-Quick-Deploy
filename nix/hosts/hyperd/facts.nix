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
      # Ready-to-toggle llama.cpp chat model stanzas for this host:
      #
      # Candidate A — current production baseline
      # llamaCpp.model           = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      # llamaCpp.huggingFaceRepo = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
      # llamaCpp.huggingFaceFile = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      # llamaCpp.sha256          = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597";
      #
      # Candidate B — same-size quality-per-byte upgrade target
      # llamaCpp.model           = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-IQ4_NL.gguf";
      # llamaCpp.huggingFaceRepo = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
      # llamaCpp.huggingFaceFile = "Qwen3-4B-Instruct-2507-IQ4_NL.gguf";
      # llamaCpp.sha256          = null; # fill after first verified download / benchmark pass
      #
      # Candidate C — same-size quality-first upgrade target
      # llamaCpp.model           = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q5_K_M.gguf";
      # llamaCpp.huggingFaceRepo = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
      # llamaCpp.huggingFaceFile = "Qwen3-4B-Instruct-2507-Q5_K_M.gguf";
      # llamaCpp.sha256          = null; # fill after first verified download / benchmark pass
      #
      # Candidate D — exact public 8B instruct source pinned for larger-model comparison
      # llamaCpp.model           = "/var/lib/llama-cpp/models/Qwen3-8B-Q4_K_M.gguf";
      # llamaCpp.huggingFaceRepo = "lm-kit/qwen-3-8b-instruct-gguf";
      # llamaCpp.huggingFaceFile = "Qwen3-8B-Q4_K_M.gguf";
      # llamaCpp.sha256          = null; # fill after staged download / verified benchmark pass
      #
      # 8B IQ4_NL remains intentionally unpinned here until a public instruct-labelled
      # GGUF source is resolved cleanly. Do not substitute a base-model GGUF silently.
      #
      # Toggle procedure:
      # 1. Replace the active llamaCpp.* lines below with one candidate block.
      # 2. Deploy.
      # 3. Run `aq-llama-benchmark.py --run-live ... --save-run` for the matching run_id.
      # 4. Backfill sha256 once the downloaded GGUF is accepted.
      llamaCpp.model           = "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      llamaCpp.huggingFaceRepo = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
      llamaCpp.huggingFaceFile = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
      llamaCpp.sha256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597";
      ui.enable          = true;
      vectorDb.enable    = false;
      listenOnLan        = false;
      rocmGfxOverride    = null;
      # Qwen3-Embedding-4B: decoder-based, last-token pooling, 2560-dim vectors.
      # ~2.5 GB RAM at Q4_K_M; supports 32K context (ctxSize 8192 for code chunks).
      # sha256 = null → first deploy downloads and prints hash; add it here afterwards.
      # MIGRATION: drop and recreate the AIDB document_embeddings table after deploy
      #   (dimension changed from 768 → 2560; existing vectors are incompatible).
      #   Run: sudo -u postgres psql -d aidb -c "DROP TABLE document_embeddings CASCADE;"
      #   Then: sudo systemctl restart ai-aidb.service  (recreates table at 2560 dims)
      embeddingDimensions = 2560;
      embeddingServer = {
        enable          = true;
        port            = 8081;
        model           = "/var/lib/llama-cpp/models/Qwen3-Embedding-4B-q4_k_m.gguf";
        huggingFaceRepo = "Mungert/Qwen3-Embedding-4B-GGUF";
        huggingFaceFile = "Qwen3-Embedding-4B-q4_k_m.gguf";
        sha256          = null; # add after first deploy: sha256sum /var/lib/llama-cpp/models/Qwen3-Embedding-4B-q4_k_m.gguf
        pooling         = "last";
        ctxSize         = 8192;
      };
      switchboard = {
        enable = true;
        routingMode = "auto";
        defaultProvider = "local";
      };
    };
  };
}
