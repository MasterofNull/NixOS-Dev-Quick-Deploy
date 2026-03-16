{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Autonomous Improvement Service — local LLM-driven system optimization
#
# Activated when:
#   mySystem.roles.aiStack.enable = true
#   mySystem.mcpServers.enable = true
#   mySystem.aiStack.autonomousImprovement.enable = true
#
# Service architecture:
#   ai-autonomous-improvement.timer  — trigger every N hours
#   ai-autonomous-improvement.service — run one improvement cycle
#
# The autonomous loop uses the local LLM at localhost:8080 to:
#   1. Analyze system metrics and detect anomalies
#   2. Generate optimization hypotheses
#   3. Execute experiments via autoresearch framework
#   4. Validate improvements and apply changes
#   5. Record all decisions and results to PostgreSQL
#
# This is Phase 1 of the AI harness evolution:
#   Transform local LLM from passive responder to active decision-maker
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  ports = cfg.ports;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  autonomous = ai.autonomousImprovement;
  sec = cfg.secrets;

  active = cfg.roles.aiStack.enable && mcp.enable && autonomous.enable;

  repoPath = mcp.repoPath;
  autonomousDir = "${repoPath}/ai-stack/autonomous-improvement";
  dataDir = "${mcp.dataDir}/autonomous-improvement";

  # Python environment with dependencies for autonomous improvement
  autonomousPython = pkgs.python3.withPackages (ps: with ps; [
    # Core dependencies
    psycopg2
    aiohttp

    # Utilities
    python-dotenv
    pyyaml
  ]);

  # Common hardening base (tier-aware)
  mkHardenedService = import ../../lib/hardened-service.nix { inherit lib; };
  hardenedBase = mkHardenedService { tier = cfg.hardwareTier; };

  svcUser = cfg.primaryUser;
  svcGroup = lib.attrByPath [ "users" "users" svcUser "group" ] "users" config;

  secretPath = name: config.sops.secrets.${name}.path;
  postgresPasswordSecret = sec.names.postgresPassword;

in {
  options.mySystem.aiStack.autonomousImprovement = {
    enable = lib.mkEnableOption "autonomous improvement system (local LLM-driven optimization)";

    interval = lib.mkOption {
      type = lib.types.int;
      default = 60;
      description = "Check interval in minutes for autonomous improvement daemon";
    };

    dryRun = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Dry run mode - generate hypotheses but don't execute experiments";
    };
  };

  config = lib.mkMerge [
    (lib.mkIf active {
      # Ensure data directory exists
      systemd.tmpfiles.rules = [
        "d '${dataDir}' 0755 ${svcUser} ${svcGroup} - -"
        "d '${dataDir}/logs' 0755 ${svcUser} ${svcGroup} - -"
      ];

      # Autonomous improvement service (one-shot cycle)
      systemd.services.ai-autonomous-improvement = {
        description = "Autonomous Improvement - Local LLM-driven system optimization";
        partOf = [ "ai-stack.target" ];
        after = [
          "network-online.target"
          "postgresql.service"
          "llama-cpp.service"
        ];
        requires = [
          "postgresql.service"
          "llama-cpp.service"
        ];
        wants = [ "network-online.target" ];

        environment = {
          PYTHONPATH = autonomousDir;
          DATA_DIR = dataDir;
          POSTGRES_HOST = "127.0.0.1";
          POSTGRES_PORT = toString ports.postgres;
          POSTGRES_DB = mcp.postgres.database;
          POSTGRES_USER = mcp.postgres.user;
          LLM_URL = "http://localhost:${toString ai.llamaCpp.port}/v1/chat/completions";
        };

        script = ''
          ${lib.optionalString sec.enable ''
          export POSTGRES_PASSWORD="$(${pkgs.coreutils}/bin/tr -d '\n' < ${secretPath postgresPasswordSecret})"
          ''}

          exec ${autonomousPython}/bin/python3 \
            ${autonomousDir}/autonomous_loop.py \
            ${lib.optionalString autonomous.dryRun "--dry-run"}
        '';

        serviceConfig = hardenedBase // {
          Type = "oneshot";
          User = svcUser;
          Group = svcGroup;
          WorkingDirectory = autonomousDir;

          # Security hardening
          ProtectHome = "read-only";
          ReadWritePaths = [ dataDir mcp.dataDir ];
          ReadOnlyPaths = [ repoPath ];
          RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
          SystemCallFilter = [ "@system-service" ];
          SystemCallErrorNumber = "EPERM";
        };
      };

      # Timer to trigger autonomous improvement periodically
      systemd.timers.ai-autonomous-improvement = {
        description = "Autonomous Improvement Timer";
        wantedBy = [ "timers.target" ];
        partOf = [ "ai-stack.target" ];

        timerConfig = {
          OnBootSec = "10min";  # First run 10 minutes after boot
          OnUnitActiveSec = "${toString autonomous.interval}min";  # Subsequent runs
          Unit = "ai-autonomous-improvement.service";
          Persistent = true;  # Run missed timers on boot
        };
      };

      # Add CLI wrapper to system packages
      environment.systemPackages = [
        (pkgs.writeShellScriptBin "aq-autonomous-improve" ''
          exec "${repoPath}/scripts/ai/aq-autonomous-improve" "$@"
        '')
      ];
    })
  ];
}
