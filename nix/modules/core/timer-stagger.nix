# Timer stagger (Rule 13, declarative): one shared default so the ai-*/aq-*
# timers never stampede the host. Root cause of the 2026-11-18 07:29 incident:
# 26 timers fired in one minute (load5 ~32 on 16 CPUs, 80C) because
#  (a) OnUnitActiveSec/OnBootSec timers had no RandomizedDelaySec, and
#  (b) Persistent=true catch-up elapses in the past, so RandomizedDelaySec is
#      added to a time that is already over and fires them all at once.
# Fix: every matched timer gets RandomizedDelaySec + FixedRandomDelay (stable
# per-timer offset) + AccuracySec, Persistent catch-up is replaced by a
# per-timer OnBootSec offset (hash-derived, heavy units pinned to distinct
# slots). Every default is a mkDefault option, so explicit per-timer values
# (including Persistent = true) win and a host can opt back into catch-up with
# mySystem.timerStagger.persistent = true.
# Evidence: docs/harness-first/evidence/2026-11-18-timer-stagger.md
{
  lib,
  config,
  ...
}: let
  cfg = config.mySystem.timerStagger;

  hexDigits = lib.stringToCharacters "0123456789abcdef";
  hexVal = c: lib.lists.findFirstIndex (x: x == c) 0 hexDigits;
  # 4 hex chars of sha256(name) -> 0..65535
  hashNum = name:
    lib.foldl' (acc: c: acc * 16 + hexVal c) 0
    (lib.stringToCharacters (builtins.substring 0 4 (builtins.hashString "sha256" name)));

  matches = name:
    lib.any (p: lib.hasPrefix p name) cfg.prefixes || lib.elem name cfg.extraNames;

  isShort = name: lib.elem name cfg.shortPeriodNames;

  # Boot window width scales with the number of staggered timers so slot
  # collisions do not grow as modules add timers (>= 2 slots per timer).
  matchedCount = lib.length (lib.filter matches (lib.attrNames config.systemd.timers));
  bootWidth = lib.max (cfg.bootWindowMinutes - 2) (2 * matchedCount);

  # Boot offset in minutes: pinned slot for heavy units, else 3.. by hash.
  bootMinutes = name:
    cfg.heavyBootSlotMinutes.${name} or (3 + lib.mod (hashNum name) bootWidth);
in {
  options.mySystem.timerStagger = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Apply RandomizedDelaySec/FixedRandomDelay/AccuracySec and a staggered boot catch-up to matching timers.";
    };
    prefixes = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = ["ai-" "aq-" "aqos-"];
      description = "Timer name prefixes the stagger applies to.";
    };
    extraNames = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "data-retention"
        "agent-reap"
        "nvd-sync"
        "lore-sync"
        "meta-optimization-analysis"
        "meta-optimization-validator"
        "fast-lane-staleness-check"
      ];
      description = "Non-prefixed timer names the stagger also applies to.";
    };
    shortPeriodNames = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [
        "ai-stack-health-monitor"
        "ai-rsi-sweep"
        "ai-prsi-rsi-dispatch"
        "ai-auto-remediate"
        "ai-context-warmer"
        "ai-mcp-process-watch"
        "ai-system-state"
        "ai-amdgpu-metrics-exporter"
        "ai-npm-security-monitor"
        "ai-cache-prewarm"
        "ai-autonomous-improvement"
        "aq-execution-cell-runner-mirror"
        "aqos-security-credential-status"
        "aq-network-policy-watchdog"
        "aq-llm-speed-probe"
        "agent-reap"
        "fast-lane-staleness-check"
      ];
      description = "Timers with a period of 15 min or less: small delay and short accuracy window.";
    };
    shortDelay = lib.mkOption {
      type = lib.types.str;
      default = "2min";
      description = "RandomizedDelaySec for short-period timers.";
    };
    longDelay = lib.mkOption {
      type = lib.types.str;
      default = "30min";
      description = "RandomizedDelaySec for hourly-or-longer timers without an explicit value.";
    };
    shortAccuracy = lib.mkOption {
      type = lib.types.str;
      default = "1min";
      description = "AccuracySec for short-period timers.";
    };
    longAccuracy = lib.mkOption {
      type = lib.types.str;
      default = "5min";
      description = "AccuracySec for hourly-or-longer timers without an explicit value.";
    };
    bootWindowMinutes = lib.mkOption {
      type = lib.types.ints.between 4 1440;
      default = 30;
      description = "Minimum upper bound (minutes after boot) of the hash-derived boot offset window; widened to 2 slots per matched timer when there are many.";
    };
    persistent = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Default Persistent= for matching timers. false avoids a past-due catch-up
        stampede (the OnBootSec offset is used instead); set true on hosts that
        are often off at the scheduled time so missed runs still catch up.
        Applied as a mkDefault: per-timer values always win.
      '';
    };
    heavyBootSlotMinutes = lib.mkOption {
      type = lib.types.attrsOf lib.types.int;
      default = {
        ai-prsi-orchestrator = 12;
        ai-optimizer = 18;
        ai-aidb-reindex = 30;
        ai-prompt-eval = 36;
        ai-local-training-loop = 42;
        ai-training-ingest = 48;
        ai-gap-auto-remediate = 54;
      };
      description = "Distinct post-boot slots (minutes, 6 apart) for CPU/llama-heavy units so they never overlap on boot.";
    };
  };

  # Extends the existing systemd.timers option type (submodule merge); no
  # per-module edits are needed for new timers.
  options.systemd.timers = lib.mkOption {
    type = lib.types.attrsOf (lib.types.submodule ({name, ...}: {
      config = lib.mkIf (cfg.enable && matches name) {
        timerConfig = {
          RandomizedDelaySec = lib.mkDefault (
            if isShort name
            then cfg.shortDelay
            else cfg.longDelay
          );
          FixedRandomDelay = lib.mkDefault true;
          AccuracySec = lib.mkDefault (
            if isShort name
            then cfg.shortAccuracy
            else cfg.longAccuracy
          );
          OnBootSec = lib.mkDefault "${toString (bootMinutes name)}min";
          Persistent = lib.mkDefault cfg.persistent;
        };
      };
    }));
  };
}
