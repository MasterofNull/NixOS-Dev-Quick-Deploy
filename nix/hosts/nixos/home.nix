{ lib, pkgs, config, ... }:
# ---------------------------------------------------------------------------
# Per-host Home Manager module for the "nixos" host.
#
# Adds packages and configuration that the legacy templates/home.nix provided
# but which are missing from the minimal nix/home/base.nix base module.
# ---------------------------------------------------------------------------
let
  aiderPackage =
    if pkgs ? aider-chat then [ pkgs.aider-chat ]
    else if pkgs ? aider then [ pkgs.aider ]
    else [ ];

  # Guard each vscode-extension so a missing entry in pkgs.vscode-extensions
  # doesn't abort the build — emit a warning instead via lib.optional.
  vsExt = scope: name:
    lib.optionals
      (pkgs ? vscode-extensions
        && pkgs.vscode-extensions ? ${scope}
        && pkgs.vscode-extensions.${scope} ? ${name})
      [ pkgs.vscode-extensions.${scope}.${name} ];
in
{
  # ---- Additional packages --------------------------------------------------
  home.packages = with pkgs;
    [
      # Gitea + Tea CLI for local forge workflows
      gitea
      tea

      # Nix development / linting
      statix deadnix alejandra nixpkgs-fmt nil

      # Modern CLI replacements
      fzf bat eza dust duf

      # Container / image tooling (complements system podman)
      podman-tui

      # Git power-tools
      tig lazygit git-lfs git-crypt

      # Secrets
      age sops

      # Shell linting (used by VSCodium shellcheck extension)
      shellcheck

      # Markdown viewer for terminal
      glow
    ]
    ++ aiderPackage;

  # ---- VSCodium (declarative via programs.vscode) ---------------------------
  # The programs.vscode module handles:
  #   - writing settings to ~/.config/VSCodium/User/settings.json
  #   - linking extension packages into the VSCodium extensions directory
  #   - creating wrapper scripts with the correct PATH
  # Do NOT also create home.file.".config/VSCodium/User/settings.json" —
  # that would conflict with the managed file this module writes.
  programs.vscode = {
    enable  = true;
    package = pkgs.vscodium;

    # Allow the user to install extra extensions at runtime (from the Open VSX
    # registry or by dragging in .vsix files) without them being wiped on
    # home-manager switch.
    mutableExtensionsDir = true;

    # Extensions sourced from pkgs.vscode-extensions (nixpkgs).
    # Each entry is guarded so an extension absent from the current channel
    # is silently skipped rather than aborting the build.
    extensions =
      # ── Nix ──────────────────────────────────────────────────────────────
      vsExt "jnoortheen" "nix-ide"           # Nix language + nil LSP
      # ── Python ───────────────────────────────────────────────────────────
      ++ vsExt "ms-python"   "python"        # Python language support
      ++ vsExt "ms-python"   "debugpy"       # Python debugger
      ++ vsExt "ms-pyright"  "pyright"       # Static type checker
      # ── Go ───────────────────────────────────────────────────────────────
      ++ vsExt "golang"      "go"            # Go language support
      # ── Rust ─────────────────────────────────────────────────────────────
      ++ vsExt "rust-lang"   "rust-analyzer" # Rust LSP
      # ── Git / version control ─────────────────────────────────────────────
      ++ vsExt "eamodio"     "gitlens"       # Git supercharged
      ++ vsExt "mhutchie"    "git-graph"     # Git branch graph
      # ── AI coding assistant ───────────────────────────────────────────────
      ++ vsExt "continue"    "continue"      # Continue.dev (local LLM + Ollama)
      # ── Data / serialisation formats ─────────────────────────────────────
      ++ vsExt "redhat"      "vscode-yaml"
      ++ vsExt "tamasfe"     "even-better-toml"
      ++ vsExt "mechatroner" "rainbow-csv"
      # ── Shell scripting ───────────────────────────────────────────────────
      ++ vsExt "timonwong"   "shellcheck"    # Shell script linting
      # ── Formatting / editing quality-of-life ─────────────────────────────
      ++ vsExt "esbenp"      "prettier-vscode"
      ++ vsExt "streetsidesoftware" "code-spell-checker"
      # ── Markdown ─────────────────────────────────────────────────────────
      ++ vsExt "yzhang"      "markdown-all-in-one"
      # ── Docker / containers ───────────────────────────────────────────────
      ++ vsExt "ms-azuretools" "vscode-docker";

    userSettings = {
      # ── Editor ───────────────────────────────────────────────────────────
      "editor.fontSize"               = 14;
      "editor.tabSize"                = 2;
      "editor.insertSpaces"           = true;
      "editor.formatOnSave"           = true;
      "editor.formatOnPaste"          = false;
      "editor.minimap.enabled"        = false;
      "editor.wordWrap"               = "on";
      "editor.rulers"                 = [ 80 120 ];
      "editor.bracketPairColorization.enabled" = true;
      "editor.guides.bracketPairs"    = "active";
      "editor.inlineSuggest.enabled"  = true;
      "editor.suggestSelection"       = "first";

      # ── Files ─────────────────────────────────────────────────────────────
      "files.trimTrailingWhitespace"  = true;
      "files.insertFinalNewline"      = true;
      "files.trimFinalNewlines"       = true;
      "files.eol"                     = "\n";
      "files.autoSave"                = "onFocusChange";
      "files.exclude" = {
        "**/.git"              = true;
        "**/.DS_Store"         = true;
        "**/node_modules"      = true;
        "**/__pycache__"       = true;
        "**/.mypy_cache"       = true;
        "**/.ruff_cache"       = true;
        "**/result"            = true;  # nix build results
        "**/result-*"          = true;
      };

      # ── Terminal ──────────────────────────────────────────────────────────
      "terminal.integrated.defaultProfile.linux" = "zsh";
      "terminal.integrated.fontSize"             = 13;
      "terminal.integrated.scrollback"           = 10000;

      # ── Workbench ─────────────────────────────────────────────────────────
      "workbench.colorTheme"          = "Default Dark Modern";
      "workbench.iconTheme"           = "vs-seti";
      "workbench.startupEditor"       = "none";
      "workbench.editor.enablePreview" = false;

      # ── Nix (jnoortheen.nix-ide + nil LSP) ───────────────────────────────
      # nil is in home.packages (nix/hosts/nixos/home.nix) and in the base
      # system packages; alejandra is used for formatting.
      "nix.enableLanguageServer"                 = true;
      "nix.serverPath"                           = "nil";
      "nix.serverSettings".nil.formatting.command = [ "alejandra" ];
      "[nix]"."editor.defaultFormatter"          = "jnoortheen.nix-ide";

      # ── Python ────────────────────────────────────────────────────────────
      "python.defaultInterpreterPath"  = "python3";
      "python.analysis.typeCheckingMode" = "basic";
      "[python]"."editor.defaultFormatter" = "ms-python.python";

      # ── Go ────────────────────────────────────────────────────────────────
      "go.useLanguageServer"          = true;
      "go.toolsManagement.autoUpdate" = false;  # nixpkgs manages go tools
      "[go]"."editor.formatOnSave"    = true;
      "[go]"."editor.defaultFormatter" = "golang.go";

      # ── Rust ──────────────────────────────────────────────────────────────
      "rust-analyzer.checkOnSave.command"     = "clippy";
      "rust-analyzer.inlayHints.enable"       = true;
      "[rust]"."editor.defaultFormatter"      = "rust-lang.rust-analyzer";

      # ── YAML ──────────────────────────────────────────────────────────────
      "[yaml]"."editor.defaultFormatter"      = "redhat.vscode-yaml";
      "yaml.validate"                         = true;

      # ── Continue.dev — wired to local Ollama (port 11434) ─────────────────
      # Open WebUI is on :3000; continue talks directly to ollama on :11434.
      # Model selection happens inside the Continue UI; this sets the default
      # provider so it works out of the box after first launch.
      "continue.telemetryEnabled"             = false;

      # ── Git ───────────────────────────────────────────────────────────────
      "git.enableSmartCommit"                 = true;
      "git.confirmSync"                       = false;
      "git.autofetch"                         = true;
      "gitlens.telemetry.enabled"             = false;

      # ── Shell ─────────────────────────────────────────────────────────────
      "shellcheck.enable"                     = true;
      "shellcheck.executablePath"             = "shellcheck";

      # ── Prettier ──────────────────────────────────────────────────────────
      "[javascript]"."editor.defaultFormatter"    = "esbenp.prettier-vscode";
      "[typescript]"."editor.defaultFormatter"    = "esbenp.prettier-vscode";
      "[json]"."editor.defaultFormatter"          = "esbenp.prettier-vscode";
      "[jsonc]"."editor.defaultFormatter"         = "esbenp.prettier-vscode";
      "[markdown]"."editor.defaultFormatter"      = "yzhang.markdown-all-in-one";

      # ── Telemetry — disable all ────────────────────────────────────────────
      "telemetry.telemetryLevel"              = "off";
      "redhat.telemetry.enabled"              = false;

      # ── Update — disabled (nixpkgs manages VSCodium version) ─────────────
      "update.mode"                           = "none";
    };
  };

  # ---- VSCodium launch wrapper ---------------------------------------------
  # Ensures PATH includes nix-provided tools (language servers, linters) so
  # extensions can find them even when launched from the COSMIC app launcher
  # rather than a terminal session.
  home.file.".local/bin/code-nix" = {
    executable = true;
    text = let
      toolPath = lib.makeBinPath (with pkgs; [
        nil alejandra deadnix statix   # Nix tooling
        shellcheck                      # Shell linting
        python3                         # Python runtime
        go                              # Go runtime
        cargo                           # Rust tooling
      ]);
    in ''
      #!/usr/bin/env bash
      # VSCodium wrapper — ensures nix-provided tools are on PATH.
      # Use this instead of the bare 'codium' command when launching from
      # scripts or other desktop integrations that may have a stripped PATH.
      export PATH="${toolPath}:$PATH"
      exec ${pkgs.vscodium}/bin/codium "$@"
    '';
  };

  # ---- NPM global prefix (needed for AI CLI wrappers) ----------------------
  home.sessionVariables = {
    NPM_CONFIG_PREFIX = "$HOME/.npm-global";
    # AI tool defaults
    AIDER_DEFAULT_MODEL = "gpt-4o-mini";
    AIDER_LOG_DIR = "$HOME/.local/share/aider/logs";
    # Point AI tools at local Ollama when available
    OLLAMA_HOST = "http://127.0.0.1:11434";
  };

  # ---- Session PATH additions -----------------------------------------------
  home.sessionPath = [
    "$HOME/.npm-global/bin"
    "$HOME/.local/bin"
  ];

  # ---- NPM config (.npmrc) --------------------------------------------------
  home.file.".npmrc".text = "prefix=\${HOME}/.npm-global\n";

  # ---- Aider default config -------------------------------------------------
  home.file.".config/aider/config.toml".text = ''
    # Aider configuration tailored for NixOS & Gitea workflows
    [core]
    auto_commits = false
    dirty_commits = false
    auto_lint = true
  '';

  # ---- Continue.dev config — Ollama backend --------------------------------
  # Writes a minimal config.json on first activation only (idempotent).
  # Using home.activation rather than home.file so the user can edit the
  # file directly without home-manager clobbering their changes on switch.
  home.activation.createContinueConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if [ ! -f "$HOME/.continue/config.json" ]; then
      mkdir -p "$HOME/.continue"
      cat > "$HOME/.continue/config.json" << 'CONTINUE_EOF'
{
  "models": [
    {
      "title": "Ollama (local)",
      "provider": "ollama",
      "model": "qwen2.5-coder:7b",
      "apiBase": "http://127.0.0.1:11434"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Ollama autocomplete",
    "provider": "ollama",
    "model": "qwen2.5-coder:7b",
    "apiBase": "http://127.0.0.1:11434"
  },
  "allowAnonymousTelemetry": false
}
CONTINUE_EOF
    fi
  '';
}
