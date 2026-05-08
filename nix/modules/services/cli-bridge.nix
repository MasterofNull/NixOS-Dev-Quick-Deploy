{
  lib,
  config,
  pkgs,
  ...
}:
# ---------------------------------------------------------------------------
# CLI Bridge — OAuth-backed Claude / Codex HTTP endpoint
#
# Provides an OpenAI-compatible /v1/chat/completions endpoint that calls
# the `claude --print` and `codex exec` CLIs.  Authentication is handled
# by each CLI's own OAuth keychain — no API keys stored anywhere in Nix.
#
# Activated when:
#   mySystem.aiStack.cliBridge.enable = true
# ---------------------------------------------------------------------------
let
  cfg = config.mySystem;
  ai = cfg.aiStack;
  bridge = ai.cliBridge;
  primaryUser = cfg.primaryUser;

  bridgePython = pkgs.python3.withPackages (ps: with ps; [ fastapi uvicorn ]);
  bridgeScript = pkgs.writeText "ai-cli-bridge.py"
    (builtins.readFile ../../../ai-stack/cli-bridge/claude_bridge.py);
in
{
  config = lib.mkIf (cfg.roles.aiStack.enable && bridge.enable) {

    systemd.services.ai-cli-bridge = {
      description = "AI CLI bridge (OAuth-backed Claude/Codex completions)";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];

      serviceConfig = {
        ExecStart = lib.escapeShellArgs [
          "${bridgePython}/bin/python3"
          bridgeScript
        ];

        # Run as the primary user so the CLI tools can reach their OAuth
        # credentials in ~/.claude/ and ~/.codex/.
        User = primaryUser;
        Group = "users";

        # Allow read-write under HOME so CLIs can update auth caches.
        ProtectHome = "no";

        # PATH must include user-local bin directories where claude/codex live.
        Environment = [
          "CLI_BRIDGE_PORT=${toString bridge.port}"
          "CLI_BRIDGE_HOST=127.0.0.1"
          "CLI_BRIDGE_TIMEOUT_S=${toString bridge.timeoutSeconds}"
          "CLI_BRIDGE_WORKSPACE_ROOT=${cfg.mcpServers.repoPath}"
          "HOME=/home/${primaryUser}"
          "PATH=/home/${primaryUser}/.local/bin:/home/${primaryUser}/.npm-global/bin:/run/current-system/sw/bin:/usr/bin:/bin"
        ] ++ lib.optional (bridge.claudeBin != "") "CLAUDE_BIN=${bridge.claudeBin}"
          ++ lib.optional (bridge.codexBin  != "") "CODEX_BIN=${bridge.codexBin}";

        WorkingDirectory = cfg.mcpServers.repoPath;

        Restart = "on-failure";
        RestartSec = "10s";

        PrivateTmp = true;
        ProtectSystem = "strict";
        ReadWritePaths = [ "/home/${primaryUser}" "/tmp" ];
        NoNewPrivileges = true;
        MemoryMax = "512M";
        RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
      };
    };

  };
}
