{ lib, config, ... }:
# ---------------------------------------------------------------------------
# Core network module — DNS resolution, resolved, NetworkManager integration.
#
# Migrated from templates/nixos-improvements/networking.nix.
# Applied unconditionally to all hosts (minimal footprint, no optional deps).
#
# Fixes:
#   - "Could not resolve host" during nix builds when DHCP doesn't supply DNS
#   - /etc/resolv.conf pointing at wrong location after NetworkManager init
# ---------------------------------------------------------------------------
{
  # systemd-resolved: stub DNS resolver with fallback servers.
  services.resolved = {
    enable     = lib.mkDefault true;
    dnssec     = lib.mkDefault "allow-downgrade";
    # Many consumer/campus resolvers advertise partial DoT support that causes
    # repeated downgrade churn; prefer stable plaintext DNS on local links.
    dnsovertls = lib.mkDefault "false";
    # Fallback DNS used when DHCP provides none or a broken nameserver.
    fallbackDns = lib.mkDefault [
      "1.1.1.1"          # Cloudflare
      "1.0.0.1"
      "8.8.8.8"          # Google
      "8.8.4.4"
      "9.9.9.9"          # Quad9 (privacy-preserving)
      "149.112.112.112"
    ];
    extraConfig = lib.mkDefault ''
      MulticastDNS=no
      Cache=yes
      DNSStubListener=yes
    '';
  };

  # Route NetworkManager DNS through systemd-resolved.
  networking.networkmanager.dns = lib.mkDefault "systemd-resolved";
  # Reduce Realtek roaming/power-save related disconnects on unstable APs.
  networking.networkmanager.wifi.powersave = lib.mkDefault false;
  networking.firewall.enable = lib.mkDefault true;

  # Captive portal detection — without a check URI, NM reports any network
  # as "full" even when a login page is required (hotel, airport, conference).
  # With this set NM reports "portal" connectivity and the desktop environment
  # (COSMIC/GNOME) shows a captive-portal notification so the user can log in.
  networking.networkmanager.settings.connectivity = {
    uri      = lib.mkDefault "http://nmcheck.gnome.org/check_network_status.txt";
    interval = lib.mkDefault 300;
  };

  # Ensure the stub-resolv.conf symlink is always present.
  # systemd-resolved manages /run/systemd/resolve/stub-resolv.conf; pointing
  # /etc/resolv.conf here prevents the race condition where NM writes a bare
  # file that omits the resolved stub address.
  environment.etc."resolv.conf".source =
    lib.mkDefault "/run/systemd/resolve/stub-resolv.conf";

  # IPv6 privacy extensions: use temporary addresses for outbound connections.
  networking.tempAddresses = lib.mkDefault "default";
  networking.firewall.logRefusedConnections = lib.mkDefault true;

  # Safety: ensure the symlink exists even before NM has run.
  systemd.tmpfiles.rules = lib.mkAfter [
    "L+ /etc/resolv.conf - - - - /run/systemd/resolve/stub-resolv.conf"
  ];
}
