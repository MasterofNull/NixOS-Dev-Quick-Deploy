{
  lib,
  config,
  ...
}: {
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    mySystem.aiStack.switchboard = {
      # Remote lane = Google Gemini direct (OpenAI-compatible endpoint).
      # The "antigravity" delegation name reflects Google's Gemini agentic
      # product; routing to Gemini makes the name match the backend.
      # The API key is in SOPS: remote_llm_api_key → /run/secrets/remote_llm_api_key
      # (must hold a Google AI Studio API key, NOT an OpenRouter key).
      remoteUrl = lib.mkForce "https://generativelanguage.googleapis.com/v1beta/openai";
      # Google's endpoint serves ONLY gemini-* models — every alias must be a
      # bare Gemini model name (no "google/", "anthropic/", "openai/" prefixes;
      # those are OpenRouter-isms and 404 against generativelanguage.googleapis.com).
      # Tiering: pro = higher-judgment (reasoning/coding); flash = fast tool use;
      # flash-lite = cheapest fallback.
      remoteModelAliases.coding = lib.mkForce "gemini-2.5-pro";
      remoteModelAliases.reasoning = lib.mkForce "gemini-2.5-pro";
      remoteModelAliases.toolCalling = lib.mkForce "gemini-2.5-flash";
      remoteModelAliases.free = lib.mkForce "gemini-2.5-flash-lite";
      remoteModelAliases.opencode = lib.mkForce "gemini-2.5-flash";
      remoteModelAliases.gemini = lib.mkForce "gemini-2.5-flash";
      remoteBudget.dailyTokenCap = lib.mkDefault 0;
      remoteBudget.fallbackToLocal = lib.mkDefault true;
    };
  };
}
