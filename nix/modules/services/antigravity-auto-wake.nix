# Foundation collaboration — Antigravity advisory-lane auto-wake (default-OFF).
#
# Problem: the Antigravity IDE does NOT poll the watched inbox
# (`.agent/collaboration/antigravity-inbox/`), so a dropped review/PRD/plan task sits there until the
# owner manually nudges the IDE. The sanctioned wake is `aq-antigravity-inbox wake <task> --actor
# owner-manual`, which runs `antigravity chat --reuse-window --mode agent "<standing wake prompt>"` to
# drive the ALREADY-RUNNING IDE to poll → claim → do → complete. That wake is deliberately actor-gated
# to `owner-manual` because it puppets the owner's OAuth-authenticated IDE session — no autonomous agent
# may fire it.
#
# This module closes the loop WITHOUT weakening that gate: a per-user systemd PATH unit (runs in the
# owner's OWN session, as the owner) watches the inbox dir and fires the `owner-manual` wake on every new
# drop. It is the owner's own session automating the owner's own manual step — so `owner-manual` is
# honest, and the harness still never drives the IDE from a service principal. Default-OFF: enable it
# when your IDE is open; a wake with no IDE running is a harmless no-op. It authorizes nothing and mints
# no lease/grant — it only nudges the IDE to look at an already-dropped advisory task.
{
  lib,
  config,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.antigravityAutoWake;
  repoPath = config.mySystem.mcpServers.repoPath;
  aqInbox = "${repoPath}/scripts/ai/aq-antigravity-inbox";
  # Resolve the next eligible pending task from the supervisor's own state (read-only), then fire the
  # owner-manual wake for exactly that task. No task pending -> no wake (so unrelated inbox churn —
  # claim markers, receipts, lane-state — never nudges the IDE). One wake handles one drop; a later drop
  # re-triggers the path unit.
  wakeScript = pkgs.writeShellScript "aq-antigravity-auto-wake" ''
    set -u
    next="$(${pkgs.python3}/bin/python3 "${aqInbox}" status --json 2>/dev/null \
      | ${pkgs.python3}/bin/python3 -c 'import sys,json;
d=json.load(sys.stdin) if not sys.stdin.isatty() else {};
print(d.get("next_eligible") or "")' 2>/dev/null)"
    if [ -n "$next" ]; then
      exec ${pkgs.python3}/bin/python3 "${aqInbox}" wake "$(${pkgs.coreutils}/bin/basename "$next")" \
        --actor owner-manual --timeout ${toString cfg.wakeTimeout}
    fi
  '';
in {
  options.mySystem.aiStack.antigravityAutoWake = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Auto-nudge the running Antigravity IDE when an advisory task is dropped into the watched inbox,
        so the owner never has to manually prompt the IDE to check it. Runs as a per-user systemd path
        unit in the owner's session and fires `aq-antigravity-inbox wake --actor owner-manual` (the only
        permitted actor) — it puppets nothing beyond the owner's own live IDE session. Default-OFF;
        enable while the IDE is open. A wake with no IDE running is a harmless no-op.
      '';
    };
    wakeTimeout = mkOption {
      type = types.ints.between 1 120;
      default = 60;
      description = "Seconds to wait on the `antigravity chat` wake invocation before giving up (1-120).";
    };
    inboxDir = mkOption {
      type = types.str;
      default = "${repoPath}/.agent/collaboration/antigravity-inbox";
      description = "Directory watched for new advisory-task drops.";
    };
  };

  config = mkIf cfg.enable {
    # Oneshot that performs the wake. Rate-limited so a churny inbox can never spin the IDE.
    systemd.user.services.aq-antigravity-auto-wake = {
      description = "Nudge the Antigravity IDE to process a newly-dropped advisory inbox task";
      startLimitIntervalSec = 60;
      startLimitBurst = 6;
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${wakeScript}";
      };
    };
    # Path unit: fire the oneshot whenever the inbox dir changes. The oneshot self-gates on a pending
    # task, so claim/receipt/lane-state churn is filtered out. default.target so it watches whenever the
    # owner is logged in (harmless without an IDE).
    systemd.user.paths.aq-antigravity-auto-wake = {
      description = "Watch the Antigravity advisory inbox for new task drops";
      wantedBy = ["default.target"];
      pathConfig = {
        PathModified = cfg.inboxDir;
        Unit = "aq-antigravity-auto-wake.service";
      };
    };
  };
}
