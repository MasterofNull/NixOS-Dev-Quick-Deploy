# Data retention — daily trim of temporal_facts.json and snapshot JSONL files.
# Prevents unbounded growth of AI harness telemetry on edge devices.
#
# Usage:
#   services.data-retention.enable = true;
{ config, lib, pkgs, ... }:

let
  cfg = config.services.data-retention;

  trimFactsScript = pkgs.writeShellScript "data-retention-trim-facts" ''
    set -euo pipefail
    export TEMPORAL_FACTS_FILE="${cfg.temporalFactsFile}"
    export TEMPORAL_FACTS_RETENTION_DAYS="${toString cfg.temporalFactsDays}"
    exec ${pkgs.bash}/bin/bash ${cfg.scriptsDir}/data/trim-temporal-facts.sh
  '';

  trimSnapshotsScript = pkgs.writeShellScript "data-retention-trim-snapshots" ''
    set -euo pipefail
    export SNAPSHOTS_DIR="${cfg.snapshotsDir}"
    export SNAPSHOTS_RETENTION_DAYS="${toString cfg.snapshotsDays}"
    exec ${pkgs.bash}/bin/bash ${cfg.scriptsDir}/data/trim-snapshots.sh
  '';

  combinedScript = pkgs.writeShellScript "data-retention-run" ''
    set -euo pipefail
    ${trimFactsScript}
    ${trimSnapshotsScript}
  '';

in
{
  options.services.data-retention = {
    enable = lib.mkEnableOption "AI harness data retention trimmer";

    user = lib.mkOption {
      type = lib.types.str;
      default = "root";
      description = "User to run the retention scripts as (must have write access to the data files).";
    };

    scriptsDir = lib.mkOption {
      type = lib.types.path;
      description = "Path to the repo's scripts/ directory (contains data/trim-*.sh).";
      example = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts";
    };

    temporalFactsFile = lib.mkOption {
      type = lib.types.str;
      description = "Absolute path to temporal_facts.json.";
      example = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.aidb/temporal_facts.json";
    };

    temporalFactsDays = lib.mkOption {
      type = lib.types.int;
      default = 30;
      description = "Retain temporal facts from the last N days.";
    };

    snapshotsDir = lib.mkOption {
      type = lib.types.str;
      description = "Absolute path to the snapshots directory containing *.jsonl files.";
      example = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/snapshots";
    };

    snapshotsDays = lib.mkOption {
      type = lib.types.int;
      default = 7;
      description = "Retain snapshot entries from the last N days.";
    };

    interval = lib.mkOption {
      type = lib.types.str;
      default = "daily";
      example = "weekly";
      description = "How often to run retention (systemd calendar format).";
    };

    onBoot = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run once on boot (after a short delay) in addition to the scheduled interval.";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.timers.data-retention = {
      description = "AI harness data retention timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.interval;
        Persistent = true;
        RandomizedDelaySec = "10min";
      } // lib.optionalAttrs cfg.onBoot {
        OnBootSec = "10min";
      };
    };

    systemd.services.data-retention = {
      description = "AI harness data retention (trim temporal facts and snapshots)";

      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        ExecStart = combinedScript;
        TimeoutStartSec = "5min";

        # Hardening
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictNamespaces = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
      };
    };
  };
}
