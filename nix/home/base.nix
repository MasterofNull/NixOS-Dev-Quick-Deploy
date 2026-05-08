{
  lib,
  pkgs,
  config,
  osConfig ? {},
  ...
}:
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
# Shared Home Manager overlays live in nix/home/*.nix.
# Per-host customisation goes in nix/hosts/<host>/home.nix.
# ---------------------------------------------------------------------------
let
  systemConfig =
    if lib.hasAttrByPath ["mySystem"] osConfig
    then osConfig
    else config;
  repoPath = lib.attrByPath ["mySystem" "mcpServers" "repoPath"] "${config.home.homeDirectory}/Documents/NixOS-Dev-Quick-Deploy" systemConfig;
  sharedSkillsDir = "${repoPath}/.agent/skills";
  defaultPortRegistry = {
    llamaCpp = 8080;
    embedding = 8081;
    mcpAidb = 8002;
    mcpHybrid = 8003;
    mcpRalph = 8004;
    switchboard = 8085;
    aiderWrapper = 8090;
    anthropicProxy = 8120;
    postgres = 5432;
  };
  portRegistry = lib.attrByPath ["mySystem" "ports"] defaultPortRegistry systemConfig;
  getRegistryPort = portName:
    lib.attrByPath [portName]
    (throw "Missing centralized port registry entry: mySystem.ports.${portName}")
    portRegistry;
  aiSwitchboardPort = lib.attrByPath ["mySystem" "aiStack" "switchboard" "port"] (getRegistryPort "switchboard") systemConfig;
  aiLlamaPort = lib.attrByPath ["mySystem" "aiStack" "llamaCpp" "port"] (getRegistryPort "llamaCpp") systemConfig;
  aiLlamaModel = lib.attrByPath ["mySystem" "aiStack" "llamaCpp" "model"] "local-model" systemConfig;
  aiLlamaCtxSize = lib.attrByPath ["mySystem" "aiStack" "llamaCpp" "ctxSize"] 16384 systemConfig;
  aiHybridPort = lib.attrByPath ["mySystem" "mcpServers" "hybridPort"] (getRegistryPort "mcpHybrid") systemConfig;
  aiAidbPort = lib.attrByPath ["mySystem" "mcpServers" "aidbPort"] (getRegistryPort "mcpAidb") systemConfig;
  aiRalphPort = lib.attrByPath ["mySystem" "mcpServers" "ralphPort"] (getRegistryPort "mcpRalph") systemConfig;
  aiAiderPort = lib.attrByPath ["mySystem" "mcpServers" "aiderWrapperPort"] (getRegistryPort "aiderWrapper") systemConfig;
  aiPostgresPort = lib.attrByPath ["mySystem" "ports" "postgres"] (getRegistryPort "postgres") systemConfig;
  switchboardProfiles = lib.attrByPath ["mySystem" "aiStack" "switchboard" "profiles"] {} systemConfig;
  continueLocalProfile = lib.attrByPath ["continue-local"] {} switchboardProfiles;
  localAgentProfile = lib.attrByPath ["local-agent"] {} switchboardProfiles;
  defaultSwitchboardProfile = lib.attrByPath ["default"] {} switchboardProfiles;
  continueContextLength =
    lib.attrByPath ["advertisedContextWindow"]
    (lib.attrByPath ["advertisedContextWindow"] aiLlamaCtxSize defaultSwitchboardProfile)
    continueLocalProfile;
  # Keep interactive editor replies decoupled from switchboard's compact
  # agent-profile defaults. Agent-to-agent budgets still live in workflow
  # sessions and switchboard profile metadata.
  continueChatMaxTokens =
    if continueContextLength > 4096
    then 4096
    else continueContextLength;
  continueTabMaxTokens = lib.min 96 (lib.max 32 continueChatMaxTokens);
  localAgentContextLength = let
    advertised = lib.attrByPath ["advertisedContextWindow"] aiLlamaCtxSize localAgentProfile;
    bounded = lib.attrByPath ["maxInputTokens"] null localAgentProfile;
  in
    if bounded != null
    then lib.min advertised bounded
    else advertised;
  localAgentChatMaxTokens =
    lib.attrByPath ["maxOutputTokens"] 1024 localAgentProfile;
  continueRemoteContextLength = 16000;
  continueRemoteMaxTokens = 4096;
  aiOpenAIBaseUrl = "http://127.0.0.1:${toString aiSwitchboardPort}/v1";
  vscodeLinuxTarget =
    if pkgs.stdenv.hostPlatform.system == "x86_64-linux"
    then "linux-x64"
    else if pkgs.stdenv.hostPlatform.system == "aarch64-linux"
    then "linux-arm64"
    else throw "Unsupported VSCodium extension platform: ${pkgs.stdenv.hostPlatform.system}";
  openaiCodexHashByTarget = {
    linux-x64 = "sha256-nXWyNNI+L7g5lc6Fa3DZTWsrA8WLXCmfJLwUstNUvDw=";
    linux-arm64 = "sha256-fLw9PEn1vtQ4LRzNotjpt8Z9REocouMQSzaSrwBfZ1g=";
  };
  continueVsixHashByTarget = {
    linux-x64 = "sha256-8jvllwe1iCZnF+3UGppEOk2QKdyhVSFDxthfTLIIQYQ=";
    linux-arm64 = "sha256-LLtJiAyHAHWD39P5x2Czf/6YxLKX4v/idgSNvtBYfvw=";
  };
  # Continue uses the switchboard OpenAI-compatible proxy directly because the
  # hybrid coordinator's /v1 ingress is protected and returns 401 to editor
  # clients that only provide placeholder local keys.
  continueApiBase = aiOpenAIBaseUrl;
  vscodiumPathValue = "${config.home.homeDirectory}/.local/bin:${config.home.homeDirectory}/.nix-profile/bin:/run/current-system/sw/bin:\${env:PATH}";
  vscodiumAiEnv = [
    {
      name = "PATH";
      value = vscodiumPathValue;
    }
    {
      name = "OPENAI_BASE_URL";
      value = aiOpenAIBaseUrl;
    }
    {
      name = "OPENAI_API_BASE";
      value = aiOpenAIBaseUrl;
    }
    {
      name = "OPENAI_API_KEY";
      value = "dummy";
    }
    {
      name = "HYBRID_COORDINATOR_URL";
      value = "http://127.0.0.1:${toString aiHybridPort}";
    }
    {
      name = "AIDB_URL";
      value = "http://127.0.0.1:${toString aiAidbPort}";
    }
    {
      name = "MCP_CONFIG_PATH";
      value = "${config.home.homeDirectory}/.mcp/config.json";
    }
    {
      name = "AI_AGENT_SKILLS_DIR";
      value = sharedSkillsDir;
    }
  ];

  # openai.chatgpt — "Codex: OpenAI's coding agent" — not in nixpkgs 25.11;
  # packaged inline from Open VSX so it installs declaratively.
  openaiCodex = pkgs.vscode-utils.buildVscodeExtension {
    pname = "openai-chatgpt";
    version = "0.5.80";
    vscodeExtPublisher = "openai";
    vscodeExtName = "chatgpt";
    vscodeExtUniqueId = "openai.chatgpt";
    vscodeExtVersion = "0.5.80";
    src = pkgs.fetchurl {
      url = "https://open-vsx.org/api/openai/chatgpt/${vscodeLinuxTarget}/0.5.80/file/openai.chatgpt-0.5.80@${vscodeLinuxTarget}.vsix";
      sha256 = openaiCodexHashByTarget.${vscodeLinuxTarget};
      # Rename .vsix → .zip so the stdenv unzip hook fires (same trick used
      # by pkgs/applications/editors/vscode/extensions/mktplcExtRefToFetchArgs.nix).
      name = "openai-chatgpt.zip";
    };
  };

  # Google.geminicodeassist — "Gemini Code Assist" — not in nixpkgs 25.11;
  # packaged inline from Open VSX so it installs declaratively.
  geminiCodeAssist = pkgs.vscode-utils.buildVscodeExtension {
    pname = "Google-geminicodeassist";
    version = "2.79.0";
    vscodeExtPublisher = "Google";
    vscodeExtName = "geminicodeassist";
    vscodeExtUniqueId = "Google.geminicodeassist";
    vscodeExtVersion = "2.79.0";
    src = pkgs.fetchurl {
      url = "https://open-vsx.org/api/Google/geminicodeassist/2.79.0/file/Google.geminicodeassist-2.79.0.vsix";
      sha256 = "sha256-/8QmCFtD7f/RNkNuZexvoevpLa9FqrZfxqmPo2Ss4zk=";
      name = "Google-geminicodeassist.zip";
    };
  };

  # Continue CLI — declarative npm packaging
  continueCli = pkgs.callPackage ../pkgs/continue-cli.nix {};

  continueMutableVsix = pkgs.fetchurl {
    url = "https://open-vsx.org/api/Continue/continue/${vscodeLinuxTarget}/1.3.38/file/Continue.continue-1.3.38@${vscodeLinuxTarget}.vsix";
    sha256 = continueVsixHashByTarget.${vscodeLinuxTarget};
    name = "Continue.continue-1.3.38-${vscodeLinuxTarget}.vsix";
  };

  cyberpunkThemeArchive =
    pkgs.runCommand "max-ss.cyberpunk-1.2.14.zip" {
      nativeBuildInputs = [pkgs.zip];
    } ''
      mkdir -p extension
      cp -R ${../../templates/vscode/max-ss.cyberpunk-1.2.14-universal}/. extension/
      ${pkgs.zip}/bin/zip -qr "$out" extension
    '';

  cyberpunkThemeExtension = pkgs.vscode-utils.buildVscodeExtension {
    pname = "max-ss-cyberpunk-theme";
    version = "1.2.14";
    vscodeExtPublisher = "max-SS";
    vscodeExtName = "Cyberpunk";
    vscodeExtUniqueId = "max-SS.Cyberpunk";
    vscodeExtVersion = "1.2.14";
    src = cyberpunkThemeArchive;
  };

  cosmicThemeDarkPalette = builtins.readFile (../../templates + "/Royal Wine-inner.ron");
  cosmicWallpaperPath = "${config.home.homeDirectory}/.local/share/wallpapers/current-desktop-background.png";

  # Declarative VSCodium settings managed by Home Manager.
  vscodiumSettings = {
    "editor.fontSize" = 14;
    "editor.tabSize" = 2;
    "editor.insertSpaces" = true;
    "editor.formatOnSave" = true;
    "editor.formatOnPaste" = false;
    "editor.minimap.enabled" = false;
    "editor.wordWrap" = "on";
    "editor.rulers" = [80 120];
    "editor.bracketPairColorization.enabled" = true;
    "editor.guides.bracketPairs" = "active";
    "editor.inlineSuggest.enabled" = true;
    "editor.suggestSelection" = "first";
    "files.trimTrailingWhitespace" = true;
    "files.insertFinalNewline" = true;
    "files.trimFinalNewlines" = true;
    "files.eol" = "\n";
    "files.autoSave" = "onFocusChange";
    "files.exclude" = {
      "**/.git" = true;
      "**/.DS_Store" = true;
      "**/node_modules" = true;
      "**/__pycache__" = true;
      "**/.mypy_cache" = true;
      "**/.ruff_cache" = true;
      "**/result" = true;
      "**/result-*" = true;
    };
    "terminal.integrated.defaultProfile.linux" = "zsh";
    "terminal.integrated.fontSize" = 13;
    "terminal.integrated.scrollback" = 10000;
    "workbench.colorTheme" = "Activate SCARLET protocol (beta)";
    "workbench.preferredDarkColorTheme" = "Activate SCARLET protocol (beta)";
    "window.autoDetectColorScheme" = false;
    "workbench.iconTheme" = "vs-seti";
    "workbench.startupEditor" = "none";
    "workbench.editor.enablePreview" = false;
    "nix.enableLanguageServer" = true;
    "nix.serverPath" = "nil";
    "nix.serverSettings".nil.formatting.command = ["alejandra"];
    "[nix]"."editor.defaultFormatter" = "jnoortheen.nix-ide";
    "python.defaultInterpreterPath" = "python3";
    "python.analysis.typeCheckingMode" = "basic";
    "[python]"."editor.defaultFormatter" = "ms-python.python";
    "go.useLanguageServer" = true;
    "go.toolsManagement.autoUpdate" = false;
    "[go]"."editor.formatOnSave" = true;
    "[go]"."editor.defaultFormatter" = "golang.go";
    "rust-analyzer.checkOnSave.command" = "clippy";
    "rust-analyzer.inlayHints.enable" = true;
    "[rust]"."editor.defaultFormatter" = "rust-lang.rust-analyzer";
    "[yaml]"."editor.defaultFormatter" = "redhat.vscode-yaml";
    "yaml.validate" = true;
    "continue.telemetryEnabled" = false;
    "continue.enableTabAutocomplete" = true;
    "continue.showInlineTip" = true;
    "cSpell.import" = [];
    "extensions.autoUpdate" = false;
    "extensions.autoCheckUpdates" = false;
    "git.enableSmartCommit" = true;
    "git.confirmSync" = false;
    "git.autofetch" = true;
    # Prevent VSCodium from injecting its own credential helper into
    # .git/config — the global gh auth credential helper is authoritative.
    "git.useIntegratedAskPass" = false;
    "git.terminalAuthentication" = false;
    "gitlens.telemetry.enabled" = false;
    "shellcheck.enable" = true;
    "shellcheck.executablePath" = "shellcheck";
    "git.path" = "${config.programs.git.package}/bin/git";
    # Native installer puts the binary at ~/.local/bin/claude.  Use the
    # absolute path so the extension works when VSCodium is launched from
    # the desktop launcher (PATH may not include ~/.local/bin there).
    # CLI paths are declarative; no npm-global compatibility wrappers.

    "claude-code.executablePath" = "${config.home.homeDirectory}/.local/bin/claude";
    # claudeProcessWrapper is intentionally omitted — setting it to the same
    # binary as executablePath causes the extension to call 'claude claude ...'
    # which crashes the extension host at startup.
    "claude-code.environmentVariables" = vscodiumAiEnv;
    "claude-code.autoStart" = false;
    "claudeCode.executablePath" = "${config.home.homeDirectory}/.local/bin/claude";
    "claudeCode.environmentVariables" = vscodiumAiEnv;
    "claudeCode.autoStart" = false;
    "gpt-codex.executablePath" = "codex";
    "gpt-codex.environmentVariables" = vscodiumAiEnv;
    "gpt-codex.autoStart" = false;
    "gptCodex.executablePath" = "codex";
    "gptCodex.environmentVariables" = vscodiumAiEnv;
    "gptCodex.autoStart" = false;
    "codex.executablePath" = "codex";
    "codex.environmentVariables" = vscodiumAiEnv;
    "codex.autoStart" = false;
    "codexIDE.executablePath" = "codex";
    "codexIDE.environmentVariables" = vscodiumAiEnv;
    "codexIDE.autoStart" = false;
    "codexIde.executablePath" = "codex";
    "codexIde.environmentVariables" = vscodiumAiEnv;
    "codexIde.autoStart" = false;
    "openai.executablePath" = "openai";
    "openai.environmentVariables" = vscodiumAiEnv;
    "openai.autoStart" = false;
    "[javascript]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
    "[typescript]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
    "[json]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
    "[jsonc]"."editor.defaultFormatter" = "esbenp.prettier-vscode";
    "[markdown]"."editor.defaultFormatter" = "yzhang.markdown-all-in-one";
    "telemetry.telemetryLevel" = "off";
    "redhat.telemetry.enabled" = false;
    "update.mode" = "none";
  };

  # Baseline JSON used to seed a writable settings.json on first activation.
  vscodiumSettingsJSON =
    pkgs.writeText "vscodium-settings-baseline.json"
    (builtins.toJSON vscodiumSettings);
  vscodiumArgvJSON =
    pkgs.writeText "vscodium-argv-baseline.json"
    (builtins.toJSON {
      # Mitigate Codium + Wayland + amdgpu freezes under memory pressure by
      # forcing software rendering for the Electron shell.
      "disable-hardware-acceleration" = true;
      # Force the editor onto XWayland on the Renoir/COSMIC workstation until
      # Electron-on-Wayland stops destabilizing the desktop session.
      "ozone-platform" = "x11";
    });
  vscodeMutableRuntimeExtensions = [
    # Qwen updates its writable runtime tree in-place. Keep it mutable so we
    # do not pin a stale immutable version that recreates .obsolete markers.
    "qwenlm.qwen-code-vscode-ide-companion"
    "ms-python.debugpy"
    "ms-toolsai.jupyter"
    "ms-toolsai.jupyter-keymap"
    "ms-toolsai.jupyter-renderers"
  ];

  # Guard helper — silently skips an extension when its scope or name is
  # absent from pkgs.vscode-extensions (e.g. older or slimmer channels).
  vsExt = scope: name: let
    hasScopes = pkgs ? vscode-extensions;
    scopeSet =
      if hasScopes
      then pkgs.vscode-extensions
      else {};
    hasScope = hasScopes && builtins.hasAttr scope scopeSet;
    extSet =
      if hasScope
      then builtins.getAttr scope scopeSet
      else {};
    hasName = hasScope && builtins.hasAttr name extSet;
  in
    lib.optionals hasName [(builtins.getAttr name extSet)];

  # VSCodium wrapped with native-lib LD_LIBRARY_PATH so node_sqlite3.node
  # (used by Continue) can dlopen libstdc++.so.6 from the GCC runtime.
  # Extracted into let so the activation hook can reference the store path
  # directly (PATH is incomplete during nixos-rebuild switch activation).
  vscodiumWrapped =
    (pkgs.symlinkJoin {
      name = "vscodium-with-native-libs";
      paths = [pkgs.vscodium];
      nativeBuildInputs = [pkgs.makeWrapper];
      postBuild = ''
        wrapProgram $out/bin/codium \
          --prefix LD_LIBRARY_PATH : ${pkgs.lib.makeLibraryPath [pkgs.stdenv.cc.cc.lib]} \
          --unset NIXOS_OZONE_WL \
          --unset ELECTRON_OZONE_PLATFORM_HINT \
          --add-flags --ozone-platform=x11
      '';
    })
    // {
      inherit (pkgs.vscodium) version pname;
      meta = pkgs.vscodium.meta // {mainProgram = "codium";};
    };

  # Nix store paths for tools the code-nix wrapper needs on its PATH.
  # These packages are in home.packages below so they're always present.
  vsWrapperPath = lib.makeBinPath (with pkgs; [
    nil
    alejandra
    deadnix
    statix # Nix LSP + formatters
    shellcheck # Shell script linting
    python3 # Python runtime
    go # Go runtime
    rustc # Rust compiler
    cargo # Rust toolchain
    clippy # Rust lints used by rust-analyzer checkOnSave
    rustfmt # Rust formatter for editor/tooling integration
    nodejs # Node.js runtime (required by AI extension language servers)
  ]);
in {
  home.stateVersion = "25.11";
  programs.home-manager.enable = true;

  # ---- XDG user directories -----------------------------------------------
  xdg = {
    enable = true;
    userDirs = {
      enable = true;
      createDirectories = true;
      desktop = "${config.home.homeDirectory}/Desktop";
      documents = "${config.home.homeDirectory}/Documents";
      download = "${config.home.homeDirectory}/Downloads";
      music = "${config.home.homeDirectory}/Music";
      pictures = "${config.home.homeDirectory}/Pictures";
      publicShare = "${config.home.homeDirectory}/Public";
      templates = "${config.home.homeDirectory}/Templates";
      videos = "${config.home.homeDirectory}/Videos";
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
    # Keep COSMIC theme overrides minimal and version-stable.
    # Newer COSMIC builds changed several per-key RON value types; forcing
    # old `Some((...))` forms breaks theme loading at session startup.
    configFile."cosmic/com.system76.CosmicTheme.Dark/v1/name" = {
      text = ''"cosmic-dark"'';
      force = true;
    };
    configFile."cosmic/com.system76.CosmicTheme.Dark/v1/is_dark" = {
      text = "true";
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

  # Remove legacy per-key COSMIC theme overrides written by older revisions.
  # They can be type-incompatible with current COSMIC (causing theme parse errors).
  home.activation.cleanupLegacyCosmicThemeOverrides = lib.hm.dag.entryAfter ["writeBoundary"] ''
    theme_dir="$HOME/.config/cosmic/com.system76.CosmicTheme.Dark/v1"
    if [ -d "$theme_dir" ]; then
      rm -f \
        "$theme_dir"/active_hint \
        "$theme_dir"/gaps \
        "$theme_dir"/window_hint \
        "$theme_dir"/shade \
        "$theme_dir"/accent_text \
        "$theme_dir"/control_tint \
        "$theme_dir"/text_tint \
        "$theme_dir"/spacing \
        "$theme_dir"/corner_radii \
        "$theme_dir"/neutral_tint \
        "$theme_dir"/bg_color \
        "$theme_dir"/primary_container_bg \
        "$theme_dir"/secondary_container_bg \
        "$theme_dir"/accent \
        "$theme_dir"/success \
        "$theme_dir"/warning \
        "$theme_dir"/destructive
      rm -f "$theme_dir"/*.backup-* 2>/dev/null || true
    fi
    unset theme_dir
  '';

  # ---- Core user packages -------------------------------------------------
  home.packages = with pkgs; [
    # Search / text processing
    ripgrep
    fd
    jq
    yq-go

    # Archives
    unzip
    p7zip

    # Network
    wget
    curl
    socat

    # System inspection / modern CLI tools
    htop
    btop
    lsof
    pciutils
    usbutils
    nvme-cli
    smartmontools
    bubblewrap
    eza
    bat
    dust
    duf

    # Core dev/tooling runtimes (critical for quick-deploy workflows)
    git
    gh
    tree
    file
    xxd
    nodejs
    chromium
    go
    rustc
    cargo
    clippy
    rustfmt
    ruby
    # vscodium is installed via programs.vscode below; listing it here too
    # would create a duplicate entry in the nix profile.
    # neovim is provided by system packages; avoid duplicate nvim.desktop.

    # Nix utilities
    nix-tree
    nix-diff
    nvd

    # Nix tooling — also on the VSCodium wrapper PATH (vsWrapperPath above)
    nil
    alejandra
    deadnix
    statix

    # Shell linting — used by the shellcheck VSCodium extension
    shellcheck

    # Nerd font required for Powerlevel10k glyphs in terminal prompts.
    nerd-fonts.meslo-lg

    # Terminal markdown viewer
    glow

    # Python AI/dev toolchain expected by system health checks
    (python3.withPackages (ps:
      with ps; [
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
        ps.trio
        # Note: pytest-anyio doesn't exist in nixpkgs; anyio includes pytest plugin
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

    # Continue CLI — AI-powered coding assistant for the terminal
    continueCli

    # Lightweight fallback editor (override in per-host home.nix)
    micro
  ];

  # ---- Git -----------------------------------------------------------------
  programs.git = {
    enable = true;
    settings = {
      # user.name and user.email are intentionally NOT set here — they are
      # written directly to ~/.gitconfig by nixos-quick-deploy.sh so the user
      # can change them with `git config --global` without a switch clobbering them.
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
    enable = true;
    autosuggestion.enable = true;
    syntaxHighlighting.enable = true;
    enableCompletion = true;
    history = {
      size = 50000;
      save = 50000;
      ignoreDups = true;
      share = true;
      extended = true;
    };
    shellAliases = {
      ll = "ls -lah";
      la = "ls -A";
      gs = "git status";
      gd = "git diff";
      gl = "git log --oneline --graph --decorate -20";
      # NixOS rebuild shortcuts
      nrs = "sudo nixos-rebuild switch --flake .";
      nrb = "sudo nixos-rebuild boot --flake .";
      nrd = "sudo nixos-rebuild dry-build --flake .";
      hms = "home-manager switch --flake .";
      # AI CLI tools
      continue = "cn"; # Continue CLI shorthand
      # pi-coding-agent wired to local switchboard (OpenAI-compatible proxy at :8085)
      pi = "OPENAI_BASE_URL=\"http://127.0.0.1:${toString aiSwitchboardPort}/v1\" OPENAI_API_KEY=dummy $HOME/.npm-global/bin/pi --provider openai";
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
  home.activation.queueP10kFirstRun = lib.hm.dag.entryAfter ["writeBoundary"] ''
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
  home.activation.removeLegacyStarshipBootstrap = lib.hm.dag.entryAfter ["writeBoundary"] ''
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
    enable = true;
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

  # ---- Continue CLI -------------------------------------------------------
  # Continue CLI is installed declaratively via nix/pkgs/continue-cli.nix.
  # Command: cn

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
    EDITOR = "micro";
    VISUAL = "micro";
    PAGER = "less";
    LESS = "-FRX";
    # npm global prefix for AI CLI tools (Continue, pi, etc.)
    NPM_CONFIG_PREFIX = "${config.home.homeDirectory}/.npm-global";
  };

  home.sessionPath = [
    "$HOME/.local/bin"
    "$HOME/.npm-global/bin" # codex, qwen, gemini, pi CLI agents
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
    enable = true;
    # vscodiumWrapped defined in let block above — extracted so the
    # activation hook can reference its store path directly.
    package = vscodiumWrapped;

    # Writable runtime extension dir is required for extensions that persist
    # state directly under their extension folder (e.g. debugpy/jupyter).
    mutableExtensionsDir = true;

    profiles.default = {
      extensions =
        # ── Nix ────────────────────────────────────────────────────────────
        vsExt "jnoortheen" "nix-ide" # Nix language + nil LSP
        # ── Python ─────────────────────────────────────────────────────────
        ++ vsExt "ms-python" "python" # Python language support
        ++ vsExt "ms-python" "black-formatter" # Python formatter
        ++ vsExt "ms-python" "vscode-pylance" # Python language server (bundles Pyright internally)
        # Bare ms-pyright.pyright removed — Pylance already includes Pyright's
        # type checker; running both causes duplicate diagnostics and conflicts.
        # ── Go ─────────────────────────────────────────────────────────────
        ++ vsExt "golang" "go" # Go language support
        # ── Rust ───────────────────────────────────────────────────────────
        ++ vsExt "rust-lang" "rust-analyzer" # Rust LSP
        # ── Git / version control ──────────────────────────────────────────
        ++ vsExt "eamodio" "gitlens" # Git supercharged
        ++ vsExt "mhutchie" "git-graph" # Git branch graph
        # ── AI coding assistant ────────────────────────────────────────────
        # All extensions below are confirmed in nixpkgs 25.11.
        # Note: Google scope uses capital G (pkgs.vscode-extensions."Google").
        ++ vsExt "anthropic" "claude-code" # Claude Code
        ++ vsExt "Google" "gemini-cli-vscode-ide-companion" # Gemini CLI companion
        ++ [geminiCodeAssist] # Gemini Code Assist (Open VSX)
        ++ [openaiCodex] # Codex — OpenAI's coding agent (Open VSX)
        ++ [cyberpunkThemeExtension] # Cyberpunk theme (local template)
        # ── Data / serialisation formats ───────────────────────────────────
        ++ vsExt "redhat" "vscode-yaml"
        ++ vsExt "tamasfe" "even-better-toml"
        ++ vsExt "mechatroner" "rainbow-csv"
        # ── Shell scripting ─────────────────────────────────────────────────
        ++ vsExt "timonwong" "shellcheck" # Powered by shellcheck binary
        # ── Formatting / editing quality-of-life ───────────────────────────
        ++ vsExt "editorconfig" "editorconfig"
        ++ vsExt "esbenp" "prettier-vscode"
        ++ vsExt "dbaeumer" "vscode-eslint"
        ++ vsExt "usernamehw" "errorlens"
        ++ vsExt "streetsidesoftware" "code-spell-checker"
        # ── Markdown ───────────────────────────────────────────────────────
        ++ vsExt "yzhang" "markdown-all-in-one";
    };
  };

  # Keep VSCodium user settings mutable so the UI can save changes.
  # If HM left a symlink from prior declarative mode, replace it with a file.
  home.activation.createVSCodiumSettings = lib.hm.dag.entryAfter ["writeBoundary"] ''
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

  # Keep VSCodium argv flags declarative. settings.json stays mutable, but the
  # Electron process flags should converge on every activation because they
  # directly affect startup stability.
  home.file.".config/VSCodium/User/argv.json".source = vscodiumArgvJSON;

  # Enforce the selected Cyberpunk theme in mutable settings.json.
  # Must run after createVSCodiumSettings which creates the file; vscodeProfiles
  # runs before writeBoundary so cannot be used as a predecessor here.
  home.activation.enforceVSCodiumTheme = lib.hm.dag.entryAfter ["createVSCodiumSettings"] ''
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

  # Remove stale AI extension keys that can break startup:
  #  - claudeProcessWrapper pointing to the same binary as executablePath
  #  - ANTHROPIC_BASE_URL override to an unavailable or incompatible local proxy
  home.activation.migrateClaudeVscodeSettings = lib.hm.dag.entryAfter ["enforceVSCodiumTheme"] ''
    settings_file="$HOME/.config/VSCodium/User/settings.json"
    if [ -f "$settings_file" ] && command -v jq >/dev/null 2>&1; then
      tmp="$(mktemp)"
      if jq '
        del(.["claude-code.claudeProcessWrapper"], .["claudeCode.claudeProcessWrapper"]) |
        .["claude-code.environmentVariables"] = ((.["claude-code.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL"))) |
        .["claudeCode.environmentVariables"] = ((.["claudeCode.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL"))) |
        .["gpt-codex.environmentVariables"] = ((.["gpt-codex.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL"))) |
        .["gptCodex.environmentVariables"] = ((.["gptCodex.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL"))) |
        .["codex.environmentVariables"] = ((.["codex.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL"))) |
        .["codexIDE.environmentVariables"] = ((.["codexIDE.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL"))) |
        .["codexIde.environmentVariables"] = ((.["codexIde.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL"))) |
        .["openai.environmentVariables"] = ((.["openai.environmentVariables"] // []) | map(select(.name != "ANTHROPIC_BASE_URL")))
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

  # Reset stale Continue workspace/global state — guarded by a version stamp.
  # This runs only when the Continue VSIX version changes, not on every switch,
  # so normal user sessions retain their conversation history and config state.
  home.activation.resetContinueVscodeState = lib.hm.dag.entryAfter ["linkGeneration"] ''
    _continue_version="1.3.38"
    _stamp_file="$HOME/.config/VSCodium/.continue-reset-version"
    _last_reset="$(cat "$_stamp_file" 2>/dev/null || true)"

    if [[ "$_last_reset" == "$_continue_version" ]]; then
      unset _continue_version _stamp_file _last_reset
    else
      echo "[vscodium] Continue version changed (''${_last_reset:-none} -> ''${_continue_version}), resetting stale state..."
      gdb="$HOME/.config/VSCodium/User/globalStorage/state.vscdb"
      if [ -f "$gdb" ] && command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 "$gdb" "delete from ItemTable where key like '%continue%' or key like 'Continue.%';" >/dev/null 2>&1 || true
      fi
      ws_root="$HOME/.config/VSCodium/User/workspaceStorage"
      if [ -d "$ws_root" ] && command -v sqlite3 >/dev/null 2>&1; then
        for wdb in "$ws_root"/*/state.vscdb; do
          [ -f "$wdb" ] || continue
          sqlite3 "$wdb" "delete from ItemTable where key like '%continue%' or key like 'Continue.%';" >/dev/null 2>&1 || true
        done
        unset wdb
      fi
      mkdir -p "$(dirname "$_stamp_file")"
      printf '%s' "$_continue_version" > "$_stamp_file"
      unset gdb ws_root
      unset _continue_version _stamp_file _last_reset
    fi
  '';

  # Reconcile versioned extension aliases with the registry that VSCodium
  # persists in the writable extension tree. Nix-managed extensions often land
  # as unversioned symlinks, but VSCodium tracks them with versioned IDs and
  # otherwise leaves stale .obsolete entries behind on every startup.
  home.activation.reconcileVscodeExtensionAliases = lib.hm.dag.entryAfter ["linkGeneration"] ''
        ext_root="$HOME/.vscode-oss/extensions"
        registry_file="$ext_root/extensions.json"
        obsolete_file="$ext_root/.obsolete"
        if command -v python3 >/dev/null 2>&1; then
          python3 - "$ext_root" "$registry_file" "$obsolete_file" <<'PYEOF'
    import json
    import pathlib
    import sys

    ext_root = pathlib.Path(sys.argv[1])
    registry = pathlib.Path(sys.argv[2])
    obsolete = pathlib.Path(sys.argv[3])

    def load_json(path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    if registry.is_file():
        entries = load_json(registry, [])
        if isinstance(entries, list):
            for entry in entries:
                ident = str(((entry.get("identifier") or {}).get("id")) or "").strip()
                version = str(entry.get("version") or "").strip()
                location = str(((entry.get("location") or {}).get("path")) or "").strip()
                if not ident or not version or not location:
                    continue
                target = pathlib.Path(location)
                if target.parent != ext_root or not target.exists():
                    continue
                alias_name = f"{ident.lower()}-{version}"
                alias_path = ext_root / alias_name
                if alias_path.exists() or alias_path.is_symlink():
                    continue
                if alias_name == target.name:
                    continue
                alias_path.symlink_to(target.name)

    if obsolete.is_file():
        data = load_json(obsolete, {})
        if isinstance(data, dict):
            removed = False
            for key in list(data.keys()):
                if not (ext_root / key).exists():
                    data.pop(key, None)
                    removed = True
            if removed:
                obsolete.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    PYEOF
        fi
        unset ext_root registry_file obsolete_file
  '';

  # Smart-prune AI-extension globalStorage caches to prevent extension-host freeze.
  #
  # Root cause: Gemini and Qwen Code write unbounded state into state.vscdb via
  # VSCode's globalState API instead of globalStorageUri (disk files).  Loading
  # 2+ MB on startup blocks the extension host for several seconds.
  #
  # What we strip (preserves all conversation text):
  #   google.geminicodeassist:
  #     - workspaceChange per message  — stale file snapshots from agent mode,
  #       already applied/discarded; fully recoverable from git. (68% of size)
  #     - ideContext on non-final messages — file content at send-time; stale.
  #   qwenlm.qwen-code-vscode-ide-companion:
  #     - Conversations with zero messages (empty "New Chat" sessions)
  #     - Oldest conversations beyond the 30 most-recent
  #
  # Skip when VSCodium is running to avoid corrupting the live WAL journal.
  home.activation.pruneHeavyExtensionGlobalState = lib.hm.dag.entryAfter ["linkGeneration"] ''
    if pgrep -u "$USER" -x codium >/dev/null 2>&1; then
      echo "[vscodium] codium running — skipping globalStorage pruning (runs on next switch after closing)"
    else
      _gdb="$HOME/.config/VSCodium/User/globalStorage/state.vscdb"
      if [ -f "$_gdb" ] && command -v python3 >/dev/null 2>&1; then
        python3 - "$_gdb" <<'PYEOF'
import json, sqlite3, sys, pathlib

db_path = pathlib.Path(sys.argv[1])
con = sqlite3.connect(str(db_path))
cur = con.cursor()
total_saved = 0

def prune_gemini(data):
    changed = False
    raw = data.get("geminiCodeAssist.chatThreads")
    if not raw:
        return data, changed
    outer = json.loads(raw) if isinstance(raw, str) else raw
    for account, acct_raw in outer.items():
        inner = json.loads(acct_raw) if isinstance(acct_raw, str) else acct_raw
        for tid in list(inner.keys()):
            t_raw = inner[tid]
            t = json.loads(t_raw) if isinstance(t_raw, str) else t_raw
            if not isinstance(t, dict):
                continue
            hist = t.get("history", [])
            last_idx = len(hist) - 1
            for i, msg in enumerate(hist):
                if not isinstance(msg, dict):
                    continue
                # workspaceChange: stale agent file snapshot — strip from all messages
                ws = msg.get("workspaceChange")
                if ws and len(json.dumps(ws)) > 64:
                    msg["workspaceChange"] = {}
                    changed = True
                # ideContext: stale file content — strip from all but the final message
                if i < last_idx:
                    ctx = msg.get("ideContext")
                    if ctx and len(json.dumps(ctx)) > 64:
                        msg["ideContext"] = {}
                        changed = True
            inner[tid] = json.dumps(t, separators=(",", ":"))
        outer[account] = json.dumps(inner, separators=(",", ":"))
    data["geminiCodeAssist.chatThreads"] = json.dumps(outer, separators=(",", ":"))
    return data, changed

def prune_qwen(data):
    changed = False
    convs = data.get("conversations", [])
    if not convs:
        return data, changed
    before = len(convs)
    convs = [c for c in convs if isinstance(c, dict) and c.get("messages")]
    if len(convs) < before:
        changed = True
    if len(convs) > 30:
        convs = sorted(convs, key=lambda c: c.get("updatedAt", 0), reverse=True)[:30]
        changed = True
    if changed:
        data["conversations"] = convs
    return data, changed

for ext_key, fn in [
    ("google.geminicodeassist",              prune_gemini),
    ("qwenlm.qwen-code-vscode-ide-companion", prune_qwen),
]:
    cur.execute("SELECT value FROM ItemTable WHERE key=?", (ext_key,))
    row = cur.fetchone()
    if not row:
        continue
    before = len(row[0])
    d, changed = fn(json.loads(row[0]))
    if changed:
        v = json.dumps(d, separators=(",", ":"))
        cur.execute("UPDATE ItemTable SET value=? WHERE key=?", (v, ext_key))
        saved = before - len(v)
        total_saved += saved
        print(f"[vscodium] pruned {ext_key}: {before//1024}KB -> {len(v)//1024}KB (saved {saved//1024}KB)")

if total_saved > 0:
    con.commit()
    print(f"[vscodium] globalStorage reclaimed: {total_saved//1024}KB total")
con.close()
PYEOF
      fi
      unset _gdb
    fi
  '';

  # Install runtime-mutable extensions that write inside their own install dir.
  home.activation.ensureMutableRuntimeVscodeExtensions = lib.hm.dag.entryAfter ["linkGeneration"] ''
    _codium="${vscodiumWrapped}/bin/codium"
    if [[ ! -x "$_codium" ]]; then
      echo "[vscodium] codium not found at ${vscodiumWrapped}/bin/codium; skipping mutable extension install"
    elif pgrep -u "$USER" -x codium >/dev/null 2>&1; then
      echo "[vscodium] codium is running; skipping extension install (run vscodium-repair after closing)"
    else
      ext_root="$HOME/.vscode-oss/extensions"
      mkdir -p "$ext_root"
      # Clear stale Continue quarantine markers from earlier immutable installs.
      rm -rf "$ext_root"/continue.continue-*.disabled 2>/dev/null || true
      # Continue mutates files under its own extension dir; install a pinned
      # writable VSIX copy instead of immutable Nix-store linkage.
      echo "[vscodium] Installing Continue extension..."
      if env -u NIXOS_OZONE_WL "$_codium" --install-extension ${continueMutableVsix} --force 2>&1 | tail -3; then
        echo "[vscodium] Continue extension installed"
      else
        echo "[vscodium] WARNING: Continue extension install exited non-zero" >&2
      fi
      for ext_id in ${lib.concatStringsSep " " vscodeMutableRuntimeExtensions}; do
        alias_path="$ext_root/$ext_id"
        if [ -L "$alias_path" ]; then
          rm -f "$alias_path"
        fi
        env -u NIXOS_OZONE_WL "$_codium" --install-extension "$ext_id" --force 2>/dev/null || true
      done
      unset ext_root ext_id alias_path
    fi
  '';

  home.activation.cleanupVscodiumDesktopEntries = lib.hm.dag.entryAfter ["writeBoundary"] ''
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

  # ---- vscodium-repair recovery script ------------------------------------
  # Manual recovery tool: stops codium, clears stale state, reinstalls
  # Continue extension, restores theme settings.  Run when Continue is
  # broken, the theme reverts, or extensions stop loading.
  home.file.".local/bin/vscodium-repair" = {
    executable = true;
    text = ''
            #!/usr/bin/env bash
            set -euo pipefail
            echo "[vscodium-repair] Starting VSCodium recovery..."

            # 1. Stop any running codium instance
            if pgrep -u "$USER" -x codium >/dev/null 2>&1; then
              echo "[vscodium-repair] Stopping running codium..."
              pkill -u "$USER" -x codium || true
              sleep 2
            fi

            ext_root="$HOME/.vscode-oss/extensions"
            settings_file="$HOME/.config/VSCodium/User/settings.json"
            mkdir -p "$ext_root"

            # 2. Clear stale AI extension obsolete markers
            obsolete="$ext_root/.obsolete"
            if [ -f "$obsolete" ] && command -v python3 >/dev/null 2>&1; then
              echo "[vscodium-repair] Clearing stale AI extension obsolete markers..."
              python3 - "$obsolete" <<'PYEOF'
      import json, pathlib, sys
      path = pathlib.Path(sys.argv[1])
      try:
          data = json.loads(path.read_text(encoding="utf-8"))
      except Exception:
          sys.exit(0)
      if not isinstance(data, dict):
          sys.exit(0)
      prefixes = (
          "continue.",
          "google.geminicodeassist-",
          "google.gemini-cli-vscode-ide-companion-",
          "qwenlm.qwen-code-vscode-ide-companion-",
          "openai.chatgpt-",
          "anthropic.claude-code-",
      )
      removed = [k for k in list(data.keys()) if k.lower().startswith(prefixes)]
      for k in removed:
          data.pop(k, None)
      if removed:
          path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
          print(f"  Removed {len(removed)} marker(s): {removed}")
      PYEOF
            fi

            # 3. Remove disabled Continue extension dirs
            for d in "$ext_root"/continue.continue-*.disabled; do
              [ -d "$d" ] || continue
              echo "[vscodium-repair] Removing disabled dir: $d"
              rm -rf "$d"
            done

            # 4. Reinstall Continue extension from pinned VSIX
            echo "[vscodium-repair] Reinstalling Continue extension..."
            env -u NIXOS_OZONE_WL codium --install-extension ${continueMutableVsix} --force

            # 5. Enforce theme and core settings
            if [ -f "$settings_file" ] && command -v jq >/dev/null 2>&1; then
              echo "[vscodium-repair] Enforcing theme settings..."
              tmp="$(mktemp)"
              if jq '
                .["workbench.colorTheme"] = "Activate SCARLET protocol (beta)" |
                .["workbench.preferredDarkColorTheme"] = "Activate SCARLET protocol (beta)" |
                .["window.autoDetectColorScheme"] = false |
                .["continue.enableTabAutocomplete"] = true |
                .["continue.telemetryEnabled"] = false
              ' "$settings_file" > "$tmp"; then
                mv "$tmp" "$settings_file"
                chmod u+rw "$settings_file"
              else
                rm -f "$tmp"
              fi
            fi

            # 6. Reset Continue state in VSCodium global storage
            gdb="$HOME/.config/VSCodium/User/globalStorage/state.vscdb"
            if [ -f "$gdb" ] && command -v sqlite3 >/dev/null 2>&1; then
              echo "[vscodium-repair] Clearing Continue global state..."
              sqlite3 "$gdb" "delete from ItemTable where key like '%continue%' or key like 'Continue.%';" 2>/dev/null || true
            fi

            # 7. Prune oversized Gemini/Qwen extension state that blocks the
            # extension host during startup.
            if [ -f "$gdb" ] && command -v python3 >/dev/null 2>&1; then
              echo "[vscodium-repair] Pruning heavy Gemini/Qwen global state..."
              python3 - "$gdb" <<'PYEOF'
      import json, pathlib, sqlite3, sys

      db_path = pathlib.Path(sys.argv[1])
      con = sqlite3.connect(str(db_path))
      cur = con.cursor()
      total_saved = 0

      def prune_gemini(data):
          changed = False
          raw = data.get("geminiCodeAssist.chatThreads")
          if not raw:
              return data, changed
          outer = json.loads(raw) if isinstance(raw, str) else raw
          for account, acct_raw in outer.items():
              inner = json.loads(acct_raw) if isinstance(acct_raw, str) else acct_raw
              for tid in list(inner.keys()):
                  t_raw = inner[tid]
                  t = json.loads(t_raw) if isinstance(t_raw, str) else t_raw
                  if not isinstance(t, dict):
                      continue
                  hist = t.get("history", [])
                  last_idx = len(hist) - 1
                  for i, msg in enumerate(hist):
                      if not isinstance(msg, dict):
                          continue
                      ws = msg.get("workspaceChange")
                      if ws and len(json.dumps(ws)) > 64:
                          msg["workspaceChange"] = {}
                          changed = True
                      if i < last_idx:
                          ctx = msg.get("ideContext")
                          if ctx and len(json.dumps(ctx)) > 64:
                              msg["ideContext"] = {}
                              changed = True
                  inner[tid] = json.dumps(t, separators=(",", ":"))
              outer[account] = json.dumps(inner, separators=(",", ":"))
          data["geminiCodeAssist.chatThreads"] = json.dumps(outer, separators=(",", ":"))
          return data, changed

      def prune_qwen(data):
          changed = False
          convs = data.get("conversations", [])
          if not convs:
              return data, changed
          before = len(convs)
          convs = [c for c in convs if isinstance(c, dict) and c.get("messages")]
          if len(convs) < before:
              changed = True
          if len(convs) > 30:
              convs = sorted(convs, key=lambda c: c.get("updatedAt", 0), reverse=True)[:30]
              changed = True
          if changed:
              data["conversations"] = convs
          return data, changed

      for ext_key, fn in [
          ("google.geminicodeassist", prune_gemini),
          ("qwenlm.qwen-code-vscode-ide-companion", prune_qwen),
      ]:
          cur.execute("SELECT value FROM ItemTable WHERE key=?", (ext_key,))
          row = cur.fetchone()
          if not row:
              continue
          before = len(row[0])
          payload, changed = fn(json.loads(row[0]))
          if changed:
              value = json.dumps(payload, separators=(",", ":"))
              cur.execute("UPDATE ItemTable SET value=? WHERE key=?", (value, ext_key))
              saved = before - len(value)
              total_saved += saved
              print(f"  pruned {ext_key}: {before//1024}KB -> {len(value)//1024}KB")

      if total_saved > 0:
          con.commit()
      con.close()
      PYEOF
            fi

            # 8. Archive oversized Continue session transcripts. Large
            # session JSON payloads can stall Continue startup and resume.
            continue_sessions="$HOME/.continue/sessions"
            if [ -d "$continue_sessions" ] && command -v python3 >/dev/null 2>&1; then
              echo "[vscodium-repair] Archiving oversized Continue sessions..."
              python3 - "$continue_sessions" <<'PYEOF'
      import pathlib, shutil, sys, time

      sessions_dir = pathlib.Path(sys.argv[1])
      archive_dir = sessions_dir.parent / f"sessions-backup-{time.strftime('%Y%m%d-%H%M%S')}"
      candidates = sorted(
          (p for p in sessions_dir.glob("*.json") if p.is_file()),
          key=lambda p: p.stat().st_mtime,
          reverse=True,
      )
      keep_names = {p.name for p in candidates[:12]}
      moved = []
      for path in candidates:
          size_mb = path.stat().st_size / (1024 * 1024)
          if path.name in keep_names and size_mb <= 8:
              continue
          if size_mb < 8 and path.name in keep_names:
              continue
          archive_dir.mkdir(parents=True, exist_ok=True)
          target = archive_dir / path.name
          shutil.move(str(path), str(target))
          moved.append((path.name, round(size_mb, 1)))
      if moved:
          print(f"  archived {len(moved)} Continue session(s) to {archive_dir}")
          for name, size_mb in moved[:10]:
              print(f"    - {name} ({size_mb} MB)")
      PYEOF
            fi

            # 9. Reset the Codex extension state DB when the current on-disk
            # migration lineage no longer matches the installed extension.
            codex_state="$HOME/.codex/state_5.sqlite"
            if [ -f "$codex_state" ]; then
              stamp="$(date +%Y%m%d-%H%M%S)"
              backup="$HOME/.codex/state_5.sqlite.pre-vscodium-repair-$stamp"
              echo "[vscodium-repair] Backing up Codex state DB to $backup"
              mv "$codex_state" "$backup"
            fi

            # 10. Force Continue config version bump so createContinueConfig rewrites it
            cfg="$HOME/.continue/config.json"
            if [ -f "$cfg" ] && command -v jq >/dev/null 2>&1; then
              echo "[vscodium-repair] Resetting Continue config version (will regenerate on next hm switch)..."
              tmp="$(mktemp)"
              if jq '.__configVersion = "0"' "$cfg" > "$tmp"; then
                mv "$tmp" "$cfg"
              else
                rm -f "$tmp"
              fi
            fi

            echo "[vscodium-repair] Done. Launch VSCodium with: codium"
            echo "  Run 'home-manager switch' to regenerate the Continue config."
    '';
  };

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
      unset NIXOS_OZONE_WL
      unset ELECTRON_OZONE_PLATFORM_HINT
      exec ${pkgs.vscodium}/bin/codium --ozone-platform=x11 "$@"
    '';
  };

  # Ship the first-run prompt wizard from the repository into ~/.local/bin.
  home.file.".local/bin/p10k-setup-wizard.sh" = lib.mkIf (builtins.pathExists ../../scripts/deploy/p10k-setup-wizard.sh) {
    source = ../../scripts/deploy/p10k-setup-wizard.sh;
    executable = true;
  };

  home.file.".local/share/wallpapers/current-desktop-background.png".source =
    ../../templates + "/ChatGPT Image Feb 21, 2026, 02_05_57 PM.png";

  # Retire legacy COSMIC font enforcement units/scripts from earlier generations.
  # Cleanup happens in activation below; defining disabled home.file entries
  # without source/text trips HM evaluation on newer releases.
  home.file.".config/playwright/cli.config.json".text = builtins.toJSON {
    browser = {
      launchOptions = {
        executablePath = "${pkgs.chromium}/bin/chromium";
        headless = true;
      };
      contextOptions = {
        viewport = {
          width = 1440;
          height = 960;
        };
      };
    };
  };
  home.file.".codex/skills/playwright/scripts/playwright_cli.sh" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      if ! command -v npx >/dev/null 2>&1; then
        echo "Error: npx is required but not found on PATH." >&2
        exit 1
      fi

      has_session_flag="false"
      has_config_flag="false"
      for arg in "$@"; do
        case "$arg" in
          --session|--session=*)
            has_session_flag="true"
            ;;
          --config|--config=*)
            has_config_flag="true"
            ;;
        esac
      done

      cmd=(npx --yes --package @playwright/cli playwright-cli)
      if [[ "$has_session_flag" != "true" && -n "''${PLAYWRIGHT_CLI_SESSION:-}" ]]; then
        cmd+=(--session "$PLAYWRIGHT_CLI_SESSION")
      fi
      if [[ "$has_config_flag" != "true" ]]; then
        cmd+=(--config "$HOME/.config/playwright/cli.config.json")
      fi
      cmd+=("$@")

      exec "''${cmd[@]}"
    '';
  };

  # Refresh font cache so newly installed user-profile fonts are picked up.
  home.activation.refreshUserFontCache = lib.hm.dag.entryAfter ["writeBoundary"] ''
    ${pkgs.fontconfig}/bin/fc-cache -f "$HOME/.nix-profile/share/fonts" >/dev/null 2>&1 || true
    ${pkgs.fontconfig}/bin/fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || true
    ${pkgs.fontconfig}/bin/fc-cache -f "$HOME/.fonts" >/dev/null 2>&1 || true
  '';

  # ---- Continue.dev config — multi-model + aq-hints --------------------------
  # Written on first activation or when __configVersion is outdated.
  # Not managed as a symlink so the user can edit it without HM clobbering
  # their changes on every switch. We still rewrite when the generated schema
  # changes or when the authoritative local chat lane/provider wiring drifts.
  home.activation.createContinueConfig = lib.hm.dag.entryAfter ["writeBoundary"] ''
        _config_version="30.0"
        _cfg="$HOME/.continue/config.json"
        _needs_write=false
        _config_contract_ok=false

        if [ ! -f "$_cfg" ]; then
          _needs_write=true
        elif command -v jq >/dev/null 2>&1; then
          _existing_ver="$(jq -r '.__configVersion // "0"' "$_cfg" 2>/dev/null || echo "0")"
          if [ "$_existing_ver" != "$_config_version" ]; then
            _needs_write=true
          fi
          if jq -e --arg api_base "${continueApiBase}" --arg cli_api_base "http://127.0.0.1:8089/v1" '
            (
              .models // []
            ) as $models
            | (
              $models
              | any(
                  .[]?;
                  .title == "Local Agent (Harness-Aware)"
                  and .apiBase == $api_base
                  and ((.requestOptions.headers["X-AI-Profile"] // "") == "local-agent")
                )
            )
            and (
              $models
              | any(
                  .[]?;
                  .title == "Claude (OAuth — CLI Bridge)"
                  and .apiBase == $cli_api_base
                  and (.model == "claude-cli")
                )
            )
            and (
              $models
              | any(
                  .[]?;
                  .title == "Codex (OAuth — CLI Bridge)"
                  and .apiBase == $cli_api_base
                  and (.model == "codex-cli")
                )
            )
            and (
              (.tabAutocompleteModel.apiBase // "") == $api_base
              and ((.tabAutocompleteModel.requestOptions.headers["X-AI-Profile"] // "") == "continue-local")
            )
            and (
              (.contextProviders // [])
              | any(.[]?; .name == "aq-hints" and ((.params.endpoint // "") == "http://127.0.0.1:8003/hints"))
            )
          ' "$_cfg" >/dev/null 2>&1; then
            _config_contract_ok=true
          else
            _needs_write=true
          fi
          unset _existing_ver
        else
          _needs_write=true
        fi

        if [ "$_needs_write" = true ]; then
          mkdir -p "$HOME/.continue"
          cat > "$_cfg" << 'CONTINUE_EOF'
    {
      "__configVersion": "30.0",
      "__frozen": "DO NOT MODIFY. contextLength=32000 and maxTokens=4096 for Local Agent are LOCKED. aq-hints remains required by the current harness Continue contract. Claude+Codex CLI Bridge models must remain.",
      "rules": [
        "You are AQ, an expert AI agent embedded in the NixOS-Dev-Quick-Deploy harness. You have full MCP tool access via the Harness MCP server.",
        "HARNESS-FIRST: Before answering questions about files or services, use tools (read_file, run_terminal_command, grep_search) to search first. Never guess.",
        "TOOL DISCIPLINE: Use MCP tools for harness ops: harness_health, get_hints, hybrid_search, get_working_memory, store_memory, query_aidb, workflow_plan, get_prsi_pending, prsi_orchestrate.",
        "AGENT MODE: In agent mode, issue tool calls directly — do not announce them. Do not say 'I will now call...' just call the tool.",
        "SESSION START: At the start of any agent session, call get_working_memory first, then harness_health.",
        "SEARCH-FIRST: Use get_hints MCP tool for ranked workflow guidance before implementing anything.",
        "NO ls-FIRST: Never run ls on repo root as the first action. Use targeted grep or read specific files.",
        "COMMIT DISCIPLINE: git add <files> && git commit -m 'type(scope): msg\\n\\nCo-Authored-By: <active-agent-name> <noreply@anthropic.com>' — replace <active-agent-name> with the model generating the work. Never hardcode a specific model version.",
        "CONTEXT LIMITS: For local models, keep messages short. Use summarize_context MCP tool if conversation grows long.",
        "RETRY BUDGET: After 2 failed retries, transport hangs, or repeated 'message exceeds context limit', stop replaying the same transcript. Checkpoint decisions and next steps to harness memory, then start a fresh session from get_working_memory or aq-memory recall.",
        "TRANSCRIPT HYGIENE: Do not paste large logs, repo maps, or repeated bootstrap banners into editor chat when a compact summary or file reference will do.",
        "PORTS: llama:8080 embed:8081 aidb:8002 hybrid:8003 ralph:8004 swb:8085 cli-bridge:8089 dash:8889 grafana:3000 owui:3001",
        "CONFIG FREEZE — contextLength=32000 maxTokens=4096 for Local Agent are LOCKED. Do not reduce. Smaller values cause message-exceeds-context hangs in Continue.",
        "CONFIG FREEZE — aq-hints remains pinned in contextProviders while the current Continue v29 harness contract and aq-qa checks require coordinator-backed hints.",
        "AGENT ROUTING — Monitoring, polling, and background tasks must use LOCAL models only. Never route autonomous/background work to remote/paid models.",
        "CONFIG FREEZE — Claude (OAuth — CLI Bridge) and Codex (OAuth — CLI Bridge) model entries are required. Do not remove them."
      ],
      "models": [
        {
          "title": "Local Agent (Harness-Aware)",
          "provider": "openai",
          "apiKey": "local-llama-cpp",
          "apiBase": "${continueApiBase}",
          "model": "${aiLlamaModel}",
          "requestOptions": {
            "headers": {
              "X-AI-Profile": "local-agent"
            }
          },
          "contextLength": ${toString localAgentContextLength},
          "maxTokens": ${toString localAgentChatMaxTokens}
        },
        {
          "title": "Continue Local (Compact)",
          "provider": "openai",
          "apiKey": "local-llama-cpp",
          "apiBase": "${continueApiBase}",
          "model": "${aiLlamaModel}",
          "requestOptions": {
            "headers": {
              "X-AI-Profile": "continue-local"
            }
          },
          "contextLength": ${toString continueContextLength},
          "maxTokens": ${toString continueChatMaxTokens}
        },
        {
          "title": "Claude (OAuth — CLI Bridge)",
          "provider": "openai",
          "apiKey": "cli-oauth",
          "apiBase": "http://127.0.0.1:8089/v1",
          "model": "claude-cli",
          "contextLength": ${toString continueRemoteContextLength},
          "maxTokens": ${toString continueRemoteMaxTokens}
        },
        {
          "title": "Codex (OAuth — CLI Bridge)",
          "provider": "openai",
          "apiKey": "cli-oauth",
          "apiBase": "http://127.0.0.1:8089/v1",
          "model": "codex-cli",
          "contextLength": ${toString continueRemoteContextLength},
          "maxTokens": ${toString continueRemoteMaxTokens}
        },
        {
          "title": "Remote Coding (Switchboard)",
          "provider": "openai",
          "apiKey": "dummy",
          "apiBase": "${continueApiBase}",
          "model": "AUTODETECT",
          "requestOptions": {
            "headers": {
              "X-AI-Profile": "remote-coding"
            }
          },
          "contextLength": ${toString continueRemoteContextLength},
          "maxTokens": ${toString continueRemoteMaxTokens}
        },
        {
          "title": "Remote Reasoning (Switchboard)",
          "provider": "openai",
          "apiKey": "dummy",
          "apiBase": "${continueApiBase}",
          "model": "AUTODETECT",
          "requestOptions": {
            "headers": {
              "X-AI-Profile": "remote-reasoning"
            }
          },
          "contextLength": ${toString continueRemoteContextLength},
          "maxTokens": ${toString continueRemoteMaxTokens}
        },
        {
          "title": "Remote Free (Switchboard)",
          "provider": "openai",
          "apiKey": "dummy",
          "apiBase": "${continueApiBase}",
          "model": "AUTODETECT",
          "requestOptions": {
            "headers": {
              "X-AI-Profile": "remote-free"
            }
          },
          "contextLength": ${toString continueRemoteContextLength},
          "maxTokens": ${toString continueRemoteMaxTokens}
        },
        {
          "title": "Remote Gemini (Switchboard)",
          "provider": "openai",
          "apiKey": "dummy",
          "apiBase": "${continueApiBase}",
          "model": "AUTODETECT",
          "requestOptions": {
            "headers": {
              "X-AI-Profile": "remote-gemini"
            }
          },
          "contextLength": ${toString continueRemoteContextLength},
          "maxTokens": ${toString continueRemoteMaxTokens}
        }
      ],
      "tabAutocompleteModel": {
        "title": "Tab Autocomplete (Continue Local)",
        "provider": "openai",
        "apiKey": "local-llama-cpp",
        "apiBase": "${continueApiBase}",
        "model": "${aiLlamaModel}",
        "requestOptions": {
          "headers": {
            "X-AI-Profile": "continue-local"
          }
        },
        "contextLength": ${toString continueContextLength},
        "maxTokens": ${toString continueTabMaxTokens}
      },
      "contextProviders": [
        {
          "name": "aq-hints",
          "params": {
            "endpoint": "http://127.0.0.1:8003/hints"
          }
        },
        { "name": "file", "params": {} },

        { "name": "diff", "params": {} },
        { "name": "codebase", "params": {} },
        { "name": "terminal", "params": {} },
        { "name": "problems", "params": {} }
      ],
      "slashCommands": [
        { "name": "edit", "description": "Edit highlighted code" },

        { "name": "comment", "description": "Add comments" },
        { "name": "share", "description": "Export chat session to markdown" },
        { "name": "cmd", "description": "Generate a shell command" },
        { "name": "commit", "description": "Generate a git commit message" }
      ],
      "mcpServers": [
        {
          "name": "Harness MCP",
          "command": "python3",
          "args": ["/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/mcp-bridge-hybrid.py"],
          "env": {
            "HYBRID_URL": "http://127.0.0.1:8003",
            "AIDB_URL": "http://127.0.0.1:8002",
            "AIDB_API_KEY_FILE": "/run/secrets/aidb_api_key",
            "HYBRID_API_KEY_FILE": "/run/secrets/hybrid_coordinator_api_key"
          }
        }
      ],
      "allowAnonymousTelemetry": false
    }
    CONTINUE_EOF
          echo "[createContinueConfig] Wrote Continue config v$_config_version"
        fi
        unset _config_version _cfg _needs_write _config_contract_ok
  '';

  home.activation.migrateContinueConfigApiBase = lib.hm.dag.entryAfter ["createContinueConfig"] ''
    cfg="$HOME/.continue/config.json"
    if [ -f "$cfg" ] && command -v jq >/dev/null 2>&1; then
      runtime_base="${continueApiBase}"

      detected_model="$(${pkgs.curl}/bin/curl --silent --show-error --fail --max-time 10 \
        "$runtime_base/models" 2>/dev/null | jq -r '.data[0].id // empty' || true)"
      if [ -z "$detected_model" ]; then
        detected_model="${aiLlamaModel}"
      fi

      tmp="$(mktemp)"
      if jq --arg newBase "$runtime_base" --arg model "$detected_model" '
        .models = ((.models // []) | map(
          if ((.provider // "") == "openai")
             and (((.requestOptions // {}).headers // {})["X-AI-Profile"] // "") != ""
          then
            .apiBase = $newBase | .model = $model
          else
            .
          end
        )) |
        .tabAutocompleteModel = ((.tabAutocompleteModel // {})
          | if ((.provider // "openai") == "openai") then .apiBase = $newBase | .model = $model else . end)
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
  home.activation.createMcpConfig = lib.hm.dag.entryAfter ["writeBoundary"] ''
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
  home.activation.linkSharedAgentSkills = lib.hm.dag.entryAfter ["createMcpConfig"] ''
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

  home.activation.ensureCodexSkillExecutables = lib.hm.dag.entryAfter ["linkSharedAgentSkills"] ''
    skills_root="$HOME/.codex/skills"
    if [ -d "$skills_root" ]; then
      find "$skills_root" -type f \( -path '*/scripts/*.sh' -o -path '*/scripts/*.py' \) -exec chmod 0755 {} +
    fi
    unset skills_root
  '';

  # Seed ~/.claude/settings.json with the stdio MCP server catalog so Claude
  # Code has access to all development tools (filesystem, git, fetch, etc.)
  # on first login.  Only writes when mcpServers key is absent; safe to run
  # on every home-manager switch — skips if already configured.
  home.activation.seedClaudeSettings = lib.hm.dag.entryAfter ["linkSharedAgentSkills"] ''
    mkdir -p "$HOME/.claude"
    settings="$HOME/.claude/settings.json"
    mcp_cfg="$HOME/.mcp/config.json"
    if [ -f "$mcp_cfg" ] && ${pkgs.jq}/bin/jq -e '.mcpServers' "$mcp_cfg" > /dev/null 2>&1; then
      if [ ! -f "$settings" ] || [ "$(${pkgs.jq}/bin/jq -r 'keys | length' "$settings" 2>/dev/null)" = "0" ]; then
        # Empty or missing settings — seed with the MCP catalog
        cp "$mcp_cfg" "$settings"
      elif ! ${pkgs.jq}/bin/jq -e '.mcpServers' "$settings" > /dev/null 2>&1; then
        # Has other settings but no mcpServers — merge without overwriting
        tmp="$(mktemp)"
        ${pkgs.jq}/bin/jq --slurpfile mcp "$mcp_cfg" \
          '. * {"mcpServers": $mcp[0].mcpServers}' "$settings" > "$tmp" \
          && mv "$tmp" "$settings" \
          || rm -f "$tmp"
        unset tmp
      fi
    fi
    unset settings mcp_cfg
  '';

  # Allow GPT4All Flatpak to read locally hosted llama.cpp models.
  home.activation.configureGpt4AllModelAccess = lib.hm.dag.entryAfter ["writeBoundary"] ''
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

  # Phase 8.1.4 — run eval regression check at user session startup.
  # Never blocks login; threshold failures are logged as warnings.
  systemd.user.services.ai-eval-startup = {
    Unit = {
      Description = "AI stack eval regression check on login";
      After = ["graphical-session.target"];
    };
    Service = {
      Type = "oneshot";
      ExecStart = "${pkgs.bash}/bin/bash -lc '${repoPath}/scripts/automation/run-eval.sh --threshold 60 --output ${repoPath}/ai-stack/eval/results || true'";
    };
    Install = {
      WantedBy = ["default.target"];
    };
  };

  # Remove stale wants links and clear any failed state from retired units.
  home.activation.cleanupCosmicFontUnitWants = lib.hm.dag.entryAfter ["writeBoundary"] ''
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
  home.activation.preReloadResetCosmicFontUnits = lib.hm.dag.entryBefore ["reloadSystemd"] ''
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user disable --now enforce-cosmic-term-font.service enforce-cosmic-term-font.path >/dev/null 2>&1 || true
      systemctl --user reset-failed enforce-cosmic-term-font.service enforce-cosmic-term-font.path >/dev/null 2>&1 || true
    fi
  '';
}
