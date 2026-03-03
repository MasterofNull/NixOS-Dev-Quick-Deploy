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
  remoteUrl = if swb.remoteUrl != null then swb.remoteUrl else "";
  remoteKeyFile = if swb.remoteApiKeyFile != null then swb.remoteApiKeyFile else "";
  hybridUrl = "http://127.0.0.1:${toString mcp.hybridPort}";
  hybridKeyFile = if sec.enable
    then "/run/secrets/${sec.names.hybridApiKey}"
    else "";

  switchboardPy = pkgs.python3.withPackages (ps: with ps; [
    fastapi
    uvicorn
    httpx
  ]);

  switchboardScript = pkgs.writeText "ai-switchboard.py" ''
    #!/usr/bin/env python3
    """AI Switchboard — OpenAI-compatible LLM routing proxy."""
    import os
    import httpx
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import Response

    LLAMA_URL  = os.environ.get("LLAMA_CPP_URL", "${llamaUrl}").rstrip("/")
    REMOTE_URL = os.environ.get("REMOTE_LLM_URL", "").rstrip("/")
    ROUTING_MODE = os.environ.get("ROUTING_MODE", "auto").strip().lower()
    DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "local").strip().lower()
    REMOTE_API_KEY = os.environ.get("REMOTE_LLM_API_KEY", "").strip()
    REMOTE_API_KEY_FILE = os.environ.get("REMOTE_LLM_API_KEY_FILE", "").strip()
    PORT       = int(os.environ.get("PORT", "${toString swb.port}"))
    HOST       = os.environ.get("HOST", "127.0.0.1")
    ROUTE_HINT_HEADER = "x-ai-route"
    PROVIDER_HINT_HEADER = "x-ai-provider"
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

    app = FastAPI(title="AI Switchboard")

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "ai-switchboard",
            "routing_mode": ROUTING_MODE,
            "default_provider": DEFAULT_PROVIDER,
            "upstreams": {
                "local": LLAMA_URL,
                "remote": REMOTE_URL if REMOTE_URL else None,
            },
            "remote_configured": bool(REMOTE_URL),
        }

    def _route_target(request: Request, payload: dict | None) -> str:
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

    def _rewrite_model(payload: dict) -> dict:
        if not isinstance(payload, dict):
            return payload
        model = str(payload.get("model", ""))
        for prefix in REMOTE_MODEL_PREFIXES:
            if model.lower().startswith(prefix):
                payload["model"] = model[len(prefix):] or "default"
                break
        if model.lower().startswith("local/"):
            payload["model"] = model[len("local/"):] or "local-model"
        return payload

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
        if body:
            try:
                payload = await request.json()
            except Exception:
                payload = None

        target_type = _route_target(request, payload)
        target = REMOTE_URL if target_type == "remote" and REMOTE_URL else LLAMA_URL

        if isinstance(payload, dict):
            payload = _rewrite_model(payload)
            import json
            body = json.dumps(payload).encode("utf-8")

        if HINTS_INJECT and path == "chat/completions" and isinstance(payload, dict):
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

        # Strip hop-by-hop headers and force non-compressed upstream responses.
        # This avoids incomplete chunked-read failures from llama.cpp under load.
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
        headers["Accept-Encoding"] = "identity"
        headers["Connection"] = "close"
        if target_type == "remote" and REMOTE_API_KEY:
            headers["Authorization"] = f"Bearer {REMOTE_API_KEY}"

        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.request(
                method  = request.method,
                url     = f"{target}/v1/{path}",
                headers = headers,
                content = body,
                params  = dict(request.query_params),
            )
        response = Response(
            content    = r.content,
            status_code = r.status_code,
            headers    = dict(r.headers),
        )
        response.headers["X-AI-Route"] = target_type
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
      serviceConfig = {
        ExecStart = lib.escapeShellArgs [
          "${switchboardPy}/bin/python3"
          "${switchboardScript}"
        ];
        Environment = [
          "PORT=${toString swb.port}"
          "HOST=127.0.0.1"
          "LLAMA_CPP_URL=${llamaUrl}"
          "ROUTING_MODE=${swb.routingMode}"
          "DEFAULT_PROVIDER=${swb.defaultProvider}"
          "REMOTE_LLM_URL=${remoteUrl}"
          "REMOTE_LLM_API_KEY_FILE=${remoteKeyFile}"
          "HYBRID_URL=${hybridUrl}"
          "HYBRID_API_KEY_FILE=${hybridKeyFile}"
        ];
        EnvironmentFile = "-/var/lib/nixos-ai-stack/optimizer/overrides.env";
        User                  = cfg.primaryUser;
        Restart               = "on-failure";
        RestartSec            = "5s";
        StartLimitIntervalSec = "300";
        StartLimitBurst       = 5;
        TimeoutStopSec        = "15s";
        KillMode              = "mixed";
        NoNewPrivileges       = true;
        ProtectSystem         = "strict";
        ProtectHome           = true;
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
