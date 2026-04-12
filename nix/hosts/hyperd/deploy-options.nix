{ lib, config, ... }:
{
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    mySystem.aiStack.switchboard = {
      remoteUrl = lib.mkDefault "https://openrouter.ai/api";
      remoteModelAliases.free = lib.mkDefault "qwen/qwen3-next-80b-a3b-instruct:free";
      remoteModelAliases.gemini = lib.mkDefault "qwen/qwen3-next-80b-a3b-instruct:free";
      remoteModelAliases.coding = lib.mkDefault "qwen/qwen3-coder:free";
      remoteModelAliases.reasoning = lib.mkDefault "qwen/qwen3-next-80b-a3b-instruct:free";
      remoteModelAliases.toolCalling = lib.mkDefault "qwen/qwen3-coder:free";
      remoteBudget.dailyTokenCap = lib.mkDefault 0;
      remoteBudget.fallbackToLocal = lib.mkDefault true;
    };
  };
}
