{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# MCP Server services — declarative NixOS systemd units.
#
# Activated when:
#   mySystem.roles.aiStack.enable = true
#   mySystem.mcpServers.enable    = true
#   mySystem.aiStack.backend      = "llamacpp"
#
# Service dependency order (boot → runtime):
#   qdrant.service (when vectorDb.enable)
#   postgresql.service (when mcpServers.postgres.enable)
#   redis-mcp.service (when mcpServers.redis.enable)
#   ai-embeddings.service       — sentence-transformers HTTP API on :8001
#   ai-aidb.service             — AIDB MCP + tool-discovery on :8002
#   ai-hybrid-coordinator.service — routing + continuous-learning on :8003
#   ai-ralph-wiggum.service     — loop orchestrator on :8004
#
# Python environments are hermetically built per service.
# All services run as the 'ai-stack' system user.
# ---------------------------------------------------------------------------
let
  cfg      = config.mySystem;
  ports    = cfg.ports;
  mcp      = cfg.mcpServers;
  ai       = cfg.aiStack;
  sec      = cfg.secrets;
  llama    = ai.llamaCpp;

  active = cfg.roles.aiStack.enable && mcp.enable && ai.backend == "llamacpp";

  repoMcp  = "${mcp.repoPath}/ai-stack/mcp-servers";
  dataDir  = mcp.dataDir;
  migrationsIni = "${mcp.repoPath}/ai-stack/migrations/alembic.ini";

  # ── Shared Python environment (packages used by ≥2 services) ─────────────
  # Individual services extend this with their own extras.
  sharedPythonPackages = ps: with ps; [
    # HTTP servers / clients
    flask
    aiohttp
    httpx
    requests
    uvicorn
    fastapi
    pydantic
    pydantic-settings

    # MCP protocol
    mcp

    # Vector DB client
    qdrant-client

    # Database
    psycopg2

    # Observability
    prometheus-client
    structlog

    # Utilities
    python-dotenv
    pyyaml
    tenacity
    openai
    anthropic
  ];

  # ── Per-service Python envs ───────────────────────────────────────────────
  # Note: no separate embeddingsPython env — embeddings are served by
  # llama-cpp-embed (llama.cpp --embedding mode) on ai.embeddingServer.port.
  # That service is declared in nix/modules/roles/ai-stack.nix.
  embedUrl = "http://127.0.0.1:${toString ai.embeddingServer.port}";

  aidbPython = pkgs.python3.withPackages (ps: sharedPythonPackages ps ++ (with ps; [
    sqlalchemy
    alembic
  ]));

  hybridPython = pkgs.python3.withPackages (ps: sharedPythonPackages ps ++ (with ps; [
    redis
    sqlalchemy
  ]));

  ralphPython = pkgs.python3.withPackages (ps: sharedPythonPackages ps ++ (with ps; [
    sqlalchemy
    redis
    gitpython
    jsonschema
  ]));

  # ── Common service hardening ──────────────────────────────────────────────
  # Mechanic: burst-limited restarts (max 5 in 5 min) prevent crash-loop floods.
  # Gatekeeper: drop all Linux capabilities; block namespace/personality syscalls.
  # ProtectHome fix: ReadOnlyPaths overrides ProtectHome to allow reading repo
  #   scripts (needed when mcpServers.repoPath is under /home/).
  commonServiceConfig = {
    User                     = "ai-stack";
    Group                    = "ai-stack";
    Restart                  = "on-failure";
    RestartSec               = "10s";
    StartLimitIntervalSec    = "300";
    StartLimitBurst          = 5;
    NoNewPrivileges          = true;
    ProtectSystem            = "strict";
    ProtectHome              = true;
    ReadWritePaths           = [ dataDir "/tmp" ];
    ReadOnlyPaths            = [ mcp.repoPath ];
    PrivateTmp               = true;
    WorkingDirectory         = dataDir;
    # Gatekeeper: minimal privilege surface
    CapabilityBoundingSet    = "";
    RestrictSUIDSGID         = true;
    LockPersonality          = true;
    RestrictNamespaces       = true;
  };

  # ── PostgreSQL connection URL (when postgres enabled) ─────────────────────
  pgUrl = "postgresql://${mcp.postgres.user}@127.0.0.1:${toString ports.postgres}/${mcp.postgres.database}";
  qdrantUrl = "http://127.0.0.1:${toString ports.qdrantHttp}";

  secretPath = name: config.sops.secrets.${name}.path;
  aidbApiKeySecret = sec.names.aidbApiKey;
  hybridApiKeySecret = sec.names.hybridApiKey;
  embeddingsApiKeySecret = sec.names.embeddingsApiKey;
  postgresPasswordSecret = sec.names.postgresPassword;
  redisPasswordSecret = sec.names.redisPassword;

  embedEnabled = ai.embeddingServer.enable;
  redisUnit = "redis-mcp.service";

  aiStackTargetWants =
    [ "ai-aidb.service" "ai-hybrid-coordinator.service" "ai-ralph-wiggum.service" ]
    ++ lib.optional llama.enable "llama-cpp.service"
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional ai.vectorDb.enable "qdrant.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit;

  aidbDeps =
    [ "network-online.target" ]
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  hybridDeps =
    [ "network-online.target" "ai-aidb.service" ]
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  ralphDeps =
    [ "network-online.target" "ai-hybrid-coordinator.service" "ai-aidb.service" ]
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit;

in
{
  config = lib.mkMerge [

    # ── Activation guard: only meaningful changes when fully enabled ──────────
    (lib.mkIf active {

      # ── System user / group ─────────────────────────────────────────────────
      users.groups.ai-stack = { gid = 35010; };
      users.users.ai-stack = {
        isSystemUser = true;
        group        = "ai-stack";
        description  = "AI stack MCP services";
        home         = dataDir;
        createHome   = true;
      };

      # ── State directories ───────────────────────────────────────────────────
      systemd.tmpfiles.rules = [
        "d ${dataDir}                    0750 ai-stack ai-stack -"
        "d ${dataDir}/aidb               0750 ai-stack ai-stack -"
        "d ${dataDir}/hybrid             0750 ai-stack ai-stack -"
        "d ${dataDir}/ralph              0750 ai-stack ai-stack -"
        "d ${dataDir}/qdrant-collections 0750 ai-stack ai-stack -"
        "d /var/log/ai-stack             0750 ai-stack ai-stack -"
      ];

      # ── Firewall: expose MCP ports on LAN when requested ───────────────────
      # embeddingsPort (:8001) omitted — embeddings served by llama-cpp-embed.
      networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan [
        mcp.aidbPort
        mcp.hybridPort
        mcp.ralphPort
      ];

      systemd.targets.ai-stack = {
        description = "Declarative AI stack orchestration target";
        wantedBy = [ "multi-user.target" ];
        wants = aiStackTargetWants ++ [ "network-online.target" ];
        after = [ "network-online.target" ];
      };

    })

    # ── PostgreSQL — optional, for AIDB tool-discovery persistence ────────────
    (lib.mkIf (active && mcp.postgres.enable) {

      services.postgresql = {
        enable  = lib.mkDefault true;
        ensureDatabases = [ mcp.postgres.database ];
        ensureUsers = [{
          name           = mcp.postgres.user;
          ensureDBOwnership = true;
        }];
        settings.port = ports.postgres;
      };

      systemd.services.postgresql.partOf = [ "ai-stack.target" ];

    })

    # ── Redis — optional, for MCP caching/queue workloads ─────────────────────
    (lib.mkIf (active && mcp.redis.enable) {

      services.redis.servers.mcp = {
        enable = lib.mkDefault true;
        port = mcp.redis.port;
        bind = mcp.redis.bind;
        save = [
          [ 900 1 ]
          [ 300 10 ]
          [ 60 10000 ]
        ];
        settings = {
          maxmemory = mcp.redis.maxmemory;
          maxmemory-policy = mcp.redis.maxmemoryPolicy;
        };
      };

      systemd.services.redis-mcp.partOf = [ "ai-stack.target" ];

    })

    # ── Embeddings: delegated to llama-cpp-embed (ai-stack.nix) ─────────────
    # No separate Python embeddings service — llama-cpp-embed on
    # ai.embeddingServer.port provides /v1/embeddings (OpenAI-compatible).
    # AIDB and hybrid-coordinator reference embedUrl defined in the let block.

    # ── AIDB MCP server — tool-discovery + RAG + telemetry ───────────────────
    (lib.mkIf active {

      systemd.services.ai-aidb = {
        description = "AIDB MCP server (tool-discovery + RAG)";
        wantedBy    = [ "ai-stack.target" ];
        after       = aidbDeps;
        requires    = aidbDeps;
        wants       = [ "network-online.target" ];
        preStart = lib.optionalString mcp.postgres.enable ''
          export AIDB_POSTGRES_HOST=127.0.0.1
          export AIDB_POSTGRES_PORT=${toString ports.postgres}
          export AIDB_POSTGRES_DB=${mcp.postgres.database}
          export AIDB_POSTGRES_USER=${mcp.postgres.user}
          export AIDB_POSTGRES_PASSWORD_FILE=${if sec.enable then secretPath postgresPasswordSecret else ""}
          ${aidbPython}/bin/alembic -c ${migrationsIni} upgrade head
        '';
        serviceConfig = commonServiceConfig // {
          PartOf = [ "ai-stack.target" ];
          ExecStart = lib.escapeShellArgs [
            "${aidbPython}/bin/python3"
            "${repoMcp}/aidb/server.py"
          ];
          Environment = [
            "PORT=${toString mcp.aidbPort}"
            "HOST=127.0.0.1"
            "QDRANT_URL=${qdrantUrl}"
            "EMBEDDING_SERVICE_URL=${embedUrl}"
            "EMBEDDINGS_API_KEY_FILE=${if sec.enable then secretPath embeddingsApiKeySecret else ""}"
            "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
            "EMBEDDING_DIMENSIONS=768"
            "DATA_DIR=${dataDir}/aidb"
            "AIDB_API_KEY_FILE=${if sec.enable then secretPath aidbApiKeySecret else ""}"
            "AIDB_POSTGRES_PASSWORD_FILE=${if sec.enable then secretPath postgresPasswordSecret else ""}"
            "AIDB_REDIS_PASSWORD_FILE=${if sec.enable then secretPath redisPasswordSecret else ""}"
          ] ++ lib.optional mcp.postgres.enable
            "DATABASE_URL=${pgUrl}";
        } // lib.optionalAttrs embedEnabled {
          ExecStartPre = pkgs.writeShellScript "aidb-wait-deps" ''
            set -e
            # Wait up to 60s for llama-cpp-embed to be ready
            for i in $(seq 1 60); do
              if ${pkgs.curl}/bin/curl -sf \
                  "${embedUrl}/health" \
                  >/dev/null 2>&1; then
                echo "Embedding server ready"
                break
              fi
              echo "Waiting for embedding server ($i/60)..."
              sleep 1
            done
          '';
        };
      };

    })

    # ── Hybrid Coordinator — local/remote LLM routing + learning ─────────────
    (lib.mkIf active {

      systemd.services.ai-hybrid-coordinator = {
        description = "AI hybrid coordinator (local/remote LLM routing)";
        wantedBy    = [ "ai-stack.target" ];
        after       = hybridDeps;
        requires    = hybridDeps;
        wants       = [ "network-online.target" ];
        serviceConfig = commonServiceConfig // {
          PartOf = [ "ai-stack.target" ];
          ExecStart = lib.escapeShellArgs [
            "${hybridPython}/bin/python3"
            "${repoMcp}/hybrid-coordinator/server.py"
          ];
          Environment = [
            "PORT=${toString mcp.hybridPort}"
            "HOST=127.0.0.1"
            "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
            "EMBEDDING_SERVICE_URL=${embedUrl}"
            "EMBEDDING_API_KEY_FILE=${if sec.enable then secretPath embeddingsApiKeySecret else ""}"
            "HYBRID_API_KEY_FILE=${if sec.enable then secretPath hybridApiKeySecret else ""}"
            "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
            "QDRANT_URL=${qdrantUrl}"
            "EMBEDDING_DIMENSIONS=384"
            "DATA_DIR=${dataDir}/hybrid"
            "POSTGRES_PASSWORD_FILE=${if sec.enable then secretPath postgresPasswordSecret else ""}"
            "REDIS_PASSWORD_FILE=${if sec.enable then secretPath redisPasswordSecret else ""}"
            "AI_HARNESS_ENABLED=${if ai.aiHarness.enable then "true" else "false"}"
            "AI_MEMORY_ENABLED=${if ai.aiHarness.memory.enable then "true" else "false"}"
            "AI_MEMORY_MAX_RECALL_ITEMS=${toString ai.aiHarness.memory.maxRecallItems}"
            "AI_TREE_SEARCH_ENABLED=${if ai.aiHarness.retrieval.treeSearchEnable then "true" else "false"}"
            "AI_TREE_SEARCH_MAX_DEPTH=${toString ai.aiHarness.retrieval.treeSearchMaxDepth}"
            "AI_TREE_SEARCH_BRANCH_FACTOR=${toString ai.aiHarness.retrieval.treeSearchBranchFactor}"
            "AI_HARNESS_EVAL_ENABLED=${if ai.aiHarness.eval.enable then "true" else "false"}"
            "AI_HARNESS_MIN_ACCEPTANCE_SCORE=${toString ai.aiHarness.eval.minAcceptanceScore}"
            "AI_HARNESS_MAX_LATENCY_MS=${toString ai.aiHarness.eval.maxLatencyMs}"
            "PYTHONPATH=${repoMcp}/shared:${repoMcp}/hybrid-coordinator"
          ] ++ lib.optional mcp.postgres.enable
            "DATABASE_URL=${pgUrl}";
        };
      };

    })

    # ── Ralph Wiggum — loop orchestrator + agent chain execution ─────────────
    (lib.mkIf active {

      systemd.services.ai-ralph-wiggum = {
        description = "AI ralph-wiggum loop orchestrator";
        wantedBy    = [ "ai-stack.target" ];
        after       = ralphDeps;
        requires    = ralphDeps;
        wants       = [ "network-online.target" ];
        serviceConfig = commonServiceConfig // {
          PartOf = [ "ai-stack.target" ];
          ExecStart = lib.escapeShellArgs [
            "${ralphPython}/bin/python3"
            "${repoMcp}/ralph-wiggum/server.py"
          ];
          Environment = [
            "PORT=${toString mcp.ralphPort}"
            "HOST=127.0.0.1"
            "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
            "HYBRID_COORDINATOR_URL=http://127.0.0.1:${toString mcp.hybridPort}"
            "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
            "DATA_DIR=${dataDir}/ralph"
            "RALPH_WIGGUM_API_KEY_FILE=${if sec.enable then secretPath aidbApiKeySecret else ""}"
            "PYTHONPATH=${repoMcp}/shared:${repoMcp}/ralph-wiggum"
          ] ++ lib.optional mcp.postgres.enable
            "DATABASE_URL=${pgUrl}";
        };
      };

    })

  ];
}
