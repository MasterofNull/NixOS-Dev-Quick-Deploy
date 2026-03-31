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
        model = lib.mkDefault "/var/lib/llama-cpp/models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
        huggingFaceRepo = lib.mkDefault "unsloth/Qwen3-4B-Instruct-2507-GGUF";
        huggingFaceFile = lib.mkDefault "Qwen3-4B-Instruct-2507-Q4_K_M.gguf";
        sha256 = lib.mkDefault "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597";
        extraArgs = lib.mkDefault [
          "--timeout" "120"
          "--parallel" "2"
          "--batch-size" "512"
          "--ubatch-size" "64"
          "--threads" "8"
          "--threads-batch" "8"
          "--flash-attn" "on"
          "--mlock"
          "--reasoning-format" "deepseek"
        ];
      };

      embeddingDimensions = lib.mkDefault 2560;
      embeddingServer = {
        enable = lib.mkDefault true;
        model = lib.mkDefault "/var/lib/llama-cpp/models/Qwen3-Embedding-4B-q4_k_m.gguf";
        huggingFaceRepo = lib.mkDefault "Mungert/Qwen3-Embedding-4B-GGUF";
        huggingFaceFile = lib.mkDefault "Qwen3-Embedding-4B-q4_k_m.gguf";
        sha256 = lib.mkDefault "2a91ec30c4c694af60cbedfc2f30d6aa5fd69a5286a8fb5544aa47868243054e";
        pooling = lib.mkDefault "last";
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
  };
}
