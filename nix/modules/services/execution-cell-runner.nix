# Execution Cell Runner — Foundation C, C3b R3 (default-OFF, enforcement-tier).
#
# Declares ONLY the Nix surface authorized by
# `.agents/plans/aqos-foundation-c/C3B-R3-DESIGN-AND-AUTHORIZATION.md` §8,
# frozen by `C3B-R3-FREEZE-AND-ACTIVATION.md` and released for build by owner
# activation `c4aaf0117ec84f8e` (`activation.grant`): a dedicated,
# unprivileged, socket-activated service for
# `ai-stack/switchboard/execution_cell_runner.py`. `enable` defaults to
# `false` — this module ships INERT; flipping it to `true` in the running
# system is a FURTHER, separate owner act (R6 canary), not this build.
#
# SF-2 (design §2, grounded 2026-07-29): the host kernel already permits
# unprivileged user namespaces (`unshare --user --map-root-user` succeeds;
# `/proc/sys/user/max_user_namespaces = 111259`), so this module needs NO
# global `security.unprivilegedUsernsClone` change. The ONLY namespace
# relaxation anywhere in this build is THIS service's own
# `RestrictNamespaces = false` — scoped to this one unprivileged unit,
# never global. (R5-shadow deploy fix: the design's original
# `"CLONE_NEWUSER CLONE_NEWNS"` was malformed — systemd wants type names,
# not CLONE_* kernel flags, so it was silently ignored — AND semantically
# incompatible with bwrap `--unshare-all`, which must create all 7
# namespace types; `false` is the honest value for a service whose sole
# job is to build bwrap sandboxes.) `nix/modules/services/switchboard.nix`
# is a byte-parity anchor (frozen hash `4811326e891cab2e…`) and is NOT
# touched by this file.
{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.executionCellRunner;
  primaryUser = config.mySystem.primaryUser;
  # R7 (`R7-PROVISIONING-DESIGN-20260803.md` §2/§3): the SAME repo-path SSOT
  # `switchboard.nix` uses (`repoPath = cfg.mcpServers.repoPath;`) — the bare
  # mirror's clone/fetch source is the live working-tree checkout, never a
  # second path invented by this module.
  mirrorSourceRepo = config.mySystem.mcpServers.repoPath;
  mirrorSyncScript = pkgs.writeShellScript "aq-execution-cell-runner-mirror-sync" ''
    set -euo pipefail
    GIT="${pkgs.git}/bin/git"
    MIRROR="${cfg.mirrorPath}"
    SOURCE="${mirrorSourceRepo}"
    if [ ! -d "$MIRROR" ]; then
      "$GIT" clone --bare "$SOURCE" "$MIRROR"
    else
      "$GIT" --git-dir="$MIRROR" fetch "$SOURCE" '+refs/heads/*:refs/heads/*'
    fi
    chown -R aq-execution-cell-runner:aq-execution-cell-runner "$MIRROR"
  '';

  runnerPython = pkgs.python3.withPackages (ps: with ps; [cryptography]);

  # R5-shadow deployment fix: the runner imports its local deps by module name
  # (execution_grant, execution_cell_clone, capability_lease, capability_lease_gate,
  # execution_cell_validator, span_taxonomy, trace, event_log) which live across
  # scripts/ai/lib and ai-stack/switchboard. Running the bare Nix-store copy left
  # them off sys.path (ModuleNotFoundError -> crash-loop). This self-contained
  # bundle co-locates the exact transitive closure so `python3 <bundle>/runner.py`
  # resolves every import as a sibling — preserving the runner's ProtectHome
  # isolation (no /home/repo dependency). Config data (first-party manifest) is
  # lazy-loaded and unused on the runner path; epoch resolves to 0 (absent file),
  # consistent with the switchboard.
  runnerBundle = pkgs.runCommand "aq-execution-cell-runner-bundle" {} ''
    mkdir -p $out
    cp ${../../../ai-stack/switchboard/execution_cell_runner.py} $out/execution_cell_runner.py
    cp ${../../../ai-stack/switchboard/execution_cell_validator.py} $out/execution_cell_validator.py
    cp ${../../../ai-stack/switchboard/capability_lease_gate.py} $out/capability_lease_gate.py
    cp ${../../../scripts/ai/lib/execution_grant.py} $out/execution_grant.py
    cp ${../../../scripts/ai/lib/execution_cell_clone.py} $out/execution_cell_clone.py
    cp ${../../../scripts/ai/lib/durable_reservation.py} $out/durable_reservation.py
    cp ${../../../scripts/ai/lib/capability_lease.py} $out/capability_lease.py
    cp ${../../../scripts/ai/lib/span_taxonomy.py} $out/span_taxonomy.py
    cp ${../../../scripts/ai/lib/trace.py} $out/trace.py
    cp ${../../../scripts/ai/lib/event_log.py} $out/event_log.py
  '';

  runnerEnvironment = [
    "CAPABILITY_EXECUTION_CELLS=${
      if cfg.enable && cfg.flagOn
      then "1"
      else "0"
    }"
    "AQ_EXECUTION_CELL_RUNNER_SOCKET_PATH=${cfg.socketPath}"
    "AQ_EXECUTION_CELL_RUNNER_ALLOW_SELF_BIND=0"
    "AQ_EXECUTION_CELL_RUNNER_CLIENT_USER=${primaryUser}"
    "AQ_EXECUTION_CELL_RUNNER_STATE_ROOT=${cfg.stateDirectory}"
    "AQ_EXECUTION_CELL_RUNNER_MAX_CONCURRENT_CELLS=${toString cfg.maxConcurrentCells}"
    "AQ_EXECUTION_CELL_RUNNER_REQUEST_TIMEOUT_SECONDS=${toString cfg.requestTimeoutSeconds}"
    "AQ_EXECUTION_CELL_RUNNER_CGROUP_PARENT=/sys/fs/cgroup/system.slice/aq-execution-cell-runner.service"
    "AQ_EXECUTION_CELL_RUNNER_PYTHON_BIN=${runnerPython}/bin/python3"
    # R5: the runner's Ed25519 PUBLIC verify key (non-secret), read at eval from
    # the tracked config/grant-signing-public-key so it stays matched with the
    # SOPS private key the switchboard adapter signs with. The runner executes
    # from the Nix store, so the module's relative-file fallback cannot resolve —
    # this env is the authoritative public-key source.
    "AQ_EXECUTION_CELL_RUNNER_PUBLIC_KEY_HEX=${removeSuffix "\n" (builtins.readFile ../../../config/grant-signing-public-key)}"
    "BWRAP_PATH=${pkgs.bubblewrap}/bin/bwrap"
    # R7 §3: MUST be JSON — `build_config_from_env` parses this via
    # `json.loads` (execution_cell_runner.py:~1130); a `key=value` string
    # throws ValueError -> mirrors={} -> every grant denies
    # `unknown-trusted-repo` (the exact failure R7 exists to fix).
    # DEPLOY-BUG #11: systemd `Environment=` applies shell-style quote-removal, so a
    # BARE `{"primary":"…"}` reaches the runtime env as `{primary:…}` (double-quotes
    # stripped) -> json.loads ValueError -> mirrors={} -> unknown-trusted-repo. The
    # JSON is SINGLE-QUOTE-wrapped so systemd strips only the outer '' and keeps the
    # inner "" literal (verify with `systemctl show … -p Environment`).
    "AQ_EXECUTION_CELL_RUNNER_TRUSTED_REPO_MIRRORS='${builtins.toJSON {primary = cfg.mirrorPath;}}'"
  ];
in {
  options.mySystem.aiStack.executionCellRunner = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Enable the default-OFF C3b R3 execution-cell-runner service
        (socket-activated, dedicated unprivileged user, bwrap-confined).
        Standing enablement of this option does NOT itself authorize live
        execution — the in-process `CAPABILITY_EXECUTION_CELLS` flag
        (`cfg.flagOn`) independently gates whether the runner will ever
        construct a cell; both default `false`. Turning the runner ON in a
        deployed system is a FURTHER, separate owner act (R6 canary).
      '';
    };

    flagOn = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Nix-side mirror of the runner's own `CAPABILITY_EXECUTION_CELLS`
        default-OFF flag. Kept as a SEPARATE option from `enable` so that
        "the systemd unit exists and is enabled" and "the runner is
        authorized to construct cells" remain two independently-auditable
        false-by-default facts, matching the design's "flag DEFAULT-OFF"
        ceiling — never collapse them into a single switch.
      '';
    };

    socketPath = mkOption {
      type = types.str;
      default = "/run/aq-execution-cell-runner/control.sock";
      description = "Unix domain socket the runner listens on. Transport only — conveys no authority (SO_PEERCRED authenticates every peer).";
    };

    stateDirectory = mkOption {
      type = types.str;
      default = "/var/lib/aq-execution-cell-runner";
      description = "Private state root for cell working trees + quarantine (StateDirectory=aq-execution-cell-runner, owned by the runner's own unprivileged system user).";
    };

    mirrorPath = mkOption {
      type = types.str;
      default = "${cfg.stateDirectory}/mirror.git";
      description = ''
        R7 (`R7-PROVISIONING-DESIGN-20260803.md` §2): path to the runner-readable
        bare git mirror the R2 clone primitive clones from. Provisioned
        declaratively by `aq-execution-cell-runner-mirror.service` (a `git clone
        --bare`/`git fetch` oneshot, never by the unprivileged cell) and kept
        fresh by a companion timer floor. Defaults under the runner's own
        StateDirectory so it inherits the same private, runner-owned root.
      '';
    };

    maxConcurrentCells = mkOption {
      type = types.ints.between 1 2;
      default = 1;
      description = "Bounded concurrent cell ceiling (design §3). Max 2 before a new review is required.";
    };

    requestTimeoutSeconds = mkOption {
      type = types.ints.positive;
      default = 30;
      description = "Default per-request bounded-command timeout (seconds) when a grant's own resource_limits.timeout_s is absent/unusable.";
    };
  };

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.maxConcurrentCells >= 1 && cfg.maxConcurrentCells <= 2;
        message = "mySystem.aiStack.executionCellRunner.maxConcurrentCells must be 1 or 2 (design §3 ceiling; raising it further requires a new review).";
      }
    ];

    users.groups.aq-execution-cell-runner = {};
    users.groups.aq-execution-cell-clients = {};

    users.users.aq-execution-cell-runner = {
      isSystemUser = true;
      group = "aq-execution-cell-runner";
      description = "C3b R3 execution-cell-runner (dedicated, unprivileged; the ONLY holder of a relaxed userns in this build)";
      home = cfg.stateDirectory;
      createHome = false;
      # No membership in any privileged group (design §3: "no membership in
      # any privileged group").
      extraGroups = [];
    };

    # Only the switchboard identity joins the client group (design §3/§8) —
    # this is the SOLE relationship between this module and the switchboard;
    # switchboard.nix itself is never edited.
    users.users.${primaryUser}.extraGroups = mkAfter ["aq-execution-cell-clients"];

    # Create the socket's parent dir root-owned (NOT via the service's
    # RuntimeDirectory — see deploy-bug #7 note in serviceConfig). root:root 0755
    # is world-traversable so a client-group member can reach the 0660 socket the
    # socket-unit creates inside it, and systemd never re-groups a root-owned dir's
    # socket to the service user on start.
    systemd.tmpfiles.rules = [
      "d ${builtins.dirOf cfg.socketPath} 0755 root root -"
      # R7 §2: the mirror oneshot (below) is a SEPARATE unit from the main
      # runner service, so it cannot rely on that service's own
      # `StateDirectory=` (systemd only creates a unit's StateDirectory
      # before THAT unit's own ExecStart). Declare the same root here so it
      # exists, correctly-owned, independent of service start ordering.
      "d ${cfg.stateDirectory} 0700 aq-execution-cell-runner aq-execution-cell-runner -"
    ];

    systemd.sockets.aq-execution-cell-runner = {
      description = "C3b R3 execution-cell-runner control socket (transport only; SO_PEERCRED-gated)";
      wantedBy = ["sockets.target"];
      socketConfig = {
        ListenStream = cfg.socketPath;
        SocketUser = "aq-execution-cell-runner";
        SocketGroup = "aq-execution-cell-clients";
        SocketMode = "0660";
        Accept = false;
        RemoveOnStop = true;
      };
    };

    systemd.services.aq-execution-cell-runner = {
      description = "C3b R3 execution-cell-runner (default-OFF, bwrap-confined execution cells)";
      requires = ["aq-execution-cell-runner.socket"];
      after = ["aq-execution-cell-runner.socket"];
      # Deploy-bug #13 (found by the R7 GREEN deploy-exercise, first live cell
      # run): R2 create_cell + the out-of-cell validator invoke git via bare
      # `subprocess.run(["git", ...])` (R2's reviewed contract: the runner
      # provides git on PATH). The service PATH had no git, so every clone raised
      # FileNotFoundError -> caught by create_cell's outer handler -> the
      # catch-all FAILURE_QUARANTINED at STAGE_CELL_CREATE (looks like a cell
      # quarantine, is actually "git not found"). The mirror-sync oneshot worked
      # only because it uses absolute ${pkgs.git}/bin/git. Provide git here.
      path = [pkgs.git];
      # NOT wantedBy multi-user.target — purely socket-activated; no
      # independent boot-time start (design: no live traffic, no adoption).
      unitConfig = {
        StartLimitIntervalSec = "300";
        StartLimitBurst = 5;
      };
      serviceConfig = {
        Type = "simple";
        ExecStart = "${runnerPython}/bin/python3 ${runnerBundle}/execution_cell_runner.py";
        Environment = runnerEnvironment;
        # StandardOutput=journal by default, but StandardError defaulted to
        # `inherit` (-> systemd's own stderr, effectively discarded), so the
        # runner's stderr — Python tracebacks AND the bug #12 `[cell-fence]`
        # quarantine diagnostic — never reached journald. Route it to journal:
        # low-cardinality operator log, root/adm-only, no cross-service leak.
        StandardError = "journal";
        User = "aq-execution-cell-runner";
        Group = "aq-execution-cell-runner";
        StateDirectory = "aq-execution-cell-runner";
        StateDirectoryMode = "0700";
        # NO RuntimeDirectory (deploy-bug #7, found by the R6 deploy-exercise):
        # a RuntimeDirectory named for this service is owned by the service User
        # (aq-execution-cell-runner), and systemd re-applies that ownership to the
        # directory AND the socket the socket-unit created inside it on service
        # start — clobbering SocketGroup=aq-execution-cell-clients to the service
        # group, so clients can no longer connect after the first activation. The
        # socket's parent dir is instead created root-owned via systemd.tmpfiles
        # (below), which systemd never re-owns on start; the socket keeps 0660
        # aq-execution-cell-runner:aq-execution-cell-clients.
        Restart = "on-failure";
        RestartSec = "5s";
        TimeoutStopSec = "15s";

        # ── Hardening ceiling (design §3/§8 — exactly this set, no more,
        # no less; switchboard.nix's own hardening is untouched) ──────────
        NoNewPrivileges = true;
        CapabilityBoundingSet = "";
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
        # The ONE relaxation vs. switchboard.nix's hardening (byte-parity
        # anchor, untouched): this service alone gets the scoped namespaces
        # bwrap needs to build its OWN inner namespaces. Every namespace
        # bwrap unshares (pid/net/ipc/uts/cgroup) happens INSIDE the user
        # namespace it creates — no host privilege is granted by this line.
        RestrictNamespaces = false; # R5-shadow deploy fix: the prior "CLONE_NEWUSER CLONE_NEWNS" was malformed (systemd wants type names) AND incompatible with bwrap --unshare-all (needs all 7 namespace types). The runner's confinement IS bwrap; namespace creation is its core function. (Hardening note for codex: scope via a valid full type list only if it ever proves necessary.)

        # cgroup v2 delegation (design §8, antigravity SHOULD-FIX, Q-R3-3):
        # required for the unprivileged runner to write `cgroup.kill` /
        # control its own per-cell cgroup subtree for the §6 whole-tree
        # reap. Delegating only pids+memory (not the full controller set).
        Delegate = "pids memory";
      };
    };

    # R7 §2: bare-mirror provisioning — a dedicated oneshot that clones (first
    # run) or fetches (subsequent runs) the working repo into the runner-
    # readable bare mirror at `cfg.mirrorPath`, NEVER performed by the
    # unprivileged cell itself. Runs as root so it can read the working
    # repo regardless of its ownership/mode and then hand the mirror to the
    # runner's own user — the runner user holds no other privileged group
    # membership (design §3) and is never the one touching the source repo.
    systemd.services.aq-execution-cell-runner-mirror = {
      description = "R7 bare-mirror provisioning/freshness sync for aq-execution-cell-runner (keeps base_revision resolvable)";
      wantedBy = ["aq-execution-cell-runner.service"];
      before = ["aq-execution-cell-runner.service"];
      serviceConfig = {
        Type = "oneshot";
        User = "root";
        ExecStart = "${mirrorSyncScript}";
      };
    };

    # Freshness floor (design §2 "path/timer sync"): best-effort periodic
    # re-fetch so the mirror does not go stale between runner activations —
    # a stale mirror only ever produces a typed `base-oid-unreachable` deny
    # (content is OID-bound), never a wrong result.
    systemd.timers.aq-execution-cell-runner-mirror = {
      description = "R7 periodic freshness floor for the aq-execution-cell-runner bare mirror";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnBootSec = "5min";
        OnUnitActiveSec = "15min";
      };
    };
  };
}
