{ lib, pkgs, config, osConfig ? {}, ... }:
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
  systemConfig =
    if lib.hasAttrByPath [ "mySystem" ] osConfig
    then osConfig
    else config;
  aiSwitchboardPort = lib.attrByPath [ "mySystem" "aiStack" "switchboard" "port" ] 8085 systemConfig;
  aiLlamaPort = lib.attrByPath [ "mySystem" "aiStack" "llamaCpp" "port" ] 8080 systemConfig;
  aiHybridPort = lib.attrByPath [ "mySystem" "mcpServers" "hybridPort" ] 8003 systemConfig;
  aiAidbPort = lib.attrByPath [ "mySystem" "mcpServers" "aidbPort" ] 8002 systemConfig;
  aiAnthropicProxyPort = lib.attrByPath [ "ports" "anthropicProxy" ] 8120 systemConfig;
  aiOpenAIBaseUrl = "http://127.0.0.1:${toString aiSwitchboardPort}/v1";
  continueApiBase =
    if lib.attrByPath [ "mySystem" "aiStack" "switchboard" "enable" ] false systemConfig
    then aiOpenAIBaseUrl
    else "http://127.0.0.1:${toString aiLlamaPort}/v1";
  vscodiumPathValue = "${config.home.homeDirectory}/.local/bin:${config.home.homeDirectory}/.nix-profile/bin:/run/current-system/sw/bin:\${env:PATH}";
  vscodiumAiEnv = [
    { name = "PATH"; value = vscodiumPathValue; }
    { name = "OPENAI_BASE_URL"; value = aiOpenAIBaseUrl; }
    { name = "OPENAI_API_BASE"; value = aiOpenAIBaseUrl; }
    { name = "OPENAI_API_KEY"; value = "dummy"; }
    { name = "HYBRID_COORDINATOR_URL"; value = "http://127.0.0.1:${toString aiHybridPort}"; }
    { name = "AIDB_URL"; value = "http://127.0.0.1:${toString aiAidbPort}"; }
    { name = "ANTHROPIC_BASE_URL"; value = "http://127.0.0.1:${toString aiAnthropicProxyPort}"; }
  ];

  # openai.chatgpt — "Codex: OpenAI's coding agent" — not in nixpkgs 25.11;
  # packaged inline from Open VSX so it installs declaratively.
  openaiCodex = pkgs.vscode-utils.buildVscodeExtension {
    pname              = "openai-chatgpt";
    version            = "0.5.76";
    vscodeExtPublisher = "openai";
    vscodeExtName      = "chatgpt";
    vscodeExtUniqueId  = "openai.chatgpt";
    vscodeExtVersion   = "0.5.76";
    src = pkgs.fetchurl {
      url    = "https://open-vsx.org/api/openai/chatgpt/0.5.76/file/openai.chatgpt-0.5.76.vsix";
      sha256 = "0n0byvz2k5hjdnc48wn4fkhrvy8bam671ml19nfhk0b7wypmxmvz";
      # Rename .vsix → .zip so the stdenv unzip hook fires (same trick used
      # by pkgs/applications/editors/vscode/extensions/mktplcExtRefToFetchArgs.nix).
      name   = "openai-chatgpt.zip";
    };
  };

  # Google.geminicodeassist — "Gemini Code Assist" — not in nixpkgs 25.11;
  # packaged inline from Open VSX so it installs declaratively.
  geminiCodeAssist = pkgs.vscode-utils.buildVscodeExtension {
    pname              = "Google-geminicodeassist";
    version            = "2.72.0";
    vscodeExtPublisher = "Google";
    vscodeExtName      = "geminicodeassist";
    vscodeExtUniqueId  = "Google.geminicodeassist";
    vscodeExtVersion   = "2.72.0";
    src = pkgs.fetchurl {
      url    = "https://open-vsx.org/api/Google/geminicodeassist/2.72.0/file/Google.geminicodeassist-2.72.0.vsix";
      sha256 = "0bsqakrbkqfa4vlazvhaw50z5s5ijiqkh8xz225zsl53aiinq03z";
      name   = "Google-geminicodeassist.zip";
    };
  };

  # Qwen Code VSCode IDE Companion — QwenLM's official AI coding assistant
  # Not in nixpkgs 25.11; packaged from Open VSX for declarative install.
  qwenCodeCompanionSha256 = null;
  qwenCodeCompanion =
    if qwenCodeCompanionSha256 == null then
      null
    else
      pkgs.vscode-utils.buildVscodeExtension {
        pname              = "qwen-code-vscode-ide-companion";
        version            = "0.10.0";
        vscodeExtPublisher = "qwenlm";
        vscodeExtName      = "qwen-code-vscode-ide-companion";
        vscodeExtUniqueId  = "qwenlm.qwen-code-vscode-ide-companion";
        vscodeExtVersion   = "0.10.0";
        src = pkgs.fetchurl {
          url    = "https://open-vsx.org/api/qwenlm/qwen-code-vscode-ide-companion/0.10.0/file/qwenlm.qwen-code-vscode-ide-companion-0.10.0.vsix";
          sha256 = qwenCodeCompanionSha256;
          name   = "qwen-code-vscode-ide-companion.zip";
        };
      };

  cyberpunkThemeArchive = pkgs.runCommand "max-ss.cyberpunk-1.2.14.zip" {
    nativeBuildInputs = [ pkgs.zip ];
  } ''
    mkdir -p extension
    cp -R ${../../templates/vscode/max-ss.cyberpunk-1.2.14-universal}/. extension/
    ${pkgs.zip}/bin/zip -qr "$out" extension
  '';

  cyberpunkThemeExtension = pkgs.vscode-utils.buildVscodeExtension {
    pname              = "max-ss-cyberpunk-theme";
    version            = "1.2.14";
    vscodeExtPublisher = "max-SS";
    vscodeExtName      = "Cyberpunk";
    vscodeExtUniqueId  = "max-SS.Cyberpunk";
    vscodeExtVersion   = "1.2.14";
    src                = cyberpunkThemeArchive;
  };

  cosmicThemeDarkPalette = builtins.readFile (../../templates + "/Royal Wine.ron");
  cosmicWallpaperPath = "${config.home.homeDirectory}/.local/share/wallpapers/current-desktop-background.png";

  # Baseline VSCodium settings — written once on first activation as a
  # writable file so the user can save changes from within VSCodium.
  # After the first deploy, home-manager never touches settings.json again.
  vscodiumSettings = {
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
    "files.trimTrailingWhitespace"  = true;
    "files.insertFinalNewline"      = true;
    "files.trimFinalNewlines"       = true;
    "files.eol"                     = "\n";
    "files.autoSave"                = "onFocusChange";
    "files.exclude" = {
      "**/.git"         = true;
      "**/.DS_Store"    = true;
      "**/node_modules" = true;
      "**/__pycache__"  = true;
      "**/.mypy_cache"  = true;
      "**/.ruff_cache"  = true;
      "**/result"       = true;
      "**/result-*"     = true;
    };
    "terminal.integrated.defaultProfile.linux" = "zsh";
    "terminal.integrated.fontSize"             = 13;
    "terminal.integrated.scrollback"           = 10000;
    "workbench.colorTheme"           = "Activate SCARLET protocol (beta)";
    "workbench.preferredDarkColorTheme" = "Activate SCARLET protocol (beta)";
    "window.autoDetectColorScheme"   = false;
    "workbench.iconTheme"            = "vs-seti";
    "workbench.startupEditor"        = "none";
    "workbench.editor.enablePreview" = false;
    "nix.enableLanguageServer"                  = true;
    "nix.serverPath"                            = "nil";
    "nix.serverSettings".nil.formatting.command = [ "alejandra" ];
    "[nix]"."editor.defaultFormatter"           = "jnoortheen.nix-ide";
    "python.defaultInterpreterPath"       = "python3";
    "python.analysis.typeCheckingMode"    = "basic";
    "[python]"."editor.defaultFormatter" = "ms-python.python";
    "go.useLanguageServer"           = true;
    "go.toolsManagement.autoUpdate"  = false;
    "[go]"."editor.formatOnSave"     = true;
    "[go]"."editor.defaultFormatter" = "golang.go";
    "rust-analyzer.checkOnSave.command"  = "clippy";
    "rust-analyzer.inlayHints.enable"    = true;
    "[rust]"."editor.defaultFormatter"   = "rust-lang.rust-analyzer";
    "[yaml]"."editor.defaultFormatter"   = "redhat.vscode-yaml";
    "yaml.validate"                      = true;
    "continue.telemetryEnabled"          = false;
    "git.enableSmartCommit"              = true;
    "git.confirmSync"                    = false;
    "git.autofetch"                      = true;
    "gitlens.telemetry.enabled"          = false;
    "shellcheck.enable"                  = true;
    "shellcheck.executablePath"          = "shellcheck";
    "git.path"                           = "${config.programs.git.package}/bin/git";
    # Native installer puts the binary at ~/.local/bin/claude.  Use the
    # absolute path so the extension works when VSCodium is launched from
    # the desktop launcher (PATH may not include ~/.local/bin there).
    # CLI paths are declarative; no npm-global compatibility wrappers.

    "claude-code.executablePath"         = "${config.home.homeDirectory}/.local/bin/claude";
    "claude-code.claudeProcessWrapper"   = "${config.home.homeDirectory}/.local/bin/claude";
    "claude-code.environmentVariables"   = vscodiumAiEnv;
    "claude-code.autoStart"              = false;
    "claudeCode.executablePath"          = "${config.home.homeDirectory}/.local/bin/claude";
    "claudeCode.claudeProcessWrapper"    = "${config.home.homeDirectory}/.local/bin/claude";
    "claudeCode.environmentVariables"    = vscodiumAiEnv;
    "claudeCode.autoStart"               = false;
    "gpt-codex.executablePath"           = "codex";
    "gpt-codex.environmentVariables"     = vscodiumAiEnv;
    "gpt-codex.autoStart"                = false;
    "gptCodex.executablePath"            = "codex";
    "gptCodex.environmentVariables"      = vscodiumAiEnv;
    "gptCodex.autoStart"                 = false;
    "codex.executablePath"               = "codex";
    "codex.environmentVariables"         = vscodiumAiEnv;
    "codex.autoStart"                    = false;
    "codexIDE.executablePath"            = "codex";
    "codexIDE.environmentVariables"      = vscodiumAiEnv;
    "codexIDE.autoStart"                 = false;
    "codexIde.executablePath"            = "codex";
    "codexIde.environmentVariables"      = vscodiumAiEnv;
    "codexIde.autoStart"                 = false;
    "openai.executablePath"              = "openai";
    "openai.environmentVariables"        = vscodiumAiEnv;
    "openai.autoStart"                   = false;
    "[javascript]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
    "[typescript]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
    "[json]"."editor.defaultFormatter"       = "esbenp.prettier-vscode";
    "[jsonc]"."editor.defaultFormatter"      = "esbenp.prettier-vscode";
    "[markdown]"."editor.defaultFormatter"   = "yzhang.markdown-all-in-one";
    "telemetry.telemetryLevel"           = "off";
    "redhat.telemetry.enabled"           = false;
    "update.mode"                        = "none";
  };

  # Pre-serialised JSON written into the Nix store; the activation script
  # copies it to ~/.config/VSCodium/User/settings.json on first run only.
  vscodiumSettingsJSON = pkgs.writeText "vscodium-settings-baseline.json"
    (builtins.toJSON vscodiumSettings);

  # Guard helper — silently skips an extension when its scope or name is
  # absent from pkgs.vscode-extensions (e.g. older or slimmer channels).
  vsExt = scope: name:
    let
      hasScopes = pkgs ? vscode-extensions;
      scopeSet = if hasScopes then pkgs.vscode-extensions else { };
      hasScope = hasScopes && builtins.hasAttr scope scopeSet;
      extSet = if hasScope then builtins.getAttr scope scopeSet else { };
      hasName = hasScope && builtins.hasAttr name extSet;
    in
    lib.optionals hasName [ (builtins.getAttr name extSet) ];

  # Nix store paths for tools the code-nix wrapper needs on its PATH.
  # These packages are in home.packages below so they're always present.
  vsWrapperPath = lib.makeBinPath (with pkgs; [
    nil alejandra deadnix statix   # Nix LSP + formatters
    shellcheck                      # Shell script linting
    python3                         # Python runtime
    go                              # Go runtime
    cargo                           # Rust toolchain
    nodejs                          # Node.js runtime (required by AI extension language servers)
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
    # Declarative COSMIC Terminal font for proper Powerlevel10k glyph rendering.
    configFile."cosmic/com.system76.CosmicTerm/v1/font_name" = {
      text = "\"MesloLGS Nerd Font Mono\"";
      force = true;
    };
    configFile."cosmic/com.system76.CosmicTerm/v1/font_size" = {
      text = "13.0";
      force = true;
    };
    configFile."cosmic/com.system76.CosmicTheme.Dark/v1/palette" = {
      text = cosmicThemeDarkPalette;
      force = true;
    };
    configFile."cosmic/com.system76.CosmicTheme.Dark.Builder/v1/palette" = {
      text = cosmicThemeDarkPalette;
      force = true;
    };
    configFile."cosmic/com.system76.CosmicTheme.Mode/v1/is_dark" = {
      text = "true";
      force = true;
    };
    configFile."cosmic/com.system76.CosmicBackground/v1/same-on-all" = {
      text = "true";
      force = true;
    };
    configFile."cosmic/com.system76.CosmicSettings.Wallpaper/v1/custom-images" = {
      text = ''
        [
            "${cosmicWallpaperPath}",
        ]
      '';
      force = true;
    };
    configFile."cosmic/com.system76.CosmicBackground/v1/all" = {
      text = ''
        (
            output: "all",
            source: Path("${cosmicWallpaperPath}"),
            filter_by_theme: true,
            rotation_frequency: 300,
            filter_method: Lanczos,
            scaling_mode: Zoom,
            sampling_method: Alphanumeric,
        )
      '';
      force = true;
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
    # neovim is provided by system packages; avoid duplicate nvim.desktop.

    # Nix utilities
    nix-tree nix-diff nvd

    # Nix tooling — also on the VSCodium wrapper PATH (vsWrapperPath above)
    nil alejandra deadnix statix

    # Shell linting — used by the shellcheck VSCodium extension
    shellcheck

    # Nerd font required for Powerlevel10k glyphs in terminal prompts.
    nerd-fonts.meslo-lg

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
      ps."pytest-cov"
      ps."pytest-xdist"
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
      alias = {
        st = "status";
        co = "checkout";
        br = "branch";
        ci = "commit";
        unstage = "reset HEAD --";
        last = "log -1 HEAD";
        visual = "log --oneline --graph --decorate --all";
      };
    };
  };

  programs.gpg.enable = true;
  services.gpg-agent = {
    enable = true;
    enableSshSupport = false;
    enableExtraSocket = true;
    defaultCacheTtl = 3600;
    defaultCacheTtlSsh = 3600;
    pinentry.package = pkgs.pinentry-gnome3;
  };
  programs.password-store = {
    enable = true;
    package = pkgs.pass;
  };
  services.gnome-keyring = {
    enable = true;
    components = [
      "pkcs11"
      "secrets"
      "ssh"
    ];
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

    # mkOrder 550 places this block before compinit (priority 550 = "before
    # completion init" in home-manager 25.11's lines-based initContent ordering).
    # P10K instant prompt must run before compinit and any terminal output.
    initContent = lib.mkOrder 550 ''
      # Powerlevel10k instant prompt — must run before compinit and any output.
      if [[ -r "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh" ]]; then
        source "''${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-''${(%):-%n}.zsh"
      fi

      # Load Powerlevel10k theme and user config.
      source ${pkgs.zsh-powerlevel10k}/share/zsh-powerlevel10k/powerlevel10k.zsh-theme

      # First interactive shell after switch: run wizard, then run
      # `p10k configure` to generate ~/.p10k.zsh (wizard only writes vars).
      if [[ -o interactive ]] && [[ -t 0 ]] && [[ -t 1 ]] && [[ -f "$HOME/.config/p10k/.pending-first-run" || ! -f "$HOME/.p10k.zsh" ]]; then
        mkdir -p "$HOME/.config/p10k"
        _p10k_marker="$HOME/.config/p10k/.configured"
        _p10k_wizard="$HOME/.local/bin/p10k-setup-wizard.sh"
        _p10k_pending="$HOME/.config/p10k/.pending-first-run"
        if [[ ! -f "$_p10k_marker" ]] && [[ -x "$_p10k_wizard" ]]; then
          "$_p10k_wizard" || true
        fi
        if [[ ! -f "$HOME/.p10k.zsh" ]] && (( ''${+functions[p10k]} )); then
          p10k configure
        fi
        [[ -f "$HOME/.p10k.zsh" ]] && rm -f "$_p10k_pending"
        unset _p10k_marker _p10k_wizard _p10k_pending
      fi

      [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
    '';
  };

  # Queue first-run prompt setup for the next interactive terminal after
  # each switch when ~/.p10k.zsh is missing.
  home.activation.queueP10kFirstRun = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    _p10k_cfg_dir="$HOME/.config/p10k"
    _p10k_pending="$_p10k_cfg_dir/.pending-first-run"
    mkdir -p "$_p10k_cfg_dir"
    if [ ! -f "$HOME/.p10k.zsh" ]; then
      : > "$_p10k_pending"
    else
      rm -f "$_p10k_pending"
    fi
    unset _p10k_cfg_dir _p10k_pending
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

  # ---- Direnv: auto-activate nix develop environments --------------------
  programs.direnv = {
    enable            = true;
    nix-direnv.enable = true;
    enableBashIntegration = true;
    enableZshIntegration = true;
  };

  programs.zellij = {
    enable = true;
    settings = {
      theme = "default";
      simplified_ui = false;
      pane_frames = true;
      default_shell = "zsh";
      mouse_mode = true;
      copy_on_select = true;
      session_serialization = true;
      scroll_buffer_size = 10000;
    };
  };

  programs.vim = {
    enable = true;
    defaultEditor = false;
    settings = {
      number = true;
      relativenumber = true;
      expandtab = true;
      tabstop = 2;
      shiftwidth = 2;
    };
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

  home.sessionPath = [
    "$HOME/.local/bin"
  ];

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
        # All extensions below are confirmed in nixpkgs 25.11.
        # Note: Google scope uses capital G (pkgs.vscode-extensions."Google").
        ++ vsExt "anthropic"   "claude-code"                    # Claude Code
        ++ vsExt "continue"    "continue"                       # Continue.dev → local llama.cpp :8080
        ++ vsExt "Google"      "gemini-cli-vscode-ide-companion" # Gemini CLI companion
        ++ [ geminiCodeAssist ]                                  # Gemini Code Assist (Open VSX)
        ++ [ openaiCodex ]                                       # Codex — OpenAI's coding agent (Open VSX)
        ++ lib.optionals (qwenCodeCompanion != null) [ qwenCodeCompanion ]  # Qwen Code VSCode IDE Companion (pinned hash required)
        ++ [ cyberpunkThemeExtension ]                           # Cyberpunk theme (local template)
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
        ;

    };
  };

  # Write VSCodium baseline settings once on first activation — never again.
  # home-manager does NOT manage settings.json, so VSCodium can save freely.
  # To reset to defaults: rm ~/.config/VSCodium/User/settings.json && home-manager switch
  home.activation.createVSCodiumSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    _settings_dir="$HOME/.config/VSCodium/User"
    _settings_file="$_settings_dir/settings.json"
    mkdir -p "$_settings_dir"
    if [ ! -f "$_settings_file" ] || [ -L "$_settings_file" ]; then
      rm -f "$_settings_file"
      cp ${vscodiumSettingsJSON} "$_settings_file"
      chmod u+rw "$_settings_file"
    fi
    unset _settings_dir _settings_file
  '';

  home.activation.cleanupVscodiumDesktopEntries = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    codium_desktop="$HOME/.local/share/applications/codium.desktop"
    codium_url="$HOME/.local/share/applications/codium-url-handler.desktop"
    if [ -L "$codium_desktop" ]; then
      target="$(readlink "$codium_desktop" 2>/dev/null || true)"
      case "$target" in
        *"/.nix-profile/share/applications/"*) rm -f "$codium_desktop" ;;
      esac
    fi
    if [ -L "$codium_url" ]; then
      target="$(readlink "$codium_url" 2>/dev/null || true)"
      case "$target" in
        *"/.nix-profile/share/applications/"*) rm -f "$codium_url" ;;
      esac
    fi
    unset codium_desktop codium_url target
  '';

  home.activation.enforceVSCodiumTheme = lib.hm.dag.entryAfter [ "createVSCodiumSettings" ] ''
    _settings_file="$HOME/.config/VSCodium/User/settings.json"
    _profiles_dir="$HOME/.config/VSCodium/User/profiles"
    if [ -f "$_settings_file" ] && command -v jq >/dev/null 2>&1; then
      _theme_filter='
        .["workbench.colorTheme"] = "Activate SCARLET protocol (beta)" |
        .["workbench.preferredDarkColorTheme"] = "Activate SCARLET protocol (beta)" |
        .["window.autoDetectColorScheme"] = false
      '

      _apply_theme() {
        _target="$1"
        _tmp="$(mktemp)"
        if ! jq empty "$_target" >/dev/null 2>&1; then
          cp ${vscodiumSettingsJSON} "$_target"
        fi
        if jq "$_theme_filter" "$_target" > "$_tmp"; then
          mv "$_tmp" "$_target"
        else
          rm -f "$_tmp"
        fi
        unset _target _tmp
      }

      _apply_theme "$_settings_file"
      if [ -d "$_profiles_dir" ]; then
        while IFS= read -r -d $'\0' _profile_settings; do
          _apply_theme "$_profile_settings"
        done < <(find "$_profiles_dir" -type f -name settings.json -print0 2>/dev/null || true)
      fi

      unset -f _apply_theme
      unset _theme_filter
    fi
    unset _settings_file _profiles_dir
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

  # Ship the first-run prompt wizard from the repository into ~/.local/bin.
  home.file.".local/bin/p10k-setup-wizard.sh" =
    lib.mkIf (builtins.pathExists ../../scripts/p10k-setup-wizard.sh) {
      source = ../../scripts/p10k-setup-wizard.sh;
      executable = true;
    };

  home.file.".local/share/wallpapers/current-desktop-background.png".source =
    (../../templates + "/ChatGPT Image Feb 21, 2026, 02_05_57 PM.png");

  # Retire legacy COSMIC font enforcement units/scripts from earlier generations.
  home.file.".local/bin/enforce-cosmic-term-font".enable = false;
  home.file.".config/systemd/user/enforce-cosmic-term-font.service".enable = false;
  home.file.".config/systemd/user/enforce-cosmic-term-font.path".enable = false;
  home.file.".config/systemd/user/default.target.wants/enforce-cosmic-term-font.service".enable = false;
  home.file.".config/systemd/user/default.target.wants/enforce-cosmic-term-font.path".enable = false;

  # Refresh font cache so newly installed user-profile fonts are picked up.
  home.activation.refreshUserFontCache = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    ${pkgs.fontconfig}/bin/fc-cache -f "$HOME/.nix-profile/share/fonts" >/dev/null 2>&1 || true
    ${pkgs.fontconfig}/bin/fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || true
    ${pkgs.fontconfig}/bin/fc-cache -f "$HOME/.fonts" >/dev/null 2>&1 || true
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
      "title": "AI Switchboard (local/remote)",
      "provider": "openai",
      "apiKey": "dummy",
      "apiBase": "${continueApiBase}"
    }
  ],
  "tabAutocompleteModel": {
    "title": "switchboard autocomplete",
    "provider": "openai",
    "apiKey": "dummy",
    "apiBase": "${continueApiBase}",
    "model": "local-model"
  },
  "allowAnonymousTelemetry": false
}
CONTINUE_EOF
    fi
  '';

  home.activation.migrateContinueConfigApiBase = lib.hm.dag.entryAfter [ "createContinueConfig" ] ''
    cfg="$HOME/.continue/config.json"
    if [ -f "$cfg" ] && command -v jq >/dev/null 2>&1; then
      tmp="$(mktemp)"
      if jq --arg newBase "${continueApiBase}" '
        .models = ((.models // []) | map(if .apiBase == "http://127.0.0.1:8080/v1" then .apiBase = $newBase else . end)) |
        .tabAutocompleteModel = ((.tabAutocompleteModel // {}) | if .apiBase == "http://127.0.0.1:8080/v1" then .apiBase = $newBase else . end)
      ' "$cfg" > "$tmp"; then
        mv "$tmp" "$cfg"
      else
        rm -f "$tmp"
      fi
      unset tmp
    fi
    unset cfg
  '';

  # Remove stale wants links and clear any failed state from retired units.
  home.activation.cleanupCosmicFontUnitWants = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    rm -f "$HOME/.config/systemd/user/enforce-cosmic-term-font.service" 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/enforce-cosmic-term-font.path" 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/default.target.wants/enforce-cosmic-term-font.service" 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/default.target.wants/enforce-cosmic-term-font.path" 2>/dev/null || true
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user disable --now enforce-cosmic-term-font.service enforce-cosmic-term-font.path >/dev/null 2>&1 || true
      systemctl --user unmask enforce-cosmic-term-font.service enforce-cosmic-term-font.path >/dev/null 2>&1 || true
      systemctl --user reset-failed enforce-cosmic-term-font.service enforce-cosmic-term-font.path >/dev/null 2>&1 || true
    fi
  '';

  # Ensure degraded checks at reload time don't see stale failed font units.
  home.activation.preReloadResetCosmicFontUnits = lib.hm.dag.entryBefore [ "reloadSystemd" ] ''
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user disable --now enforce-cosmic-term-font.service enforce-cosmic-term-font.path >/dev/null 2>&1 || true
      systemctl --user reset-failed enforce-cosmic-term-font.service enforce-cosmic-term-font.path >/dev/null 2>&1 || true
    fi
  '';

}
