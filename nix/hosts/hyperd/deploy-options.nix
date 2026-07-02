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
      # Gemini 3.x via the antigravity wrapper. Every alias is a bare Gemini
      # model name (no "google/"/"anthropic/"/"openai/" prefixes — those are
      # OpenRouter-isms and 404 against the Gemini backend). Tiering mirrors
      # config/model-coordinator.json tiers.google:
      #   3.1-pro   = higher-judgment (reasoning/coding, complex/critical)
      #   flash-3.5 = default lane + fast tool use
      # CONFIRM exact id strings + effort mechanism (reasoning_effort param vs
      # id suffix) before nixos-rebuild — these are post-cutoff model names.
      remoteModelAliases.coding = lib.mkForce "gemini-3.1-pro";
      remoteModelAliases.reasoning = lib.mkForce "gemini-3.1-pro";
      remoteModelAliases.toolCalling = lib.mkForce "gemini-flash-3.5";
      remoteModelAliases.free = lib.mkForce "gemini-flash-3.5";
      remoteModelAliases.opencode = lib.mkForce "gemini-flash-3.5";
      remoteModelAliases.gemini = lib.mkForce "gemini-flash-3.5";
      remoteBudget.dailyTokenCap = lib.mkDefault 0;
      remoteBudget.fallbackToLocal = lib.mkDefault true;
    };
  };
}
