{ lib, config, ... }:
{
  imports =
    [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # ── Host-Specific Configuration ───────────────────────────────────────────────
  # Shared ai-dev and workstation-class behavior now lives in
  # nix/modules/profiles/ai-dev.nix and
  # nix/modules/host-classes/p14s-amd-ai-workstation.nix.
  # Keep only machine-specific overrides here.

  # Use the unified host SOPS bundle for CrowdSec rather than a separate secret
  # path. The secret is decrypted by mySystem.secrets into /run/secrets/*.
  mySystem.security.crowdsec = {
    enable = lib.mkForce true;
    enableFirewallBouncer = lib.mkForce true;
    apiKeyFile =
      lib.mkForce "/run/secrets/${config.mySystem.secrets.names.crowdsecBouncerApiKey}";
  };

  # Pin the workstation to the current kernel/hardening posture explicitly so
  # the install/rebuild/switch workflow keeps these choices visible at host
  # level instead of only inheriting them implicitly from the ai-dev profile.
  mySystem.kernel.track = lib.mkForce "6.19-latest";
  mySystem.kernel.hardening = {
    enable = lib.mkForce true;
    level = lib.mkForce "maximum";
    mitigations = {
      spectre = lib.mkForce true;
      meltdown = lib.mkForce true;
      mds = lib.mkForce true;
      srso = lib.mkForce true;
    };
  };
}
