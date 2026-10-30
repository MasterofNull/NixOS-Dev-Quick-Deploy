# P1.7 (system-integrity-recovery): AC-aware power profile + local-model speed probe.
# Evidence: .agents/delegation/outputs/llama-throughput-diagnosis-20261027.md
# (battery + power-saver = 1.7-2.0 tok/s vs 3.75-4.58 on AC + performance).
# Both features are opt-in via mySystem.deployment.powerPolicy.*.
{
  lib,
  pkgs,
  config,
  ...
}: let
  cfg = config.mySystem;
  pcfg = cfg.deployment.powerPolicy;
  ppctl = "${pkgs.power-profiles-daemon}/bin/powerprofilesctl";

  # Idempotent; does nothing when no Mains supply reports online state (desktop).
  applyProfile = pkgs.writeShellScript "power-policy-apply" ''
    online=""
    for f in /sys/class/power_supply/*/online; do
      [ -r "$f" ] || continue
      t="$(cat "$(dirname "$f")/type" 2>/dev/null || true)"
      [ "$t" = Mains ] || continue
      online="$(cat "$f")"
      [ "$online" = 1 ] && break
    done
    [ -n "$online" ] || exit 0
    if [ "$online" = 1 ]; then want=performance; else want=balanced; fi
    [ "$(${ppctl} get)" = "$want" ] || ${ppctl} set "$want"
  '';

  scriptPath = "${cfg.mcpServers.repoPath}/scripts/ai/aq-llm-speed-probe";
  llamaUrl = "http://127.0.0.1:${toString cfg.aiStack.llamaCpp.port}";
in {
  config = lib.mkMerge [
    (lib.mkIf pcfg.acAwareProfile.enable {
      assertions = [
        {
          assertion = config.services.power-profiles-daemon.enable;
          message = "mySystem.deployment.powerPolicy.acAwareProfile requires services.power-profiles-daemon.enable (set by hardware/mobile.nix on mobile hosts).";
        }
      ];

      systemd.services.power-policy-apply = {
        description = "Apply AC-aware power profile (performance on AC, balanced on battery)";
        after = ["power-profiles-daemon.service"];
        wants = ["power-profiles-daemon.service"];
        # graphical.target, not multi-user.target: power-profiles-daemon is After=multi-user.target, and a
        # target is implicitly After= every unit it wants, so multi-user -> apply -> ppd -> multi-user cycled.
        wantedBy = ["graphical.target" "post-resume.target"];
        serviceConfig = {
          Type = "oneshot";
          ExecStart = "${applyProfile}";
        };
      };

      services.udev.extraRules = ''
        SUBSYSTEM=="power_supply", ATTR{type}=="Mains", TAG+="systemd", ENV{SYSTEMD_WANTS}+="power-policy-apply.service"
      '';
    })

    (lib.mkIf pcfg.speedProbe.enable {
      systemd.services.aq-llm-speed-probe = {
        description = "Local model tok/s probe (power/memory cause labelling)";
        after = ["llama-cpp.service"];
        path = [pkgs.power-profiles-daemon pkgs.procps];
        serviceConfig = {
          Type = "oneshot";
          User = cfg.primaryUser;
          SupplementaryGroups = ["ai-stack"];
          Environment = [
            "LLAMA_URL=${llamaUrl}"
            "AQ_TELEMETRY_DIR=/var/lib/ai-stack/hybrid/telemetry"
            "AQ_SPEED_MIN_TOKPS=${pcfg.speedProbe.minTokPerSec}"
          ];
          ExecStart = "${pkgs.python3}/bin/python3 ${scriptPath}";
          # Exit 1 (slow) is a finding recorded in telemetry, not a unit failure.
          SuccessExitStatus = "1";
          NoNewPrivileges = true;
          ProtectSystem = "strict";
          ProtectHome = "read-only";
          ReadWritePaths = ["/var/lib/ai-stack/hybrid/telemetry"];
          PrivateTmp = true;
          TimeoutStartSec = "420";
          MemoryMax = "128M";
        };
      };

      systemd.timers.aq-llm-speed-probe = {
        description = "Periodic local model speed probe";
        wantedBy = ["timers.target"];
        timerConfig = {
          OnBootSec = "10min";
          OnUnitActiveSec = "${toString pcfg.speedProbe.intervalMinutes}min";
          Unit = "aq-llm-speed-probe.service";
        };
      };

      # 90 s after resume, once the profile/AC state has settled.
      systemd.services.aq-llm-speed-probe-resume = {
        description = "Local model speed probe after resume";
        wantedBy = ["post-resume.target"];
        after = ["post-resume.target"];
        serviceConfig = {
          Type = "oneshot";
          TimeoutStartSec = "150";
          ExecStart = "${pkgs.coreutils}/bin/sleep 90";
          ExecStartPost = "${pkgs.systemd}/bin/systemctl --no-block start aq-llm-speed-probe.service";
        };
      };
    })
  ];
}
