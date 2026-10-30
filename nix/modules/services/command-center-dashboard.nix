{
  lib,
  config,
  pkgs,
  ...
}: let
  cfg = config.mySystem;
  ports = cfg.ports;
  mon = cfg.monitoring;
  cc = mon.commandCenter;
  mcp = cfg.mcpServers;
  sec = cfg.secrets;
  svcUser = cfg.primaryUser;
  svcGroup = lib.attrByPath ["users" "users" svcUser "group"] "users" config;
  secretPath = name: config.sops.secrets.${name}.path;
  hybridApiKeySecret = sec.names.hybridApiKey;
  mutableOptimizerDir = cfg.deployment.mutableSpaces.aiStackOptimizerDir;
  mutableLogDir = cfg.deployment.mutableSpaces.aiStackLogDir;

  dashboardRoot = "${mcp.repoPath}";
  dashboardBackendRoot = "${dashboardRoot}/dashboard/backend";
  dashboardPublicDir = "${dashboardRoot}/dashboard/public";
  credentialStatusPublisher = pkgs.writeText "aqos-publish-credential-status.py"
    (builtins.readFile ../../../scripts/security/publish-credential-status.py);
  credentialCatalog = pkgs.writeText "aqos-security-credential-catalog-v1.json"
    (builtins.readFile ../../../config/security-credential-catalog-v1.json);
  credentialStatusDir = "/run/aqos-security";
  declaredCredentialArgs = lib.concatMap
    (name: ["--declared-name" name])
    (builtins.attrNames config.sops.secrets);

  # Root-run helper for the only privileged model-hot-swap write. Sudoers
  # cannot constrain `ln -sf` arguments safely (a `*` matches `-t /etc ...`),
  # so the sole NOPASSWD target is this fixed wrapper that validates its input.
  llamaSetActiveModel = pkgs.writeShellApplication {
    name = "aq-llama-set-active-model";
    runtimeInputs = [pkgs.coreutils];
    text = ''
      models_dir=/var/lib/llama-cpp/models
      name="''${1:-}"
      if [ "$#" -ne 1 ] || ! [[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$ ]] \
        || [ "$name" = "active.gguf" ] || [ ! -f "$models_dir/$name" ] \
        || [ -L "$models_dir/$name" ]; then
        echo "usage: aq-llama-set-active-model <model>.gguf (regular file in $models_dir)" >&2
        exit 2
      fi
      ln -sfn "$models_dir/$name" "$models_dir/active.gguf"
    '';
  };

  # Units the dashboard may start/stop/restart: what service_manager.py
  # discovers (`systemctl show ai-stack.target` Wants = target `wants` plus
  # services that are wantedBy/requiredBy it) plus the dashboard itself.
  # Rules are generated for units whose serviceConfig.User is a non-root user,
  # so a restart never runs agent-editable checkout code as root. Root units
  # (ai-pgvector-bootstrap, ai-mutable-path-bootstrap: oneshots) are excluded;
  # qdrant is the one allowed root unit (store binary + store config only).
  rootAllowedUnits = ["qdrant.service"];
  aiStackTarget = "ai-stack.target";
  aiStackUnits = lib.unique (
    (lib.filter (u: lib.hasSuffix ".service" u) (config.systemd.targets.ai-stack.wants or []))
    ++ (lib.mapAttrsToList (n: _: "${n}.service")
      (lib.filterAttrs (_: u: lib.any (t: lib.elem t (u.wantedBy ++ u.requiredBy)) [aiStackTarget])
        config.systemd.services))
  );
  unitRunsAsRoot = unit: let
    name = lib.removeSuffix ".service" unit;
    user = config.systemd.services.${name}.serviceConfig.User or "root";
  in
    user == "root";
  dashboardManagedUnits =
    lib.filter (u: !(unitRunsAsRoot u) || lib.elem u rootAllowedUnits) aiStackUnits
    ++ ["command-center-dashboard-api.service"];

  # cscli decision removal takes a caller-chosen ID; sudoers cannot constrain
  # the argument safely, so the sole NOPASSWD target is this validating wrapper.
  crowdsecDecisionDelete = pkgs.writeShellApplication {
    name = "aq-crowdsec-decision-delete";
    runtimeInputs = [pkgs.crowdsec];
    text = ''
      id="''${1:-}"
      if [ "$#" -ne 1 ] || ! [[ "$id" =~ ^[0-9]+$ ]]; then
        echo "usage: aq-crowdsec-decision-delete <numeric-decision-id>" >&2
        exit 2
      fi
      exec cscli decisions delete --id "$id"
    '';
  };

  # nft takes `-f <file>`, `-i`, `include`, etc.; sudoers cannot constrain those,
  # so the sole NOPASSWD target is this wrapper. It accepts only the exact nft
  # forms firewall.py issues (list ruleset / list chain, optional -a; delete
  # rule ... handle N; add rule ... accept comment X) and execs the store nft.
  nftDashboard = pkgs.writeShellApplication {
    name = "aq-nft-dashboard";
    text = ''
      nft_bin=${pkgs.nftables}/bin/nft
      fam_re='^(inet|ip|ip6)$'
      name_re='^[A-Za-z_][A-Za-z0-9_-]{0,31}$'
      tok_re='^[A-Za-z0-9_./:,{} "-]+$'
      cmt_re='^"?[A-Za-z0-9_-]+"?$'
      num_re='^[0-9]+$'
      reject() {
        echo "aq-nft-dashboard: rejected arguments" >&2
        exit 2
      }
      flag=()
      if [ "''${1:-}" = "-a" ]; then
        flag=(-a)
        shift
      fi
      verb="''${1:-}"
      obj="''${2:-}"
      case "$verb $obj" in
        "list ruleset")
          [ "$#" -eq 2 ] || reject
          exec "$nft_bin" "''${flag[@]}" list ruleset
          ;;
        "list chain")
          [ "$#" -eq 5 ] || reject
          [[ "$3" =~ $fam_re && "$4" =~ $name_re && "$5" =~ $name_re ]] || reject
          exec "$nft_bin" "''${flag[@]}" list chain "$3" "$4" "$5"
          ;;
        "delete rule")
          [ "$#" -eq 7 ] && [ "''${#flag[@]}" -eq 0 ] && [ "$6" = handle ] || reject
          [[ "$3" =~ $fam_re && "$4" =~ $name_re && "$5" =~ $name_re && "$7" =~ $num_re ]] || reject
          exec "$nft_bin" delete rule "$3" "$4" "$5" handle "$7"
          ;;
        "add rule")
          [ "$#" -ge 8 ] && [ "''${#flag[@]}" -eq 0 ] || reject
          [[ "$3" =~ $fam_re && "$4" =~ $name_re && "$5" =~ $name_re ]] || reject
          rest=("''${@:6}")
          n=''${#rest[@]}
          [ "''${rest[n-3]}" = accept ] && [ "''${rest[n-2]}" = comment ] || reject
          [[ "''${rest[n-1]}" =~ $cmt_re ]] || reject
          for tok in "''${rest[@]:0:n-3}"; do
            [[ "$tok" =~ $tok_re && "$tok" != -* ]] || reject
          done
          exec "$nft_bin" add rule "$3" "$4" "$5" "''${rest[@]}"
          ;;
        *) reject ;;
      esac
    '';
  };

  dashboardPython = pkgs.python3.withPackages (ps:
    with ps; [
      fastapi
      uvicorn
      pydantic
      pydantic-settings
      jsonschema
      python-dotenv
      websockets
      psutil
      aiofiles
      aiohttp
      asyncpg
    ]);
  dashboardPathPackages = [
    pkgs.bash
    pkgs.coreutils
    pkgs.crowdsec
    pkgs.curl
    pkgs.findutils
    pkgs.gawk
    pkgs.gnugrep
    pkgs.iproute2
    pkgs.iptables
    pkgs.nftables
    pkgs.procps
    pkgs.sudo
    pkgs.systemd
  ];
in {
  config = lib.mkIf (mon.enable && cc.enable) {
    # s1c (END-TO-END-BARE-METAL-PLAN.md) deferred finding: on a freshly
    # disko-installed VM this service failed at systemd step 216/GROUP —
    # svcGroup above is read back through `config.users.users.${svcUser}.group`
    # (falling back to "users" only if that attrpath is entirely absent), so
    # whatever it resolves to is assumed, not guaranteed, to be a group NixOS
    # actually declares. Fix at the root: declare the resolved group name
    # ourselves so the service's Group= always names something real,
    # regardless of what set (or didn't set) users.users.${svcUser}.group.
    # mkDefault: a no-op wherever this group is already declared (every real
    # host — "users" is a stock NixOS group) — only fills a genuine gap.
    users.groups.${svcGroup} = lib.mkIf (svcGroup != "") (lib.mkDefault {});

    # ── Sudo rules for firewall management ──────────────────────────────────────
    # The dashboard provides operator controls for captive portal bypass and
    # CrowdSec bouncer management. These require elevated privileges but are
    # tightly scoped to specific commands.
    environment.systemPackages = [llamaSetActiveModel crowdsecDecisionDelete nftDashboard];

    security.sudo.extraRules = [
      {
        users = [svcUser];
        commands = [
          # nftables: list and modify firewall rules (captive portal bypass)
          # via the validating wrapper only (never bare nft: -f/-i/include)
          {
            command = "${nftDashboard}/bin/aq-nft-dashboard";
            options = ["NOPASSWD"];
          }
          # CrowdSec bouncer control (pause/resume for portal login)
          {
            command = "${pkgs.systemd}/bin/systemctl start crowdsec-firewall-bouncer";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl stop crowdsec-firewall-bouncer";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl restart crowdsec-firewall-bouncer";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl is-active crowdsec-firewall-bouncer";
            options = ["NOPASSWD"];
          }
          # NixOS firewall reset (restore declarative rules)
          {
            command = "${pkgs.systemd}/bin/systemctl restart firewall";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl is-active firewall";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl is-active nftables";
            options = ["NOPASSWD"];
          }
          # CrowdSec CLI for decision management (view/remove blocked IPs)
          {
            command = "${pkgs.crowdsec}/bin/cscli decisions list -o json";
            options = ["NOPASSWD"];
          }
          {
            command = "${crowdsecDecisionDelete}/bin/aq-crowdsec-decision-delete";
            options = ["NOPASSWD"];
          }
          # iptables fallback (read-only listing; fixed args — a trailing `*`
          # would also permit `-L x -A ...` rule changes)
          {
            command = "${pkgs.iptables}/bin/iptables -L -n -v";
            options = ["NOPASSWD"];
          }
          # llama-cpp model hot-swap (restart service to load new model)
          {
            command = "${pkgs.systemd}/bin/systemctl restart llama-cpp";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl is-active llama-cpp";
            options = ["NOPASSWD"];
          }
          # Dashboard service controls: exact per-unit commands matching
          # service_manager.py (`systemctl --no-block <verb> <unit>.service`).
        ]
        ++ lib.concatMap (unit:
          map (verb: {
            command = "${pkgs.systemd}/bin/systemctl --no-block ${verb} ${unit}";
            options = ["NOPASSWD"];
          }) ["start" "stop" "restart"])
        dashboardManagedUnits
        ++ [
          # Local improvement loop operator controls
          {
            command = "${pkgs.systemd}/bin/systemctl start ai-local-training-loop.service";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl stop ai-local-training-loop.service";
            options = ["NOPASSWD"];
          }
          {
            command = "${pkgs.systemd}/bin/systemctl restart ai-local-training-loop.service";
            options = ["NOPASSWD"];
          }
          # llama-cpp model symlink update (swap active model without rebuild)
          {
            command = "${llamaSetActiveModel}/bin/aq-llama-set-active-model";
            options = ["NOPASSWD"];
          }
        ];
      }
    ];

    systemd.tmpfiles.rules = [
      "d ${cc.dataDir} 0750 ${svcUser} ${svcGroup} -"
      "d ${cc.dataDir}/cache 0750 ${svcUser} ${svcGroup} -"
      "d ${cc.dataDir}/telemetry 0750 ${svcUser} ${svcGroup} -"
      "d ${cc.dataDir}/model-downloads 0750 ${svcUser} ${svcGroup} -"
      # Root publishes a strictly metadata-only credential snapshot below a
      # root-owned /run parent that the dashboard cannot rename or replace.
      "d ${credentialStatusDir} 0750 root ${svcGroup} -"
      # Repair existing llama.cpp directory modes so the dashboard can show
      # model inventory through the llama supplementary group without write
      # access to model files.
      "z /var/lib/llama-cpp 0750 llama llama -"
      "z /var/lib/llama-cpp/models 0750 llama llama -"
      # Dashboard needs the sudo timestamp hierarchy present, but sudo itself
      # expects /run/sudo/ts to remain root-owned.
      "d /run/sudo 0711 root root -"
      "d /run/sudo/ts 0700 root root -"
    ];

    # SC-1: a root one-shot observes only the existence/type of sops-nix
    # runtime files. It never reads their contents, and the dashboard only
    # reads its redacted snapshot. Mutations require the future broker slice.
    systemd.services.aqos-security-credential-status = {
      description = "AQ-OS Security Center credential status publisher";
      wantedBy = ["multi-user.target"];
      before = ["command-center-dashboard-api.service"];
      after = ["local-fs.target"];
      serviceConfig = {
        Type = "oneshot";
        User = "root";
        Group = "root";
        UMask = "0027";
        NoNewPrivileges = true;
        CapabilityBoundingSet = ["CAP_CHOWN"];
        AmbientCapabilities = [];
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
        ReadOnlyPaths = ["/run/secrets"];
        ReadWritePaths = [credentialStatusDir];
        ExecStart = lib.escapeShellArgs (
          [
            "${pkgs.python3}/bin/python3"
            "-I"
            "${credentialStatusPublisher}"
            "--catalog" "${credentialCatalog}"
            "--runtime-dir" "/run/secrets"
            "--output" "${credentialStatusDir}/credential-status.json"
            "--group" svcGroup
          ]
          ++ declaredCredentialArgs
        );
      } // lib.optionalAttrs config.security.apparmor.enable {
        AppArmorProfile = "aqos-security-credential-status";
      };
    };
    systemd.timers.aqos-security-credential-status = {
      wantedBy = ["timers.target"];
      timerConfig = { OnBootSec = "2min"; OnUnitActiveSec = "5min"; Unit = "aqos-security-credential-status.service"; };
    };

    security.apparmor.policies."aqos-security-credential-status" = lib.mkIf config.security.apparmor.enable {
      state = "enforce";
      profile = ''
        #include <tunables/global>
        profile aqos-security-credential-status flags=(attach_disconnected) {
          #include <abstractions/base>
          ${pkgs.python3}/bin/python3 ix,
          ${credentialStatusPublisher} r,
          ${credentialCatalog} r,
          /nix/store/** r,
          /nix/store/**/*.so* mr,
          /run/secrets/ r,
          deny /run/secrets/** r,
          ${credentialStatusDir}/ rw,
          ${credentialStatusDir}/** rwk,
          /dev/urandom r,
          capability chown,
        }
      '';
    };

    # ── API + dashboard serving ────────────────────────────────────────────────
    # Production authority for the command center dashboard.
    # This service serves both the FastAPI backend (/api/*) and the operator UI
    # (/) from a single port. The current operator surface is the static
    # dashboard/public application mounted by the backend.
    systemd.services.command-center-dashboard-api = {
      description = "NixOS Command Center Dashboard API";
      wantedBy = ["multi-user.target"];
      path = dashboardPathPackages;
      after =
        ["network-online.target" "prometheus.service"]
        ++ lib.optionals cfg.roles.aiStack.enable ["ai-stack.target"];
      wants =
        ["network-online.target" "prometheus.service"]
        ++ lib.optionals cfg.roles.aiStack.enable ["ai-stack.target"];
      serviceConfig = {
        Type = "simple";
        # Phase 72.x — attach AppArmor profile (complain mode; enforce after May-30 soak)
        AppArmorProfile = "command-center-dashboard-api";
        User = svcUser;
        Group = svcGroup;
        SupplementaryGroups = ["llama" "ai-stack"];
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
        ReadOnlyPaths = [dashboardRoot];
        ReadWritePaths = [
          cc.dataDir
          mutableOptimizerDir
          "/tmp"
          "/run/sudo/ts"
          "${dashboardRoot}/docs/development"
          "${dashboardRoot}/data"
        ];
      };
      environment =
        {
          SERVICE_HOST = "127.0.0.1";
          PROMETHEUS_PORT = toString mon.prometheusPort;
          OTEL_COLLECTOR_HEALTH_PORT = toString ports.otelCollectorHealth;
          DASHBOARD_API_BIND_ADDRESS = cc.bindAddress;
          DASHBOARD_API_PORT = toString cc.apiPort;
          DASHBOARD_MODE = "systemd";
          DASHBOARD_EXPOSE_HOSTNAME = "false";
          DASHBOARD_HOSTNAME_ALIAS = "local-node";
          DASHBOARD_FRONTEND_DIST = dashboardPublicDir;
          DASHBOARD_CSP = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' ws: wss:; script-src 'self' 'unsafe-inline' https://unpkg.com https://d3js.org https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com";
          DASHBOARD_RATE_LIMIT_ENABLED = "true";
          DASHBOARD_RATE_LIMIT_WINDOW_SECONDS = "60";
          DASHBOARD_RATE_LIMIT_DEFAULT_RPM = "240";
          DASHBOARD_RATE_LIMIT_HEALTH_RPM = "120";
          DASHBOARD_RATE_LIMIT_SEARCH_RPM = "90";
          DASHBOARD_RATE_LIMIT_OPERATOR_WRITE_RPM = "30";
          DASHBOARD_OPERATOR_AUDIT_LOG_PATH = "${cc.dataDir}/telemetry/operator-audit.jsonl";
          DASHBOARD_DATA_DIR = "${cc.dataDir}";
          DASHBOARD_CONTEXT_DB_PATH = "${cc.dataDir}/telemetry/deployments-context.db";
          MODEL_REGISTRY_PATH = "${cc.dataDir}/model-registry.json";
          MODEL_STAGING_DIR = "${cc.dataDir}/model-downloads";
          MODEL_DIR = "/var/lib/llama-cpp/models";
          LLAMA_CPP_HEALTH_URL = "http://127.0.0.1:${toString cfg.aiStack.llamaCpp.port}/health";
          XDG_CACHE_HOME = "${cc.dataDir}/cache";
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
          PRSI_ACTION_QUEUE_PATH = "${mutableOptimizerDir}/prsi/action-queue.json";
          PRSI_ACTIONS_LOG_PATH = "${mutableLogDir}/prsi-actions.jsonl";
          PRSI_POLICY_FILE = "${mcp.repoPath}/config/runtime-prsi-policy.json";
          PRSI_STATE_PATH = "${mutableOptimizerDir}/prsi/runtime-state.json";
          OPTIMIZER_OVERRIDES_ENV = "${cc.dataDir}/telemetry/optimizer-overrides.env";
          OPTIMIZER_ACTIONS_LOG = "${cc.dataDir}/telemetry/optimizer-actions.jsonl";
          AI_SECURITY_AUDIT_DIR = "${mcp.dataDir}/security";
          AI_NPM_SECURITY_DIR = "${mcp.dataDir}/security/npm";
          SUDO_BIN = "/run/wrappers/bin/sudo";
          SYSTEMCTL_BIN = "${pkgs.systemd}/bin/systemctl";
          NFT_BIN = "${pkgs.nftables}/bin/nft";
          NFT_PRIVILEGED_BIN = "${nftDashboard}/bin/aq-nft-dashboard";
          CSCLI_BIN = "${pkgs.crowdsec}/bin/cscli";
          CSCLI_DECISION_DELETE_BIN = "${crowdsecDecisionDelete}/bin/aq-crowdsec-decision-delete";
          IPTABLES_BIN = "${pkgs.iptables}/bin/iptables";
        }
        // lib.optionalAttrs sec.enable {
          AIDER_WRAPPER_API_KEY_FILE = secretPath sec.names.aiderWrapperApiKey;
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
