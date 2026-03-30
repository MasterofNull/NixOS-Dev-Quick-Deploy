# Lore Sync Service
# Periodically syncs patches from lore.kernel.org for monitored subsystems.
#
# Usage:
#   services.lore-sync = {
#     enable = true;
#     subsystems = [ "dri-devel" "netdev" ];
#     interval = "6h";
#   };
{ config, lib, pkgs, ... }:

let
  cfg = config.services.lore-sync;

  # Mailing list configurations
  mailingLists = {
    dri-devel = {
      url = "https://lore.kernel.org/dri-devel";
      email = "dri-devel@lists.freedesktop.org";
      description = "DRM/Graphics subsystem";
    };
    netdev = {
      url = "https://lore.kernel.org/netdev";
      email = "netdev@vger.kernel.org";
      description = "Networking subsystem";
    };
    linux-fsdevel = {
      url = "https://lore.kernel.org/linux-fsdevel";
      email = "linux-fsdevel@vger.kernel.org";
      description = "Filesystem development";
    };
    linux-mm = {
      url = "https://lore.kernel.org/linux-mm";
      email = "linux-mm@kvack.org";
      description = "Memory management";
    };
    linux-security-module = {
      url = "https://lore.kernel.org/linux-security-module";
      email = "linux-security-module@vger.kernel.org";
      description = "Security modules (LSM)";
    };
    linux-hardening = {
      url = "https://lore.kernel.org/linux-hardening";
      email = "linux-hardening@vger.kernel.org";
      description = "Kernel hardening";
    };
    rust-for-linux = {
      url = "https://lore.kernel.org/rust-for-linux";
      email = "rust-for-linux@vger.kernel.org";
      description = "Rust for Linux development";
    };
  };

  # Generate sync script
  syncScript = pkgs.writeShellScript "lore-sync" ''
    set -euo pipefail

    LORE_DIR="${cfg.dataDir}"
    AIDB_ENDPOINT="${cfg.aidbEndpoint}"
    LOG_FILE="/var/log/lore-sync/sync.log"

    log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }

    mkdir -p "$LORE_DIR" "$(dirname "$LOG_FILE")"

    log "Starting lore sync for subsystems: ${lib.concatStringsSep ", " cfg.subsystems}"

    ${lib.concatMapStrings (subsystem: ''
      log "Syncing ${subsystem}..."

      # Use public-inbox/lei if available, otherwise fetch via HTTP
      if command -v lei >/dev/null 2>&1; then
        lei q -o "$LORE_DIR/${subsystem}" \
          --threads \
          -f mboxrd \
          "l:${mailingLists.${subsystem}.email} AND dt:${toString cfg.lookbackDays}d.." \
          2>&1 | tee -a "$LOG_FILE" || true
      else
        # Fallback: fetch recent Atom feed
        ${pkgs.curl}/bin/curl -sf \
          "${mailingLists.${subsystem}.url}/new.atom" \
          -o "$LORE_DIR/${subsystem}.atom" 2>&1 | tee -a "$LOG_FILE" || true
      fi

      # Extract patch metadata and send to AIDB if available
      if ${pkgs.curl}/bin/curl -sf "$AIDB_ENDPOINT/health" >/dev/null 2>&1; then
        log "Reporting to AIDB..."
        # Count new patches (simplified - real implementation would parse mbox)
        patch_count=$(find "$LORE_DIR/${subsystem}" -type f -name "*.mbox" 2>/dev/null | wc -l || echo 0)
        ${pkgs.curl}/bin/curl -sf "$AIDB_ENDPOINT/kernel/lore/sync" \
          -H "Content-Type: application/json" \
          -d "{\"subsystem\": \"${subsystem}\", \"patch_count\": $patch_count}" \
          >/dev/null 2>&1 || true
      fi

    '') cfg.subsystems}

    log "Lore sync complete"
  '';

in
{
  options.services.lore-sync = {
    enable = lib.mkEnableOption "lore.kernel.org patch synchronization service";

    subsystems = lib.mkOption {
      type = lib.types.listOf (lib.types.enum (builtins.attrNames mailingLists));
      default = [ "linux-hardening" "rust-for-linux" ];
      example = [ "dri-devel" "netdev" "linux-fsdevel" ];
      description = ''
        Kernel subsystem mailing lists to monitor.
        Available: ${lib.concatStringsSep ", " (builtins.attrNames mailingLists)}
      '';
    };

    interval = lib.mkOption {
      type = lib.types.str;
      default = "6h";
      example = "1d";
      description = "How often to sync (systemd calendar format).";
    };

    lookbackDays = lib.mkOption {
      type = lib.types.int;
      default = 7;
      description = "Number of days to look back for patches.";
    };

    dataDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/lore-sync";
      description = "Directory to store synced patch data.";
    };

    aidbEndpoint = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:8002";
      description = "AIDB MCP server endpoint for reporting.";
    };

    useLei = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Use public-inbox/lei for fetching (recommended).";
    };
  };

  config = lib.mkIf cfg.enable {
    # Ensure required packages
    environment.systemPackages = lib.mkIf cfg.useLei [
      pkgs.public-inbox
    ];

    # Create data directory
    systemd.tmpfiles.rules = [
      "d ${cfg.dataDir} 0755 root root -"
      "d /var/log/lore-sync 0755 root root -"
    ];

    # Timer for periodic sync
    systemd.timers.lore-sync = {
      description = "Lore kernel patch sync timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "5min";
        OnUnitActiveSec = cfg.interval;
        RandomizedDelaySec = "10min";
        Persistent = true;
      } // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
        # systemd 257+: defer reactivation if service still running
        DeferReactivation = true;
      };
    };

    # Service for sync execution
    systemd.services.lore-sync = {
      description = "Lore kernel patch synchronization";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      serviceConfig = {
        Type = "oneshot";
        ExecStart = syncScript;
        TimeoutStartSec = "30min";

        # Hardening
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ReadWritePaths = [ cfg.dataDir "/var/log/lore-sync" ];
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
