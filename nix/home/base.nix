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
  aiLlamaModel = lib.attrByPath ["mySystem" "aiStack" "llamaCpp" "model"] "local-model" systemConfig;
  aiLlamaCtxSize = lib.attrByPath ["mySystem" "aiStack" "llamaCpp" "ctxSize"] 16384 systemConfig;
  aiHybridPort = lib.attrByPath ["mySystem" "mcpServers" "hybridPort"] (getRegistryPort "mcpHybrid") systemConfig;
  aiAidbPort = lib.attrByPath ["mySystem" "mcpServers" "aidbPort"] (getRegistryPort "mcpAidb") systemConfig;
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
  # ~/.npm-global/bin is added so the Gemini CLI companion and Codex extensions
  # can find their respective CLIs (gemini, codex) when VSCodium is launched
  # from the desktop (where the shell profile may not have run yet).
  terminfoDir = "/run/current-system/sw/share/terminfo";
  vscodiumPathValue = "${config.home.homeDirectory}/.local/bin:${config.home.homeDirectory}/.npm-global/bin:${config.home.homeDirectory}/.nix-profile/bin:/run/current-system/sw/bin:\${env:PATH}";
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
      name = "TERMINFO";
      value = terminfoDir;
    }
    {
      name = "TERMINFO_DIRS";
      value = terminfoDir;
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
      # Name must end in .vsix: nixpkgs' unpack-vsix-setup-hook (post-2026-07 bump)
      # only unpacks *.vsix. (The pre-bump stdenv hook needed the opposite .zip rename.)
      name = "openai-chatgpt.vsix";
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
    # Name must end in .vsix: nixpkgs' unpack-vsix-setup-hook (post-2026-07 bump)
    # only unpacks *.vsix; a .zip name fails unpackPhase with "do not know how to unpack".
    pkgs.runCommand "max-ss.cyberpunk-1.2.14.vsix" {
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
    # openai.chatgpt (Codex) — the correct setting key is chatgpt.cliExecutable.
    # The extension has no environmentVariables setting; it relies on PATH.
    # ~/.npm-global/bin/codex is reachable via vscodiumPathValue above.
    # The stale codex.*/gpt-codex.*/etc. keys below are no-ops (not in the
    # extension schema) and will be pruned by the enforceCodexVscodeSettings
    # activation hook on rebuild.
    "chatgpt.cliExecutable" = "${config.home.homeDirectory}/.npm-global/bin/codex";
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

    # Agentic CLI tools (Token-optimized for AI agents)
    (pkgs.callPackage ../pkgs/agentic-tools.nix {})

    # Native LLM CLI tools (Phase 36 restoration)
    llama-cpp

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
        ps.httpx
        ps.fastapi
        ps.uvicorn
        ps.pydantic
        ps.requests
        ps.psutil
        ps.redis
        # pyyaml: governance gates (check-doc-frontmatter, env-contract) and several
        # aq-* CLIs parse YAML; without it they degrade to yaml-free/skip fallbacks.
        # Provisioning it in the CLI python lets those checks validate fully.
        ps.pyyaml
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
        # Gradio v5 is currently marked insecure in nixpkgs; keep it out of the
        # always-installed Home Manager Python bundle and use a project venv
        # when a demo UI explicitly needs it.
        # Playwright for browser automation — uses system chromium (no download needed)
        playwright
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
      # NixOS rebuild shortcuts — nrs runs preflight first, nrs-force skips it
      nrs = "scripts/governance/pre-rebuild-preflight.sh && sudo nixos-rebuild switch --flake .#hyperd-ai-dev";
      nrs-force = "sudo nixos-rebuild switch --flake .#hyperd-ai-dev";
      nrb = "sudo nixos-rebuild boot --flake .#hyperd-ai-dev";
      nrd = "sudo nixos-rebuild dry-build --flake .#hyperd-ai-dev";
      hms = "home-manager switch --flake .#hyperd";
      # AI CLI tools
      continue = "cn"; # Continue CLI shorthand
      # Agentic CLI Tools (Token-optimized)
      ag = "agrep";
      al = "als";
      ac = "acat";
      as = "asum";
      ad = "adiff";
      # Llama.cpp & Local Agent CLI tools
      lc = "llama-cli";
      lsrv = "llama-server";
      aq-loop = "aq-agent-loop";
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

      # Phase 86 — HITL alert indicator
      # Prints "[ ATTN: N PENDING ALERT(S) ]" before each prompt if human_gate
      # items are waiting in the attention queue.
      _aq_alert_precmd() {
        local _attn="$HOME/Documents/NixOS-Dev-Quick-Deploy/.agents/attention/ATTENTION.json"
        [[ -f "$_attn" ]] || return 0
        local _n
        _n=$(jq '[.alerts[] | select(.status=="pending")] | length' "$_attn" 2>/dev/null) || return 0
        (( _n > 0 )) && print -P "%F{red}%B[ ATTN: $_n PENDING ALERT(S) — run aq-alerts ]%b%f"
      }
      precmd_functions+=(_aq_alert_precmd)

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
    TERMINFO = terminfoDir;
    TERMINFO_DIRS = terminfoDir;
    # npm global prefix for AI CLI tools (Continue, pi, etc.)
    NPM_CONFIG_PREFIX = "${config.home.homeDirectory}/.npm-global";
    # Playwright — use nix-installed chromium; never download browsers at runtime
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1";
    CHROMIUM_PATH = "${pkgs.chromium}/bin/chromium";
  };

  home.sessionPath = [
    "$HOME/.local/bin"
    "$HOME/.npm-global/bin" # codex, qwen, gemini, pi CLI agents
    "${repoPath}/scripts/ai"
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
  # `vscodeProfiles` writes its generated settings late in activation, so this
  # must run after it as a final convergence pass or the active color theme can
  # disappear even though the preferred-theme keys remain present.
  #
  # WARNING: if VSCodium is running during home-manager switch it will overwrite
  # settings.json from its in-memory state after this patch executes, losing the
  # colorTheme key again.  Close VSCodium before running `nrs` or `hms`.
  home.activation.enforceVSCodiumTheme = lib.hm.dag.entryAfter ["vscodeProfiles"] ''
    settings_file="$HOME/.config/VSCodium/User/settings.json"
    if pgrep -x "codium" >/dev/null 2>&1; then
      echo "[home-manager] WARNING: VSCodium is running — theme patch applied but may be" >&2
      echo "               overwritten when VSCodium saves settings. Restart VSCodium after" >&2
      echo "               this switch to apply the Cyberpunk/SCARLET theme." >&2
    fi
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

  # Enforce Codex extension settings on every activation.
  # settings.json is mutable (seeded once), so policy-critical keys must be
  # patched here rather than relying on the one-shot createVSCodiumSettings.
  #
  # Codex:  set chatgpt.cliExecutable to the npm-global binary; prune stale
  #         no-op keys (codex.*, gpt-codex.*, etc.) that the extension ignores.
  home.activation.enforceCodexVscodeSettings = lib.hm.dag.entryAfter ["migrateClaudeVscodeSettings"] ''
    settings_file="$HOME/.config/VSCodium/User/settings.json"
    if [ -f "$settings_file" ] && command -v jq >/dev/null 2>&1; then
      tmp="$(mktemp)"
      if jq '
        .["chatgpt.cliExecutable"] = (env.HOME + "/.npm-global/bin/codex") |
        del(
          .["gpt-codex.executablePath"], .["gpt-codex.environmentVariables"], .["gpt-codex.autoStart"],
          .["gptCodex.executablePath"], .["gptCodex.environmentVariables"], .["gptCodex.autoStart"],
          .["codex.executablePath"], .["codex.environmentVariables"], .["codex.autoStart"],
          .["codexIDE.executablePath"], .["codexIDE.environmentVariables"], .["codexIDE.autoStart"],
          .["codexIde.executablePath"], .["codexIde.environmentVariables"], .["codexIde.autoStart"],
          .["openai.executablePath"], .["openai.environmentVariables"], .["openai.autoStart"]
        )
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
    ai_obsolete_prefixes = (
        "continue.",
        "qwenlm.qwen-code-vscode-ide-companion-",
        "openai.chatgpt-",
        "anthropic.claude-code-",
    )

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
                if key.lower().startswith(ai_obsolete_prefixes) or not (ext_root / key).exists():
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
  # Root cause: Qwen Code writes unbounded state into state.vscdb via
  # VSCode's globalState API instead of globalStorageUri (disk files).  Loading
  # 2+ MB on startup blocks the extension host for several seconds.
  #
  # What we strip (preserves all conversation text):
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
      obsolete="$ext_root/.obsolete"
      if [ -f "$obsolete" ] && command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,pathlib,sys; p=pathlib.Path(sys.argv[1]); prefixes=("continue.","qwenlm.qwen-code-vscode-ide-companion-","openai.chatgpt-","anthropic.claude-code-"); data=json.loads(p.read_text(encoding="utf-8")); changed=False
if isinstance(data, dict):
    for key in list(data):
        if key.lower().startswith(prefixes):
            data.pop(key, None); changed=True
if changed:
    p.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")' "$obsolete" || true
      fi
      unset ext_root ext_id alias_path obsolete
    fi
  '';

  home.activation.clearAiVscodeObsoleteMarkers = lib.hm.dag.entryAfter [
    "createContinueConfig"
    "createVSCodiumSettings"
    "enforceCodexVscodeSettings"
    "ensureMutableRuntimeVscodeExtensions"
    "migrateClaudeVscodeSettings"
    "pruneHeavyExtensionGlobalState"
    "reconcileVscodeExtensionAliases"
    "resetContinueVscodeState"
    "seedClaudeSettings"
    "vscodeProfiles"
  ] ''
    obsolete="$HOME/.vscode-oss/extensions/.obsolete"
    if [ -f "$obsolete" ] && command -v python3 >/dev/null 2>&1; then
      python3 -c 'import json,pathlib,sys; p=pathlib.Path(sys.argv[1]); prefixes=("continue.","qwenlm.qwen-code-vscode-ide-companion-","openai.chatgpt-","anthropic.claude-code-"); data=json.loads(p.read_text(encoding="utf-8")); changed=False
if isinstance(data, dict):
    for key in list(data):
        if key.lower().startswith(prefixes):
            data.pop(key, None); changed=True
if changed:
    p.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")' "$obsolete" || true
    fi
    unset obsolete
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

  # ---- Continue.dev config — multi-model + harness --------------------------
  # Written on first activation or when __configVersion is outdated.
  # Not managed as a symlink so the user can edit it without HM clobbering
  # their changes on every switch. We still rewrite when the generated schema
  # changes or when the authoritative local chat lane/provider wiring drifts.
  home.activation.createContinueConfig = lib.hm.dag.entryAfter ["writeBoundary"] ''
        _config_version="34.0"
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
          if jq -e --arg api_base "${continueApiBase}" '
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
              (.tabAutocompleteModel.apiBase // "") == $api_base
              and ((.tabAutocompleteModel.requestOptions.headers["X-AI-Profile"] // "") == "continue-local")
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
      "__configVersion": "34.0",
      "__frozen": "DO NOT MODIFY. CLI bridge decommissioned (7dc4c950) — Claude/Codex bridge entries removed. contextLength/maxTokens for Local Agent tuned for v1.3.38. aq-hints removed — not supported in Continue v1.3.38.",
      "rules": [
        "You are AQ, an expert AI agent embedded in the NixOS-Dev-Quick-Deploy harness. You have full MCP tool access via the Harness MCP server.",
        "CONVERSATIONAL GUARD: For greetings, casual chat, or questions not about code or the harness, respond directly in plain text. Do NOT search the codebase, invoke MCP tools, or run any commands. Example: 'how are you today?' gets a plain text reply, no tool calls.",
        "HARNESS-FIRST: Before answering questions about files or services, use tools (read_file, run_terminal_command, grep_search) to search first. Never guess.",
        "CONTINUE MCP NAMING: In Continue, Harness MCP tools are exposed with an `mcp_server_` prefix. Use the exact surfaced names from the current client session, such as `mcp_server_get_working_memory`, `mcp_server_recall_memory`, `mcp_server_harness_health`, `mcp_server_get_hints`, `mcp_server_hybrid_search`, `mcp_server_query_aidb`, `mcp_server_workflow_plan`, `mcp_server_get_prsi_pending`, and `mcp_server_prsi_orchestrate`.",
        "TOOL DISCIPLINE: Use Continue MCP tools for harness ops: `mcp_server_harness_health`, `mcp_server_get_hints`, `mcp_server_hybrid_search`, `mcp_server_get_working_memory`, `mcp_server_recall_memory`, `mcp_server_store_memory`, `mcp_server_query_aidb`, `mcp_server_workflow_plan`, `mcp_server_get_prsi_pending`, `mcp_server_prsi_orchestrate`.",
        "WRAPPER-FIRST: Prefer Continue MCP tools and aq-* wrappers over raw curl or handwritten HTTP calls. If `mcp_server_get_working_memory`, `mcp_server_recall_memory`, `mcp_server_query_aidb`, `mcp_server_workflow_plan`, or `aq-memory` can answer the task, use them instead of direct endpoint probing.",
        "AGENT MODE: In agent mode, issue tool calls directly — do not announce them. Do not say 'I will now call...' just call the tool.",
        "SESSION START: Only call `mcp_server_get_working_memory` + `mcp_server_harness_health` when beginning a technical harness task. If `mcp_server_get_working_memory` is unavailable in the current session, fall back to `mcp_server_recall_memory` with a bounded continuation query. If `mcp_server_harness_health` is unavailable, run `aq-qa 0 --json` via terminal. For conversational messages, respond directly. You may call `aq-prime` for orientation via terminal.",
        "SEARCH-FIRST: Use `agrep` and `mcp_server_get_hints` for ranked workflow guidance before implementing anything.",
        "INTROSPECTION MODE: For questions about your operation, capabilities, limitations, memory, orchestration, or collaboration, start with `aq-operational-perspective --task \"<prompt>\" --format json` when terminal execution is available. Otherwise use aq-feedback-loop --task \"<prompt>\" --format json or aq-context-bootstrap --task \"<prompt>\" --format json; prefer aq-context-manage summary --task \"<prompt>\" --json and embedded-assist as compact search/context helpers, and if they select context-offload, execute sanctioned aq-* preflight_commands or continuation_startup_commands before answering. Full access to `aq-*`, `agrep`, `als`, `acat`, and `asum` is enabled.",
        "INTROSPECTION OUTPUT: Separate observed signals, inferred constraints, evidence sources, and unknowns. Do not present unverified behavior as fact.",
        "NO ls-FIRST: Never run ls on repo root as the first action. Use `als` or targeted grep/read.",
        "COMMIT DISCIPLINE: git add <files> && git commit -m 'type(scope): msg\\n\\nCo-Authored-By: <active-agent-name> <noreply@harness.local>' — replace <active-agent-name> with the model generating the work. Never hardcode a specific model version.",
        "CONTEXT LIMITS: For local models, keep messages short. Use summarize_context MCP tool if conversation grows long.",
        "LANE SELECTION: Use local-agent for bounded repo/runtime checks, health, monitoring, and background-safe harness work. Use continue-local for compact editor help. Use remote-free for lightweight synthesis, remote-reasoning for architecture/policy or larger-context judgment, remote-coding for implementation, and remote-tool-calling only for strict tool schemas.",
        "CONTEXT STRATEGY: Local lanes must aggressively offload to harness memory and compact often. Remote lanes may use their larger context windows when justified, but should still prefer retrieval-first handoffs over replaying long transcripts.",
        "RETRY BUDGET: After 2 failed retries, transport hangs, or repeated 'message exceeds context limit', stop replaying the same transcript. Checkpoint decisions and next steps to harness memory, then start a fresh session from `mcp_server_get_working_memory`, `mcp_server_recall_memory`, or aq-memory recall.",
        "TRANSCRIPT HYGIENE: Do not paste large logs, repo maps, or repeated bootstrap banners into editor chat when a compact summary or file reference will do.",
        "SHELL SAFETY: In zsh, always quote URLs containing ?, &, *, [, or ] before running shell commands. Never issue an unquoted AIDB or coordinator query URL.",
        "PORTS: llama:8080 embed:8081 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dash:8889 grafana:3000 owui:3001",
        "AGENT ROUTING — Monitoring, polling, and background tasks must use LOCAL models only. Never route autonomous/background work to remote/paid models.",
        "CANONICAL WORKFLOW — Full contract: .agent/WORKFLOW-CANON.md. Every non-trivial task follows: ORIENT(aq-prime+aq-hints+recall-memory) → RESEARCH(agrep/als/acat/asum codebase + web-search for external practices) → PRD/PLAN(.agent/ + .agents/plans/) → MEMORY-CHECKPOINT(store plan before executing) → EXECUTE(one slice at a time) → VALIDATE(tier0-gate + security-checklist) → COMMIT(atomic, Co-Authored-By).",
        "PRD GATE — Before implementing any multi-file change: write a .agent/PROJECT-<NAME>-PRD.md covering problem, goal, scope, constraints, acceptance criteria, and security requirements. Never start coding without a written plan.",
        "MEMORY DISCIPLINE — Before executing any slice: store the plan to harness memory (mcp_server_store_memory or aq-memory store). At session start: recall memory first (mcp_server_get_working_memory → mcp_server_recall_memory). Compact context before it exceeds 60% of the model window.",
        "SECURITY GATE — Apply before every commit: (1) no hardcoded secrets/ports/tokens; (2) verify all new imports/packages exist before adding them; (3) no injection patterns (SQL, shell, path traversal); (4) treat all LLM outputs as untrusted input; (5) if auth middleware added, verify it is wired in; (6) run bash -n on shell files and python3 -m py_compile on Python files.",
        "CONTEXT ENGINEERING — Reference files by path, do not paste full contents. Use mcp_server_hybrid_search and mcp_server_get_hints to retrieve exactly what the current slice needs. Pass only slice-relevant context to sub-agents. Never replay full transcripts."
      ],
      "models": [
        {
          "title": "Local Agent (Harness-Aware)",
          "provider": "openai",
          "apiKey": "local-llama-cpp",
          "apiBase": "${continueApiBase}",
          "model": "${aiLlamaModel}",
          "requestOptions": {
            "timeout": 300000,
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
          "title": "Antigravity Collective",
          "provider": "openai",
          "apiKey": "dummy",
          "apiBase": "${continueApiBase}",
          "model": "AUTODETECT",
          "requestOptions": {
            "headers": {
              "X-AI-Profile": "antigravity-collective"
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
        { "name": "file", "params": {} },
        { "name": "diff", "params": {} },
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
          "args": ["${repoPath}/scripts/ai/mcp-bridge-hybrid.py"],
          "env": {
            "HYBRID_URL": "http://127.0.0.1:8003",
            "AIDB_URL": "http://127.0.0.1:8002",
            "AIDB_API_KEY_FILE": "/run/secrets/aidb_api_key",
            "HYBRID_API_KEY_FILE": "/run/secrets/hybrid_coordinator_api_key"
          }
        },
        {
          "name": "OSINT Tools",
          "command": "python3",
          "args": ["${repoPath}/ai-stack/mcp-servers/osint-tools/server.py"],
          "env": {}
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
        mcp_config="$HOME/.mcp/config.json"

        write_harness_mcp_config() {
          cat > "$mcp_config" << 'MCP_EOF'
    {
      "mcpServers": {
         "hybrid-coordinator": {
           "command": "python3",
           "args": ["${repoPath}/scripts/ai/mcp-bridge-hybrid.py"],
           "env": {
             "HYBRID_URL": "http://127.0.0.1:${toString aiHybridPort}",
             "AIDB_URL": "http://127.0.0.1:${toString aiAidbPort}",
             "HYBRID_API_KEY_FILE": "/run/secrets/hybrid_coordinator_api_key",
             "AIDB_API_KEY_FILE": "/run/secrets/aidb_api_key"
           }
         },
         "osint-tools": {
           "command": "python3",
           "args": ["${repoPath}/ai-stack/mcp-servers/osint-tools/server.py"]
         },
         "github": {
           "command": "${repoPath}/scripts/ai/mcp-github-server",
           "args": []
         }
      }
    }
    MCP_EOF
        }

        needs_mcp_repair=0
        if [ ! -f "$mcp_config" ]; then
          needs_mcp_repair=1
         elif ! ${pkgs.jq}/bin/jq -e '.mcpServers["hybrid-coordinator"]' "$mcp_config" >/dev/null 2>&1; then
           needs_mcp_repair=1
         elif ! ${pkgs.jq}/bin/jq -e '.mcpServers["osint-tools"] and .mcpServers.github' "$mcp_config" >/dev/null 2>&1; then
           needs_mcp_repair=1
        elif ${pkgs.jq}/bin/jq -e '
          .mcpServers
          | to_entries
          | any(
              (.value.command // "") == "npx"
              or ((.value.command // "") == "nix" and ((.value.args // []) | index("github:utensils/mcp-nixos")))
              or (((.value.env // {}).GITHUB_PERSONAL_ACCESS_TOKEN // "") == "set-me")
            )
        ' "$mcp_config" >/dev/null 2>&1; then
          needs_mcp_repair=1
        fi

        if [ "$needs_mcp_repair" = "1" ]; then
          if [ -f "$mcp_config" ]; then
            cp "$mcp_config" "$HOME/.mcp/config.json.legacy.$(date -u +%Y%m%d%H%M%S)"
          fi
          write_harness_mcp_config
        fi
        unset needs_mcp_repair

        if [ ! -f "$HOME/.mcp/registry.json" ]; then
          cat > "$HOME/.mcp/registry.json" << 'MCP_REGISTRY_EOF'
    {
       "servers": [
         { "id": "hybrid-coordinator", "category": "harness", "description": "Local harness MCP bridge for coordinator, AIDB, memory, workflow, and QA tools" },
         { "id": "osint-tools", "category": "domain", "description": "Local OSINT MCP wrapper" },
         { "id": "github", "category": "research", "description": "Read-only GitHub MCP wrapper" }
       ]
    }
    MCP_REGISTRY_EOF
        fi

        mkdir -p "$HOME/.config/claude"
        ln -sfn "$HOME/.mcp/config.json" "$HOME/.config/claude/mcp.json"
         unset mcp_config
   '';

  # Project the admitted MCP set into each client's real user configuration.
  # The generic ~/.mcp catalog remains for clients that support it, while
  # Claude and Codex use their native configuration stores.
  home.activation.reconcileAgentMcpClients = lib.hm.dag.entryAfter ["createMcpConfig"] ''
    claude_cfg="$HOME/.claude.json"
    mkdir -p "$HOME/.codex"
    if [ ! -f "$claude_cfg" ]; then
      printf '{}\n' > "$claude_cfg"
    fi
    claude_tmp="$(mktemp)"
    ${pkgs.jq}/bin/jq \
      --arg repo "${repoPath}" \
      --arg hybrid_url "http://127.0.0.1:${toString aiHybridPort}" \
      --arg aidb_url "http://127.0.0.1:${toString aiAidbPort}" '
        .mcpServers = (.mcpServers // {})
        | .mcpServers["hybrid-coordinator"] = {
            type: "stdio",
            command: "python3",
            args: [($repo + "/scripts/ai/mcp-bridge-hybrid.py")],
            env: {
              HYBRID_URL: $hybrid_url,
              AIDB_URL: $aidb_url,
              HYBRID_API_KEY_FILE: "/run/secrets/hybrid_coordinator_api_key",
              AIDB_API_KEY_FILE: "/run/secrets/aidb_api_key"
            }
          }
        | .mcpServers["osint-tools"] = {
            type: "stdio",
            command: "python3",
            args: [($repo + "/ai-stack/mcp-servers/osint-tools/server.py")],
            env: {}
          }
        | .mcpServers.github = {
            type: "stdio",
            command: ($repo + "/scripts/ai/mcp-github-server"),
            args: [],
            env: {}
          }
      ' "$claude_cfg" > "$claude_tmp"
    chmod 600 "$claude_tmp"
    mv "$claude_tmp" "$claude_cfg"

    codex_cfg="$HOME/.codex/config.toml"
    touch "$codex_cfg"
    codex_tmp="$(mktemp)"
    ${pkgs.yq-go}/bin/yq -p toml -o toml '
      del(.features.codex_hooks)
      | .mcp_servers."hybrid-coordinator" = {
          "command": "python3",
          "args": ["${repoPath}/scripts/ai/mcp-bridge-hybrid.py"],
          "default_tools_approval_mode": "writes",
          "env": {
            "HYBRID_URL": "http://127.0.0.1:${toString aiHybridPort}",
            "AIDB_URL": "http://127.0.0.1:${toString aiAidbPort}",
            "HYBRID_API_KEY_FILE": "/run/secrets/hybrid_coordinator_api_key",
            "AIDB_API_KEY_FILE": "/run/secrets/aidb_api_key"
          }
        }
      | .mcp_servers."osint-tools" = {
          "command": "python3",
          "args": ["${repoPath}/ai-stack/mcp-servers/osint-tools/server.py"],
          "default_tools_approval_mode": "prompt"
        }
      | .mcp_servers.openaiDeveloperDocs = {
          "url": "https://developers.openai.com/mcp",
          "default_tools_approval_mode": "auto"
        }
    ' "$codex_cfg" > "$codex_tmp"
    chmod 600 "$codex_tmp"
    mv "$codex_tmp" "$codex_cfg"
    unset claude_cfg claude_tmp codex_cfg codex_tmp
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
      elif ${pkgs.jq}/bin/jq -e '
        .mcpServers
        | to_entries
        | any(
            (.value.command // "") == "npx"
            or ((.value.command // "") == "nix" and ((.value.args // []) | index("github:utensils/mcp-nixos")))
            or (((.value.env // {}).GITHUB_PERSONAL_ACCESS_TOKEN // "") == "set-me")
          )
      ' "$settings" > /dev/null 2>&1; then
        tmp="$(mktemp)"
        ${pkgs.jq}/bin/jq --slurpfile mcp "$mcp_cfg" \
          '.mcpServers = $mcp[0].mcpServers' "$settings" > "$tmp" \
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
