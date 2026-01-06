# NixOS module for AI Stack auto-start on boot
# Ensures podman-compose AI stack starts automatically after system reboot
#
# Usage: Add to configuration.nix imports:
#   imports = [ ./ai-stack-autostart.nix ];

{ config, pkgs, lib, ... }:

let
  aiStackPath = "/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose";
  userName = "hyperd";
in
{
  # Enable podman and podman-compose
  virtualisation.podman = {
    enable = true;
    dockerCompat = false;  # Don't create docker alias
    defaultNetwork.settings.dns_enabled = true;
  };

  # Ensure podman-compose is available
  environment.systemPackages = with pkgs; [
    podman-compose
  ];

  # Create systemd service for AI stack
  systemd.services.ai-stack = {
    description = "NixOS AI Stack (Podman Compose)";
    documentation = [ "https://github.com/NixOS/NixOS-Dev-Quick-Deploy" ];

    # Service dependencies
    requires = [ "podman.service" ];
    after = [ "network-online.target" "podman.service" ];
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
      ExecStart = "${pkgs.podman-compose}/bin/podman-compose up -d";

      # Stop AI stack gracefully
      ExecStop = "${pkgs.podman-compose}/bin/podman-compose down";

      # Timeout settings
      TimeoutStartSec = 300;
      TimeoutStopSec = 120;

      # Run as user, not root
      User = userName;
      Group = "users";

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
      User = userName;
      ExecStart = pkgs.writeShellScript "ai-stack-health-check" ''
        #!/bin/bash
        cd ${aiStackPath}

        # Check if containers are running
        RUNNING=$(${pkgs.podman}/bin/podman ps -q | wc -l)

        if [ "$RUNNING" -lt 5 ]; then
          echo "WARNING: Less than 5 containers running. Expected at least 10."
          # Auto-restart if needed
          ${pkgs.podman-compose}/bin/podman-compose up -d
        fi

        # Check critical services
        for service in local-ai-llama-cpp local-ai-qdrant local-ai-redis; do
          if ! ${pkgs.podman}/bin/podman ps --format '{{.Names}}' | grep -q "^$service$"; then
            echo "ERROR: $service is not running. Attempting restart..."
            ${pkgs.podman-compose}/bin/podman-compose restart "$service" || true
          fi
        done
      '';
    };
  };

  # Optional: User service for monitoring dashboard
  systemd.user.services.ai-stack-monitor = {
    description = "AI Stack Live Monitoring Dashboard";

    serviceConfig = {
      Type = "simple";
      ExecStart = "/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/ai-stack-monitor.sh";
      Restart = "on-failure";
      RestartSec = 10;
    };

    # Don't enable by default (users can start manually)
    # To enable: systemctl --user enable ai-stack-monitor
  };
}
