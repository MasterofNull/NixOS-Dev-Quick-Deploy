{ lib, pkgs, config, ... }:
# ---------------------------------------------------------------------------
# Home Manager base module — applies to every user on every host.
#
# Provides:
#   - Shell: zsh with history, completion, aliases, and Powerlevel10k prompt
#   - Core dev tools: git, ripgrep, fd, jq, btop, nix utilities
#   - XDG user directories
#   - Direnv: automatic .envrc / nix develop shell loading
#   - SSH client defaults
#   - VSCodium: declarative extensions, settings, wrapper, Continue.dev config
#
# Per-host customisation goes in nix/hosts/<host>/home.nix.
# ---------------------------------------------------------------------------
let
  # Guard helper — silently skips an extension when its scope or name is
  # absent from pkgs.vscode-extensions (e.g. older or slimmer channels).
  vsExt = scope: name:
    lib.optionals
      (pkgs ? vscode-extensions
        && pkgs.vscode-extensions ? ${scope}
        && pkgs.vscode-extensions.${scope} ? ${name})
      [ pkgs.vscode-extensions.${scope}.${name} ];

  # Nix store paths for tools the code-nix wrapper needs on its PATH.
  # These packages are in home.packages below so they're always present.
  vsWrapperPath = lib.makeBinPath (with pkgs; [
    nil alejandra deadnix statix   # Nix LSP + formatters
    shellcheck                      # Shell script linting
    python3                         # Python runtime
    go                              # Go runtime
    cargo                           # Rust toolchain
  ]);
in
{
  home.stateVersion = "25.11";
  programs.home-manager.enable = true;

  # ---- XDG user directories -----------------------------------------------
  xdg = {
    enable = true;
    userDirs = {
      enable            = true;
      createDirectories = true;
      desktop    = "${config.home.homeDirectory}/Desktop";
      documents  = "${config.home.homeDirectory}/Documents";
      download   = "${config.home.homeDirectory}/Downloads";
      music      = "${config.home.homeDirectory}/Music";
      pictures   = "${config.home.homeDirectory}/Pictures";
      publicShare = "${config.home.homeDirectory}/Public";
      templates  = "${config.home.homeDirectory}/Templates";
      videos     = "${config.home.homeDirectory}/Videos";
    };
  };

  # ---- Core user packages -------------------------------------------------
  home.packages = with pkgs; [
    # Search / text processing
    ripgrep fd jq yq-go

    # Archives
    unzip p7zip

    # Network
    wget curl socat

    # System inspection / modern CLI tools
    htop btop lsof pciutils usbutils nvme-cli smartmontools
    eza bat dust duf

    # Core dev/tooling runtimes (critical for quick-deploy workflows)
    git gh tree file xxd
    nodejs go cargo ruby
    # vscodium is installed via programs.vscode below; listing it here too
    # would create a duplicate entry in the nix profile.
    neovim kubectl

    # Nix utilities
    nix-tree nix-diff nvd

    # Nix tooling — also on the VSCodium wrapper PATH (vsWrapperPath above)
    nil alejandra deadnix statix

    # Shell linting — used by the shellcheck VSCodium extension
    shellcheck

    # Terminal markdown viewer
    glow

    # Python AI/dev toolchain expected by system health checks
    (python3.withPackages (ps: with ps; [
      pandas
      numpy
      ps."scikit-learn"
      torch
      openai
      anthropic
      langchain
      ps."qdrant-client"
      ps."sentence-transformers"
      polars
      black
      ruff
      mypy
      pytest
      jupyterlab
      notebook
      transformers
      accelerate
      datasets
      tensorflow
      # `llama-index` and `llama-index-cli` currently install the same
      # `bin/llamaindex-cli` entrypoint, which breaks buildEnv with a path
      # collision during Home Manager activation.
      # Install llama-index via project-local virtualenv/pip when needed.
      chromadb
      faiss
      dask
      gradio
    ]))

    # Lightweight fallback editor (override in per-host home.nix)
    micro
  ];

  # ---- Git -----------------------------------------------------------------
  programs.git = {
    enable = true;
    settings = {
      user.name = lib.mkDefault "NixOS User";
      user.email = lib.mkDefault "user@localhost";
      init.defaultBranch = "main";
      pull.rebase = true;
      push.autoSetupRemote = true;
      core.autocrlf = "input";
      diff.colorMoved = "default";
    };
  };

  # ---- Zsh ----------------------------------------------------------------
  programs.zsh = {
    enable                    = true;
    autosuggestion.enable     = true;
    syntaxHighlighting.enable = true;
    enableCompletion          = true;
    history = {
      size       = 50000;
      save       = 50000;
      ignoreDups = true;
      share      = true;
      extended   = true;
    };
    shellAliases = {
      ll  = "ls -lah";
      la  = "ls -A";
      gs  = "git status";
      gd  = "git diff";
      gl  = "git log --oneline --graph --decorate -20";
      # NixOS rebuild shortcuts
      nrs = "sudo nixos-rebuild switch --flake .";
      nrb = "sudo nixos-rebuild boot --flake .";
      nrd = "sudo nixos-rebuild dry-build --flake .";
      hms = "home-manager switch --flake .";
    };

    initContent = ''
      # Powerlevel10k instant prompt (must stay near the top of init).
      if [[ -r "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh" ]]; then
        source "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh"
      fi

      # Prefer Powerlevel10k for this workstation baseline.
      source ${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k/powerlevel10k.zsh-theme
      [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
    '';
  };

  # Health checks require this marker and users can still rerun `p10k configure`
  # at any time to regenerate ~/.p10k.zsh interactively.
  home.file.".config/p10k/.configured".text = ''
    managed-by-home-manager
  '';

  # Remove legacy Starship bootstrap lines from pre-migration ~/.zshrc files.
  # Prompt is managed by Powerlevel10k in this repository baseline.
  home.activation.removeLegacyStarshipBootstrap = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    zshrc="$HOME/.zshrc"
    if [ -f "$zshrc" ] && [ ! -L "$zshrc" ]; then
      ${pkgs.gnused}/bin/sed -i \
        -e '/\.nix-profile\/bin\/starship/d' \
        -e '/starship init zsh/d' \
        "$zshrc"
    fi
  '';

  # Default prompt config so fresh systems render cleanly before first manual tune.
  home.file.".p10k.zsh".text = ''
    typeset -g POWERLEVEL9K_LEFT_PROMPT_ELEMENTS=(dir vcs)
    typeset -g POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=(status command_execution_time background_jobs time)
    typeset -g POWERLEVEL9K_MODE=nerdfont-complete
    typeset -g POWERLEVEL9K_PROMPT_ADD_NEWLINE=true
    (( ''${+functions[p10k]} )) && p10k reload
  '';


  # ---- Direnv: auto-activate nix develop environments --------------------
  programs.direnv = {
    enable            = true;
    nix-direnv.enable = true;
  };

  # ---- SSH client ---------------------------------------------------------
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    matchBlocks."*" = {
      addKeysToAgent = "yes";
      serverAliveInterval = 60;
      serverAliveCountMax = 3;
      extraOptions = {
        HashKnownHosts = "yes";
      };
    };
  };

  # ---- Session variables --------------------------------------------------
  home.sessionVariables = {
    EDITOR  = "micro";
    VISUAL  = "micro";
    PAGER   = "less";
    LESS    = "-FRX";
  };

  home.sessionVariablesExtra = ''
    if [ -f /etc/rancher/k3s/k3s.yaml ]; then
      export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    fi
  '';

  # =========================================================================
  # VSCodium — declarative extensions, settings, wrapper, Continue.dev
  #
  # Applies to every host/profile because VSCodium ships in all three
  # profileData.systemPackageNames lists (ai-dev, gaming, minimal).
  # Per-host home.nix files may extend userSettings or add extensions via
  # programs.vscode.profiles.default.* using the same vsExt guard pattern.
  # =========================================================================

  # ---- programs.vscode (vscodium) -----------------------------------------
  # The module writes ~/.config/VSCodium/User/settings.json and links
  # extensions into the VSCodium extensions directory.
  # Do NOT create home.file.".config/VSCodium/User/settings.json" in any
  # other module — that would conflict with this managed file.
  programs.vscode = {
    enable  = true;
    package = pkgs.vscodium;

    # mutableExtensionsDir = true lets users install extra extensions at
    # runtime (Open VSX, .vsix drag-drop) without losing them on switch.
    mutableExtensionsDir = true;

    profiles.default = {
      extensions =
        # ── Nix ────────────────────────────────────────────────────────────
        vsExt "jnoortheen" "nix-ide"            # Nix language + nil LSP
        # ── Python ─────────────────────────────────────────────────────────
        ++ vsExt "ms-python"   "python"         # Python language support
        ++ vsExt "ms-python"   "black-formatter" # Python formatter
        ++ vsExt "ms-python"   "vscode-pylance"  # Python language server
        ++ vsExt "ms-python"   "debugpy"        # Python debugger
        ++ vsExt "ms-toolsai"  "jupyter"        # Notebooks
        ++ vsExt "ms-toolsai"  "jupyter-keymap"
        ++ vsExt "ms-toolsai"  "jupyter-renderers"
        ++ vsExt "ms-pyright"  "pyright"        # Static type checker
        # ── Go ─────────────────────────────────────────────────────────────
        ++ vsExt "golang"      "go"             # Go language support
        # ── Rust ───────────────────────────────────────────────────────────
        ++ vsExt "rust-lang"   "rust-analyzer"  # Rust LSP
        # ── Git / version control ──────────────────────────────────────────
        ++ vsExt "eamodio"     "gitlens"        # Git supercharged
        ++ vsExt "mhutchie"    "git-graph"      # Git branch graph
        # ── AI coding assistant ────────────────────────────────────────────
        ++ vsExt "anthropic"   "claude-code"    # Claude Code
        ++ vsExt "openai"      "gpt-codex"      # OpenAI Codex
        ++ vsExt "openai"      "codex-ide"      # OpenAI Codex IDE
        ++ vsExt "google"      "geminicodeassist" # Gemini Code Assist
        ++ vsExt "googlecloudtools" "gemini-code-assist" # Gemini Code Assist (alt id)
        ++ vsExt "continue"    "continue"       # Continue.dev → local Ollama
        ++ vsExt "codeium"     "codeium"        # Codeium
        ++ vsExt "kombai"      "kombai"         # Kombai
        # ── Data / serialisation formats ───────────────────────────────────
        ++ vsExt "redhat"      "vscode-yaml"
        ++ vsExt "tamasfe"     "even-better-toml"
        ++ vsExt "mechatroner" "rainbow-csv"
        # ── Shell scripting ─────────────────────────────────────────────────
        ++ vsExt "timonwong"   "shellcheck"     # Powered by shellcheck binary
        # ── Formatting / editing quality-of-life ───────────────────────────
        ++ vsExt "editorconfig" "editorconfig"
        ++ vsExt "esbenp"      "prettier-vscode"
        ++ vsExt "dbaeumer"    "vscode-eslint"
        ++ vsExt "usernamehw"  "errorlens"
        ++ vsExt "streetsidesoftware" "code-spell-checker"
        # ── Markdown ───────────────────────────────────────────────────────
        ++ vsExt "yzhang"      "markdown-all-in-one"
        # ── Docker / containers ─────────────────────────────────────────────
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
        "**/.git"        = true;
        "**/.DS_Store"   = true;
        "**/node_modules" = true;
        "**/__pycache__" = true;
        "**/.mypy_cache" = true;
        "**/.ruff_cache" = true;
        "**/result"      = true;   # nix build results
        "**/result-*"    = true;
      };

      # ── Terminal ──────────────────────────────────────────────────────────
      "terminal.integrated.defaultProfile.linux" = "zsh";
      "terminal.integrated.fontSize"             = 13;
      "terminal.integrated.scrollback"           = 10000;

      # ── Workbench ─────────────────────────────────────────────────────────
      "workbench.colorTheme"           = "Default Dark Modern";
      "workbench.iconTheme"            = "vs-seti";
      "workbench.startupEditor"        = "none";
      "workbench.editor.enablePreview" = false;

      # ── Nix (jnoortheen.nix-ide + nil LSP) ───────────────────────────────
      "nix.enableLanguageServer"                  = true;
      "nix.serverPath"                            = "nil";
      "nix.serverSettings".nil.formatting.command = [ "alejandra" ];
      "[nix]"."editor.defaultFormatter"           = "jnoortheen.nix-ide";

      # ── Python ────────────────────────────────────────────────────────────
      "python.defaultInterpreterPath"       = "python3";
      "python.analysis.typeCheckingMode"    = "basic";
      "[python]"."editor.defaultFormatter" = "ms-python.python";

      # ── Go ────────────────────────────────────────────────────────────────
      "go.useLanguageServer"           = true;
      "go.toolsManagement.autoUpdate"  = false;   # nixpkgs manages go tools
      "[go]"."editor.formatOnSave"     = true;
      "[go]"."editor.defaultFormatter" = "golang.go";

      # ── Rust ──────────────────────────────────────────────────────────────
      "rust-analyzer.checkOnSave.command"  = "clippy";
      "rust-analyzer.inlayHints.enable"    = true;
      "[rust]"."editor.defaultFormatter"   = "rust-lang.rust-analyzer";

      # ── YAML ──────────────────────────────────────────────────────────────
      "[yaml]"."editor.defaultFormatter"   = "redhat.vscode-yaml";
      "yaml.validate"                      = true;

      # ── Continue.dev — wired to local Ollama (port 11434) ─────────────────
      "continue.telemetryEnabled"          = false;

      # ── Git ───────────────────────────────────────────────────────────────
      "git.enableSmartCommit"              = true;
      "git.confirmSync"                    = false;
      "git.autofetch"                      = true;
      "gitlens.telemetry.enabled"          = false;

      # ── Shell ─────────────────────────────────────────────────────────────
      "shellcheck.enable"                  = true;
      "shellcheck.executablePath"          = "shellcheck";

      # ── Prettier ──────────────────────────────────────────────────────────
      "[javascript]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
      "[typescript]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
      "[json]"."editor.defaultFormatter"       = "esbenp.prettier-vscode";
      "[jsonc]"."editor.defaultFormatter"      = "esbenp.prettier-vscode";
      "[markdown]"."editor.defaultFormatter"   = "yzhang.markdown-all-in-one";

      # ── Telemetry — all off ────────────────────────────────────────────────
      "telemetry.telemetryLevel"           = "off";
      "redhat.telemetry.enabled"           = false;

      # ── Auto-update — disabled (nixpkgs manages VSCodium version) ─────────
      "update.mode"                        = "none";
      };
    };
  };

  # Keep VSCodium settings mutable across Home Manager switches:
  # 1) snapshot writable user settings before the symlink stage
  # 2) restore after the symlink stage so settings.json remains editable
  home.activation.backupVscodiumMutableSettings = lib.hm.dag.entryBefore [ "writeBoundary" ] ''
    settings_file="$HOME/.config/VSCodium/User/settings.json"
    state_dir="$HOME/.local/share/nixos-quick-deploy/state/vscodium"
    backup_file="$state_dir/settings.json"

    mkdir -p "$state_dir"

    if [ -f "$settings_file" ] && [ ! -L "$settings_file" ]; then
      cp -f "$settings_file" "$backup_file"
    fi
  '';

  home.activation.restoreVscodiumMutableSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    settings_dir="$HOME/.config/VSCodium/User"
    settings_file="$settings_dir/settings.json"
    state_dir="$HOME/.local/share/nixos-quick-deploy/state/vscodium"
    backup_file="$state_dir/settings.json"

    mkdir -p "$settings_dir" "$state_dir"

    if [ -f "$backup_file" ]; then
      rm -f "$settings_file"
      cp -f "$backup_file" "$settings_file"
      chmod u+rw "$settings_file" 2>/dev/null || true
    elif [ -L "$settings_file" ]; then
      resolved_settings="$(readlink -f "$settings_file" 2>/dev/null || true)"
      if [ -n "$resolved_settings" ] && [ -f "$resolved_settings" ]; then
        rm -f "$settings_file"
        cp -f "$resolved_settings" "$settings_file"
        chmod u+rw "$settings_file" 2>/dev/null || true
      fi
    fi

    if [ -f "$settings_file" ] && [ ! -L "$settings_file" ]; then
      cp -f "$settings_file" "$backup_file"
    fi
  '';

  # ---- VSCodium launch wrapper ---------------------------------------------
  # Prepends Nix-managed tool paths so language servers and linters work when
  # VSCodium is launched from the COSMIC app launcher (stripped PATH) rather
  # than a shell session that sources ~/.nix-profile/etc/profile.d/hm-session-vars.sh.
  home.file.".local/bin/code-nix" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      # VSCodium wrapper — prepends nix-managed tool paths.
      export PATH="${vsWrapperPath}:$PATH"
      exec ${pkgs.vscodium}/bin/codium "$@"
    '';
  };

  # ---- Flatpak user-scope Flathub remote --------------------------------------
  # Ensures the Flathub remote exists at user scope so sync-flatpak-profile.sh
  # --scope user (the default) can install apps without system-level privileges.
  # Running at user scope means no polkit prompts and no system-scope installs,
  # which prevents duplicate app entries in the COSMIC launcher.
  home.activation.addFlathubUserRemote = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if command -v flatpak >/dev/null 2>&1; then
      flatpak remote-add --user --if-not-exists flathub \
        https://dl.flathub.org/repo/flathub.flatpakrepo 2>/dev/null || true
    fi
  '';

  # ---- Continue.dev config — llama.cpp backend --------------------------------
  # Written once on first activation; not managed as a symlink so the user
  # can edit it without home-manager clobbering their changes on switch.
  # Points at the llama-server OpenAI-compatible API on :8080.
  home.activation.createContinueConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if [ ! -f "$HOME/.continue/config.json" ]; then
      mkdir -p "$HOME/.continue"
      cat > "$HOME/.continue/config.json" << 'CONTINUE_EOF'
{
  "models": [
    {
      "title": "llama.cpp (local :8080)",
      "provider": "openai",
      "apiKey": "dummy",
      "apiBase": "http://127.0.0.1:8080/v1"
    }
  ],
  "tabAutocompleteModel": {
    "title": "llama.cpp autocomplete",
    "provider": "openai",
    "apiKey": "dummy",
    "apiBase": "http://127.0.0.1:8080/v1",
    "model": "local-model"
  },
  "allowAnonymousTelemetry": false
}
CONTINUE_EOF
    fi
  '';
}
