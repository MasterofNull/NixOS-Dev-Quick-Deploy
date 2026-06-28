{
  lib,
  config,
  pkgs,
  ...
}: let
  cfg = config.mySystem;
  cdev = cfg.roles.cppDev;

  llvm = pkgs.llvmPackages_22 or pkgs.llvmPackages;

  # Core build tools — available system-wide so agents don't need a devShell
  buildTools = with pkgs; [
    cmake
    ninja
    pkg-config
    ccache
    gnumake
    git
  ];

  # Clang toolchain — clang-format, clang-tidy, clangd all in one package
  clangTools = [
    llvm.clang-tools
  ];

  # Debuggers and memory analysers
  debugTools = with pkgs; [
    gdb
    llvm.lldb
    valgrind
    heaptrack # heap profiler with flamegraph output
    strace
    ltrace
  ];

  # Static analysis
  analysisTools = with pkgs; [
    cppcheck
    include-what-you-use
  ];

  # Qt dev helpers (lightweight; full Qt env stays in the project devShell)
  qtTools = with pkgs; [
    qt6.qttools # qdoc, qdbusviewer, designer
    qtcreator
  ];

  # Java — required to run NeoForge/Fabric Minecraft servers during testing
  javaTools = lib.optionals cdev.enableJava [
    pkgs.jdk21
  ];

  allPackages =
    buildTools
    ++ clangTools
    ++ debugTools
    ++ analysisTools
    ++ javaTools
    ++ lib.optionals cdev.enableQtTools qtTools;

  leanCtxBin = "/run/current-system/sw/bin/lean-ctx";
  user = cfg.primaryUser;
  claudeJson = "/home/${user}/.claude.json";
in {
  # ---------------------------------------------------------------------------
  # C++ / Qt Development Role
  #
  # Provides a system-wide C++ toolchain so every agent and shell session can
  # run cmake, clang-tidy, gdb, valgrind, and cppcheck without entering a
  # project-specific nix develop shell.
  #
  # Also declaratively registers lean-ctx as an MCP server in ~/.claude.json
  # so the registration survives home-directory wipes and new-machine deploys.
  #
  # Activated when: mySystem.roles.cppDev.enable = true
  # ---------------------------------------------------------------------------

  options.mySystem.roles.cppDev = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable system-wide C++/Qt development toolchain.";
    };

    enableJava = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Install JDK 21 system-wide.
        Required for running NeoForge/Fabric Minecraft servers during
        PrismLauncher server-pack testing without entering a devShell.
      '';
    };

    enableQtTools = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Install Qt Designer and QtCreator.
        Off by default; the project devShell already provides the full Qt env.
      '';
    };

    declareLeanCtxMcp = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Declaratively register lean-ctx as an MCP server in ~/.claude.json on
        every nixos-rebuild switch.  Idempotent — only writes when the entry is
        absent, and merges rather than replacing the file.
      '';
    };

    ccacheSizeGb = lib.mkOption {
      type = lib.types.int;
      default = 10;
      description = "Maximum ccache cache size in GiB.";
    };
  };

  config = lib.mkIf cdev.enable {
    # ── System packages ──────────────────────────────────────────────────────
    environment.systemPackages = allPackages;

    # ── Session environment ───────────────────────────────────────────────────
    environment.sessionVariables = {
      # Point build systems to the shared ccache directory
      CCACHE_DIR = "/var/cache/ccache-cpp";
      CCACHE_MAXSIZE = "${toString cdev.ccacheSizeGb}G";
      # Make clangd find compile_commands.json one directory up by default
      CLANGD_FLAGS = "--compile-commands-dir=build";
    };

    # ── ccache directory ─────────────────────────────────────────────────────
    systemd.tmpfiles.rules = [
      "d /var/cache/ccache-cpp 0775 ${user} users -"
    ];

    # ── File descriptor limits (large C++ projects need many open files) ─────
    security.pam.loginLimits = [
      {
        domain = user;
        type = "soft";
        item = "nofile";
        value = "65536";
      }
      {
        domain = user;
        type = "hard";
        item = "nofile";
        value = "524288";
      }
    ];

    # ── Declarative lean-ctx MCP registration ────────────────────────────────
    # Merges the lean-ctx entry into ~/.claude.json on every rebuild.
    # Idempotent: skips if the entry already exists.
    system.activationScripts.cppDevLeanCtxMcp = lib.mkIf cdev.declareLeanCtxMcp {
      deps = ["users"];
      text = ''
        CLAUDE_JSON="${claudeJson}"
        LEAN_CTX_BIN="${leanCtxBin}"
        PY3="${pkgs.python3}/bin/python3"

        if [ ! -f "$CLAUDE_JSON" ]; then
          # File absent — seed it with the lean-ctx entry only
          printf '{\n  "mcpServers": {\n    "lean-ctx": {\n      "command": "%s",\n      "args": [],\n      "type": "stdio"\n    }\n  }\n}\n' \
            "$LEAN_CTX_BIN" > "$CLAUDE_JSON"
          chown ${user}:users "$CLAUDE_JSON"
          chmod 600 "$CLAUDE_JSON"
          echo "cppDev: seeded $CLAUDE_JSON with lean-ctx MCP entry"
        else
          # File exists — merge only if lean-ctx is absent
          HAS_ENTRY=$("$PY3" -c "
import json, sys
try:
    d = json.load(open('$CLAUDE_JSON'))
    sys.exit(0 if 'lean-ctx' in d.get('mcpServers', {}) else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; echo $?)
          if [ "$HAS_ENTRY" != "0" ]; then
            "$PY3" - "$CLAUDE_JSON" "$LEAN_CTX_BIN" <<'PYEOF'
import json, sys
path, bin_path = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        d = json.load(f)
except (json.JSONDecodeError, OSError):
    d = {}
d.setdefault("mcpServers", {})["lean-ctx"] = {
    "command": bin_path,
    "args": [],
    "type": "stdio",
}
with open(path, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
PYEOF
            chown ${user}:users "$CLAUDE_JSON"
            echo "cppDev: merged lean-ctx MCP entry into $CLAUDE_JSON"
          fi
        fi
      '';
    };
  };
}
