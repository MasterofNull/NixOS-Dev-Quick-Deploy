# Network Configuration with DNS Fix
# NixOS 26.05 Yarara
# Purpose: Proper DNS resolution configuration to prevent hostname resolution errors
#
# Features:
# - systemd-resolved with proper /etc/resolv.conf symlink
# - Fallback DNS servers (Cloudflare, Google)
# - NetworkManager integration with systemd-resolved
# - Fixes "Could not resolve host" warnings during nix operations
#
# Usage: Import this file in your configuration.nix:
#   imports = [ ./nixos-improvements/networking.nix ];

{ config, pkgs, lib, ... }:

{
  # Enable systemd-resolved for DNS resolution
  services.resolved = {
    enable = true;
    # Use systemd-resolved's stub resolver
    dnssec = "allow-downgrade";
    # Enable DNS over TLS (opportunistic)
    dnsovertls = "opportunistic";
    # Fallback DNS servers (used when DHCP doesn't provide DNS)
    fallbackDns = [
      "1.1.1.1"        # Cloudflare primary
      "1.0.0.1"        # Cloudflare secondary
      "8.8.8.8"        # Google primary
      "8.8.4.4"        # Google secondary
      "9.9.9.9"        # Quad9 primary
      "149.112.112.112" # Quad9 secondary
    ];
    # Enable LLMNR (Link-Local Multicast Name Resolution)
    llmnr = "true";
    # Disable mDNS in systemd-resolved (Avahi handles mDNS)
    extraConfig = ''
      MulticastDNS=no
      Cache=yes
      DNSStubListener=yes
    '';
  };

  # Ensure /etc/resolv.conf is properly managed by systemd-resolved
  # This prevents "Could not resolve host" errors
  environment.etc."resolv.conf".source = lib.mkForce "/run/systemd/resolve/stub-resolv.conf";

  # Configure NetworkManager to use systemd-resolved for DNS
  networking.networkmanager = {
    dns = "systemd-resolved";
    # Tell NetworkManager to manage /etc/resolv.conf via systemd-resolved
    # This ensures the symlink is maintained
    settings.main."rc-manager" = "symlink";
  };

  # Add fallback nameservers (these get added to systemd-resolved config)
  networking.nameservers = lib.mkDefault [
    "1.1.1.1"
    "8.8.8.8"
  ];

  # Enable IPv6 privacy extensions
  networking.tempAddresses = "default";

  # Ensure /etc/resolv.conf symlink is created at boot
  # This is a safety fallback in case NetworkManager hasn't created it yet
  systemd.tmpfiles.rules = [
    "L+ /etc/resolv.conf - - - - /run/systemd/resolve/stub-resolv.conf"
  ];
}
