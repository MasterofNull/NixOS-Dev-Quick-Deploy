/**
  Phase 16.5.3 — Reference SBC configuration (Raspberry Pi 4 / aarch64).

  Purpose: demonstrates a minimum-footprint AI stack on an aarch64 SBC with
  4-6 GB RAM.  Open WebUI is disabled automatically (micro tier, Phase 16.5.2);
  only the llama.cpp HTTP API is exposed on :8080.

  Target hardware: Raspberry Pi 4 / 5 (4-8 GB), RockPro64, or any aarch64
  board with ≥4 GB RAM.  Copy this file and add a real hardware-configuration.nix
  from `nixos-generate-config` to deploy on physical hardware.

  Success metric for Phase 16.5.3:
    nix path-info -rS .#nixosConfigurations.sbc-minimal-ai-dev.config.system.build.toplevel
  should report ≤ 2 GB closure (without AI models — those are fetched at runtime).
*/
{ ... }:
{
  mySystem = {
    hostName    = "sbc-minimal";
    primaryUser = "pi";

    # Target platform — aarch64-linux for all Raspberry Pi / Rockchip boards.
    system = "aarch64-linux";

    hardware = {
      # Raspberry Pi 4 (4 GB) — micro tier.  Discrete GPU absent; iGPU is
      # VideoCore VI (not ROCm-capable) so acceleration defaults to "cpu".
      systemRamGb      = 4;
      gpuVendor        = "none";
      igpuVendor       = "none";
      cpuVendor        = "arm";
      storageType      = "sd";
      isMobile         = false;
      firmwareType     = "efi";         # RPi 4 with UEFI firmware (RPi4-UEFI project)
      earlyKmsPolicy   = "off";
      # nixos-hardware module for Raspberry Pi 4:
      #   nixosHardwareModule = "raspberry-pi-4";
      # Omit for generic aarch64 SBC targets.
      nixosHardwareModule = null;
    };

    kernel.track = "latest-stable";

    deployment = {
      enableHibernation  = false;
      swapSizeGb         = 0;           # use zram instead
      rootFsckMode       = "check";
      initrdEmergencyAccess = true;
    };

    disk = {
      layout = "none";                  # manage partitions via SD card imager
      device = "/dev/disk/by-id/CHANGE-ME";
      luks.enable  = false;
      btrfsSubvolumes = [ "@root" "@home" "@nix" ];
    };

    secureboot.enable = false;          # UEFI Secure Boot not available on RPi
    secrets.enable    = false;          # no SOPS secrets for minimal demo

    compliance.hospitalClassified.enable = false;

    # Roles — minimal profile already defaults aiStack/gaming/desktop to false.
    # AI stack is DISABLED here because the 12 GB minimum assertion would reject
    # a 4 GB SBC.  For SBCs with ≥12 GB RAM (RPi 5 with 16 GB or RK3588 boards),
    # set roles.aiStack.enable = true and update hardware.systemRamGb accordingly.
    roles.aiStack.enable        = false;
    roles.server.enable         = false;
    roles.mobile.enable         = false;
    roles.virtualization.enable = false;
    localhostIsolation.enable   = true;

    # MCP servers require ≥8 GB for comfortable operation; disable on micro tier.
    mcpServers.enable = false;

    # AI stack config — set roles.aiStack.enable = true to activate on higher-RAM SBCs.
    # ui.enable will auto-disable via Phase 16.5.2 tier guard (micro/nano tiers).
    # acceleration = "cpu" (no ROCm/CUDA on RPi VideoCore).
    aiStack = {
      backend       = "llamacpp";
      acceleration  = "cpu";
      listenOnLan   = false;
      vectorDb.enable        = false;
      embeddingServer.enable = false;
      switchboard.enable     = false;

      # Model path is auto-selected by Phase 16.2.1 tier logic (micro → 1.5B).
      # To enable automatic HuggingFace download, set:
      #   llamaCpp.huggingFaceRepo = "Qwen/Qwen2.5-1.5B-Instruct-GGUF";
      #   llamaCpp.huggingFaceFile = "qwen2.5-1.5b-instruct-q8_0.gguf";
      #   llamaCpp.sha256 = "<64-char sha256 of the GGUF file>";
      # After manual download to /var/lib/llama-cpp/models/, no sha256 is needed.
    };
  };
}
