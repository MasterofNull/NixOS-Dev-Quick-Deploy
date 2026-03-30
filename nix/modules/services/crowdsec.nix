{ lib, config, pkgs, ... }:
let
  cfg = config.mySystem;
  cs = cfg.security.crowdsec;
in
{
  # ---------------------------------------------------------------------------
  # Crowdsec IPS: behavior-based intrusion prevention system.
  # Watches logs for malicious patterns, shares threat intel, and blocks IPs.
  # Available in NixOS 24.05+.
  # ---------------------------------------------------------------------------

  options.mySystem.security.crowdsec = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable Crowdsec intrusion prevention system.";
    };

    enableFirewallBouncer = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable Crowdsec firewall bouncer to auto-ban IPs via nftables.";
    };

    watchNginx = lib.mkOption {
      type = lib.types.bool;
      default = config.services.nginx.enable;
      description = "Watch Nginx access logs for malicious requests.";
    };

    watchSshd = lib.mkOption {
      type = lib.types.bool;
      default = config.services.openssh.enable;
      description = "Watch SSH auth logs for brute-force attempts.";
    };

    apiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Path to file containing Crowdsec bouncer API key (sops secret).";
    };
  };

  config = lib.mkIf cs.enable {
    assertions = [
      {
        assertion = cs.enableFirewallBouncer -> cs.apiKeyFile != null;
        message = "mySystem.security.crowdsec.enableFirewallBouncer requires apiKeyFile.";
      }
    ];

    services.crowdsec = {
      enable = true;
      # Use a distinct watcher identity so we don't collide with the stale
      # partially-created "hyperd" machine left behind by earlier failed boots.
      name = "${cfg.hostName}-watcher";

      # Local API server for bouncers to connect to
      settings = {
        # Upstream startup writes local watcher credentials here via
        # `cscli machines add --auto`. Keep it under the writable state dir.
        lapi.credentialsFile = "/var/lib/crowdsec/state/local_api_credentials.yaml";
        general.api.server = {
          enable = true;
          listen_uri = "127.0.0.1:8088";
        };
      };

      # Acquisitions: which log sources to monitor
      localConfig.acquisitions = lib.optionals cs.watchSshd [
        {
          source = "journalctl";
          journalctl_filter = [ "_SYSTEMD_UNIT=sshd.service" ];
          labels.type = "syslog";
        }
      ] ++ lib.optionals cs.watchNginx [
        {
          source = "file";
          filenames = [ "/var/log/nginx/access.log" ];
          labels.type = "nginx";
        }
        {
          source = "file";
          filenames = [ "/var/log/nginx/error.log" ];
          labels.type = "nginx";
        }
      ];
    };

    # Firewall bouncer: block malicious IPs at the firewall level
    # Only enabled when both enableFirewallBouncer=true AND apiKeyFile is set
    services.crowdsec-firewall-bouncer = lib.mkIf (cs.enableFirewallBouncer && cs.apiKeyFile != null) {
      enable = true;
      # When a secret-backed API key file is provided, disable auto-registration
      # and force the runtime file path so the upstream placeholder doesn't
      # collide with our module value during option merging.
      registerBouncer.enable = lib.mkForce false;
      secrets.apiKeyPath = lib.mkForce cs.apiKeyFile;
      settings = {
        api_url = "http://${config.services.crowdsec.settings.general.api.server.listen_uri}";
        mode = "nftables";
        nftables = {
          ipv4.table = "crowdsec";
          ipv4.chain = "crowdsec-chain";
          ipv6.table = "crowdsec6";
          ipv6.chain = "crowdsec6-chain";
        };
      };
    };

    # Systemd hardening for crowdsec services
    systemd.tmpfiles.rules = [
      "d /var/log/crowdsec 0750 crowdsec crowdsec -"
    ];

    systemd.services.crowdsec = {
      serviceConfig = {
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        NoNewPrivileges = true;
        ReadWritePaths = [ "/var/lib/crowdsec" "/var/log/crowdsec" ];
      };
    };

    # When the bouncer API key comes from a secret provider, CrowdSec still
    # needs that key registered in its local database. Reconcile the local
    # bouncer record to the runtime secret before the bouncer starts so deploys
    # do not fail with "API error: access forbidden".
    systemd.services.crowdsec-firewall-bouncer-key-sync = lib.mkIf (cs.enableFirewallBouncer && cs.apiKeyFile != null) {
      description = "Sync CrowdSec firewall bouncer API key from secret";
      wantedBy = [ "multi-user.target" ];
      after = [ "crowdsec.service" ];
      wants = [ "crowdsec.service" ];
      before = [ "crowdsec-firewall-bouncer.service" ];
      serviceConfig = {
        Type = "oneshot";
        User = config.services.crowdsec.user;
        Group = config.services.crowdsec.group;
        LoadCredential = [ "API_KEY_FILE:${toString cs.apiKeyFile}" ];
        StateDirectory = "crowdsec-firewall-bouncer-key-sync";
        ReadWritePaths = [ "/var/lib/crowdsec" ];
        DynamicUser = true;
        LockPersonality = true;
        PrivateDevices = true;
        ProcSubset = "pid";
        ProtectClock = true;
        ProtectControlGroups = true;
        ProtectHome = true;
        ProtectHostname = true;
        ProtectKernelLogs = true;
        ProtectKernelModules = true;
        ProtectKernelTunables = true;
        ProtectProc = "invisible";
        RestrictNamespaces = true;
        RestrictRealtime = true;
        RestrictAddressFamilies = [ "AF_UNIX" ];
        CapabilityBoundingSet = [ "" ];
        SystemCallArchitectures = "native";
        SystemCallFilter = [
          "@system-service"
          "~@privileged"
          "~@resources"
        ];
        UMask = "0077";
      };
      script = let
        bouncerName = config.services.crowdsec-firewall-bouncer.registerBouncer.bouncerName;
        crowdsecConfigFile = (pkgs.formats.yaml { }).generate "crowdsec-sync.yaml" config.services.crowdsec.settings.general;
        cscliBin = lib.getExe' config.services.crowdsec.package "cscli";
      in ''
        set -euo pipefail

        export PATH="${lib.makeBinPath [ config.services.crowdsec.package ]}:$PATH"
        cscli=${lib.escapeShellArg cscliBin}
        crowdsec_config=${lib.escapeShellArg crowdsecConfigFile}
        api_key="$(<"$CREDENTIALS_DIRECTORY/API_KEY_FILE")"

        if "$cscli" -c "$crowdsec_config" bouncers list --output json | ${lib.getExe pkgs.jq} -e -- ${lib.escapeShellArg "any(.[]; .name == \"${bouncerName}\")"} >/dev/null; then
          "$cscli" -c "$crowdsec_config" bouncers delete -- ${lib.escapeShellArg bouncerName}
        fi

        "$cscli" -c "$crowdsec_config" bouncers add --key "$api_key" -- ${lib.escapeShellArg bouncerName} >/dev/null
      '';
    };

    systemd.services.crowdsec-firewall-bouncer = lib.mkIf (cs.enableFirewallBouncer && cs.apiKeyFile != null) {
      after = [ "crowdsec-firewall-bouncer-key-sync.service" ];
      wants = [ "crowdsec-firewall-bouncer-key-sync.service" ];
      requires = [ "crowdsec-firewall-bouncer-key-sync.service" ];
    };

    # Open firewall for local API only (bouncer communication)
    networking.firewall.interfaces."lo".allowedTCPPorts = [ 8088 ];

    # Install crowdsec CLI for management
    environment.systemPackages = [ pkgs.crowdsec ];
  };
}
