# Foundation C — C6-B2 confined revocation-epoch authority. DEFAULT-OFF.
#
# A dedicated, unprivileged, confined service wrapping the C6-B1 `revocation_epoch.py`
# primitive (commit 91c91f36). Its StateDirectory holds `epoch` (the durable fleet-kill-switch
# counter, seeded once from the tracked genesis SSOT `config/capability-lease-epoch` and never
# reset by a rebuild thereafter), a stable `epoch.lock` inode (created on first bump attempt by
# `revocation_epoch._acquire_epoch_lock`), a durable single-use replay ledger, and append-only
# bounded audit receipts (`epoch.audit.jsonl`, created by `revocation_epoch._append_audit_receipt`).
# Its control UDS is mode 0660, group-restricted, and `revocation_epoch_transport.serve()`
# additionally reads+logs `SO_PEERCRED` — transport membership is NEVER sufficient authority.
#
# C6-S (mechanism B — dedicated TEG-only launch socket + principal topology; see
# `.agents/plans/aqos-foundation-c/C6-S-DESIGN-AND-AUTHORIZATION.md`) adds a SECOND UDS,
# `launchSocketPath`, alongside the control socket above, gated by a NEW, separately-declared
# `aq-revocation-launch-clients` group. That group is declared EMPTY here — the TEG joins it in
# C6b, not this module — so the launch socket grants no one anything yet, and it carries no
# reachable operation until C6a lands `authorize_launch` (this module's transport serves it a
# deny-all stub via `serve_multi()`). Control-socket group membership below is UNCHANGED by
# C6-S: ALA/C2-SCI/owner keep exactly their current `aq-revocation-epoch-clients` access; none of
# them is added to the launch group.
#
# UNLIKE the C2-SCI issuer and the ALA, this service holds NO private signing key anywhere — it
# is SOPS-free by design. Owners sign a `aq.revocation-epoch-bump/1` bump document OFFLINE with
# their own tooling (`revocation_epoch.sign_bump` is explicitly "FOR OFFLINE OWNER-SIGNING
# TOOLING AND TEST FIXTURES ONLY"; this service never calls it and never holds owner key
# material). The only trust root it reads is the tracked, PUBLIC owner-key allowlist
# `config/aqos/c6-owner-public-keys.json` (a repo file, not a secret) — the AUTHORITY is the
# owner-signed bump verified against that allowlist by `revocation_epoch.apply_bump`, never the
# service's own identity, socket group, or peer credentials.
#
# `enable` defaults to false — this module ships INERT. Flipping it on is a separate owner act
# from provisioning the real owner public key into `config/aqos/c6-owner-public-keys.json`
# (currently an all-zeros placeholder that fails closed — see C6-FREEZE-20260807.md watch item
# A1) and from any C6-B3 scheduler-gate flag flip. `nix/modules/services/switchboard.nix` is NOT
# touched by this file.
{
  config,
  lib,
  pkgs,
  ...
}:
with lib; let
  cfg = config.mySystem.aiStack.revocationEpochAuthority;
  repoPath = config.mySystem.mcpServers.repoPath;
  # aq-epoch-bump (C6-B1) is the intended client, run interactively by the owner as
  # primaryUser — NOT this dedicated authority user — so socket access is granted via a shared
  # client group both are members of. Mirrors the ALA/C2-SCI client-access fix exactly (the ALA
  # lesson: without this, an owner-uid caller cannot reach a 0660 socket left in the authority's
  # own group, and every bump attempt fails-closed at the transport layer before it ever reaches
  # the verify check).
  primaryUser = config.mySystem.primaryUser;

  authPython = pkgs.python3.withPackages (ps: with ps; [cryptography]);

  # Minimal self-contained bundle (WR-3 lesson, documented in revocation_epoch.py's own module
  # docstring): revocation_epoch_transport.py (the __main__ entrypoint) imports ONLY
  # revocation_epoch.py, which itself has no local-module dependency (stdlib + cryptography
  # only) — no capability_lease.py bundled, since this primitive never imports it. The confined
  # service therefore needs no /home access for code; its one config input (the owner-key
  # allowlist) is read from a repo path via ReadOnlyPaths below.
  authBundle = pkgs.runCommand "aq-revocation-epoch-authority-bundle" {} ''
    mkdir -p $out
    cp ${../../../scripts/ai/lib/revocation_epoch_transport.py} $out/revocation_epoch_transport.py
    cp ${../../../scripts/ai/lib/revocation_epoch.py} $out/revocation_epoch.py
  '';

  # Genesis epoch value — read from the SAME tracked SSOT capability_lease_gate.py and the ALA/
  # C2-SCI epoch readers already use (`config/capability-lease-epoch`), so this authority's OWN
  # durable epoch store starts in lockstep with the existing epoch baseline rather than an
  # independently-hardcoded value. Trimmed to a bare digit string (no embedded newline — a
  # tmpfiles rule argument is a single line).
  genesisEpoch = lib.strings.trim (builtins.readFile ../../../config/capability-lease-epoch);
in {
  options.mySystem.aiStack.revocationEpochAuthority = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = ''
        Enable the default-OFF C6-B2 confined `aq-revocation-epoch-authority` service (dedicated
        unprivileged user, NO private key — SOPS-free, owner-verify-only, confined UDS).
        Enabling the unit does NOT itself route any scheduler admission decision through it —
        C6-B3's (not-yet-built) `CAPABILITY_SCHEDULER_LEASE_GATE` flag independently gates
        epoch-reader consumption. Both default false; both are separate owner acts, and neither
        substitutes for provisioning the real owner public key (A1).
      '';
    };
    socketPath = mkOption {
      type = types.str;
      default = "/run/aq-revocation-epoch-authority/control.sock";
      description = "UDS the authority serves on (group-restricted 0660; SO_PEERCRED is logged as defense-in-depth only — the trust boundary is the presented owner-signed bump, verified against config/aqos/c6-owner-public-keys.json, never the peer).";
    };
    launchSocketPath = mkOption {
      type = types.str;
      default = "/run/aq-revocation-epoch-authority/launch.sock";
      description = "C6-S (mechanism B) dedicated TEG-only launch socket, alongside the unchanged control socket above — group-restricted 0660 to the NEW, separately-declared `aq-revocation-launch-clients` group (declared empty in this slice; the TEG joins in C6b). No operation is reachable over this socket yet — `authorize_launch` is added in C6a. Lives in the same RuntimeDirectory as the control socket; no new directory rule needed.";
    };
    statePath = mkOption {
      type = types.str;
      default = "/var/lib/aq-revocation-epoch-authority";
      description = "StateDirectory root. Holds `epoch` (durable counter, seeded once from config/capability-lease-epoch, never reset by rebuild), `epoch.lock` (stable lock inode, created on first bump attempt), `epoch.audit.jsonl` (append-only audit receipts), and `ledger/` (durable single-use replay ledger). 0700 — authority-only; nothing else on the host reads or writes this tree.";
    };
    ownerKeysPath = mkOption {
      type = types.str;
      default = "${repoPath}/config/aqos/c6-owner-public-keys.json";
      description = "The SOLE verifier allowlist for a presented `aq.revocation-epoch-bump/1` document — a tracked PUBLIC file (no private key anywhere in this service). Read fresh per request so an owner key rotation/revocation takes effect without a service restart. Currently an all-zeros placeholder that fails every real signature closed (C6-FREEZE-20260807.md watch item A1) until the owner provisions a real key at activation.";
    };
  };

  config = mkIf cfg.enable {
    users.users.aq-revocation-epoch-authority = {
      isSystemUser = true;
      group = "aq-revocation-epoch-authority";
      # Member of BOTH client groups so serve()/serve_multi() can chgrp each socket to its own
      # group (chown to a group requires membership). This grants NO key access and NO launch
      # authority — there IS no key for this service to hold, and the authority is the *server*
      # of the launch socket, never a *client* of its own authorize_launch op (C6-S design §2.2
      # item 3: chgrp-only role, not a launch consumer). The only trust-bearing state it touches
      # is its own StateDirectory (0700, authority-only) and the read-only public owner-key
      # allowlist.
      extraGroups = ["aq-revocation-epoch-clients" "aq-revocation-launch-clients"];
      description = "Foundation C C6-B2 confined revocation-epoch authority (no private key)";
    };
    users.groups.aq-revocation-epoch-authority = {};
    # Shared client group (control socket): members may connect to the 0660 socket. Widens ONLY
    # connect access, never epoch-write access — a peer that connects still advances nothing
    # without a bump an active owner key actually signed (mirrors aq-lease-signing-clients /
    # aq-c2-scheduler-context-clients / aq-execution-cell-clients).
    users.groups.aq-revocation-epoch-clients = {};
    users.users.${primaryUser}.extraGroups = mkAfter ["aq-revocation-epoch-clients"];
    # C6-S launch-socket client group (mechanism B) — declared EMPTY of non-authority
    # principals in this slice. The authority-user above is a member ONLY for the chgrp role;
    # the TEG (the sole intended launch consumer) joins in C6b (dispatch-gateway.nix). The
    # owner/primaryUser is deliberately NOT added here — the kill-lever stays on the control
    # socket, structurally severed from the launch surface (design §2.2 item 4).
    users.groups.aq-revocation-launch-clients = {};

    systemd.tmpfiles.rules = [
      # 0755 = world-traversable so a client-group member (the owner running aq-epoch-bump) can
      # reach the socket inside; the socket itself (0660, client-group) is the access control.
      # Matches the effective RuntimeDirectory mode so the two never disagree across rebuilds.
      # C6-S's launch.sock (cfg.launchSocketPath) lives in this SAME directory by default — no
      # separate tmpfiles rule needed; its own 0660/group restriction is the access control.
      "d ${builtins.dirOf cfg.socketPath} 0755 aq-revocation-epoch-authority aq-revocation-epoch-authority -"
      # Declare the StateDirectory root + the ledger subdir explicitly, ahead of first service
      # start (Rule 13 — declarative-only; mirrors c2-scheduler-context-issuer.nix's identical
      # "parent, explicitly, so nested creation never depends on tmpfiles' leading-component
      # behavior" comment). systemd's own StateDirectory= would also create the root, but an
      # explicit rule here keeps the epoch-seed rule below (which targets a path under this
      # root) independent of unit-start ordering.
      "d ${cfg.statePath} 0700 aq-revocation-epoch-authority aq-revocation-epoch-authority -"
      "d ${cfg.statePath}/ledger 0700 aq-revocation-epoch-authority aq-revocation-epoch-authority -"
      # C6d (`.agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md`
      # §2.1) journal + two-independent-uniqueness-index StateDirectories --
      # siblings of `epoch`/`ledger` above, same 0700 authority-owned mode.
      # `ledger/` (above) is now legacy: `revocation_epoch.apply_bump` no
      # longer consults it for gating (recover() only detects+logs a
      # non-empty legacy ledger, never imports it — design §2.3/§7); it
      # stays declared so any pre-C6d StateDirectory content is preserved
      # across a rebuild (Rule 12/13 — never dropped, never reset).
      "d ${cfg.statePath}/journal 0700 aq-revocation-epoch-authority aq-revocation-epoch-authority -"
      "d ${cfg.statePath}/by-request-id 0700 aq-revocation-epoch-authority aq-revocation-epoch-authority -"
      "d ${cfg.statePath}/by-idempotency-key 0700 aq-revocation-epoch-authority aq-revocation-epoch-authority -"
      # Seed the epoch store ONCE from the tracked genesis SSOT. `f` (lowercase) creates the
      # file ONLY if it does not already exist and never rewrites its content on a later
      # rebuild — critical: a bumped epoch must survive every subsequent `nixos-rebuild switch`
      # untouched. `revocation_epoch.read_epoch` fails closed (typed `EpochStoreError`, never a
      # silent 0) on a genuinely absent store, so this line exists precisely to avoid that
      # failure mode on first activation without ever risking a reset on a later rebuild.
      "f ${cfg.statePath}/epoch 0640 aq-revocation-epoch-authority aq-revocation-epoch-authority - ${genesisEpoch}"
    ];

    systemd.services.aq-revocation-epoch-authority = {
      description = "Foundation C C6-B2 confined revocation-epoch authority (default-OFF, no private key, owner-verify-only)";
      wantedBy = ["multi-user.target"];
      serviceConfig = {
        # C6d recover-before-listen barrier (design §3.4), extended by C6-S
        # §3 to both sockets: the transport's __main__ runs
        # revocation_epoch.recover() to completion, under epoch.lock, ONCE,
        # BEFORE serve_multi() binds/listens/accepts on EITHER the control
        # or the new launch socket, and only calls sd_notify(READY=1) (raw
        # stdlib, no new dependency) once BOTH are listening -- so any unit
        # ordered After= this one, and any client, observes it ready only
        # once its journal is reconciled AND both sockets are up.
        # Type=notify (was Type=simple) is what makes systemd actually wait
        # for that signal.
        Type = "notify";
        ExecStart = "${authPython}/bin/python3 ${authBundle}/revocation_epoch_transport.py";
        User = "aq-revocation-epoch-authority";
        Group = "aq-revocation-epoch-authority";
        RuntimeDirectory = "aq-revocation-epoch-authority";
        StateDirectory = "aq-revocation-epoch-authority";
        StateDirectoryMode = "0700";
        Environment = [
          "AQ_REVOCATION_EPOCH_SOCKET_PATH=${cfg.socketPath}"
          "AQ_REVOCATION_EPOCH_CLIENT_GROUP=aq-revocation-epoch-clients"
          "AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH=${cfg.ownerKeysPath}"
          "AQ_REVOCATION_EPOCH_EPOCH_PATH=${cfg.statePath}/epoch"
          "AQ_REVOCATION_EPOCH_LEDGER_DIR=${cfg.statePath}/ledger"
          # C6-S (mechanism B) — the dedicated TEG-only launch socket, alongside the
          # unchanged control socket above. No reachable op until C6a; deny-all stub.
          "AQ_REVOCATION_LAUNCH_SOCKET_PATH=${cfg.launchSocketPath}"
          "AQ_REVOCATION_LAUNCH_CLIENT_GROUP=aq-revocation-launch-clients"
        ];
        Restart = "on-failure";
        RestartSec = "5s";
        StandardError = "journal";
        # ── Hardening (mirrors lease-signing-authority.nix / c2-scheduler-context-issuer.nix)
        # — this service holds no key at all, so its blast radius is already smaller than
        # either of those, but every other confinement layer still applies in full. ──
        NoNewPrivileges = true;
        CapabilityBoundingSet = "";
        ProtectSystem = "strict";
        ProtectHome = "read-only";
        PrivateTmp = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
        RestrictAddressFamilies = ["AF_UNIX"];
        # Read-only exposure of the one config input (the public owner-key allowlist); the
        # epoch/ledger/audit paths all live under StateDirectory (read-write by construction —
        # ReadWritePaths is implicit for StateDirectory under ProtectSystem=strict, no
        # additional declaration needed).
        ReadOnlyPaths = [cfg.ownerKeysPath];
      };
    };
  };
}
