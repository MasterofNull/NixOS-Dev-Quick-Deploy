{ lib, config, ... }:
# ---------------------------------------------------------------------------
# aqos-install-vm — disposable disk/install-MECHANICS harness host for the
# golden aqos-workstation profile (slice s1a,
# .agents/plans/aqos-installer-experience/END-TO-END-BARE-METAL-PLAN.md).
#
# Unlike nix/hosts/aqos-vm (which only proves BOOT, via
# `nixos-rebuild build-vm`'s self-synthesized disk — it never partitions
# anything), this host is the PAYLOAD for
# inputs.disko.lib.testLib.makeDiskoTest (see flake.nix
# checks.x86_64-linux.aqos-install-vm-disko-{plain,luks} and
# scripts/testing/aqos-install-vm-dogfood.sh): it is extended
# (`.extendModules`, wired in flake.nix) by disko's rootless in-VM test
# framework, which partitions/formats a REAL virtual disk inside qemu,
# nixos-enters + installs this exact closure, then reboots into it from the
# freshly-written disk — proving disk+install MECHANICS, not just boot.
#
# Golden profile imported unmodified (via facts.nix -> mySystem.profile =
# "aqos-workstation", forced in flake.nix); only VM-safe overrides below,
# modeled on nix/hosts/aqos-vm/default.nix.
# ---------------------------------------------------------------------------
{
  imports = [ ./facts.nix ];

  # Same deliberate, documented exception as aqos-vm/default.nix (see
  # nix/modules/core/users.nix's "never set initialPassword" policy):
  # throwaway VM, no prior /etc/shadow to preserve, and the harness needs to
  # be able to prove a console login after a real disko install.
  users.users.${config.mySystem.primaryUser}.initialPassword = "aqosvm";

  # No real network/hardware to reach — keep the VM guest quiet and fast.
  # mkForce (not mkDefault): nix/modules/core/network.nix already sets this
  # with mkDefault true, and two mkDefault definitions at the same priority
  # conflict rather than one silently winning.
  networking.firewall.enable = lib.mkForce false;

  # Boot marker for the post-install, rebooted VM (checked via
  # `machine.wait_for_unit` + journalctl in flake.nix's makeDiskoTest
  # `bootCommands` — the disko test framework gives us a Python test-driver
  # `machine` object with real systemctl/journalctl access, unlike
  # aqos-vm-dogfood.sh's headless `-nographic` qemu which has to scrape
  # /dev/console instead). RemainAfterExit so a one-shot's success is
  # observable via wait_for_unit after it has already run.
  systemd.services.aqos-install-vm-dogfood-marker = {
    description = "AQOS install-VM dogfood boot marker (scripts/testing/aqos-install-vm-dogfood.sh)";
    wantedBy = [ "multi-user.target" ];
    after = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      # systemd services get a minimal PATH that excludes /run/current-system/sw/bin
      # (where systemPackages install), so check the system-profile path directly —
      # that is exactly where the golden aqos-workstation profile puts hyperfine.
      if [ -x /run/current-system/sw/bin/hyperfine ]; then
        echo "AQOS-INSTALL-VM-DOGFOOD-BOOT-OK golden_marker=hyperfine-ok"
      else
        echo "AQOS-INSTALL-VM-DOGFOOD-BOOT-OK golden_marker=MISSING"
      fi
    '';
  };
}
