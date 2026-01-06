{ config, pkgs, lib, ... }:

# NixOS module for automatic AI stack orphaned process cleanup
# Part of: NixOS-Dev-Quick-Deploy
# Purpose: Prevents orphaned processes from previous container runs
#
# Usage:
#   imports = [ ./ai-stack-cleanup.nix ];
#   services.ai-stack-cleanup.enable = true;

let
  cfg = config.services.ai-stack-cleanup;

  cleanupScript = pkgs.writeShellScript "cleanup-ai-stack-orphans" ''
    set -euo pipefail

    info() { echo "ℹ $*"; }
    success() { echo "✓ $*"; }
    warn() { echo "⚠ $*"; }

    info "Scanning for orphaned AI stack processes..."
    killed_count=0

    # AI stack ports
    declare -A AI_PORTS=(
      [8091]="aidb-http"
      [8791]="aidb-websocket"
      [8092]="hybrid-coordinator"
      [8094]="nixos-docs"
      [3001]="open-webui"
      [8098]="ralph-wiggum"
    )

    # Check each port for orphaned processes
    for port in "''${!AI_PORTS[@]}"; do
      service="''${AI_PORTS[$port]}"

      if pid=$(${pkgs.lsof}/bin/lsof -ti:$port 2>/dev/null); then
        process_cmd=$(${pkgs.procps}/bin/ps -p "$pid" -o cmd= 2>/dev/null || echo "unknown")

        if echo "$process_cmd" | ${pkgs.gnugrep}/bin/grep -qE "(server\.py|uvicorn.*open_webui|tool_discovery|continuous_learning)"; then
          warn "Found orphaned $service process on port $port (PID: $pid)"

          if kill -9 "$pid" 2>/dev/null; then
            success "Killed orphaned process $pid"
            ((killed_count++))
          fi

          sleep 0.5
        fi
      fi
    done

    # Check for orphaned processes by pattern
    for pattern in "start_with_discovery.sh" "start_with_learning.sh" \
                   "tool_discovery_daemon.py" "continuous_learning_daemon.py" \
                   "self_healing_daemon.py"; do
      if pids=$(${pkgs.procps}/bin/pgrep -f "$pattern" 2>/dev/null); then
        for pid in $pids; do
          cgroup=$(cat /proc/$pid/cgroup 2>/dev/null | head -1 || echo "")

          if ! echo "$cgroup" | ${pkgs.gnugrep}/bin/grep -qE "(podman|docker|libpod)"; then
            warn "Killing orphaned process: $pattern (PID: $pid)"
            kill -9 "$pid" 2>/dev/null || true
            ((killed_count++))
            sleep 0.5
          fi
        done
      fi
    done

    info "Cleanup complete - killed $killed_count orphaned processes"
  '';

in {
  options.services.ai-stack-cleanup = {
    enable = lib.mkEnableOption "AI stack orphaned process cleanup service";

    onBoot = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run cleanup automatically on system boot";
    };

    onShutdown = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Run cleanup on system shutdown (prevents orphans)";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.services.ai-stack-cleanup = {
      description = "Cleanup orphaned AI stack processes";
      documentation = [ "https://github.com/yourusername/NixOS-Dev-Quick-Deploy" ];

      # Run before podman/docker services start
      before = [ "podman.service" "docker.service" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${cleanupScript}";
        RemainAfterExit = true;
        StandardOutput = "journal";
        StandardError = "journal";

        # Security hardening
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        NoNewPrivileges = false;  # Need privileges to kill processes
      };

      # Run on boot if enabled
      wantedBy = lib.mkIf cfg.onBoot [ "multi-user.target" ];
    };

    # Optional: Run cleanup on shutdown to prevent orphans
    systemd.services.ai-stack-cleanup-shutdown = lib.mkIf cfg.onShutdown {
      description = "Cleanup AI stack processes before shutdown";
      before = [ "shutdown.target" ];
      conflicts = [ "shutdown.target" ];

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${cleanupScript}";
        StandardOutput = "journal";
        StandardError = "journal";
      };

      wantedBy = [ "shutdown.target" ];
    };
  };
}
