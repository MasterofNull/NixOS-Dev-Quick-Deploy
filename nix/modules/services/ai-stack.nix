{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem.aiStack;
  roleEnabled = config.mySystem.roles.aiStack.enable;
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
    ${pkgs.kubectl}/bin/kubectl --request-timeout=${cfg.kubectlTimeout} -n "$NAMESPACE" patch configmap env --type merge -p '{"data":{"EMBEDDING_MODEL":"${cfg.embeddingModel}","LLAMA_CPP_DEFAULT_MODEL":"${cfg.llamaDefaultModel}","LLAMA_CPP_MODEL_FILE":"${cfg.llamaModelFile}"}}' >/dev/null
  '';
in
{
  options.mySystem.aiStack = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable declarative AI stack runtime services when the aiStack role is active.";
    };

    modelProfile = lib.mkOption {
      type = lib.types.enum [ "auto" "small" "medium" "large" ];
      default = "auto";
      description = "Requested model profile tier for host-level AI stack defaults.";
    };

    embeddingModel = lib.mkOption {
      type = lib.types.str;
      default = "BAAI/bge-small-en-v1.5";
      description = "Default embedding model written into the AI stack env ConfigMap.";
    };

    llamaDefaultModel = lib.mkOption {
      type = lib.types.str;
      default = "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF";
      description = "Default llama.cpp model identifier written into the AI stack env ConfigMap.";
    };

    llamaModelFile = lib.mkOption {
      type = lib.types.str;
      default = "qwen2.5-coder-7b-instruct-q4_k_m.gguf";
      description = "Default llama.cpp GGUF filename written into the AI stack env ConfigMap.";
    };

    namespace = lib.mkOption {
      type = lib.types.str;
      default = "ai-stack";
      description = "Kubernetes namespace containing the AI stack resources and env ConfigMap.";
    };

    manifestPath = lib.mkOption {
      type = lib.types.path;
      default = ../../.. + "/ai-stack/kubernetes";
      description = "Path to the AI stack Kubernetes kustomization directory used by the reconciliation service.";
    };

    reconcileIntervalMinutes = lib.mkOption {
      type = lib.types.ints.positive;
      default = 15;
      description = "How often to re-run Kubernetes reconciliation for the AI stack manifests.";
    };

    kubectlTimeout = lib.mkOption {
      type = lib.types.str;
      default = "60s";
      description = "kubectl request timeout for API checks and apply operations.";
    };

    disableMarkerPath = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/nixos-quick-deploy/disable-ai-stack";
      description = "When this marker file exists, AI stack manifest reconciliation is skipped.";
    };
  };

  config = lib.mkIf (roleEnabled && cfg.enable && config.mySystem.aiStack.backend == "k3s") {
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
  };
}
