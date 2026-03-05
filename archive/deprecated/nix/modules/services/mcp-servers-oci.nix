{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  ports = cfg.ports;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  sec = cfg.secrets;
  llama = ai.llamaCpp;

  active = cfg.roles.aiStack.enable && mcp.enable && ai.backend == "llamacpp" && mcp.runtime == "oci";

  backend = mcp.oci.backend;
  dataDir = mcp.dataDir;
  repoPath = mcp.repoPath;
  migrationsIni = "${mcp.repoPath}/ai-stack/migrations/alembic.ini";
  embedEnabled = ai.embeddingServer.enable;

  redisUnit = "redis-mcp.service";
  containerUnit = name: "${backend}-${name}";

  containerService = name: "${containerUnit name}.service";

  aidbContainer = "ai-aidb";
  hybridContainer = "ai-hybrid-coordinator";
  ralphContainer = "ai-ralph-wiggum";

  aidbUnit = containerUnit aidbContainer;
  hybridUnit = containerUnit hybridContainer;
  ralphUnit = containerUnit ralphContainer;

  aidbService = containerService aidbContainer;
  hybridService = containerService hybridContainer;
  ralphService = containerService ralphContainer;

  secretPath = name: config.sops.secrets.${name}.path;
  aidbApiKeySecret = sec.names.aidbApiKey;
  hybridApiKeySecret = sec.names.hybridApiKey;
  embeddingsApiKeySecret = sec.names.embeddingsApiKey;
  postgresPasswordSecret = sec.names.postgresPassword;
  redisPasswordSecret = sec.names.redisPassword;
  qdrantUrl = "http://127.0.0.1:${toString ports.qdrantHttp}";
  pgUrl = "postgresql://${mcp.postgres.user}@127.0.0.1:${toString ports.postgres}/${mcp.postgres.database}";

  mcpPython = pkgs.python3.withPackages (ps: with ps; [
    flask
    aiohttp
    httpx
    requests
    uvicorn
    fastapi
    pydantic
    pydantic-settings
    mcp
    qdrant-client
    psycopg2
    prometheus-client
    structlog
    pyyaml
    tenacity
    openai
    anthropic
    sqlalchemy
    alembic
    redis
    gitpython
    jsonschema
  ]);

  runtimeImage = pkgs.dockerTools.buildLayeredImage {
    name = "ai-mcp-runtime";
    tag = "latest";
    contents = [
      mcpPython
      pkgs.bash
      pkgs.coreutils
      pkgs.curl
      pkgs.findutils
      pkgs.gnugrep
      pkgs.gawk
      pkgs.jq
      pkgs.procps
      pkgs.iproute2
      pkgs.cacert
    ];
    config = {
      WorkingDir = "/repo";
      Cmd = [ "${pkgs.bash}/bin/bash" "-lc" "sleep infinity" ];
    };
  };

  commonContainer = {
    image = "ai-mcp-runtime:latest";
    imageFile = runtimeImage;
    autoStart = true;
    extraOptions = [ "--network=host" "--pull=never" ];
    volumes = [
      "${repoPath}:/repo:ro"
      "${dataDir}:${dataDir}"
      "/run/secrets:/run/secrets:ro"
    ];
  };

  aidbDeps =
    [ "network-online.target" ]
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  hybridDeps =
    [ "network-online.target" aidbService ]
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  ralphDeps =
    [ "network-online.target" aidbService hybridService ]
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit;
in
{
  config = lib.mkIf active {
    assertions = [
      {
        assertion = backend != "podman";
        message = "mcpServers.runtime=oci currently supports only docker backend in this profile.";
      }
    ];

    virtualisation.docker.enable = lib.mkDefault true;
    virtualisation.oci-containers.backend = backend;

    # Native infra backing OCI MCP services
    services.postgresql = lib.mkIf mcp.postgres.enable {
      enable = lib.mkDefault true;
      ensureDatabases = [ mcp.postgres.database ];
      ensureUsers = [{
        name = mcp.postgres.user;
        ensureDBOwnership = true;
      }];
      settings.port = ports.postgres;
    };

    services.redis.servers.mcp = lib.mkIf mcp.redis.enable {
      enable = lib.mkDefault true;
      port = ports.redis;
      bind = mcp.redis.bind;
      save = [ [ 900 1 ] [ 300 10 ] [ 60 10000 ] ];
      settings = {
        maxmemory = mcp.redis.maxmemory;
        maxmemory-policy = mcp.redis.maxmemoryPolicy;
      };
    };

    systemd.targets.ai-stack = {
      description = "Declarative AI stack orchestration target (OCI mode)";
      wantedBy = [ "multi-user.target" ];
      wants = [ aidbService hybridService ralphService ]
        ++ lib.optional llama.enable "llama-cpp.service"
        ++ lib.optional embedEnabled "llama-cpp-embed.service"
        ++ lib.optional ai.vectorDb.enable "qdrant.service"
        ++ lib.optional mcp.postgres.enable "postgresql.service"
        ++ lib.optional mcp.redis.enable redisUnit
        ++ [ "network-online.target" ];
      after = [ "network-online.target" ];
    };

    # Bind native infra to ai-stack target
    systemd.services.postgresql.partOf = lib.optional mcp.postgres.enable "ai-stack.target";
    systemd.services.redis-mcp.partOf = lib.optional mcp.redis.enable "ai-stack.target";
    systemd.services.qdrant.partOf = lib.optional ai.vectorDb.enable "ai-stack.target";
    systemd.services.llama-cpp.partOf = lib.optional llama.enable "ai-stack.target";
    systemd.services.llama-cpp-embed.partOf = lib.optional embedEnabled "ai-stack.target";

    virtualisation.oci-containers.containers = {
      "${aidbContainer}" = commonContainer // {
        cmd = [ "${mcpPython}/bin/python3" "/repo/ai-stack/mcp-servers/aidb/server.py" ];
        environment = {
          PORT = toString mcp.aidbPort;
          HOST = "127.0.0.1";
          QDRANT_URL = qdrantUrl;
          EMBEDDING_SERVICE_URL = "http://127.0.0.1:${toString ai.embeddingServer.port}";
          EMBEDDINGS_API_KEY_FILE = if sec.enable then secretPath embeddingsApiKeySecret else "";
          LLAMA_CPP_BASE_URL = "http://127.0.0.1:${toString llama.port}";
          EMBEDDING_DIMENSIONS = "768";
          DATA_DIR = "${dataDir}/aidb";
          AIDB_API_KEY_FILE = if sec.enable then secretPath aidbApiKeySecret else "";
          AIDB_POSTGRES_PASSWORD_FILE = if sec.enable then secretPath postgresPasswordSecret else "";
          AIDB_REDIS_PASSWORD_FILE = if sec.enable then secretPath redisPasswordSecret else "";
          PYTHONPATH = "/repo/ai-stack/mcp-servers/shared:/repo/ai-stack/mcp-servers/aidb";
        } // lib.optionalAttrs mcp.postgres.enable {
          DATABASE_URL = pgUrl;
        };
      };

      "${hybridContainer}" = commonContainer // {
        cmd = [ "${mcpPython}/bin/python3" "/repo/ai-stack/mcp-servers/hybrid-coordinator/server.py" ];
        environment = {
          PORT = toString mcp.hybridPort;
          HOST = "127.0.0.1";
          LLAMA_CPP_BASE_URL = "http://127.0.0.1:${toString llama.port}";
          EMBEDDING_SERVICE_URL = "http://127.0.0.1:${toString ai.embeddingServer.port}";
          EMBEDDING_API_KEY_FILE = if sec.enable then secretPath embeddingsApiKeySecret else "";
          HYBRID_API_KEY_FILE = if sec.enable then secretPath hybridApiKeySecret else "";
          AIDB_URL = "http://127.0.0.1:${toString mcp.aidbPort}";
          QDRANT_URL = qdrantUrl;
          EMBEDDING_DIMENSIONS = "384";
          DATA_DIR = "${dataDir}/hybrid";
          POSTGRES_PASSWORD_FILE = if sec.enable then secretPath postgresPasswordSecret else "";
          REDIS_PASSWORD_FILE = if sec.enable then secretPath redisPasswordSecret else "";
          AI_HARNESS_ENABLED = if ai.aiHarness.enable then "true" else "false";
          AI_MEMORY_ENABLED = if ai.aiHarness.memory.enable then "true" else "false";
          AI_MEMORY_MAX_RECALL_ITEMS = toString ai.aiHarness.memory.maxRecallItems;
          AI_TREE_SEARCH_ENABLED = if ai.aiHarness.retrieval.treeSearchEnable then "true" else "false";
          AI_TREE_SEARCH_MAX_DEPTH = toString ai.aiHarness.retrieval.treeSearchMaxDepth;
          AI_TREE_SEARCH_BRANCH_FACTOR = toString ai.aiHarness.retrieval.treeSearchBranchFactor;
          AI_HARNESS_EVAL_ENABLED = if ai.aiHarness.eval.enable then "true" else "false";
          AI_HARNESS_MIN_ACCEPTANCE_SCORE = toString ai.aiHarness.eval.minAcceptanceScore;
          AI_HARNESS_MAX_LATENCY_MS = toString ai.aiHarness.eval.maxLatencyMs;
          PYTHONPATH = "/repo/ai-stack/mcp-servers/shared:/repo/ai-stack/mcp-servers/hybrid-coordinator";
        } // lib.optionalAttrs mcp.postgres.enable {
          DATABASE_URL = pgUrl;
        };
      };

      "${ralphContainer}" = commonContainer // {
        cmd = [ "${mcpPython}/bin/python3" "/repo/ai-stack/mcp-servers/ralph-wiggum/server.py" ];
        environment = {
          PORT = toString mcp.ralphPort;
          HOST = "127.0.0.1";
          LLAMA_CPP_BASE_URL = "http://127.0.0.1:${toString llama.port}";
          HYBRID_COORDINATOR_URL = "http://127.0.0.1:${toString mcp.hybridPort}";
          AIDB_URL = "http://127.0.0.1:${toString mcp.aidbPort}";
          DATA_DIR = "${dataDir}/ralph";
          RALPH_WIGGUM_API_KEY_FILE = if sec.enable then secretPath aidbApiKeySecret else "";
          PYTHONPATH = "/repo/ai-stack/mcp-servers/shared:/repo/ai-stack/mcp-servers/ralph-wiggum";
        } // lib.optionalAttrs mcp.postgres.enable {
          DATABASE_URL = pgUrl;
        };
      };
    };

    systemd.services."${aidbUnit}" = {
      wantedBy = [ "ai-stack.target" ];
      after = aidbDeps;
      requires = aidbDeps;
      wants = [ "network-online.target" ];
      preStart = lib.optionalString mcp.postgres.enable ''
        export AIDB_POSTGRES_HOST=127.0.0.1
        export AIDB_POSTGRES_PORT=${toString ports.postgres}
        export AIDB_POSTGRES_DB=${mcp.postgres.database}
        export AIDB_POSTGRES_USER=${mcp.postgres.user}
        export AIDB_POSTGRES_PASSWORD_FILE=${if sec.enable then secretPath postgresPasswordSecret else ""}
        ${mcpPython}/bin/alembic -c ${migrationsIni} upgrade head
      '';
      partOf = [ "ai-stack.target" ];
      restartIfChanged = true;
    };

    systemd.services."${hybridUnit}" = {
      wantedBy = [ "ai-stack.target" ];
      after = hybridDeps;
      requires = hybridDeps;
      wants = [ "network-online.target" ];
      partOf = [ "ai-stack.target" ];
      restartIfChanged = true;
    };

    systemd.services."${ralphUnit}" = {
      wantedBy = [ "ai-stack.target" ];
      after = ralphDeps;
      requires = ralphDeps;
      wants = [ "network-online.target" ];
      partOf = [ "ai-stack.target" ];
      restartIfChanged = true;
    };
  };
}
