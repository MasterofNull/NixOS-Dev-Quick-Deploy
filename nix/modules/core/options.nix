{ lib, ... }:
{
  options.mySystem = {
    hostName = lib.mkOption {
      type = lib.types.str;
      default = "nixos";
      description = "Host name for this machine.";
    };

    primaryUser = lib.mkOption {
      type = lib.types.str;
      default = "nixos";
      description = "Primary local user name.";
    };

    sshAuthorizedKeys = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      example = [ "ssh-ed25519 AAAA... user@hostname" ];
      description = ''
        SSH public keys authorized for the primary user.
        Set in nix/hosts/<host>/default.nix so each machine declares its own
        keys without hard-coding them in shared modules.
      '';
    };

    system = lib.mkOption {
      type = lib.types.str;
      default = "x86_64-linux";
      description = "Target nix system architecture string.";
    };

    profile = lib.mkOption {
      type = lib.types.enum [ "ai-dev" "gaming" "minimal" ];
      default = "minimal";
      description = "Declarative system profile selector.";
    };

    hardware = {
      gpuVendor = lib.mkOption {
        type = lib.types.enum [
          # ── x86_64 ──────────────────────────────────────────────────────────
          "amd"           # AMD Radeon (RDNA/GCN) — Mesa radeonsi + LACT
          "intel"         # Intel HD/Iris/UHD (integrated, Gen 4–13+) — i915/xe
          "intel-arc"     # Intel Arc A/B-series discrete — xe driver
          "nvidia"        # NVIDIA GeForce/Quadro — proprietary driver
          # ── ARM / SoC ───────────────────────────────────────────────────────
          "adreno"        # Qualcomm Adreno — Mesa freedreno + Turnip Vulkan
          "mali"          # ARM Mali (Bifrost/Valhall) — Panfrost/Lima open-source
          "apple"         # Apple AGX (M-series) — Asahi Mesa honeykrisp/agx
          # ── Catch-all ───────────────────────────────────────────────────────
          "none"          # No discrete GPU / headless
        ];
        default = "none";
        description = ''
          Primary (discrete) GPU vendor.
          On hybrid systems this is the dGPU; the iGPU goes in igpuVendor.
          "apple" requires the Asahi Linux kernel and mesa-asahi-edge overlay.
          "mali" enables Panfrost (open) — proprietary Mali requires manual setup.
        '';
      };

      igpuVendor = lib.mkOption {
        type = lib.types.enum [
          "amd"     # AMD APU integrated GPU (e.g. Ryzen iGPU alongside Radeon dGPU)
          "intel"   # Intel iGPU alongside a discrete dGPU (Optimus, MUX)
          "apple"   # Apple AGX when used as iGPU on M-series with external GPU
          "none"    # No secondary iGPU (single-GPU or CPU-only)
        ];
        default = "none";
        description = ''
          Secondary integrated GPU vendor.
          Set when dGPU + iGPU coexist and need PRIME/hybrid graphics support.
          Leave "none" for single-GPU systems.
        '';
      };

      cpuVendor = lib.mkOption {
        type = lib.types.enum [
          # ── x86_64 ──────────────────────────────────────────────────────────
          "amd"        # AMD Ryzen/EPYC — AMD P-state, k10temp, schedutil
          "intel"      # Intel Core/Xeon — Intel P-state/EPP, thermald, powersave
          # ── AArch64 (ARM64) ─────────────────────────────────────────────────
          "arm"        # Generic ARM Cortex-A (Raspberry Pi, AllWinner, etc.)
          "qualcomm"   # Qualcomm Snapdragon — cpuidle, Adreno GPU, ACPI tables
          "apple"      # Apple M-series — Asahi Linux kernel, efficiency/perf cores
          # ── Other architectures ─────────────────────────────────────────────
          "riscv"      # RISC-V (SiFive, StarFive, AllWinner D1, etc.)
          # ── Fallback ────────────────────────────────────────────────────────
          "unknown"    # Undetected — safe no-op; extend discover-system-facts.sh
        ];
        default = "unknown";
        description = ''
          Detected CPU / SoC vendor.
          Set automatically by scripts/discover-system-facts.sh.
          Override in nix/hosts/<host>/facts.nix if auto-detection is wrong.
        '';
      };

      storageType = lib.mkOption {
        type = lib.types.enum [ "nvme" "ssd" "hdd" ];
        default = "ssd";
        description = "Primary storage device type. Controls I/O scheduler, fstrim, and power tuning.";
      };

      systemRamGb = lib.mkOption {
        type = lib.types.int;
        default = 8;
        description = "Total installed RAM in GB. Used for adaptive zswap pool sizing and Nix build parallelism.";
      };

      isMobile = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "True for laptops/mobile workstations. Enables power profiles, lid handling, and battery tuning.";
      };

      firmwareType = lib.mkOption {
        type = lib.types.enum [ "efi" "bios" "unknown" ];
        default = "unknown";
        description = "Detected firmware boot mode. Used for bootloader defaults.";
      };

      earlyKmsPolicy = lib.mkOption {
        type = lib.types.enum [ "auto" "force" "off" ];
        default = "off";
        description = "Early kernel modesetting: auto = driver default, force = add GPU module to initrd, off = disable.";
      };

      nixosHardwareModule = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "nixos-hardware module name (e.g. 'lenovo-thinkpad-p14s-amd-gen2') or null to skip.";
      };
    };

    kernel = {
      track = lib.mkOption {
        type = lib.types.enum [ "latest-stable" "default" ];
        default = "latest-stable";
        description = ''
          Kernel package selection policy.
          - latest-stable: use pkgs.linuxPackages_latest when available.
          - default: use pkgs.linuxPackages (board/vendor defaults).
          This is generated from local hardware facts during deployment.
        '';
      };
    };

    deployment = {
      enableHibernation = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable swap-backed hibernation. Requires swapSizeGb >= systemRamGb.";
      };

      swapSizeGb = lib.mkOption {
        type = lib.types.int;
        default = 0;
        description = "Hibernation swap size in GB. 0 inherits from hardware-configuration.nix.";
      };

      rootFsckMode = lib.mkOption {
        type = lib.types.enum [ "check" "skip" ];
        default = "check";
        description = "Root filesystem fsck policy in initrd. Use 'skip' only as temporary recovery mode.";
      };

      initrdEmergencyAccess = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Allow initrd emergency shell access for local recovery when boot dependencies fail.";
      };

      tmpUseTmpfs = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Mount /tmp as tmpfs for faster temporary I/O.";
      };

      nixBinaryCaches = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [
          "https://cache.nixos.org"
          "https://nix-community.cachix.org"
          "https://devenv.cachix.org"
        ];
        description = "Binary cache substituter URLs. Extend in facts.nix for private caches.";
      };

      fsIntegrityMonitor = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable post-boot filesystem integrity monitoring (journal signature scan + timer).";
        };

        intervalMinutes = lib.mkOption {
          type = lib.types.ints.positive;
          default = 60;
          description = "How often to rerun the filesystem integrity monitor timer.";
        };
      };

      diskHealthMonitor = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable periodic SMART/NVMe health checks for the root disk.";
        };

        intervalMinutes = lib.mkOption {
          type = lib.types.ints.positive;
          default = 180;
          description = "How often to rerun the disk health monitor timer.";
        };
      };

      bootloaderEspMinFreeMb = lib.mkOption {
        type = lib.types.ints.positive;
        default = 128;
        description = "Minimum free space required on the EFI System Partition before deploy proceeds.";
      };
    };

    logging = {
      audit = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable Linux audit subsystem (auditd) for host audit trails.";
        };

        watchPaths = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [
            "/var/lib/aidb"
            "/var/lib/postgresql"
            "/var/lib/redis"
            "/srv/patient-data"
          ];
          example = [ "/srv/patient-data" "/var/lib/aidb" ];
          description = ''
            Filesystem paths to watch with auditd.
            Each path is tracked with read/write/execute/attribute access and
            tagged with mySystem.logging.audit.key.
          '';
        };

        key = lib.mkOption {
          type = lib.types.str;
          default = "patient-data-access";
          description = "Audit key used for watched patient-data paths.";
        };

        immutableRules = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Lock audit rules after boot (`-e 2`) so runtime tampering requires
            a reboot to change policy.
          '';
        };
      };

      remoteSyslog = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = "Forward logs to a remote syslog collector.";
        };

        host = lib.mkOption {
          type = lib.types.str;
          default = "";
          example = "10.42.0.20";
          description = "Remote syslog collector host or IP.";
        };

        port = lib.mkOption {
          type = lib.types.port;
          default = 6514;
          description = "Remote syslog collector port.";
        };

        protocol = lib.mkOption {
          type = lib.types.enum [ "tcp" "udp" ];
          default = "tcp";
          description = "Transport protocol used for remote syslog forwarding.";
        };
      };
    };

    disk = {
      layout = lib.mkOption {
        type = lib.types.enum [ "none" "gpt-efi-ext4" "gpt-efi-btrfs" "gpt-luks-ext4" ];
        default = "none";
        description = "Declarative disk layout selector for disko-backed provisioning.";
      };

      device = lib.mkOption {
        type = lib.types.str;
        default = "/dev/disk/by-id/CHANGE-ME";
        description = "Primary disk device for disko layouts.";
      };

      luks.enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable LUKS encryption for supported disk layouts.";
      };

      btrfsSubvolumes = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ "@root" "@home" "@nix" ];
        description = "Btrfs subvolumes to materialize for btrfs layouts.";
      };
    };

    secureboot.enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable secure boot integration (lanzaboote) when available.";
    };

    secrets = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable declarative sops-nix secret decryption into /run/secrets.";
      };

      sopsFile = lib.mkOption {
        type = lib.types.str;
        default = "/etc/nixos/secrets/secrets.sops.yaml";
        description = "Absolute path to the SOPS-encrypted secrets file.";
      };

      allowRepoLocalSopsFile = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Allow using a repo-local SOPS file path (for example nix/hosts/<host>/secrets.sops.yaml).
          Keep this false for strict zero-secrets-in-repo operation.
        '';
      };

      ageKeyFile = lib.mkOption {
        type = lib.types.str;
        default = "/var/lib/sops-nix/key.txt";
        description = "Path to the AGE private key used by sops-nix at activation time.";
      };

      names = {
        aidbApiKey = lib.mkOption {
          type = lib.types.str;
          default = "aidb_api_key";
          description = "SOPS key name for AIDB API auth secret.";
        };

        hybridApiKey = lib.mkOption {
          type = lib.types.str;
          default = "hybrid_coordinator_api_key";
          description = "SOPS key name for Hybrid Coordinator API auth secret.";
        };

        embeddingsApiKey = lib.mkOption {
          type = lib.types.str;
          default = "embeddings_api_key";
          description = "SOPS key name for embeddings API auth secret.";
        };

        postgresPassword = lib.mkOption {
          type = lib.types.str;
          default = "postgres_password";
          description = "SOPS key name for PostgreSQL password secret.";
        };

        redisPassword = lib.mkOption {
          type = lib.types.str;
          default = "redis_password";
          description = "SOPS key name for Redis password secret.";
        };
      };
    };

    # ---------------------------------------------------------------------------
    # Orthogonal role toggles — composable across any profile.
    # Profile (ai-dev/gaming/minimal) selects the primary package set.
    # Roles layer additional capabilities on top without creating profile explosion.
    # ---------------------------------------------------------------------------
    roles = {
      aiStack.enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Layer AI/ML inference and local LLM tooling onto any profile.";
      };

      gaming.enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Layer gaming stack (Steam, Wine, Gamemode, MangoHud) onto any profile.";
      };

      mobile.enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Layer laptop/mobile power management. Auto-set from hardware.isMobile; override here if needed.";
      };

      server.enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Layer server hardening and headless optimisations (no DM, trim GUI services).";
      };

      desktop.enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Layer desktop/workstation defaults (display manager, audio, Bluetooth, XDG portals).";
      };

      virtualization.enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Layer KVM/QEMU virtualization (libvirtd, virt-manager, OVMF UEFI firmware).";
      };
    };

    # ---------------------------------------------------------------------------
    # AI stack configuration — consumed by nix/modules/roles/ai-stack.nix.
    # These options are only active when roles.aiStack.enable = true.
    # ---------------------------------------------------------------------------
    aiStack = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Enable declarative AI stack runtime services when the aiStack role is active.";
      };

      backend = lib.mkOption {
        type = lib.types.enum [ "llamacpp" ];
        default = "llamacpp";
        description = ''
          Inference backend.
          - llamacpp: native llama.cpp server (OpenAI-compatible API on :8080).
            Default for single-workstation AI development; no daemon overhead.
        '';
      };

      acceleration = lib.mkOption {
        type = lib.types.enum [ "auto" "rocm" "cuda" "cpu" ];
        default = "auto";
        description = ''
          GPU acceleration for inference.
          "auto" derives from hardware.gpuVendor: amd→rocm, nvidia→cuda, else→cpu.
          Override only when auto detection is incorrect for your hardware.
        '';
      };


      ui = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable Open WebUI browser interface on port 3000. Connects to the local inference server.";
        };
      };

      # Deprecated compatibility shim for pre-llamaCpp deploy options.
      # Legacy files may still set `mySystem.aiStack.models = [ "model:tag" ]`.
      # The native llama.cpp path now uses `mySystem.aiStack.llamaCpp.model`.
      models = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        description = "DEPRECATED: legacy Ollama-era model tags. Ignored by the llama.cpp backend.";
      };

      llamaCpp = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable native llama.cpp OpenAI-compatible inference server on port 8080.";
        };

        host = lib.mkOption {
          type = lib.types.str;
          default = "127.0.0.1";
          description = "Bind address for llama.cpp server.";
        };

        port = lib.mkOption {
          type = lib.types.port;
          default = 8080;
          description = "TCP port for llama.cpp server.";
        };

        model = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/llama-cpp/models/model.gguf";
          description = "Path to the GGUF model file loaded by llama.cpp.";
        };

        extraArgs = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [ ];
          description = "Additional CLI flags passed to llama-server.";
        };

        huggingFaceRepo = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "unsloth/Qwen3-4B-Instruct-2507-GGUF";
          description = ''
            HuggingFace repo (org/name) from which to download the model GGUF
            on first boot if the file at `model` is absent.
            null = disable automatic download (model must be placed manually).
          '';
        };

        huggingFaceFile = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
          description = ''
            Filename within the HuggingFace repo to download.
            Defaults to the basename of `model` when null.
          '';
        };

        sha256 = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "5b3e7f...";
          description = "Required SHA256 (hex) for downloaded chat GGUF model when huggingFaceRepo is set.";
        };
      };

      embeddingServer = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = ''
            Enable a dedicated llama.cpp embedding server on a separate port.
            Serves /v1/embeddings for RAG ingestion (Qdrant) and Open WebUI.
            Runs independently from the chat inference server.
          '';
        };

        port = lib.mkOption {
          type = lib.types.port;
          default = 8081;
          description = "TCP port for the embedding llama.cpp instance.";
        };

        model = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/llama-cpp/models/embed.gguf";
          description = "Path to the GGUF embedding model file (e.g. nomic-embed-text, bge-small-en).";
        };

        huggingFaceRepo = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "nomic-ai/nomic-embed-text-v1.5-GGUF";
          description = "HuggingFace repo for auto-download of the embedding model on first boot.";
        };

        huggingFaceFile = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "nomic-embed-text-v1.5.Q8_0.gguf";
          description = "Filename within the HuggingFace repo. Defaults to basename of model when null.";
        };

        sha256 = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "c2f9a1...";
          description = "Required SHA256 (hex) for downloaded embedding GGUF model when huggingFaceRepo is set.";
        };

        extraArgs = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [ ];
          description = "Additional CLI flags for the embedding llama-server instance.";
        };
      };

      embeddingDimensions = lib.mkOption {
        type = lib.types.ints.positive;
        default = 768;
        description = ''
          Embedding vector dimension used by the active embedding model.
          Keep this aligned with the embedding model served on
          mySystem.aiStack.embeddingServer.port.
        '';
      };

      vectorDb = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = "Enable Qdrant vector database on port 6333. Required for RAG workflows and the AIDB embeddings service.";
        };
      };

      listenOnLan = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Expose inference servers and Open WebUI on all network interfaces.
          Default: loopback-only (127.0.0.1). Only enable on a trusted LAN.
        '';
      };

      rocmGfxOverride = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "11.0.0";
        description = ''
          ROCm GFX architecture version override (e.g. "11.0.0" for RDNA3).
          Required for AMD GPUs not yet in the official ROCm support matrix.
          null = let ROCm auto-detect (correct for most supported GPUs).
        '';
      };

      # ── Switchboard: local/remote LLM routing proxy ─────────────────────────
      switchboard = {
        enable = lib.mkOption {
          type    = lib.types.bool;
          default = false;
          description = "Enable AI Switchboard OpenAI-compatible proxy on port 8085 for local/remote LLM routing.";
        };
        port = lib.mkOption {
          type    = lib.types.port;
          default = 8085;
          description = "TCP port for the AI Switchboard proxy.";
        };

        routingMode = lib.mkOption {
          type = lib.types.enum [ "auto" "local_only" "remote_only" ];
          default = "auto";
          description = ''
            Switchboard routing strategy.
            auto: route by request hints/model prefix;
            local_only: always use local llama.cpp;
            remote_only: always use configured remote endpoint.
          '';
        };

        defaultProvider = lib.mkOption {
          type = lib.types.enum [ "local" "remote" ];
          default = "local";
          description = "Default provider used in auto mode when no explicit route hint is present.";
        };

        remoteUrl = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "https://openrouter.ai/api";
          description = ''
            OpenAI-compatible remote endpoint base URL.
            Expected form: https://host[/api] (without /v1 suffix is preferred).
          '';
        };

        remoteApiKeyFile = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "/run/secrets/remote_llm_api_key";
          description = "Path to remote LLM API key file for switchboard upstream authentication.";
        };
      };

      # ── AI harness architecture (memory + eval + tree-search retrieval) ─────
      aiHarness = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable harness-engineering runtime features for the AI stack.";
        };

        memory = {
          enable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Enable tiered agent memory (episodic, semantic, procedural).";
          };

          maxRecallItems = lib.mkOption {
            type = lib.types.ints.positive;
            default = 8;
            description = "Maximum memory entries returned per recall request.";
          };
        };

        retrieval = {
          treeSearchEnable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Enable tree-search retrieval expansion in hybrid coordinator.";
          };

          treeSearchMaxDepth = lib.mkOption {
            type = lib.types.ints.positive;
            default = 2;
            description = "Maximum tree-search depth for retrieval branching.";
          };

          treeSearchBranchFactor = lib.mkOption {
            type = lib.types.ints.positive;
            default = 3;
            description = "Maximum branches evaluated per tree-search depth level.";
          };
        };

        eval = {
          enable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Enable harness evaluation endpoints and scorecards.";
          };

          minAcceptanceScore = lib.mkOption {
            type = lib.types.float;
            default = 0.7;
            description = "Minimum overall harness score required to pass.";
          };

          maxLatencyMs = lib.mkOption {
            type = lib.types.ints.positive;
            default = 3000;
            description = "Default latency SLO target (ms) for harness evaluations.";
          };
        };
      };
    };

    # ---------------------------------------------------------------------------
    # Monitoring stack (Prometheus + Node Exporter).
    # Replaces ad-hoc dashboard collector parsing with stable metrics endpoints.
    # ---------------------------------------------------------------------------
    monitoring = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Enable declarative Prometheus + node_exporter system monitoring.";
      };

      listenOnLan = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Expose Prometheus and node_exporter ports on LAN.";
      };

      prometheusPort = lib.mkOption {
        type = lib.types.port;
        default = 9090;
        description = "Prometheus HTTP listen port.";
      };

      nodeExporterPort = lib.mkOption {
        type = lib.types.port;
        default = 9100;
        description = "node_exporter listen port.";
      };

      commandCenter = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable declarative command-center dashboard services and collectors.";
        };

        bindAddress = lib.mkOption {
          type = lib.types.str;
          default = "127.0.0.1";
          description = "Bind address for command-center frontend and API.";
        };

        frontendPort = lib.mkOption {
          type = lib.types.port;
          default = 8888;
          description = "Command-center dashboard frontend port.";
        };

        apiPort = lib.mkOption {
          type = lib.types.port;
          default = 8889;
          description = "Command-center dashboard API backend port.";
        };

        dataDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/nixos-system-dashboard";
          description = "Persistent command-center dashboard data directory.";
        };

        collectorLiteIntervalSeconds = lib.mkOption {
          type = lib.types.ints.positive;
          default = 5;
          description = "Fast collector interval (seconds) for system/network metrics.";
        };

        collectorFullIntervalSeconds = lib.mkOption {
          type = lib.types.ints.positive;
          default = 60;
          description = "Full collector interval (seconds) for deeper stack metrics.";
        };
      };
    };


    # ---------------------------------------------------------------------------
    # Central host-mode port registry.
    # Single source of truth for localhost service bindings.
    # ---------------------------------------------------------------------------
    ports = {
      llamaCpp = lib.mkOption {
        type = lib.types.port;
        default = 8080;
        description = "llama.cpp inference HTTP port.";
      };

      embedding = lib.mkOption {
        type = lib.types.port;
        default = 8081;
        description = "llama.cpp embedding HTTP port.";
      };

      qdrantHttp = lib.mkOption {
        type = lib.types.port;
        default = 6333;
        description = "Qdrant HTTP API port.";
      };

      qdrantGrpc = lib.mkOption {
        type = lib.types.port;
        default = 6334;
        description = "Qdrant gRPC API port.";
      };

      postgres = lib.mkOption {
        type = lib.types.port;
        default = 5432;
        description = "PostgreSQL TCP port.";
      };

      redis = lib.mkOption {
        type = lib.types.port;
        default = 6379;
        description = "Redis TCP port.";
      };

      mcpAidb = lib.mkOption {
        type = lib.types.port;
        default = 8002;
        description = "AIDB MCP HTTP port.";
      };

      mcpHybrid = lib.mkOption {
        type = lib.types.port;
        default = 8003;
        description = "Hybrid coordinator MCP HTTP port.";
      };

      mcpRalph = lib.mkOption {
        type = lib.types.port;
        default = 8004;
        description = "Ralph orchestrator MCP HTTP port.";
      };

      switchboard = lib.mkOption {
        type = lib.types.port;
        default = 8085;
        description = "AI switchboard proxy port.";
      };

      prometheus = lib.mkOption {
        type = lib.types.port;
        default = 9090;
        description = "Prometheus HTTP port.";
      };

      nodeExporter = lib.mkOption {
        type = lib.types.port;
        default = 9100;
        description = "Node exporter HTTP port.";
      };

      commandCenterFrontend = lib.mkOption {
        type = lib.types.port;
        default = 8888;
        description = "Command-center frontend port.";
      };

      commandCenterApi = lib.mkOption {
        type = lib.types.port;
        default = 8889;
        description = "Command-center API port.";
      };

      otlpGrpc = lib.mkOption {
        type = lib.types.port;
        default = 4317;
        description = "OpenTelemetry OTLP gRPC receiver port.";
      };

      otlpHttp = lib.mkOption {
        type = lib.types.port;
        default = 4318;
        description = "OpenTelemetry OTLP HTTP receiver port.";
      };

      otelCollectorMetrics = lib.mkOption {
        type = lib.types.port;
        default = 9464;
        description = "OpenTelemetry collector internal Prometheus telemetry port.";
      };
    };

    localhostIsolation = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable nftables localhost service-segmentation for internal AI/data ports.";
      };

      allowedServiceGids = lib.mkOption {
        type = lib.types.listOf lib.types.int;
        default = [ 0 35010 35011 35012 ];
        description = "Allowed Linux GIDs for loopback access to restricted internal service ports.";
      };
    };
    # MCP (Model Context Protocol) server configuration.
    # Declarative systemd services for the local AI stack MCP tier.
    # These are only active when roles.aiStack.enable = true and
    # aiStack.backend = "llamacpp" (K3s backend uses Kubernetes for MCP).
    # ---------------------------------------------------------------------------
    mcpServers = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Enable declarative MCP server services (embeddings, aidb,
          hybrid-coordinator, ralph-wiggum) as native NixOS systemd units.
          Requires roles.aiStack.enable = true and backend = "llamacpp".
        '';
      };
      repoPath = lib.mkOption {
        type = lib.types.str;
        default = "/opt/nixos-quick-deploy";
        description = ''
          Absolute path to the NixOS-Dev-Quick-Deploy repository root on the
          deployed system. MCP server Python source is read from
          <repoPath>/ai-stack/mcp-servers/.
        '';
      };

      dataDir = lib.mkOption {
        type = lib.types.str;
        default = "/var/lib/ai-stack";
        description = "Persistent state directory for all MCP services.";
      };

      embeddingModel = lib.mkOption {
        type = lib.types.str;
        default = "BAAI/bge-small-en-v1.5";
        description = "HuggingFace model ID for the local embeddings service.";
      };

      embeddingsPort = lib.mkOption {
        type = lib.types.port;
        default = 8001;
        description = "TCP port for the embeddings HTTP service.";
      };

      aidbPort = lib.mkOption {
        type = lib.types.port;
        default = 8002;
        description = "TCP port for the AIDB MCP server HTTP endpoint.";
      };

      hybridPort = lib.mkOption {
        type = lib.types.port;
        default = 8003;
        description = "TCP port for the hybrid-coordinator MCP server.";
      };

      ralphPort = lib.mkOption {
        type = lib.types.port;
        default = 8004;
        description = "TCP port for the ralph-wiggum loop MCP server.";
      };

      postgres = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable PostgreSQL for AIDB telemetry and tool-discovery persistence.";
        };

        database = lib.mkOption {
          type = lib.types.str;
          default = "aidb";
          description = "PostgreSQL database name for the AI stack.";
        };

        user = lib.mkOption {
          type = lib.types.str;
          default = "aidb";
          description = "PostgreSQL user for the AI stack.";
        };
      };

      redis = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable Redis cache service for MCP stack.";
        };

        port = lib.mkOption {
          type = lib.types.port;
          default = 6379;
          description = "Redis TCP port for MCP services.";
        };

        bind = lib.mkOption {
          type = lib.types.str;
          default = "127.0.0.1";
          description = "Redis bind address.";
        };

        maxmemory = lib.mkOption {
          type = lib.types.str;
          default = "512mb";
          description = "Redis maxmemory setting.";
        };

        maxmemoryPolicy = lib.mkOption {
          type = lib.types.str;
          default = "allkeys-lru";
          description = "Redis maxmemory-policy setting.";
        };
      };
    };

    profileData = {
      flatpakApps = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        description = "Profile-scoped Flatpak app identifiers.";
      };

      systemPackageNames = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        description = "Profile-scoped system package names merged with base packages and deduplicated.";
      };
    };
  };
}
