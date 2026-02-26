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
  repoPath = lib.attrByPath [ "mySystem" "mcpServers" "repoPath" ] "${config.home.homeDirectory}/Documents/NixOS-Dev-Quick-Deploy" systemConfig;
  sharedSkillsDir = "${repoPath}/.agent/skills";
  portRegistry = lib.attrByPath [ "mySystem" "ports" ] { } systemConfig;
  aiSwitchboardPort = lib.attrByPath [ "mySystem" "aiStack" "switchboard" "port" ] (lib.attrByPath [ "switchboard" ] 8085 portRegistry) systemConfig;
  aiLlamaPort = lib.attrByPath [ "mySystem" "aiStack" "llamaCpp" "port" ] (lib.attrByPath [ "llamaCpp" ] 8080 portRegistry) systemConfig;
  aiLlamaModel = lib.attrByPath [ "mySystem" "aiStack" "llamaCpp" "model" ] "local-model" systemConfig;
  aiHybridPort = lib.attrByPath [ "mySystem" "mcpServers" "hybridPort" ] (lib.attrByPath [ "mcpHybrid" ] 8003 portRegistry) systemConfig;
  aiAidbPort = lib.attrByPath [ "mySystem" "mcpServers" "aidbPort" ] (lib.attrByPath [ "mcpAidb" ] 8002 portRegistry) systemConfig;
  aiAnthropicProxyPort = lib.attrByPath [ "mySystem" "ports" "anthropicProxy" ] 8120 systemConfig;
  aiPostgresPort = lib.attrByPath [ "mySystem" "ports" "postgres" ] 5432 systemConfig;
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
    { name = "MCP_CONFIG_PATH"; value = "${config.home.homeDirectory}/.mcp/config.json"; }
    { name = "AI_AGENT_SKILLS_DIR"; value = sharedSkillsDir; }
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

  continueVsix = pkgs.fetchurl {
    url    = "https://open-vsx.org/api/Continue/continue/linux-x64/1.3.32/file/Continue.continue-1.3.32@linux-x64.vsix";
    sha256 = "1nmw9p1jkjcf0gpwzzv836yhlrlf40ymdxyc8iql5hw5h8p433fc";
    name   = "Continue.continue-1.3.32-linux-x64.vsix";
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

  # Declarative VSCodium settings managed by Home Manager.
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
    "cSpell.import"                      = [ ];
    "extensions.autoUpdate"              = false;
    "extensions.autoCheckUpdates"        = false;
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

  # Baseline JSON used to seed a writable settings.json on first activation.
  vscodiumSettingsJSON = pkgs.writeText "vscodium-settings-baseline.json"
    (builtins.toJSON vscodiumSettings);
  vscodeMutableRuntimeExtensions = [
    "continue.continue"
    "ms-python.debugpy"
    "ms-toolsai.jupyter"
    "ms-toolsai.jupyter-keymap"
    "ms-toolsai.jupyter-renderers"
  ];

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

    # Writable runtime extension dir is required for extensions that persist
    # state directly under their extension folder (e.g. debugpy/jupyter).
    mutableExtensionsDir = true;

    profiles.default = {
      extensions =
        # ── Nix ────────────────────────────────────────────────────────────
        vsExt "jnoortheen" "nix-ide"            # Nix language + nil LSP
        # ── Python ─────────────────────────────────────────────────────────
        ++ vsExt "ms-python"   "python"         # Python language support
        ++ vsExt "ms-python"   "black-formatter" # Python formatter
        ++ vsExt "ms-python"   "vscode-pylance"  # Python language server
        # debugpy/jupyter are installed as mutable runtime extensions below.
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

  # Keep VSCodium user settings mutable so the UI can save changes.
  # If HM left a symlink from prior declarative mode, replace it with a file.
  home.activation.createVSCodiumSettings = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    settings_dir="$HOME/.config/VSCodium/User"
    settings_file="$settings_dir/settings.json"
    mkdir -p "$settings_dir"

    if [ -L "$settings_file" ]; then
      tmp_file="$(mktemp)"
      cp --dereference "$settings_file" "$tmp_file"
      rm -f "$settings_file"
      mv "$tmp_file" "$settings_file"
      chmod u+rw "$settings_file"
      unset tmp_file
    elif [ ! -f "$settings_file" ]; then
      cp ${vscodiumSettingsJSON} "$settings_file"
      chmod u+rw "$settings_file"
    fi

    unset settings_dir settings_file
  '';

  # Enforce the selected Cyberpunk theme in mutable settings.json.
  home.activation.enforceVSCodiumTheme = lib.hm.dag.entryAfter [ "vscodeProfiles" ] ''
    settings_file="$HOME/.config/VSCodium/User/settings.json"
    if [ -f "$settings_file" ] && command -v jq >/dev/null 2>&1; then
      tmp="$(mktemp)"
      if jq '
        .["workbench.colorTheme"] = "Activate SCARLET protocol (beta)" |
        .["workbench.preferredDarkColorTheme"] = "Activate SCARLET protocol (beta)" |
        .["window.autoDetectColorScheme"] = false
      ' "$settings_file" > "$tmp"; then
        mv "$tmp" "$settings_file"
        chmod u+rw "$settings_file" || true
      else
        rm -f "$tmp"
      fi
      unset tmp
    fi
    unset settings_file
  '';

  # Reset stale Continue workspace/global state that can block client bootstrap
  # after extension/config migrations.
  home.activation.resetContinueVscodeState = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    gdb="$HOME/.config/VSCodium/User/globalStorage/state.vscdb"
    if [ -f "$gdb" ] && command -v sqlite3 >/dev/null 2>&1; then
      sqlite3 "$gdb" "delete from ItemTable where key like '%continue%' or key like 'Continue.%';" >/dev/null 2>&1 || true
    fi
    ws_root="$HOME/.config/VSCodium/User/workspaceStorage"
    if [ -d "$ws_root" ] && command -v sqlite3 >/dev/null 2>&1; then
      for wdb in "$ws_root"/*/state.vscdb; do
        [ -f "$wdb" ] || continue
        sqlite3 "$wdb" "delete from ItemTable where key like '%continue%' or key like 'Continue.%' or value like '%continue%';" >/dev/null 2>&1 || true
      done
      unset wdb
    fi
    unset gdb ws_root
  '';

  # Install runtime-mutable extensions that write inside their own install dir.
  home.activation.ensureMutableRuntimeVscodeExtensions = lib.hm.dag.entryAfter [ "linkGeneration" ] ''
    if command -v codium >/dev/null 2>&1 && ! pgrep -u "$USER" -x codium >/dev/null 2>&1; then
      ext_root="$HOME/.vscode-oss/extensions"
      mkdir -p "$ext_root"
      for ext_id in ${lib.concatStringsSep " " vscodeMutableRuntimeExtensions}; do
        alias_path="$ext_root/$ext_id"
        case "$ext_id" in
          continue.continue) alias_path="$ext_root/Continue.continue" ;;
        esac
        if [ -L "$alias_path" ]; then
          rm -f "$alias_path"
        fi
        if [ "$ext_id" = "continue.continue" ]; then
          codium --install-extension "${continueVsix}" --force >/dev/null 2>&1 || true
        else
          codium --install-extension "$ext_id" --force >/dev/null 2>&1 || true
        fi
      done
      unset ext_root ext_id alias_path
    fi
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
      "apiBase": "${continueApiBase}",
      "model": "${aiLlamaModel}"
    }
  ],
  "tabAutocompleteModel": {
    "title": "switchboard autocomplete",
    "provider": "openai",
    "apiKey": "dummy",
    "apiBase": "${continueApiBase}",
    "model": "${aiLlamaModel}"
  },
  "allowAnonymousTelemetry": false
}
CONTINUE_EOF
    fi
  '';

  home.activation.migrateContinueConfigApiBase = lib.hm.dag.entryAfter [ "createContinueConfig" ] ''
    cfg="$HOME/.continue/config.json"
    if [ -f "$cfg" ] && command -v jq >/dev/null 2>&1; then
      runtime_base="${continueApiBase}"
      if ${pkgs.curl}/bin/curl --silent --show-error --fail --max-time 5 \
        "http://127.0.0.1:8085/v1/models" >/dev/null 2>&1; then
        runtime_base="http://127.0.0.1:8085/v1"
      fi

      detected_model="$(${pkgs.curl}/bin/curl --silent --show-error --fail --max-time 10 \
        "$runtime_base/models" 2>/dev/null | jq -r '.data[0].id // empty' || true)"
      if [ -z "$detected_model" ]; then
        detected_model="${aiLlamaModel}"
      fi

      tmp="$(mktemp)"
      if jq --arg newBase "$runtime_base" --arg model "$detected_model" '
        .models = ((.models // []) | map(
          if ((.provider // "") == "openai") then
            .apiBase = $newBase
          else
            .
          end
          | .model = $model
        )) |
        .tabAutocompleteModel = ((.tabAutocompleteModel // {})
          | if ((.provider // "openai") == "openai") then .apiBase = $newBase else . end
          | .model = $model)
      ' "$cfg" > "$tmp"; then
        mv "$tmp" "$cfg"
      else
        rm -f "$tmp"
      fi
      unset tmp runtime_base detected_model
    fi
    unset cfg
  '';

  # ---- MCP config bootstrap ---------------------------------------------------
  # Keep a local MCP server catalog available for agent clients that read
  # ~/.mcp/config.json and ~/.config/claude/mcp.json.
  home.activation.createMcpConfig = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    mkdir -p "$HOME/.mcp"
    if [ ! -f "$HOME/.mcp/config.json" ]; then
      cat > "$HOME/.mcp/config.json" << 'MCP_EOF'
{
  "mcpServers": {
    "mcp-nixos": {
      "command": "nix",
      "args": ["run", "github:utensils/mcp-nixos"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${repoPath}"]
    },
    "git": {
      "command": "npx",
      "args": ["-y", "@cyanheads/git-mcp-server"]
    },
    "fetch": {
      "command": "npx",
      "args": ["-y", "mcp-server-fetch-typescript"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://mcp@127.0.0.1:${toString aiPostgresPort}/mcp"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "set-me"
      }
    }
  }
}
MCP_EOF
    fi

    if [ ! -f "$HOME/.mcp/registry.json" ]; then
      cat > "$HOME/.mcp/registry.json" << 'MCP_REGISTRY_EOF'
{
  "servers": [
    { "id": "mcp-nixos", "category": "nixos", "description": "NixOS package and option discovery" },
    { "id": "filesystem", "category": "project", "description": "Project file read/write/search tools" },
    { "id": "git", "category": "project", "description": "Repository status, diff, and commit tooling" },
    { "id": "fetch", "category": "web", "description": "HTTP fetch for docs, APIs, and release notes" },
    { "id": "memory", "category": "agent", "description": "Cross-session lightweight memory store" },
    { "id": "postgres", "category": "database", "description": "PostgreSQL access for AIDB and ops data" },
    { "id": "github", "category": "remote", "description": "GitHub repo/issue/PR automation" }
  ]
}
MCP_REGISTRY_EOF
    fi

    mkdir -p "$HOME/.config/claude"
    ln -sfn "$HOME/.mcp/config.json" "$HOME/.config/claude/mcp.json"
  '';

  # Make skills catalog agent-agnostic: Claude and Codex both read the same
  # project skill definitions from .agent/skills, without duplicate installs.
  home.activation.linkSharedAgentSkills = lib.hm.dag.entryAfter [ "createMcpConfig" ] ''
    src="${sharedSkillsDir}"

    if [ -d "$src" ]; then
      mkdir -p "$HOME/.claude"
      ln -sfn "$src" "$HOME/.claude/skills"

      mkdir -p "$HOME/.codex/skills"
      for d in "$src"/*; do
        [ -d "$d" ] || continue
        name="$(basename "$d")"
        target="$HOME/.codex/skills/$name"
        if [ -L "$target" ]; then
          ln -sfn "$d" "$target"
          continue
        fi
        if [ -e "$target" ]; then
          continue
        fi
        ln -s "$d" "$target"
      done
      unset d name target
    fi
    unset src
  '';

  # Allow GPT4All Flatpak to read locally hosted llama.cpp models.
  home.activation.configureGpt4AllModelAccess = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    if command -v flatpak >/dev/null 2>&1; then
      if flatpak info io.gpt4all.gpt4all >/dev/null 2>&1; then
        flatpak override --user --filesystem=/var/lib/llama-cpp:ro io.gpt4all.gpt4all >/dev/null 2>&1 || true
        gpt4all_models_dir="$HOME/.var/app/io.gpt4all.gpt4all/data/nomic.ai/GPT4All/models"
        mkdir -p "$(dirname "$gpt4all_models_dir")"
        if [ -L "$gpt4all_models_dir" ]; then
          ln -sfn /var/lib/llama-cpp/models "$gpt4all_models_dir"
        elif [ -d "$gpt4all_models_dir" ]; then
          if [ -z "$(find "$gpt4all_models_dir" -mindepth 1 -print -quit 2>/dev/null)" ]; then
            rmdir "$gpt4all_models_dir"
          else
            mv "$gpt4all_models_dir" "$gpt4all_models_dir.backup.$(date +%Y%m%d%H%M%S)"
          fi
          ln -s /var/lib/llama-cpp/models "$gpt4all_models_dir"
        elif [ ! -e "$gpt4all_models_dir" ]; then
          ln -s /var/lib/llama-cpp/models "$gpt4all_models_dir"
        fi
        unset gpt4all_models_dir
      fi
    fi
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
