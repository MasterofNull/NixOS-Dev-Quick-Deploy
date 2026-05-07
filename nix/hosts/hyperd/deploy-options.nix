{ lib, config, ... }:
{
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    mySystem.aiStack.switchboard = {
      remoteUrl = lib.mkForce "https://openrouter.ai/api/v1";
      # Delegation priority: Claude (paid) → o4-mini/Codex (paid) → free fallbacks.
      # The API key is in SOPS: remote_llm_api_key → /run/secrets/remote_llm_api_key
      remoteModelAliases.coding = lib.mkForce "anthropic/claude-sonnet-4-5";
      remoteModelAliases.reasoning = lib.mkForce "anthropic/claude-sonnet-4-5";
      remoteModelAliases.toolCalling = lib.mkForce "openai/o4-mini";
      remoteModelAliases.free = lib.mkDefault "meta-llama/llama-3.3-70b-instruct:free";
      remoteModelAliases.gemini = lib.mkDefault "google/gemini-2.0-flash-exp:free";
      remoteBudget.dailyTokenCap = lib.mkDefault 0;
      remoteBudget.fallbackToLocal = lib.mkDefault true;
    };
  };
}
