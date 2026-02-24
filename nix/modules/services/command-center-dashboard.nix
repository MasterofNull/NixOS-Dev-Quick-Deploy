{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  ports = cfg.ports;
  mon = cfg.monitoring;
  cc = mon.commandCenter;
  mcp = cfg.mcpServers;

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
    users.groups.command-center = { gid = 35012; };
    users.users.command-center = {
      isSystemUser = true;
      group = "command-center";
      description = "Command center dashboard services";
      home = cc.dataDir;
      createHome = true;
    };

    systemd.tmpfiles.rules = [
      "d ${cc.dataDir} 0750 command-center command-center -"
      "d ${cc.dataDir}/telemetry 0750 command-center command-center -"
    ];

    systemd.services.command-center-dashboard-api = {
      description = "NixOS Command Center Dashboard API";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" "prometheus.service" ];
      wants = [ "network-online.target" "prometheus.service" ];
      serviceConfig = {
        Type = "simple";
        User = "command-center";
        Group = "command-center";
        Restart = "on-failure";
        RestartSec = "5s";
        WorkingDirectory = dashboardBackendRoot;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ReadOnlyPaths = [ dashboardRoot ];
        ReadWritePaths = [ cc.dataDir "/tmp" ];
      };
      environment = {
        SERVICE_HOST = "127.0.0.1";
        PROMETHEUS_PORT = toString mon.prometheusPort;
        DASHBOARD_API_BIND_ADDRESS = cc.bindAddress;
        DASHBOARD_API_PORT = toString cc.apiPort;
        AIDB_URL = "http://127.0.0.1:${toString mcp.aidbPort}";
        HYBRID_URL = "http://127.0.0.1:${toString mcp.hybridPort}";
        RALPH_URL = "http://127.0.0.1:${toString mcp.ralphPort}";
        QDRANT_URL = "http://127.0.0.1:${toString ports.qdrantHttp}";
        LLAMA_URL = "http://127.0.0.1:${toString cfg.aiStack.llamaCpp.port}";
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
        User = "command-center";
        Group = "command-center";
        Restart = "on-failure";
        RestartSec = "5s";
        WorkingDirectory = dashboardRoot;
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
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
        exec ${pkgs.bash}/bin/bash "${dashboardRoot}/scripts/serve-dashboard.sh"
      '';
    };

    networking.firewall.allowedTCPPorts = lib.mkIf mon.listenOnLan [
      cc.frontendPort
      cc.apiPort
    ];
  };
}
