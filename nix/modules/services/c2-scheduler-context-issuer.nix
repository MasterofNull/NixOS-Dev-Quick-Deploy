# Foundation C — C2 scheduler-lease-context issuer (C2-SCI), subslice B2. DEFAULT-OFF.
#
# A dedicated, unprivileged, confined service that is the SOLE minter of Ed25519-signed
# `aq.scheduler-lease-context/1` documents (scripts/ai/lib/scheduler_context_issuer.py). It holds
# the issuer's OWN Ed25519 PRIVATE key (SOPS -> /run/secrets, 0400, owned by this service's own
# user) — a distinct key family from the C2 admission-lease signer (ALA, config/aqos/
# lease-signer-keys.json). Verifiers hold only the public key (config/aqos/
# c6-scheduler-signer-keys.json). Authority to mint is the PRESENTED, independently-verified
# Ed25519-signed C2 lease, never the caller/peer — SO_PEERCRED is defense-in-depth only (design
# rev2/rev3/rev4 §3); see scheduler_context_issuer.py / scheduler_context_transport.py docstrings.
#
# `enable` defaults to false — this module ships INERT. Turning it on AND flipping
# `CAPABILITY_SCHEDULER_CONTEXT_ISSUER=1` in the switchboard (a separate B3 subslice, not built
# here) are further, separate owner acts; they are independently gated from C6's
# `CAPABILITY_SCHEDULER_LEASE_GATE` flag (design §4). The SOPS private key + the matching public
# key in config/aqos/c6-scheduler-signer-keys.json are provisioned at activation, not by this
# file. `nix/modules/services/switchboard.nix` is NOT touched by this file.
{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.c2SchedulerContextIssuer;
  repoPath = config.mySystem.mcpServers.repoPath;
  # The switchboard (the sole intended client, once B3 wires its outbound call) runs as the human
  # primaryUser, NOT this dedicated issuer user, so socket access is granted via a shared client
  # group both are members of — mirrors lease-signing-authority.nix's client-access fix exactly
  # (the ALA lesson: without this, the switchboard's owner-uid caller cannot reach a 0660 socket
  # left in the issuer's own group, and every mint call fails-closed at the transport layer before
  # it ever reaches the trust check).
  primaryUser = config.mySystem.primaryUser;

  issuerPython = pkgs.python3.withPackages (ps: with ps; [cryptography]);

  # Self-contained bundle: scheduler_context_transport (the __main__ entrypoint) imports
  # scheduler_context_issuer, which imports capability_lease; none of the three has any other
  # local dependency, so the confined service needs no /home access for code (manifest-equivalent
  # inputs — the lease-signer verifier allowlist + epoch file — are read from config paths via
  # ReadOnlyPaths below).
  issuerBundle = pkgs.runCommand "aq-c2-scheduler-context-issuer-bundle" {} ''
    mkdir -p $out
    cp ${../../../scripts/ai/lib/scheduler_context_transport.py} $out/scheduler_context_transport.py
    cp ${../../../scripts/ai/lib/scheduler_context_issuer.py} $out/scheduler_context_issuer.py
    cp ${../../../scripts/ai/lib/capability_lease.py} $out/capability_lease.py
  '';
in {
  options.mySystem.aiStack.c2SchedulerContextIssuer = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Enable the default-OFF C2 scheduler-lease-context issuer service (dedicated unprivileged
        user, SOPS Ed25519 private key, confined UDS). Enabling the unit does NOT itself route any
        admission decision through it — the switchboard's (not-yet-built, B3)
        `CAPABILITY_SCHEDULER_CONTEXT_ISSUER` flag independently gates that. Both default false;
        both are separate owner acts.
      '';
    };
    socketPath = mkOption {
      type = types.str;
      default = "/run/aq-c2-scheduler-context-issuer/control.sock";
      description = "UDS the issuer serves on (group-restricted 0660; SO_PEERCRED is logged as defense-in-depth only — the trust boundary is the presented signed lease, not the peer).";
    };
    keyPath = mkOption {
      type = types.str;
      default = "/run/secrets/c6-scheduler-context-signing-key";
      description = "SOPS-provisioned Ed25519 private key (0400, owned by aq-c2-scheduler-context-issuer). Absent -> the service fail-closes (signer-unavailable); no context can mint.";
    };
    keyId = mkOption {
      type = types.str;
      default = "c2-scheduler-context-signer-2026-08";
      description = "issuer_key_id stamped into every minted context; MUST match an active entry in config/aqos/c6-scheduler-signer-keys.json.";
    };
    leaseKeysPath = mkOption {
      type = types.str;
      default = "${repoPath}/config/aqos/lease-signer-keys.json";
      description = "The SOLE verifier allowlist for the PRESENTED C2 admission lease (a DISTINCT key family from keyId's own signer-verifier file). Read fresh per request so a revocation takes effect without a service restart.";
    };
    epochPath = mkOption {
      type = types.str;
      default = "${repoPath}/config/capability-lease-epoch";
      description = "The same authoritative revocation-epoch source lease_signing_authority._resolve_epoch() uses (design OBLIG-1 / mandate 4) — never a caller-supplied epoch.";
    };
    contextTtlCapSeconds = mkOption {
      type = types.int;
      default = 900;
      description = "Upper bound on a minted context's lifetime; the actual expiry is min(lease.expires_at, issued_at + this) per design mandate 4 — a context can never outlive its lease.";
    };
    ledgerDir = mkOption {
      type = types.str;
      default = "/var/lib/aq-c2-scheduler-context-issuer/ledger";
      description = ''
        B2.5 durable single-use ledger directory (`scheduler_context_issuer
        .DurableSingleUseLedger`): one `O_CREAT|O_EXCL`-created marker file per consumed
        `{lease_id, grant_digest}`, under `StateDirectory` so it survives a service restart —
        closes the fail-open-across-restarts gap the B1/B2 in-memory ledger left open (a restart
        must never forget which leases were already consumed). 0700, owned by
        aq-c2-scheduler-context-issuer. Operator reset path: delete one marker file to clear
        exactly that lease's single-use slot (see the class docstring).
      '';
    };
  };

  config = mkIf cfg.enable {
    users.users.aq-c2-scheduler-context-issuer = {
      isSystemUser = true;
      group = "aq-c2-scheduler-context-issuer";
      # Member of the client group so serve() can chgrp the socket to it (chown to a group requires
      # membership). This grants NO key access — the Ed25519 private key is 0400 user-only.
      extraGroups = ["aq-c2-scheduler-context-clients"];
      description = "Foundation C C2-SCI confined scheduler-lease-context issuer";
    };
    users.groups.aq-c2-scheduler-context-issuer = {};
    # Shared client group: members may connect to the 0660 socket. Widens ONLY connect access,
    # never key access — and per the trust model, a peer that connects still mints nothing without
    # a presented lease it cannot forge (mirrors aq-lease-signing-clients / aq-execution-cell-clients).
    users.groups.aq-c2-scheduler-context-clients = {};
    users.users.${primaryUser}.extraGroups = mkAfter ["aq-c2-scheduler-context-clients"];

    systemd.tmpfiles.rules = [
      # 0755 = world-traversable so a client-group member (the switchboard user) can reach the
      # socket inside; the socket itself (0660, client-group) is the access control. Matches the
      # effective RuntimeDirectory mode so the two never disagree across rebuilds.
      "d ${builtins.dirOf cfg.socketPath} 0755 aq-c2-scheduler-context-issuer aq-c2-scheduler-context-issuer -"
      # B2.5: declare the durable single-use ledger dir (+ its StateDirectory parent, explicitly
      # so nested creation never depends on tmpfiles' leading-component behavior) ahead of first
      # service start (Rule 13 — declarative-only). 0700: issuer-only, no client-group access —
      # the ledger is never read/written by anything but this service itself.
      "d ${builtins.dirOf cfg.ledgerDir} 0700 aq-c2-scheduler-context-issuer aq-c2-scheduler-context-issuer -"
      "d ${cfg.ledgerDir} 0700 aq-c2-scheduler-context-issuer aq-c2-scheduler-context-issuer -"
    ];

    systemd.services.aq-c2-scheduler-context-issuer = {
      description = "Foundation C C2-SCI scheduler-lease-context issuer (default-OFF, confined Ed25519 minter)";
      wantedBy = ["multi-user.target"];
      serviceConfig = {
        Type = "simple";
        ExecStart = "${issuerPython}/bin/python3 ${issuerBundle}/scheduler_context_transport.py";
        User = "aq-c2-scheduler-context-issuer";
        Group = "aq-c2-scheduler-context-issuer";
        RuntimeDirectory = "aq-c2-scheduler-context-issuer";
        StateDirectory = "aq-c2-scheduler-context-issuer";
        StateDirectoryMode = "0700";
        Environment = [
          "AQ_SCHEDULER_CONTEXT_SOCKET_PATH=${cfg.socketPath}"
          "AQ_SCHEDULER_CONTEXT_CLIENT_GROUP=aq-c2-scheduler-context-clients"
          "AQ_SCHEDULER_CONTEXT_KEY_PATH=${cfg.keyPath}"
          "AQ_SCHEDULER_CONTEXT_KEY_ID=${cfg.keyId}"
          "AQ_SCHEDULER_CONTEXT_LEASE_KEYS_PATH=${cfg.leaseKeysPath}"
          "AQ_SCHEDULER_CONTEXT_EPOCH_PATH=${cfg.epochPath}"
          "AQ_SCHEDULER_CONTEXT_TTL_CAP_SECONDS=${toString cfg.contextTtlCapSeconds}"
          # B2.5: durable single-use ledger — closes the fail-open-across-restarts gap the B1/B2
          # in-memory ledger left open. build_env_handler() switches to DurableSingleUseLedger
          # whenever this is set (always, for this unit).
          "AQ_SCHEDULER_CONTEXT_LEDGER_DIR=${cfg.ledgerDir}"
        ];
        Restart = "on-failure";
        RestartSec = "5s";
        StandardError = "journal";
        # ── Hardening (mirrors lease-signing-authority.nix / execution-cell-runner.nix) ──
        NoNewPrivileges = true;
        CapabilityBoundingSet = "";
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        PrivateTmp = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
        RestrictAddressFamilies = ["AF_UNIX"];
        ReadOnlyPaths = [cfg.leaseKeysPath cfg.epochPath];
      };
    };
  };
}
