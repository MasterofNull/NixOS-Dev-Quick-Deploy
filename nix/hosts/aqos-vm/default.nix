{ lib, config, ... }:
# ---------------------------------------------------------------------------
# aqos-vm — disposable dogfood host for the golden aqos-workstation profile.
#
# Built ONLY via `nixos-rebuild build-vm --flake .#aqos-vm` (see
# scripts/testing/aqos-vm-dogfood.sh). Never deployed to real hardware, never
# switched with sudo. VM-safe overrides only; all golden-profile behavior
# (roles/packages/hardening) is inherited unmodified from
# nix/modules/profiles/aqos-workstation.nix — nothing is duplicated here.
# ---------------------------------------------------------------------------
{
  imports =
    lib.optionals (builtins.pathExists ./facts.nix) [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # Deliberate, documented exception to the "never set initialPassword" policy
  # in nix/modules/core/users.nix: this is a throwaway VM with no prior
  # /etc/shadow to preserve, and the dogfood harness needs to be able to log
  # in (console/serial) to assert the booted system is coherent.
  users.users.${config.mySystem.primaryUser}.initialPassword = "aqosvm";

  # No real network/hardware to reach — keep the VM guest quiet and fast.
  # mkForce (not mkDefault): nix/modules/core/network.nix already sets this
  # with mkDefault true, and two mkDefault definitions at the same priority
  # conflict rather than one silently winning.
  networking.firewall.enable = lib.mkForce false;

  # Step B (scripts/testing/aqos-vm-dogfood.sh --full) boots this VM headless
  # (-nographic) with no way to script a login over the serial console. This
  # oneshot prints a single, greppable line to /dev/console once multi-user
  # boot is reached, proving (a) the golden profile actually boots and (b) a
  # golden-profile package (hyperfine) is really installed and on PATH — not
  # just present in the evaluated config (which Step A already checks).
  systemd.services.aqos-vm-dogfood-marker = {
    description = "AQOS VM dogfood boot marker (scripts/testing/aqos-vm-dogfood.sh)";
    wantedBy = [ "multi-user.target" ];
    after = [ "multi-user.target" ];
    serviceConfig.Type = "oneshot";
    script = ''
      marker="MISSING"
      if command -v hyperfine >/dev/null 2>&1; then marker="hyperfine-ok"; fi
      echo "AQOS-VM-DOGFOOD-BOOT-OK golden_marker=$marker" > /dev/console 2>/dev/null || true
    '';
  };
}
