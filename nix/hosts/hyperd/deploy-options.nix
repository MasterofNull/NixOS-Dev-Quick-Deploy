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
      # Google Gemini direct via the antigravity wrapper. Every alias is a bare
      # valid Gemini id (no "google/"/"anthropic/"/"openai/" prefixes — those are
      # OpenRouter-isms and 404 against generativelanguage.googleapis.com).
      # LATEST ids: gemini-3.1-pro (reasoning/coding), gemini-3.5-flash
      # (efficiency/speed/agentic loops), gemini-3.1-flash-lite (cost-sensitive).
      # Baseline fallback: gemini-2.5-{pro,flash,flash-lite} (Vertex adds -001).
      # Tiering mirrors config/model-coordinator.json tiers.google.
      # Effort = thinking_level preset (minimal|low|medium|high) or thinking_budget
      # int; the /v1beta/openai endpoint does NOT support reasoning_effort —
      # switchboard must pass thinking_config (see switchboard-thinking-budget-injection).
      remoteModelAliases.coding = lib.mkForce "gemini-3.1-pro";
      remoteModelAliases.reasoning = lib.mkForce "gemini-3.1-pro";
      remoteModelAliases.toolCalling = lib.mkForce "gemini-3.5-flash";
      remoteModelAliases.free = lib.mkForce "gemini-3.1-flash-lite";
      remoteModelAliases.opencode = lib.mkForce "gemini-3.5-flash";
      remoteModelAliases.gemini = lib.mkForce "gemini-3.5-flash";
      remoteBudget.dailyTokenCap = lib.mkDefault 0;
      remoteBudget.fallbackToLocal = lib.mkDefault true;
    };
  };
}
