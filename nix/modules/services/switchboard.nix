{ lib, config, pkgs, ... }:
# ---------------------------------------------------------------------------
# Switchboard — local/remote LLM routing proxy (Switchboard strategy).
#
# Provides an OpenAI-compatible endpoint on ai.switchboard.port (:8085) that
# forwards requests to the local llama.cpp server.  REMOTE_LLM_URL can be
# set via an EnvironmentFile to route to an external API instead.
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

    LLAMA_URL  = os.environ.get("LLAMA_CPP_URL", "${llamaUrl}")
    REMOTE_URL = os.environ.get("REMOTE_LLM_URL", "")
    PORT       = int(os.environ.get("PORT", "${toString swb.port}"))
    HOST       = os.environ.get("HOST", "127.0.0.1")

    app = FastAPI(title="AI Switchboard")

    @app.get("/health")
    async def health():
        upstream = REMOTE_URL if REMOTE_URL else LLAMA_URL
        return {"status": "ok", "upstream": upstream}

    @app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy(path: str, request: Request):
        target  = REMOTE_URL if REMOTE_URL else LLAMA_URL
        body    = await request.body()
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.request(
                method  = request.method,
                url     = f"{target}/v1/{path}",
                headers = headers,
                content = body,
                params  = dict(request.query_params),
            )
        return Response(
            content    = r.content,
            status_code = r.status_code,
            headers    = dict(r.headers),
        )

    if __name__ == "__main__":
        uvicorn.run(app, host=HOST, port=PORT)
  '';
in
{
  config = lib.mkIf (cfg.roles.aiStack.enable && swb.enable) {

    systemd.services.ai-switchboard = {
      description = "AI Switchboard — local/remote LLM routing proxy";
      wantedBy    = [ "multi-user.target" ];
      after       = [ "network-online.target" ];
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
