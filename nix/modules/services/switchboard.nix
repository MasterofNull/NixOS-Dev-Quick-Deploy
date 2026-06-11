{
  lib,
  config,
  pkgs,
  ...
}:
# ---------------------------------------------------------------------------
# Switchboard — local/remote LLM routing proxy (Switchboard strategy).
#
# Provides an OpenAI-compatible endpoint on ai.switchboard.port (:8085) that
# routes requests to local llama.cpp and/or a remote OpenAI-compatible API.
#
# Activated when:
#   mySystem.roles.aiStack.enable = true
#   mySystem.aiStack.switchboard.enable = true
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  ai = cfg.aiStack;
  swb = ai.switchboard;
  sec = cfg.secrets;
  mcp = cfg.mcpServers;
  # Phase 164 Stage C: when headroom proxy is enabled, route completions through
  # headroom (:8787) which compresses payloads before forwarding to llama.cpp.
  llamaUrl =
    if ai.headroomProxy.enable
    then "http://127.0.0.1:${toString ai.headroomProxy.port}"
    else "http://${ai.llamaCpp.host}:${toString ai.llamaCpp.port}";
  embeddingUrl =
    if ai.embeddingServer.enable
    then "http://${ai.llamaCpp.host}:${toString ai.embeddingServer.port}"
    else "";
  remoteUrl =
    if swb.remoteUrl != null
    then swb.remoteUrl
    else "";
  remoteEnabled = remoteUrl != "";
  remoteKeyFile =
    if swb.remoteApiKeyFile != null
    then swb.remoteApiKeyFile
    else if sec.enable && remoteEnabled
    then "/run/secrets/${sec.names.remoteLlmApiKey}"
    else "";
  hybridUrl = "http://127.0.0.1:${toString mcp.hybridPort}";
  hybridKeyFile =
    if sec.enable
    then "/run/secrets/${sec.names.hybridApiKey}"
    else "";
  mutableOptimizerDir = cfg.deployment.mutableSpaces.aiStackOptimizerDir;
  repoPath = cfg.mcpServers.repoPath;
  localAgentStateDir = "/home/${cfg.primaryUser}/.local/share/nixos-ai-stack/local-agents";
  remoteBudgetStatePath = "${mutableOptimizerDir}/switchboard-remote-budget.json";
  defaultProfileCard = ''
    /no_think
    [profile-card:default]
    You are AQ, an expert coding and systems developer. You are proficient in NixOS and grounded in the NixOS-Dev-Quick-Deploy harness.

    MANDATORY: Show your work with proof (als, agrep, read_file) and CHECK-IN with a plan before acting.

    === COMMON TASKS ===
    PRSI / Optimization: run: scripts/automation/prsi-orchestrator.py list
    Service Health: run: aq-qa 0
    Search Code: run: agrep "<keyword>" . --include="*.py"
    Knowledge: run: query_aidb {query: "<q>"}

    Key dirs: scripts/ai/, scripts/agent-tools/, ai-stack/mcp-servers/, nix/modules/, dashboard/, config/
    Ports: llama:8080 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dashboard:8889
  '';
  # Compact card: ~50 tokens (~8 s prompt on Qwen3.6-35B w/ 12 GPU layers).
  # Previous 874-char / ~218-token card added ~37 s of prompt-processing latency,
  # causing smoke tests to time out on this hardware. Trim to essentials only.
  continueLocalCard = ''
    /no_think
    [profile-card:continue-local]
    Concise. als/agrep first — never browse blindly. Act, don't restate.
    PRSI: /var/lib/nixos-ai-stack/prsi/action-queue.json | aq-hints "<q>" | aq-qa 0
  '';
  harnessAwareBody = ''
    You are AQ, an expert coding and systems developer embedded in the NixOS-Dev-Quick-Deploy harness. You are proficient in NixOS and autonomous AI orchestration.

    === OPERATIONAL GUIDELINES ===
    - CHECK-IN FIRST: Before making system changes, show your research and proposed plan with proof (file reads, command outputs).
    - EVIDENCE-BASED: Ground every answer in the actual system state using tools.
    - NIXOS MASTERY: Apply best practices for NixOS, Flakes, and declarative configuration.
    - PRECISION: Never guess; search and verify first.

    === TASK → FIRST ACTIONS ===
    PRSI / Self-Improvement:
      MCP tool: get_prsi_pending -> then prsi_orchestrate {action: "approve", ...}
      Approval flow: Proposed Plan -> User Check-in -> Execute (dry_run=true first)

    Service Health:
      MCP tool: harness_health -> then journalctl -u ai-*.service -n 50 --no-pager

    Knowledge Retrieval:
      MCP tool: query_aidb {query: "<question>"} (vector search)
      MCP tool: get_hint {query: "<task summary>"} (pattern lookup)

    Project Exploration:
      1. Use als -d 1 or search_files for orientation.
      2. Use read_file (or acat) to provide proof of current state.

    === COMMIT RULES ===
    git add <specific files> && scripts/governance/tier0-validation-gate.sh --pre-commit && git commit -m "type(scope): msg\n\nCo-Authored-By: AQ <noreply@harness.local>"
  '';
  localAgentCard = ''
    /no_think
    [profile-card:local-agent]
    ${harnessAwareBody}
  '';
  remoteDefaultCard = ''
    [profile-card:remote-default]
    Optimize for token efficiency.
    Use brief answers first, expand only when requested.
    Avoid restating long policy docs unless explicitly asked.
  '';
  remoteGeminiCard = ''
    [profile-card:remote-gemini]
    Use Gemini as the front-door remote orchestration lane for discovery, planning, and synthesis.
    ${harnessAwareBody}
    Keep the output handoff-ready and explicitly trigger local tools, embeddings, or local models when they should take over.
  '';
  remoteFreeCard = ''
    [profile-card:remote-free]
    Use low-cost or free remote capacity for probing, not for unrestricted context bloat.
    Keep prompts compact and prefer retrieval before raising token spend.
  '';
  remoteCodingCard = ''
    [profile-card:remote-coding]
    Use the configured coding-optimized remote model for concrete implementation help.
    Keep file scope explicit and avoid broad background dumps.
  '';
  remoteReasoningCard = ''
    [profile-card:remote-reasoning]
    Use the configured higher-judgment remote model for architecture, policy, and tradeoff work.
    Spend tokens intentionally and only after scoping the decision clearly.
  '';
  remoteToolCallingCard = ''
    [profile-card:remote-tool-calling]
    Use the configured remote tool-calling lane for bounded tool use with strict arguments.
    Prefer minimal tool schemas, explicit constraints, and concise final output.
  '';
  remoteOpencodeCard = ''
    [profile-card:remote-opencode]
    Use the opencode coding-agent lane backed by a free or low-cost remote model.
    Route concrete file-editing, refactoring, and code-generation tasks here to preserve
    paid-tier budget. Keep prompts scoped to a single file or function; do not dump broad context.
  '';
  localToolCallingCard = ''
    [profile-card:local-tool-calling]
    Use the local tool-calling lane for bounded built-in tool execution on the local host.
    The runtime leases a small active tool set; use the leased tools for evidence, then synthesize.
    For broad analysis, gather only the strongest 2-4 evidence points before answering.
    Use lease_tools to swap to a different active bundle when the current leased tools are the wrong fit.
    Preserve strict tool schemas, prefer concise execution, and surface tool failures explicitly.
    CRITICAL: Issue the tool call directly — do not announce it, do not self-correct, do not loop.
  '';
  embeddingLocalCard = ''
    [profile-card:embedding-local]
    Embeddings profile: retrieval/ranking only, not chat reasoning.
    Prioritize progressive disclosure by selecting only relevant chunks.
  '';
  embeddedAssistCard = ''
    /no_think
    [profile-card:embedded-assist]
    Use compact reasoning and progressive disclosure.
    Prefer hybrid retrieval (semantic + lexical), then ask for clarification on low confidence.
    Do not expand full policy docs unless explicitly requested.
    CRITICAL: Act immediately on each turn. Never repeat a stated intention more than once — if you said you will do something, do it now.
    SEARCH-FIRST RULE: Before answering any question about project files, services, or code — run a als or agrep lookup. Never say "I see the project structure, what would you like to do?" — search, read, then act.
    Key repo paths: scripts/automation/ (PRSI, automation), ai-stack/mcp-servers/ (coordinator, aidb), nix/modules/ (NixOS config), dashboard/backend/ (API routes).
  '';
  localCodingCard = ''
    /no_think
    [profile-card:local-coding]
    You are a precision coding agent on constrained APU hardware. Code accuracy is the primary goal.

    === CODING RULES (non-negotiable) ===
    - frequency_penalty=0.0 ALWAYS for any structured/JSON/code output (penalty causes premature EOS)
    - Validate every code block: Python → py_compile, Bash → bash -n, Nix → nix-instantiate --parse
    - Read the file before editing. Never guess at file contents.
    - One file change per tool call. Verify after each write.
    - NEVER hardcode ports/URLs — read from env vars or options.nix.

    === CONTEXT PRE-FETCH (do first) ===
    1. hybrid_search "skill <task-keyword>" in skills-patterns collection → load relevant SKILL.md (max 2)
    2. hybrid_search "<error or pattern>" in error-solutions collection if debugging
    3. als/agrep to verify file paths before reading

    === OUTPUT FORMAT ===
    - Code blocks with language tag. No prose filler before the code.
    - For NixOS: alejandra-formatted, deadnix-clean.
    - For Python: type-annotated signatures, no blocking I/O in async handlers.
    - For commits: type(scope): description + Co-Authored-By line.

    === EMBEDDED ASSIST INTEGRATION ===
    This profile receives pre-fetched context from embedded-assist (skills, patterns, recent errors).
    Use the injected context — it is already filtered for relevance. Do not re-fetch unless context is missing.
  '';
  switchboardProfileDefaults = {
    default = {
      forceProvider = null;
      injectHints = true;
      modelAlias = null;
      advertisedContextWindow = ai.llamaCpp.ctxSize;
      # Guard untagged callers (Codex CLI, Claude Code extension, etc.) against
      # unbounded context that exceeds the llama.cpp per-request timeout.
      maxInputTokens = 1500;
      maxMessages = 12;
      maxOutputTokens = 768;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = defaultProfileCard;
    };
    "continue-local" = {
      forceProvider = "local";
      injectHints = false;
      modelAlias = null;
      advertisedContextWindow = ai.llamaCpp.ctxSize;
      maxInputTokens = swb.continueLocal.maxInputTokens;
      maxMessages = swb.continueLocal.maxMessages;
      maxOutputTokens = 768;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = continueLocalCard;
    };
    "local-agent" = {
      forceProvider = "local";
      injectHints = true;
      modelAlias = null;
      advertisedContextWindow = ai.llamaCpp.ctxSize;
      maxInputTokens = 8000;
      maxMessages = 16;
      maxOutputTokens = 4096;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = localAgentCard;
    };
    # Coding-optimised local profile: larger output budget, code-accuracy system prompt,
    # and embedded-assist pre-context injection (handled by ai_coordinator_handlers.py).
    "local-coding" = {
      forceProvider = "local";
      injectHints = true;
      modelAlias = null;
      advertisedContextWindow = ai.llamaCpp.ctxSize;
      maxInputTokens = 5500;
      maxMessages = 12;
      maxOutputTokens = 2048;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = localCodingCard;
    };
    "remote-default" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias = null;
      advertisedContextWindow = null;
      maxInputTokens = 3500;
      maxMessages = 16;
      maxOutputTokens = 2048;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = remoteDefaultCard;
    };
    "remote-gemini" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias =
        if swb.remoteModelAliases.gemini != null
        then swb.remoteModelAliases.gemini
        else swb.remoteModelAliases.free;
      advertisedContextWindow = null;
      maxInputTokens = 3500;
      maxMessages = 16;
      maxOutputTokens = 1400;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = remoteGeminiCard;
    };
    "remote-free" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias = swb.remoteModelAliases.free;
      advertisedContextWindow = null;
      maxInputTokens = 3500;
      maxMessages = 16;
      maxOutputTokens = 1200;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = remoteFreeCard;
    };
    "remote-coding" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias = swb.remoteModelAliases.coding;
      advertisedContextWindow = null;
      maxInputTokens = 5000;
      maxMessages = 20;
      maxOutputTokens = 1800;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = remoteCodingCard;
    };
    "remote-reasoning" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias = swb.remoteModelAliases.reasoning;
      advertisedContextWindow = null;
      maxInputTokens = 6000;
      maxMessages = 20;
      maxOutputTokens = 1800;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = remoteReasoningCard;
    };
    "remote-tool-calling" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias = swb.remoteModelAliases.toolCalling;
      advertisedContextWindow = null;
      maxInputTokens = 3500;
      maxMessages = 16;
      maxOutputTokens = 900;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = remoteToolCallingCard;
    };
    "remote-opencode" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias =
        if swb.remoteModelAliases.opencode != null
        then swb.remoteModelAliases.opencode
        else swb.remoteModelAliases.free;
      advertisedContextWindow = null;
      maxInputTokens = 5000;
      maxMessages = 20;
      maxOutputTokens = 2000;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = remoteOpencodeCard;
    };
    "local-tool-calling" = {
      forceProvider = "local";
      injectHints = false;
      modelAlias = null;
      advertisedContextWindow = ai.llamaCpp.ctxSize;
      maxInputTokens = 12000;
      maxMessages = 20;
      maxOutputTokens = 2048;
      embeddingsOnly = false;
      toolExecution = "built-in";
      profileCard = localToolCallingCard;
    };
    "embedding-local" = {
      forceProvider = "local";
      injectHints = false;
      modelAlias = null;
      advertisedContextWindow = 512;
      maxInputTokens = 512;
      maxMessages = 8;
      maxOutputTokens = 256;
      embeddingsOnly = true;
      toolExecution = null;
      profileCard = embeddingLocalCard;
    };
    "embedded-assist" = {
      forceProvider = "local";
      injectHints = false;
      modelAlias = null;
      advertisedContextWindow = ai.llamaCpp.ctxSize;
      maxInputTokens = 1800;
      maxMessages = 10;
      maxOutputTokens = 512;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = embeddedAssistCard;
    };
    # Internal profile for coordinator-originated LLM calls.
    # Disables hint injection to break the circular hints loop:
    # coordinator → switchboard(default) → coordinator(GET /hints) → circular.
    # No profile card, no loop detection — coordinator manages its own context.
    "coordinator-internal" = {
      forceProvider = "local";
      injectHints = false;
      modelAlias = null;
      advertisedContextWindow = ai.llamaCpp.ctxSize;
      maxInputTokens = 8000;
      maxMessages = 20;
      maxOutputTokens = 4096;
      embeddingsOnly = false;
      toolExecution = null;
      profileCard = "";
    };
  };
  configuredSwitchboardProfiles = swb.profiles;
  switchboardProfileCatalog =
    switchboardProfileDefaults
    // lib.mapAttrs
    (name: value:
      (
        if builtins.hasAttr name switchboardProfileDefaults
        then switchboardProfileDefaults.${name}
        else {}
      )
      // value)
    configuredSwitchboardProfiles;
  switchboardProfileCatalogJson = builtins.toJSON switchboardProfileCatalog;
  switchboardProfileCatalogFile = pkgs.writeText "ai-switchboard-profile-catalog.json" switchboardProfileCatalogJson;

  switchboardPy = pkgs.python3.withPackages (ps:
    with ps; [
      fastapi
      uvicorn
      httpx
      pyyaml
    ]);
in {
  config = lib.mkIf (cfg.roles.aiStack.enable && swb.enable) {
    systemd.services.ai-switchboard = {
      description = "AI Switchboard — local/remote LLM routing proxy";
      wantedBy = ["multi-user.target" "ai-stack.target"];
      partOf = ["ai-stack.target"];
      after = ["network-online.target" "ai-stack.target"];
      wants = ["network-online.target"];
      unitConfig = {
        StartLimitIntervalSec = "300";
        StartLimitBurst = 5;
      };
      serviceConfig = {
        ExecStart = lib.escapeShellArgs [
          "${switchboardPy}/bin/python3"
          "${repoPath}/ai-stack/switchboard/switchboard.py"
        ];
        Environment = [
          "PORT=${toString swb.port}"
          "HOST=127.0.0.1"
          "LLAMA_CPP_URL=${llamaUrl}"
          "LLAMA_CPP_INFERENCE_TIMEOUT_SECONDS=600.0"
          "LLAMA_CTX_SIZE=${toString ai.llamaCpp.ctxSize}"
          "EMBEDDING_URL=${embeddingUrl}"
          "ROUTING_MODE=${swb.routingMode}"
          "DEFAULT_PROVIDER=${swb.defaultProvider}"
          "REMOTE_LLM_URL=${remoteUrl}"
          "REMOTE_LLM_API_KEY_FILE=${remoteKeyFile}"
          "SWB_REMOTE_MODEL_ALIAS_GEMINI=${
            if swb.remoteModelAliases.gemini != null
            then swb.remoteModelAliases.gemini
            else if swb.remoteModelAliases.free != null
            then swb.remoteModelAliases.free
            else ""
          }"
          "SWB_REMOTE_MODEL_ALIASES_ENABLED=${
            if swb.remoteModelAliases.enable
            then "1"
            else "0"
          }"
          "SWB_REMOTE_MODEL_ALIAS_FREE=${
            if swb.remoteModelAliases.free != null
            then swb.remoteModelAliases.free
            else ""
          }"
          "SWB_REMOTE_MODEL_ALIAS_CODING=${
            if swb.remoteModelAliases.coding != null
            then swb.remoteModelAliases.coding
            else ""
          }"
          "SWB_REMOTE_MODEL_ALIAS_REASONING=${
            if swb.remoteModelAliases.reasoning != null
            then swb.remoteModelAliases.reasoning
            else ""
          }"
          "SWB_REMOTE_MODEL_ALIAS_TOOL_CALLING=${
            if swb.remoteModelAliases.toolCalling != null
            then swb.remoteModelAliases.toolCalling
            else ""
          }"
          "SWB_REMOTE_MODEL_ALIAS_OPENCODE=${
            if swb.remoteModelAliases.opencode != null
            then swb.remoteModelAliases.opencode
            else ""
          }"
          "SWB_REMOTE_DAILY_TOKEN_CAP=${toString swb.remoteBudget.dailyTokenCap}"
          "SWB_REMOTE_BUDGET_FALLBACK_LOCAL=${
            if swb.remoteBudget.fallbackToLocal
            then "1"
            else "0"
          }"
          "SWB_REMOTE_BUDGET_STATE_PATH=${remoteBudgetStatePath}"
          "SWB_CONTINUE_LOCAL_MAX_INPUT_TOKENS=${toString swb.continueLocal.maxInputTokens}"
          "SWB_CONTINUE_LOCAL_MAX_MESSAGES=${toString swb.continueLocal.maxMessages}"
          # Must match --parallel N in facts.nix llamaCpp.extraArgs so the
          # switchboard concurrency ceiling matches llama.cpp's slot count.
          "SWB_LOCAL_CONCURRENCY=${toString swb.localConcurrency}"
          "SWB_RESERVED_SLOTS=${toString swb.reservedSlots}"
          "SWB_LOCAL_TOOL_CALL_LIMIT=16"
          "SWB_ACTIVE_TOOL_SCHEMA_LIMIT=7"
          "SWB_TOOL_WORKING_SET_ENABLED=1"
          "SWB_REMOTE_TOOL_WORKING_SET_ENABLED=1"
          "SWB_CONTEXT_OUTPUT_GC_ENABLED=1"
          "SWB_CONTEXT_OUTPUT_GC_MIN_CHARS=2400"
          "SWB_CONTEXT_OUTPUT_GC_SUMMARY_CHARS=900"
          "SWB_CONTEXT_ARTIFACT_DIR=${localAgentStateDir}/switchboard-artifacts"
          "SWB_TOOL_RESULT_DEDUPE_ENABLED=1"
          "SWB_PROFILE_CATALOG_YAML_FILE=${repoPath}/config/switchboard-profiles.yaml"
          "SWB_PROFILE_CATALOG_JSON_FILE=${switchboardProfileCatalogFile}"
          "HYBRID_COORDINATOR_URL=${hybridUrl}"
          "HYBRID_URL=${hybridUrl}"
          "HYBRID_API_KEY_FILE=${hybridKeyFile}"
          "LOCAL_AGENTS_PATH=${repoPath}/ai-stack/local-agents"
          "REPO_PATH=${repoPath}"
        ];
        EnvironmentFile = "-${mutableOptimizerDir}/overrides.env";
        User = cfg.primaryUser;
        WorkingDirectory = repoPath;
        Restart = "on-failure";
        RestartSec = "5s";
        TimeoutStopSec = "15s";
        KillMode = "mixed";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        ReadOnlyPaths = [repoPath];
        ReadWritePaths = [localAgentStateDir "${repoPath}/.agents/telemetry"];
        PrivateTmp = true;
        CapabilityBoundingSet = "";
        RestrictSUIDSGID = true;
        LockPersonality = true;
        RestrictNamespaces = true;
      };
    };

    networking.firewall.allowedTCPPorts =
      lib.mkIf ai.listenOnLan [swb.port];
  };
}
