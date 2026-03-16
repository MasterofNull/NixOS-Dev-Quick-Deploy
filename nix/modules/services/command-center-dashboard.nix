{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  ports = cfg.ports;
  mon = cfg.monitoring;
  cc = mon.commandCenter;
  mcp = cfg.mcpServers;
  sec = cfg.secrets;
  svcUser = cfg.primaryUser;
  svcGroup = lib.attrByPath [ "users" "users" svcUser "group" ] "users" config;
  secretPath = name: config.sops.secrets.${name}.path;
  hybridApiKeySecret = sec.names.hybridApiKey;

  dashboardRoot = "${mcp.repoPath}";
  dashboardBackendRoot = "${dashboardRoot}/dashboard/backend";
  dashboardPublicDir = "${dashboardRoot}/dashboard/public";

  dashboardPython = pkgs.python3.withPackages (ps: with ps; [
    fastapi
    uvicorn
    pydantic
    pydantic-settings
    python-dotenv
    websockets
    psutil
    aiofiles
    aiohttp
    asyncpg
  ]);
in
{
  config = lib.mkIf (mon.enable && cc.enable) {
    systemd.tmpfiles.rules = [
      "d ${cc.dataDir} 0750 ${svcUser} ${svcGroup} -"
      "d ${cc.dataDir}/telemetry 0750 ${svcUser} ${svcGroup} -"
      # Dashboard needs /run/sudo/ts for sudo -n systemctl operations
      "d /run/sudo 0711 root root -"
      "d /run/sudo/ts 0700 ${svcUser} ${svcGroup} -"
    ];

    # ── API + dashboard serving ────────────────────────────────────────────────
    # Production authority for the command center dashboard.
    # This service serves both the FastAPI backend (/api/*) and the operator UI
    # (/) from a single port. The current operator surface is the static
    # dashboard/public application mounted by the backend.
    systemd.services.command-center-dashboard-api = {
      description = "NixOS Command Center Dashboard API";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" "prometheus.service" ]
        ++ lib.optionals cfg.roles.aiStack.enable [ "ai-stack.target" ];
      wants = [ "network-online.target" "prometheus.service" ]
        ++ lib.optionals cfg.roles.aiStack.enable [ "ai-stack.target" ];
      serviceConfig = {
        Type = "simple";
        User = svcUser;
        Group = svcGroup;
        Restart = "on-failure";
        RestartSec = "5s";
        WorkingDirectory = dashboardBackendRoot;
        # The dashboard executes a tightly bounded set of sudo -n systemctl
        # operations for operator service control. NoNewPrivileges blocks that
        # escalation path entirely, so keep it disabled while ReadOnlyPaths and
        # NixOS sudo allowlists constrain what can run.
        NoNewPrivileges = false;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadOnlyPaths = [ dashboardRoot ];
        ReadWritePaths = [
          cc.dataDir
          "/tmp"
          "/run/sudo/ts"
          "${dashboardRoot}/docs/development"
          "${dashboardRoot}/data"
        ];
      };
      environment = {
        SERVICE_HOST = "127.0.0.1";
        PROMETHEUS_PORT = toString mon.prometheusPort;
        DASHBOARD_API_BIND_ADDRESS = cc.bindAddress;
        DASHBOARD_API_PORT = toString cc.apiPort;
        DASHBOARD_MODE = "systemd";
        DASHBOARD_EXPOSE_HOSTNAME = "false";
        DASHBOARD_HOSTNAME_ALIAS = "local-node";
        DASHBOARD_FRONTEND_DIST = dashboardPublicDir;
        AIDB_URL = "http://127.0.0.1:${toString mcp.aidbPort}";
        HYBRID_URL = "http://127.0.0.1:${toString mcp.hybridPort}";
        RALPH_URL = "http://127.0.0.1:${toString mcp.ralphPort}";
        QDRANT_URL = "http://127.0.0.1:${toString ports.qdrantHttp}";
        LLAMA_URL = "http://127.0.0.1:${toString cfg.aiStack.llamaCpp.port}";
        EMBEDDINGS_URL = "http://127.0.0.1:${toString cfg.aiStack.embeddingServer.port}";
        SWITCHBOARD_URL = "http://127.0.0.1:${toString cfg.aiStack.switchboard.port}";
        AIDER_WRAPPER_URL = "http://127.0.0.1:${toString mcp.aiderWrapperPort}";
        NIXOS_DOCS_URL = "http://127.0.0.1:${toString mcp.nixosDocsPort}";
        EMBEDDINGS_PORT = toString cfg.aiStack.embeddingServer.port;
        SWITCHBOARD_PORT = toString cfg.aiStack.switchboard.port;
        EMBEDDING_DIMENSIONS = toString cfg.aiStack.embeddingDimensions;
        POSTGRES_PORT = toString ports.postgres;
        AIDB_DB_USER = mcp.postgres.user;
        AIDB_DB_NAME = mcp.postgres.database;
        BASH_BIN = "${pkgs.bash}/bin/bash";
        PRSI_ACTION_QUEUE_PATH = "${cc.dataDir}/telemetry/prsi-action-queue.json";
        PRSI_ACTIONS_LOG_PATH = "${cc.dataDir}/telemetry/prsi-actions.jsonl";
        PRSI_POLICY_FILE = "${mcp.repoPath}/config/runtime-prsi-policy.json";
        PRSI_STATE_PATH = "${cc.dataDir}/telemetry/prsi-runtime-state.json";
        OPTIMIZER_OVERRIDES_ENV = "${cc.dataDir}/telemetry/optimizer-overrides.env";
        OPTIMIZER_ACTIONS_LOG = "${cc.dataDir}/telemetry/optimizer-actions.jsonl";
        AI_SECURITY_AUDIT_DIR = "${mcp.dataDir}/security";
        AI_NPM_SECURITY_DIR = "${mcp.dataDir}/security/npm";
      } // lib.optionalAttrs sec.enable {
        HYBRID_API_KEY_FILE = secretPath hybridApiKeySecret;
        POSTGRES_PASSWORD_FILE = secretPath sec.names.postgresPassword;
      };
      script = ''
        export PYTHONPATH="${dashboardBackendRoot}"
        exec ${dashboardPython}/bin/uvicorn api.main:app \
          --host "${cc.bindAddress}" \
          --port "${toString cc.apiPort}"
      '';
    };

    networking.firewall.allowedTCPPorts = lib.mkIf mon.listenOnLan [
      cc.apiPort
    ];
  };
}
