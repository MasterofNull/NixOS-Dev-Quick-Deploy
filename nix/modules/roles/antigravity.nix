{
  lib,
  config,
  pkgs,
  ...
}:
# ---------------------------------------------------------------------------
# Antigravity Role — Multi-Agent Collaborative Collective integration.
#
# Formalizes the Antigravity IDE (VS Code fork) and its integration with the
# local AI harness as the primary multi-agent orchestration lane.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  ai = cfg.aiStack;
  swb = ai.switchboard;
in {
  options.mySystem.roles.antigravity = {
    enable = lib.mkEnableOption "Antigravity Collective role";
  };

  config = lib.mkIf cfg.roles.antigravity.enable {
    # Ensure Switchboard is configured for the collective.
    mySystem.aiStack.switchboard.enable = true;

    # Use the Antigravity Collective as the default front-door routing lanes.
    mySystem.aiStack.localFrontdoorRouting = {
      defaultProfile = "antigravity-collective";
      explorationProfile = "antigravity-collective";
      planningProfile = "antigravity-collective";
    };

    # Environment variables for Antigravity-aware tools.
    environment.variables = {
      ANTIGRAVITY_COLLECTIVE_ENABLED = "1";
      DEFAULT_AI_PROFILE = "antigravity-collective";
      PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
      PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1";
      CHROMIUM_PATH = "${pkgs.chromium}/bin/chromium";
      CHROME_EXECUTABLE = "${pkgs.chromium}/bin/chromium";
    };

    # Dependencies for the collective.
    environment.systemPackages = with pkgs; [
      # Antigravity IDE is usually installed via Home Manager,
      # but system-level helpers go here.
      nodejs_22
      chromium
      playwright-driver
    ];
  };
}
