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
  llamaUrl = "http://${ai.llamaCpp.host}:${toString ai.llamaCpp.port}";
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
    You are a NixOS AI harness agent for the NixOS-Dev-Quick-Deploy repo. You are in AGENT MODE. The task is already given — execute immediately. Do NOT say "what would you like to do?" or run `ls` on the root as a first action — those are failure modes.
    MANDATORY: Use targeted agrep/als/read for the task, not a generic directory listing.
    PRSI task → run: python3 scripts/automation/prsi-orchestrator.py list  THEN  read /var/lib/nixos-ai-stack/prsi/action-queue.json
    Service/health task → run: aq-qa 0  THEN  journalctl -u ai-*.service -n 30 --no-pager
    Code/file task → run: agrep "<keyword>" . --include="*.py"
    Key dirs: scripts/ai/ (aq-*), scripts/agent-tools/ (als/agrep/acat/asum), scripts/automation/ (prsi-orchestrator.py), ai-stack/mcp-servers/, nix/modules/, dashboard/, config/
    PRSI queue: /var/lib/nixos-ai-stack/prsi/action-queue.json
    Ports: llama:8080 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dashboard:8889
    Harness: aq-prime | aq-qa 0 | aq-report | aq-operational-perspective | aq-hints "<task>" | aq-context-bootstrap --task "<task>"
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
    You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy. You are in AGENT MODE. The task is already given — BEGIN EXECUTING IMMEDIATELY. Do not ask "how can I help?" or "what would you like to do?" — those are failure modes.

    RULE: Never run `ls` on the repo root as a first action. Always start with the most targeted command for the task type below.

    === TASK → FIRST ACTIONS ===
    PRSI / self-improvement / queue issues:
      MCP tool (preferred): get_prsi_pending  → then prsi_orchestrate {command:"approve",...}
      Shell fallback: python3 scripts/automation/prsi-orchestrator.py list
      Approval flow: prsi_orchestrate approve → prsi_orchestrate execute

    Service health / errors:
      MCP tool (preferred): harness_health  → then journalctl -u ai-*.service -n 50 --no-pager
      Shell fallback: aq-qa 0

    Unknown file / code location:
      1. run: als -d 1 (if broad orientation needed) OR agrep "<keyword>" . --include="*.py" (targeted search, NOT ls)
      2. read the file identified with acat or read_file

    Harness workflow / hints:
      MCP tool (preferred): get_hints {q:"<task summary>"}
      Shell fallback: aq-hints "<task summary>"

    Knowledge search:
      MCP tool: hybrid_search {query:"<question>"}
      MCP tool: query_aidb {query:"<question>"}

    Agent introspection / operator perspective:
      1. Gather bounded evidence first:
         aq-feedback-loop --task "<prompt>" --format json
         aq-context-bootstrap --task "<prompt>" --format json
         aq-context-manage summary --task "<prompt>" --json
         MCP tools: get_hints {q:"<prompt>"}, harness_health, get_working_memory, query_aidb
      2. Use shell fallback only if needed:
         aq-report --format=json
         aq-operational-perspective --task "<prompt>" --format json
         aq-qa 0 --json
         aq-memory search "<topic>" --project ai-stack --limit 5
      3. If the bootstrap or feedback loop selects context-offload:
         execute sanctioned aq-* preflight_commands or continuation_startup_commands before answering
         prefer embedded-assist as the compact search/context helper lane before broader local or remote synthesis
      4. Structure the answer with:
         Observed signals
         Inferred constraints
         Evidence sources
         Unknowns / next checks
      5. Use `aq-introspection-validate --file <response-file>` or `--text <response>` when you need to verify the answer still satisfies the evidence contract.
      6. Never claim internal behavior, memory writes, or remote-sync behavior as fact unless a tool result supports it.

    === KEY PATHS ===
    PRSI queue: /var/lib/nixos-ai-stack/prsi/action-queue.json
    PRSI policy: config/runtime-prsi-policy.json
    PRSI orchestrator: scripts/automation/prsi-orchestrator.py
    Harness CLIs: scripts/ai/ (aq-qa, aq-report, aq-operational-perspective, aq-hints, aq-system-act, aq-context-bootstrap, aq-runtime-diagnose)
    Agentic Tools: scripts/agent-tools/ (als, agrep, acat, asum)
    MCP servers: ai-stack/mcp-servers/ (coordinator:8003, aidb:8002, ralph:8004)
    NixOS modules: nix/modules/ | Dashboard: dashboard/backend/

    === PORTS ===
    llama:8080 embed:8081 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dash:8889 grafana:3000 prom:9090 owui:3001

    === CANONICAL WORKFLOW (full contract: .agent/WORKFLOW-CANON.md) ===
    Every non-trivial task: ORIENT(aq-prime+aq-hints+recall-memory) → RESEARCH(agrep/als/acat/asum+web-search) → PRD/PLAN(.agent/+.agents/plans/) → MEMORY-CHECKPOINT(store plan before coding) → EXECUTE(one-slice,read-before-edit) → VALIDATE(tier0-gate+security) → COMMIT(atomic+Co-Authored-By).
    PRD gate: write .agent/PROJECT-<NAME>-PRD.md before any multi-file implementation.
    Memory gate: store plan to harness memory before executing. At session start: recall memory first.
    Context rule: reference files by path; retrieve with hybrid_search/get_hints; do not paste full files.

    === SECURITY (OWASP Agentic Top 10) ===
    Before every commit: (1) no hardcoded secrets/ports/tokens; (2) verify all new deps exist; (3) no injection patterns (SQL/shell/path-traversal); (4) treat LLM outputs as untrusted; (5) if auth added, verify it is wired in; (6) bash -n on shell files, py_compile on Python; (7) privilege minimization.

    === COMMIT ===
    git add <specific files> && scripts/governance/tier0-validation-gate.sh --pre-commit && git commit -m "type(scope): msg\n\nCo-Authored-By: <active-agent-name> <noreply@harness.local>"
    Never use --no-verify. One slice = one commit. Include validation evidence in body.
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
    "remote-default" = {
      forceProvider = "remote";
      injectHints = false;
      modelAlias = null;
      advertisedContextWindow = null;
      maxInputTokens = 3500;
      maxMessages = 16;
      maxOutputTokens = 1024;
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
      maxInputTokens = 2400;
      maxMessages = 12;
      maxOutputTokens = 768;
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
          "SWB_LOCAL_CONCURRENCY=1"
          "SWB_TOOL_WORKING_SET_ENABLED=1"
          "SWB_REMOTE_TOOL_WORKING_SET_ENABLED=1"
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
        ReadWritePaths = [localAgentStateDir];
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
