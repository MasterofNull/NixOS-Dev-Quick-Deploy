# Test-only disko device tree for inputs.disko.lib.testLib.makeDiskoTest
# (see flake.nix checks.x86_64-linux.aqos-install-vm-disko-luks and
# scripts/testing/aqos-install-vm-dogfood.sh).
#
# Mirrors the PRODUCTION LUKS layout at nix/modules/disk/gpt-luks-ext4.nix
# (ESP + LUKS -> ext4 root), with ONE deliberate difference: the production
# layout leaves LUKS interactive (`askPassword`, a real install prompts a
# human for a real passphrase at the terminal) — that is correct behavior
# on real hardware and matches "disk encryption is the user's choice at
# install, per OS best practice" (see the plan doc header). This TEST
# fixture instead sets `settings.keyFile = "/tmp/secret.key"`: a FIXED,
# NON-SECRET, TEST-ONLY key file that disko's own test framework
# (nix-community/disko lib/tests.nix `makeDiskoTest`) pre-seeds with the
# literal string "secretsecret" on both the installer machine and — via
# nix/hosts/aqos-install-vm/vm-test-safety.nix's `boot.initrd.secrets` —
# the installed system's initrd, purely so `nix build` (rootless, no tty)
# can drive `cryptsetup luksFormat`/`luksOpen` non-interactively end to end.
#
# NEVER reuse this keyfile/path/value outside this disposable VM test — the
# production layout (gpt-luks-ext4.nix) never sets a keyFile/passwordFile,
# so a real install always prompts interactively for a real passphrase.
{
  disko.devices.disk.main = {
    type = "disk";
    device = "/dev/vda"; # overwritten by disko's testLib.prepareDiskoConfig
    content = {
      type = "gpt";
      partitions = {
        ESP = {
          size = "512M";
          type = "EF00";
          content = {
            type = "filesystem";
            format = "vfat";
            mountpoint = "/boot";
            mountOptions = [ "umask=0077" ];
          };
        };
        cryptroot = {
          size = "100%";
          content = {
            type = "luks";
            name = "cryptroot";
            settings = {
              # TEST-ONLY fixed key file — see file header. Never a real secret.
              keyFile = "/tmp/secret.key";
              allowDiscards = true;
            };
            content = {
              type = "filesystem";
              format = "ext4";
              mountpoint = "/";
            };
          };
        };
      };
    };
  };
}
