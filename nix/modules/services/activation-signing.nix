# Activation signing MVP, slice 2: owner-side provisioning (SSOT
# .agents/plans/system-integrity-recovery/ACTIVATION-PIPELINE.md rev7).
#
# Provides, all owned by root and changeable only by an owner-authenticated rebuild or a sudo password:
#   /var/lib/aq-activation/{log,evidence}  0755 dirs; head (0644) is created by `--init-chain`
#   /var/lib/aq-activation/signing.key      0400, generated ON THE HOST by a oneshot (never in the repo or SOPS)
#   /var/lib/aq-activation/signing.pub      public half, for the owner to pin into signerPublicKeys
#   /etc/aq-activation/signers.json         {"keys": [<pinned public keys>]}; empty until pinned => nothing verifies
#   /etc/aq-activation/deployment-id        machine identity; Nix-declared, else written once by aq-activation-deployment-id from /etc/machine-id + deployment-salt
#   /etc/aq-activation/eligible.json        the only source of item eligibility
#   aq-activation-sign                      store-installed signer, sudo with a password (never NOPASSWD)
{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.activation.signing;
  primaryUser = config.mySystem.primaryUser;
  stateDir = "/var/lib/aq-activation";

  pyEnv = pkgs.python3.withPackages (ps: [ps.cryptography]);

  # Store copy of the verifier library and the signer, from the same checkout sources.
  bundle = pkgs.runCommand "aq-activation-signer-bundle" {} ''
    mkdir -p $out
    cp ${../../../scripts/ai/lib/activation_chain.py} $out/activation_chain.py
    cp ${../../../scripts/ai/lib/activation_signer.py} $out/activation_signer.py
  '';

  # Scrubbed environment: nothing inherited (no PYTHON*, PATH, HOME); python -I ignores cwd and user site.
  signer = pkgs.writeShellScriptBin "aq-activation-sign" ''
    exec ${pkgs.coreutils}/bin/env -i \
      LC_ALL=C.UTF-8 \
      SUDO_USER="''${SUDO_USER:-}" \
      SUDO_UID="''${SUDO_UID:-}" \
      SUDO_GID="''${SUDO_GID:-}" \
      AQ_ACTIVATION_SYSTEMCTL=${pkgs.systemd}/bin/systemctl \
      ${pyEnv}/bin/python -I ${bundle}/activation_signer.py "$@"
  '';
  signerBin = "${signer}/bin/aq-activation-sign";

  eligibleType = types.submodule {
    options = {
      plan = mkOption {type = types.strMatching "[a-z0-9._-]{1,64}";};
      item = mkOption {type = types.strMatching "[a-z0-9._-]{1,64}";};
      units = mkOption {
        type = types.listOf types.str;
        description = "systemd units that run the item; each must reference only store or manifest paths.";
      };
      paths = mkOption {
        type = types.listOf types.str;
        default = [];
        description = "Exact store paths (or owner-declared paths) of the executables, helpers and configuration.";
      };
      state_paths = mkOption {
        type = types.listOf types.str;
        default = [];
        description = "Mutable state paths the item reads; shown to and confirmed by the owner at signing.";
      };
    };
  };
in {
  options.mySystem.activation.signing = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = "Provision the activation signer, signing-key bootstrap, verifier inputs under /etc/aq-activation and the password-required sudo rule.";
    };
    signerPublicKeys = mkOption {
      type = types.listOf (types.strMatching "[0-9a-f]{64}");
      default = [];
      description = ''
        Ed25519 public keys (hex, 32 bytes) the verifier accepts. Empty until the owner pins the key from
        /var/lib/aq-activation/signing.pub after first boot; while empty nothing verifies (fail closed).
      '';
    };
    deploymentIdSalt = mkOption {
      type = types.str;
      default = "nixos-dev-quick-deploy/activation";
      description = "Salt for the derived deployment id.";
    };
    deploymentId = mkOption {
      type = types.nullOr (types.strMatching "[A-Za-z0-9._-]{8,64}");
      default = null;
      description = ''
        Explicit, unique, stable machine identity bound into the genesis and every later envelope. When null
        (default) the aq-activation-deployment-id oneshot writes /etc/aq-activation/deployment-id once, as the
        first 32 hex of sha256 "<deploymentIdSalt>:<contents of /etc/machine-id>", so hosts sharing a hostname
        differ and a rename does not invalidate the chain. Signer and verifier both read only that file; if it
        is absent (no valid /etc/machine-id, oneshot failed) both fail closed.
      '';
    };
    eligibleItems = mkOption {
      type = types.listOf eligibleType;
      default = [];
      description = "Owner-controlled manifest of items the signer may grant. Empty: every grant is refused.";
    };
  };

  config = mkIf cfg.enable {
    environment.systemPackages = [signer];

    # `head` is deliberately not pre-created: `--init-chain` refuses when it exists.
    systemd.tmpfiles.rules = [
      "d ${stateDir} 0755 root root -"
      "d ${stateDir}/log 0755 root root -"
      "d ${stateDir}/evidence 0755 root root -"
    ];

    environment.etc."aq-activation/signers.json".text = builtins.toJSON {keys = cfg.signerPublicKeys;};
    environment.etc."aq-activation/deployment-salt".text = cfg.deploymentIdSalt + "\n";
    environment.etc."aq-activation/deployment-id" = mkIf (cfg.deploymentId != null) {text = cfg.deploymentId + "\n";};
    environment.etc."aq-activation/eligible.json".text = builtins.toJSON cfg.eligibleItems;

    systemd.services.aq-activation-deployment-id = mkIf (cfg.deploymentId == null) {
      description = "Provision the activation deployment id from machine-id + salt if absent";
      wantedBy = ["multi-user.target"];
      before = ["aq-activation-keygen.service"];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${pyEnv}/bin/python -I ${bundle}/activation_signer.py --init-id";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ReadWritePaths = ["/etc/aq-activation"];
        CapabilityBoundingSet = ["CAP_DAC_OVERRIDE" "CAP_CHOWN" "CAP_FOWNER"];
        RestrictAddressFamilies = ["AF_UNIX"];
        LockPersonality = true;
      };
    };

    systemd.services.aq-activation-keygen = {
      description = "Generate the activation signing key if absent (host-local, root-only)";
      wantedBy = ["multi-user.target"];
      after = ["systemd-tmpfiles-setup.service"];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = "${pyEnv}/bin/python -I ${bundle}/activation_signer.py --init-key";
        UMask = "0077";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ReadWritePaths = [stateDir];
        CapabilityBoundingSet = ["CAP_DAC_OVERRIDE" "CAP_CHOWN" "CAP_FOWNER"];
        RestrictAddressFamilies = ["AF_UNIX"];
        LockPersonality = true;
      };
    };

    # Password required (no NOPASSWD); timestamp_timeout=0 is global (core/base.nix), env_reset pinned per command.
    security.sudo.extraRules = [
      {
        users = [primaryUser];
        commands =
          map (a: {command = "${signerBin} ${a}";}) ["--init-chain" "--recover" "grant *" "revoke *" "wave-grant *"];
      }
    ];
    security.sudo.extraConfig = ''
      Defaults!${signerBin} env_reset
    '';
  };
}
