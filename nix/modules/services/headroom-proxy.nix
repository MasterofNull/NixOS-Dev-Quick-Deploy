{
  lib,
  config,
  pkgs,
  ...
}:
# ---------------------------------------------------------------------------
# headroom-proxy — OpenAI-compatible context compression proxy
#
# Sits between switchboard and llama.cpp. Intercepts all chat/completions
# requests, compresses tool outputs / logs / RAG chunks before forwarding
# to the upstream LLM. Claims 60-95% payload reduction.
#
# Architecture:
#   switchboard (:8085) → headroom-proxy (:8787) → llama.cpp (:8080)
#
# Activated when:
#   mySystem.aiStack.headroomProxy.enable = true
#
# PACKAGING NOTE (Phase 164 Stage C):
#   headroom-ai's Python dependencies include litellm ≥1.86.2, magika, and
#   sqlite-vec, which are either absent from nixpkgs-25.11 or pinned to older
#   versions. Options for completing the NixOS packaging:
#     a) Wait for nixpkgs to update litellm and add the missing packages.
#     b) Use poetry2nix / dream2nix with the headroom pyproject.toml.
#     c) Add the missing packages as local fetchPypi derivations (tedious).
#   Until then the service is defined but the headroomPython env below must
#   be completed by the operator. The options, service unit, and switchboard
#   wiring are fully functional once a correct Python env is provided.
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  ai = cfg.aiStack;
  hp = ai.headroomProxy;

  active = cfg.roles.aiStack.enable && hp.enable;

  llamaUpstream = "http://${ai.llamaCpp.host}:${toString ai.llamaCpp.port}";

  # ---------------------------------------------------------------------------
  # Python environment for headroom-ai[proxy]
  #
  # INCOMPLETE — see packaging note above. Replace the TODO comment below with
  # a complete `pkgs.python3.withPackages` expression once all deps are
  # resolvable. The placeholder produces an empty env so the service fails
  # cleanly rather than silently.
  #
  # Minimal target env (all available in nixpkgs-25.11 or local derivations):
  #   pkgs.python3.withPackages (ps: with ps; [
  #     tiktoken pydantic click rich fastapi uvicorn httpx websockets zstandard
  #     watchdog opentelemetry-api onnxruntime transformers
  #     # Needs local derivation or nixpkgs update:
  #     # litellm (need ≥1.86.2; nixpkgs-25.11 ships 1.69.0)
  #     # magika
  #     # sqlite-vec
  #     # ast-grep-cli (Python package, different from the CLI tool)
  #     # openai (headroom requires ≥2.14.0)
  #     (headroomAiDerivation)   # TODO: add local fetchPypi derivation
  #   ])
  # ---------------------------------------------------------------------------
  headroomPython = pkgs.python3.withPackages (ps:
    with ps; [
      tiktoken
      pydantic
      click
      rich
      # TODO: add headroom-ai and remaining deps (see packaging note)
    ]
  );

in {
  config = lib.mkIf active {
    # ── systemd service ──────────────────────────────────────────────────────
    systemd.services.ai-headroom-proxy = {
      description = "headroom context-compression proxy for llama.cpp";
      after = [ "network.target" "ai-llama-cpp.service" ];
      requires = [ "ai-llama-cpp.service" ];
      wantedBy = [ "multi-user.target" ];

      environment = {
        # Route OpenAI-compatible requests to local llama.cpp
        OPENAI_TARGET_API_URL = llamaUpstream;
        HEADROOM_PORT = toString hp.port;
        HEADROOM_LOG_LEVEL = if hp.debug then "DEBUG" else "INFO";
      };

      serviceConfig = {
        Type = "simple";
        Restart = "on-failure";
        RestartSec = "5s";
        ExecStart = "${headroomPython}/bin/headroom proxy --port ${toString hp.port}";
        User = cfg.primaryUser;

        # Hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        PrivateTmp = true;
        PrivateDevices = true;
      };
    };

    # ── firewall ─────────────────────────────────────────────────────────────
    # headroom listens loopback-only; no firewall port needed for external access.
    # Add hp.port here if external access is ever required.
  };
}
