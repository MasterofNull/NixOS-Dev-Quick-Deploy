{ lib, config, ... }:
{
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    mySystem.aiStack.switchboard = {
      remoteUrl = lib.mkForce null;
      # Qwen free tier (qwen3-next-80b-a3b-instruct:free, qwen3-coder:free) removed
      # from OpenRouter as of 2026-05. Aliases updated to currently available free
      # alternatives. These take effect when remoteUrl is re-enabled.
      remoteModelAliases.free = lib.mkDefault "meta-llama/llama-3.3-70b-instruct:free";
      remoteModelAliases.gemini = lib.mkDefault "google/gemini-2.0-flash-exp:free";
      remoteModelAliases.coding = lib.mkDefault "deepseek/deepseek-r1:free";
      remoteModelAliases.reasoning = lib.mkDefault "deepseek/deepseek-r1:free";
      remoteModelAliases.toolCalling = lib.mkDefault "meta-llama/llama-3.3-70b-instruct:free";
      remoteBudget.dailyTokenCap = lib.mkDefault 0;
      remoteBudget.fallbackToLocal = lib.mkDefault true;
    };
  };
}
