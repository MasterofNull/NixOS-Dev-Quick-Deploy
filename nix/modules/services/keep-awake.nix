# Opt-in lid-closed keep-awake watcher for delegated tasks (see scripts/ai/aq-keep-awake).
# Default-OFF. Enabling the service only starts the watcher; it still does nothing until the
# user runs `aq-keep-awake on` (state file), so manual/lid sleep stays normal by default.
{
  lib,
  config,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.keepAwake;
  repoPath = config.mySystem.mcpServers.repoPath;
in {
  options.mySystem.aiStack.keepAwake.enable = mkOption {
    type = types.bool;
    default = false;
    description = "Run the aq-keep-awake watcher as a user service (opt-in per session via `aq-keep-awake on`).";
  };

  config = mkIf cfg.enable {
    systemd.user.services.aq-keep-awake = {
      description = "Hold lid-switch/sleep inhibitor while delegated tasks run (opt-in, guarded)";
      wantedBy = ["default.target"];
      path = [pkgs.systemd pkgs.coreutils];
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python3 ${repoPath}/scripts/ai/aq-keep-awake watch --interval 30";
        Restart = "on-failure";
        RestartSec = "10s";
      };
    };
  };
}
