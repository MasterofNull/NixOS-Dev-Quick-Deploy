# Foundation C — SAFETY: dead-man auto-revert guard for enforcement activations.
# DEFAULT-OFF / INERT. Owner-directed 2026-09-24.
#
# Purpose: when a security enforcement control is switched ON, auto-revert it OFF if the
# system doesn't stay healthy within a bounded window — a bad activation self-heals in N
# minutes without a human catching it. This ADDS a layer; it never replaces the existing
# manual kill-switches (CAPABILITY_LEASE_ENFORCEMENT / CAPABILITY_CELL_ADAPTER env flags,
# nix/modules/services/switchboard.nix; the C6 `aq-epoch-bump` lever) or the health-spider /
# dashboard capability-enforcement signal (`/api/stats/capability-enforcement`,
# `aq-health-spider`'s `_capability_enforcement_check`) — this composes with those, it does
# not reimplement them.
#
# Generic by design: this module (and scripts/ai/lib/activation_guard.py it runs) has NO
# per-control knowledge — no C6/C2/C3b branches. Every armed activation carries its OWN
# health-check command and its OWN revert command, supplied by the operator at `arm` time
# via `aq-activation-guard arm <control-id> --window <minutes> --health-check <cmd>
# --revert-cmd <the documented kill action>`. Enabling this module turns ON the periodic
# sweep that enforces already-armed deadlines; it arms NOTHING by itself — arming any
# specific activation is always a separate, explicit operator act (never auto-armed by a
# rebuild, a profile, or this module).
#
# FAIL-SAFE property (the reason this exists): at an armed deadline, the sweep
# (scripts/ai/lib/activation_guard.py::sweep) reverts unless the configured health check
# read back an explicit GREEN. RED, an unreadable/erroring health check, and any internal
# error in the sweep itself all resolve to executing the revert command + a LOUD `aq-event`
# alert — never to silently leaving a bad activation on.
{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.activationAutoRevert;
  repoPath = config.mySystem.mcpServers.repoPath;
  guardPython = pkgs.python3;
in {
  options.mySystem.aiStack.activationAutoRevert = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Enable the default-OFF activation-auto-revert-guard sweep timer. When on, a periodic
        sweep checks every armed activation (written by `aq-activation-guard arm ...`) past
        its deadline: health GREEN -> auto-confirm (no action); NOT-GREEN or unreadable ->
        execute that activation's own documented revert command + emit a LOUD `aq-event`
        alert (fail-safe: errs toward revert, never toward silently leaving a bad activation
        on). REVERT: enable = false (any already-armed records simply stop being swept —
        confirm/disarm them by hand, or re-enable to resume enforcing their deadlines).
        Enabling this arms NOTHING by itself; arming is always a separate operator act.
      '';
    };

    stateDir = mkOption {
      type = types.str;
      default = "/var/lib/aq-activation-guard";
      description = ''
        StateDirectory root holding armed/<control-id>.json (0600, one per currently-armed
        activation) and history.jsonl (append-only terminal record: confirmed/disarmed/
        auto-reverted). Durable across service restarts and rebuilds — the directory itself
        is declared once via systemd.tmpfiles.rules (Rule 13, declarative-only) and never
        reset; its contents are runtime state the guard itself manages.
      '';
    };

    sweepIntervalSec = mkOption {
      type = types.str;
      default = "60";
      description = ''
        OnUnitActiveSec cadence for the sweep service — how often armed deadlines are
        checked, independent of any individual activation's own --window. 60s means an armed
        deadline is acted on within at most ~1 minute of passing.
      '';
    };

    user = mkOption {
      type = types.str;
      default = "root";
      description = ''
        User the sweep runs as. Root by default: the guard's entire purpose is executing an
        operator-supplied revert command (systemctl restart/override, aq-* CLI, a kill-file
        write, ...) which generally needs the same service-management privilege a human
        running that same kill action by hand would need. The guard has no elevated
        privilege beyond what the armed revert-cmd itself requires — it is a scheduler for
        commands the operator already trusts, not a new privilege boundary.
      '';
    };
  };

  config = mkIf cfg.enable {
    systemd.tmpfiles.rules = [
      "d ${cfg.stateDir} 0700 ${cfg.user} ${cfg.user} -"
      "d ${cfg.stateDir}/armed 0700 ${cfg.user} ${cfg.user} -"
    ];

    systemd.timers.activation-auto-revert = {
      description = "Dead-man auto-revert guard sweep timer (Foundation C safety layer, default-OFF)";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnUnitActiveSec = cfg.sweepIntervalSec;
        OnBootSec = "1min";
        AccuracySec = "5s";
      };
    };

    systemd.services.activation-auto-revert = {
      description = "Dead-man auto-revert guard sweep — arm/confirm/disarm state machine (see aq-activation-guard)";
      path = with pkgs; [systemd bash];
      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        ExecStart = lib.escapeShellArgs [
          "${guardPython}/bin/python3"
          "${repoPath}/scripts/ai/aq-activation-guard"
          "sweep"
          "--state-dir"
          cfg.stateDir
        ];
        Environment = ["AQ_ACTIVATION_GUARD_STATE_DIR=${cfg.stateDir}"];
        TimeoutStartSec = "5min";
        # Deliberately NOT sandboxed with ProtectSystem/ProtectHome/RestrictNamespaces etc:
        # an armed revert-cmd is an operator-supplied documented kill action (systemctl
        # restart, a config-override write, another aq-* CLI, ...) and needs the same
        # system-management reach the human kill action needs — over-sandboxing this unit
        # would silently break the one thing it exists to do. The narrower hardening below
        # (NoNewPrivileges, RestrictSUIDSGID, LockPersonality) costs nothing a legitimate
        # revert command would ever need.
        NoNewPrivileges = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
      };
    };
  };
}
