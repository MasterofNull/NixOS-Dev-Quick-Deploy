{
  lib,
  pkgs,
  config,
  ...
}:
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
  options.mySystem.networkPolicyObservability = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable passive network policy observation and status projection.";
    };
    mode = lib.mkOption {
      type = lib.types.enum [ "legacy" "policy" ];
      default = "legacy";
      description = "Network policy operational mode (legacy default, policy selectable in N3).";
    };
  };

  config = {
    # systemd-resolved: stub DNS resolver with fallback servers.
    services.resolved = {
      enable = lib.mkDefault true;
      # 26.05: dnssec/dnsovertls/fallbackDns/extraConfig were removed/renamed — all
      # [Resolve] section keys now live under structured settings.Resolve.
      settings.Resolve = {
        DNSSEC = lib.mkDefault "allow-downgrade";
        # Many consumer/campus resolvers advertise partial DoT support that causes
        # repeated downgrade churn; prefer stable plaintext DNS on local links.
        DNSOverTLS = lib.mkDefault "false";
        # Fallback DNS used when DHCP provides none or a broken nameserver.
        FallbackDNS = lib.mkDefault "1.1.1.1 1.0.0.1 8.8.8.8 8.8.4.4 9.9.9.9 149.112.112.112";
        MulticastDNS = lib.mkDefault "no";
        LLMNR = lib.mkDefault "no";
        Cache = lib.mkDefault "yes";
        DNSStubListener = lib.mkDefault "yes";
      };
    };

    # Route NetworkManager DNS through systemd-resolved.
    networking.networkmanager.dns = lib.mkDefault "systemd-resolved";
    # Reduce Realtek roaming/power-save related disconnects on unstable APs.
    networking.networkmanager.wifi.powersave = lib.mkDefault false;
    networking.firewall.enable = lib.mkDefault true;

    # Belt-and-suspenders: add reliable public DNS as global resolved.conf servers.
    # These are tried when per-link DNS fails completely (timeout/SERVFAIL).
    networking.nameservers = lib.mkDefault [
      "1.1.1.1"
      "1.0.0.1"
      "8.8.8.8"
      "8.8.4.4"
    ];

    # Override DHCP-provided DNS on wifi after NM pushes it to systemd-resolved.
    #
    # WHY: systemd-resolved's fallbackDns only fires on timeout/SERVFAIL, NOT on
    # NXDOMAIN. A router that answers queries but returns wrong results for external
    # hosts (NXDOMAIN for cache.nixos.org etc.) trips nix builds and API connections
    # even though fallbackDns is configured. Running after NM's DNS push guarantees
    # 1.1.1.1 handles all wifi queries.
    networking.networkmanager.dispatcherScripts = [
      {
        source = pkgs.writeScript "10-wifi-reliable-dns" ''
          #!/bin/sh
          IFACE=$1
          ACTION=$2
          case "$ACTION" in
            up|dhcp4-change)
              if [ -d "/sys/class/net/$IFACE/wireless" ]; then
                if [ "${config.mySystem.networkPolicyObservability.mode}" = "policy" ] && [ -x /run/current-system/sw/bin/aq-network-policy ]; then
                  /run/current-system/sw/bin/aq-network-policy execute "$IFACE" "$ACTION" --mode policy >/dev/null 2>&1 || true
                else
                  /run/current-system/sw/bin/resolvectl dns "$IFACE" \
                    1.1.1.1 1.0.0.1 8.8.8.8 8.8.4.4
                  /run/current-system/sw/bin/resolvectl domain "$IFACE" "~."
                fi
              fi
              ;;
          esac
        '';
        type = "basic";
      }
    ] ++ (lib.optional config.mySystem.networkPolicyObservability.enable {
      source = pkgs.writeScript "20-aq-network-policy-observe" ''
        #!/bin/sh
        IFACE=$1
        ACTION=$2
        case "$ACTION" in
          up|dhcp4-change|down|connectivity-change)
            if [ -x /run/current-system/sw/bin/aq-network-policy ]; then
              /run/current-system/sw/bin/aq-network-policy observe "$IFACE" >/dev/null 2>&1 || true
            fi
            ;;
        esac
      '';
      type = "basic";
    });

    # Captive portal + internet connectivity detection.
    # NM checks this URI periodically; a 204 response means CONNECTIVITY_FULL,
    # a redirect means CONNECTIVITY_PORTAL (captive portal), no response means
    # CONNECTIVITY_LIMITED (network but no internet — WiFi icon shows warning).
    # detectportal.firefox.com returns HTTP 204 reliably from Mozilla's CDN.
    # 30s interval gives <30s lag when internet is lost/restored.
    networking.networkmanager.settings.connectivity = {
      uri = lib.mkDefault "http://detectportal.firefox.com/success.txt";
      interval = lib.mkDefault 30;
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

    # Safety: ensure the symlink exists even before NM has run, and declare N2 private dirs and locks.
    systemd.tmpfiles.rules = lib.mkAfter [
      "L+ /etc/resolv.conf - - - - /run/systemd/resolve/stub-resolv.conf"
      "d /var/lib/aq-network-policy 0755 root root - -"
      "d /var/lib/aq-network-policy/private 0700 root root - -"
      "d /run/aq-network-policy 0755 root root - -"
      "d /run/aq-network-policy/private 0700 root root - -"
      "d /run/lock/aq-network-policy 0755 root root - -"
      "f /run/lock/aq-network-policy/effect-operation.lock 0600 root root - -"
      "f /run/lock/aq-network-policy/trusted-profiles.lock 0600 root root - -"
      "f /run/lock/aq-network-policy/override-lease.lock 0600 root root - -"
      "f /run/lock/aq-network-policy/health.lock 0600 root root - -"
    ];

    # Independent watchdog service and timer for policy-mode lease expiry
    systemd.services.aq-network-policy-watchdog = lib.mkIf (config.mySystem.networkPolicyObservability.enable && config.mySystem.networkPolicyObservability.mode == "policy") {
      description = "AQ Network Policy Watchdog and Expiry Revert";
      after = [ "network.target" ];
      onFailure = [ "aq-network-policy-emergency-revert.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "/run/current-system/sw/bin/aq-network-policy watchdog --mode policy";
        TimeoutStartSec = "15s";
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        ReadWritePaths = [
          "/run/aq-network-policy"
          "/run/lock/aq-network-policy"
          "/var/lib/aq-network-policy"
        ];
      };
    };

    systemd.timers.aq-network-policy-watchdog = lib.mkIf (config.mySystem.networkPolicyObservability.enable && config.mySystem.networkPolicyObservability.mode == "policy") {
      description = "AQ Network Policy Watchdog Timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "5s";
        OnUnitActiveSec = "10s";
        RandomizedDelaySec = "1s";
      };
    };

    systemd.services.aq-network-policy-emergency-revert = lib.mkIf (config.mySystem.networkPolicyObservability.enable && config.mySystem.networkPolicyObservability.mode == "policy") {
      description = "AQ Network Policy Emergency Revert Fallback";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "/run/current-system/sw/bin/aq-network-policy emergency-revert";
        TimeoutStartSec = "10s";
      };
    };
  };
}
