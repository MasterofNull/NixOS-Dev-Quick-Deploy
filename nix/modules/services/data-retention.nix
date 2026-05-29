# Data retention — daily trim of temporal_facts.json and snapshot JSONL files.
# Prevents unbounded growth of AI harness telemetry on edge devices.
#
# Usage:
#   services.data-retention.enable = true;
{
  config,
  lib,
  pkgs,
  ...
}: let
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

  trimAiLogsScript = pkgs.writeShellScript "data-retention-trim-ai-logs" ''
    set -euo pipefail
    export REPO_ROOT="${cfg.repoRoot}"
    export AI_LOGS_AUDIT_SIDECAR_DAYS="${toString cfg.aiLogs.auditSidecarDays}"
    export AI_LOGS_HINT_AUDIT_DAYS="${toString cfg.aiLogs.hintAuditDays}"
    export AI_LOGS_HYBRID_EVENTS_DAYS="${toString cfg.aiLogs.hybridEventsDays}"
    export AI_LOGS_DELEGATION_FEEDBACK_DAYS="${toString cfg.aiLogs.delegationFeedbackDays}"
    export AI_LOGS_DELEGATION_OUTPUTS_DAYS="${toString cfg.aiLogs.delegationOutputsDays}"
    export AI_LOGS_USER_SPOOL_DAYS="${toString cfg.aiLogs.userSpoolDays}"
    export AI_LOGS_AIDB_EVENTS_DAYS="${toString cfg.aiLogs.aidbEventsDays}"
    export AI_LOGS_WORKFLOW_SESSIONS_DAYS="${toString cfg.aiLogs.workflowSessionsDays}"
    exec ${pkgs.bash}/bin/bash ${cfg.scriptsDir}/data/trim-ai-logs.sh
  '';

  combinedScript = pkgs.writeShellScript "data-retention-run" ''
    set -euo pipefail
    ${trimFactsScript}
    ${trimSnapshotsScript}
    ${lib.optionalString cfg.aiLogs.enable "${trimAiLogsScript}"}
  '';
in {
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

    repoRoot = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Absolute path to the repo root (required for aiLogs user-spool and delegation output cleanup).";
      example = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy";
    };

    aiLogs = {
      enable = lib.mkEnableOption "AI stack log decay (audit sidecar, hint-audit, hybrid-events, delegation outputs)";

      auditSidecarDays = lib.mkOption {
        type = lib.types.int;
        default = 7;
        description = "Days to retain entries in /var/log/ai-audit-sidecar/tool-audit.jsonl.";
      };

      hintAuditDays = lib.mkOption {
        type = lib.types.int;
        default = 7;
        description = "Days to retain entries in /var/log/nixos-ai-stack/hint-audit.jsonl.";
      };

      hybridEventsDays = lib.mkOption {
        type = lib.types.int;
        default = 14;
        description = "Days to retain entries in /var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl.";
      };

      delegationFeedbackDays = lib.mkOption {
        type = lib.types.int;
        default = 30;
        description = "Days to retain entries in delegation-feedback.jsonl (longer — used for failure analysis).";
      };

      delegationOutputsDays = lib.mkOption {
        type = lib.types.int;
        default = 14;
        description = "Days to retain per-task output files in .agents/delegation/outputs/.";
      };

      userSpoolDays = lib.mkOption {
        type = lib.types.int;
        default = 14;
        description = "Days to retain entries in .agents/telemetry/hybrid-events.jsonl (user-space spool).";
      };

      aidbEventsDays = lib.mkOption {
        type = lib.types.int;
        default = 7;
        description = "Days to retain entries in /var/lib/ai-stack/aidb/telemetry/aidb-events.jsonl. Kept short to prevent the file from exceeding the 50 MB rotation threshold that would trigger a cross-service permission error.";
      };

      workflowSessionsDays = lib.mkOption {
        type = lib.types.int;
        default = 30;
        description = "Days to retain workflow sessions in /var/lib/ai-stack/hybrid/workflow-sessions.json (keyed by updated_at). 894-session / 6 MB bloat causes 64ms sync parse on every multi-turn load — trim aggressively.";
      };
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
      wantedBy = ["timers.target"];
      timerConfig =
        {
          OnCalendar = cfg.interval;
          Persistent = true;
          RandomizedDelaySec = "10min";
        }
        // lib.optionalAttrs cfg.onBoot {
          OnBootSec = "10min";
        };
    };

    systemd.services.data-retention = {
      description = "AI harness data retention (trim temporal facts and snapshots)";

      # Inject minimal PATH so shell scripts can call python3 / date / find.
      # Systemd services run with an empty PATH — without this, python3 is not found.
      path = with pkgs; [ python3 bash coreutils findutils ];

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
