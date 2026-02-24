{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Capability Registry — Index Card strategy.
#
# Generates /etc/ai-stack/capabilities.json at build time from the current
# mySystem option values.  Any agent or tool can read this file at runtime to
# discover which AI stack features are enabled without querying systemd.
#
# Activated when mySystem.roles.aiStack.enable = true.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  ai  = cfg.aiStack;
  mcp = cfg.mcpServers;

  caps = {
    backend         = ai.backend;
    inference       = ai.llamaCpp.enable;
    inferencePort   = ai.llamaCpp.port;
    embedding       = ai.embeddingServer.enable;
    embeddingPort   = ai.embeddingServer.port;
    vectorDb        = ai.vectorDb.enable;
    openWebui       = ai.ui.enable;
    mcpServers      = mcp.enable;
    mcpAidbPort     = mcp.aidbPort;
    mcpHybridPort   = mcp.hybridPort;
    mcpRalphPort    = mcp.ralphPort;
    switchboard     = ai.switchboard.enable;
    switchboardPort = ai.switchboard.port;
  };

  capsJson = pkgs.writeText "ai-capabilities.json" (builtins.toJSON caps);
in
{
  config = lib.mkIf cfg.roles.aiStack.enable {
    environment.etc."ai-stack/capabilities.json" = {
      source = capsJson;
      mode   = "0644";
    };
  };
}
