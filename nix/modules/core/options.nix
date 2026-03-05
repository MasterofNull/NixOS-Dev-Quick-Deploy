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

    hardwareTier = lib.mkOption {
      type = lib.types.enum [ "nano" "micro" "small" "medium" "large" ];
      readOnly = true;
      description = ''
        Derived hardware capability tier used by validation and policy gates.
        Computed by nix/lib/hardware-tier.nix from declared host hardware facts.
        nano   — < 2 GB RAM   (SBC / embedded)
        micro  — 2-7 GB RAM   (Raspberry Pi / light SBC)
        small  — 8-15 GB RAM  (laptop / thin client)
        medium — 16-31 GB RAM (workstation)
        large  — ≥ 32 GB RAM  (high-end workstation / server)
        A discrete GPU bumps the tier one level up.
      '';
    };

    nixpkgsTrack = lib.mkOption {
      type = lib.types.enum [ "stable" "unstable" ];
      default = "stable";
      description = ''
        Nixpkgs channel track for this host.
        - stable: use flake input nixpkgs (default, pinned to 25.11)
        - unstable: use flake input nixpkgs-unstable when available
      '';
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
          Set automatically by scripts/governance/discover-system-facts.sh.
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

      mutableSpaces = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Enable declarative mutable writable roots for user and program state.
            Paths are provisioned via systemd-tmpfiles so they remain mutable
            across rebuilds while all policy lives in Nix options.
          '';
        };

        aiStackStateDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/nixos-ai-stack";
          description = ''
            Base mutable state directory for AI stack runtime metadata and
            declarative helper artifacts (optimizer overrides, integrity baseline).
          '';
        };

        aiStackOptimizerDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/nixos-ai-stack/optimizer";
          description = ''
            Mutable optimizer directory (for PRSI optimizer state and
            switchboard/hybrid runtime override environment files).
          '';
        };

        aiStackLogDir = lib.mkOption {
          type = lib.types.str;
          default = "/var/log/nixos-ai-stack";
          description = ''
            Mutable AI stack operational log directory used by optimization and
            gap-closure loops.
          '';
        };

        userWritablePaths = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [
            "/var/lib/nixos-ai-stack/mutable/user"
          ];
          description = ''
            Writable roots owned by the primary user for user-level mutable data.
            Keep paths absolute and outside the Nix store.
          '';
        };

        programWritablePaths = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [
            "/var/lib/nixos-ai-stack/mutable/program"
            "/var/lib/nixos-ai-stack"
            "/var/lib/nixos-ai-stack/optimizer"
            "/var/log/nixos-ai-stack"
          ];
          description = ''
            Writable roots used by managed services/programs for mutable state.
            These paths are also used by service hardening allowlists.
          '';
        };
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

      nixTrustedPublicKeys = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [
          "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
          "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs="
          "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw="
        ];
        description = ''
          Trusted public keys for configured Nix binary caches.
          Keep this list aligned with deployment.nixBinaryCaches.
        '';
      };

      nixAllowedUris = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [
          "file:"
          "git+file:"
          "https://cache.nixos.org/"
          "https://nix-community.cachix.org/"
          "https://devenv.cachix.org/"
          "https://github.com/"
          "https://gitlab.com/"
          "https://huggingface.co/"
          "https://pypi.org/"
          "https://files.pythonhosted.org/"
          "https://registry.npmjs.org/"
          "https://crates.io/"
          "https://static.crates.io/"
        ];
        description = ''
          Allowlist of URIs Nix evaluation is allowed to fetch from.
          Applied when mySystem.roles.aiStack.enable = true.
        '';
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

      securityAuditHighCvssThreshold = lib.mkOption {
        type = lib.types.number;
        default = 7.0;
        description = ''
          CVSS score threshold for high-severity vulnerability alerts.
          Used by the weekly security audit timer (Phase 11.5).
          Vulnerabilities with CVSS >= this value trigger desktop notifications.
        '';
      };

      npmSecurity = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Enable periodic npm supply-chain monitoring (audit + lockfile hygiene
            + lifecycle script risk checks + npm config posture).
          '';
        };

        intervalMinutes = lib.mkOption {
          type = lib.types.ints.positive;
          default = 360;
          description = "How often to run npm supply-chain monitoring.";
        };

        failOnHigh = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = ''
            When true, npm monitor exits non-zero on high/critical findings so
            systemd marks the run failed for stronger operator visibility.
          '';
        };

        responseMode = lib.mkOption {
          type = lib.types.enum [ "report" "fail" "quarantine" ];
          default = "report";
          description = ''
            Threat response mode when npm high/critical findings are detected:
            `report` writes findings only, `fail` marks service failed, and
            `quarantine` writes an active quarantine state artifact and fails.
            `failOnHigh` remains supported as a compatibility override.
          '';
        };

        suspiciousLogLookbackHours = lib.mkOption {
          type = lib.types.ints.positive;
          default = 24;
          description = "How far back npm log files are scanned for suspicious install patterns.";
        };

        threatIntelFile = lib.mkOption {
          type = lib.types.str;
          default = "config/security/npm-threat-intel.json";
          description = ''
            Path to npm threat-intel IOC file (known malicious package names,
            typosquat regexes, suspicious lifecycle script signatures).
          '';
        };

        quarantineStateFile = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/ai-stack/security/npm/quarantine-state.json";
          description = ''
            Path for current npm quarantine state. Used by agents/scripts to
            gate operations when responseMode=`quarantine` is active.
          '';
        };

        incidentLogFile = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/ai-stack/security/npm/incidents.jsonl";
          description = ''
            JSONL incident ledger for npm threat events and resolution records.
          '';
        };
      };

      autoRemediation = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Enable post-deploy aq-report driven auto-remediation for safe actions:
            intent-contract coverage probes and stale query-gap curation.
          '';
        };

        dryRun = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = "When true, computes remediation actions without mutating workflow sessions or query_gaps.";
        };

        reportSince = lib.mkOption {
          type = lib.types.str;
          default = "7d";
          description = "aq-report lookback window used when a cached report snapshot is unavailable.";
        };

        intentMinRuns = lib.mkOption {
          type = lib.types.ints.positive;
          default = 3;
          description = "Minimum workflow run count before intent-contract auto-remediation is considered.";
        };

        intentMinCoveragePct = lib.mkOption {
          type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 100.0);
          default = 90.0;
          description = "Trigger threshold for low intent-contract coverage.";
        };

        intentTargetCoveragePct = lib.mkOption {
          type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 99.0);
          default = 95.0;
          description = "Target coverage used to size bounded synthetic remediation probes.";
        };

        intentMaxProbeRuns = lib.mkOption {
          type = lib.types.ints.positive;
          default = 3;
          description = "Maximum synthetic workflow probe runs per convergence cycle.";
        };

        intentBoundedEnable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Enable bounded iterative intent-contract remediation loop during
            post-deploy convergence.
          '';
        };

        intentBoundedTargetCoveragePct = lib.mkOption {
          type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 100.0);
          default = 65.0;
          description = "Target intent-contract coverage for bounded remediation loop.";
        };

        intentBoundedRunsPerPass = lib.mkOption {
          type = lib.types.ints.positive;
          default = 8;
          description = "Maximum remediation runs started per bounded intent pass.";
        };

        intentBoundedMaxTotalRuns = lib.mkOption {
          type = lib.types.ints.positive;
          default = 24;
          description = "Total run budget for bounded intent remediation per convergence cycle.";
        };

        intentBoundedMaxPasses = lib.mkOption {
          type = lib.types.ints.positive;
          default = 4;
          description = "Maximum bounded intent remediation passes per convergence cycle.";
        };

        intentBoundedSleepSeconds = lib.mkOption {
          type = lib.types.ints.positive;
          default = 2;
          description = "Sleep delay between bounded intent remediation passes.";
        };

        intentBoundedTimeoutSeconds = lib.mkOption {
          type = lib.types.ints.positive;
          default = 180;
          description = "Timeout budget for bounded intent remediation execution.";
        };

        hintBoundedEnable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Enable bounded hint-adoption remediation loop during post-deploy
            convergence.
          '';
        };

        hintBoundedTargetAdoptionPct = lib.mkOption {
          type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 100.0);
          default = 70.0;
          description = "Target hint adoption success rate for bounded remediation loop.";
        };

        hintBoundedRunsPerPass = lib.mkOption {
          type = lib.types.ints.positive;
          default = 3;
          description = "Maximum hinted tasks submitted per bounded hint remediation pass.";
        };

        hintBoundedMaxTotalRuns = lib.mkOption {
          type = lib.types.ints.positive;
          default = 9;
          description = "Total hinted-task budget per bounded hint remediation cycle.";
        };

        hintBoundedMaxPasses = lib.mkOption {
          type = lib.types.ints.positive;
          default = 5;
          description = "Maximum bounded hint remediation passes per convergence cycle.";
        };

        hintBoundedPollMaxSeconds = lib.mkOption {
          type = lib.types.ints.positive;
          default = 90;
          description = "Maximum per-task status polling time for hint remediation runs.";
        };

        hintBoundedSleepSeconds = lib.mkOption {
          type = lib.types.ints.positive;
          default = 2;
          description = "Sleep delay between bounded hint remediation passes.";
        };

        hintBoundedTimeoutSeconds = lib.mkOption {
          type = lib.types.ints.positive;
          default = 420;
          description = "Timeout budget for bounded hint remediation execution.";
        };

        hintBoundedWorkspace = lib.mkOption {
          type = lib.types.str;
          default = "/var/lib/ai-stack/hybrid/remediation";
          description = ''
            Writable workspace used for bounded hint-remediation mutation probes.
            Should remain under mutable AI stack data paths.
          '';
        };

        hintBoundedFile = lib.mkOption {
          type = lib.types.str;
          default = "hint-remediation/notes.md";
          description = "Relative file path used by bounded hint-remediation probes.";
        };

        staleGapCurationEnable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Enable stale query gap curation by applying safe DELETE actions inferred
            from aq-report recommendation strings that already include stale-gap SQL guidance.
          '';
        };

        staleGapMinTokenLen = lib.mkOption {
          type = lib.types.ints.positive;
          default = 12;
          description = "Minimum token length extracted from stale-gap recommendations before deletion is allowed.";
        };

        staleGapMaxRowsPerToken = lib.mkOption {
          type = lib.types.ints.positive;
          default = 250;
          description = "Safety cap for rows deleted per stale-gap token in one cycle.";
        };

        staleGapMaxDeleteTotal = lib.mkOption {
          type = lib.types.ints.positive;
          default = 500;
          description = "Safety cap for total stale-gap rows deleted per convergence cycle.";
        };
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
        description = ''
          Enable declarative sops-nix API key protection for AI stack services.

          When true, each AI stack service (AIDB, hybrid coordinator, embeddings,
          aider-wrapper, PostgreSQL, Redis) requires a matching API key or password
          from /run/secrets/* before accepting requests.

          When false (default), services start without authentication — any local
          process can call them without credentials. This is convenient for isolated
          development machines but is not recommended for shared or networked hosts.

          The deploy script (nixos-quick-deploy.sh) will prompt to enable protection
          on first run when the AI stack role is active. To enable manually, set
          mySystem.secrets.enable = true in nix/hosts/<host>/deploy-options.local.nix
          and rerun with --force-ai-secrets-bootstrap to generate the secrets file.
        '';
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

        aiderWrapperApiKey = lib.mkOption {
          type = lib.types.str;
          default = "aider_wrapper_api_key";
          description = "SOPS key name for aider-wrapper API auth secret.";
        };

        nixosDocsApiKey = lib.mkOption {
          type = lib.types.str;
          default = "nixos_docs_api_key";
          description = "SOPS key name for nixos-docs API auth secret.";
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

      # Phase 19.1.4 — bash/zsh tab-completion for aq-* tools.
      shellCompletions = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          When true, install /etc/profile.d/aq-completions.sh which provides
          bash/zsh tab-completion for aq-hints, aq-report, and aq-prompt-eval.
          Dynamic completions call aq-hints --format=shell-complete at tab time.
        '';
      };

      # Phase 18.4.2 — MOTD digest on login (condensed aq-report).
      motdReport = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          When true, install /etc/profile.d/ai-report-motd.sh which prints a
          5-line AI stack digest (routing %, cache hit rate, eval trend, top gap,
          first recommendation) on interactive shell login if the last report
          is more than 24 hours old.
        '';
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

        ctxSize = lib.mkOption {
          type = lib.types.int;
          default = 32768;
          description = "Context size (tokens) for llama.cpp server. Default is 32K for modern models.";
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

        inferenceTimeoutSeconds = lib.mkOption {
          type    = lib.types.ints.positive;
          default = 300;
          description = ''
            HTTP request timeout (seconds) for llama.cpp chat-completion calls.
            Increase on slow hardware (CPU-only inference). Injected as
            LLAMA_CPP_INFERENCE_TIMEOUT_SECONDS into the hybrid-coordinator service.
          '';
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

        pooling = lib.mkOption {
          type = lib.types.enum [ "none" "mean" "cls" "last" "rank" ];
          default = "mean";
          description = ''
            Pooling strategy passed to llama-server --pooling.
            Use "mean" for encoder-style models (nomic-embed-text, bge-*).
            Use "last" for decoder-style models (Qwen3-Embedding, LLM2Vec).
          '';
        };

        ctxSize = lib.mkOption {
          type = lib.types.ints.positive;
          default = 4096;
          description = ''
            Context window (tokens) for the embedding server.
            Qwen3-Embedding-4B and similar models support up to 8192 tokens;
            4096 is a safe default for long code/document chunks.
          '';
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

      modelAllowlist = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        example = [
          "unsloth/Qwen3-4B-Instruct-2507-GGUF"
          "nomic-ai/nomic-embed-text-v1.5-GGUF"
          "TheBloke/Llama-2-7B-Chat-GGUF"
        ];
        description = ''
          Phase 11.3.3 — Model Weight Integrity: Allowlisted HuggingFace repos.
          When non-empty, only models from these repos can be downloaded and loaded.
          Empty list = no allowlist enforcement (any repo permitted).
          Attempting to use an unlisted repo triggers a NixOS assertion failure.
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

          timeoutSeconds = lib.mkOption {
            type = lib.types.ints.positive;
            default = 30;
            description = ''
              Hard timeout (seconds) for harness evaluation calls. This bounds
              long-running eval requests independently from the latency SLO score.
            '';
          };

          timeoutHardCapSeconds = lib.mkOption {
            type = lib.types.ints.positive;
            default = 20;
            description = ''
              Absolute upper bound (seconds) for harness evaluation calls after
              timeout normalization. Prevents accidental multi-hour waits if
              runtime timeout values are misconfigured.
            '';
          };
        };

        runtime = {
          defaultSafetyMode = lib.mkOption {
            type = lib.types.enum [ "plan-readonly" "execute-mutating" ];
            default = "plan-readonly";
            description = "Default workflow run safety mode for hybrid coordinator sessions.";
          };

          defaultTokenLimit = lib.mkOption {
            type = lib.types.ints.positive;
            default = 8000;
            description = "Default per-run token budget when not explicitly provided by client.";
          };

          defaultToolCallLimit = lib.mkOption {
            type = lib.types.ints.positive;
            default = 40;
            description = "Default per-run tool-call budget when not explicitly provided by client.";
          };

          safetyPolicy = lib.mkOption {
            type = lib.types.attrs;
            default = {
              modes = {
                "plan-readonly" = {
                  allowed_risk_classes = [ "safe" ];
                  requires_approval = [ "review-required" ];
                  blocked = [ "blocked" ];
                };
                "execute-mutating" = {
                  allowed_risk_classes = [ "safe" ];
                  requires_approval = [ "review-required" ];
                  blocked = [ "blocked" ];
                };
              };
            };
            description = "Declarative runtime safety policy consumed by hybrid coordinator.";
          };

          isolationProfiles = lib.mkOption {
            type = lib.types.attrs;
            default = {
              default_profile_by_mode = {
                "plan-readonly" = "readonly-strict";
                "execute-mutating" = "execute-guarded";
              };
              profiles = {
                "readonly-strict" = {
                  workspace_root = "/var/lib/nixos-ai-stack/mutable/program/agent-runs";
                  allow_workspace_write = false;
                  allowed_processes = [ "rg" "cat" "ls" "jq" "sed" ];
                  network_policy = "none";
                };
                "execute-guarded" = {
                  workspace_root = "/var/lib/nixos-ai-stack/mutable/program/agent-runs";
                  allow_workspace_write = true;
                  allowed_processes = [ "rg" "cat" "ls" "jq" "sed" "bash" "python3" "node" "git" ];
                  network_policy = "loopback";
                };
              };
            };
            description = "Declarative per-mode runtime isolation profiles for workflow runs.";
          };

          workflowBlueprints = lib.mkOption {
            type = lib.types.attrs;
            default = {
              version = "1.0";
              blueprints = [
                {
                  id = "coding-bugfix-safe";
                  title = "Coding Bugfix (Safe First)";
                  default_safety_mode = "plan-readonly";
                  intent_contract = {
                    user_intent = "Fix root cause safely with minimal blast radius.";
                    definition_of_done = "Bug resolved, validation evidence captured, and rollback path documented.";
                    depth_expectation = "standard";
                    spirit_constraints = [
                      "Prioritize root-cause correction over superficial symptom masking."
                      "Do not exit after green checks if acceptance evidence is incomplete."
                    ];
                    no_early_exit_without = [
                      "verification evidence"
                      "risk summary"
                      "rollback command"
                    ];
                    anti_goals = [
                      "checkbox-only completion"
                      "silent unresolved blocker"
                    ];
                  };
                  phases = [
                    { id = "discover"; tools = [ "hints" "route_search" "tree_search" ]; }
                    { id = "plan"; tools = [ "workflow_plan" ]; }
                    { id = "execute"; tools = [ "route_search" "memory_recall" ]; requires_approval = true; }
                    { id = "validate"; tools = [ "harness_eval" "health" ]; }
                  ];
                }
              ];
            };
            description = "Declarative workflow blueprint catalog served by hybrid coordinator.";
          };

          schedulerPolicy = lib.mkOption {
            type = lib.types.attrs;
            default = {
              version = "1.0";
              selection = {
                max_candidates = 5;
                allowed_statuses = [ "ready" "degraded" ];
                require_all_tags = false;
                freshness_window_seconds = 3600;
                weights = {
                  status = 0.45;
                  runtime_class = 0.2;
                  transport = 0.15;
                  tag_overlap = 0.1;
                  freshness = 0.1;
                };
              };
              status_weights = {
                ready = 1.0;
                degraded = 0.5;
                draining = 0.1;
                offline = 0.0;
              };
            };
            description = "Declarative runtime scheduling policy for control-plane candidate selection.";
          };

          cachePrewarm = {
            enable = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Enable periodic semantic-cache/routing prewarm using seed-routing-traffic.sh.";
            };

            queryCount = lib.mkOption {
              type = lib.types.ints.positive;
              default = 8;
              description = "Number of seeded queries per prewarm run.";
            };

            intervalMinutes = lib.mkOption {
              type = lib.types.ints.positive;
              default = 30;
              description = "How often to run cache prewarm timer.";
            };
          };

          telemetryEnabled = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = ''
              Enable AIDB telemetry event persistence (JSONL + PostgreSQL telemetry_events)
              for runtime monitoring, dashboard analytics, and feedback-loop auditing.
            '';
          };

          toolSecurity = {
            enable = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Enable first-use security auditing for tool metadata/parameters.";
            };

            enforce = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Block tool usage when the security auditor flags unsafe behavior.";
            };

            cacheTtlHours = lib.mkOption {
              type = lib.types.ints.positive;
              default = 168;
              description = "TTL for cached safe tool audit decisions.";
            };

            policy = lib.mkOption {
              type = lib.types.attrs;
              default = {
                version = "1.0";
                blocked_tools = [ "shell_exec" "shell_execute" "remote_ssh_exec" "raw_system_command" "danger_tool" ];
                keyword_exempt_tools = [ "route_search" ];
                blocked_endpoint_patterns = [ "/control/*" "*/reload-model" "*/session/*/mode" ];
                blocked_reason_keywords = [
                  "exec"
                  "shell"
                  "sudo"
                  "delete"
                  "truncate"
                  "drop"
                  "overwrite"
                  "network egress"
                ];
                strip_manifest_keys = [ "exec" "command" "shell" "script" "sudo" "token" "api_key" ];
                blocked_parameter_keys = [ "exec" "command" "shell" "script" "sudo" "api_key" "token" ];
                max_parameter_string_length = 4096;
              };
              description = "Declarative first-use tool security auditor policy.";
            };
          };

          semanticToolingAutorun = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = ''
              Automatically run semantic tooling orchestration (hints + capability
              discovery + planned tool metadata) on hybrid /query requests.
            '';
          };

          hintFeedbackDbEnabled = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Enable Postgres-backed hint feedback profile loading in hints_engine.";
          };

          hintFeedbackDbCacheTtlSeconds = lib.mkOption {
            type = lib.types.ints.positive;
            default = 120;
            description = "Cache TTL (seconds) for in-memory hint feedback profile snapshots.";
          };

          hintDiversityRepeatWindow = lib.mkOption {
            type = lib.types.ints.positive;
            default = 300;
            description = "Number of recent hint-audit rows to inspect for repeated-hint concentration.";
          };

          hintDiversityRepeatCapPct = lib.mkOption {
            type = lib.types.addCheck lib.types.float (v: v >= 10.0 && v <= 100.0);
            default = 60.0;
            description = "Repeat-share percentage cap before a hint ID is considered overused.";
          };

          hintDiversityRepeatMinCount = lib.mkOption {
            type = lib.types.ints.positive;
            default = 6;
            description = "Minimum recent injection count before repeat-cap logic is applied.";
          };

          hintDiversityTypeMin = lib.mkOption {
            type = lib.types.str;
            default = "runtime_signal:1,gap_topic:1,workflow_rule:1";
            description = "Minimum per-type hint quotas (comma-separated type:n), e.g. runtime_signal:1,gap_topic:1.";
          };

          hintDiversityTypeMax = lib.mkOption {
            type = lib.types.str;
            default = "runtime_signal:2,prompt_template:1,gap_topic:2,workflow_rule:1,tool_warning:1";
            description = "Maximum per-type hint quotas (comma-separated type:n) used during final hint selection.";
          };

          hintBandit = {
            enable = lib.mkOption {
              type = lib.types.bool;
              default = true;
              description = "Enable contextual bandit scoring on top of hint_feedback_profiles.";
            };

            minEvents = lib.mkOption {
              type = lib.types.ints.positive;
              default = 3;
              description = "Minimum feedback events required before bandit scoring applies to a hint arm.";
            };

            priorAlpha = lib.mkOption {
              type = lib.types.addCheck lib.types.float (v: v > 0.0);
              default = 1.0;
              description = "Beta prior alpha for helpful/unhelpful posterior mean.";
            };

            priorBeta = lib.mkOption {
              type = lib.types.addCheck lib.types.float (v: v > 0.0);
              default = 1.0;
              description = "Beta prior beta for helpful/unhelpful posterior mean.";
            };

            explorationWeight = lib.mkOption {
              type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 2.0);
              default = 0.35;
              description = "Exploration coefficient applied to the UCB-style uncertainty term.";
            };

            maxAdjust = lib.mkOption {
              type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 1.0);
              default = 0.12;
              description = "Maximum absolute score adjustment contributed by the contextual bandit policy.";
            };

            confidenceFloor = lib.mkOption {
              type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 1.0);
              default = 0.15;
              description = "Minimum confidence multiplier for low-sample bandit arms.";
            };
          };

          aiderToolingPlanEnabled = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = ''
              Automatically inject workflow/tooling plans into aider-wrapper tasks
              so agent execution follows the shared tool orchestration layer.
            '';
          };

          aiderHintsMinScore = lib.mkOption {
            type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 1.0);
            default = 0.55;
            description = "Minimum aq-hints score required before injection into aider task prompts.";
          };

          aiderHintsMinSnippetChars = lib.mkOption {
            type = lib.types.ints.positive;
            default = 24;
            description = "Minimum hint snippet length required before injection into aider task prompts.";
          };

          aiderHintsMinTokenOverlap = lib.mkOption {
            type = lib.types.addCheck lib.types.int (v: v >= 0);
            default = 1;
            description = ''
              Minimum lexical token overlap required between task prompt and
              hint metadata/snippet before hint injection into aider tasks.
            '';
          };

          aiderHintsBypassOverlapScore = lib.mkOption {
            type = lib.types.addCheck lib.types.float (v: v >= 0.0 && v <= 1.0);
            default = 0.72;
            description = ''
              Hint score threshold that bypasses token-overlap gating for high-confidence hints.
            '';
          };

          aiderSmallScopeSubtreeOnly = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = ''
              Enable aider `--subtree-only` for file-scoped tasks to reduce full-repo scanning.
            '';
          };

          aiderSmallScopeMapTokens = lib.mkOption {
            type = lib.types.addCheck lib.types.int (v: v >= 0);
            default = 384;
            description = "Repo-map token budget for file-scoped aider tasks.";
          };

          aiderAnalysisFastMode = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = ''
              Enable analysis-only aider profile (read-only files, reduced map tokens,
              shorter timeout) for no-edit prompts.
            '';
          };

          aiderAnalysisMapTokens = lib.mkOption {
            type = lib.types.addCheck lib.types.int (v: v >= 0);
            default = 0;
            description = "Repo-map token budget for analysis-only aider tasks (0 disables repo map).";
          };

          aiderAnalysisMaxRuntimeSeconds = lib.mkOption {
            type = lib.types.ints.positive;
            default = 75;
            description = "Maximum runtime for analysis-only aider tasks before timeout.";
          };

          aiderAnalysisRouteToHybrid = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Route analysis-only tasks through hybrid /query fast path before invoking aider.";
          };

          aiderAutoFileScope = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Automatically infer likely file paths from task prompts when files[] is empty.";
          };

          aiderAutoFileScopeMax = lib.mkOption {
            type = lib.types.ints.positive;
            default = 6;
            description = "Maximum inferred files for automatic aider file scope.";
          };

          aiderDefaultMapTokens = lib.mkOption {
            type = lib.types.addCheck lib.types.int (v: v >= 0);
            default = 512;
            description = "Default repo-map token budget when no explicit files are scoped.";
          };

          parityScorecard = lib.mkOption {
            type = lib.types.attrs;
            default = {
              version = "1.0";
              tracks = [
                { id = "run_trajectory_replay"; weight = 0.2; status = "partial"; }
                { id = "runtime_control_plane"; weight = 0.2; status = "partial"; }
                { id = "runtime_safety_envelope"; weight = 0.2; status = "partial"; }
                { id = "budget_guardrails"; weight = 0.15; status = "partial"; }
                { id = "cli_workflow_ergonomics"; weight = 0.15; status = "partial"; }
                { id = "mcp_workflow_blueprints"; weight = 0.1; status = "partial"; }
              ];
            };
            description = "Declarative parity scorecard data source for runtime/reporting.";
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

      grafanaPort = lib.mkOption {
        type = lib.types.port;
        default = 3000;
        description = "Grafana HTTP listen port.";
      };

      amdgpuMetricsIntervalSeconds = lib.mkOption {
        type = lib.types.ints.positive;
        default = 60;
        description = ''
          Interval for ai-amdgpu-metrics-exporter timer runs.
          Increased from sub-minute defaults to reduce audit/systemd churn.
        '';
      };

      commandCenter = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = "Enable declarative command-center dashboard services and collectors.";
        };

        bindAddress = lib.mkOption {
          type = lib.types.str;
          default = "0.0.0.0";
          description = "Bind address for command-center frontend and API. Use 0.0.0.0 to accept both IPv4 (127.0.0.1) and IPv6 (::1) loopback when localhost resolves to ::1.";
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

      aiderWrapper = lib.mkOption {
        type = lib.types.port;
        default = 8090;
        description = "Aider-wrapper MCP HTTP port.";
      };

      anthropicProxy = lib.mkOption {
        type = lib.types.port;
        default = 8120;
        description = "Local Anthropic-compatible proxy HTTP port.";
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

      grafana = lib.mkOption {
        type = lib.types.port;
        default = 3000;
        description = "Grafana HTTP port.";
      };

      openWebui = lib.mkOption {
        type = lib.types.port;
        default = 3001;
        description = "Open WebUI browser interface port.";
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

      aiderWrapperPort = lib.mkOption {
        type = lib.types.port;
        default = 8090;
        description = "TCP port for the aider-wrapper async coding assistant MCP server.";
      };

      nixosDocsPort = lib.mkOption {
        type        = lib.types.port;
        default     = 8096;
        description = "TCP port for the nixos-docs MCP server.";
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
