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
  svcUser  = cfg.primaryUser;
  svcGroup = lib.attrByPath [ "users" "users" svcUser "group" ] "users" config;

  active = cfg.roles.aiStack.enable && mcp.enable && ai.backend == "llamacpp";

  repoMcp  = "${mcp.repoPath}/ai-stack/mcp-servers";
  dataDir  = mcp.dataDir;
  migrationsIni = "${mcp.repoPath}/ai-stack/migrations/alembic.ini";
  aidbConfig = pkgs.writeText "aidb-config.yaml" ''
    server:
      host: 127.0.0.1
      api_port: ${toString mcp.aidbPort}
      workers: 1

    database:
      postgres:
        host: 127.0.0.1
        port: ${toString ports.postgres}
        database: ${mcp.postgres.database}
        user: ${mcp.postgres.user}
      redis:
        host: 127.0.0.1
        port: ${toString mcp.redis.port}
        db: 0

    llm:
      llama_cpp:
        host: http://127.0.0.1:${toString llama.port}

    logging:
      level: INFO
      file: ${dataDir}/aidb/logs/aidb-mcp.log
      max_size: 10MB
      backup_count: 5

    telemetry:
      enabled: false
      path: ${dataDir}/aidb/telemetry/aidb-events.jsonl

    security:
      api_key_file: ${if sec.enable then secretPath aidbApiKeySecret else "/dev/null"}
      rate_limit:
        enabled: true
        requests_per_minute: 60

    rag:
      embedding_model: BAAI/bge-small-en-v1.5
      embedding_dimension: 384
      default_limit: 5
      default_context_chars: 4000
      max_context_chars: 12000
      pgvector:
        hnsw_m: 16
        hnsw_ef_construction: 64
  '';

  # ── Shared Python environment (packages used by ≥2 services) ─────────────
  # Individual services extend this with their own extras.
  sharedPythonPackages = ps:
    let
      pyAttrOrNull = names:
        let
          found = builtins.filter (n: builtins.hasAttr n ps) names;
        in
        if found == [ ] then null else builtins.getAttr (builtins.head found) ps;
      otelPkgs = builtins.filter (x: x != null) [
        (pyAttrOrNull [ "opentelemetry-api" "opentelemetry_api" ])
        (pyAttrOrNull [ "opentelemetry-sdk" "opentelemetry_sdk" ])
        (pyAttrOrNull [ "opentelemetry-exporter-otlp" "opentelemetry_exporter_otlp" ])
        (pyAttrOrNull [ "opentelemetry-exporter-otlp-proto-grpc" "opentelemetry_exporter_otlp_proto_grpc" ])
        (pyAttrOrNull [ "opentelemetry-instrumentation-fastapi" "opentelemetry_instrumentation_fastapi" ])
      ];
      aidbExtraPkgs = builtins.filter (x: x != null) [
        (pyAttrOrNull [ "sentence-transformers" "sentence_transformers" ])
        (pyAttrOrNull [ "transformers" ])
        (pyAttrOrNull [ "huggingface-hub" "huggingface_hub" ])
        (pyAttrOrNull [ "scikit-learn" "scikit_learn" ])
        (pyAttrOrNull [ "numpy" ])
        (pyAttrOrNull [ "scipy" ])
        (pyAttrOrNull [ "pandas" ])
      ];
    in
    (with ps; [
    # HTTP servers / clients
    flask
    aiohttp
    httpx
    requests
    uvicorn
    fastapi
    pydantic
    pydantic-settings

    # MCP protocol (must use ps.mcp; local `mcp` is module config attrset)
    ps.mcp

    # Vector DB client
    qdrant-client

    # Database
    psycopg
    psycopg2
    asyncpg

    # Observability
    prometheus-client
    structlog

    # Utilities
    python-dotenv
    pyyaml
    tenacity
    openai
    anthropic
    watchfiles   # Phase 9.2.2: inotify-based telemetry file watching
  ]) ++ otelPkgs ++ aidbExtraPkgs;

  # ── Per-service Python envs ───────────────────────────────────────────────
  # Note: no separate embeddingsPython env — embeddings are served by
  # llama-cpp-embed (llama.cpp --embedding mode) on ai.embeddingServer.port.
  # That service is declared in nix/modules/roles/ai-stack.nix.
  embedUrl = "http://127.0.0.1:${toString ai.embeddingServer.port}";

  aidbPython = pkgs.python3.withPackages (ps: sharedPythonPackages ps ++ (with ps; [
    sqlalchemy
    alembic
    pgvector
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

  aiderPython = pkgs.python3.withPackages (ps: sharedPythonPackages ps ++ (with ps; []));

  # ── Common service hardening ──────────────────────────────────────────────
  # Mechanic: burst-limited restarts (max 5 in 5 min) prevent crash-loop floods.
  # Gatekeeper: drop all Linux capabilities; block namespace/personality syscalls.
  # ProtectHome fix: ReadOnlyPaths overrides ProtectHome to allow reading repo
  #   scripts (needed when mcpServers.repoPath is under /home/).
  commonServiceConfig = {
    User                     = svcUser;
    Group                    = svcGroup;
    Restart                  = "on-failure";
    RestartSec               = "10s";
    NoNewPrivileges          = true;
    ProtectSystem            = "strict";
    ProtectHome              = "read-only";
    ReadWritePaths           = [ dataDir "/tmp" ];
    ReadOnlyPaths            = [ mcp.repoPath ];
    PrivateTmp               = true;
    WorkingDirectory         = dataDir;
    # Gatekeeper: minimal privilege surface
    CapabilityBoundingSet    = "";
    RestrictSUIDSGID         = true;
    LockPersonality          = true;
    RestrictNamespaces       = true;
    # Phase 13.1.1 — restrict to necessary address families only
    RestrictAddressFamilies  = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
    # Phase 13.1.2 — allow only the syscalls needed for normal service operation
    SystemCallFilter         = [ "@system-service" ];
    SystemCallErrorNumber    = "EPERM";
  };

  # ── PostgreSQL connection URL (when postgres enabled) ─────────────────────
  pgUrl = "postgresql://${mcp.postgres.user}@127.0.0.1:${toString ports.postgres}/${mcp.postgres.database}";
  qdrantUrl = "http://127.0.0.1:${toString ports.qdrantHttp}";

  secretPath = name: config.sops.secrets.${name}.path;
  aidbApiKeySecret = sec.names.aidbApiKey;
  hybridApiKeySecret = sec.names.hybridApiKey;
  embeddingsApiKeySecret = sec.names.embeddingsApiKey;
  postgresPasswordSecret     = sec.names.postgresPassword;
  redisPasswordSecret        = sec.names.redisPassword;
  aiderWrapperApiKeySecret   = sec.names.aiderWrapperApiKey;

  embedEnabled = ai.embeddingServer.enable;
  redisUnit = "redis-mcp.service";
  authSelfTestUnit = "ai-auth-selftest.service";
  otlpCollectorUnit = "ai-otel-collector.service";
  otlpEndpoint = "http://127.0.0.1:${toString ports.otlpGrpc}";
  otelCollectorConfig = pkgs.writeText "ai-otel-collector.yaml" ''
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 127.0.0.1:${toString ports.otlpGrpc}
          http:
            endpoint: 127.0.0.1:${toString ports.otlpHttp}

    processors:
      batch: {}

    exporters:
      nop: {}

    service:
      telemetry:
        logs:
          level: "warn"
        metrics:
          readers:
            - pull:
                exporter:
                  prometheus:
                    host: 127.0.0.1
                    port: ${toString ports.otelCollectorMetrics}
      pipelines:
        traces:
          receivers: [otlp]
          processors: [batch]
          exporters: [nop]
  '';
  requiredSecretFiles =
    [
      (secretPath aidbApiKeySecret)
      (secretPath hybridApiKeySecret)
      (secretPath embeddingsApiKeySecret)
      (secretPath postgresPasswordSecret)
    ];

  aiStackTargetWants =
    [ "ai-aidb.service" "ai-hybrid-coordinator.service" "ai-ralph-wiggum.service" ]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ [ otlpCollectorUnit ]
    ++ lib.optional mcp.postgres.enable "ai-pgvector-bootstrap.service"
    ++ lib.optional llama.enable "llama-cpp.service"
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional ai.vectorDb.enable "qdrant.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit;

  aidbDeps =
    [ "network-online.target" ]
    ++ [ otlpCollectorUnit ]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ lib.optional mcp.postgres.enable "ai-pgvector-bootstrap.service"
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  hybridDeps =
    [ "network-online.target" "ai-aidb.service" ]
    ++ [ otlpCollectorUnit ]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  ralphDeps =
    [ "network-online.target" "ai-hybrid-coordinator.service" "ai-aidb.service" ]
    ++ [ otlpCollectorUnit ]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit;

in
{
  config = lib.mkMerge [

    # ── Activation guard: only meaningful changes when fully enabled ──────────
    (lib.mkIf active {
      assertions = [
        {
          assertion = sec.enable;
          message = ''
            mySystem.mcpServers requires mySystem.secrets.enable=true when
            mySystem.roles.aiStack.enable=true.
          '';
        }
        # 6.5.3 — Port collision guard: service URL env vars must map to distinct ports.
        {
          assertion = mcp.aidbPort != mcp.hybridPort
                   && mcp.aidbPort != mcp.ralphPort
                   && mcp.hybridPort != mcp.ralphPort;
          message = "MCP service port conflict: aidbPort=${toString mcp.aidbPort}, hybridPort=${toString mcp.hybridPort}, ralphPort=${toString mcp.ralphPort} must all be distinct.";
        }
        # 6.5.3 — Non-empty path guard: repoPath and dataDir must be set before env blocks are generated.
        {
          assertion = mcp.repoPath != "";
          message = "mySystem.mcpServers.repoPath must be set to the repository root when MCP servers are active.";
        }
        {
          assertion = mcp.dataDir != "";
          message = "mySystem.mcpServers.dataDir must be set to a writable state directory when MCP servers are active.";
        }
      ];

      # ── System user / group ─────────────────────────────────────────────────
      # ── State directories ───────────────────────────────────────────────────
      systemd.tmpfiles.rules = [
        "d ${dataDir}                    0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/aidb               0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/aidb/logs          0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/aidb/telemetry     0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/hybrid             0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/ralph              0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/ralph/state        0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/ralph/telemetry    0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/qdrant-collections          0750 ${svcUser} ${svcGroup} -"
        "d /var/log/ai-stack                      0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/aider-wrapper               0750 ${svcUser} ${svcGroup} -"
        "d ${dataDir}/aider-wrapper/workspace     0750 ${svcUser} ${svcGroup} -"
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

    (lib.mkIf active {
      systemd.services.ai-otel-collector = {
        description = "AI stack OpenTelemetry collector";
        wantedBy = [ "ai-stack.target" ];
        partOf = [ "ai-stack.target" ];
        after = [ "network-online.target" ];
        wants = [ "network-online.target" ];
        serviceConfig = {
          Type = "simple";
          User = svcUser;
          Group = svcGroup;
          Restart = "on-failure";
          RestartSec = "5s";
          ExecStart = lib.escapeShellArgs [
            "${pkgs.opentelemetry-collector-contrib}/bin/otelcol-contrib"
            "--config"
            otelCollectorConfig
          ];
        };
      };
    })

    # ── PostgreSQL — optional, for AIDB tool-discovery persistence ────────────
    (lib.mkIf (active && mcp.postgres.enable) {

      services.postgresql = {
        enable  = lib.mkDefault true;
        extensions = ps: with ps; [ pgvector ];
        ensureDatabases = [ mcp.postgres.database ];
        ensureUsers = [{
          name           = mcp.postgres.user;
          ensureDBOwnership = true;
        }];
        settings.port = ports.postgres;
        authentication = lib.mkIf (!sec.enable) ''
          local all postgres                                peer map=postgres
          local ${mcp.postgres.database} ${mcp.postgres.user} trust
          host  ${mcp.postgres.database} ${mcp.postgres.user} 127.0.0.1/32 trust
          host  ${mcp.postgres.database} ${mcp.postgres.user} ::1/128      trust
        '';
      };

      systemd.services.postgresql.partOf = [ "ai-stack.target" ];

      systemd.services.ai-pgvector-bootstrap = {
        description = "Bootstrap pgvector extension for AIDB database";
        wantedBy = [ "ai-stack.target" ];
        partOf = [ "ai-stack.target" ];
        after = [ "postgresql.service" "postgresql-setup.service" ];
        requires = [ "postgresql.service" "postgresql-setup.service" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          set -euo pipefail

          ${lib.optionalString sec.enable ''
          secret_file=${lib.escapeShellArg (secretPath postgresPasswordSecret)}
          for _ in $(seq 1 30); do
            [[ -r "$secret_file" ]] && break
            sleep 1
          done
          [[ -r "$secret_file" ]] || {
            echo "postgres password secret file is not readable: $secret_file" >&2
            exit 1
          }
          pg_pw="$(${pkgs.coreutils}/bin/tr -d '\n' < "$secret_file")"
          pw_tag='$nqd_pw$'
          if [[ "$pg_pw" == *"$pw_tag"* ]]; then
            echo "postgres password contains unsupported marker sequence: $pw_tag" >&2
            exit 1
          fi
          sql="ALTER ROLE \"${mcp.postgres.user}\" WITH PASSWORD ''${pw_tag}"
          sql+="''${pg_pw}"
          sql+="''${pw_tag};"
          ${pkgs.util-linux}/bin/runuser -u postgres -- \
            ${config.services.postgresql.finalPackage}/bin/psql \
              --set=ON_ERROR_STOP=1 \
              --no-psqlrc \
              --dbname=${lib.escapeShellArg mcp.postgres.database} \
              --command="$sql"
          ''}

          ${pkgs.util-linux}/bin/runuser -u postgres -- \
          ${config.services.postgresql.finalPackage}/bin/psql \
            --set=ON_ERROR_STOP=1 \
            --no-psqlrc \
            --dbname=${lib.escapeShellArg mcp.postgres.database} \
            --command="CREATE EXTENSION IF NOT EXISTS vector;"
        '';
      };

    })

    (lib.mkIf (active && sec.enable) {
      systemd.services.ai-auth-selftest = {
        description = "AI auth self-test (secrets wiring + DB auth)";
        wantedBy = [ "ai-stack.target" ];
        partOf = [ "ai-stack.target" ];
        wants = [ "network-online.target" ];
        after =
          [ "network-online.target" ]
          ++ lib.optional mcp.postgres.enable "postgresql.service"
          ++ lib.optional mcp.postgres.enable "ai-pgvector-bootstrap.service";
        requires =
          lib.optional mcp.postgres.enable "postgresql.service"
          ++ lib.optional mcp.postgres.enable "ai-pgvector-bootstrap.service";
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          User = svcUser;
          Group = svcGroup;
        };
        script = ''
          set -euo pipefail

          check_secret_file() {
            local path="$1"
            if [[ ! -r "$path" ]]; then
              echo "missing or unreadable secret: $path" >&2
              exit 1
            fi
            if [[ ! -s "$path" ]]; then
              echo "empty secret file: $path" >&2
              exit 1
            fi
          }

          ${lib.concatMapStringsSep "\n" (path: "check_secret_file ${lib.escapeShellArg path}") requiredSecretFiles}

          ${lib.optionalString mcp.postgres.enable ''
          pg_pw="$(${pkgs.coreutils}/bin/tr -d '\n' < ${lib.escapeShellArg (secretPath postgresPasswordSecret)})"
          [[ -n "$pg_pw" ]] || { echo "postgres password secret is empty" >&2; exit 1; }
          export PGPASSWORD="$pg_pw"
          ${config.services.postgresql.finalPackage}/bin/psql \
            --set=ON_ERROR_STOP=1 \
            --no-psqlrc \
            --host=127.0.0.1 \
            --port=${toString ports.postgres} \
            --username=${lib.escapeShellArg mcp.postgres.user} \
            --dbname=${lib.escapeShellArg mcp.postgres.database} \
            --command='SELECT 1;' \
            >/dev/null
          unset PGPASSWORD
          ''}
        '';
      };
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
        partOf      = [ "ai-stack.target" ];
        after       = aidbDeps;
        requires    = aidbDeps;
        wants       = [ "network-online.target" ];
        preStart = lib.optionalString mcp.postgres.enable ''
          export AIDB_POSTGRES_HOST=127.0.0.1
          export AIDB_POSTGRES_PORT=${toString ports.postgres}
          export AIDB_POSTGRES_DB=${mcp.postgres.database}
          export AIDB_POSTGRES_USER=${mcp.postgres.user}
          ${lib.optionalString sec.enable ''
            export AIDB_POSTGRES_PASSWORD_FILE=${secretPath postgresPasswordSecret}
          ''}
          ${aidbPython}/bin/alembic -c ${migrationsIni} upgrade head
        '';
        serviceConfig = commonServiceConfig // {
          ExecStart = lib.escapeShellArgs [
            "${aidbPython}/bin/python3"
            "${repoMcp}/aidb/server.py"
          ];
          Environment = [
            "AIDB_CONFIG=${aidbConfig}"
            "AI_STRICT_ENV=true"
            "PORT=${toString mcp.aidbPort}"
            "HOST=127.0.0.1"
            "QDRANT_URL=${qdrantUrl}"
            "EMBEDDING_SERVICE_URL=${embedUrl}"
            "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
            "EMBEDDING_DIMENSIONS=${toString ai.embeddingDimensions}"
            "OTEL_TRACING_ENABLED=true"
            "OTEL_EXPORTER_OTLP_ENDPOINT=${otlpEndpoint}"
            "OTEL_SAMPLE_RATE=1.0"
            "DATA_DIR=${dataDir}/aidb"
            "XDG_STATE_HOME=${dataDir}/aidb/state"
            "AIDB_VSCODE_TELEMETRY_DIR=${dataDir}/aidb/telemetry"
            "POSTGRES_HOST=127.0.0.1"
            "POSTGRES_PORT=${toString ports.postgres}"
            "POSTGRES_DB=${mcp.postgres.database}"
            "POSTGRES_USER=${mcp.postgres.user}"
            "AIDB_REDIS_HOST=127.0.0.1"
            "AIDB_REDIS_PORT=${toString mcp.redis.port}"
            "AIDB_REDIS_DB=0"
            "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
            "HYBRID_COORDINATOR_URL=http://127.0.0.1:${toString mcp.hybridPort}"
            "RALPH_URL=http://127.0.0.1:${toString mcp.ralphPort}"
            "PYTHONPATH=${repoMcp}:${repoMcp}/aidb"
          ] ++ lib.optional mcp.postgres.enable
            "DATABASE_URL=${pgUrl}"
            ++ lib.optional sec.enable "EMBEDDINGS_API_KEY_FILE=${secretPath embeddingsApiKeySecret}"
            ++ lib.optional sec.enable "AIDB_API_KEY_FILE=${secretPath aidbApiKeySecret}"
            ++ lib.optional sec.enable "AIDB_POSTGRES_PASSWORD_FILE=${secretPath postgresPasswordSecret}";
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
        partOf      = [ "ai-stack.target" ];
        after       = hybridDeps;
        requires    = hybridDeps;
        wants       = [ "network-online.target" ];
        serviceConfig = commonServiceConfig // {
          ExecStart = lib.escapeShellArgs [
            "${hybridPython}/bin/python3"
            "${repoMcp}/hybrid-coordinator/server.py"
          ];
          Environment = [
            "PORT=${toString mcp.hybridPort}"
            "AI_STRICT_ENV=true"
            "MCP_SERVER_MODE=http"
            "MCP_SERVER_PORT=${toString mcp.hybridPort}"
            "HOST=127.0.0.1"
            "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
            "EMBEDDING_SERVICE_URL=${embedUrl}"
            "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
            "QDRANT_URL=${qdrantUrl}"
            "EMBEDDING_DIMENSIONS=${toString ai.embeddingDimensions}"
            "OTEL_TRACING_ENABLED=true"
            "OTEL_EXPORTER_OTLP_ENDPOINT=${otlpEndpoint}"
            "OTEL_SAMPLE_RATE=1.0"
            "DATA_DIR=${dataDir}/hybrid"
            "XDG_STATE_HOME=${dataDir}/hybrid/state"
            "CONTINUOUS_LEARNING_DATA_ROOT=${dataDir}/hybrid"
            "CONTINUOUS_LEARNING_TELEMETRY_DIR=${dataDir}/hybrid/telemetry"
            "CONTINUOUS_LEARNING_STATS_PATH=${dataDir}/hybrid/telemetry/continuous_learning_stats.json"
            "OPTIMIZATION_PROPOSALS_PATH=${dataDir}/hybrid/telemetry/optimization_proposals.jsonl"
            "CONTINUOUS_LEARNING_CHECKPOINT_DIR=${dataDir}/hybrid/checkpoints"
            "FINETUNE_DATA_PATH=${dataDir}/hybrid/fine-tuning/dataset.jsonl"
            "POSTGRES_HOST=127.0.0.1"
            "POSTGRES_PORT=${toString ports.postgres}"
            "POSTGRES_DB=${mcp.postgres.database}"
            "POSTGRES_USER=${mcp.postgres.user}"
            "REDIS_URL=redis://127.0.0.1:${toString mcp.redis.port}/0"
            "AI_HARNESS_ENABLED=${if ai.aiHarness.enable then "true" else "false"}"
            "AI_MEMORY_ENABLED=${if ai.aiHarness.memory.enable then "true" else "false"}"
            "AI_MEMORY_MAX_RECALL_ITEMS=${toString ai.aiHarness.memory.maxRecallItems}"
            "AI_TREE_SEARCH_ENABLED=${if ai.aiHarness.retrieval.treeSearchEnable then "true" else "false"}"
            "AI_TREE_SEARCH_MAX_DEPTH=${toString ai.aiHarness.retrieval.treeSearchMaxDepth}"
            "AI_TREE_SEARCH_BRANCH_FACTOR=${toString ai.aiHarness.retrieval.treeSearchBranchFactor}"
            "AI_HARNESS_EVAL_ENABLED=${if ai.aiHarness.eval.enable then "true" else "false"}"
            "AI_HARNESS_MIN_ACCEPTANCE_SCORE=${toString ai.aiHarness.eval.minAcceptanceScore}"
            "AI_HARNESS_MAX_LATENCY_MS=${toString ai.aiHarness.eval.maxLatencyMs}"
            "PYTHONPATH=${repoMcp}:${repoMcp}/hybrid-coordinator"
          ] ++ lib.optional mcp.postgres.enable
            "DATABASE_URL=${pgUrl}"
            ++ lib.optional sec.enable "EMBEDDING_API_KEY_FILE=${secretPath embeddingsApiKeySecret}"
            ++ lib.optional sec.enable "HYBRID_API_KEY_FILE=${secretPath hybridApiKeySecret}"
            ++ lib.optional sec.enable "POSTGRES_PASSWORD_FILE=${secretPath postgresPasswordSecret}";
        };
      };

    })

    # ── Ralph Wiggum — loop orchestrator + agent chain execution ─────────────
    (lib.mkIf active {

      systemd.services.ai-ralph-wiggum = {
        description = "AI ralph-wiggum loop orchestrator";
        wantedBy    = [ "ai-stack.target" ];
        partOf      = [ "ai-stack.target" ];
        after       = ralphDeps;
        requires    = ralphDeps;
        wants       = [ "network-online.target" ];
        serviceConfig = commonServiceConfig // {
          ExecStart = lib.escapeShellArgs [
            "${ralphPython}/bin/python3"
            "${repoMcp}/ralph-wiggum/server.py"
          ];
          Environment = [
            "AI_STRICT_ENV=true"
            "PORT=${toString mcp.ralphPort}"
            "HOST=127.0.0.1"
            "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
            "HYBRID_COORDINATOR_URL=http://127.0.0.1:${toString mcp.hybridPort}"
            "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
            "AIDER_WRAPPER_HOST=127.0.0.1"
            "AIDER_WRAPPER_PORT=${toString mcp.aiderWrapperPort}"
            "DATA_DIR=${dataDir}/ralph"
            "XDG_STATE_HOME=${dataDir}/ralph/state"
            "RALPH_STATE_FILE=${dataDir}/ralph/ralph-state.json"
            "RALPH_TELEMETRY_PATH=${dataDir}/ralph/telemetry/ralph-events.jsonl"
            "POSTGRES_HOST=127.0.0.1"
            "POSTGRES_PORT=${toString ports.postgres}"
            "POSTGRES_DB=${mcp.postgres.database}"
            "POSTGRES_USER=${mcp.postgres.user}"
            "PYTHONPATH=${repoMcp}:${repoMcp}/ralph-wiggum"
          ] ++ lib.optional mcp.postgres.enable
            "DATABASE_URL=${pgUrl}"
            ++ lib.optional sec.enable "RALPH_WIGGUM_API_KEY_FILE=${secretPath aidbApiKeySecret}";
          # Phase 13.1.1 — ralph only communicates with loopback services
          IPAddressAllow = [ "127.0.0.1/8" "::1/128" ];
          IPAddressDeny  = "any";
        };
      };

    })

    # ── Aider Wrapper — async code modification MCP server ───────────────────
    (lib.mkIf active {

      systemd.services.ai-aider-wrapper = {
        description = "Aider Wrapper MCP server (async code modification)";
        wantedBy    = [ "ai-stack.target" ];
        partOf      = [ "ai-stack.target" ];
        after       = [ "network-online.target" ];
        wants       = [ "network-online.target" ];
        serviceConfig = commonServiceConfig // {
          ExecStart = lib.escapeShellArgs [
            "${aiderPython}/bin/python3"
            "${repoMcp}/aider-wrapper/server.py"
          ];
          Environment = [
            "AIDER_WRAPPER_PORT=${toString mcp.aiderWrapperPort}"
            "AIDER_WORKSPACE=${dataDir}/aider-wrapper/workspace"
            "LLAMA_CPP_HOST=127.0.0.1"
            "LLAMA_CPP_PORT=${toString llama.port}"
            "PYTHONPATH=${repoMcp}:${repoMcp}/aider-wrapper"
          ] ++ lib.optional sec.enable "AIDER_WRAPPER_API_KEY_FILE=${secretPath aiderWrapperApiKeySecret}";
        };
      };

    })

  ];
}
