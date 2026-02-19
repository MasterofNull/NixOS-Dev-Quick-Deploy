{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# AI Stack role — native NixOS service implementation.
#
# Activated when: mySystem.roles.aiStack.enable = true
#
# Backends
# ────────
# llamacpp (default)
#   • llama-server on :8080 (OpenAI-compatible API)
#   • Open WebUI on :3000 (wired to llama-server via OPENAI_API_BASE_URLS)
#   • Qdrant vector DB on :6333 (when vectorDb.enable)
#   • No Ollama daemon — llama.cpp serves models from local GGUF files.
#
# ollama
#   • services.ollama on :11434
#   • ollama-model-pull oneshot on first boot
#   • Open WebUI on :3000 (OLLAMA_BASE_URL)
#   • Qdrant vector DB on :6333 (when vectorDb.enable)
#
# k3s
#   • Kubernetes-orchestrated stack — see nix/modules/services/ai-stack.nix
# ---------------------------------------------------------------------------
let
  cfg  = config.mySystem;
  ai   = cfg.aiStack;

  roleEnabled = cfg.roles.aiStack.enable;
  listenAddr  = if ai.listenOnLan then "0.0.0.0" else "127.0.0.1";
  llama       = ai.llamaCpp;

  hasOpenWebui = lib.versionAtLeast lib.version "24.11";
  hasQdrant    = lib.versionAtLeast lib.version "24.11";

  # Open WebUI environment — different API target per backend.
  openWebuiEnv =
    (if ai.backend == "llamacpp" then {
      # llama-server exposes an OpenAI-compatible API; wire open-webui to it.
      OPENAI_API_BASE_URLS = "http://127.0.0.1:${toString llama.port}";
      OPENAI_API_KEYS      = "dummy";  # llama-server ignores the value
      OLLAMA_BASE_URL      = "";       # disable built-in Ollama probe
      WEBUI_AUTH           = lib.mkDefault "false";
      ENABLE_SIGNUP        = lib.mkDefault "false";
    } else {
      OLLAMA_BASE_URL = "http://127.0.0.1:11434";
      WEBUI_AUTH      = lib.mkDefault "false";
      ENABLE_SIGNUP   = lib.mkDefault "false";
    })
    // lib.optionalAttrs (ai.vectorDb.enable && hasQdrant) {
      VECTOR_DB  = "qdrant";
      QDRANT_URI = "http://127.0.0.1:6333";
    };
in
{
  config = lib.mkMerge [

    # ── llama.cpp — active when llamaCpp.enable regardless of backend ─────────
    # The llama-server provides an OpenAI-compatible HTTP API on :8080.
    # Model path is controlled by mySystem.aiStack.llamaCpp.model; the unit
    # starts automatically once a GGUF file exists at that path.
    (lib.mkIf (roleEnabled && llama.enable) {

      users.groups.llama = { };
      users.users.llama = {
        isSystemUser = true;
        group        = "llama";
        description  = "llama.cpp inference server";
        home         = "/var/lib/llama-cpp";
        createHome   = true;
      };

      systemd.tmpfiles.rules = [
        "d /var/lib/llama-cpp/models 0750 llama llama -"
      ];

      systemd.services.llama-cpp = {
        description = "llama.cpp OpenAI-compatible inference server";
        wantedBy    = [ "multi-user.target" ];
        after       = [ "network.target" ];
        # Skip until the GGUF is provisioned; re-activates automatically
        # after the model is placed (e.g. via systemctl start llama-cpp).
        unitConfig.ConditionPathExists = llama.model;
        serviceConfig = {
          Type             = "simple";
          User             = "llama";
          Group            = "llama";
          Restart          = "on-failure";
          RestartSec       = "5s";
          StateDirectory   = "llama-cpp";
          RuntimeDirectory = "llama-cpp";
          ExecStart = lib.concatStringsSep " " ([
            "${pkgs.llama-cpp}/bin/llama-server"
            "--host" (lib.escapeShellArg llama.host)
            "--port" (toString llama.port)
            "--model" (lib.escapeShellArg llama.model)
          ] ++ (map lib.escapeShellArg llama.extraArgs));
        };
      };

      networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan (
        [ llama.port ]
        ++ lib.optional (ai.ui.enable && hasOpenWebui) 3000
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) 6333
        ++ lib.optional (ai.vectorDb.enable && hasQdrant) 6334
      );
    })

    # ── Open WebUI — active for llamacpp and ollama backends ──────────────────
    (lib.mkIf (roleEnabled && ai.backend != "k3s" && ai.ui.enable && hasOpenWebui) {
      services.open-webui = {
        enable      = true;
        host        = listenAddr;
        port        = 3000;
        environment = openWebuiEnv;
      };
    })

    # ── Qdrant vector database — shared across backends ───────────────────────
    (lib.mkIf (roleEnabled && ai.backend != "k3s" && ai.vectorDb.enable && hasQdrant) {
      services.qdrant.enable = true;
    })

    # ── Ollama backend — only when explicitly selected ────────────────────────
    (lib.mkIf (roleEnabled && ai.backend == "ollama") (
      let
        resolvedAccel =
          if ai.acceleration != "auto" then ai.acceleration
          else if cfg.hardware.gpuVendor == "amd"    then "rocm"
          else if cfg.hardware.gpuVendor == "nvidia"  then "cuda"
          else "cpu";
      in {
        services.ollama = {
          enable       = true;
          host         = listenAddr;
          acceleration = lib.mkIf (resolvedAccel != "cpu") resolvedAccel;
          rocmOverrideGfx = lib.mkIf
            (resolvedAccel == "rocm" && ai.rocmGfxOverride != null)
            ai.rocmGfxOverride;
        };

        systemd.services.ollama-model-pull = lib.mkIf (ai.models != [ ]) {
          description = "Pull declared Ollama models on first boot";
          wantedBy    = [ "multi-user.target" ];
          after       = [ "ollama.service" "network-online.target" ];
          wants       = [ "network-online.target" ];
          requires    = [ "ollama.service" ];
          serviceConfig = {
            Type            = "oneshot";
            RemainAfterExit = true;
            User            = "ollama";
            ExecStart = pkgs.writeShellScript "ollama-model-pull" (
              lib.concatMapStrings
                (m: "  ${pkgs.ollama}/bin/ollama pull ${lib.escapeShellArg m} || true\n")
                ai.models
            );
          };
        };

        networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan (
          [ 11434 ]
          ++ lib.optional (ai.ui.enable && hasOpenWebui) 3000
          ++ lib.optional (ai.vectorDb.enable && hasQdrant) 6333
          ++ lib.optional (ai.vectorDb.enable && hasQdrant) 6334
        );
      }
    ))

  ];
}
