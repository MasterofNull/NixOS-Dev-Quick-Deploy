# Agent reaper — periodic cleanup of orphaned/wedged aq-agent-loop processes AND
# reconciliation of stale delegation-registry rows.
#
# The registry (.agents/delegation/registry.jsonl) accumulates rows stuck at
# status=running when a background dispatch's process dies without the --wait handler
# updating it (or an antigravity dispatch that never records a pid). aq-agent-reap
# --reconcile-registry marks those (dead/absent pid, aged) as status=orphaned so ops
# views (aq-tui-dashboard) show true live state.
#
# IMPORTANT: runs as the registry OWNER (primaryUser), not root — the reconcile rewrites
# the file via os.replace, which would otherwise flip it to root-owned and break the
# hyperd delegate scripts' `>>` appends.
#
# Usage:
#   services.agent-reap.enable = true;
{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.services.agent-reap;

  reapScript = pkgs.writeShellScript "agent-reap-run" ''
    set -euo pipefail
    # aq-agent-reap resolves the registry relative to its own repo location; invoke the
    # repo copy directly. --reconcile-registry also runs the process-reap pass. The
    # built-in quiescence guard downgrades the registry write to a safe preview if any
    # dispatch is active, so a live agent's concurrent append is never raced.
    exec ${cfg.repoRoot}/scripts/ai/aq-agent-reap \
      --reconcile-registry \
      --registry-age ${toString cfg.registryAge} \
      --max-age ${toString cfg.maxAge}
  '';
in {
  options.services.agent-reap = {
    enable = lib.mkEnableOption "aq-agent-reap orphan-process + registry reconciliation timer";

    user = lib.mkOption {
      type = lib.types.str;
      default = "root";
      description = "User to run the reaper as. MUST own .agents/delegation/registry.jsonl — the reconcile rewrites it via os.replace, so a non-owner (e.g. root) would change file ownership and break delegate appends.";
    };

    repoRoot = lib.mkOption {
      type = lib.types.str;
      description = "Absolute path to the repo root (the reaper resolves the registry relative to its own location under here).";
      example = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy";
    };

    registryAge = lib.mkOption {
      type = lib.types.int;
      default = 1800;
      description = "Minimum age in seconds before a dead/absent-pid status=running row is reconciled to orphaned. The bound protects a just-dispatched task that has not yet recorded its pid.";
    };

    maxAge = lib.mkOption {
      type = lib.types.int;
      default = 3600;
      description = "Wall-clock age (s) beyond which a still-running aq-agent-loop process is reaped as a runaway.";
    };

    interval = lib.mkOption {
      type = lib.types.str;
      default = "*:0/30";
      example = "hourly";
      description = "systemd OnCalendar cadence (default every 30 min, matching the registry stall threshold).";
    };

    onBoot = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run once shortly after boot in addition to the scheduled interval.";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.timers.agent-reap = {
      description = "aq-agent-reap orphan-process + registry reconciliation timer";
      wantedBy = ["timers.target"];
      timerConfig =
        {
          OnCalendar = cfg.interval;
          Persistent = true;
          RandomizedDelaySec = "2min";
        }
        // lib.optionalAttrs cfg.onBoot {
          OnBootSec = "5min";
        };
    };

    systemd.services.agent-reap = {
      description = "Reap orphaned aq-agent-loop processes + reconcile stale delegation-registry rows";

      # ps/pgrep (procps) to enumerate/guard processes; python3 for the reaper itself.
      path = with pkgs; [python3 procps coreutils];

      serviceConfig = {
        Type = "oneshot";
        User = cfg.user;
        ExecStart = reapScript;
        TimeoutStartSec = "2min";

        # Hardening. Deliberately NOT set: ProtectHome (repo + registry live under /home)
        # and ProtectProc (the reaper needs ps/pgrep to see agent processes).
        PrivateTmp = true;
        NoNewPrivileges = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictNamespaces = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
      };
    };
  };
}
