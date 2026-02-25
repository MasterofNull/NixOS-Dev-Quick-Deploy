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
  llamaUrl = "http://${ai.llamaCpp.host}:${toString ai.llamaCpp.port}";
  remoteUrl = if swb.remoteUrl != null then swb.remoteUrl else "";
  remoteKeyFile = if swb.remoteApiKeyFile != null then swb.remoteApiKeyFile else "";

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

        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        headers.pop("content-length", None)
        headers.pop(ROUTE_HINT_HEADER, None)
        headers.pop(PROVIDER_HINT_HEADER, None)
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
        uvicorn.run(app, host=HOST, port=PORT)
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
        ];
        User                  = cfg.primaryUser;
        Restart               = "on-failure";
        RestartSec            = "5s";
        StartLimitIntervalSec = "300";
        StartLimitBurst       = 5;
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
