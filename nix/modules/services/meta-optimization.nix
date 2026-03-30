{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem.aiStack.metaOptimization;
  aiStackCfg = config.mySystem.aiStack;
  ports = config.mySystem.ports;
  svcUser = config.mySystem.primaryUser;
  svcGroup = lib.attrByPath [ "users" "users" svcUser "group" ] "users" config;
  sec = config.mySystem.secrets;
  secretPath = name: config.sops.secrets.${name}.path;

  metaOptRoot = "${aiStackCfg.repoPath}/ai-stack/meta-optimization";

  metaOptPython = pkgs.python3.withPackages (ps: with ps; [
    asyncpg
    aiohttp
    psycopg2
  ]);
in
{
  options.mySystem.aiStack.metaOptimization = {
    enable = lib.mkEnableOption "AI harness meta-optimization service";

    dataDir = lib.mkOption {
      type = lib.types.path;
      default = "/var/lib/ai-stack/meta-optimization";
      description = "Data directory for meta-optimization state";
    };

    analysisIntervalHours = lib.mkOption {
      type = lib.types.int;
      default = 24;
      description = "Hours between meta-optimization analysis runs";
    };

    analysisWindowDays = lib.mkOption {
      type = lib.types.int;
      default = 7;
      description = "Days of historical data to analyze";
    };

    autoApplyProposals = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Automatically apply high-confidence improvement proposals (dangerous!)";
    };
  };

  config = lib.mkIf cfg.enable {
    # Ensure meta-optimization directory exists
    systemd.tmpfiles.rules = [
      "d ${cfg.dataDir} 0750 ${svcUser} ${svcGroup} -"
      "d ${cfg.dataDir}/proposals 0750 ${svcUser} ${svcGroup} -"
      "d ${cfg.dataDir}/baselines 0750 ${svcUser} ${svcGroup} -"
    ];

    # Meta-optimization analysis service (runs periodically)
    systemd.services.meta-optimization-analysis = {
      description = "AI Harness Meta-Optimization Analysis";
      after = [ "network-online.target" "postgresql.service" ]
        ++ lib.optionals aiStackCfg.enable [ "ai-stack.target" ];
      wants = [ "network-online.target" ];
      requires = [ "postgresql.service" ];

      serviceConfig = {
        Type = "oneshot";
        User = svcUser;
        Group = svcGroup;
        WorkingDirectory = metaOptRoot;

        # Security hardening
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadOnlyPaths = [ aiStackCfg.repoPath ];
        ReadWritePaths = [ cfg.dataDir ];
        PrivateTmp = true;
        NoNewPrivileges = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
      };

      environment = {
        POSTGRES_HOST = "127.0.0.1";
        POSTGRES_PORT = toString ports.postgres;
        POSTGRES_USER = aiStackCfg.postgres.user;
        POSTGRES_DB = aiStackCfg.postgres.database;
        LLAMA_CHAT_URL = "http://127.0.0.1:${toString aiStackCfg.llamaCpp.port}";
        META_OPT_DATA_DIR = cfg.dataDir;
        ANALYSIS_WINDOW_DAYS = toString cfg.analysisWindowDays;
      } // lib.optionalAttrs sec.enable {
        POSTGRES_PASSWORD_FILE = secretPath sec.names.postgresPassword;
      };

      script = ''
        # Read PostgreSQL password if available
        if [ -n "$POSTGRES_PASSWORD_FILE" ] && [ -f "$POSTGRES_PASSWORD_FILE" ]; then
          export POSTGRES_PASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
        fi

        # Run meta-optimization analysis
        exec ${metaOptPython}/bin/python3 ${metaOptRoot}/meta_optimizer.py \
          --days "$ANALYSIS_WINDOW_DAYS" \
          --output-dir "${cfg.dataDir}/proposals"
      '';
    };

    # Timer for periodic meta-optimization analysis
    systemd.timers.meta-optimization-analysis = {
      description = "Timer for AI Harness Meta-Optimization Analysis";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "1h";  # First run 1 hour after boot
        OnUnitActiveSec = "${toString cfg.analysisIntervalHours}h";
        Persistent = true;  # Catch up missed runs after downtime
        RandomizedDelaySec = "30m";  # Spread load
      };
    };

    # Evolution tracker service (captures baselines and validates impacts)
    systemd.services.meta-optimization-validator = {
      description = "AI Harness Evolution Impact Validator";
      after = [ "network-online.target" "postgresql.service" ]
        ++ lib.optionals aiStackCfg.enable [ "ai-stack.target" ];
      wants = [ "network-online.target" ];
      requires = [ "postgresql.service" ];

      serviceConfig = {
        Type = "oneshot";
        User = svcUser;
        Group = svcGroup;
        WorkingDirectory = metaOptRoot;

        # Security hardening
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadOnlyPaths = [ aiStackCfg.repoPath ];
        ReadWritePaths = [ cfg.dataDir ];
        PrivateTmp = true;
        NoNewPrivileges = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
      };

      environment = {
        POSTGRES_HOST = "127.0.0.1";
        POSTGRES_PORT = toString ports.postgres;
        POSTGRES_USER = aiStackCfg.postgres.user;
        POSTGRES_DB = aiStackCfg.postgres.database;
        REPO_ROOT = aiStackCfg.repoPath;
        META_OPT_DATA_DIR = cfg.dataDir;
      } // lib.optionalAttrs sec.enable {
        POSTGRES_PASSWORD_FILE = secretPath sec.names.postgresPassword;
      };

      script = ''
        # Read PostgreSQL password if available
        if [ -n "$POSTGRES_PASSWORD_FILE" ] && [ -f "$POSTGRES_PASSWORD_FILE" ]; then
          export POSTGRES_PASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
        fi

        # Capture performance baselines
        ${metaOptPython}/bin/python3 -c '
import asyncio
import os
import sys
sys.path.insert(0, "${metaOptRoot}")
from harness_evolution_tracker import HarnessEvolutionTracker

async def main():
    tracker = HarnessEvolutionTracker(
        pg_host="127.0.0.1",
        pg_port=${toString ports.postgres},
        pg_user="${aiStackCfg.postgres.user}",
        pg_database="${aiStackCfg.postgres.database}",
        pg_password=os.getenv("POSTGRES_PASSWORD", "")
    )
    await tracker.connect()

    try:
        # Capture baselines for key metrics
        await tracker.capture_baseline("routing_accuracy", component="route_handler", window_hours=24)
        await tracker.capture_baseline("avg_route_latency_ms", component="route_handler", window_hours=24)
        await tracker.capture_baseline("hint_success_rate", component="hints_engine", window_hours=24)

        # Get summary
        summary = await tracker.get_evolution_summary(days=30)
        print(f"Evolution summary: {summary}")
    finally:
        await tracker.close()

asyncio.run(main())
'
      '';
    };

    # Timer for baseline capture and validation
    systemd.timers.meta-optimization-validator = {
      description = "Timer for Evolution Impact Validation";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = "15m";
      } // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
        DeferReactivation = true;
      };
    };

    # Optional: Apply approved proposals automatically
    systemd.services.meta-optimization-applier = lib.mkIf cfg.autoApplyProposals {
      description = "AI Harness Meta-Optimization Auto-Applier";
      after = [ "meta-optimization-analysis.service" ];
      requires = [ "meta-optimization-analysis.service" ];

      serviceConfig = {
        Type = "oneshot";
        User = svcUser;
        Group = svcGroup;
        WorkingDirectory = aiStackCfg.repoPath;

        # More restrictive - can modify repo
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadWritePaths = [
          aiStackCfg.repoPath
          cfg.dataDir
        ];
        PrivateTmp = true;
        NoNewPrivileges = true;
      };

      environment = {
        POSTGRES_HOST = "127.0.0.1";
        POSTGRES_PORT = toString ports.postgres;
        POSTGRES_USER = aiStackCfg.postgres.user;
        POSTGRES_DB = aiStackCfg.postgres.database;
        REPO_ROOT = aiStackCfg.repoPath;
      } // lib.optionalAttrs sec.enable {
        POSTGRES_PASSWORD_FILE = secretPath sec.names.postgresPassword;
      };

      script = ''
        echo "⚠️  Auto-apply is ENABLED - this will modify harness code automatically!"

        # TODO: Implement safe auto-application logic
        # 1. Fetch approved proposals from database
        # 2. Apply changes to code
        # 3. Run validation tests
        # 4. Commit if tests pass
        # 5. Record in evolution history

        echo "Auto-apply not yet implemented - manual review required"
        exit 0
      '';
    };
  };
}
