# NixOS module for AI Stack auto-start on boot
# NOTE: K3s is the primary runtime (Phase 9).
#
# Usage: Add to configuration.nix imports:
#   imports = [ ./ai-stack-autostart.nix ];

{ config, pkgs, lib, ... }:

let
  # Replace @PROJECT_ROOT@ before importing this module.
  aiStackPath = "@PROJECT_ROOT@/ai-stack/kubernetes";
  kubeconfig = "/etc/rancher/k3s/k3s.yaml";
in
{
  # Create systemd service for AI stack
  systemd.services.ai-stack = {
    description = "NixOS AI Stack (K3s)";
    documentation = [ "https://github.com/NixOS/NixOS-Dev-Quick-Deploy" ];

    # Service dependencies
    after = [ "network-online.target" "k3s.service" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "multi-user.target" ];

    # Service configuration
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = "yes";
      WorkingDirectory = aiStackPath;

      # Wait for network to be fully ready
      ExecStartPre = "${pkgs.coreutils}/bin/sleep 5";

      # Start AI stack
      ExecStart = "${pkgs.kubectl}/bin/kubectl --kubeconfig=${kubeconfig} apply -k ${aiStackPath}";

      # Stop AI stack gracefully
      ExecStop = "${pkgs.kubectl}/bin/kubectl --kubeconfig=${kubeconfig} scale deploy -n ai-stack --replicas=0 --all";

      # Timeout settings
      TimeoutStartSec = 300;
      TimeoutStopSec = 120;

      # Environment
      Environment = "PATH=/run/current-system/sw/bin";
    };
  };

  # Optional: Create a timer for periodic health checks
  systemd.timers.ai-stack-health = {
    description = "AI Stack Health Check Timer";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "5min";
      OnUnitActiveSec = "15min";
      Unit = "ai-stack-health.service";
    };
  };

  systemd.services.ai-stack-health = {
    description = "AI Stack Health Check";
    serviceConfig = {
      Type = "oneshot";
      ExecStart = pkgs.writeShellScript "ai-stack-health-check" ''
        #!/bin/bash
        export KUBECONFIG=${kubeconfig}

        # Check if deployments are ready
        READY_COUNT=$(${pkgs.kubectl}/bin/kubectl get deploy -n ai-stack -o jsonpath='{range .items[*]}{.status.readyReplicas}{"\n"}{end}' | awk '$1>0{c++} END{print c+0}')
        if [ "$READY_COUNT" -lt 3 ]; then
          echo "WARNING: Less than 3 deployments ready. Rolling out restart..."
          ${pkgs.kubectl}/bin/kubectl rollout restart deploy -n ai-stack --all
        fi
      '';
    };
  };

  # Optional: User service for monitoring dashboard
  systemd.user.services.ai-stack-monitor = {
    description = "AI Stack Live Monitoring Dashboard";

    serviceConfig = {
      Type = "simple";
      ExecStart = "@PROJECT_ROOT@/scripts/ai-stack-monitor.sh";
      Restart = "on-failure";
      RestartSec = 10;
    };

    # Don't enable by default (users can start manually)
    # To enable: systemctl --user enable ai-stack-monitor
  };
}
