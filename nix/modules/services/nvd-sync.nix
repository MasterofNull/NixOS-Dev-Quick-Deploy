# NVD CVE Sync Service
# Periodically syncs Linux kernel CVEs from NIST NVD to AIDB.
#
# Usage:
#   services.nvd-sync.enable = true;
{ config, lib, pkgs, ... }:

let
  cfg = config.services.nvd-sync;
  aidbCfg = config.mySystem.mcpServers;

  syncScript = pkgs.writeShellScript "nvd-cve-sync" ''
    set -euo pipefail

    AIDB_ENDPOINT="${cfg.aidbEndpoint}"
    LOG_FILE="/var/log/nvd-sync/sync.log"

    log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }

    mkdir -p "$(dirname "$LOG_FILE")"

    log "Starting NVD CVE sync..."

    # Check if AIDB is available
    if ! ${pkgs.curl}/bin/curl -sf "$AIDB_ENDPOINT/health" >/dev/null 2>&1; then
      log "ERROR: AIDB not available at $AIDB_ENDPOINT"
      exit 1
    fi

    # Trigger CVE sync
    response=$(${pkgs.curl}/bin/curl -sf "$AIDB_ENDPOINT/kernel/cves/sync" \
      -X POST \
      -H "Content-Type: application/json" \
      ${lib.optionalString (cfg.fullSync) ''-d '{"full_sync": true}' ''} \
      2>&1) || {
      log "ERROR: CVE sync request failed"
      exit 1
    }

    log "CVE sync triggered: $response"

    # Also sync kernel releases
    if ${pkgs.curl}/bin/curl -sf "$AIDB_ENDPOINT/kernel/releases/sync" -X POST >/dev/null 2>&1; then
      log "Kernel releases sync triggered"
    fi

    log "NVD sync complete"
  '';

in
{
  options.services.nvd-sync = {
    enable = lib.mkEnableOption "NVD CVE synchronization service";

    aidbEndpoint = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:8002";
      description = "AIDB MCP server endpoint.";
    };

    interval = lib.mkOption {
      type = lib.types.str;
      default = "daily";
      example = "hourly";
      description = "How often to sync CVEs (systemd calendar format).";
    };

    fullSync = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Perform full CVE sync (slower, fetches all historical data).";
    };

    onBoot = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run sync shortly after boot.";
    };
  };

  config = lib.mkIf cfg.enable {
    # Create log directory
    systemd.tmpfiles.rules = [
      "d /var/log/nvd-sync 0755 root root -"
    ];

    # Timer for periodic sync
    systemd.timers.nvd-sync = {
      description = "NVD CVE sync timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.interval;
        Persistent = true;
        RandomizedDelaySec = "30min";
      } // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
        # systemd 257+: schedule the next run from service inactivity instead of
        # immediately retriggering after an overdue OnCalendar interval.
        DeferReactivation = true;
      } // lib.optionalAttrs cfg.onBoot {
        OnBootSec = "5min";
      };
    };

    # Service for sync execution
    systemd.services.nvd-sync = {
      description = "NVD CVE synchronization";
      after = [ "network-online.target" "aidb-mcp-server.service" ];
      wants = [ "network-online.target" ];

      serviceConfig = {
        Type = "oneshot";
        ExecStart = syncScript;
        TimeoutStartSec = "15min";

        # Hardening
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ReadWritePaths = [ "/var/log/nvd-sync" ];
        NoNewPrivileges = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictNamespaces = true;
        RestrictSUIDSGID = true;
        MemoryDenyWriteExecute = true;
        LockPersonality = true;
      };
    };
  };
}
