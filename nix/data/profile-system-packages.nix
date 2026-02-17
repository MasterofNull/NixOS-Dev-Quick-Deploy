{
  # Profile package names only. Core packages are declared in
  # nix/modules/core/base.nix, and final package selection is deduplicated.
  ai-dev = [
    "chromium"
    "firefox"
    "goose-cli"
    "python3"
    "sqlite"
    "podman"
  ];

  gaming = [
    "chromium"
    "firefox"
    "goose-cli"
    "mangohud"
    "gamemode"
  ];

  minimal = [
    "firefox"
  ];
}
