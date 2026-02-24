{
  # Profile package names only. Core packages are declared in
  # nix/modules/core/base.nix, and final package selection is deduplicated.
  # VSCodium is managed via Home Manager (nix/home/base.nix -> programs.vscode),
  # so it must not be duplicated in system package profiles.
  ai-dev = [
    "nodejs"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
    "sqlite"
    "wireshark"
    "tcpdump"
    "nmap"
    "mtr"
    "traceroute"
    "sops"
    "age"
    "btrfs-progs"
    "pciutils"
    # NOTE: gpt4all is intentionally excluded from systemPackageNames because
    # recent nixpkgs revisions can evaluate but fail to build it (Qt6 private
    # target mismatch), which breaks full system deploys.
    # Declarative GPT4All install is provided via Flatpak profile data
    # (see nix/data/flatpak-profiles.nix: io.gpt4all.gpt4all).

    # ── Phase 29: MLOps lifecycle tooling (ai-dev profile only) ──────────────
    # dvc: data/model artifact versioning.
    "dvc"
    # httpie: human-friendly HTTP client for local API testing.
    "httpie"
  ];

  gaming = [
    "nodejs"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
    "sqlite"
    "btrfs-progs"
    "pciutils"
    "mangohud"
    "gamemode"
  ];

  minimal = [
    "nodejs"
    "go"
    "cargo"
    "ruby"
    "neovim"
    "python3"
  ];
}
