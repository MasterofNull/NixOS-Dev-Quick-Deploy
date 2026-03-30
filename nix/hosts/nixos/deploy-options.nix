{ lib, config, ... }:
{
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    mySystem.aiStack = {
      switchboard = {
        remoteUrl = lib.mkDefault "https://openrouter.ai/api";
        remoteModelAliases.free = lib.mkDefault "arcee-ai/trinity-large-preview:free";
        remoteModelAliases.coding = lib.mkDefault "qwen/qwen3-coder:free";
        remoteModelAliases.reasoning = lib.mkDefault "nvidia/nemotron-3-super-120b-a12b:free";
        remoteModelAliases.toolCalling = lib.mkDefault "arcee-ai/trinity-large-preview:free";
        remoteBudget.dailyTokenCap = lib.mkDefault 0;
        remoteBudget.fallbackToLocal = lib.mkDefault true;
      };
    };
  };
}
