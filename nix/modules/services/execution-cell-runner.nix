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
# `RestrictNamespaces = "CLONE_NEWUSER CLONE_NEWNS"` — scoped to this one
# unprivileged unit, never global. `nix/modules/services/switchboard.nix`
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

  runnerPython = pkgs.python3.withPackages (ps: with ps; [cryptography]);

  runnerEnvironment = [
    "CAPABILITY_EXECUTION_CELLS=${
      if cfg.enable && cfg.flagOn
      then "1"
      else "0"
    }"
    "AQ_EXECUTION_CELL_RUNNER_SOCKET_PATH=${cfg.socketPath}"
    "AQ_EXECUTION_CELL_RUNNER_STATE_ROOT=${cfg.stateDirectory}"
    "AQ_EXECUTION_CELL_RUNNER_MAX_CONCURRENT_CELLS=${toString cfg.maxConcurrentCells}"
    "AQ_EXECUTION_CELL_RUNNER_REQUEST_TIMEOUT_SECONDS=${toString cfg.requestTimeoutSeconds}"
    "AQ_EXECUTION_CELL_RUNNER_CGROUP_PARENT=/sys/fs/cgroup/system.slice/aq-execution-cell-runner.service"
    "AQ_EXECUTION_CELL_RUNNER_PYTHON_BIN=${runnerPython}/bin/python3"
    "BWRAP_PATH=${pkgs.bubblewrap}/bin/bwrap"
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
      # NOT wantedBy multi-user.target — purely socket-activated; no
      # independent boot-time start (design: no live traffic, no adoption).
      unitConfig = {
        StartLimitIntervalSec = "300";
        StartLimitBurst = 5;
      };
      serviceConfig = {
        Type = "simple";
        ExecStart = "${runnerPython}/bin/python3 ${../../../ai-stack/switchboard/execution_cell_runner.py}";
        Environment = runnerEnvironment;
        User = "aq-execution-cell-runner";
        Group = "aq-execution-cell-runner";
        StateDirectory = "aq-execution-cell-runner";
        StateDirectoryMode = "0700";
        RuntimeDirectory = "aq-execution-cell-runner";
        RuntimeDirectoryMode = "0750";
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
        RestrictNamespaces = "CLONE_NEWUSER CLONE_NEWNS";

        # cgroup v2 delegation (design §8, antigravity SHOULD-FIX, Q-R3-3):
        # required for the unprivileged runner to write `cgroup.kill` /
        # control its own per-cell cgroup subtree for the §6 whole-tree
        # reap. Delegating only pids+memory (not the full controller set).
        Delegate = "pids memory";
      };
    };
  };
}
