{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem.aiStack;
  roleEnabled = config.mySystem.roles.aiStack.enable;

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
  # The ollama backend is handled by nix/modules/roles/ai-stack.nix.
  # This module only handles the K3s backend.
  config = lib.mkIf (roleEnabled && cfg.enable) (lib.mkMerge [

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
