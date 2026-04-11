{ lib, config, ... }:
let
  cfg = config.mySystem;
  isP14sAmdAiDev =
    cfg.profile == "ai-dev"
    && cfg.hardware.nixosHardwareModule == "lenovo-thinkpad-p14s-amd-gen2";
in
{
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

      llamaCpp = {
        activeModel = lib.mkDefault "gemma4-e4b";
        extraArgs = lib.mkDefault [
          "--timeout" "120"
          "--parallel" "1"
          "--batch-size" "512"
          "--ubatch-size" "64"
          "--threads" "8"
          "--threads-batch" "8"
          "--flash-attn" "on"
          "--mlock"
        ];
      };

      embeddingServer = {
        enable = lib.mkDefault true;
        activeModel = lib.mkDefault "bge-m3";
        extraArgs = lib.mkDefault [
          "--threads" "8"
          "--batch-size" "512"
          "--flash-attn" "on"
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
        users = [ cfg.primaryUser ];
        commands = [
          {
            command = "/home/${cfg.primaryUser}/Documents/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/nixos-rebuild";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/systemctl";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/journalctl";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/flatpak";
            options = [ "NOPASSWD" ];
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
  };
}
