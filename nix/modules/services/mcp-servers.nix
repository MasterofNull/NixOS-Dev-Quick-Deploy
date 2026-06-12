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

  # Phase 36.4.1 — service-scoped identities
  aiGroup = "ai-stack";
  aidbUser = "ai-aidb";
  hybridUser = "ai-hybrid";
  ralphUser = "ai-ralph";
  aiderUser = "ai-aider";
  docsUser = "ai-docs";
  auditUser = "ai-audit";

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
    else
      builtins.path {
        path = mcp.repoPath;
        name = "nixos-quick-deploy-repo";
      };

  repoMcp = "${toString repoSource}/ai-stack/mcp-servers";
  repoAiStack = "${toString repoSource}/ai-stack";
  # Keep active OSINT service evaluation secure. Maigret/MOSAIC remain excluded
  # until local derivations no longer pull insecure PyPDF2.

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
  singleLineValue = value:
    lib.replaceStrings ["\r" "\n"] [" " " "] value;
  mcpIntegrityBaseline = "${mutableStateDir}/mcp-source-baseline.sha256";
  migrationsIni = "${toString repoSource}/ai-stack/migrations/alembic.ini";
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
        requests_per_minute: 300

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
  runtimeSchedulerPolicyJson =
    pkgs.writeText "runtime-scheduler-policy.json" (builtins.toJSON ai.aiHarness.runtime.schedulerPolicy);
  parityScorecardJson =
    pkgs.writeText "parity-scorecard.json" (builtins.toJSON ai.aiHarness.runtime.parityScorecard);
  runtimeToolSecurityPolicyJson =
    pkgs.writeText "runtime-tool-security-policy.json" (builtins.toJSON ai.aiHarness.runtime.toolSecurity.policy);
  auditSidecarScript =
    pkgs.writeText "audit_sidecar.py" (builtins.readFile ../../../ai-stack/mcp-servers/shared/audit_sidecar.py);

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
      # Phase A.2 fix: coordinator appends Phase 56 agent-events to sidecar audit log
      "/var/log/ai-audit-sidecar"
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
      cryptography # Phase D: Ed25519 A2A agent card signing (AM-G2)
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
      Group = aiGroup;
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
  aiderWrapperApiKeySecret = sec.names.aiderWrapperApiKey;

  embedEnabled = ai.embeddingServer.enable;
  redisUnit = "redis-mcp.service";
  mutableBootstrapUnit = "ai-mutable-path-bootstrap.service";
  authSelfTestUnit = "ai-auth-selftest.service";
  otlpCollectorUnit = "ai-otel-collector.service";
  otlpEndpoint = "http://127.0.0.1:${toString ports.otlpGrpc}";
  # Phase 21.1 — OTEL collector config with Tempo exporter for trace persistence.
  # Traces are forwrded to Grafana Tempo for storage and querying.
  otelCollectorConfig = pkgs.writeText "ai-otel-collector.yaml" ''
    extensions:
      health_check:
        endpoint: 127.0.0.1:${toString ports.otelCollectorHealth}

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
      extensions: [health_check]
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
        # ... (removed for brevity in instruction, but I'll provide full block)
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
    })

    (lib.mkIf cfg.roles.aiStack.enable {
      # ── Phase 36.4.1 — Service-scoped identities ────────────────────────────
      # These must exist whenever the AI stack is enabled, regardless of backend,
      # to ensure secret ownership and directory permissions are consistent.
      users.groups.${aiGroup} = {};
      users.users = {
        ${aidbUser} = {
          isSystemUser = true;
          group = aiGroup;
          description = "AIDB MCP service user";
          home = "${dataDir}/aidb";
        };
        ${hybridUser} = {
          isSystemUser = true;
          group = aiGroup;
          description = "Hybrid Coordinator service user";
          home = "${dataDir}/hybrid";
        };
        ${ralphUser} = {
          isSystemUser = true;
          group = aiGroup;
          description = "Ralph Wiggum service user";
          home = "${dataDir}/ralph";
        };
        ${aiderUser} = {
          isSystemUser = true;
          group = aiGroup;
          description = "Aider Wrapper service user";
          home = "${dataDir}/aider-wrapper";
        };
        ${docsUser} = {
          isSystemUser = true;
          group = aiGroup;
          description = "NixOS Docs service user";
          home = "${dataDir}/nixos-docs";
        };
        ${auditUser} = {
          isSystemUser = true;
          group = aiGroup;
          description = "AI audit service user";
        };
        # Add primary user to the group for manual intervention/auditing
        ${svcUser}.extraGroups = [aiGroup];
      };

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
            ${pkgs.coreutils}/bin/install -d -m 0750 -o ${lib.escapeShellArg svcUser} -g ${lib.escapeShellArg aiGroup} "$path"
          }
          ${lib.concatMapStringsSep "\n" (path: "create_path ${lib.escapeShellArg path}") (lib.unique (runtimeWorkspaceRoots ++ mutableProgramPaths ++ cfg.deployment.mutableSpaces.userWritablePaths))}
        '';
      };

      # ── State directories ───────────────────────────────────────────────────
      systemd.tmpfiles.rules =
        [
          "d ${dataDir}                    0750 root ${aiGroup} -"
          "d ${dataDir}/aidb               0750 ${aidbUser} ${aiGroup} -"
          "d ${dataDir}/aidb/mcp-cache     0750 ${aidbUser} ${aiGroup} -"
          "d ${dataDir}/aidb/logs          0750 ${aidbUser} ${aiGroup} -"
          "d ${dataDir}/aidb/telemetry     0750 ${aidbUser} ${aiGroup} -"
          "f ${dataDir}/aidb/telemetry/aidb-events.jsonl 0640 ${aidbUser} ${aiGroup} - -"
          "d ${dataDir}/aidb/shared-skills 0750 ${aidbUser} ${aiGroup} -"
          "Z ${dataDir}/aidb/shared-skills 0750 ${aidbUser} ${aiGroup} -"
          "d ${dataDir}/hybrid             0750 ${hybridUser} ${aiGroup} -"
          # Phase 117.1 — 0770 lets hyperd (in ai-stack group) write mirror artifacts
          # (attention-snapshot.json, agent-resume.json) from aq-session-start and
          # attention_queue.py so ai-system-state can read them as ai-hybrid.
          "d ${dataDir}/hybrid/telemetry   0770 ${hybridUser} ${aiGroup} -"
          "z ${dataDir}/hybrid/telemetry   0770 ${hybridUser} ${aiGroup} -"
          "d ${dataDir}/hybrid/fine-tuning 0750 ${hybridUser} ${aiGroup} -"
          # Phase 106.1 — checkpoints dir was hyperd:users (created by init mkdir); coordinator (ai-hybrid) needs rw.
          # Z recursively relabels existing dir/files to ai-hybrid:ai-stack ownership.
          "d ${dataDir}/hybrid/checkpoints 0750 ${hybridUser} ${aiGroup} -"
          "Z ${dataDir}/hybrid/checkpoints 0750 ${hybridUser} ${aiGroup} -"
          "z ${dataDir}/hybrid/fine-tuning 0750 ${hybridUser} ${aiGroup} -"
          "f ${dataDir}/hybrid/telemetry/hybrid-events.jsonl 0640 ${hybridUser} ${aiGroup} - -"
          "z ${dataDir}/hybrid/telemetry/hybrid-events.jsonl 0640 ${hybridUser} ${aiGroup} - -"
          "f ${dataDir}/hybrid/telemetry/continuous_learning_stats.json 0640 ${hybridUser} ${aiGroup} - -"
          # Phase 95.1 — delegation-feedback.jsonl was root:root; coordinator (ai-hybrid) needs rw.
          # f creates if absent; z relabels if already present (root:root from prior session).
          "f ${dataDir}/hybrid/telemetry/delegation-feedback.jsonl 0640 ${hybridUser} ${aiGroup} - -"
          "z ${dataDir}/hybrid/telemetry/delegation-feedback.jsonl 0640 ${hybridUser} ${aiGroup} - -"
          # Phase 120 — agent-run-events.jsonl written by both ai-hybrid (coordinator events)
          # and hyperd (race-harness). 0640→0664 so group (ai-stack, which includes hyperd) can append.
          "f ${dataDir}/hybrid/telemetry/agent-run-events.jsonl 0664 ${hybridUser} ${aiGroup} - -"
          "z ${dataDir}/hybrid/telemetry/agent-run-events.jsonl 0664 ${hybridUser} ${aiGroup} - -"
          "f ${dataDir}/hybrid/fine-tuning/dataset.jsonl 0660 ${hybridUser} ${aiGroup} - -"
          "f ${dataDir}/hybrid/fine-tuning/dataset_export.jsonl 0660 ${hybridUser} ${aiGroup} - -"
          "f ${dataDir}/hybrid/telemetry/aidb-reindex-latest.json 0660 ${svcUser} ${aiGroup} - -"
          "f ${dataDir}/hybrid/telemetry/latest-focused-ci.json 0660 ${svcUser} ${aiGroup} - -"
          "d ${dataDir}/ralph              0750 ${ralphUser} ${aiGroup} -"
          "d ${dataDir}/ralph/state        0750 ${ralphUser} ${aiGroup} -"
          "d ${dataDir}/ralph/telemetry    0750 ${ralphUser} ${aiGroup} -"
          "f ${dataDir}/ralph/telemetry/ralph-events.jsonl 0640 ${ralphUser} ${aiGroup} - -"
          "d ${dataDir}/security           0750 ${auditUser} ${aiGroup} -"
          "Z ${dataDir}/security           0750 ${auditUser} ${aiGroup} -"
          "d ${dataDir}/security/evidence  0770 ${auditUser} ${aiGroup} -"
          "d ${dataDir}/security/npm       0750 ${auditUser} ${aiGroup} -"
          "d ${dataDir}/qdrant-collections          0750 ${aidbUser} ${aiGroup} -"
          "d /var/log/ai-stack                      0750 root ${aiGroup} -"
          "f /var/log/ai-stack/tool-audit.jsonl     0660 ${svcUser} ${aiGroup} - -"
          "f /var/log/ai-stack/agent-commands.jsonl 0660 ${svcUser} ${aiGroup} - -"
          # base.nix creates mutableLogDir via its mutableUserServicePaths d-rule (0750 primaryUser users).
          # We must NOT add a second d-rule here (systemd-tmpfiles warns on duplicate paths).
          # Use z-only to override ownership/mode so service-owned child logs are not
          # unsafe transitions under a user-owned parent.
          "z ${mutableLogDir}                       0770 root ${aiGroup} -"
          "f ${mutableLogDir}/hint-audit.jsonl   0660 ${hybridUser} ${aiGroup} - -"
          "z ${mutableLogDir}/hint-audit.jsonl   0660 ${hybridUser} ${aiGroup} - -"
          "f ${mutableLogDir}/hint-feedback.jsonl 0660 ${svcUser} ${aiGroup} - -"
          "f ${mutableLogDir}/query-gaps.jsonl 0660 ${svcUser} ${aiGroup} - -"
          # Audit sidecar log dir — coordinator (ai-stack group) needs rw to append Phase 56 events.
          "d /var/log/ai-audit-sidecar              0750 ${auditUser} ${aiGroup} -"
          "f /var/log/ai-audit-sidecar/tool-audit.jsonl 0660 ${auditUser} ${aiGroup} - -"
          "z /var/log/ai-audit-sidecar/tool-audit.jsonl 0660 ${auditUser} ${aiGroup} - -"
          "d ${dataDir}/aider-wrapper               0750 ${aiderUser} ${aiGroup} -"
          "d ${dataDir}/aider-wrapper/workspace     0750 ${aiderUser} ${aiGroup} -"
          "d ${dataDir}/nixos-docs           0750 ${docsUser} ${aiGroup} -"
          "d ${dataDir}/nixos-docs/cache     0750 ${docsUser} ${aiGroup} -"
          "d ${dataDir}/nixos-docs/repos     0750 ${docsUser} ${aiGroup} -"
        ]
        # Collision guard: security/npm is already declared above with auditUser (line 655).
        # Only add a d-rule for npm-security paths that land OUTSIDE the pre-declared subtree.
        ++ map (path: "d ${path} 0750 ${svcUser} ${aiGroup} -") (
          lib.subtractLists
          ["${dataDir}/security/npm" "${dataDir}/security"]
          (lib.unique [
            (builtins.dirOf cfg.deployment.npmSecurity.quarantineStateFile)
            (builtins.dirOf cfg.deployment.npmSecurity.incidentLogFile)
          ])
        )
        ++ map (root: "d ${root} 0750 ${svcUser} ${aiGroup} -") runtimeWorkspaceRoots;
    })

    (lib.mkIf active {
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

      # base.nix generates a z-rule for mutableLogDir (= mutableUserServicePaths)
      # that resets owner/group to primaryUser:primaryGroup. Using lib.mkAfter ensures
      # this z-rule is appended AFTER base.nix's rule so service-owned child logs are
      # not unsafe transitions under a user-owned parent.
      systemd.tmpfiles.rules = lib.mkAfter [
        "z ${mutableLogDir} 0770 root ${aiGroup} -"
      ];
    })

    (lib.mkIf active {
      systemd.services.ai-otel-collector = {
        description = "AI stack OpenTelemetry collector";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        # Phase 21.1 — Wait for Tempo to be ready before forwrding traces.
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
            User = aidbUser;
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
                "AIDB_TOOL_SCHEMA_CACHE=${dataDir}/aidb/mcp-cache/tool_schemas.json"
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
                "AI_SEARCH_SCORE_THRESHOLD=${toString ai.aiHarness.retrieval.searchScoreThreshold}"
                # Rate limits tuned for batch ingestion pipelines.
                # Per-tool tiered limits (10/60/600 RPM by risk tier) remain unchanged — those protect
                # against high-risk tool abuse. These env vars raise the three limits that throttle
                # bulk document ingestion from localhost:
                #   - General RPM: raised from 60 → 300 in config above (requests_per_minute)
                #   - Ingest-specific RPM: 100 → 500 (separate ingest window in TieredRateLimiter)
                #   - Global hourly: 1000 → 10000 (shared bucket consumed by every API call)
                "AIDB_RATE_LIMIT_INGEST_RPM=500"
                "AIDB_RATE_LIMIT_GLOBAL_RPH=10000"
                # Bound fire-and-forget Qdrant vectorization so imports cannot starve foreground
                # vector search or overload the local embedding server.
                "AIDB_QDRANT_VECTORIZE_MAX_CONCURRENCY=2"
                "AIDB_QDRANT_VECTORIZE_MAX_QUEUE=16"
                "AIDB_QDRANT_VECTORIZE_TIMEOUT_S=45"
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
        path = [pkgs.nsjail]; # Phase 62.1: nsjail execution sandbox
        serviceConfig =
          commonServiceConfig
          // {
            User = hybridUser;
            # Phase 72.x — attach AppArmor profile (complain mode; enforce after May-30 soak)
            AppArmorProfile = "ai-hybrid-coordinator";
            ExecStart = lib.escapeShellArgs [
              "${hybridPython}/bin/python3"
              "${repoMcp}/hybrid-coordinator/server.py"
            ];
            Restart = "always";
            RestartSec = "5s";
            Environment =
              [
                "PORT=${toString mcp.hybridPort}"
                "AI_STRICT_ENV=true"
                "MCP_SERVER_MODE=http"
                "MCP_SERVER_PORT=${toString mcp.hybridPort}"
                "HOST=127.0.0.1"
                "AI_LOCAL_MODEL_ID=${llama.activeModel}"
                "AI_AGENT_NAME=local-${cfg.hardwareTier}-agent"
                "AI_SEMANTIC_TOOLING_AUTORUN=true"
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
                "LOCAL_MAX_INPUT_TOKENS=1800"
                "LOCAL_MAX_OUTPUT_TOKENS=800"
                "LOCAL_CONFIDENCE_THRESHOLD=0.35"
                "AI_REMOTE_BURST_QUALITY_THRESHOLD=${toString ai.switchboard.remoteBurst.qualityThreshold}"
                "AI_REMOTE_BURST_QUEUE_DEPTH_TRIGGER=${toString ai.switchboard.remoteBurst.queueDepthTrigger}"
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
                "THERMAL_CRITICAL_C=85"
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
                "AI_TREE_SEARCH_MAX_BRANCHES=${toString ai.aiHarness.retrieval.treeSearchMaxBranches}"
                "AI_TREE_SEARCH_TIMEOUT_S=${toString ai.aiHarness.retrieval.treeSearchTimeoutSeconds}"
                "AI_HARNESS_EVAL_ENABLED=${
                  if ai.aiHarness.eval.enable
                  then "true"
                  else "false"
                }"
                "AI_HARNESS_MIN_ACCEPTANCE_SCORE=${toString ai.aiHarness.eval.minAcceptanceScore}"
                "AI_HARNESS_MAX_LATENCY_MS=${toString ai.aiHarness.eval.maxLatencyMs}"
                "AI_HARNESS_EVAL_TIMEOUT_S=${toString ai.aiHarness.eval.timeoutSeconds}"
                "AI_HARNESS_EVAL_TIMEOUT_HARD_CAP_S=${toString ai.aiHarness.eval.timeoutHardCapSeconds}"
                "RAGAS_FAITHFULNESS_ENABLED=${
                  if ai.aiHarness.eval.faithfulnessEnabled
                  then "true"
                  else "false"
                }"
                "RAGAS_FAITHFULNESS_SAMPLE_RATE=${toString ai.aiHarness.eval.faithfulnessSampleRate}"
                # Keep tool-oriented retrieval probes aligned with harness phase
                # maintenance and dashboard operator workflows.
                "AI_CAPABILITY_DISCOVERY_ENABLED=true"
                "AI_CAPABILITY_DISCOVERY_ON_QUERY=true"
                # Speculative decoding state — reflects llama.cpp --spec-type draft-mtp launch flag.
                # Coordinator scorecard reads this to report speculative_decoding_enabled correctly.
                "AI_SPECULATIVE_DECODING_ENABLED=${
                  if llama.specType != ""
                  then "true"
                  else "false"
                }"
                "AI_SPECULATIVE_DECODING_MODE=${
                  if llama.specType != ""
                  then llama.specType
                  else "draft-model"
                }"
                "LLAMA_SPEC_DRAFT_N_MAX=${toString llama.specDraftNMax}"
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
                "AI_DELEGATE_TIMEOUT_S=${toString ai.aiHarness.runtime.delegateTimeoutSeconds}"
                "AI_DELEGATE_TIMEOUT_SLACK_S=${toString ai.aiHarness.runtime.delegateInnerSlackSeconds}"
                # Local slot retry: wait up to 4×15s=60s for llama.cpp to free when remote is also rate-limited.
                "AI_DELEGATE_LOCAL_SLOT_BUSY_MAX_RETRIES=4"
                "AI_DELEGATE_LOCAL_SLOT_BUSY_RETRY_DELAY_S=15.0"
                "AI_DELEGATE_LOCAL_SLOT_BUSY_RETRY_BUDGET_FLOOR_S=5.0"
                "AI_SEMANTIC_CACHE_WARM_ON_START=${
                  if ai.aiHarness.runtime.cachePrewarm.startupWarmEnable
                  then "true"
                  else "false"
                }"
                (lib.escapeShellArg "AI_SEMANTIC_CACHE_WARM_QUERIES=${lib.concatStringsSep "|" ai.aiHarness.runtime.cachePrewarm.startupQueries}")
                "RUNTIME_SAFETY_POLICY_FILE=${runtimeSafetyPolicyJson}"
                "RUNTIME_ISOLATION_PROFILES_FILE=${runtimeIsolationProfilesJson}"
                "AI_ROUTING_POLICY_FILE=${repoSource}/config/routing-policy.yaml"
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
                (lib.escapeShellArg "AI_WEB_RESEARCH_USER_AGENT=${ai.aiHarness.runtime.webResearch.userAgent}")
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
                (lib.escapeShellArg "AI_BROWSER_RESEARCH_USER_AGENT=${ai.aiHarness.runtime.browserResearch.userAgent}")
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
                (lib.escapeShellArg "AI_LOCAL_SYSTEM_PROMPT_IDENTITY=${singleLineValue ai.aiHarness.runtime.localSystemPrompt.identity}")
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
                "PYTHONPATH=${workflowHandlersPkg}/${pkgs.python3.sitePackages}:${repoMcp}:${repoMcp}/hybrid-coordinator:${repoAiStack}:${repoAiStack}/capability-gap:${repoAiStack}/efficiency:${repoAiStack}/offloading:${repoAiStack}/observability:${repoAiStack}/world-model:${repoAiStack}/progressive-disclosure:${repoAiStack}/affective-engine:${repoAiStack}/autoresearch:${repoAiStack}/identity-kernel:${repoAiStack}/local-agents:${repoAiStack}/model-optimization:${repoAiStack}/real-time-learning:${toString repoSource}/scripts/ai/lib"
                # Phase 101 — attention_queue writable path. repoSource is Nix store (read-only);
                # mcp.repoPath is the live checkout string, so writes succeed.
                "ATTENTION_QUEUE_DIR=${mcp.repoPath}/.agents/attention"
                # Phase 12.3.2 — audit sidecar socket path
                "AUDIT_SOCKET_PATH=/run/ai-audit-sidecar.sock"
                # Phase A.1 fix: point hints_engine at sidecar audit log (group-readable by ai-stack)
                "TOOL_AUDIT_LOG_PATH=/var/log/ai-audit-sidecar/tool-audit.jsonl"
                "AI_SEARCH_SCORE_THRESHOLD=${toString ai.aiHarness.retrieval.searchScoreThreshold}"
                # Phase 8.1 — hard cap on LLM generation within /query to bound route_search P95
                "AI_QUERY_LLM_TIMEOUT_S=${toString ai.aiHarness.runtime.queryLlmTimeoutSeconds}"
                # Model probe reads capabilities at startup and auto-computes budgets.
                # Env vars below are FALLBACK DEFAULTS only — the probe overrides them
                # when it successfully detects the loaded model. Set env vars to lock
                # a specific value regardless of what the probe measures.
                "AI_MODEL_PROFILE_PATH=${dataDir}/model-profile.json"
                # Fallback token budgets (probe will override these at runtime):
                "AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS=2000"
                "AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_LOOKUP=400"
                "AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_FORMAT=400"
                "AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_REASONING=1500"
                "AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_SYNTHESIZE=2000"
                "AI_ROUTE_LOCAL_RESPONSE_MAX_TOKENS_HEAVY=2700"
                "AI_ROUTE_REMOTE_RESPONSE_MAX_TOKENS=800"
                "AI_DISTILL_MIN_WORDS=50"
                "AI_DISTILL_PROJECT=session-knowledge"
                "AI_HEAVY_SYNTHESIS_TOKENS_THRESHOLD=800"
                # Phase 62.1: nsjail sandbox path (shell_tools.py reads NSJAIL_BIN)
                "NSJAIL_BIN=${pkgs.nsjail}/bin/nsjail"
              ]
              ++ lib.optional mcp.postgres.enable
              "DATABASE_URL=${pgUrl}"
              ++ lib.optional sec.enable "EMBEDDING_API_KEY_FILE=${secretPath embeddingsApiKeySecret}"
              ++ lib.optional sec.enable "HYBRID_API_KEY_FILE=${secretPath hybridApiKeySecret}"
              ++ lib.optional sec.enable "RALPH_WIGGUM_API_KEY_FILE=${secretPath aidbApiKeySecret}"
              ++ lib.optional sec.enable "POSTGRES_PASSWORD_FILE=${secretPath postgresPasswordSecret}";
            EnvironmentFile = "-${mutableOptimizerDir}/overrides.env";
            # Phase 163 — allow coordinator subprocesses (aq-qa) to write attention alerts.
            # commonServiceConfig sets ProtectHome=read-only; ATTENTION_QUEUE_DIR points to
            # live repo under /home/hyperd/. Without this override, attention_queue._ensure_dirs()
            # and file writes both fail with EPERM, causing aq-qa check 86.2 to abort the script
            # (set -euo pipefail) → empty stdout + exit 1 on every run_qa_check call.
            ReadWritePaths = serviceWritablePaths ++ [
              "${mcp.repoPath}/.agents/attention"
            ];
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
            User = ralphUser;
            ExecStart = lib.escapeShellArgs [
              "${ralphPython}/bin/python3"
              "${repoMcp}/ralph-wiggum/server.py"
            ];
            Environment =
              [
                "AI_STRICT_ENV=true"
                "PORT=${toString mcp.ralphPort}"
                "HOST=127.0.0.1"
                "AI_LOCAL_MODEL_ID=${llama.activeModel}"
                "AI_AGENT_NAME=local-${cfg.hardwareTier}-agent"
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
            User = aiderUser;
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
            User = docsUser;
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
              "${toString repoSource}/scripts/data/sync-knowledge-sources"
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
          User = auditUser;
          Group = aiGroup;
          WorkingDirectory = dataDir;
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${toString repoSource}/scripts/security/security-audit.sh"
            "--repo-root"
            "${toString repoSource}"
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
          git
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
          User = auditUser;
          Group = aiGroup;
          WorkingDirectory = dataDir;
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${toString repoSource}/scripts/security/npm-security-monitor.sh"
            "--repo-root"
            "${toString repoSource}"
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

      systemd.tmpfiles.rules = [
        # Parent dirs and shared telemetry files are declared in the main state
        # tmpfiles block above. Keep this block to extra post-deploy artifacts only
        # so activation does not emit duplicate or unsafe ownership transitions.
        "f ${dataDir}/hybrid/telemetry/latest-aq-report.json 0664 ${svcUser} ${aiGroup} - -"
        "z ${dataDir}/hybrid/telemetry/latest-aq-report.json 0664 ${svcUser} ${aiGroup} -"
        # Phase 115.2 — system-state artifact: written by ai-hybrid (hybridUser owns telemetry dir);
        # readable by ai-stack group (0640) so dashboard + coordinator MCP tool can read it.
        "f ${dataDir}/hybrid/telemetry/latest-system-state.json 0640 ${hybridUser} ${aiGroup} -"
        "z ${dataDir}/hybrid/telemetry/latest-system-state.json 0640 ${hybridUser} ${aiGroup} -"
        # Phase 117.2/117.3 — mirror files for ai-system-state fallback reads.
        # attention-snapshot: written by attention_queue.py (various callers); 0664 so both
        #   ai-hybrid and hyperd can write; ai-stack group can read.
        # agent-resume: written by aq-session-start (runs as hyperd); 0640 so ai-hybrid
        #   (in ai-stack group) can read it.
        "f ${dataDir}/hybrid/telemetry/attention-snapshot.json 0664 ${hybridUser} ${aiGroup} -"
        "f ${dataDir}/hybrid/telemetry/agent-resume.json 0640 ${svcUser} ${aiGroup} -"
      ];

      # ── Autonomous Remediation Loop ───────────────────────────────────────
      systemd.services.ai-health-spider = {
        description = "AI stack health spider telemetry and remediation engine";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = ["network-online.target" "ai-hybrid-coordinator.service"];
        wants = ["network-online.target"];
        path = with pkgs; [bash coreutils curl gnugrep python3];
        serviceConfig =
          commonServiceConfig
          // {
            Type = "simple";
            User = svcUser;
            # aq-health-spider is a Python script; explicit interpreter bypasses the
            # noexec bind-mount ProtectHome="read-only" places on /home.
            # Script from repoSource (Nix store copy) — world-readable, in ReadOnlyPaths.
            ExecStart = lib.escapeShellArgs [
              "${pkgs.python3}/bin/python3"
              "${toString repoSource}/scripts/ai/aq-health-spider"
              "--interval"
              "900"
            ];
            Restart = "always";
            RestartSec = "10s";
            Environment = [
              "REPO_ROOT=${mcp.repoPath}"
              # Phase 101 pattern: repoSource is Nix store (read-only); live path needed for writes.
              "ATTENTION_QUEUE_DIR=${mcp.repoPath}/.agents/attention"
            ];
          };
      };

      # Phase 85 — Drop Zone Daemon: watches .agents/drops/*.drop.yaml and dispatches
      # via dispatch_task() (Python import, no shell-out).  Provides AFK autonomous intake.
      systemd.services.ai-drop-daemon = {
        description = "AI Drop Zone Daemon — watches .agents/drops/ for task files";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = ["network-online.target" "ai-hybrid-coordinator.service"];
        wants = ["network-online.target"];
        path = with pkgs; [bash coreutils];
        serviceConfig =
          commonServiceConfig
          // {
            Type = "simple";
            User = svcUser;
            # WorkingDirectory override: drop-daemon watches live .agents/drops/ in the repo.
            WorkingDirectory = mcp.repoPath;
            # Script from repoSource (Nix store copy, world-readable, in ReadOnlyPaths).
            # Explicit interpreter bypasses noexec bind-mount from ProtectHome="read-only".
            ExecStart = lib.escapeShellArgs [
              "${hybridPython}/bin/python3"
              "${toString repoSource}/scripts/ai/aq-drop-daemon"
            ];
            Restart = "on-failure";
            RestartSec = "5s";
            # ReadWritePaths override: daemon moves/archives files in the live repo drops dir.
            ReadWritePaths = serviceWritablePaths ++ [mcp.repoPath];
            Environment = [
              "LLAMA_URL=http://127.0.0.1:${toString ports.llamaCpp}"
              "HYBRID_URL=http://127.0.0.1:${toString ports.mcpHybrid}"
              "RALPH_URL=http://127.0.0.1:${toString ports.mcpRalph}"
              "DROP_DAEMON_TIMEOUT=300"
              # Security: agent mode (run_shell_command) is blocked by default.
              # Set to "true" in deploy-options.local.nix only after deliberate review.
              "DROP_ALLOW_AGENT=false"
              "DROP_MAX_PER_CYCLE=3"
              "DROP_MAX_QUEUED=20"
              # REPO_ROOT required: script resolves paths from __file__ (Nix store, read-only)
              # Without this, .agents/drops/.lock → EROFS on every cycle.
              "REPO_ROOT=${mcp.repoPath}"
              # ATTENTION_QUEUE_DIR: attention_queue.py resolves from __file__ (Nix store)
              # without this env var → _ensure_dirs() mkdir on Nix store → EROFS.
              "ATTENTION_QUEUE_DIR=${mcp.repoPath}/.agents/attention"
            ];
          };
      };

      # ── Phase 87.3 — Daily training ingest timer ─────────────────────────────
      # Reads hybrid-events.jsonl, delegation-feedback.jsonl, and
      # optimization_proposals.jsonl (last 24h) and writes structured fine-tuning
      # samples to fine-tuning/dataset.jsonl so the local model can learn from
      # its own production traffic.  Requires nixos-rebuild to activate.
      systemd.services.ai-training-ingest = {
        description = "AI training data ingest — telemetry → fine-tuning dataset";
        restartIfChanged = false;
        path = with pkgs; [bash coreutils python3];
        serviceConfig =
          commonServiceConfig
          // {
            Type = "oneshot";
            User = svcUser;
            Restart = "no";
            ExecStart = lib.escapeShellArgs [
              "${pkgs.python3}/bin/python3"
              "${toString repoSource}/ai-stack/local-agents/training_ingest.py"
              "--hours"
              "24"
            ];
            Environment = [
              "TELEMETRY_DIR=/var/lib/ai-stack/hybrid/telemetry"
              "FINE_TUNING_DATASET=/var/lib/ai-stack/hybrid/fine-tuning/dataset.jsonl"
              # REPO_ROOT needed so _REPO_ROOT resolves to live checkout (not read-only Nix store)
              "REPO_ROOT=${mcp.repoPath}"
              # ATTENTION_QUEUE_DIR: attention_queue.py resolves from __file__ (Nix store)
              # without this, _push_review_alerts() → _ensure_dirs() → EROFS.
              "ATTENTION_QUEUE_DIR=${mcp.repoPath}/.agents/attention"
            ];
            # commonServiceConfig sets ProtectHome="read-only" which blocks writes to
            # /home/hyperd/... even when REPO_ROOT points there.  Add explicit ReadWritePaths
            # so training_ingest.py can write harness-prompt-extensions.json.
            ReadWritePaths = serviceWritablePaths ++ [
              "${mcp.repoPath}/config"
              "${mcp.repoPath}/.agents/attention"
              # Phase 157: candidate_lifecycle.save() creates .agents/improvement/candidates.lock
              # (fcntl LOCK_EX cross-process safety). AppArmor 'k' on this path is satisfied
              # by the existing NixOS-managed file-lock syscall allowance in hardenedBase.
              "${mcp.repoPath}/.agents/improvement"
            ];
          };
      };

      systemd.timers.ai-training-ingest = {
        description = "Daily AI training data ingest timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig = {
          OnCalendar = "*-*-* 03:00:00";
          Persistent = true;
          RandomizedDelaySec = "10min";
        };
      };

      systemd.services.ai-auto-remediate = {
        description = "AI stack autonomous remediation loop";
        restartIfChanged = false;
        path = with pkgs; [bash coreutils curl gnugrep python3];
        serviceConfig =
          commonServiceConfig
          // {
            Type = "oneshot";
            User = svcUser;
            Restart = "no";
            ExecStart = lib.escapeShellArgs [
              "${pkgs.bash}/bin/bash"
              "${toString repoSource}/scripts/automation/auto-remediate.sh"
            ];
            Environment = ["REPO_ROOT=${mcp.repoPath}"];
          };
      };

      systemd.services.ai-throttler = {
        description = "AI stack autonomous resource throttler";
        wantedBy = ["ai-stack.target"];
        partOf = ["ai-stack.target"];
        after = ["network-online.target" "ai-hybrid-coordinator.service" "llama-cpp.service"];
        wants = ["network-online.target"];
        path = with pkgs; [bash coreutils curl (python3.withPackages (ps: with ps; [httpx]))];
        serviceConfig =
          commonServiceConfig
          // {
            Type = "simple";
            User = svcUser;
            ExecStart = lib.escapeShellArgs [
              "${(pkgs.python3.withPackages (ps: with ps; [httpx]))}/bin/python3"
              "${toString repoSource}/scripts/ai/aq-throttler"
            ];
            Restart = "always";
            RestartSec = "10s";
          };
      };

      systemd.timers.ai-auto-remediate = {
        description = "AI stack autonomous remediation timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig = {
          OnBootSec = "5min";
          OnUnitActiveSec = "15min";
          Persistent = true;
        };
      };

      # --- AIDB periodic re-indexer ---
      systemd.services.ai-aidb-reindex = lib.mkIf cfg.deployment.aidbReindex.enable {
        description = "AIDB knowledge re-indexer (logic-patterns + project corpus)";
        restartIfChanged = false;
        path = with pkgs; [
          bash
          coreutils
          curl
          findutils
          gnugrep
          jq
          python3
        ];
        after = [
          "network-online.target"
          "systemd-tmpfiles-setup.service"
          "ai-aidb.service"
        ];
        wants = ["network-online.target" "ai-aidb.service"];
        serviceConfig = {
          Type = "oneshot";
          User = svcUser;
          Group = aiGroup;
          WorkingDirectory = dataDir;
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${toString repoSource}/scripts/automation/aidb-reindex.sh"
          ];
          ReadOnlyPaths = ["/"];
          ReadWritePaths = ["${dataDir}"];
          PrivateTmp = true;
          ProtectHome = "read-only";
          ProtectSystem = "strict";
          NoNewPrivileges = true;
          PrivateNetwork = false;
          SystemCallFilter = ["@system-service" "~@privileged"];
          MemoryMax = "1G";
          TimeoutStartSec = "10800"; # 3h: 7700+ chunks × 1.0s/chunk = ~128 min; 3h gives headroom for slow embed
          StandardOutput = "journal";
          StandardError = "journal";
        };
        environment = {
          REPO_ROOT = mcp.repoPath;
          AIDB_URL = "http://127.0.0.1:${toString mcp.aidbPort}";
          AIDB_API_KEY_FILE = "/run/secrets/aidb_api_key";
          INGEST_DELAY = cfg.deployment.aidbReindex.projectKnowledgeDelay;
          REINDEX_OUTPUT = "${dataDir}/hybrid/telemetry/aidb-reindex-latest.json";
        };
      };

      systemd.timers.ai-aidb-reindex = lib.mkIf cfg.deployment.aidbReindex.enable {
        description = "Periodic AIDB knowledge re-index timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig = {
          OnBootSec = cfg.deployment.aidbReindex.onBootDelaySec;
          OnUnitActiveSec = "${toString cfg.deployment.aidbReindex.intervalHours}h";
          # Spread concurrent timer firings across a 10-minute window so that
          # multiple system events (boot, rebuild, daily tick) don't all trigger
          # an embed-intensive reindex at the exact same moment.
          RandomizedDelaySec = "10min";
          Persistent = true;
          Unit = "ai-aidb-reindex.service";
        };
      };

      # Phase 56.2 — Automated session crystallization (nightly, Qwen distills async)
      systemd.services.ai-crystallize-sessions = {
        description = "Crystallize Continue sessions into AIDB episodic memory";
        restartIfChanged = false;
        path = with pkgs; [bash coreutils curl findutils python3];
        after = [
          "network-online.target"
          "ai-hybrid-coordinator.service"
        ];
        wants = ["network-online.target" "ai-hybrid-coordinator.service"];
        serviceConfig = {
          Type = "oneshot";
          User = "hyperd"; # needs ~/.continue/sessions access
          Group = aiGroup;
          WorkingDirectory = "/home/hyperd";
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${toString repoSource}/scripts/ai/aq-crystallize"
            "--session-dir"
            "/home/hyperd/.continue/sessions"
            "--since-hours"
            "25" # process sessions from last 25h (overlap buffer)
          ];
          PrivateTmp = true;
          PrivateNetwork = false;
          NoNewPrivileges = true;
          TimeoutStartSec = "3600";
          StandardOutput = "journal";
          StandardError = "journal";
        };
        environment = {
          HYBRID_COORDINATOR_URL = "http://127.0.0.1:${toString mcp.hybridPort}";
        };
      };

      systemd.timers.ai-crystallize-sessions = {
        description = "Nightly session crystallization timer (Phase 56.2)";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnCalendar = "*-*-* 02:00:00";
          Unit = "ai-crystallize-sessions.service";
        };
      };

      systemd.services.ai-post-deploy-converge = {
        description = "AI stack post-deploy declarative convergence";
        # Timer/manual-trigger driven only — never started by switch-to-configuration.
        # restartIfChanged = false prevents nixos-rebuild switch from blocking on this
        # oneshot service when the unit file changes (Persistent timer would fire it
        # immediately on reload, hanging the activation script indefinitely).
        restartIfChanged = false;
        path = with pkgs; [
          bash
          coreutils
          curl
          findutils
          gawk
          git
          gnugrep
          jq
          nodejs
          python3
          ripgrep
          util-linux
          iproute2
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
          Group = aiGroup;
          WorkingDirectory = dataDir;
          ExecStart = lib.escapeShellArgs [
            "${pkgs.bash}/bin/bash"
            "${toString repoSource}/scripts/automation/post-deploy-converge.sh"
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
      # The sidecar runs as auditUser and owns the log dir; the socket is 0660 so
      # only aiGroup members can send entries.
      systemd.sockets.ai-audit-sidecar = {
        description = "AI stack tool audit log Unix socket";
        wantedBy = ["sockets.target"];
        socketConfig = {
          ListenStream = "/run/ai-audit-sidecar.sock";
          SocketMode = "0660";
          SocketGroup = aiGroup;
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
            # Must run as auditUser (not DynamicUser) because the script lives under
            # /home/<primaryUser> which is mode 0700 — a DynamicUser ephemeral UID
            # cannot traverse it regardless of ProtectHome/ReadOnlyPaths overrides.
            User = auditUser;
            Group = aiGroup;
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
            ExecStart = "${pkgs.bash}/bin/bash ${toString repoSource}/scripts/testing/check-mcp-integrity.sh";
            SuccessExitStatus = [0];
            Environment = [
              "MCP_SERVER_DIR=${toString repoSource}/ai-stack/mcp-servers"
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
    # JSONL and also forwrded to the system journal via logger(1).
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
            ExecStart = "${pkgs.bash}/bin/bash ${toString repoSource}/scripts/testing/check-mcp-processes.sh";
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

      # ── Phase 115.2 — System Intelligence Hub refresh timer ──────────────────
      # Runs aq-system-state every 15 minutes as ai-hybrid (owner of telemetry dir)
      # to write /var/lib/ai-stack/hybrid/telemetry/latest-system-state.json.
      # Interactive terminal runs (as hyperd) skip artifact persistence gracefully.
      systemd.services.ai-system-state = {
        description = "AI System Intelligence Hub state snapshot";
        # path entries are available as bare commands to ExecStart scripts
        path = with pkgs; [bash coreutils git python3 jq curl systemd];
        serviceConfig =
          # Inherit all hardening directives from commonServiceConfig:
          #   ProtectHome="read-only"   — allows entering /home/hyperd/ (repo lives there)
          #   WorkingDirectory=dataDir  — ai-hybrid owns /var/lib/ai-stack
          #   ReadWritePaths            — includes the telemetry dir for artifact writes
          #   ReadOnlyPaths=[repoSource]— allows reading repo scripts in Nix store
          #   NoNewPrivileges, etc.     — full systemd hardening baseline
          commonServiceConfig
          // {
            Type = "oneshot";
            User = hybridUser;
            # Do not restart oneshot services; the timer handles re-invocation
            Restart = "no";
            # Two layered restrictions block scripts under /home for non-hyperd users:
            # 1) /home/hyperd/ is mode 700 — DAC blocks ai-hybrid from traversing it.
            # 2) ProtectHome="read-only" bind-mounts /home with noexec on newer systemd,
            #    blocking execve() on shebang scripts even if DAC were open.
            # Fix: use explicit Nix store interpreter (not subject to noexec) and point
            # at the Nix store copy (repoSource) which is in ReadOnlyPaths and is
            # world-readable. Python reads the script via file I/O — no execve().
            # The live repo is still accessible via REPO_ROOT env var at runtime.
            ExecStart = lib.escapeShellArgs [
              "${pkgs.python3}/bin/python3"
              "${toString repoSource}/scripts/ai/aq-system-state"
            ];
            TimeoutStartSec = "120s";
            Environment = [
              "SYSTEM_STATE_ARTIFACT_PATH=${dataDir}/hybrid/telemetry/latest-system-state.json"
              "QDRANT_URL=${qdrantUrl}"
              "REPO_ROOT=${mcp.repoPath}"
            ];
          };
      };

      systemd.timers.ai-system-state = {
        description = "System Intelligence Hub 15-minute refresh timer";
        wantedBy = ["timers.target"];
        partOf = ["ai-stack.target"];
        timerConfig = {
          OnBootSec = "3min";
          OnUnitActiveSec = "15min";
          RandomizedDelaySec = "30s";
          Persistent = true;
          Unit = "ai-system-state.service";
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

    # ── Phase 66.3 — AppArmor profiles: hybrid-coordinator + dashboard API ──────
    # Gemini VP Eng review: audit (complain) mode first; switch to enforce after
    # one week of clean audit logs (journalctl -b --grep apparmor).
    # Both profiles drafted in .agent/collaboration/GEMINI-PHASE-65-REVIEW.md.
    (lib.mkIf active {
      security.apparmor.policies."ai-hybrid-coordinator" = {
        state = "enforce"; # Phase 66.3: soak complete — enforced 2026-05-30
        profile = ''
          #include <tunables/global>
          # Phase 66.3 — ai-hybrid-coordinator: hybrid MCP + HTTP coordinator
          # Profile paths are derived directly from the NixOS service unit
          # declarations (ReadWritePaths, ReadOnlyPaths, PrivateTmp).
          # Confinement: declared paths only, loopback network, no raw sockets.
          profile ai-hybrid-coordinator flags=(attach_disconnected) {
            #include <abstractions/base>
            #include <abstractions/nameservice>
            #include <abstractions/python>

            # Nix store — read-only execution (covers Python stdlib, certifi SSL, libs)
            /nix/store/** r,
            /nix/store/**/*.so* mr,
            /nix/store/**/bin/python3* ix,
            # Phase 84 (rev2): shell subprocess execution for qa_check + continuous-learning daemon.
            # NoNewPrivileges=true blocks Ux/Px profile transitions (EPERM). Must use ix (inherit).
            # Children inherit this profile — add explicit rules for what aq-qa spawns.
            /nix/store/**/bin/bash   ix,
            /nix/store/**/bin/dash   ix,
            /nix/store/**/bin/sh     ix,
            /run/current-system/sw/bin/bash ix,
            /run/current-system/sw/bin/sh   ix,
            # systemctl is-active — reads unit state via D-Bus / /run/systemd/
            /nix/store/**/bin/systemctl ix,
            /run/current-system/sw/bin/systemctl ix,
            /run/systemd/           r,
            /run/systemd/**         r,
            /run/dbus/system_bus_socket rw,
            # curl — loopback HTTP health probes (network already inet stream)
            /nix/store/**/bin/curl  ix,
            /run/current-system/sw/bin/curl ix,
            /etc/ssl/**             r,
            /etc/resolv.conf        r,
            # jq, coreutils (used in _aq-qa-bash output formatting)
            # coreutils multi-call binary (pkgs.coreutils-full provides /bin/coreutils
            # as the dispatcher; individual tool symlinks also covered by per-name rules)
            /nix/store/**/bin/coreutils ix,
            /nix/store/**/bin/jq    ix,
            /nix/store/**/bin/cat   ix,
            /nix/store/**/bin/grep  ix,
            /nix/store/**/bin/sed   ix,
            /nix/store/**/bin/awk   ix,
            /nix/store/**/bin/date  ix,
            /nix/store/**/bin/printf ix,
            /nix/store/**/bin/wc    ix,
            /nix/store/**/bin/sort  ix,
            /nix/store/**/bin/head  ix,
            /nix/store/**/bin/tail  ix,
            /nix/store/**/bin/ls    ix,
            /nix/store/**/bin/mkdir ix,
            /nix/store/**/bin/cp    ix,
            /nix/store/**/bin/mv    ix,
            /nix/store/**/bin/rm    ix,
            /nix/store/**/bin/tr    ix,
            /nix/store/**/bin/cut   ix,
            /nix/store/**/bin/echo  ix,
            # Phase 163 — aq-qa phase 0 probes executed through /qa/check.
            # These must inherit the coordinator profile because NoNewPrivileges=true
            # prevents profile transitions. Without the explicit exec rules, denied
            # subprocesses can abort _aq-qa-bash before it emits machine JSON.
            /nix/store/**/bin/ss        ix,
            /nix/store/**/bin/psql      ix,
            /nix/store/**/bin/redis-cli ix,
            /nix/store/**/bin/getent    ix,
            ${mcp.repoPath}/scripts/ai/aqd ix,
            ${mcp.repoPath}/scripts/ai/aq-alerts ix,
            /run/current-system/sw/bin/jq  ix,
            /run/current-system/sw/** r,
            /run/current-system/sw/**/*.so* mr,

            # === ReadOnlyPaths (from service unit) ===
            # Repo source tree — config files, scripts (NixOS: ReadOnlyPaths=)
            ${repoSource}/** r,
            ${mcp.repoPath}/** r,
            # Phase 163 — attention queue write access (ReadWritePaths override)
            ${mcp.repoPath}/.agents/attention/ rw,
            ${mcp.repoPath}/.agents/attention/** rwk,

            # === ReadWritePaths (from service unit) ===
            # rwk: read, write/create (O_CREAT+truncate), file lock (fcntl/flock)
            /var/lib/ai-stack/ rw,
            /var/lib/ai-stack/** rwk,
            /var/lib/nixos-ai-stack/ rw,
            /var/lib/nixos-ai-stack/** rwk,
            /var/log/ai-audit-sidecar/ rw,
            /var/log/ai-audit-sidecar/** rwk,
            /var/log/nixos-ai-stack/ rw,
            /var/log/nixos-ai-stack/** rwk,

            # === PrivateTmp=true — private tmpfs (from service unit) ===
            /tmp/ rw,
            /tmp/** rwk,
            /var/tmp/ rw,
            /var/tmp/** rwk,

            # === Secrets (agenix — real path after symlink resolution) ===
            /run/secrets/ r,
            /run/secrets/** r,
            /run/secrets.d/ r,
            /run/secrets.d/** r,

            # === System resources (Python async runtime + psutil) ===
            /proc/self/** r,
            /proc/ r,
            @{PROC}/@{pids}/cmdline r,
            @{PROC}/@{pids}/stat r,
            @{PROC}/@{pids}/statm r,
            @{PROC}/@{pids}/status r,
            @{PROC}/@{pids}/limits r,
            @{PROC}/@{pids}/fd/ r,
            @{PROC}/@{pids}/fd/** r,
            /proc/sys/kernel/osrelease r,
            /proc/meminfo r,
            /dev/null rw,
            /dev/urandom r,

            # Hardware temperature sensors — coordinator telemetry
            # /sys/class/hwmon/ entries are symlinks → real device paths hwmonN/
            /sys/class/hwmon/ r,
            /sys/class/hwmon/** r,
            /sys/devices/**/hwmon*/temp*_input r,
            /sys/devices/**/hwmon*/temp*_label r,
            /sys/devices/**/hwmon*/name r,

            # Unix socket (audit sidecar)
            /run/ai-audit-sidecar.sock rw,

            # Network — loopback only (ports: 8003, 8002, 8085, 6379, 5432, 6333)
            network inet stream,
            network inet dgram,
            network unix stream,
            deny network raw,
            deny network packet,

            # Deny privileged capabilities
            deny capability sys_admin,
            deny capability sys_ptrace,
            deny capability net_admin,
            deny capability net_raw,

            # Deny writes/exec to home/root; reads allowed for repo paths above.
            # auto-added by apparmor-fix-agent 2026-05-31
            /proc/@{pids}/cgroup r,  # /proc/<pid> → @{pids}
            /sys/fs/cgroup/** r,
            # auto-added by apparmor-fix-agent 2026-06-10
            /dev/tty rw,  # open
            deny /home/** wx,
            deny /root/** rwx,
          }
        '';
      };

      security.apparmor.policies."command-center-dashboard-api" = {
        state = "enforce"; # Phase 66.3: soak complete — enforced 2026-05-30
        profile = ''
          #include <tunables/global>
          # Phase 66.3 — command-center-dashboard-api: dashboard FastAPI backend
          # Reads Python directly from repo (hot-reload on file change, no rebuild).
          # Confinement: repo read, dashboard data rw, localhost :8889 only.
          profile command-center-dashboard-api flags=(attach_disconnected) {
            #include <abstractions/base>

            # Repo read (dashboard reads Python directly from repo)
            ${repoSource}/** r,

            # Nix store
            /nix/store/** r,
            /nix/store/**/*.so* mr,
            /nix/store/**/bin/python3* ix,
            # uvicorn exec chain: start script → uvicorn wrapper → .uvicorn-wrapped binary.
            # Both live in separate Nix store derivations; glob covers any hash.
            /nix/store/**/bin/uvicorn ix,
            /nix/store/**/bin/.uvicorn-wrapped ix,
            /run/current-system/sw/** r,

            # tty — uvicorn probes for interactive terminal on startup (needs rw)
            /dev/tty rw,

            # Dashboard data (telemetry snapshots — read only from data dir)
            ${dataDir}/** r,
            # rwk: SQLite requires file_lock (k) in addition to rw; without k the
            # context-store candidate fails and startup falls back to repo path.
            /var/lib/nixos-system-dashboard/** rwk,
            # /tmp SQLite databases: context.db fallback, workflow-store.db, and any
            # other SQLite temp files. w covers file creation; k required for file lock.
            /tmp/ r,
            /tmp/*.db rwk,
            /tmp/*.db-* rwk,

            # System resources (Python async runtime + psutil)
            /proc/ r,
            /proc/self/** r,
            /proc/stat r,
            /proc/uptime r,
            /proc/sys/kernel/osrelease r,
            /proc/meminfo r,
            # psutil reads network stats via /proc/<pid>/net/dev (real pid path,
            # not /proc/self symlink — AppArmor resolves symlinks before matching).
            /proc/@{pids}/net/dev r,
            /proc/@{pids}/net/** r,
            # psutil.net_connections() walks /proc/<pid>/fd/ for ALL pids to count
            # open sockets — requires read access to other processes' fd directories.
            /proc/@{pids}/fd/ r,
            /dev/null rw,
            /dev/urandom r,

            # Hardware monitoring — GPU (DRM/AMDGPU), hwmon, thermal, platform devices.
            # psutil and custom GPU stat readers walk these sysfs trees.
            /sys/class/drm/ r,
            /sys/class/drm/** r,
            /sys/class/hwmon/ r,
            /sys/class/hwmon/** r,
            /sys/class/thermal/ r,
            /sys/class/thermal/** r,
            # Full sysfs device tree: covers ACPI (LNXSYSTM), PCI, NVMe, virtual/thermal.
            # psutil walks /sys/devices/** for hwmon, thermal, battery, and GPU stats.
            /sys/devices/** r,
            # lspci resolves GPU names through PCI bus symlinks before reading
            # device details under /sys/devices/**.
            /sys/bus/pci/devices/ r,
            /sys/bus/pci/devices/** r,

            # ip — psutil/netifaces execs ip for network interface enumeration.
            # nft — dashboard reads firewall rules_count via nft list ruleset.
            # Use **/bin/<cmd> (not pkg*/bin/) because store path starts with hash.
            /nix/store/**/bin/ip ix,
            /nix/store/**/bin/nft ix,

            # Secrets — NixOS mounts secrets at /run/secrets/ AND /run/secrets.d/<N>/
            /run/secrets/ r,
            /run/secrets/** r,
            /run/secrets.d/ r,
            /run/secrets.d/** r,

            # DNS resolution config read by Python's socket/urllib on first connect
            /run/systemd/resolve/stub-resolv.conf r,

            # AI stack logs — dashboard reads tool-audit and hint-audit for analytics
            /var/log/nixos-ai-stack/ r,
            /var/log/nixos-ai-stack/** r,
            /var/log/ai-audit-sidecar/ r,
            /var/log/ai-audit-sidecar/** r,

            # systemctl — dashboard service health panel calls systemctl is-active,
            # status, and show to display live service state. Also allows the
            # transitive nft/systemd-libs it loads via D-Bus activation.
            /nix/store/**/bin/systemctl ix,
            /run/current-system/sw/bin/systemctl ix,
            /run/systemd/private/** r,
            /run/systemd/units/** r,
            /run/dbus/system_bus_socket rw,
            network unix dgram,
            /sys/fs/cgroup/** r,
            /proc/@{pids}/cgroup r,

            # Network — localhost only (:8889) + outbound to coordinator loopback
            network inet stream,
            network unix stream,
            deny network raw,
            deny network packet,

            # Deny privileged capabilities
            deny capability sys_admin,
            deny capability net_admin,

            # Allow runtime repo reads (repoPath is under /home on dev machines).
            ${mcp.repoPath}/** r,

            # ptrace read — psutil reads /proc/<pid>/ for CPU/mem/net metrics
            # capability sys_ptrace needed for net_connections() reading other pids' /proc/<pid>/fd/
            capability sys_ptrace,
            ptrace read peer=unconfined,

            # Deny writes/exec to home/root; reads allowed for repo above.
            # auto-added by apparmor-fix-agent 2026-05-30
            /proc/@{pids}/comm r,  # /proc/<pid> → @{pids}
            # ss -tlnp runs inside the inherited coordinator profile during
            # /qa/check and reads per-process net tables to enumerate listeners.
            /proc/@{pids}/net/tcp r,
            /proc/@{pids}/net/tcp6 r,
            /proc/@{pids}/net/udp r,
            /proc/@{pids}/net/udp6 r,
            /proc/@{pids}/net/unix r,
            /sys/kernel/mm/transparent_hugepage/enabled r,
            /run/log/journal/ r,  # open
            /var/log/journal/ r,  # open
            /proc/sys/kernel/random/boot_id r,  # open
            # auto-added by apparmor-fix-agent 2026-05-30
            /var/lib/llama-cpp/models/ r,  # open
            # auto-added by apparmor-fix-agent 2026-05-30
            /etc/machine-id r,  # open
            # journal — wildcard covers all machine-id subdirs, rotated archives, and .journal~ tmps.
            # Replaces 20+ per-file rules accumulated by apparmor-fix-agent (Phase 94.2).
            /var/log/journal/** r,
            /run/log/journal/** r,
            # sudo — AppArmor resolves symlinks, so /run/wrappers/bin/sudo (symlink)
            # resolves to /run/wrappers/wrappers.<hash>/sudo before the rule is checked.
            # Wildcard glob covers both the symlink and any hash after rebuild.
            /run/wrappers/bin/sudo ix,
            /run/wrappers/wrappers.*/sudo ix,
            /nix/var/nix/profiles/ r,
            /nix/var/nix/profiles/** r,
            # CLI tools invoked by health probes and aq-qa
            /nix/store/**/bin/aq-qa ix,
            /nix/store/**/bin/lspci ix,
            /nix/store/**/bin/grep ix,
            # journalctl — dashboard reads journal logs via subprocess exec
            /nix/store/**/bin/journalctl ix,
            # Dashboard keyword signals
            /home/hyperd/.local/share/nixos-system-dashboard/** r,
            # auto-added by apparmor-fix-agent 2026-06-07
            /proc/@{pids}/stat r,  # /proc/<pid> → @{pids}
            deny /home/** wx,
            deny /root/** rwx,
          }
        '';
      };
    })

    # ── Phase 12.3.3 — Forwrd audit log to remote syslog when configured ────
    (lib.mkIf (active && cfg.logging.remoteSyslog.enable) {
      # rsyslogd imfile module tails the audit JSONL and feeds entries into the
      # existing omfwd forwrding pipeline configured by logging.nix.
      services.rsyslogd.extraConfig = lib.mkAfter ''
        # Phase 12.3.3 — AI tool audit log forwrding
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
