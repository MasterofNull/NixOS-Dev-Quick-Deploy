{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem.aiStack;
  roleEnabled = config.mySystem.roles.aiStack.enable;

  # Ollama acceleration: "auto" → rocm (AMD ThinkPad P14s Gen 2a);
  # override explicitly to "cuda" for NVIDIA or "cpu" to disable GPU.
  resolvedAcceleration =
    if cfg.acceleration == "cpu" then null
    else if cfg.acceleration == "auto" then "rocm"
    else cfg.acceleration;  # "rocm" | "cuda" passed through

  listenHost = if cfg.listenOnLan then "0.0.0.0" else "127.0.0.1";

  # K3s ConfigMap reconciler script — only active when backend = "k3s".
  reconcilerScript = pkgs.writeShellScript "nixos-ai-stack-reconcile" ''
    set -euo pipefail

    MANIFEST_PATH="${cfg.manifestPath}"
    DISABLE_MARKER="${cfg.disableMarkerPath}"
    NAMESPACE="${cfg.namespace}"

    if [[ -e "$DISABLE_MARKER" ]]; then
      echo "[ai-stack-reconcile] Disable marker exists: $DISABLE_MARKER; skipping apply."
      exit 0
    fi

    if [[ ! -d "$MANIFEST_PATH" ]]; then
      echo "[ai-stack-reconcile] Manifest path not found: $MANIFEST_PATH; skipping apply."
      exit 0
    fi

    if ! ${pkgs.kubectl}/bin/kubectl --request-timeout=${cfg.kubectlTimeout} cluster-info >/dev/null 2>&1; then
      echo "[ai-stack-reconcile] Kubernetes API is not reachable; skipping apply."
      exit 0
    fi

    echo "[ai-stack-reconcile] Applying manifests from $MANIFEST_PATH"
    ${pkgs.kubectl}/bin/kubectl --request-timeout=${cfg.kubectlTimeout} apply -k "$MANIFEST_PATH"

    echo "[ai-stack-reconcile] Patching env ConfigMap model defaults in namespace ${cfg.namespace}"
    ${pkgs.kubectl}/bin/kubectl --request-timeout=${cfg.kubectlTimeout} -n "$NAMESPACE" patch configmap env --type merge \
      -p '{"data":{"EMBEDDING_MODEL":"${cfg.embeddingModel}","LLAMA_CPP_DEFAULT_MODEL":"${cfg.llamaDefaultModel}","LLAMA_CPP_MODEL_FILE":"${cfg.llamaModelFile}"}}'
  '';
in
{
  options.mySystem.aiStack = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable declarative AI stack runtime services when the aiStack role is active.";
    };

    # ── Backend selection ────────────────────────────────────────────────────
    backend = lib.mkOption {
      type = lib.types.enum [ "ollama" "k3s" ];
      default = "ollama";
      description = ''
        AI stack deployment backend.
        "ollama" — native NixOS systemd services; no containers required.
        "k3s"    — Kubernetes-based stack; switch to this once K3s is operational.
      '';
    };

    # ── Ollama options (backend = "ollama") ──────────────────────────────────
    acceleration = lib.mkOption {
      type = lib.types.enum [ "auto" "cpu" "rocm" "cuda" ];
      default = "auto";
      description = ''
        GPU acceleration for ollama.
        "auto" resolves to "rocm" (AMD default for this machine).
        Use "cuda" for NVIDIA, "cpu" to disable GPU offload.
      '';
    };

    models = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ "qwen2.5-coder:7b" ];
      description = "Ollama model tags to ensure are present on first boot (ollama backend only).";
    };

    ui = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Enable Open WebUI frontend on port 3000 (ollama backend only).";
      };
    };

    vectorDb = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable Qdrant vector database (reserved — not yet wired up).";
      };
    };

    listenOnLan = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Expose AI services on all interfaces (0.0.0.0). Default: loopback only.";
    };

    # ── K3s / Kubernetes options (backend = "k3s") ───────────────────────────
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

  config = lib.mkIf (roleEnabled && cfg.enable) (lib.mkMerge [

    # ── Ollama backend ────────────────────────────────────────────────────────
    (lib.mkIf (cfg.backend == "ollama") {

      services.ollama = {
        enable = true;
        acceleration = resolvedAcceleration;
        host = listenHost;
      };

      # Pull each model after ollama starts. `ollama pull` is idempotent —
      # instant when the model is already present.
      systemd.services.ollama-model-pull = lib.mkIf (cfg.models != []) {
        description = "Ensure configured ollama models are present";
        after = [ "ollama.service" "network-online.target" ];
        wants = [ "ollama.service" "network-online.target" ];
        wantedBy = [ "multi-user.target" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          set -euo pipefail
          ${lib.concatMapStringsSep "\n" (m: ''
            echo "Ensuring ollama model: ${m}"
            ${pkgs.ollama}/bin/ollama pull ${lib.escapeShellArg m}
          '') cfg.models}
        '';
      };

      services.open-webui = lib.mkIf cfg.ui.enable {
        enable = true;
        host = listenHost;
        port = 3000;
        environment = {
          OLLAMA_BASE_URL = "http://127.0.0.1:11434";
          WEBUI_AUTH = "false";
        };
      };

      networking.firewall.allowedTCPPorts = lib.mkIf cfg.listenOnLan [
        11434  # ollama REST API
        3000   # Open WebUI
      ];
    })

    # ── K3s backend ───────────────────────────────────────────────────────────
    (lib.mkIf (cfg.backend == "k3s") {

      services.k3s = {
        enable = lib.mkDefault true;
        role = lib.mkDefault "server";
      };

      environment.systemPackages = [
        pkgs.kubectl
        pkgs.kubernetes-helm
      ];

      systemd.services.nixos-ai-stack-reconcile = {
        description = "Reconcile AI stack Kubernetes manifests";
        after = [ "k3s.service" "network-online.target" ];
        wants = [ "k3s.service" "network-online.target" ];
        serviceConfig = {
          Type = "oneshot";
          User = "root";
          ConditionPathExists = "!${cfg.disableMarkerPath}";
        };
        script = "${reconcilerScript}";
      };

      systemd.timers.nixos-ai-stack-reconcile = {
        description = "Periodic AI stack Kubernetes reconciliation";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "2m";
          OnUnitActiveSec = "${toString cfg.reconcileIntervalMinutes}m";
          Unit = "nixos-ai-stack-reconcile.service";
        };
      };
    })

  ]);
}
