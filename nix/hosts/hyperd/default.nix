{
  lib,
  config,
  ...
}: {
  imports =
    lib.optionals (builtins.pathExists ./facts.nix) [./facts.nix]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [./hardware-configuration.nix];

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
  mySystem.kernel.track = lib.mkForce "latest-stable";
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

  # ── Feature toggles tracked in git (owner 2026-11-19: everything ON at next rebuild) ──
  # These used to live only in the gitignored deploy-options.local.nix, which a pure flake
  # build (git tree) never sees, so they silently did not apply. Non-secret booleans belong
  # here; the local file stays for secrets wiring and per-machine overrides only.
  # mkDefault so deploy-options.local.nix (when built --impure) can still override.
  mySystem.roles.agenticToolchain.enable = lib.mkDefault true;
  # Dead-man auto-revert sweep timer. Arms nothing by itself; reverts only an activation
  # explicitly armed with `aq-activation-guard arm`. REVERT: false. Plain assignment (not
  # mkDefault): ai-dev.nix sets this to mkDefault false, and two mkDefaults conflict.
  mySystem.aiStack.activationAutoRevert.enable = true;
  # aq-oncalld: local-only incident intake (journal -> triage -> claim). No external sends.
  # REVERT: false.
  services.aiOncalld.enable = lib.mkDefault true;
  # auditd with a narrowed watch list: postgres/redis data dirs are left out because -p rwxa
  # on them logs every DB file read (churn). REVERT: false.
  mySystem.logging.audit.enable = lib.mkDefault true;
  mySystem.logging.audit.watchPaths = lib.mkDefault ["/var/lib/aidb" "/srv/patient-data"];
}
