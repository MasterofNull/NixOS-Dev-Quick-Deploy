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
  ]);
in
{
  config = lib.mkIf (mon.enable && cc.enable) {
    systemd.tmpfiles.rules = [
      "d ${cc.dataDir} 0750 ${svcUser} ${svcGroup} -"
      "d ${cc.dataDir}/telemetry 0750 ${svcUser} ${svcGroup} -"
    ];

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
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadOnlyPaths = [ dashboardRoot ];
        ReadWritePaths = [ cc.dataDir "/tmp" ];
      };
      environment = {
        SERVICE_HOST = "127.0.0.1";
        PROMETHEUS_PORT = toString mon.prometheusPort;
        DASHBOARD_API_BIND_ADDRESS = cc.bindAddress;
        DASHBOARD_API_PORT = toString cc.apiPort;
        DASHBOARD_MODE = "systemd";
        AIDB_URL = "http://127.0.0.1:${toString mcp.aidbPort}";
        HYBRID_URL = "http://127.0.0.1:${toString mcp.hybridPort}";
        RALPH_URL = "http://127.0.0.1:${toString mcp.ralphPort}";
        QDRANT_URL = "http://127.0.0.1:${toString ports.qdrantHttp}";
        LLAMA_URL = "http://127.0.0.1:${toString cfg.aiStack.llamaCpp.port}";
        EMBEDDINGS_URL = "http://127.0.0.1:${toString cfg.aiStack.embeddingServer.port}";
        SWITCHBOARD_URL = "http://127.0.0.1:${toString cfg.aiStack.switchboard.port}";
        EMBEDDINGS_PORT = toString cfg.aiStack.embeddingServer.port;
        SWITCHBOARD_PORT = toString cfg.aiStack.switchboard.port;
        EMBEDDING_DIMENSIONS = toString cfg.aiStack.embeddingDimensions;
      } // lib.optionalAttrs sec.enable {
        HYBRID_API_KEY_FILE = secretPath hybridApiKeySecret;
      };
      script = ''
        export PYTHONPATH="${dashboardBackendRoot}"
        exec ${dashboardPython}/bin/uvicorn api.main:app --host "${cc.bindAddress}" --port "${toString cc.apiPort}"
      '';
    };

    systemd.services.command-center-dashboard-frontend = {
      description = "NixOS Command Center Dashboard Frontend";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" "command-center-dashboard-api.service" ];
      wants = [ "network-online.target" "command-center-dashboard-api.service" ];
      serviceConfig = {
        Type = "simple";
        User = svcUser;
        Group = svcGroup;
        Restart = "on-failure";
        RestartSec = "5s";
        WorkingDirectory = dashboardRoot;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadOnlyPaths = [ dashboardRoot ];
        ReadWritePaths = [ cc.dataDir "/tmp" ];
      };
      environment = {
        DASHBOARD_PORT = toString cc.frontendPort;
        DASHBOARD_BIND_ADDRESS = cc.bindAddress;
        DASHBOARD_DATA_DIR = cc.dataDir;
        SERVICE_HOST = "127.0.0.1";
        DASHBOARD_API_URL = "http://127.0.0.1:${toString cc.apiPort}";
      };
      script = ''
        exec ${pkgs.python3}/bin/python3 -m http.server \
          "${toString cc.frontendPort}" \
          --bind "${cc.bindAddress}" \
          --directory "${dashboardRoot}"
      '';
    };

    networking.firewall.allowedTCPPorts = lib.mkIf mon.listenOnLan [
      cc.frontendPort
      cc.apiPort
    ];
  };
}
