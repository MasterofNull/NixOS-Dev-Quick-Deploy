{ lib, config, ... }:
let
  cfg = config.mySystem;
  mon = cfg.monitoring;
  cc = mon.commandCenter;
  ing = cfg.ingress;

  backendApi = "http://127.0.0.1:${toString cc.apiPort}";
  backendUi = "http://127.0.0.1:${toString cc.frontendPort}";
in
{
  options.mySystem.ingress = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable host Nginx TLS ingress for dashboard and API.";
    };

    domain = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Public DNS hostname for ingress virtual host.";
    };

    useAcme = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Use ACME/LetsEncrypt to provision TLS certificates.";
    };

    acmeEmail = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Contact email for ACME registration.";
    };

    tlsCertPath = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Path to static TLS certificate when useAcme=false.";
    };

    tlsKeyPath = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Path to static TLS private key when useAcme=false.";
    };

    exposeOnLan = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Open 80/443 in firewall for external ingress.";
    };
  };

  config = lib.mkIf ing.enable {
    assertions = [
      {
        assertion = ing.domain != null && ing.domain != "";
        message = "mySystem.ingress.enable requires mySystem.ingress.domain.";
      }
      {
        assertion = if ing.useAcme then (ing.acmeEmail != null && ing.acmeEmail != "") else (ing.tlsCertPath != null && ing.tlsKeyPath != null);
        message = "Ingress TLS is incomplete: set acmeEmail when useAcme=true, or tlsCertPath/tlsKeyPath when useAcme=false.";
      }
    ];

    services.nginx = {
      enable = true;
      recommendedProxySettings = true;
      recommendedTlsSettings = true;
      virtualHosts."${ing.domain}" = {
        forceSSL = true;
        enableACME = ing.useAcme;
        locations."/".proxyPass = backendUi;
        locations."/api/".proxyPass = backendApi;
      } // lib.optionalAttrs (!ing.useAcme) {
        sslCertificate = ing.tlsCertPath;
        sslCertificateKey = ing.tlsKeyPath;
      };
    };

    security.acme = lib.mkIf ing.useAcme {
      acceptTerms = true;
      defaults.email = ing.acmeEmail;
    };

    networking.firewall.allowedTCPPorts = lib.mkIf ing.exposeOnLan [ 80 443 ];

    warnings = lib.optionals (mon.commandCenter.bindAddress != "127.0.0.1") [
      "Command center bindAddress is not loopback; prefer 127.0.0.1 behind nginx TLS ingress."
    ];
  };
}
