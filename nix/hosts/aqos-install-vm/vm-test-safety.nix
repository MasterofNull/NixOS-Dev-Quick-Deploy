{ config, lib, pkgs, ... }:
# ---------------------------------------------------------------------------
# extraSystemConfig for inputs.disko.lib.testLib.makeDiskoTest (see
# flake.nix checks.x86_64-linux.aqos-install-vm-disko-{plain,luks}).
#
# disko's OWN default settings for the "installed" test system
# (documentation off, forced console log level, the LUKS test-keyfile
# initrd secret, mkDefault systemd-boot — see the `installed-system` module
# in the disko flake's lib/tests.nix) only get wired in when makeDiskoTest
# builds its OWN `eval-config` call, which is sourced from DISKO's pinned
# nixpkgs (nixpkgs-unstable) — a different version than ours (nixos-26.05).
# We instead pass `extendModules` = our own already-built
# nixosConfiguration's `.extendModules` (see flake.nix) so the golden
# aqos-workstation profile evaluates against OUR pinned nixpkgs throughout,
# never nixpkgs-unstable. That means disko's `installed-system` module is
# skipped entirely, so this file carries the same settings over by hand
# (content copied verbatim from disko's lib/tests.nix `installed-system`).
#
# Test-only: never imported by a real host — only referenced from flake.nix
# checks.
# ---------------------------------------------------------------------------
{
  documentation.enable = lib.mkForce false;
  hardware.enableAllFirmware = lib.mkForce false;
  boot.consoleLogLevel = lib.mkForce 100;
  boot.loader.systemd-boot.enable = lib.mkDefault true;

  # LUKS test-only auto-unlock keyfile (matches disko-luks.nix's
  # settings.keyFile = "/tmp/secret.key"). Inert for the plain layout: no
  # LUKS device references this path, so it's simply never read.
  boot.initrd.secrets = lib.mkIf config.boot.initrd.systemd.enable {
    "/tmp/secret.key" = pkgs.writeText "secret.key" "secretsecret";
  };
  boot.initrd.preDeviceCommands = lib.mkIf (!config.boot.initrd.systemd.enable) ''
    echo -n 'secretsecret' > /tmp/secret.key
  '';
}
