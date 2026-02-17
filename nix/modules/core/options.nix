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
        type = lib.types.enum [ "amd" "intel" "nvidia" "none" ];
        default = "none";
        description = "Primary (discrete) GPU vendor. On hybrid systems this is the dGPU (Nvidia/AMD).";
      };

      igpuVendor = lib.mkOption {
        type = lib.types.enum [ "amd" "intel" "none" ];
        default = "none";
        description = "Secondary integrated GPU vendor. Set when dGPU+iGPU coexist (e.g. Intel iGPU + Nvidia dGPU). Enables PRIME/hybrid graphics support.";
      };

      cpuVendor = lib.mkOption {
        type = lib.types.enum [ "amd" "intel" "unknown" ];
        default = "unknown";
        description = "Detected CPU vendor.";
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
