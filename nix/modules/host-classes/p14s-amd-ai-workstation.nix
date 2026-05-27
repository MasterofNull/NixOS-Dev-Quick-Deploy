{
  lib,
  config,
  ...
}: let
  cfg = config.mySystem;
  isP14sAmdAiDev =
    cfg.profile
    == "ai-dev"
    && cfg.hardware.nixosHardwareModule == "lenovo-thinkpad-p14s-amd-gen2";
in {
  config = lib.mkIf isP14sAmdAiDev {
    mySystem.roles.aiStack.enable = lib.mkDefault true;
    mySystem.roles.server.enable = lib.mkDefault false;
    mySystem.roles.mobile.enable = lib.mkDefault true;
    mySystem.roles.virtualization.enable = lib.mkDefault true;

    mySystem.mcpServers.repoPath =
      lib.mkDefault "/home/${cfg.primaryUser}/Documents/NixOS-Dev-Quick-Deploy";

    mySystem.aiStack = {
      backend = lib.mkDefault "llamacpp";
      acceleration = lib.mkDefault "auto";
      rocmGfxOverride = lib.mkDefault "9.0.0";
      switchboard = {
        localConcurrency = lib.mkDefault 4;
        reservedSlots = lib.mkDefault 1;
        continueLocal = {
          # Increased limits for high-end interactive use.
          maxInputTokens = lib.mkDefault 4000;
          maxMessages = lib.mkDefault 12;
        };
      };

      llamaCpp = {
        activeModel = lib.mkDefault "gemma4-e4b";
        # Mobile 27GB RAM target: leave memory reclaimable so the editor and
        # desktop are not OOM-killed when the dashboard or QA tooling runs.
        ctxSize = lib.mkDefault 16384;
        extraArgs = lib.mkDefault [
          "--timeout"
          "600"
          "--parallel"
          "1"
          "--batch-size"
          "512"
          "--ubatch-size"
          "256"
          "--threads"
          "8"
          "--threads-batch"
          "8"
          "--flash-attn"
          "on"
          "--cache-type-k"
          "q8_0"
          "--cache-type-v"
          "q8_0"
          "--prompt-cache-capacity"
          "3"
        ];
      };

      embeddingServer = {
        enable = lib.mkDefault true;
        activeModel = lib.mkDefault "bge-m3";
        extraArgs = lib.mkDefault [
          "--threads"
          "4"
          "--batch-size"
          "2048"
          "--flash-attn"
          "on"
        ];
      };

      ui.enable = lib.mkDefault true;
      vectorDb.enable = lib.mkDefault true;
      listenOnLan = lib.mkDefault false;
    };

    mySystem.secrets.enable = lib.mkDefault true;
    mySystem.secrets.sopsFile =
      lib.mkDefault "/home/${cfg.primaryUser}/.local/share/nixos-quick-deploy/secrets/${cfg.hostName}/secrets.sops.yaml";
    mySystem.secrets.ageKeyFile =
      lib.mkDefault "/home/${cfg.primaryUser}/.config/sops/age/keys.txt";

    # Prefer stability over manual GPU power tuning on this workstation.
    # This removes the recurring amdgpu overdrive boot warning and narrows the
    # remaining DMCUB diagnostics to core display/firmware behavior.
    hardware.amdgpu.overdrive.enable = lib.mkForce false;

    security.sudo.extraRules = lib.mkAfter [
      {
        users = [cfg.primaryUser];
        commands = [
          {
            command = "/home/${cfg.primaryUser}/Documents/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh *";
            options = ["NOPASSWD"];
          }
          {
            command = "/run/current-system/sw/bin/nixos-rebuild *";
            options = ["NOPASSWD"];
          }
          {
            command = "/run/current-system/sw/bin/systemctl *";
            options = ["NOPASSWD"];
          }
          {
            command = "/run/current-system/sw/bin/journalctl *";
            options = ["NOPASSWD"];
          }
          {
            command = "/run/current-system/sw/bin/flatpak *";
            options = ["NOPASSWD"];
          }
          # Model-switch CLI: allows aq-coder / aq-architect without password prompt.
          # Script is repo-local, executable, Python shebang — sudo resolves interpreter.
          {
            command = "${cfg.mcpServers.repoPath}/scripts/ai/aq-model-switch *";
            options = ["NOPASSWD"];
          }
        ];
      }
    ];

    boot.kernelParams = lib.mkAfter [
      # This platform repeatedly marks TSC unstable during boot; telling the
      # kernel up front avoids the watchdog warning and switches directly to the
      # fallback clocksource.
      "tsc=unstable"
    ];

    environment.sessionVariables = {
      # Keep the desktop stack on the conservative display path here. Recent
      # freezes on this Renoir/COSMIC workstation line up with amdgpu DMUB/DC
      # faults, so do not force the experimental HDR path globally.
      ENABLE_HDR_WSI = lib.mkForce "0";
      DXVK_HDR = lib.mkForce "0";
    };

    # Phase 63.5 — AI stack state paths under /persist (impermanence).
    # Only active when mySystem.aiStack.impermanence.enable = true AND
    # the impermanence NixOS module is available in the flake inputs.
    # /persist must be a mounted filesystem before nixos-rebuild switch.
    environment.persistence = lib.mkIf cfg.aiStack.impermanence.enable {
      "${cfg.aiStack.impermanence.persistPath}" = {
        hideMounts = true;
        directories = [
          "/var/lib/ai-stack"
          "/var/lib/nixos-system-dashboard"
          "/var/lib/qdrant"
          "/var/lib/redis-ai"
        ];
        users.${cfg.primaryUser} = {
          directories = [
            ".config/Continue"
            ".local/share/nixos-system-dashboard"
          ];
        };
      };
    };
  };
}
