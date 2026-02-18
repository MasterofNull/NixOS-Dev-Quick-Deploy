{ lib, pkgs, config, ... }:
let
  cfg = config.mySystem.deployment.diskHealthMonitor;
  interval = toString cfg.intervalMinutes;

  diskHealthCheck = pkgs.writeShellApplication {
    name = "disk-health-check";
    runtimeInputs = with pkgs; [
      coreutils
      gawk
      gnugrep
      util-linux
      smartmontools
      nvme-cli
    ];
    text = ''
      set -euo pipefail

      info() {
        printf '[disk-health-check] %s\n' "$*"
      }

      root_src="$(findmnt -no SOURCE / 2>/dev/null || true)"
      if [[ -z "$root_src" ]]; then
        info "Unable to resolve root block device."
        exit 1
      fi

      root_real="$(readlink -f "$root_src" 2>/dev/null || true)"
      if [[ -z "$root_real" ]]; then
        root_real="$root_src"
      fi

      if [[ ! -b "$root_real" ]]; then
        info "Root source '$root_src' resolved to '$root_real' (not a block device); skipping SMART/NVMe checks."
        exit 0
      fi

      parent_kname="$(lsblk -no PKNAME "$root_real" 2>/dev/null | head -n1 || true)"
      if [[ -n "$parent_kname" ]]; then
        disk_dev="/dev/$parent_kname"
      else
        disk_dev="$root_real"
      fi

      info "Checking disk: $disk_dev (root source: $root_src)"

      smart_out="$(smartctl -H "$disk_dev" 2>/dev/null || true)"
      if [[ -n "$smart_out" ]]; then
        if echo "$smart_out" | grep -Eiq 'SMART overall-health self-assessment test result:[[:space:]]*PASSED|SMART Health Status:[[:space:]]*OK'; then
          info "SMART overall health: PASSED"
        elif echo "$smart_out" | grep -Eiq 'FAILED|FAIL'; then
          info "CRITICAL: SMART reports disk failure."
          exit 2
        else
          info "SMART health output inconclusive; review manually."
        fi
      else
        info "SMART output unavailable for $disk_dev."
      fi

      if [[ "$disk_dev" == /dev/nvme* ]]; then
        nvme_out="$(nvme smart-log "$disk_dev" 2>/dev/null || true)"
        if [[ -n "$nvme_out" ]]; then
          critical_warning="$(echo "$nvme_out" | awk '/critical_warning/ {print $3; exit}')"
          if [[ -n "$critical_warning" && "$critical_warning" != "0x0" && "$critical_warning" != "0" ]]; then
            info "CRITICAL: NVMe critical_warning=$critical_warning"
            exit 2
          fi
          media_errors="$(echo "$nvme_out" | awk '/media_errors/ {print $3; exit}')"
          if [[ -n "$media_errors" && "$media_errors" != "0" ]]; then
            info "WARNING: NVMe media_errors=$media_errors"
          fi
          info "NVMe health check complete."
        else
          info "NVMe smart-log unavailable for $disk_dev."
        fi
      fi

      exit 0
    '';
  };
in
{
  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ diskHealthCheck ];

    systemd.services.disk-health-monitor = {
      description = "Disk Health Monitor (SMART/NVMe)";
      after = [ "multi-user.target" ];
      onFailure = [ "deploy-guardrail-alert@%n.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${diskHealthCheck}/bin/disk-health-check";
      };
    };

    systemd.timers.disk-health-monitor = {
      description = "Periodic disk health monitor";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "5min";
        OnUnitActiveSec = "${interval}min";
        RandomizedDelaySec = "5min";
        Persistent = true;
        Unit = "disk-health-monitor.service";
      };
    };
  };
}
