{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem.aiStack;
  roleEnabled = config.mySystem.roles.aiStack.enable;
  primaryUser = config.mySystem.primaryUser;
  primaryHome = "/home/${primaryUser}";

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
  # The llama.cpp backend is handled by nix/modules/roles/ai-stack.nix.
  # This module only handles the K3s backend.
  config = lib.mkIf (roleEnabled && cfg.enable) (lib.mkMerge [

    # ── K3s backend ───────────────────────────────────────────────────────────
    (lib.mkIf (cfg.backend == "k3s") {

      services.k3s = {
        enable = lib.mkDefault true;
        role = lib.mkDefault "server";
        extraFlags = lib.mkAfter [
          "--write-kubeconfig=/etc/rancher/k3s/k3s.yaml"
          "--write-kubeconfig-mode=0644"
        ];
      };

      environment.sessionVariables.KUBECONFIG = lib.mkDefault "/etc/rancher/k3s/k3s.yaml";

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

      # Ensure kubectl works for the primary user without requiring manual
      # export/bootstrapping: seed ~/.kube/config from the K3s kubeconfig.
      systemd.services.nixos-ai-stack-kubeconfig-bootstrap = {
        description = "Bootstrap primary-user kubeconfig for K3s AI stack";
        after = [ "k3s.service" ];
        wants = [ "k3s.service" ];
        wantedBy = [ "multi-user.target" ];
        serviceConfig = {
          Type = "oneshot";
          User = "root";
        };
        script = ''
          set -euo pipefail
          kube_src="/etc/rancher/k3s/k3s.yaml"
          kube_dir="${primaryHome}/.kube"
          kube_dst="${primaryHome}/.kube/config"

          if [[ ! -f "$kube_src" ]]; then
            exit 0
          fi

          install -d -m 0750 -o ${primaryUser} -g ${primaryUser} "$kube_dir"
          install -m 0600 -o ${primaryUser} -g ${primaryUser} "$kube_src" "$kube_dst"
        '';
      };
    })

  ]);
}
