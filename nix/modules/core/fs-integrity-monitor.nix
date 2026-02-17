{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem.deployment.fsIntegrityMonitor;
  interval = toString cfg.intervalMinutes;

  fsIntegrityCheck = pkgs.writeShellApplication {
    name = "fs-integrity-check";
    runtimeInputs = with pkgs; [
      coreutils
      gnugrep
      util-linux
      systemd
    ];
    text = ''
      set -euo pipefail

      info() {
        printf '[fs-integrity-check] %s\n' "$*"
      }

      pattern='Failed to start File System Check on|Dependency failed for /sysroot|You are in emergency mode|systemd-fsck.*failed|status=1/FAILURE|status=4|has unrepaired errors, please fix them manually|mounting fs with errors, running e2fsck is recommended|error count since last fsck'

      current_boot="$(journalctl -b --no-pager 2>/dev/null || true)"
      current_kernel="$(journalctl -k -b --no-pager 2>/dev/null || true)"
      previous_boot="$(journalctl -b -1 --no-pager 2>/dev/null || true)"
      previous_kernel="$(journalctl -k -b -1 --no-pager 2>/dev/null || true)"

      combined_logs="$current_boot"$'\n'"$current_kernel"$'\n'"$previous_boot"$'\n'"$previous_kernel"

      if echo "$combined_logs" | grep -Eiq "$pattern"; then
        root_src="$(findmnt -no SOURCE / 2>/dev/null || true)"
        root_real="$(readlink -f "$root_src" 2>/dev/null || true)"
        root_uuid=""
        if [ -z "$root_real" ]; then
          root_real="$root_src"
        fi
        if [ -n "$root_real" ] && [ -b "$root_real" ]; then
          root_uuid="$(blkid -s UUID -o value "$root_real" 2>/dev/null || true)"
          if [ -z "$root_uuid" ]; then
            root_uuid="$(lsblk -no UUID "$root_real" 2>/dev/null | head -n1 || true)"
          fi
        fi

        if [ -n "$root_uuid" ]; then
          info "CRITICAL: filesystem integrity signatures detected."
          info "Recommended offline repair: e2fsck -f /dev/disk/by-uuid/$root_uuid"
        else
          info "CRITICAL: filesystem integrity signatures detected."
          info "Recommended offline repair: e2fsck -f <root-device>"
        fi
        exit 2
      fi

      info "No filesystem integrity failure signatures detected in current/previous boot logs."
      exit 0
    '';
  };
in
{
  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ fsIntegrityCheck ];

    systemd.services.fs-integrity-monitor = {
      description = "Filesystem Integrity Monitor";
      after = [ "multi-user.target" ];
      onFailure = [ "deploy-guardrail-alert@%n.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${fsIntegrityCheck}/bin/fs-integrity-check";
      };
    };

    systemd.timers.fs-integrity-monitor = {
      description = "Periodic filesystem integrity monitor";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "3min";
        OnUnitActiveSec = "${interval}min";
        RandomizedDelaySec = "2min";
        Persistent = true;
        Unit = "fs-integrity-monitor.service";
      };
    };
  };
}
