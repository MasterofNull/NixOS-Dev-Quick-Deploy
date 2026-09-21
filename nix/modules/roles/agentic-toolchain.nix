{
  lib,
  config,
  pkgs,
  ...
}: let
  cfg = config.mySystem.roles.agenticToolchain;

  # ---------------------------------------------------------------------------
  # ST-1 (.agents/plans/factory-shared-toolchain/DESIGN.md) — the shared
  # agentic dev toolchain SSOT. Pinned to this flake's nixpkgs (flake.lock);
  # reference-shared via the Nix store (one path, N projects, no vendoring).
  #
  # BASELINE — tools the agentic dev team needs on every project regardless
  # of domain. Seeded conservatively from the owner-reported gap (2026-09-19):
  # deployed projects (e.g. native-plant) lack Playwright/browser-testing
  # tooling — `playwright install` fails offline and NixOS can't run the
  # dynamically-linked, non-Nix browser binaries it tries to download.
  #
  # Deliberately NOT duplicated here (already system-wide — see SSOTs below,
  # checked before writing this list):
  #   - jq, ripgrep, git, curl  -> nix/modules/core/base.nix basePackageNames
  #     (unconditional, every profile)
  #   - fd                      -> nix/data/profile-system-packages.nix
  #     ai-dev profile list (already on PATH for the ai-dev profile)
  #   - nodejs, go, rustc, cargo, ruby, neovim -> base.nix basePackageNames
  # ---------------------------------------------------------------------------
  baselinePackages = with pkgs; [
    # Playwright driver + pre-fetched browser binaries (Chromium/Firefox/
    # WebKit). Mirrors the already-working flake.nix devShells.mobile-web /
    # devShells.qa-auto convention and nix/home/base.nix's
    # PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD pattern, but exposes it via
    # environment.systemPackages so ANY agent shell on the host reaches it —
    # not only this repo's own home-manager user session. A project's own
    # playwright npm/pip package still ships with the project; only the heavy
    # browser binaries are shared.
    playwright-driver
  ];

  # OPT-IN — heavier/specialized sets a project selects explicitly via
  # mySystem.roles.agenticToolchain.profiles. Never force-installed. Add new
  # profiles through the governed contribute-back flow (ST-4:
  # capability-intake + flake-review), not ad hoc.
  toolchainProfiles = {
    # Rust dev tooling beyond the bare compiler (cargo/rustc are already
    # system-wide via base.nix basePackageNames — not repeated here):
    # linting, formatting, LSP. Mirrors flake.nix devShells.rust minus the
    # already-system-wide duplicates.
    rust = with pkgs; [
      clippy
      rustfmt
      rust-analyzer
    ];
  };

  knownProfileNames = builtins.attrNames toolchainProfiles;

  selectedProfilePackages =
    lib.concatMap (name: toolchainProfiles.${name}) cfg.profiles;
in {
  # ---------------------------------------------------------------------------
  # Shared Agentic Dev Toolchain (ST-1)
  #
  # DEFAULT OFF. Activated when: mySystem.roles.agenticToolchain.enable = true
  #
  # When enabled (owner sets the flag + reruns nixos-rebuild), the baseline
  # toolchain lands on every agent shell's PATH via environment.systemPackages
  # — no per-project vendoring, no restart beyond the one rebuild. Until the
  # owner flips this flag, this module changes nothing about the running
  # system: no packages added, no env vars set, no PATH changes.
  #
  # See .agents/plans/factory-shared-toolchain/DESIGN.md for the two-speed
  # model this module implements the "durable / pinned / fleet-wide" half of
  # — live/on-demand tool reach (aq-tool, ST-2) is a separately implemented
  # runtime path, not part of this default-off module.
  # ---------------------------------------------------------------------------
  options.mySystem.roles.agenticToolchain = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        DEFAULT OFF. When true, adds the baseline shared agentic dev toolchain
        (currently: Playwright driver + pre-fetched browsers) to every agent
        shell's PATH via environment.systemPackages, pinned to this flake's
        nixpkgs (flake.lock) and reference-shared via the Nix store — never
        vendored per project.

        Enabling this requires the owner to set this to true and run
        `nixos-rebuild switch` (or `build` to preview) — it is inert until
        then. See .agents/plans/factory-shared-toolchain/DESIGN.md (ST-1).
      '';
    };

    profiles = lib.mkOption {
      type = lib.types.listOf (lib.types.enum knownProfileNames);
      default = [];
      description = ''
        Opt-in, named toolchain profiles layered on top of the baseline when
        mySystem.roles.agenticToolchain.enable = true. Never force-installed —
        a project selects only what it needs. Ignored entirely when enable =
        false. Available profiles: ${toString knownProfileNames}.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = baselinePackages ++ selectedProfilePackages;

    environment.sessionVariables = {
      # Same convention as nix/home/base.nix: point any project's own
      # Playwright bindings at the Nix-store browsers instead of letting them
      # try (and fail, on NixOS) to download their own.
      PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
      PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = "1";
    };
  };
}
