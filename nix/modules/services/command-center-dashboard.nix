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
  dashboardFrontendRoot = "${dashboardRoot}/dashboard/frontend";
  dashboardFrontendDist = "${dashboardFrontendRoot}/dist";

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
      "d ${cc.dataDir}/npm-cache 0750 ${svcUser} ${svcGroup} -"
    ];

    # ── Frontend TypeScript build (oneshot) ───────────────────────────────────
    # Runs `npm run build` (tsc + vite) before the API service starts.
    # Triggered automatically on: first boot, nixos-rebuild switch, or manual
    # `systemctl start command-center-dashboard-build`.
    # RemainAfterExit keeps the unit "active" so the API does not restart it.
    systemd.services.command-center-dashboard-build = {
      description = "Build NixOS Command Center Dashboard frontend (TypeScript → dist/)";
      wantedBy = [ "command-center-dashboard-api.service" ];
      before = [ "command-center-dashboard-api.service" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        User = svcUser;
        Group = svcGroup;
        WorkingDirectory = dashboardFrontendRoot;
        NoNewPrivileges = true;
        # npm lifecycle scripts (esbuild, etc.) call spawn('sh'/'python3').
        # Keep ProtectSystem strict but give write access to the build dirs
        # and redirect npm cache so it stays inside cc.dataDir.
        ProtectSystem = "strict";
        ReadWritePaths = [
          dashboardFrontendRoot
          "${cc.dataDir}/npm-cache"
          "/tmp"
        ];
        # Increase timeout for first-time npm install (large dep tree)
        TimeoutStartSec = "300";
      };
      # PATH needs: node+npm, bash (sh alias), coreutils (cp/mkdir/…), python3
      # (esbuild postinstall), git (some lifecycle hooks).
      path = with pkgs; [ nodejs bash coreutils python3 git ];
      environment = {
        # Redirect npm cache + logs out of ~/.npm (which may be read-only
        # under strict sandboxing) into cc.dataDir/npm-cache.
        npm_config_cache = "${cc.dataDir}/npm-cache";
        # Suppress interactive prompts.
        CI = "true";
      };
      script = ''
        set -euo pipefail

        # Install dependencies when node_modules is absent or stale.
        if [[ ! -d node_modules ]] || \
           [[ package-lock.json -nt node_modules/.package-lock.json ]]; then
          echo "Installing npm dependencies…"
          npm ci 2>/dev/null || npm install
        fi

        echo "Building frontend (tsc + vite)…"
        npm run build

        echo "Frontend build complete: ${dashboardFrontendDist}"
      '';
    };

    # ── API + SPA backend ─────────────────────────────────────────────────────
    # Serves both the FastAPI backend (/api/*) and the compiled React SPA (/).
    # Replaces the old python3 -m http.server frontend service.
    systemd.services.command-center-dashboard-api = {
      description = "NixOS Command Center Dashboard API";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" "prometheus.service"
                "command-center-dashboard-build.service" ]
        ++ lib.optionals cfg.roles.aiStack.enable [ "ai-stack.target" ];
      wants = [ "network-online.target" "prometheus.service"
                "command-center-dashboard-build.service" ]
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
        # Frontend dist — served as SPA by FastAPI StaticFiles
        DASHBOARD_FRONTEND_DIST = dashboardFrontendDist;
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

    # Dashboard is now single-port: the API serves both /api/* and the SPA.
    # The old cc.frontendPort (python http.server) is retired.
    networking.firewall.allowedTCPPorts = lib.mkIf mon.listenOnLan [
      cc.apiPort
    ];
  };
}
