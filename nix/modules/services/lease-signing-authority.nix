# Foundation C — Asymmetric Lease Signing Authority (ALA rev4), DEFAULT-OFF.
#
# A dedicated, unprivileged, confined service that is the SOLE minter of Ed25519-signed
# first-party capability leases. It holds the Ed25519 PRIVATE key (SOPS -> /run/secrets, 0400,
# owned by this service's own user) — the owner-uid switchboard cannot read it; verifiers hold
# only the public key (config/aqos/lease-signer-keys.json). It NEVER trusts caller input: it reads
# the manifest + resolves the epoch itself and mints every field (rev4 mandate 2', oracle closed).
#
# `enable` defaults to false — this module ships INERT. Turning it on AND flipping
# `CAPABILITY_ASYMMETRIC_LEASE=1` in the switchboard are further, separate owner acts. The SOPS
# private key + the matching public key in config/aqos/lease-signer-keys.json are provisioned at
# activation. `nix/modules/services/switchboard.nix` is NOT touched by this file.
{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.leaseSigningAuthority;
  repoPath = config.mySystem.mcpServers.repoPath;

  authPython = pkgs.python3.withPackages (ps: with ps; [cryptography]);

  # Minimal self-contained bundle: lease_signing_authority imports ONLY capability_lease (which
  # has no local deps — stdlib + cryptography), so the confined service needs no /home access for
  # code. (Manifest + epoch are read from config paths via ReadOnlyPaths below.)
  authBundle = pkgs.runCommand "aq-lease-signing-authority-bundle" {} ''
    mkdir -p $out
    cp ${../../../scripts/ai/lib/lease_signing_authority.py} $out/lease_signing_authority.py
    cp ${../../../scripts/ai/lib/capability_lease.py} $out/capability_lease.py
  '';
in {
  options.mySystem.aiStack.leaseSigningAuthority = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Enable the default-OFF ALA rev4 lease-signing-authority service (dedicated unprivileged
        user, SOPS Ed25519 private key, confined UDS). Enabling the unit does NOT itself route
        first-party lease issuance through it — the switchboard's `CAPABILITY_ASYMMETRIC_LEASE`
        flag independently gates that. Both default false; both are separate owner acts.
      '';
    };
    socketPath = mkOption {
      type = types.str;
      default = "/run/aq-lease-signing-authority/control.sock";
      description = "UDS the authority serves on (transport only; group-restricted 0660; the authority never trusts caller input).";
    };
    keyPath = mkOption {
      type = types.str;
      default = "/run/secrets/lease-signing-ed25519-private-key";
      description = "SOPS-provisioned Ed25519 private key (0400, owned by aq-lease-signing-authority). Absent -> the service fail-closes (signer-unavailable); no lease can mint.";
    };
    keyId = mkOption {
      type = types.str;
      default = "lease-signer-2026-08";
      description = "key_id stamped into minted leases; MUST match an active entry in config/aqos/lease-signer-keys.json.";
    };
  };

  config = mkIf cfg.enable {
    users.users.aq-lease-signing-authority = {
      isSystemUser = true;
      group = "aq-lease-signing-authority";
      description = "Foundation C ALA confined lease signing authority";
    };
    users.groups.aq-lease-signing-authority = {};

    systemd.tmpfiles.rules = [
      "d ${builtins.dirOf cfg.socketPath} 0750 aq-lease-signing-authority aq-lease-signing-authority -"
    ];

    systemd.services.aq-lease-signing-authority = {
      description = "Foundation C ALA rev4 lease signing authority (default-OFF, confined Ed25519 minter)";
      # NOT wantedBy multi-user.target by default beyond enable; the unit exists but mints nothing
      # unless the switchboard flag is also on and a valid SOPS key is provisioned.
      wantedBy = ["multi-user.target"];
      serviceConfig = {
        Type = "simple";
        ExecStart = "${authPython}/bin/python3 ${authBundle}/lease_signing_authority.py";
        User = "aq-lease-signing-authority";
        Group = "aq-lease-signing-authority";
        RuntimeDirectory = "aq-lease-signing-authority";
        StateDirectory = "aq-lease-signing-authority";
        Environment = [
          "AQ_LEASE_SIGNING_SOCKET_PATH=${cfg.socketPath}"
          "AQ_LEASE_SIGNING_KEY_PATH=${cfg.keyPath}"
          "AQ_LEASE_SIGNING_KEY_ID=${cfg.keyId}"
          "AQ_LEASE_SIGNING_MANIFEST_PATH=${repoPath}/config/first-party-tools.json"
          "AQ_LEASE_SIGNING_EPOCH_PATH=${repoPath}/config/capability-lease-epoch"
        ];
        Restart = "on-failure";
        RestartSec = "5s";
        StandardError = "journal";
        # ── Hardening (mirrors execution-cell-runner.nix; no network, no privilege) ──
        NoNewPrivileges = true;
        CapabilityBoundingSet = "";
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        PrivateTmp = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
        RestrictAddressFamilies = ["AF_UNIX"];
        # read-only exposure of just the two config inputs (ProtectHome=read-only already permits;
        # named explicitly so intent is auditable) and the SOPS key dir.
        ReadOnlyPaths = ["${repoPath}/config/first-party-tools.json" "${repoPath}/config/capability-lease-epoch"];
      };
    };
  };
}
