{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# AI Stack role — native NixOS service implementation.
#
# Activated when: mySystem.roles.aiStack.enable = true
#                 AND mySystem.aiStack.backend = "ollama"  (default)
#
# Provisions:
#   - services.ollama          — LLM inference daemon (ROCm/CUDA/CPU)
#   - ollama-model-pull        — oneshot to pull declared models on first boot
#   - services.open-webui      — browser UI on port 3000  (when ui.enable)
#   - services.qdrant          — vector database on port 6333 (when vectorDb.enable)
#   - firewall ports           — opened only when listenOnLan = true
#
# The k3s backend path (full Kubernetes orchestration) is NOT implemented here;
# it falls through to the existing phase-09 bash orchestration until a
# dedicated k3s module is written.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  ai  = cfg.aiStack;

  # Only engage this module when the role is enabled and backend is ollama.
  enabled = cfg.roles.aiStack.enable && ai.backend == "ollama";

  # Resolve acceleration: "auto" derives from detected GPU vendor.
  resolvedAccel =
    if ai.acceleration != "auto" then ai.acceleration
    else if cfg.hardware.gpuVendor == "amd"    then "rocm"
    else if cfg.hardware.gpuVendor == "nvidia"  then "cuda"
    else "cpu";

  listenAddr = if ai.listenOnLan then "0.0.0.0" else "127.0.0.1";

  # open-webui arrived in nixpkgs ~24.11; qdrant has been available longer.
  hasOpenWebui = lib.versionAtLeast lib.version "24.11";
  hasQdrant    = lib.versionAtLeast lib.version "24.11";
in
{
  config = lib.mkIf enabled {

    # -------------------------------------------------------------------------
    # Ollama inference daemon
    # -------------------------------------------------------------------------
    services.ollama = {
      enable = true;
      host   = listenAddr;
      # acceleration: only set when not CPU — avoids invalid "cpu" enum value
      # on older nixpkgs that use a stricter type.
      acceleration = lib.mkIf (resolvedAccel != "cpu") resolvedAccel;
      # ROCm GFX override for AMD GPUs outside the official support matrix.
      rocmOverrideGfx = lib.mkIf
        (resolvedAccel == "rocm" && ai.rocmGfxOverride != null)
        ai.rocmGfxOverride;
    };

    # -------------------------------------------------------------------------
    # Model pull oneshot — idempotent, runs after ollama is ready.
    # ollama pull is a no-op when the model is already cached locally.
    # -------------------------------------------------------------------------
    systemd.services.ollama-model-pull = lib.mkIf (ai.models != [ ]) {
      description = "Pull declared ollama models on first boot";
      wantedBy    = [ "multi-user.target" ];
      after       = [ "ollama.service" "network-online.target" ];
      wants       = [ "network-online.target" ];
      requires    = [ "ollama.service" ];
      serviceConfig = {
        Type            = "oneshot";
        RemainAfterExit = true;
        User            = "ollama";
        # Each pull is attempted independently; a single model failure does not
        # abort the rest. The service exits 0 as long as the script completes.
        ExecStart = pkgs.writeShellScript "ollama-model-pull" (
          lib.concatMapStrings
            (m: "  ${pkgs.ollama}/bin/ollama pull ${lib.escapeShellArg m} || true\n")
            ai.models
        );
      };
    };

    # -------------------------------------------------------------------------
    # Open WebUI — browser interface to ollama
    # -------------------------------------------------------------------------
    services.open-webui = lib.mkIf (ai.ui.enable && hasOpenWebui) {
      enable = true;
      host   = listenAddr;
      port   = 3000;
      environment = {
        # Point at local ollama; works whether listening on loopback or LAN.
        OLLAMA_BASE_URL = "http://127.0.0.1:11434";
        # Single-user local install: disable auth and signup prompts.
        # Set WEBUI_AUTH = "true" in facts.nix if this machine is shared.
        WEBUI_AUTH    = lib.mkDefault "false";
        ENABLE_SIGNUP = lib.mkDefault "false";
      };
    };

    # -------------------------------------------------------------------------
    # Qdrant vector database — required for RAG and AIDB embeddings
    # -------------------------------------------------------------------------
    services.qdrant = lib.mkIf (ai.vectorDb.enable && hasQdrant) {
      enable = true;
    };

    # -------------------------------------------------------------------------
    # Firewall — only punch holes when explicitly exposing on LAN
    # -------------------------------------------------------------------------
    networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan (
      [ 11434 ]                                                  # ollama
      ++ lib.optional (ai.ui.enable && hasOpenWebui) 3000        # open-webui
      ++ lib.optional (ai.vectorDb.enable && hasQdrant) 6333     # qdrant HTTP
      ++ lib.optional (ai.vectorDb.enable && hasQdrant) 6334     # qdrant gRPC
    );
  };
}
