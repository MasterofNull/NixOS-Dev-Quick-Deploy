{
  lib,
  config,
  pkgs,
  ...
}:
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
  cfg = config.mySystem;
  ports = cfg.ports;
  mcp = cfg.mcpServers;
  ai = cfg.aiStack;
  sec = cfg.secrets;
  llama = ai.llamaCpp;
  svcUser = cfg.primaryUser;
  svcGroup = lib.attrByPath ["users" "users" svcUser "group"] "users" config;

  active = cfg.roles.aiStack.enable && mcp.enable && ai.backend == "llamacpp";

  # Phase 16.4.1/16.4.2 — tier-aware hardening base.
  mkHardenedService = import ../../lib/hardened-service.nix {inherit lib;};
  # Each MCP service gets a MemoryMax ceiling sized to the detected hardware tier
  # (nano→256M, micro→512M, small→1G, medium→2G, large→4G).
  hardenedBase = mkHardenedService {tier = cfg.hardwareTier;};

  # Repo source for pure evaluation: use flakeRepoPath if set, otherwise import
  # repoPath into Nix store via builtins.path. This allows access to repo files
  # during pure evaluation without forbidden /home path access.
  repoSource =
    if mcp.flakeRepoPath != null
    then mcp.flakeRepoPath
    else builtins.path {
      path = mcp.repoPath;
      name = "nixos-quick-deploy-repo";
    };

  repoMcp = "${repoSource}/ai-stack/mcp-servers";

  # ── Phase 2.4: YAML workflow handlers + workflows package (Nix store) ───
  # Packages the workflows engine and YAML workflow HTTP handlers into the
  # Nix store so they are declarative, reproducible, and rollback-capable.
  # The hybrid coordinator imports yaml_workflow_handlers dynamically; this
  # derivation ensures the code comes from /nix/store, not the mutable repo.
  workflowHandlersPkg =
    pkgs.runCommand "yaml-workflow-handlers" {
      src = repoSource;
    } ''
      sp="${pkgs.python3.sitePackages}"
      mkdir -p "$out/$sp/workflows"
      cp $src/ai-stack/workflows/*.py "$out/$sp/workflows/"
      cp $src/ai-stack/mcp-servers/hybrid-coordinator/yaml_workflow_handlers.py "$out/$sp/"
    '';

  dataDir = mcp.dataDir;
  mutableStateDir = cfg.deployment.mutableSpaces.aiStackStateDir;
  mutableOptimizerDir = cfg.deployment.mutableSpaces.aiStackOptimizerDir;
  mutableLogDir = cfg.deployment.mutableSpaces.aiStackLogDir;
  mcpIntegrityBaseline = "${mutableStateDir}/mcp-source-baseline.sha256";
  migrationsIni = "${repoSource}/ai-stack/migrations/alembic.ini";
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
      enabled: ${
      if ai.aiHarness.runtime.telemetryEnabled
      then "true"
      else "false"
    }
      path: ${dataDir}/aidb/telemetry/aidb-events.jsonl

    security:
      api_key_file: ${
      if sec.enable
      then secretPath aidbApiKeySecret
      else "/dev/null"
    }
      rate_limit:
        enabled: true
        requests_per_minute: 60

    rag:
      embedding_model: Qwen/Qwen3-Embedding-4B
      embedding_dimension: ${toString ai.embeddingDimensions}
      default_limit: 5
      default_context_chars: 4000
      max_context_chars: 12000
      pgvector:
        hnsw_m: 16
        hnsw_ef_construction: 64
  '';

  runtimeSafetyPolicyJson =
    pkgs.writeText "runtime-safety-policy.json" (builtins.toJSON ai.aiHarness.runtime.safetyPolicy);
  runtimeIsolationProfilesJson =
    pkgs.writeText "runtime-isolation-profiles.json" (builtins.toJSON ai.aiHarness.runtime.isolationProfiles);
  workflowBlueprintsJson =
    pkgs.writeText "workflow-blueprints.json" (builtins.toJSON ai.aiHarness.runtime.workflowBlueprints);
  runtimeSchedulerPolicyJson =
    pkgs.writeText "runtime-scheduler-policy.json" (builtins.toJSON ai.aiHarness.runtime.schedulerPolicy);
  parityScorecardJson =
    pkgs.writeText "parity-scorecard.json" (builtins.toJSON ai.aiHarness.runtime.parityScorecard);
  runtimeToolSecurityPolicyJson =
    pkgs.writeText "runtime-tool-security-policy.json" (builtins.toJSON ai.aiHarness.runtime.toolSecurity.policy);
  auditSidecarScript =
    pkgs.writeText "audit_sidecar.py" (builtins.readFile ../../../ai-stack/mcp-servers/shared/audit_sidecar.py);

  runtimeSafetyModes =
    if
      builtins.isAttrs ai.aiHarness.runtime.safetyPolicy
      && builtins.hasAttr "modes" ai.aiHarness.runtime.safetyPolicy
      && builtins.isAttrs ai.aiHarness.runtime.safetyPolicy.modes
    then ai.aiHarness.runtime.safetyPolicy.modes
    else {};

  runtimeIsolationProfiles =
    if
      builtins.isAttrs ai.aiHarness.runtime.isolationProfiles
      && builtins.hasAttr "profiles" ai.aiHarness.runtime.isolationProfiles
      && builtins.isAttrs ai.aiHarness.runtime.isolationProfiles.profiles
    then ai.aiHarness.runtime.isolationProfiles.profiles
    else {};

  pathWithinDataDir = path:
    path == dataDir || lib.hasPrefix "${dataDir}/" path;

  runtimeWorkspaceRoots = let
    values = builtins.attrValues runtimeIsolationProfiles;
    roots =
      map (
        p:
          if builtins.isAttrs p && builtins.hasAttr "workspace_root" p
          then toString p.workspace_root
          else ""
      )
      values;
  in
    lib.unique (builtins.filter (x: x != "") roots);

  mutableProgramPaths =
    if cfg.deployment.mutableSpaces.enable
    then
      lib.unique (
        cfg.deployment.mutableSpaces.programWritablePaths
        ++ [mutableStateDir mutableOptimizerDir mutableLogDir]
      )
    else [];

  serviceWritablePaths = lib.unique ([
      dataDir
      "/tmp"
    ]
    ++ mutableProgramPaths ++ runtimeWorkspaceRoots);

  # ── Shared Python environment (packages used by ≥2 services) ─────────────
  # Individual services extend this with their own extras.
  sharedPythonPackages = ps: let
    pyAttrOrNull = names: let
      found = builtins.filter (n: builtins.hasAttr n ps) names;
    in
      if found == []
      then null
      else builtins.getAttr (builtins.head found) ps;
    otelPkgs = builtins.filter (x: x != null) [
      (pyAttrOrNull ["opentelemetry-api" "opentelemetry_api"])
      (pyAttrOrNull ["opentelemetry-sdk" "opentelemetry_sdk"])
      (pyAttrOrNull ["opentelemetry-exporter-otlp" "opentelemetry_exporter_otlp"])
      (pyAttrOrNull ["opentelemetry-exporter-otlp-proto-grpc" "opentelemetry_exporter_otlp_proto_grpc"])
      (pyAttrOrNull ["opentelemetry-instrumentation-fastapi" "opentelemetry_instrumentation_fastapi"])
    ];
    aidbExtraPkgs = builtins.filter (x: x != null) [
      (pyAttrOrNull ["sentence-transformers" "sentence_transformers"])
      (pyAttrOrNull ["transformers"])
      (pyAttrOrNull ["huggingface-hub" "huggingface_hub"])
      (pyAttrOrNull ["scikit-learn" "scikit_learn"])
      (pyAttrOrNull ["numpy"])
      (pyAttrOrNull ["scipy"])
      (pyAttrOrNull ["pandas"])
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
      watchfiles # Phase 9.2.2: inotify-based telemetry file watching
    ])
    ++ otelPkgs ++ aidbExtraPkgs;

  # ── Per-service Python envs ───────────────────────────────────────────────
  # Note: no separate embeddingsPython env — embeddings are served by
  # llama-cpp-embed (llama.cpp --embedding mode) on ai.embeddingServer.port.
  # That service is declared in nix/modules/roles/ai-stack.nix.
  embedUrl = "http://127.0.0.1:${toString ai.embeddingServer.port}";

  aidbPython = pkgs.python3.withPackages (ps:
    sharedPythonPackages ps
    ++ (with ps; [
      sqlalchemy
      alembic
      pgvector
    ]));

  hybridPython = pkgs.python3.withPackages (ps:
    sharedPythonPackages ps
    ++ (with ps; [
      redis
      sqlalchemy
      beautifulsoup4
      trio
    ]));

  ralphPython = pkgs.python3.withPackages (ps:
    sharedPythonPackages ps
    ++ (with ps; [
      sqlalchemy
      redis
      gitpython
      jsonschema
    ]));

  aiderPython = pkgs.python3.withPackages (ps: sharedPythonPackages ps ++ (with ps; []));

  nixosDocsPython = pkgs.python3.withPackages (ps:
    sharedPythonPackages ps
    ++ (with ps; [
      diskcache
      gitpython
      beautifulsoup4
      markdownify
      lxml
      redis
    ]));

  knowledgeSyncPath = lib.makeBinPath [
    pkgs.bash
    pkgs.coreutils
    pkgs.findutils
    pkgs.gnugrep
    pkgs.gnused
    pkgs.systemd
    aidbPython
  ];

  # Phase 12.3.2 — audit sidecar uses only stdlib (asyncio/json/socket).
  auditSidecarPython = pkgs.python3;

  # ── Common service hardening ──────────────────────────────────────────────
  # Built on top of mkHardenedService (Phase 16.4.1/16.4.2) which provides the
  # tier-aware MemoryMax ceiling and core systemd hardening directives.
  # Overrides:
  #   ProtectHome = "read-only"   — repo scripts may live under /home/
  #   Restart / RestartSec        — burst-limited restart policy for MCP services
  #   ReadWritePaths/ReadOnlyPaths — service-specific paths
  commonServiceConfig =
    hardenedBase
    // {
      User = svcUser;
      Group = svcGroup;
      Restart = "on-failure";
      RestartSec = "10s";
      # ProtectHome override: repo scripts may be under /home/; "read-only" allows
      # reading them while still blocking writes to /home.
      ProtectHome = "read-only";
      ReadWritePaths = serviceWritablePaths;
      ReadOnlyPaths = [repoSource];
      WorkingDirectory = dataDir;
      # Phase 13.1.1 — restrict to necessary address families only
      RestrictAddressFamilies = ["AF_UNIX" "AF_INET" "AF_INET6"];
      # Phase 13.1.2 — allow only the syscalls needed for normal service operation
      SystemCallFilter = ["@system-service"];
      SystemCallErrorNumber = "EPERM";
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
  aiderWrapperApiKeySecret = sec.names.aiderWrapperApiKey;
  nixosDocsApiKeySecret = sec.names.nixosDocsApiKey;

  embedEnabled = ai.embeddingServer.enable;
  redisUnit = "redis-mcp.service";
  mutableBootstrapUnit = "ai-mutable-path-bootstrap.service";
  authSelfTestUnit = "ai-auth-selftest.service";
  otlpCollectorUnit = "ai-otel-collector.service";
  otlpEndpoint = "http://127.0.0.1:${toString ports.otlpGrpc}";
  # Phase 21.1 — OTEL collector config with Tempo exporter for trace persistence.
  # Traces are forwarded to Grafana Tempo for storage and querying.
  otelCollectorConfig = pkgs.writeText "ai-otel-collector.yaml" ''
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 127.0.0.1:${toString ports.otlpGrpc}
          http:
            endpoint: 127.0.0.1:${toString ports.otlpHttp}

    processors:
      batch:
        timeout: 5s
        send_batch_size: 512

    exporters:
      # Phase 21.1 — Export traces to Grafana Tempo for distributed tracing.
      # Tempo receives traces via OTLP gRPC on port 4320.
      otlp/tempo:
        endpoint: 127.0.0.1:${toString cfg.monitoring.tracing.tempoOtlpGrpcPort}
        tls:
          insecure: true

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
          exporters: [otlp/tempo]
  '';
  requiredSecretFiles = [
    (secretPath aidbApiKeySecret)
    (secretPath hybridApiKeySecret)
    (secretPath embeddingsApiKeySecret)
    (secretPath postgresPasswordSecret)
  ];

  aiStackTargetWants =
    ["ai-aidb.service" "ai-hybrid-coordinator.service" "ai-ralph-wiggum.service"]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ [otlpCollectorUnit]
    ++ lib.optional mcp.postgres.enable "ai-pgvector-bootstrap.service"
    ++ lib.optional llama.enable "llama-cpp.service"
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional ai.vectorDb.enable "qdrant.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit;

  aidbDeps =
    ["network-online.target" mutableBootstrapUnit]
    ++ [otlpCollectorUnit]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ lib.optional mcp.postgres.enable "ai-pgvector-bootstrap.service"
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  hybridDeps =
    ["network-online.target" mutableBootstrapUnit "ai-aidb.service"]
    ++ [otlpCollectorUnit]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ lib.optional embedEnabled "llama-cpp-embed.service"
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit
    ++ lib.optional ai.vectorDb.enable "qdrant.service";

  ralphDeps =
    ["network-online.target" mutableBootstrapUnit "ai-hybrid-coordinator.service" "ai-aidb.service"]
    ++ [otlpCollectorUnit]
    ++ lib.optional sec.enable authSelfTestUnit
    ++ lib.optional mcp.postgres.enable "postgresql.service"
    ++ lib.optional mcp.redis.enable redisUnit;
in {
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
          assertion =
            mcp.aidbPort
            != mcp.hybridPort
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
        {
          assertion =
            builtins.isAttrs ai.aiHarness.runtime.safetyPolicy
            && builtins.hasAttr "modes" ai.aiHarness.runtime.safetyPolicy
            && builtins.isAttrs ai.aiHarness.runtime.safetyPolicy.modes
            && builtins.hasAttr "plan-readonly" ai.aiHarness.runtime.safetyPolicy.modes
            && builtins.hasAttr "execute-mutating" ai.aiHarness.runtime.safetyPolicy.modes;
          message = ''
            mySystem.aiStack.aiHarness.runtime.safetyPolicy must define
            modes.plan-readonly and modes.execute-mutating.
          '';
        }
        {
          assertion =
            builtins.isAttrs ai.aiHarness.runtime.isolationProfiles
            && builtins.hasAttr "profiles" ai.aiHarness.runtime.isolationProfiles
            && builtins.isAttrs ai.aiHarness.runtime.isolationProfiles.profiles;
          message = ''
            mySystem.aiStack.aiHarness.runtime.isolationProfiles.profiles must be an attribute set.
          '';
        }
        {
          assertion =
            builtins.isAttrs ai.aiHarness.runtime.workflowBlueprints
            && builtins.hasAttr "blueprints" ai.aiHarness.runtime.workflowBlueprints;
          message = ''
            mySystem.aiStack.aiHarness.runtime.workflowBlueprints must contain a blueprints list.
          '';
        }
        {
          assertion =
            builtins.isAttrs ai.aiHarness.runtime.schedulerPolicy
            && builtins.hasAttr "selection" ai.aiHarness.runtime.schedulerPolicy;
          message = ''
            mySystem.aiStack.aiHarness.runtime.schedulerPolicy must contain selection.
          '';
        }
        {
          assertion =
            builtins.isAttrs ai.aiHarness.runtime.parityScorecard
            && builtins.hasAttr "tracks" ai.aiHarness.runtime.parityScorecard;
          message = ''
            mySystem.aiStack.aiHarness.runtime.parityScorecard must contain tracks.
          '';
        }
        {
          assertion = pathWithinDataDir cfg.deployment.npmSecurity.quarantineStateFile;
          message = ''
            mySystem.deployment.npmSecurity.quarantineStateFile must stay under
            mySystem.mcpServers.dataDir (${dataDir}) so mount namespacing remains
            declarative and robust.
          '';
        }
        {
          assertion = pathWithinDataDir cfg.deployment.npmSecurity.incidentLogFile;
          message = ''
            mySystem.deployment.npmSecurity.incidentLogFile must stay under
            mySystem.mcpServers.dataDir (${dataDir}) so mount namespacing remains
            declarative and robust.
          '';
        }
      ];

      systemd.services.ai-mutable-path-bootstrap = {
        description = "AI stack mutable path bootstrap";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        before = [
          "ai-aidb.service"
          "ai-hybrid-coordinator.service"
          "ai-ralph-wiggum.service"
          "ai-aider-wrapper.service"
          "ai-nixos-docs.service"
        ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          set -euo pipefail
          create_path() {
            local path="$1"
            ${pkgs.coreutils}/bin/install -d -m 0750 -o ${lib.escapeShellArg svcUser} -g ${lib.escapeShellArg svcGroup} "$path"
          }
          ${lib.concatMapStringsSep "\n" (path: "create_path ${lib.escapeShellArg path}") (lib.unique (runtimeWorkspaceRoots ++ mutableProgramPaths ++ cfg.deployment.mutableSpaces.userWritablePaths))}
        '';
      };

      # ── System user / group ─────────────────────────────────────────────────
      # ── State directories ───────────────────────────────────────────────────
      systemd.tmpfiles.rules =
        [
          "d ${dataDir}                    0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/aidb               0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/aidb/logs          0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/aidb/telemetry     0750 ${svcUser} ${svcGroup} -"
          "f ${dataDir}/aidb/telemetry/aidb-events.jsonl 0640 ${svcUser} ${svcGroup} - -"
          "d ${dataDir}/hybrid             0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/hybrid/telemetry   0750 ${svcUser} ${svcGroup} -"
          "f ${dataDir}/hybrid/telemetry/hybrid-events.jsonl 0640 ${svcUser} ${svcGroup} - -"
          "f ${dataDir}/hybrid/telemetry/continuous_learning_stats.json 0640 ${svcUser} ${svcGroup} - -"
          "d ${dataDir}/ralph              0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/ralph/state        0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/ralph/telemetry    0750 ${svcUser} ${svcGroup} -"
          "f ${dataDir}/ralph/telemetry/ralph-events.jsonl 0640 ${svcUser} ${svcGroup} - -"
          "d ${dataDir}/security           0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/security/npm       0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/qdrant-collections          0750 ${svcUser} ${svcGroup} -"
          "d /var/log/ai-stack                      0750 ${svcUser} ${svcGroup} -"
          "d ${mutableLogDir}                       0750 ${svcUser} ${svcGroup} -"
          "f ${mutableLogDir}/hint-feedback.jsonl 0640 ${svcUser} ${svcGroup} - -"
          "f ${mutableLogDir}/query-gaps.jsonl 0640 ${svcUser} ${svcGroup} - -"
          # Audit sidecar log dir — used when socket-activated sidecar writes JSONL.
          "d /var/log/ai-audit-sidecar              0750 ${svcUser} ${svcGroup} -"
          "f /var/log/ai-audit-sidecar/tool-audit.jsonl 0640 ${svcUser} ${svcGroup} - -"
          "d ${dataDir}/aider-wrapper               0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/aider-wrapper/workspace     0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/nixos-docs           0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/nixos-docs/cache     0750 ${svcUser} ${svcGroup} -"
          "d ${dataDir}/nixos-docs/repos     0750 ${svcUser} ${svcGroup} -"
        ]
        ++ map (path: "d ${path} 0750 ${svcUser} ${svcGroup} -") (lib.unique [
          (builtins.dirOf cfg.deployment.npmSecurity.quarantineStateFile)
          (builtins.dirOf cfg.deployment.npmSecurity.incidentLogFile)
        ])
        ++ map (root: "d ${root} 0750 ${svcUser} ${svcGroup} -") runtimeWorkspaceRoots;

      # ── Firewall: expose MCP ports on LAN when requested ───────────────────
      # embeddingsPort (:8001) omitted — embeddings served by llama-cpp-embed.
      networking.firewall.allowedTCPPorts = lib.mkIf ai.listenOnLan [
        mcp.aidbPort
        mcp.hybridPort
        mcp.ralphPort
        mcp.nixosDocsPort
      ];

      systemd.targets.ai-stack = {
        description = "Declarative AI stack orchestration target";
        wantedBy = ["multi-user.target"];
        wants = aiStackTargetWants ++ ["network-online.target"];
        after = ["network-online.target"];
      };
    })

    (lib.mkIf active {
      systemd.services.ai-otel-collector = {
        description = "AI stack OpenTelemetry collector";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        # Phase 21.1 — Wait for Tempo to be ready before forwarding traces.
        after =
          ["network-online.target"]
          ++ lib.optional cfg.monitoring.tracing.enable "ai-tempo.service";
        wants =
          ["network-online.target"]
          ++ lib.optional cfg.monitoring.tracing.enable "ai-tempo.service";
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
        enable = lib.mkDefault true;
        extensions = ps: with ps; [pgvector];
        ensureDatabases = [mcp.postgres.database];
        ensureUsers = [
          {
            name = mcp.postgres.user;
            ensureDBOwnership = true;
          }
        ];
        settings.port = ports.postgres;
        authentication = lib.mkIf (!sec.enable) ''
          local all postgres                                peer map=postgres
          local ${mcp.postgres.database} ${mcp.postgres.user} trust
          host  ${mcp.postgres.database} ${mcp.postgres.user} 127.0.0.1/32 trust
          host  ${mcp.postgres.database} ${mcp.postgres.user} ::1/128      trust
        '';
      };

      systemd.services.postgresql.partOf = ["ai-stack.target"];

      systemd.services.ai-pgvector-bootstrap = {
        description = "Bootstrap pgvector extension for AIDB database";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = ["postgresql.service" "postgresql-setup.service"];
        requires = ["postgresql.service" "postgresql-setup.service"];
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
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        wants = ["network-online.target"];
        after =
          ["network-online.target"]
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
          [900 1]
          [300 10]
          [60 10000]
        ];
        settings = {
          maxmemory = mcp.redis.maxmemory;
          maxmemory-policy = mcp.redis.maxmemoryPolicy;
        };
      };

      systemd.services.redis-mcp.partOf = ["ai-stack.target"];
    })

    # ── Embeddings: delegated to llama-cpp-embed (ai-stack.nix) ─────────────
    # No separate Python embeddings service — llama-cpp-embed on
    # ai.embeddingServer.port provides /v1/embeddings (OpenAI-compatible).
    # AIDB and hybrid-coordinator reference embedUrl defined in the let block.

    # ── AIDB MCP server — tool-discovery + RAG + telemetry ───────────────────
    (lib.mkIf active {
      systemd.services.ai-aidb = {
        description = "AIDB MCP server (tool-discovery + RAG)";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = aidbDeps;
        requires = aidbDeps;
        wants = ["network-online.target"];
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
        serviceConfig =
          commonServiceConfig
          // {
            ExecStart = lib.escapeShellArgs [
              "${aidbPython}/bin/python3"
              "${repoMcp}/aidb/server.py"
            ];
            Environment =
              [
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
                "AIDB_SHARED_SKILLS_DIR=${dataDir}/aidb/shared-skills"
                "XDG_STATE_HOME=${dataDir}/aidb/state"
                "AIDB_VSCODE_TELEMETRY_DIR=${dataDir}/aidb/telemetry"
                "POSTGRES_HOST=127.0.0.1"
                "POSTGRES_PORT=${toString ports.postgres}"
                "POSTGRES_DB=${mcp.postgres.database}"
                "POSTGRES_USER=${mcp.postgres.user}"
                "AIDB_REDIS_HOST=127.0.0.1"
                "AIDB_REDIS_PORT=${toString mcp.redis.port}"
                "AIDB_REDIS_DB=0"
                # Phase 13.2.1 — explicit allowlist required by AI_STRICT_ENV.
                # googleapis.com is the only external host aidb may call (Google Search tool).
                # Application-level outbound allowlist is the egress defence-in-depth (Phase 13.2.1).
                "AIDB_OUTBOUND_ALLOWLIST=googleapis.com"
                # Phase 12.3.2 — audit sidecar socket path (service writes here, never to file directly)
                "AUDIT_SOCKET_PATH=/run/ai-audit-sidecar.sock"
                "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
                "HYBRID_COORDINATOR_URL=http://127.0.0.1:${toString mcp.hybridPort}"
                "RALPH_URL=http://127.0.0.1:${toString mcp.ralphPort}"
                "AI_TOOL_SECURITY_AUDIT_ENABLED=${
                  if ai.aiHarness.runtime.toolSecurity.enable
                  then "true"
                  else "false"
                }"
                "AI_TOOL_SECURITY_AUDIT_ENFORCE=${
                  if ai.aiHarness.runtime.toolSecurity.enforce
                  then "true"
                  else "false"
                }"
                "AI_TOOL_SECURITY_CACHE_TTL_HOURS=${toString ai.aiHarness.runtime.toolSecurity.cacheTtlHours}"
                "RUNTIME_TOOL_SECURITY_POLICY_FILE=${runtimeToolSecurityPolicyJson}"
                "PYTHONPATH=${repoMcp}:${repoMcp}/aidb"
              ]
              ++ lib.optional mcp.postgres.enable
              "DATABASE_URL=${pgUrl}"
              ++ lib.optional sec.enable "EMBEDDINGS_API_KEY_FILE=${secretPath embeddingsApiKeySecret}"
              ++ lib.optional sec.enable "AIDB_API_KEY_FILE=${secretPath aidbApiKeySecret}"
              ++ lib.optional sec.enable "AIDB_POSTGRES_PASSWORD_FILE=${secretPath postgresPasswordSecret}";
          }
          // lib.optionalAttrs embedEnabled {
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
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = hybridDeps;
        requires = hybridDeps;
        wants = ["network-online.target"];
        serviceConfig =
          commonServiceConfig
          // {
            ExecStart = lib.escapeShellArgs [
              "${hybridPython}/bin/python3"
              "${repoMcp}/hybrid-coordinator/server.py"
            ];
            Environment =
              [
                "PORT=${toString mcp.hybridPort}"
                "AI_STRICT_ENV=true"
                "MCP_SERVER_MODE=http"
                "MCP_SERVER_PORT=${toString mcp.hybridPort}"
                "HOST=127.0.0.1"
                "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
                "LLAMA_CPP_INFERENCE_TIMEOUT_SECONDS=${toString llama.inferenceTimeoutSeconds}"
                "SWITCHBOARD_URL=http://127.0.0.1:${toString ports.switchboard}"
                "SWITCHBOARD_REMOTE_URL=${
                  if ai.switchboard.remoteUrl != null
                  then ai.switchboard.remoteUrl
                  else ""
                }"
                "SWITCHBOARD_REMOTE_ALIAS_GEMINI=${
                  if ai.switchboard.remoteModelAliases.gemini != null
                  then ai.switchboard.remoteModelAliases.gemini
                  else if ai.switchboard.remoteModelAliases.free != null
                  then ai.switchboard.remoteModelAliases.free
                  else ""
                }"
                "SWITCHBOARD_REMOTE_ALIAS_FREE=${
                  if ai.switchboard.remoteModelAliases.free != null
                  then ai.switchboard.remoteModelAliases.free
                  else ""
                }"
                "SWITCHBOARD_REMOTE_ALIAS_CODING=${
                  if ai.switchboard.remoteModelAliases.coding != null
                  then ai.switchboard.remoteModelAliases.coding
                  else ""
                }"
                "SWITCHBOARD_REMOTE_ALIAS_REASONING=${
                  if ai.switchboard.remoteModelAliases.reasoning != null
                  then ai.switchboard.remoteModelAliases.reasoning
                  else ""
                }"
                "SWITCHBOARD_REMOTE_ALIAS_TOOL_CALLING=${
                  if ai.switchboard.remoteModelAliases.toolCalling != null
                  then ai.switchboard.remoteModelAliases.toolCalling
                  else ""
                }"
                "RALPH_WIGGUM_URL=http://127.0.0.1:${toString mcp.ralphPort}"
                "AI_TASK_CLASSIFICATION_ENABLED=true"
                "LOCAL_MAX_INPUT_TOKENS=600"
                "LOCAL_MAX_OUTPUT_TOKENS=300"
                "LOCAL_CONFIDENCE_THRESHOLD=0.35"
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
                "HYBRID_TELEMETRY_PATH=${dataDir}/hybrid/telemetry/hybrid-events.jsonl"
                "HYBRID_TELEMETRY_ENABLED=true"
                "OPTIMIZATION_PROPOSALS_PATH=${dataDir}/hybrid/telemetry/optimization_proposals.jsonl"
                "CONTINUOUS_LEARNING_CHECKPOINT_DIR=${dataDir}/hybrid/checkpoints"
                "FINETUNE_DATA_PATH=${dataDir}/hybrid/fine-tuning/dataset.jsonl"
                "HINT_AUDIT_LOG_PATH=${mutableLogDir}/hint-audit.jsonl"
                "HINT_FEEDBACK_LOG_PATH=${mutableLogDir}/hint-feedback.jsonl"
                "POSTGRES_HOST=127.0.0.1"
                "POSTGRES_PORT=${toString ports.postgres}"
                "POSTGRES_DB=${mcp.postgres.database}"
                "POSTGRES_USER=${mcp.postgres.user}"
                "REDIS_URL=redis://127.0.0.1:${toString mcp.redis.port}/0"
                "AI_HARNESS_ENABLED=${
                  if ai.aiHarness.enable
                  then "true"
                  else "false"
                }"
                "AI_MEMORY_ENABLED=${
                  if ai.aiHarness.memory.enable
                  then "true"
                  else "false"
                }"
                "AI_MEMORY_MAX_RECALL_ITEMS=${toString ai.aiHarness.memory.maxRecallItems}"
                "AI_MEMORY_REPAIR_MISMATCHED_COLLECTIONS=${
                  if ai.aiHarness.memory.repairMismatchedCollections
                  then "true"
                  else "false"
                }"
                "AI_TREE_SEARCH_ENABLED=${
                  if ai.aiHarness.retrieval.treeSearchEnable
                  then "true"
                  else "false"
                }"
                "AI_TREE_SEARCH_MAX_DEPTH=${toString ai.aiHarness.retrieval.treeSearchMaxDepth}"
                "AI_TREE_SEARCH_BRANCH_FACTOR=${toString ai.aiHarness.retrieval.treeSearchBranchFactor}"
                "AI_HARNESS_EVAL_ENABLED=${
                  if ai.aiHarness.eval.enable
                  then "true"
                  else "false"
                }"
                "AI_HARNESS_MIN_ACCEPTANCE_SCORE=${toString ai.aiHarness.eval.minAcceptanceScore}"
                "AI_HARNESS_MAX_LATENCY_MS=${toString ai.aiHarness.eval.maxLatencyMs}"
                "AI_HARNESS_EVAL_TIMEOUT_S=${toString ai.aiHarness.eval.timeoutSeconds}"
                "AI_HARNESS_EVAL_TIMEOUT_HARD_CAP_S=${toString ai.aiHarness.eval.timeoutHardCapSeconds}"
                "AI_SEMANTIC_TOOLING_AUTORUN=${
                  if ai.aiHarness.runtime.semanticToolingAutorun
                  then "true"
                  else "false"
                }"
                "AI_HINT_FEEDBACK_DB_ENABLED=${
                  if ai.aiHarness.runtime.hintFeedbackDbEnabled
                  then "true"
                  else "false"
                }"
                "AI_HINT_FEEDBACK_DB_CACHE_TTL_SECONDS=${toString ai.aiHarness.runtime.hintFeedbackDbCacheTtlSeconds}"
                "AI_HINT_DIVERSITY_REPEAT_WINDOW=${toString ai.aiHarness.runtime.hintDiversityRepeatWindow}"
                "AI_HINT_DIVERSITY_REPEAT_CAP_PCT=${toString ai.aiHarness.runtime.hintDiversityRepeatCapPct}"
                "AI_HINT_DIVERSITY_REPEAT_MIN_COUNT=${toString ai.aiHarness.runtime.hintDiversityRepeatMinCount}"
                "AI_HINT_DIVERSITY_TYPE_MIN=${ai.aiHarness.runtime.hintDiversityTypeMin}"
                "AI_HINT_DIVERSITY_TYPE_MAX=${ai.aiHarness.runtime.hintDiversityTypeMax}"
                "AI_HINT_BANDIT_ENABLED=${
                  if ai.aiHarness.runtime.hintBandit.enable
                  then "true"
                  else "false"
                }"
                "AI_HINT_BANDIT_MIN_EVENTS=${toString ai.aiHarness.runtime.hintBandit.minEvents}"
                "AI_HINT_BANDIT_PRIOR_ALPHA=${toString ai.aiHarness.runtime.hintBandit.priorAlpha}"
                "AI_HINT_BANDIT_PRIOR_BETA=${toString ai.aiHarness.runtime.hintBandit.priorBeta}"
                "AI_HINT_BANDIT_EXPLORATION_WEIGHT=${toString ai.aiHarness.runtime.hintBandit.explorationWeight}"
                "AI_HINT_BANDIT_MAX_ADJUST=${toString ai.aiHarness.runtime.hintBandit.maxAdjust}"
                "AI_HINT_BANDIT_CONFIDENCE_FLOOR=${toString ai.aiHarness.runtime.hintBandit.confidenceFloor}"
                "AI_RUN_DEFAULT_SAFETY_MODE=${ai.aiHarness.runtime.defaultSafetyMode}"
                "AI_RUN_DEFAULT_TOKEN_LIMIT=${toString ai.aiHarness.runtime.defaultTokenLimit}"
                "AI_RUN_DEFAULT_TOOL_CALL_LIMIT=${toString ai.aiHarness.runtime.defaultToolCallLimit}"
                "AI_SEMANTIC_CACHE_WARM_ON_START=${
                  if ai.aiHarness.runtime.cachePrewarm.startupWarmEnable
                  then "true"
                  else "false"
                }"
                "AI_SEMANTIC_CACHE_WARM_QUERIES=${lib.escapeShellArg (lib.concatStringsSep "|" ai.aiHarness.runtime.cachePrewarm.startupQueries)}"
                "RUNTIME_SAFETY_POLICY_FILE=${runtimeSafetyPolicyJson}"
                "RUNTIME_ISOLATION_PROFILES_FILE=${runtimeIsolationProfilesJson}"
                "WORKFLOW_BLUEPRINTS_FILE=${repoSource}/config/workflow-blueprints.json"
                "RUNTIME_SCHEDULER_POLICY_FILE=${runtimeSchedulerPolicyJson}"
                "PARITY_SCORECARD_FILE=${parityScorecardJson}"
                "AI_TOOL_SECURITY_AUDIT_ENABLED=${
                  if ai.aiHarness.runtime.toolSecurity.enable
                  then "true"
                  else "false"
                }"
                "AI_TOOL_SECURITY_AUDIT_ENFORCE=${
                  if ai.aiHarness.runtime.toolSecurity.enforce
                  then "true"
                  else "false"
                }"
                "AI_TOOL_SECURITY_CACHE_TTL_HOURS=${toString ai.aiHarness.runtime.toolSecurity.cacheTtlHours}"
                "RUNTIME_TOOL_SECURITY_POLICY_FILE=${runtimeToolSecurityPolicyJson}"
                "AI_CODE_EXEC_TOOLING_MANIFEST_ENABLED=${
                  if ai.aiHarness.runtime.codeExecution.enable
                  then "true"
                  else "false"
                }"
                "AI_CODE_EXEC_MAX_TOOLS=${toString ai.aiHarness.runtime.codeExecution.maxManifestTools}"
                "AI_CODE_EXEC_MAX_RESULT_CHARS=${toString ai.aiHarness.runtime.codeExecution.maxResultChars}"
                "AI_CODE_EXEC_MAX_REASON_CHARS=${toString ai.aiHarness.runtime.codeExecution.maxReasonChars}"
                "AI_WEB_RESEARCH_ENABLED=${
                  if ai.aiHarness.runtime.webResearch.enable
                  then "true"
                  else "false"
                }"
                "AI_WEB_RESEARCH_MAX_URLS=${toString ai.aiHarness.runtime.webResearch.maxUrls}"
                "AI_WEB_RESEARCH_MAX_SELECTORS=${toString ai.aiHarness.runtime.webResearch.maxSelectors}"
                "AI_WEB_RESEARCH_TIMEOUT_SECONDS=${toString ai.aiHarness.runtime.webResearch.timeoutSeconds}"
                "AI_WEB_RESEARCH_PER_HOST_DELAY_SECONDS=${toString ai.aiHarness.runtime.webResearch.perHostDelaySeconds}"
                "AI_WEB_RESEARCH_MAX_RESPONSE_BYTES=${toString ai.aiHarness.runtime.webResearch.maxResponseBytes}"
                "AI_WEB_RESEARCH_MAX_TEXT_CHARS=${toString ai.aiHarness.runtime.webResearch.maxTextChars}"
                "AI_WEB_RESEARCH_MAX_LINKS=${toString ai.aiHarness.runtime.webResearch.maxLinks}"
                "AI_WEB_RESEARCH_MAX_REDIRECTS=${toString ai.aiHarness.runtime.webResearch.maxRedirects}"
                "AI_WEB_RESEARCH_USER_AGENT=${lib.escapeShellArg ai.aiHarness.runtime.webResearch.userAgent}"
                "AI_BROWSER_RESEARCH_ENABLED=${
                  if ai.aiHarness.runtime.browserResearch.enable
                  then "true"
                  else "false"
                }"
                "AI_BROWSER_RESEARCH_MAX_URLS=${toString ai.aiHarness.runtime.browserResearch.maxUrls}"
                "AI_BROWSER_RESEARCH_MAX_SELECTORS=${toString ai.aiHarness.runtime.browserResearch.maxSelectors}"
                "AI_BROWSER_RESEARCH_TIMEOUT_SECONDS=${toString ai.aiHarness.runtime.browserResearch.timeoutSeconds}"
                "AI_BROWSER_RESEARCH_PER_HOST_DELAY_SECONDS=${toString ai.aiHarness.runtime.browserResearch.perHostDelaySeconds}"
                "AI_BROWSER_RESEARCH_MAX_TEXT_CHARS=${toString ai.aiHarness.runtime.browserResearch.maxTextChars}"
                "AI_BROWSER_RESEARCH_MAX_LINKS=${toString ai.aiHarness.runtime.browserResearch.maxLinks}"
                "AI_BROWSER_RESEARCH_MAX_REDIRECTS=${toString ai.aiHarness.runtime.browserResearch.maxRedirects}"
                "AI_BROWSER_RESEARCH_USER_AGENT=${lib.escapeShellArg ai.aiHarness.runtime.browserResearch.userAgent}"
                "AI_BROWSER_RESEARCH_CHROMIUM_BIN=${
                  if ai.aiHarness.runtime.browserResearch.chromiumBinary == "chromium"
                  then lib.getExe pkgs.chromium
                  else ai.aiHarness.runtime.browserResearch.chromiumBinary
                }"
                "AI_BROWSER_RESEARCH_VIRTUAL_TIME_BUDGET_MS=${toString ai.aiHarness.runtime.browserResearch.virtualTimeBudgetMs}"
                "AI_LOCAL_SYSTEM_PROMPT=${
                  if ai.aiHarness.runtime.localSystemPrompt.enable
                  then "true"
                  else "false"
                }"
                "AI_LOCAL_SYSTEM_PROMPT_IDENTITY=${lib.escapeShellArg ai.aiHarness.runtime.localSystemPrompt.identity}"
                "AI_LOCAL_SYSTEM_PROMPT_RULES_JSON=${builtins.toJSON ai.aiHarness.runtime.localSystemPrompt.rules}"
                "AI_LOCAL_SYSTEM_PROMPT_WORKFLOW_JSON=${builtins.toJSON ai.aiHarness.runtime.localSystemPrompt.workflow}"
                "AI_LOCAL_SYSTEM_PROMPT_OUTPUT_SECTIONS_JSON=${builtins.toJSON ai.aiHarness.runtime.localSystemPrompt.outputSections}"
                "AI_LOCAL_FRONTDOOR_ROUTING_ENABLE=${
                  if ai.aiHarness.runtime.localFrontdoorRouting.enable
                  then "true"
                  else "false"
                }"
                "AI_LOCAL_FRONTDOOR_DEFAULT_PROFILE=${ai.aiHarness.runtime.localFrontdoorRouting.defaultProfile}"
                "AI_LOCAL_FRONTDOOR_EXPLORE_PROFILE=${ai.aiHarness.runtime.localFrontdoorRouting.explorationProfile}"
                "AI_LOCAL_FRONTDOOR_PLAN_PROFILE=${ai.aiHarness.runtime.localFrontdoorRouting.planningProfile}"
                "AI_LOCAL_FRONTDOOR_IMPLEMENTATION_PROFILE=${ai.aiHarness.runtime.localFrontdoorRouting.implementationProfile}"
                "AI_LOCAL_FRONTDOOR_REASONING_PROFILE=${ai.aiHarness.runtime.localFrontdoorRouting.reasoningProfile}"
                "AI_LOCAL_FRONTDOOR_TOOL_CALLING_PROFILE=${ai.aiHarness.runtime.localFrontdoorRouting.toolCallingProfile}"
                "AI_LOCAL_FRONTDOOR_CONTINUATION_PROFILE=${ai.aiHarness.runtime.localFrontdoorRouting.continuationProfile}"
                "PYTHONPATH=${workflowHandlersPkg}/${pkgs.python3.sitePackages}:${repoMcp}:${repoMcp}/hybrid-coordinator"
                # Phase 12.3.2 — audit sidecar socket path
                "AUDIT_SOCKET_PATH=/run/ai-audit-sidecar.sock"
              ]
              ++ lib.optional mcp.postgres.enable
              "DATABASE_URL=${pgUrl}"
              ++ lib.optional sec.enable "EMBEDDING_API_KEY_FILE=${secretPath embeddingsApiKeySecret}"
              ++ lib.optional sec.enable "HYBRID_API_KEY_FILE=${secretPath hybridApiKeySecret}"
              ++ lib.optional sec.enable "RALPH_WIGGUM_API_KEY_FILE=${secretPath aidbApiKeySecret}"
              ++ lib.optional sec.enable "POSTGRES_PASSWORD_FILE=${secretPath postgresPasswordSecret}";
            EnvironmentFile = "-${mutableOptimizerDir}/overrides.env";
          };
      };
    })

    # ── Ralph Wiggum — loop orchestrator + agent chain execution ─────────────
    (lib.mkIf active {
      systemd.services.ai-ralph-wiggum = {
        description = "AI ralph-wiggum loop orchestrator";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = ralphDeps;
        requires = ralphDeps;
        wants = ["network-online.target"];
        serviceConfig =
          commonServiceConfig
          // {
            ExecStart = lib.escapeShellArgs [
              "${ralphPython}/bin/python3"
              "${repoMcp}/ralph-wiggum/server.py"
            ];
            Environment =
              [
                "AI_STRICT_ENV=true"
                "PORT=${toString mcp.ralphPort}"
                "HOST=127.0.0.1"
                "LLAMA_CPP_BASE_URL=http://127.0.0.1:${toString llama.port}"
                "HYBRID_COORDINATOR_URL=http://127.0.0.1:${toString mcp.hybridPort}"
                "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
                "HYBRID_API_KEY_FILE=${secretPath hybridApiKeySecret}"
                "AIDER_WRAPPER_HOST=127.0.0.1"
                "AIDER_WRAPPER_PORT=${toString mcp.aiderWrapperPort}"
                "DATA_DIR=${dataDir}/ralph"
                "XDG_STATE_HOME=${dataDir}/ralph/state"
                "RALPH_STATE_FILE=${dataDir}/ralph/ralph-state.json"
                "RALPH_TELEMETRY_PATH=${dataDir}/ralph/telemetry/ralph-events.jsonl"
                "RALPH_AUDIT_LOG=true"
                "POSTGRES_HOST=127.0.0.1"
                "POSTGRES_PORT=${toString ports.postgres}"
                "POSTGRES_DB=${mcp.postgres.database}"
                "POSTGRES_USER=${mcp.postgres.user}"
                "PYTHONPATH=${repoMcp}:${repoMcp}/ralph-wiggum"
              ]
              ++ lib.optional mcp.postgres.enable
              "DATABASE_URL=${pgUrl}"
              ++ lib.optional sec.enable "RALPH_WIGGUM_API_KEY_FILE=${secretPath aidbApiKeySecret}";
            # Phase 13.1.1 — ralph only communicates with loopback services
            IPAddressAllow = ["127.0.0.1/8" "::1/128"];
            IPAddressDeny = ["any"];
          };
      };
    })

    # ── Aider Wrapper — async code modification MCP server ───────────────────
    (lib.mkIf active {
      systemd.services.ai-aider-wrapper = {
        description = "Aider Wrapper MCP server (async code modification)";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = ["network-online.target" mutableBootstrapUnit];
        requires = [mutableBootstrapUnit];
        wants = ["network-online.target"];
        serviceConfig =
          commonServiceConfig
          // {
            ExecStart = lib.escapeShellArgs [
              "${aiderPython}/bin/python3"
              "${repoMcp}/aider-wrapper/server.py"
            ];
            Environment =
              [
                "AIDER_WRAPPER_PORT=${toString mcp.aiderWrapperPort}"
                "AIDER_TASK_TIMEOUT_SECONDS=600"
                "AIDER_TERMINATE_GRACE_SECONDS=5"
                "AIDER_WATCHDOG_INTERVAL_SECONDS=10"
                "AIDER_WATCHDOG_MAX_RUNTIME_SECONDS=180"
                "AIDER_BIN=${pkgs."aider-chat"}/bin/aider"
                "AIDER_WORKSPACE=${dataDir}/aider-wrapper/workspace"
                "LLAMA_CPP_HOST=127.0.0.1"
                "LLAMA_CPP_PORT=${toString llama.port}"
                "PYTHONPATH=${repoMcp}:${repoMcp}/aider-wrapper"
                # Phase 14.1.1 — bubblewrap filesystem sandbox for aider subprocess.
                "AI_AIDER_SANDBOX=true"
                "BWRAP_PATH=${pkgs.bubblewrap}/bin/bwrap"
                # If unprivileged user namespaces are disabled, retry once unsandboxed
                # so hint/eval feedback loops still complete on constrained hosts.
                "AI_AIDER_SANDBOX_FALLBACK_UNSAFE=true"
                # Phase 19.3.3 — prepend top aq-hint to aider --message for steered task execution.
                "AI_HINTS_ENABLED=true"
                "AI_HINTS_MIN_SCORE=${toString ai.aiHarness.runtime.aiderHintsMinScore}"
                "AI_HINTS_MIN_SNIPPET_CHARS=${toString ai.aiHarness.runtime.aiderHintsMinSnippetChars}"
                "AI_HINTS_MIN_TOKEN_OVERLAP=${toString ai.aiHarness.runtime.aiderHintsMinTokenOverlap}"
                "AI_HINTS_BYPASS_OVERLAP_SCORE=${toString ai.aiHarness.runtime.aiderHintsBypassOverlapScore}"
                "AI_TOOLING_PLAN_ENABLED=${
                  if ai.aiHarness.runtime.aiderToolingPlanEnabled
                  then "true"
                  else "false"
                }"
                "AI_AIDER_SMALL_SCOPE_SUBTREE_ONLY=${
                  if ai.aiHarness.runtime.aiderSmallScopeSubtreeOnly
                  then "true"
                  else "false"
                }"
                "AIDER_SMALL_SCOPE_MAP_TOKENS=${toString ai.aiHarness.runtime.aiderSmallScopeMapTokens}"
                "AI_AIDER_ANALYSIS_FAST_MODE=${
                  if ai.aiHarness.runtime.aiderAnalysisFastMode
                  then "true"
                  else "false"
                }"
                "AIDER_ANALYSIS_MAP_TOKENS=${toString ai.aiHarness.runtime.aiderAnalysisMapTokens}"
                "AIDER_ANALYSIS_MAX_RUNTIME_SECONDS=${toString ai.aiHarness.runtime.aiderAnalysisMaxRuntimeSeconds}"
                "AI_AIDER_ANALYSIS_ROUTE_TO_HYBRID=${
                  if ai.aiHarness.runtime.aiderAnalysisRouteToHybrid
                  then "true"
                  else "false"
                }"
                "AI_AIDER_AUTO_FILE_SCOPE=${
                  if ai.aiHarness.runtime.aiderAutoFileScope
                  then "true"
                  else "false"
                }"
                "AIDER_AUTO_FILE_SCOPE_MAX=${toString ai.aiHarness.runtime.aiderAutoFileScopeMax}"
                "AIDER_DEFAULT_MAP_TOKENS=${toString ai.aiHarness.runtime.aiderDefaultMapTokens}"
                "HINTS_URL=http://127.0.0.1:${toString mcp.hybridPort}/hints"
                "HINT_FEEDBACK_URL=http://127.0.0.1:${toString mcp.hybridPort}/hints/feedback"
                "WORKFLOW_PLAN_URL=http://127.0.0.1:${toString mcp.hybridPort}/workflow/plan"
                "HINT_AUDIT_LOG_PATH=${mutableLogDir}/hint-audit.jsonl"
                "HINT_FEEDBACK_LOG_PATH=${mutableLogDir}/hint-feedback.jsonl"
                "TASK_AUDIT_LOG_PATH=${mutableLogDir}/aider-task-audit.jsonl"
              ]
              ++ lib.optional sec.enable "AIDER_WRAPPER_API_KEY_FILE=${secretPath aiderWrapperApiKeySecret}"
              ++ lib.optional sec.enable "HYBRID_API_KEY_FILE=${secretPath hybridApiKeySecret}";
            # hint-audit.jsonl and tool-audit.jsonl both land in the mutable AI log dir.
            ReadWritePaths = [dataDir "/tmp" mutableLogDir];
            # Phase 13.1.1 — aider-wrapper only communicates with loopback services
            IPAddressAllow = ["127.0.0.1/8" "::1/128"];
            IPAddressDeny = ["any"];
          };
      };
    })

    # ── NixOS Docs — documentation MCP server ─────────────────────────────────
    (lib.mkIf active {
      systemd.services.ai-nixos-docs = {
        description = "NixOS documentation MCP server";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after =
          ["network-online.target" mutableBootstrapUnit]
          ++ lib.optional mcp.redis.enable redisUnit;
        requires =
          [mutableBootstrapUnit]
          ++ lib.optional mcp.redis.enable redisUnit;
        wants = ["network-online.target"];
        serviceConfig =
          commonServiceConfig
          // {
            ExecStart = lib.escapeShellArgs [
              "${nixosDocsPython}/bin/uvicorn"
              "server:app"
              "--host"
              "127.0.0.1"
              "--port"
              (toString mcp.nixosDocsPort)
              "--no-access-log"
            ];
            WorkingDirectory = "${repoMcp}/nixos-docs";
            Environment = [
              "NIXOS_DOCS_PORT=${toString mcp.nixosDocsPort}"
              "REDIS_HOST=127.0.0.1"
              "REDIS_PORT=${toString mcp.redis.port}"
              "NIXOS_CACHE_DIR=${dataDir}/nixos-docs/cache"
              "NIXOS_REPOS_DIR=${dataDir}/nixos-docs/repos"
              "NIXOS_CACHE_TTL=86400"
              "PYTHONPATH=${repoMcp}:${repoMcp}/nixos-docs"
            ];
            ReadWritePaths = [dataDir "/tmp" "${dataDir}/nixos-docs"];
          };
      };
    })

    # ── Knowledge Source Sync — weekly AIDB source refresh ───────────────────
    (lib.mkIf active {
      systemd.services.ai-sync-knowledge-sources = {
        description = "AI knowledge source sync (AIDB import registry)";
        after = ["ai-aidb.service" "network-online.target"];
        requires = ["ai-aidb.service"];
        wants = ["network-online.target"];
        serviceConfig =
          commonServiceConfig
          // {
            Type = "oneshot";
            ExecStart = lib.escapeShellArgs [
              "${pkgs.bash}/bin/bash"
              "${repoSource}/scripts/data/sync-knowledge-sources"
            ];
            Environment =
              [
                "PATH=${knowledgeSyncPath}"
                "AIDB_URL=http://127.0.0.1:${toString mcp.aidbPort}"
                "XDG_CACHE_HOME=${dataDir}/hybrid/cache"
              ]
              ++ lib.optional sec.enable "AIDB_API_KEY_FILE=${secretPath aidbApiKeySecret}";
          };
      };

      systemd.timers.ai-sync-knowledge-sources = {
        description = "Weekly AI knowledge source sync timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig =
          {
            OnCalendar = "weekly";
            RandomizedDelaySec = "1h";
            Persistent = true;
            Unit = "ai-sync-knowledge-sources.service";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };
    })

    # ── Phase 11.5: Security Audit — weekly pip-audit + npm audit ───────────
    (lib.mkIf active {
      systemd.services.ai-security-audit = {
        description = "AI Stack security vulnerability audit (pip-audit + npm audit)";
        after = ["network-online.target"];
        wants = ["network-online.target"];
        path = [
          pkgs.bash
          pkgs.coreutils
          pkgs.curl
          pkgs.findutils
          pkgs.jq
          pkgs.nodejs
          pkgs.pip-audit
          pkgs.python3
          pkgs.rage
          pkgs.sops
        ];
        serviceConfig = {
          Type = "oneshot";
          User = svcUser;
          Group = svcGroup;
          WorkingDirectory = dataDir;
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${repoSource}/scripts/security/security-audit.sh"
            "--repo-root"
            mcp.repoPath
            "--output-dir"
            "${dataDir}/security"
          ];
          # Security hardening — read-only access except output dir
          ReadOnlyPaths = ["/"];
          ReadWritePaths = ["${dataDir}/security"];
          PrivateTmp = true;
          ProtectHome = "read-only";
          ProtectSystem = "strict";
          NoNewPrivileges = true;
          # Allow network access for vulnerability database lookups
          PrivateNetwork = false;
          # Restrict to minimal syscalls
          SystemCallFilter = ["@system-service" "~@privileged"];
          # Memory limit appropriate for audit tooling
          MemoryMax = "1G";
          # Log to journal
          StandardOutput = "journal";
          StandardError = "journal";
        };
        environment = {
          # Pass configuration from options (Phase 11.5.2)
          AI_SECURITY_AUDIT_HIGH_CVSS_THRESHOLD = toString cfg.deployment.securityAuditHighCvssThreshold;
          AI_SECURITY_AUDIT_NOTIFY_USER = svcUser;
        };
      };

      systemd.timers.ai-security-audit = {
        description = "Weekly AI stack security audit timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig =
          {
            OnCalendar = "weekly";
            RandomizedDelaySec = "2h";
            Persistent = true;
            Unit = "ai-security-audit.service";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };

      systemd.services.ai-npm-security-monitor = lib.mkIf cfg.deployment.npmSecurity.enable {
        description = "AI Stack npm supply-chain security monitor";
        # Timer/manual-trigger driven; do not block ai-stack.target activation.
        path = with pkgs; [
          bash
          coreutils
          findutils
          gawk
          gnugrep
          jq
          nodejs
          python3
          ripgrep
        ];
        after = ["network-online.target" "systemd-tmpfiles-setup.service"];
        wants = ["network-online.target" "systemd-tmpfiles-setup.service"];
        serviceConfig = {
          Type = "oneshot";
          User = svcUser;
          Group = svcGroup;
          WorkingDirectory = dataDir;
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${repoSource}/scripts/security/npm-security-monitor.sh"
            "--repo-root"
            mcp.repoPath
            "--output-dir"
            "${dataDir}/security/npm"
          ];
          ReadOnlyPaths = ["/"];
          # Keep namespace requirements stable by anchoring writes to dataDir.
          # Per-path confinement is still preserved by service logic + assertions.
          ReadWritePaths = ["${dataDir}"];
          PrivateTmp = true;
          # Repo lives under /home/<primaryUser>; allow read-only traversal.
          ProtectHome = "read-only";
          ProtectSystem = "strict";
          NoNewPrivileges = true;
          PrivateNetwork = false;
          SystemCallFilter = ["@system-service" "~@privileged"];
          MemoryMax = "1G";
          StandardOutput = "journal";
          StandardError = "journal";
        };
        environment = {
          NPM_SECURITY_LOG_LOOKBACK_HOURS = toString cfg.deployment.npmSecurity.suspiciousLogLookbackHours;
          NPM_SECURITY_FAIL_ON_HIGH = lib.boolToString cfg.deployment.npmSecurity.failOnHigh;
          NPM_SECURITY_RESPONSE_MODE = cfg.deployment.npmSecurity.responseMode;
          NPM_SECURITY_THREAT_INTEL_FILE = cfg.deployment.npmSecurity.threatIntelFile;
          NPM_SECURITY_QUARANTINE_STATE_FILE = cfg.deployment.npmSecurity.quarantineStateFile;
          NPM_SECURITY_INCIDENT_LOG_FILE = cfg.deployment.npmSecurity.incidentLogFile;
        };
      };

      systemd.timers.ai-npm-security-monitor = lib.mkIf cfg.deployment.npmSecurity.enable {
        description = "Periodic npm supply-chain security monitor timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig = {
          OnBootSec = "15min";
          OnUnitActiveSec = "${toString cfg.deployment.npmSecurity.intervalMinutes}min";
          Persistent = true;
          Unit = "ai-npm-security-monitor.service";
        };
      };

      systemd.services.ai-post-deploy-converge = {
        description = "AI stack post-deploy declarative convergence";
        # Timer/manual-trigger driven to avoid blocking ai-stack.target activation
        # during nixos-rebuild switch.
        path = with pkgs; [
          bash
          coreutils
          curl
          findutils
          gawk
          gnugrep
          jq
          nodejs
          python3
          ripgrep
          util-linux
        ];
        after = [
          "network-online.target"
          "ai-aidb.service"
          "ai-hybrid-coordinator.service"
          "ai-aider-wrapper.service"
        ];
        wants = ["network-online.target"];
        serviceConfig = {
          Type = "oneshot";
          User = svcUser;
          Group = svcGroup;
          WorkingDirectory = dataDir;
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${repoSource}/scripts/automation/post-deploy-converge.sh"
          ];
          ReadOnlyPaths = ["/"];
          ReadWritePaths = ["${dataDir}"];
          PrivateTmp = true;
          # Repo lives under /home/<primaryUser>; allow read-only traversal.
          ProtectHome = "read-only";
          ProtectSystem = "strict";
          NoNewPrivileges = true;
          PrivateNetwork = false;
          SystemCallFilter = ["@system-service" "~@privileged"];
          MemoryMax = "768M";
          StandardOutput = "journal";
          StandardError = "journal";
        };
        environment =
          {
            POST_DEPLOY_REPO_ROOT = mcp.repoPath;
            POST_DEPLOY_DATA_DIR = dataDir;
            HYBRID_URL = "http://127.0.0.1:${toString mcp.hybridPort}";
            POST_DEPLOY_NPM_OUT_DIR = "${dataDir}/security/npm";
            POST_DEPLOY_AQ_REPORT_OUT = "${dataDir}/hybrid/telemetry/latest-aq-report.json";
            POST_DEPLOY_SUMMARY_OUT = "${dataDir}/hybrid/telemetry/post-deploy-converge-latest.json";
            POST_DEPLOY_HINT_FEEDBACK_SYNC_OUT = "${dataDir}/hybrid/telemetry/hint-feedback-sync-latest.json";
            POST_DEPLOY_AUTO_REMEDIATE_OUT = "${dataDir}/hybrid/telemetry/aq-auto-remediation-latest.json";
            POST_DEPLOY_AUTO_REMEDIATE_ENABLE = lib.boolToString cfg.deployment.autoRemediation.enable;
            POST_DEPLOY_AUTO_REMEDIATE_DRY_RUN = lib.boolToString cfg.deployment.autoRemediation.dryRun;
            POST_DEPLOY_AUTO_REMEDIATE_REPORT_SINCE = cfg.deployment.autoRemediation.reportSince;
            POST_DEPLOY_INTENT_REMEDIATE_ENABLE = lib.boolToString cfg.deployment.autoRemediation.enable;
            POST_DEPLOY_INTENT_MIN_RUNS = toString cfg.deployment.autoRemediation.intentMinRuns;
            POST_DEPLOY_INTENT_MIN_COVERAGE_PCT = toString cfg.deployment.autoRemediation.intentMinCoveragePct;
            POST_DEPLOY_INTENT_TARGET_COVERAGE_PCT = toString cfg.deployment.autoRemediation.intentTargetCoveragePct;
            POST_DEPLOY_INTENT_MAX_PROBE_RUNS = toString cfg.deployment.autoRemediation.intentMaxProbeRuns;
            POST_DEPLOY_INTENT_BOUNDED_ENABLE = lib.boolToString cfg.deployment.autoRemediation.intentBoundedEnable;
            POST_DEPLOY_INTENT_BOUNDED_TARGET_COVERAGE_PCT = toString cfg.deployment.autoRemediation.intentBoundedTargetCoveragePct;
            POST_DEPLOY_INTENT_BOUNDED_RUNS_PER_PASS = toString cfg.deployment.autoRemediation.intentBoundedRunsPerPass;
            POST_DEPLOY_INTENT_BOUNDED_MAX_TOTAL_RUNS = toString cfg.deployment.autoRemediation.intentBoundedMaxTotalRuns;
            POST_DEPLOY_INTENT_BOUNDED_MAX_PASSES = toString cfg.deployment.autoRemediation.intentBoundedMaxPasses;
            POST_DEPLOY_INTENT_BOUNDED_SLEEP_SECONDS = toString cfg.deployment.autoRemediation.intentBoundedSleepSeconds;
            POST_DEPLOY_INTENT_BOUNDED_TIMEOUT_SECONDS = toString cfg.deployment.autoRemediation.intentBoundedTimeoutSeconds;
            POST_DEPLOY_HINT_BOUNDED_ENABLE = lib.boolToString cfg.deployment.autoRemediation.hintBoundedEnable;
            POST_DEPLOY_HINT_BOUNDED_TARGET_ADOPTION_PCT = toString cfg.deployment.autoRemediation.hintBoundedTargetAdoptionPct;
            POST_DEPLOY_HINT_BOUNDED_RUNS_PER_PASS = toString cfg.deployment.autoRemediation.hintBoundedRunsPerPass;
            POST_DEPLOY_HINT_BOUNDED_MAX_TOTAL_RUNS = toString cfg.deployment.autoRemediation.hintBoundedMaxTotalRuns;
            POST_DEPLOY_HINT_BOUNDED_MAX_PASSES = toString cfg.deployment.autoRemediation.hintBoundedMaxPasses;
            POST_DEPLOY_HINT_BOUNDED_POLL_MAX_SECONDS = toString cfg.deployment.autoRemediation.hintBoundedPollMaxSeconds;
            POST_DEPLOY_HINT_BOUNDED_SLEEP_SECONDS = toString cfg.deployment.autoRemediation.hintBoundedSleepSeconds;
            POST_DEPLOY_HINT_BOUNDED_TIMEOUT_SECONDS = toString cfg.deployment.autoRemediation.hintBoundedTimeoutSeconds;
            POST_DEPLOY_HINT_BOUNDED_WORKSPACE = cfg.deployment.autoRemediation.hintBoundedWorkspace;
            POST_DEPLOY_HINT_BOUNDED_FILE = cfg.deployment.autoRemediation.hintBoundedFile;
            POST_DEPLOY_STALE_GAP_CURATION_ENABLE = lib.boolToString cfg.deployment.autoRemediation.staleGapCurationEnable;
            POST_DEPLOY_STALE_GAP_MIN_TOKEN_LEN = toString cfg.deployment.autoRemediation.staleGapMinTokenLen;
            POST_DEPLOY_STALE_GAP_MAX_ROWS_PER_TOKEN = toString cfg.deployment.autoRemediation.staleGapMaxRowsPerToken;
            POST_DEPLOY_STALE_GAP_MAX_DELETE_TOTAL = toString cfg.deployment.autoRemediation.staleGapMaxDeleteTotal;
            POST_DEPLOY_BASH_BIN = "${pkgs.bash}/bin/bash";
            POST_DEPLOY_PYTHON_BIN = "${hybridPython}/bin/python3";
            POST_DEPLOY_TIMEOUT_BIN = "${pkgs.coreutils}/bin/timeout";
            POST_DEPLOY_ROUTING_SEED_TIMEOUT_SECONDS = "120";
            POST_DEPLOY_QDRANT_REBUILD_TIMEOUT_SECONDS = "900";
            POST_DEPLOY_QDRANT_REBUILD_MODE = "auto";
            POST_DEPLOY_AQ_REPORT_TIMEOUT_SECONDS = "120";
            POST_DEPLOY_HYBRID_HEALTH_RETRIES = "36";
            POST_DEPLOY_HYBRID_HEALTH_RETRY_SECONDS = "5";
            HINT_FEEDBACK_LOG_PATH = "${mutableLogDir}/hint-feedback.jsonl";
            POSTGRES_HOST = "127.0.0.1";
            POSTGRES_PORT = toString ports.postgres;
            POSTGRES_DB = mcp.postgres.database;
            POSTGRES_USER = mcp.postgres.user;
          }
          // lib.optionalAttrs sec.enable {
            POSTGRES_PASSWORD_FILE = secretPath postgresPasswordSecret;
            HYBRID_API_KEY_FILE = secretPath hybridApiKeySecret;
          };
      };

      systemd.timers.ai-post-deploy-converge = {
        description = "Periodic AI stack post-deploy convergence timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig = {
          OnBootSec = "4min";
          OnUnitActiveSec = "6h";
          Persistent = true;
          Unit = "ai-post-deploy-converge.service";
        };
      };

      # Phase 12.4.2 — Hourly MCP source file integrity check
      # ── Phase 12.3.2 — Tool audit log sidecar ────────────────────────────────
      # The socket is group-writable (svcGroup) so MCP services can send entries.
      # The sidecar runs as svcUser and owns the log dir; the socket is 0660 so
      # only svcGroup members can send entries.
      systemd.sockets.ai-audit-sidecar = {
        description = "AI stack tool audit log Unix socket";
        wantedBy = ["sockets.target"];
        socketConfig = {
          ListenStream = "/run/ai-audit-sidecar.sock";
          SocketMode = "0660";
          SocketGroup = svcGroup;
          Accept = false;
        };
      };

      systemd.services.ai-audit-sidecar = {
        description = "AI stack tool audit log sidecar";
        requires = ["ai-audit-sidecar.socket"];
        after = ["ai-audit-sidecar.socket"];
        serviceConfig =
          (mkHardenedService {
            tier = cfg.hardwareTier;
            memoryMax = "128M";
          })
          // {
            Type = "simple";
            # Must run as svcUser (not DynamicUser) because the script lives under
            # /home/<primaryUser> which is mode 0700 — a DynamicUser ephemeral UID
            # cannot traverse it regardless of ProtectHome/ReadOnlyPaths overrides.
            User = svcUser;
            Group = svcGroup;
            ProtectHome = "read-only";
            ReadOnlyPaths = [repoSource];
            LogsDirectory = "ai-audit-sidecar";
            ExecStart = "${auditSidecarPython}/bin/python3 ${auditSidecarScript}";
            Restart = "on-failure";
            RestartSec = "5s";
            RestrictAddressFamilies = ["AF_UNIX"];
            SystemCallFilter = ["@system-service"];
            SystemCallErrorNumber = "EPERM";
            Environment = [
              "TOOL_AUDIT_LOG_PATH=/var/log/ai-audit-sidecar/tool-audit.jsonl"
              "TOOL_AUDIT_FALLBACK_LOG_PATH=${mutableLogDir}/tool-audit.jsonl"
              "AUDIT_SOCKET_PATH=/run/ai-audit-sidecar.sock"
            ];
          };
      };

      systemd.services.ai-mcp-integrity-check = {
        description = "AI stack MCP source file integrity check";
        after = ["local-fs.target"];
        serviceConfig =
          (mkHardenedService {
            tier = cfg.hardwareTier;
            memoryMax = "64M";
          })
          // {
            # Phase 14.1.2 — Runs as primaryUser (not DynamicUser) because the repo
            # lives under /home/<user> (mode 0700) which ephemeral UIDs cannot traverse.
            Type = "oneshot";
            User = svcUser;
            Group = svcGroup;
            ProtectHome = "read-only";
            StateDirectory = "ai-mcp-integrity";
            ReadOnlyPaths = [
              repoSource
              mcpIntegrityBaseline
            ];
            RestrictAddressFamilies = ["AF_UNIX"];
            SystemCallFilter = ["@system-service"];
            SystemCallErrorNumber = "EPERM";
            ExecStart = "${pkgs.bash}/bin/bash ${repoSource}/scripts/testing/check-mcp-integrity.sh";
            SuccessExitStatus = [0];
            Environment = [
              "MCP_SERVER_DIR=${repoSource}/ai-stack/mcp-servers"
              "MCP_INTEGRITY_BASELINE=${mcpIntegrityBaseline}"
              "MCP_INTEGRITY_ALERT_DIR=/var/lib/ai-mcp-integrity/alerts"
            ];
          };
      };

      systemd.timers.ai-mcp-integrity-check = {
        description = "Hourly AI stack MCP source file integrity check timer";
        wantedBy = ["timers.target"];
        timerConfig =
          {
            OnCalendar = "hourly";
            RandomizedDelaySec = "5m";
            Persistent = true;
            Unit = "ai-mcp-integrity-check.service";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };
    })

    # ── Phase 12.4.1 — MCP process tree watchdog timer ───────────────────────
    # Scans each MCP service's cgroup for unexpected executables (non-Nix-store
    # binaries).  Alerts written to /var/log/ai-mcp-process-watch/alerts/ as
    # JSONL and also forwarded to the system journal via logger(1).
    (lib.mkIf active {
      systemd.services.ai-mcp-process-watch = {
        description = "AI stack MCP process tree watchdog";
        after = ["local-fs.target"];
        serviceConfig =
          (mkHardenedService {
            tier = cfg.hardwareTier;
            memoryMax = "32M";
            tasksMax = 16;
          })
          // {
            Type = "oneshot";
            User = svcUser;
            Group = svcGroup;
            ProtectHome = "read-only";
            LogsDirectory = "ai-mcp-process-watch";
            # Needs to read /proc and /sys/fs/cgroup; cannot use ProtectSystem=strict with these.
            ProtectSystem = "full";
            ReadOnlyPaths = ["/proc" "/sys/fs/cgroup"];
            ExecStart = "${pkgs.bash}/bin/bash ${repoSource}/scripts/testing/check-mcp-processes.sh";
            SuccessExitStatus = [0];
            Environment = [
              "MCP_SERVICES=\"ai-aidb.service ai-hybrid-coordinator.service ai-ralph-wiggum.service ai-embeddings.service ai-audit-sidecar.service\""
              "ALERT_DIR=/var/log/ai-mcp-process-watch/alerts"
              "ALLOWLIST_FILE=/etc/ai-mcp-process-allowlist"
            ];
          };
      };

      systemd.timers.ai-mcp-process-watch = {
        description = "Periodic MCP process tree watchdog";
        wantedBy = ["timers.target"];
        timerConfig =
          {
            OnCalendar = "*:0/15"; # every 15 minutes
            RandomizedDelaySec = "60s";
            Persistent = true;
            Unit = "ai-mcp-process-watch.service";
          }
          // lib.optionalAttrs (lib.versionAtLeast lib.version "25.11") {
            DeferReactivation = true;
          };
      };
    })

    # ── Phase 12.1.2 + 12.1.3 — AppArmor profiles for MCP servers ────────────
    # Declarative profile generation from Nix expressions (Phase 12.1.3):
    #   - Port numbers, data directories, and secret paths are interpolated from
    #     the module options so profiles stay consistent with actual deployment.
    #   - One abstract base profile + per-service inheriting profiles.
    # Confinement goals:
    #   - Restrict filesystem writes to service-specific data directories only
    #   - Allow /nix/store/** read for Python interpreter + package closures
    #   - Deny shell interpreter execution (/bin/sh, /bin/bash etc.)
    #   - Allow loopback TCP only; deny raw/packet sockets
    (lib.mkIf active {
      security.apparmor.policies."ai-mcp-base" = {
        state = "enforce";
        profile = ''
          #include <tunables/global>
          # Phase 12.1.2 — Abstract base profile for AI stack Python MCP servers.
          # Per-service profiles inherit this via the "profile" keyword.
          # Python binaries in /nix/store/<hash>-python3-<ver>-env/bin/python3
          # use a store-hash path so we allow the whole /nix/store/** subtree.
          profile ai-mcp-base flags=(attach_disconnected) {
            #include <abstractions/base>

            # Nix store: Python interpreter, packages, shared libraries
            /nix/store/** r,
            /nix/store/**/*.so* mr,
            /nix/store/**/bin/python3* ix,

            # Repo path (source code, scripts) — read-only
            ${repoSource}/** r,

            # Service data directory (read-write)
            ${dataDir}/** rw,

            # Secrets (read-only)
            /run/secrets/ r,
            /run/secrets/** r,

            # Standard system paths
            /proc/sys/kernel/osrelease r,
            /proc/meminfo r,
            /dev/null rw,
            /dev/urandom r,
            /dev/random r,
            /tmp/** rw,
            /run/user/** rw,

            # Unix sockets (audit sidecar, Redis)
            /run/ai-audit-sidecar.sock rw,

            # Loopback TCP/IP only; deny raw and packet sockets
            network inet stream,
            network inet6 stream,
            network unix stream,
            deny network raw,
            deny network packet,

            # Deny shell execution — MCP servers must not spawn /bin/sh etc.
            deny /bin/sh x,
            deny /bin/bash x,
            deny /usr/bin/sh x,
            deny /usr/bin/bash x,
            deny /run/current-system/sw/bin/bash x,
            deny /run/current-system/sw/bin/sh x,

            # Deny home and root directory access
            deny /home/** rwx,
            deny /root/** rwx,
          }
        '';
      };
    })

    # ── Phase 12.3.3 — Forward audit log to remote syslog when configured ────
    (lib.mkIf (active && cfg.logging.remoteSyslog.enable) {
      # rsyslogd imfile module tails the audit JSONL and feeds entries into the
      # existing omfwd forwarding pipeline configured by logging.nix.
      services.rsyslogd.extraConfig = lib.mkAfter ''
        # Phase 12.3.3 — AI tool audit log forwarding
        module(load="imfile")
        input(type="imfile"
              File="/var/log/ai-audit-sidecar/tool-audit.jsonl"
              Tag="ai-tool-audit"
              Severity="info"
              Facility="local0"
              reopenOnTruncate="on")
      '';
    })
  ];
}
