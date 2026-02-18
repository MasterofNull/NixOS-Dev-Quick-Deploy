{ pkgs, ... }:
let
  guardrailFailureNotify = pkgs.writeShellApplication {
    name = "guardrail-failure-notify";
    runtimeInputs = with pkgs; [
      coreutils
      gnugrep
      systemd
      util-linux
    ];
    text = ''
      set -euo pipefail

      unit_name="''${1:-unknown.service}"
      timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
      alert_dir="/var/lib/nixos-quick-deploy/alerts"
      safe_unit="${unit_name//[![:alnum:]_.-]/_}"
      alert_file="''${alert_dir}/''${safe_unit}-''${timestamp}.log"

      mkdir -p "$alert_dir"

      {
        echo "=== Deployment Guardrail Failure ==="
        echo "Timestamp (UTC): $timestamp"
        echo "Host: $(hostname -s 2>/dev/null || hostname)"
        echo "Unit: $unit_name"
        echo
        echo "=== systemctl status ==="
        systemctl --no-pager --full status "$unit_name" 2>&1 || true
        echo
        echo "=== journalctl (last 200 lines) ==="
        journalctl -u "$unit_name" -n 200 --no-pager 2>&1 || true
        echo
        echo "=== Recommended next step ==="
        echo "Run: /run/current-system/sw/bin/fs-integrity-check"
        echo "Run: /run/current-system/sw/bin/disk-health-check"
        echo "If root fs errors are present, boot rescue media and run offline repair:"
        echo "  e2fsck -f -y /dev/disk/by-uuid/<root-uuid>"
      } >"$alert_file"

      alert_msg="Guardrail monitor failure in $unit_name. Details: $alert_file"
      echo "$alert_msg"
      echo "$alert_msg" | systemd-cat -t deploy-guardrail-alert -p err || true

      if command -v wall >/dev/null 2>&1; then
        wall "$alert_msg" || true
      fi
    '';
  };
in
{
  config = {
    environment.systemPackages = [ guardrailFailureNotify ];

    systemd.services."deploy-guardrail-alert@" = {
      description = "Deployment Guardrail Failure Alert (%i)";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${guardrailFailureNotify}/bin/guardrail-failure-notify %i";
      };
    };
  };
}
