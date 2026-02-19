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
        type = lib.types.enum [ "ollama" "k3s" ];
        default = "ollama";
        description = ''
          Inference backend.
          - ollama: native NixOS systemd services (services.ollama + open-webui + qdrant).
            Recommended for single-workstation AI development.
          - k3s: full Kubernetes-orchestrated stack (AIDB, hybrid-coordinator, ralph-wiggum).
            Only needed for multi-service production deployments.
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

      models = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ "qwen2.5-coder:7b" ];
        example = [ "qwen2.5-coder:7b" "phi3:mini" "deepseek-coder:6.7b" ];
        description = ''
          Ollama model tags to pull on first boot.
          Pulled by a oneshot systemd service after ollama starts.
          Idempotent: ollama pull is a no-op when the model is already present.
          See https://ollama.com/library for available tags.
        '';
      };

      ui = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable Open WebUI browser interface on port 3000. Connects to local ollama automatically.";
        };
      };

      llamaCpp = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = "Enable a native llama.cpp OpenAI-compatible server alongside Ollama.";
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
          Expose ollama (11434), Open WebUI (3000), and Qdrant (6333) on all
          network interfaces. Default: loopback-only (127.0.0.1).
          Only enable on a trusted local network.
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

      # ── K3s / Kubernetes options (backend = "k3s") ──────────────────────────
      modelProfile = lib.mkOption {
        type = lib.types.enum [ "auto" "small" "medium" "large" ];
        default = "auto";
        description = "Requested model profile tier for K3s AI stack defaults.";
      };

      embeddingModel = lib.mkOption {
        type = lib.types.str;
        default = "BAAI/bge-small-en-v1.5";
        description = "Default embedding model written into the AI stack env ConfigMap (k3s backend).";
      };

      llamaDefaultModel = lib.mkOption {
        type = lib.types.str;
        default = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF";
        description = "Default llama.cpp model identifier written into the AI stack env ConfigMap (k3s backend).";
      };

      llamaModelFile = lib.mkOption {
        type = lib.types.str;
        default = "qwen2.5-coder-7b-instruct-q4_k_m.gguf";
        description = "Default llama.cpp GGUF filename written into the AI stack env ConfigMap (k3s backend).";
      };

      namespace = lib.mkOption {
        type = lib.types.str;
        default = "ai-stack";
        description = "Kubernetes namespace containing the AI stack resources (k3s backend).";
      };

      manifestPath = lib.mkOption {
        type = lib.types.path;
        default = ../../.. + "/ai-stack/kubernetes";
        description = "Path to the AI stack Kubernetes kustomization directory (k3s backend).";
      };

      reconcileIntervalMinutes = lib.mkOption {
        type = lib.types.ints.positive;
        default = 15;
        description = "How often to re-run Kubernetes reconciliation for the AI stack manifests (k3s backend).";
      };

      kubectlTimeout = lib.mkOption {
        type = lib.types.str;
        default = "60s";
        description = "kubectl request timeout for API checks and apply operations (k3s backend).";
      };

      disableMarkerPath = lib.mkOption {
        type = lib.types.str;
        default = "/var/lib/nixos-quick-deploy/disable-ai-stack";
        description = "When this marker file exists, K3s manifest reconciliation is skipped (k3s backend).";
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
