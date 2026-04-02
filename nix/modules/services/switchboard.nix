{ lib, config, pkgs, ... }:
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
  cfg      = config.mySystem;
  ai       = cfg.aiStack;
  swb      = ai.switchboard;
  sec      = cfg.secrets;
  mcp      = cfg.mcpServers;
  llamaUrl = "http://${ai.llamaCpp.host}:${toString ai.llamaCpp.port}";
  embeddingUrl = if ai.embeddingServer.enable
    then "http://${ai.llamaCpp.host}:${toString ai.embeddingServer.port}"
    else "";
  remoteUrl = if swb.remoteUrl != null then swb.remoteUrl else "";
  remoteEnabled = remoteUrl != "";
  remoteKeyFile =
    if swb.remoteApiKeyFile != null then swb.remoteApiKeyFile
    else if sec.enable && remoteEnabled then "/run/secrets/${sec.names.remoteLlmApiKey}"
    else "";
  hybridUrl = "http://127.0.0.1:${toString mcp.hybridPort}";
  hybridKeyFile = if sec.enable
    then "/run/secrets/${sec.names.hybridApiKey}"
    else "";
  mutableOptimizerDir = cfg.deployment.mutableSpaces.aiStackOptimizerDir;
  repoPath = cfg.mcpServers.repoPath;
  remoteBudgetStatePath = "${mutableOptimizerDir}/switchboard-remote-budget.json";
  continueLocalCard = ''
    [profile-card:continue-local]
    Keep responses concise and execution-focused.
    Do not request full repository policy text unless user asks.
    Prefer minimal context and recent turns for quick chat stability.
  '';
  remoteDefaultCard = ''
    [profile-card:remote-default]
    Optimize for token efficiency.
    Use brief answers first, expand only when requested.
    Avoid restating long policy docs unless explicitly asked.
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
  localToolCallingCard = ''
    [profile-card:local-tool-calling]
    Use the local tool-calling lane for bounded built-in tool execution on the local host.
    Preserve strict tool schemas, prefer concise execution, and surface tool failures explicitly.
  '';
  embeddingLocalCard = ''
    [profile-card:embedding-local]
    Embeddings profile: retrieval/ranking only, not chat reasoning.
    Prioritize progressive disclosure by selecting only relevant chunks.
  '';

  switchboardPy = pkgs.python3.withPackages (ps: with ps; [
    fastapi
    uvicorn
    httpx
  ]);

  switchboardScript = pkgs.writeText "ai-switchboard.py" ''
    #!/usr/bin/env python3
    """AI Switchboard — OpenAI-compatible LLM routing proxy."""
    import hashlib
    import os
    import json
    import re
    import sys
    import time
    from urllib.parse import urlparse

    import httpx
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response, StreamingResponse

    LLAMA_URL  = os.environ.get("LLAMA_CPP_URL", "${llamaUrl}").rstrip("/")
    EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "${embeddingUrl}").rstrip("/")
    REMOTE_URL = os.environ.get("REMOTE_LLM_URL", "").rstrip("/")
    ROUTING_MODE = os.environ.get("ROUTING_MODE", "auto").strip().lower()
    DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "local").strip().lower()
    REMOTE_API_KEY = os.environ.get("REMOTE_LLM_API_KEY", "").strip()
    REMOTE_API_KEY_FILE = os.environ.get("REMOTE_LLM_API_KEY_FILE", "").strip()
    PORT       = int(os.environ.get("PORT", "${toString swb.port}"))
    HOST       = os.environ.get("HOST", "127.0.0.1")
    ROUTE_HINT_HEADER = "x-ai-route"
    PROVIDER_HINT_HEADER = "x-ai-provider"
    PROFILE_HINT_HEADER = "x-ai-profile"
    REMOTE_MODEL_PREFIXES = (
        "remote/",
        "openai/",
        "anthropic/",
        "openrouter/",
        "custom/",
    )
    HYBRID_URL      = os.environ.get("HYBRID_URL", "").rstrip("/")
    HINTS_INJECT    = os.environ.get("HINTS_INJECT", "1").strip() not in ("0", "false", "no")
    HINTS_LIMIT     = int(os.environ.get("HINTS_LIMIT", "2"))
    LOCAL_AGENTS_PATH = os.environ.get("LOCAL_AGENTS_PATH", "${repoPath}/ai-stack/local-agents").strip()
    LOCAL_TOOL_CALL_LIMIT = int(os.environ.get("SWB_LOCAL_TOOL_CALL_LIMIT", "8"))
    CONNECT_TIMEOUT_S = float(os.environ.get("SWB_CONNECT_TIMEOUT_S", "10"))
    WRITE_TIMEOUT_S = float(os.environ.get("SWB_WRITE_TIMEOUT_S", "60"))
    POOL_TIMEOUT_S = float(os.environ.get("SWB_POOL_TIMEOUT_S", "30"))
    LOCAL_READ_TIMEOUT_S = float(os.environ.get("SWB_LOCAL_READ_TIMEOUT_S", "900"))
    REMOTE_READ_TIMEOUT_S = float(os.environ.get("SWB_REMOTE_READ_TIMEOUT_S", "300"))
    STREAM_READ_TIMEOUT_S = float(os.environ.get("SWB_STREAM_READ_TIMEOUT_S", "1800"))
    LOCAL_CONCURRENCY = max(1, int(os.environ.get("SWB_LOCAL_CONCURRENCY", "2")))
    REMOTE_CONCURRENCY = max(1, int(os.environ.get("SWB_REMOTE_CONCURRENCY", "4")))
    CONTINUE_LOCAL_MAX_INPUT_TOKENS = max(256, int(os.environ.get("SWB_CONTINUE_LOCAL_MAX_INPUT_TOKENS", "2200")))
    CONTINUE_LOCAL_MAX_MESSAGES = max(2, int(os.environ.get("SWB_CONTINUE_LOCAL_MAX_MESSAGES", "12")))
    REMOTE_DEFAULT_MAX_INPUT_TOKENS = max(256, int(os.environ.get("SWB_REMOTE_DEFAULT_MAX_INPUT_TOKENS", "3500")))
    REMOTE_DEFAULT_MAX_MESSAGES = max(2, int(os.environ.get("SWB_REMOTE_DEFAULT_MAX_MESSAGES", "16")))
    PROFILE_CARDS_ENABLED = os.environ.get("SWB_PROFILE_CARDS_ENABLED", "1").strip() not in ("0", "false", "no")
    SEMANTIC_PRUNE_ENABLED = os.environ.get("SWB_SEMANTIC_PRUNE_ENABLED", "1").strip() not in ("0", "false", "no")
    SEMANTIC_TOP_K = max(2, int(os.environ.get("SWB_SEMANTIC_TOP_K", "8")))
    SEMANTIC_MAX_CANDIDATES = max(4, int(os.environ.get("SWB_SEMANTIC_MAX_CANDIDATES", "24")))
    SEMANTIC_EMBED_TIMEOUT_S = float(os.environ.get("SWB_SEMANTIC_EMBED_TIMEOUT_S", "4"))
    REASONING_MODE = os.environ.get("SWB_REASONING_MODE", "hybrid").strip().lower()
    LEXICAL_ENABLED = os.environ.get("SWB_LEXICAL_ENABLED", "1").strip() not in ("0", "false", "no")
    DECOMPOSE_ENABLED = os.environ.get("SWB_DECOMPOSE_ENABLED", "1").strip() not in ("0", "false", "no")
    ANSWERABILITY_GATE_ENABLED = os.environ.get("SWB_ANSWERABILITY_GATE_ENABLED", "1").strip() not in ("0", "false", "no")
    ANSWERABILITY_MIN_SCORE = float(os.environ.get("SWB_ANSWERABILITY_MIN_SCORE", "0.28"))
    EMBEDDED_ASSIST_MAX_INPUT_TOKENS = max(256, int(os.environ.get("SWB_EMBEDDED_ASSIST_MAX_INPUT_TOKENS", "1800")))
    EMBEDDED_ASSIST_MAX_MESSAGES = max(2, int(os.environ.get("SWB_EMBEDDED_ASSIST_MAX_MESSAGES", "10")))
    CARD_CONTINUE_LOCAL = ${builtins.toJSON continueLocalCard}
    CARD_REMOTE_DEFAULT = ${builtins.toJSON remoteDefaultCard}
    CARD_REMOTE_FREE = ${builtins.toJSON remoteFreeCard}
    CARD_REMOTE_CODING = ${builtins.toJSON remoteCodingCard}
    CARD_REMOTE_REASONING = ${builtins.toJSON remoteReasoningCard}
    CARD_REMOTE_TOOL_CALLING = ${builtins.toJSON remoteToolCallingCard}
    CARD_LOCAL_TOOL_CALLING = ${builtins.toJSON localToolCallingCard}
    CARD_EMBEDDING_LOCAL = ${builtins.toJSON embeddingLocalCard}
    _LOCAL_TOOL_REGISTRY = None
    REMOTE_MODEL_ALIASES_ENABLED = os.environ.get("SWB_REMOTE_MODEL_ALIASES_ENABLED", "1").strip() not in ("0", "false", "no")
    REMOTE_MODEL_ALIAS_FREE = os.environ.get("SWB_REMOTE_MODEL_ALIAS_FREE", "").strip()
    REMOTE_MODEL_ALIAS_CODING = os.environ.get("SWB_REMOTE_MODEL_ALIAS_CODING", "").strip()
    REMOTE_MODEL_ALIAS_REASONING = os.environ.get("SWB_REMOTE_MODEL_ALIAS_REASONING", "").strip()
    REMOTE_MODEL_ALIAS_TOOL_CALLING = os.environ.get("SWB_REMOTE_MODEL_ALIAS_TOOL_CALLING", "").strip()
    REMOTE_DAILY_TOKEN_CAP = max(0, int(os.environ.get("SWB_REMOTE_DAILY_TOKEN_CAP", "0")))
    REMOTE_BUDGET_FALLBACK_LOCAL = os.environ.get("SWB_REMOTE_BUDGET_FALLBACK_LOCAL", "1").strip() not in ("0", "false", "no")
    REMOTE_BUDGET_STATE_PATH = os.environ.get("SWB_REMOTE_BUDGET_STATE_PATH", "").strip()
    _hybrid_key_file = os.environ.get("HYBRID_API_KEY_FILE", "").strip()
    HYBRID_API_KEY  = ""
    if _hybrid_key_file:
        try:
            with open(_hybrid_key_file) as _kf:
                HYBRID_API_KEY = _kf.read().strip()
        except OSError:
            pass

    def _read_secret(path: str) -> str:
        if not path:
            return ""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return ""

    if not REMOTE_API_KEY and REMOTE_API_KEY_FILE:
        REMOTE_API_KEY = _read_secret(REMOTE_API_KEY_FILE)

    def _normalize_remote_url(url: str) -> str:
        if not url:
            return ""
        return url[:-1] if url.endswith("/") else url

    REMOTE_URL = _normalize_remote_url(REMOTE_URL)

    if LOCAL_AGENTS_PATH and LOCAL_AGENTS_PATH not in sys.path:
        sys.path.insert(0, LOCAL_AGENTS_PATH)

    app = FastAPI(title="AI Switchboard")
    _local_sem = None
    _remote_sem = None

    @app.on_event("startup")
    async def _startup():
        import asyncio
        global _local_sem, _remote_sem
        _local_sem = asyncio.Semaphore(LOCAL_CONCURRENCY)
        _remote_sem = asyncio.Semaphore(REMOTE_CONCURRENCY)

    @app.get("/health")
    async def health():
        budget_state = _budget_state_current()
        return {
            "status": "ok",
            "service": "ai-switchboard",
            "routing_mode": ROUTING_MODE,
            "default_provider": DEFAULT_PROVIDER,
            "upstreams": {
                "local": LLAMA_URL,
                "embedding": EMBEDDING_URL if EMBEDDING_URL else None,
                "remote": REMOTE_URL if REMOTE_URL else None,
            },
            "remote_configured": bool(REMOTE_URL),
            "profiles": {
                "default": {"force_provider": None, "inject_hints": HINTS_INJECT},
                "continue-local": {"force_provider": "local", "inject_hints": False},
                "remote-default": {"force_provider": "remote", "inject_hints": False},
                "remote-free": {"force_provider": "remote", "inject_hints": False, "model_alias": REMOTE_MODEL_ALIAS_FREE or None},
                "remote-coding": {"force_provider": "remote", "inject_hints": False, "model_alias": REMOTE_MODEL_ALIAS_CODING or None},
                "remote-reasoning": {"force_provider": "remote", "inject_hints": False, "model_alias": REMOTE_MODEL_ALIAS_REASONING or None},
                "remote-tool-calling": {"force_provider": "remote", "inject_hints": False, "model_alias": REMOTE_MODEL_ALIAS_TOOL_CALLING or None},
                "local-tool-calling": {"force_provider": "local", "inject_hints": False, "tool_execution": "built-in"},
                "embedding-local": {"force_provider": "local", "inject_hints": False, "embeddings_only": True},
                "embedded-assist": {"force_provider": "local", "inject_hints": False, "embeddings_only": False},
            },
            "policies": {
                "continue_local_max_input_tokens": CONTINUE_LOCAL_MAX_INPUT_TOKENS,
                "continue_local_max_messages": CONTINUE_LOCAL_MAX_MESSAGES,
                "remote_default_max_input_tokens": REMOTE_DEFAULT_MAX_INPUT_TOKENS,
                "remote_default_max_messages": REMOTE_DEFAULT_MAX_MESSAGES,
                "embedded_assist_max_input_tokens": EMBEDDED_ASSIST_MAX_INPUT_TOKENS,
                "embedded_assist_max_messages": EMBEDDED_ASSIST_MAX_MESSAGES,
                "profile_cards_enabled": PROFILE_CARDS_ENABLED,
                "semantic_prune_enabled": SEMANTIC_PRUNE_ENABLED,
                "reasoning_mode": REASONING_MODE,
                "lexical_enabled": LEXICAL_ENABLED,
                "decompose_enabled": DECOMPOSE_ENABLED,
                "answerability_gate_enabled": ANSWERABILITY_GATE_ENABLED,
                "remote_daily_token_cap": REMOTE_DAILY_TOKEN_CAP,
                "remote_budget_fallback_local": REMOTE_BUDGET_FALLBACK_LOCAL,
                "remote_model_aliases_enabled": REMOTE_MODEL_ALIASES_ENABLED,
            },
            "remote_budget": budget_state,
        }

    def _route_target(request: Request, payload: dict | None, profile: str) -> str:
        if profile == "continue-local":
            return "local"
        if profile in ("remote-default", "remote-free", "remote-coding", "remote-reasoning", "remote-tool-calling"):
            return "remote" if REMOTE_URL else "local"
        if profile == "local-tool-calling":
            return "local"
        if profile == "embedding-local":
            return "local"
        if profile == "embedded-assist":
            return "local"

        route_hint = request.headers.get(ROUTE_HINT_HEADER, "").strip().lower()
        provider_hint = request.headers.get(PROVIDER_HINT_HEADER, "").strip().lower()

        if ROUTING_MODE == "local_only":
            return "local"
        if ROUTING_MODE == "remote_only":
            return "remote" if REMOTE_URL else "local"

        if route_hint in ("local", "remote"):
            return route_hint if (route_hint != "remote" or REMOTE_URL) else "local"
        if provider_hint in ("local", "remote"):
            return provider_hint if (provider_hint != "remote" or REMOTE_URL) else "local"

        model = ""
        if isinstance(payload, dict):
            model = str(payload.get("model", "")).strip().lower()
        if any(model.startswith(prefix) for prefix in REMOTE_MODEL_PREFIXES):
            return "remote" if REMOTE_URL else "local"

        if DEFAULT_PROVIDER == "remote" and REMOTE_URL:
            return "remote"
        return "local"

    def _remote_model_alias(name: str) -> str:
        lowered = (name or "").strip().lower()
        if lowered in ("free", "budget", "cheap"):
            return REMOTE_MODEL_ALIAS_FREE
        if lowered in ("coding", "code", "coder"):
            return REMOTE_MODEL_ALIAS_CODING
        if lowered in ("reasoning", "architecture", "thinking"):
            return REMOTE_MODEL_ALIAS_REASONING
        if lowered in ("tool", "tools", "tool-calling", "tool_calling", "function", "function-calling"):
            return REMOTE_MODEL_ALIAS_TOOL_CALLING
        return ""

    def _rewrite_model(payload: dict, profile: str) -> dict:
        if not isinstance(payload, dict):
            return payload
        model = str(payload.get("model", ""))
        alias_model = ""
        if REMOTE_MODEL_ALIASES_ENABLED:
            if profile == "remote-free":
                alias_model = REMOTE_MODEL_ALIAS_FREE
            elif profile == "remote-coding":
                alias_model = REMOTE_MODEL_ALIAS_CODING
            elif profile == "remote-reasoning":
                alias_model = REMOTE_MODEL_ALIAS_REASONING
            elif profile == "remote-tool-calling":
                alias_model = REMOTE_MODEL_ALIAS_TOOL_CALLING
        for prefix in REMOTE_MODEL_PREFIXES:
            if model.lower().startswith(prefix):
                suffix = model[len(prefix):] or "default"
                alias_model = alias_model or _remote_model_alias(suffix)
                payload["model"] = alias_model or suffix
                break
        if model.lower().startswith("local/"):
            payload["model"] = model[len("local/"):] or "local-model"
        elif alias_model and not model:
            payload["model"] = alias_model
        return payload

    def _effective_profile(request: Request) -> str:
        profile = request.headers.get(PROFILE_HINT_HEADER, "").strip().lower()
        if not profile:
            profile = request.query_params.get("ai_profile", "").strip().lower()
        allowed = ("continue-local", "local-tool-calling", "remote-default", "remote-free", "remote-coding", "remote-reasoning", "remote-tool-calling", "embedding-local", "embedded-assist", "default")
        return profile if profile in allowed else "default"

    def _budget_state_current() -> dict:
        today = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
        state = {"date": today, "remote_tokens_used": 0}
        if not REMOTE_BUDGET_STATE_PATH:
            return state
        try:
            with open(REMOTE_BUDGET_STATE_PATH, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict) and loaded.get("date") == today:
                state["remote_tokens_used"] = int(loaded.get("remote_tokens_used", 0) or 0)
        except Exception:
            pass
        return state

    def _budget_state_save(remote_tokens_used: int) -> None:
        if not REMOTE_BUDGET_STATE_PATH:
            return
        state_path = __import__("pathlib").Path(REMOTE_BUDGET_STATE_PATH)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "date": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d"),
            "remote_tokens_used": max(0, int(remote_tokens_used)),
        }
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        tmp.replace(state_path)

    def _estimate_payload_tokens(payload: dict | None) -> int:
        if not isinstance(payload, dict):
            return 0
        if isinstance(payload.get("messages"), list):
            return _estimate_messages_tokens(payload.get("messages", []))
        if isinstance(payload.get("input"), list):
            return _estimate_messages_tokens(payload.get("input", []))
        if "prompt" in payload:
            return _estimate_tokens(str(payload.get("prompt", "")))
        return 0

    def _remote_budget_status(projected_delta: int) -> tuple[bool, dict]:
        state = _budget_state_current()
        used = int(state.get("remote_tokens_used", 0) or 0)
        projected = used + max(0, int(projected_delta))
        remaining = max(0, REMOTE_DAILY_TOKEN_CAP - used) if REMOTE_DAILY_TOKEN_CAP > 0 else None
        allowed = REMOTE_DAILY_TOKEN_CAP <= 0 or projected <= REMOTE_DAILY_TOKEN_CAP
        return allowed, {
            "date": state.get("date"),
            "remote_tokens_used": used,
            "projected_remote_tokens_used": projected,
            "remote_daily_token_cap": REMOTE_DAILY_TOKEN_CAP,
            "remote_tokens_remaining": remaining,
        }

    def _timeout_for(target_type: str, is_stream: bool) -> httpx.Timeout:
        if is_stream:
            read_timeout = STREAM_READ_TIMEOUT_S
        elif target_type == "remote":
            read_timeout = REMOTE_READ_TIMEOUT_S
        else:
            read_timeout = LOCAL_READ_TIMEOUT_S
        return httpx.Timeout(
            connect=CONNECT_TIMEOUT_S,
            read=read_timeout,
            write=WRITE_TIMEOUT_S,
            pool=POOL_TIMEOUT_S,
        )

    def _is_self_referential(url: str) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            port = parsed.port
            if port is None:
                port = 443 if parsed.scheme == "https" else 80
            return host in {"127.0.0.1", "localhost", "::1"} and port == PORT
        except Exception:
            return False

    def _response_headers(raw_headers: dict) -> dict:
        hop = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailer",
            "transfer-encoding",
            "upgrade",
            "content-length",
        }
        return {k: v for k, v in raw_headers.items() if k.lower() not in hop}

    def _tool_name(tool: dict) -> str:
        if not isinstance(tool, dict):
            return ""
        if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            return str(tool["function"].get("name", "")).strip()
        return str(tool.get("name", "")).strip()

    def _tool_payload_from_schema(schema: dict) -> dict:
        return {
            "type": "function",
            "function": {
                "name": schema.get("name", ""),
                "description": schema.get("description", ""),
                "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
            },
        }

    def _load_local_tool_registry():
        global _LOCAL_TOOL_REGISTRY
        if _LOCAL_TOOL_REGISTRY is not None:
            return _LOCAL_TOOL_REGISTRY
        try:
            from tool_registry import get_registry, ToolCall
            from builtin_tools.ai_coordination import register_ai_coordination_tools
            from builtin_tools.computer_use import register_computer_use_tools
            from builtin_tools.file_operations import register_file_tools
            from builtin_tools.shell_tools import register_shell_tools
        except Exception as exc:
            raise RuntimeError(f"failed to import local agent tooling from {LOCAL_AGENTS_PATH}: {exc}") from exc

        registry = get_registry()
        if not registry.tools:
            register_file_tools(registry)
            register_shell_tools(registry)
            register_ai_coordination_tools(registry)
            register_computer_use_tools(registry)
        _LOCAL_TOOL_REGISTRY = (registry, ToolCall)
        return _LOCAL_TOOL_REGISTRY

    def _normalize_local_tools(requested_tools):
        registry, _tool_call_cls = _load_local_tool_registry()
        available = {
            tool.name: _tool_payload_from_schema(tool.to_json_schema())
            for tool in registry.list_tools()
        }
        if isinstance(requested_tools, list) and requested_tools:
            selected = []
            unsupported = []
            seen = set()
            for tool in requested_tools:
                name = _tool_name(tool)
                if not name:
                    continue
                if name not in available:
                    unsupported.append(name)
                    continue
                if name in seen:
                    continue
                selected.append(available[name])
                seen.add(name)
            if unsupported:
                raise ValueError(
                    "local-tool-calling only supports built-in server tools; unsupported: "
                    + ", ".join(sorted(set(unsupported)))
                )
            if not selected:
                raise ValueError("local-tool-calling did not receive any executable built-in tools")
            return selected, set(seen)
        selected = list(available.values())
        return selected, {name for name in available}

    def _normalize_tool_choice(tool_choice, allowed_names):
        if tool_choice in (None, "", False):
            return "auto"
        if isinstance(tool_choice, str):
            lowered = tool_choice.strip().lower()
            if lowered in {"auto", "none", "required"}:
                return lowered
            return "auto"
        if isinstance(tool_choice, dict):
            function_name = _tool_name(tool_choice)
            if function_name and function_name not in allowed_names:
                raise ValueError(f"tool_choice requested unsupported local tool: {function_name}")
            return tool_choice
        return "auto"

    async def _execute_local_tool_calling(payload: dict) -> tuple[dict, int]:
        registry, tool_call_cls = _load_local_tool_registry()
        tools_payload, allowed_names = _normalize_local_tools(payload.get("tools"))
        tool_choice = _normalize_tool_choice(payload.get("tool_choice"), allowed_names)
        messages = list(payload.get("messages") or [])
        if not messages:
            raise ValueError("chat/completions requires messages for local-tool-calling")

        requested_limit = payload.get("max_tool_calls", LOCAL_TOOL_CALL_LIMIT)
        try:
            max_tool_calls = int(requested_limit)
        except (TypeError, ValueError):
            max_tool_calls = LOCAL_TOOL_CALL_LIMIT
        max_tool_calls = max(1, min(max_tool_calls, LOCAL_TOOL_CALL_LIMIT))
        tool_calls_used = 0
        request_payload = dict(payload)
        request_payload["messages"] = messages
        request_payload["tools"] = tools_payload
        request_payload["tool_choice"] = tool_choice
        request_payload["stream"] = False

        async with httpx.AsyncClient(timeout=_timeout_for("local", False)) as client:
            while True:
                upstream = await client.post(
                    f"{LLAMA_URL}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=request_payload,
                )
                body = upstream.json()
                if upstream.status_code >= 400:
                    message = body.get("error", {}).get("message") if isinstance(body, dict) else str(body)
                    raise RuntimeError(f"local llama.cpp tool step failed: {message or upstream.text}")

                choices = body.get("choices", []) if isinstance(body, dict) else []
                if not choices:
                    raise RuntimeError("local llama.cpp returned no choices during tool execution")
                message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    return body, tool_calls_used

                messages.append({
                    "role": "assistant",
                    "content": message.get("content", "") or "",
                    "tool_calls": tool_calls,
                })

                for tool_call in tool_calls:
                    if tool_calls_used >= max_tool_calls:
                        raise RuntimeError(f"local tool-call limit exceeded: {tool_calls_used}>{max_tool_calls}")
                    function_payload = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
                    tool_name = str(function_payload.get("name", "")).strip()
                    tool_call_id = str(tool_call.get("id", "")).strip() or hashlib.md5(
                        f"{tool_name}:{time.time()}".encode("utf-8")
                    ).hexdigest()[:16]
                    if tool_name not in allowed_names:
                        tool_result_text = json.dumps({
                            "tool": tool_name,
                            "status": "error",
                            "error": f"unsupported local tool: {tool_name}",
                        })
                    else:
                        raw_arguments = function_payload.get("arguments", "{}")
                        try:
                            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments or {})
                        except Exception as exc:
                            tool_result_text = json.dumps({
                                "tool": tool_name,
                                "status": "error",
                                "error": f"invalid JSON arguments: {exc}",
                                "raw_arguments": raw_arguments,
                            })
                        else:
                            tool_call_obj = tool_call_cls(
                                id=tool_call_id,
                                tool_name=tool_name,
                                arguments=arguments,
                                model_id=str(body.get("model", "")),
                                session_id=f"switchboard-{hashlib.md5(json.dumps(messages, default=str).encode('utf-8')).hexdigest()[:12]}",
                            )
                            tool_result = await registry.execute_tool_call(tool_call_obj)
                            tool_result_text = registry.format_tool_result(tool_result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result_text,
                    })
                    tool_calls_used += 1

                request_payload["messages"] = messages
                request_payload["tool_choice"] = "auto"

    def _estimate_tokens(text: str) -> int:
        # Lightweight approximation for guardrail decisions. Keep a
        # character-based floor so long dense blobs without whitespace do not
        # evade input trimming.
        text = str(text or "")
        word_estimate = int(len(text.split()) * 1.3)
        char_estimate = int((len(text) + 3) / 4)
        return max(1, word_estimate, char_estimate)

    def _estimate_messages_tokens(messages: list) -> int:
        total = 0
        for m in messages:
            if not isinstance(m, dict):
                continue
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
            total += _estimate_tokens(str(content))
        return total

    def _extract_content_text(message: dict) -> str:
        content = message.get("content", "")
        if isinstance(content, list):
            return " ".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content)

    def _truncate_text_to_token_budget(text: str, max_tokens: int) -> str:
        raw = str(text or "")
        if max_tokens <= 0 or _estimate_tokens(raw) <= max_tokens:
            return raw
        max_chars = max(64, max_tokens * 4)
        if len(raw) <= max_chars:
            return raw
        if max_chars <= 80:
            return raw[:max_chars]
        head_chars = int(max_chars * 0.7)
        tail_chars = max(24, max_chars - head_chars - 18)
        return raw[:head_chars] + "\n[... trimmed ...]\n" + raw[-tail_chars:]

    def _truncate_message_to_token_budget(message: dict, max_tokens: int) -> dict:
        updated = dict(message)
        updated["content"] = _truncate_text_to_token_budget(_extract_content_text(message), max_tokens)
        return updated

    def _tokenize(text: str) -> list[str]:
        return [t for t in re.split(r"[^a-z0-9_./-]+", (text or "").lower()) if len(t) >= 2]

    def _decompose_query(query_text: str) -> list[str]:
        if not query_text.strip():
            return []
        if not DECOMPOSE_ENABLED:
            return [query_text]
        lowered = query_text.strip()
        parts = re.split(r"\b(?:and|then|also)\b|[,\n;]+", lowered, maxsplit=3)
        pieces = [p.strip() for p in parts if p.strip()]
        if len(pieces) <= 1:
            return [query_text]
        return [query_text] + pieces[:3]

    async def _semantic_scores(candidates: list, query_text: str) -> dict[int, float]:
        if not SEMANTIC_PRUNE_ENABLED or not EMBEDDING_URL or not query_text.strip():
            return {}
        try:
            import math
            payload = {
                "model": "semantic-rerank",
                "input": [query_text] + [_extract_content_text(m)[:2000] for m in candidates],
            }
            timeout = httpx.Timeout(connect=2.0, read=SEMANTIC_EMBED_TIMEOUT_S, write=2.0, pool=2.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{EMBEDDING_URL}/v1/embeddings", json=payload)
            if resp.status_code != 200:
                return {}
            data = resp.json()
            rows = data.get("data", [])
            if len(rows) < 2:
                return {}

            qv = rows[0].get("embedding", [])
            if not isinstance(qv, list) or not qv:
                return {}

            qnorm = math.sqrt(sum(float(x) * float(x) for x in qv)) or 1.0
            scored = {}
            for idx, row in enumerate(rows[1:]):
                ev = row.get("embedding", [])
                if not isinstance(ev, list) or not ev:
                    continue
                dot = sum(float(a) * float(b) for a, b in zip(qv, ev))
                enorm = math.sqrt(sum(float(x) * float(x) for x in ev)) or 1.0
                # Clamp cosine to [0,1] so unrelated context does not score ~0.5 by default.
                cosine = dot / (qnorm * enorm)
                scored[idx] = max(0.0, min(1.0, cosine))
            return scored
        except Exception:
            return {}

    def _lexical_scores(candidates: list, query_variants: list[str]) -> dict[int, float]:
        if not LEXICAL_ENABLED or not query_variants:
            return {}
        token_sets = [set(_tokenize(q)) for q in query_variants if q.strip()]
        token_sets = [s for s in token_sets if s]
        if not token_sets:
            return {}
        scores = {}
        for idx, msg in enumerate(candidates):
            text = _extract_content_text(msg).lower()
            msg_tokens = set(_tokenize(text))
            if not msg_tokens:
                continue
            best = 0.0
            for qset in token_sets:
                overlap = len(qset.intersection(msg_tokens))
                if overlap <= 0:
                    continue
                containment = overlap / max(1, len(qset))
                exact_bonus = 0.12 if any(t in text for t in list(qset)[:4]) else 0.0
                best = max(best, min(1.0, containment + exact_bonus))
            if best > 0.0:
                scores[idx] = best
        return scores

    def _rrf_scores(score_maps: list[dict[int, float]]) -> dict[int, float]:
        # Reciprocal-rank fusion to combine semantic + lexical ranking robustly.
        fused = {}
        k = 50.0
        for smap in score_maps:
            ranked = sorted(smap.items(), key=lambda item: item[1], reverse=True)
            for rank, (idx, _) in enumerate(ranked, start=1):
                fused[idx] = fused.get(idx, 0.0) + (1.0 / (k + rank))
        return fused

    async def _select_non_system(non_system_messages: list, query_text: str) -> tuple[list, float, str]:
        if len(non_system_messages) <= SEMANTIC_TOP_K:
            return non_system_messages, 1.0, "no-prune"
        candidates = non_system_messages[-SEMANTIC_MAX_CANDIDATES:]
        scoring_candidates = []
        scoring_index_map = []
        query_norm = query_text.strip().lower()
        for idx, msg in enumerate(candidates):
            if (
                query_norm
                and isinstance(msg, dict)
                and msg.get("role") == "user"
                and _extract_content_text(msg).strip().lower() == query_norm
            ):
                # Exclude the latest query itself from retrieval confidence.
                continue
            scoring_candidates.append(msg)
            scoring_index_map.append(idx)
        if not scoring_candidates:
            return candidates[-SEMANTIC_TOP_K:], 0.0, "recency-fallback"
        query_variants = _decompose_query(query_text)
        semantic_raw = await _semantic_scores(scoring_candidates, query_variants[0] if query_variants else "")
        lexical_raw = _lexical_scores(scoring_candidates, query_variants)
        semantic = {scoring_index_map[idx]: score for idx, score in semantic_raw.items() if idx < len(scoring_index_map)}
        lexical = {scoring_index_map[idx]: score for idx, score in lexical_raw.items() if idx < len(scoring_index_map)}

        mode = REASONING_MODE
        if mode not in ("semantic", "lexical", "hybrid"):
            mode = "hybrid"

        if mode == "semantic":
            combined = semantic
            best_score = max(semantic.values(), default=0.0)
        elif mode == "lexical":
            combined = lexical
            best_score = max(lexical.values(), default=0.0)
        else:
            if semantic and lexical:
                combined = _rrf_scores([semantic, lexical])
                # Keep best raw relevance estimate for answerability gate.
                best_score = max((0.65 * semantic.get(i, 0.0) + 0.35 * lexical.get(i, 0.0)) for i in set(semantic) | set(lexical))
            else:
                combined = semantic or lexical
                best_score = max((combined or {0: 0.0}).values())

        if not combined:
            # Recency fallback when retrieval signals are unavailable.
            return candidates[-SEMANTIC_TOP_K:], 0.0, "recency-fallback"

        top = {idx for idx, _ in sorted(combined.items(), key=lambda item: item[1], reverse=True)[:SEMANTIC_TOP_K]}
        for idx in range(max(0, len(candidates) - 2), len(candidates)):
            top.add(idx)
        selected = [m for idx, m in enumerate(candidates) if idx in top]
        return (selected if selected else non_system_messages), best_score, f"{mode}-rrf"

    async def _trim_profile_messages(messages: list, profile: str) -> tuple[list, bool, int, int, str, float, bool]:
        if not isinstance(messages, list):
            return messages, False, 0, 0, "none", 1.0, False

        if profile == "continue-local":
            max_tokens = CONTINUE_LOCAL_MAX_INPUT_TOKENS
            max_messages = CONTINUE_LOCAL_MAX_MESSAGES
        elif profile == "remote-default":
            max_tokens = REMOTE_DEFAULT_MAX_INPUT_TOKENS
            max_messages = REMOTE_DEFAULT_MAX_MESSAGES
        elif profile == "embedded-assist":
            max_tokens = EMBEDDED_ASSIST_MAX_INPUT_TOKENS
            max_messages = EMBEDDED_ASSIST_MAX_MESSAGES
        else:
            return messages, False, 0, 0, "none", 1.0, False

        before = _estimate_messages_tokens(messages)
        if before <= max_tokens and len(messages) <= max_messages:
            return messages, False, before, before, "none", 1.0, False

        system_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
        non_system = [m for m in messages if isinstance(m, dict) and m.get("role") != "system"]
        latest_user = ""
        for msg in reversed(non_system):
            if msg.get("role") == "user":
                latest_user = _extract_content_text(msg)
                break

        selected, relevance, reasoning_policy = await _select_non_system(non_system, latest_user)
        if selected:
            non_system = selected

        # Keep the newest conversational turns, plus at most one system prompt.
        kept = non_system[-max_messages:]
        if system_msgs:
            kept = [system_msgs[-1]] + kept

        # Enforce token budget by dropping oldest conversational messages first.
        while kept and _estimate_messages_tokens(kept) > max_tokens:
            if len(kept) > 1 and isinstance(kept[0], dict) and kept[0].get("role") == "system":
                if len(kept) > 2:
                    del kept[1]
                else:
                    break
            else:
                kept.pop(0)

        if kept and _estimate_messages_tokens(kept) > max_tokens:
            largest_idx = max(
                range(len(kept)),
                key=lambda idx: _estimate_tokens(_extract_content_text(kept[idx])) if isinstance(kept[idx], dict) else 0,
            )
            reserved_tokens = 0
            for idx, message in enumerate(kept):
                if idx == largest_idx or not isinstance(message, dict):
                    continue
                reserved_tokens += _estimate_tokens(_extract_content_text(message))
            available_tokens = max(128, max_tokens - reserved_tokens)
            if isinstance(kept[largest_idx], dict):
                kept[largest_idx] = _truncate_message_to_token_budget(kept[largest_idx], available_tokens)

        after = _estimate_messages_tokens(kept)
        gate_applied = False
        if (
            ANSWERABILITY_GATE_ENABLED
            and latest_user.strip()
            and profile in ("continue-local", "embedded-assist")
            and relevance < ANSWERABILITY_MIN_SCORE
        ):
            gate_applied = True
            gate_msg = {
                "role": "system",
                "content": (
                    "[answerability-gate] Retrieval confidence is low. "
                    "Ask a clarifying question before making assumptions, then answer briefly."
                ),
            }
            if not any(isinstance(m, dict) and "[answerability-gate]" in str(m.get("content", "")) for m in kept):
                kept = [gate_msg] + kept
        mode = f"{reasoning_policy}+trim"
        return kept, True, before, after, mode, relevance, gate_applied

    def _profile_card(profile: str) -> str:
        if not PROFILE_CARDS_ENABLED:
            return ""
        if profile == "continue-local":
            return CARD_CONTINUE_LOCAL.strip()
        if profile == "remote-default":
            return CARD_REMOTE_DEFAULT.strip()
        if profile == "remote-free":
            return CARD_REMOTE_FREE.strip()
        if profile == "remote-coding":
            return CARD_REMOTE_CODING.strip()
        if profile == "remote-reasoning":
            return CARD_REMOTE_REASONING.strip()
        if profile == "remote-tool-calling":
            return CARD_REMOTE_TOOL_CALLING.strip()
        if profile == "local-tool-calling":
            return CARD_LOCAL_TOOL_CALLING.strip()
        if profile == "embedding-local":
            return CARD_EMBEDDING_LOCAL.strip()
        if profile == "embedded-assist":
            return (
                "[profile-card:embedded-assist]\n"
                "Use compact reasoning and progressive disclosure.\n"
                "Prefer hybrid retrieval (semantic + lexical), then ask for clarification on low confidence.\n"
                "Do not expand full policy docs unless explicitly requested."
            )
        return ""

    def _ensure_profile_card(messages: list, profile: str) -> tuple[list, bool]:
        if not isinstance(messages, list):
            return messages, False
        card = _profile_card(profile)
        if not card:
            return messages, False
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "system" and card in str(m.get("content", "")):
                return messages, False
        return ([{"role": "system", "content": card}] + list(messages)), True

    async def _get_hints(query: str):
        """Return a hints string from hybrid-coordinator, or None on any failure."""
        if not HYBRID_URL or not query.strip():
            return None
        try:
            from urllib.parse import urlencode
            params = urlencode({"q": query[:200], "limit": HINTS_LIMIT})
            hdrs = {}
            if HYBRID_API_KEY:
                hdrs["X-API-Key"] = HYBRID_API_KEY
            async with httpx.AsyncClient(timeout=2.0) as hclient:
                resp = await hclient.get(f"{HYBRID_URL}/hints?{params}", headers=hdrs)
            if resp.status_code != 200:
                return None
            data = resp.json()
            hints_list = data.get("hints", []) if isinstance(data, dict) else []
            if not hints_list:
                return None
            lines = ["[AI stack — tools available for this task]"]
            for item in hints_list:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("title") or item.get("id") or ""
                    tip  = item.get("hint") or item.get("description") or item.get("text") or ""
                    txt  = (f"{name}: {tip}".strip(": ")) if name else tip
                    if txt:
                        lines.append(f"- {txt}")
            return "\n".join(lines) if len(lines) > 1 else None
        except Exception:
            return None

    @app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy(path: str, request: Request):
        body = await request.body()
        payload = None
        input_trimmed = False
        input_tokens_before = 0
        input_tokens_after = 0
        input_policy = "none"
        profile_card_applied = False
        relevance = 1.0
        gate_applied = False
        if body:
            try:
                payload = await request.json()
            except Exception:
                payload = None

        profile = _effective_profile(request)
        target_type = _route_target(request, payload, profile)
        target = REMOTE_URL if target_type == "remote" and REMOTE_URL else LLAMA_URL
        if profile in ("remote-default", "remote-free", "remote-coding", "remote-reasoning", "remote-tool-calling") and not REMOTE_URL:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "message": f"{profile} profile requested but no REMOTE_LLM_URL is configured",
                        "type": "route_configuration_error",
                    }
                },
            )
        if profile == "embedding-local":
            if path not in ("embeddings", "models"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "message": "embedding-local profile only supports /v1/embeddings and /v1/models",
                            "type": "invalid_profile_for_endpoint",
                        }
                    },
                )
            if not EMBEDDING_URL:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "message": "embedding-local profile requested but EMBEDDING_URL is not configured",
                            "type": "route_configuration_error",
                        }
                    },
                )
            target = EMBEDDING_URL
        if path == "embeddings" and target_type == "local" and EMBEDDING_URL:
            target = EMBEDDING_URL
        if _is_self_referential(target):
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "message": "switchboard upstream points to itself; refusing recursive route",
                        "type": "route_configuration_error",
                    }
                },
            )

        if isinstance(payload, dict):
            payload = _rewrite_model(payload, profile)
            if path == "chat/completions":
                msgs = payload.get("messages")
                if isinstance(msgs, list):
                    with_card, card_applied = _ensure_profile_card(msgs, profile)
                    trimmed, did_trim, before, after, policy, relevance, gate_applied = await _trim_profile_messages(with_card, profile)
                    payload["messages"] = trimmed
                    input_trimmed = did_trim
                    input_tokens_before = before
                    input_tokens_after = after
                    input_policy = policy
                    profile_card_applied = card_applied
                else:
                    relevance = 1.0
                    gate_applied = False
            body = json.dumps(payload).encode("utf-8")

        remote_token_delta = _estimate_payload_tokens(payload)
        remote_budget = None
        payload_model = str(payload.get("model", "")).strip().lower() if isinstance(payload, dict) else ""
        explicit_remote = (
            profile in ("remote-default", "remote-free", "remote-coding", "remote-reasoning", "remote-tool-calling")
            or request.headers.get(ROUTE_HINT_HEADER, "").strip().lower() == "remote"
            or request.headers.get(PROVIDER_HINT_HEADER, "").strip().lower() == "remote"
            or any(payload_model.startswith(prefix) for prefix in REMOTE_MODEL_PREFIXES)
        )
        if target_type == "remote" and REMOTE_DAILY_TOKEN_CAP > 0:
            allowed, remote_budget = _remote_budget_status(remote_token_delta)
            if not allowed:
                if REMOTE_BUDGET_FALLBACK_LOCAL and not explicit_remote and path != "embeddings":
                    target_type = "local"
                    target = EMBEDDING_URL if path == "embeddings" and EMBEDDING_URL else LLAMA_URL
                else:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "message": "remote daily token budget exhausted",
                                "type": "remote_budget_exhausted",
                                "budget": remote_budget,
                            }
                        },
                    )

        use_hints = HINTS_INJECT and profile != "continue-local"
        if use_hints and path == "chat/completions" and isinstance(payload, dict):
            messages = payload.get("messages") or []
            first_user = next(
                (m.get("content", "") for m in messages if m.get("role") == "user"),
                "",
            )
            if first_user:
                hint_text = await _get_hints(str(first_user))
                if hint_text:
                    sys_idxs = [i for i, m in enumerate(messages) if m.get("role") == "system"]
                    if sys_idxs:
                        i = sys_idxs[-1]
                        messages[i] = dict(messages[i])
                        messages[i]["content"] = messages[i]["content"].rstrip() + "\n\n" + hint_text
                    else:
                        messages = [{"role": "system", "content": hint_text}] + list(messages)
                    payload["messages"] = messages
                    body = json.dumps(payload).encode("utf-8")

        is_stream = bool(isinstance(payload, dict) and payload.get("stream") is True)
        local_tool_execution_used = False
        local_tool_calls_used = 0

        hop_by_hop = {
            "host",
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailer",
            "transfer-encoding",
            "upgrade",
            "content-length",
            "accept-encoding",
        }
        headers = {k: v for k, v in request.headers.items() if k.lower() not in hop_by_hop}
        headers.pop(ROUTE_HINT_HEADER, None)
        headers.pop(PROVIDER_HINT_HEADER, None)
        headers.pop(PROFILE_HINT_HEADER, None)
        headers["Accept-Encoding"] = "identity"
        headers["Connection"] = "close"
        if target_type == "remote" and REMOTE_API_KEY:
            headers["Authorization"] = f"Bearer {REMOTE_API_KEY}"

        timeout = _timeout_for(target_type, is_stream)
        sem = _remote_sem if target_type == "remote" else _local_sem

        try:
            async with sem:
                if (
                    path == "chat/completions"
                    and profile == "local-tool-calling"
                    and target_type == "local"
                    and isinstance(payload, dict)
                    and not is_stream
                ):
                    try:
                        local_body, local_tool_calls_used = await _execute_local_tool_calling(payload)
                    except ValueError as exc:
                        return JSONResponse(
                            status_code=400,
                            content={"error": {"message": str(exc), "type": "invalid_local_tool_request"}},
                        )
                    except RuntimeError as exc:
                        return JSONResponse(
                            status_code=502,
                            content={"error": {"message": str(exc), "type": "local_tool_execution_error"}},
                        )
                    response = JSONResponse(status_code=200, content=local_body)
                    local_tool_execution_used = True
                else:
                    client = httpx.AsyncClient(timeout=timeout)
                    if is_stream:
                        req = client.build_request(
                            method=request.method,
                            url=f"{target}/v1/{path}",
                            headers=headers,
                            content=body,
                            params=dict(request.query_params),
                        )
                        upstream = await client.send(req, stream=True)

                        async def _iter():
                            try:
                                async for chunk in upstream.aiter_bytes():
                                    yield chunk
                            finally:
                                await upstream.aclose()
                                await client.aclose()

                        response = StreamingResponse(
                            _iter(),
                            status_code=upstream.status_code,
                            headers=_response_headers(dict(upstream.headers)),
                        )
                    else:
                        async with client:
                            upstream = await client.request(
                                method=request.method,
                                url=f"{target}/v1/{path}",
                                headers=headers,
                                content=body,
                                params=dict(request.query_params),
                            )
                        response = Response(
                            content=upstream.content,
                            status_code=upstream.status_code,
                            headers=_response_headers(dict(upstream.headers)),
                        )
        except httpx.TimeoutException:
            return JSONResponse(
                status_code=504,
                content={
                    "error": {
                        "message": "upstream timeout",
                        "type": "upstream_timeout",
                        "target": target_type,
                    }
                },
            )
        except httpx.HTTPError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "message": f"upstream transport error: {exc}",
                        "type": "upstream_transport_error",
                        "target": target_type,
                    }
                },
            )

        response.headers["X-AI-Route"] = target_type
        response.headers["X-AI-Profile"] = profile
        if local_tool_execution_used:
            response.headers["X-AI-Tool-Execution"] = "local-agent"
            response.headers["X-AI-Tool-Calls-Used"] = str(local_tool_calls_used)
        if remote_budget:
            response.headers["X-AI-Remote-Tokens-Used"] = str(remote_budget.get("remote_tokens_used", 0))
            if remote_budget.get("remote_tokens_remaining") is not None:
                response.headers["X-AI-Remote-Tokens-Remaining"] = str(remote_budget.get("remote_tokens_remaining"))
        if input_trimmed:
            response.headers["X-AI-Input-Trimmed"] = "1"
            response.headers["X-AI-Input-Tokens-Before"] = str(input_tokens_before)
            response.headers["X-AI-Input-Tokens-After"] = str(input_tokens_after)
        if input_policy != "none":
            response.headers["X-AI-Input-Policy"] = input_policy
        response.headers["X-AI-Retrieval-Confidence"] = f"{relevance:.3f}"
        if gate_applied:
            response.headers["X-AI-Answerability-Gate"] = "1"
        if profile_card_applied:
            response.headers["X-AI-Profile-Card"] = "1"
        if target_type == "remote" and REMOTE_DAILY_TOKEN_CAP > 0:
            latest_budget = _budget_state_current()
            used = int(latest_budget.get("remote_tokens_used", 0) or 0) + max(0, int(remote_token_delta))
            _budget_state_save(used)
            response.headers["X-AI-Remote-Tokens-Used"] = str(used)
            response.headers["X-AI-Remote-Tokens-Remaining"] = str(max(0, REMOTE_DAILY_TOKEN_CAP - used))
        return response

    if __name__ == "__main__":
        uvicorn.run(app, host=HOST, port=PORT, timeout_graceful_shutdown=5)
  '';
in
{
  config = lib.mkIf (cfg.roles.aiStack.enable && swb.enable) {

    systemd.services.ai-switchboard = {
      description = "AI Switchboard — local/remote LLM routing proxy";
      wantedBy    = [ "multi-user.target" "ai-stack.target" ];
      partOf      = [ "ai-stack.target" ];
      after       = [ "network-online.target" "ai-stack.target" ];
      wants       = [ "network-online.target" ];
      unitConfig = {
        StartLimitIntervalSec = "300";
        StartLimitBurst = 5;
      };
      serviceConfig = {
        ExecStart = lib.escapeShellArgs [
          "${switchboardPy}/bin/python3"
          "${switchboardScript}"
        ];
        Environment = [
          "PORT=${toString swb.port}"
          "HOST=127.0.0.1"
          "LLAMA_CPP_URL=${llamaUrl}"
          "EMBEDDING_URL=${embeddingUrl}"
          "ROUTING_MODE=${swb.routingMode}"
          "DEFAULT_PROVIDER=${swb.defaultProvider}"
          "REMOTE_LLM_URL=${remoteUrl}"
          "REMOTE_LLM_API_KEY_FILE=${remoteKeyFile}"
          "SWB_REMOTE_MODEL_ALIASES_ENABLED=${if swb.remoteModelAliases.enable then "1" else "0"}"
          "SWB_REMOTE_MODEL_ALIAS_FREE=${if swb.remoteModelAliases.free != null then swb.remoteModelAliases.free else ""}"
          "SWB_REMOTE_MODEL_ALIAS_CODING=${if swb.remoteModelAliases.coding != null then swb.remoteModelAliases.coding else ""}"
          "SWB_REMOTE_MODEL_ALIAS_REASONING=${if swb.remoteModelAliases.reasoning != null then swb.remoteModelAliases.reasoning else ""}"
          "SWB_REMOTE_MODEL_ALIAS_TOOL_CALLING=${if swb.remoteModelAliases.toolCalling != null then swb.remoteModelAliases.toolCalling else ""}"
          "SWB_REMOTE_DAILY_TOKEN_CAP=${toString swb.remoteBudget.dailyTokenCap}"
          "SWB_REMOTE_BUDGET_FALLBACK_LOCAL=${if swb.remoteBudget.fallbackToLocal then "1" else "0"}"
          "SWB_REMOTE_BUDGET_STATE_PATH=${remoteBudgetStatePath}"
          "HYBRID_URL=${hybridUrl}"
          "HYBRID_API_KEY_FILE=${hybridKeyFile}"
          "LOCAL_AGENTS_PATH=${repoPath}/ai-stack/local-agents"
        ];
        EnvironmentFile = "-${mutableOptimizerDir}/overrides.env";
        User                  = cfg.primaryUser;
        WorkingDirectory      = repoPath;
        Restart               = "on-failure";
        RestartSec            = "5s";
        TimeoutStopSec        = "15s";
        KillMode              = "mixed";
        NoNewPrivileges       = true;
        ProtectSystem         = "strict";
        ProtectHome           = "read-only";
        ReadOnlyPaths         = [ repoPath ];
        PrivateTmp            = true;
        CapabilityBoundingSet = "";
        RestrictSUIDSGID      = true;
        LockPersonality       = true;
        RestrictNamespaces    = true;
      };
    };

    networking.firewall.allowedTCPPorts =
      lib.mkIf ai.listenOnLan [ swb.port ];

  };
}
