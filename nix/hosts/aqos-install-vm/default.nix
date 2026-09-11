{ lib, config, pkgs, ... }:
let
  # s1c: nix/modules/services/mcp-servers.nix hard-asserts
  # mySystem.secrets.enable=true whenever mySystem.roles.aiStack.enable=true
  # (only the ai-dev variant of this host enables aiStack — plain/luks/
  # gaming/minimal never do). A disposable VM has no real SOPS key (HARD
  # CONSTRAINT: no real secrets), so this derivation generates a TEST-ONLY
  # age keypair + a SOPS file of dummy placeholder values ENTIRELY AT BUILD
  # TIME, self-contained in the Nix store — nothing is ever written to the
  # repo tree. That matters because `nix/hosts/*/secrets.sops.yaml` is
  # deliberately repo-gitignored everywhere (.gitignore:162, zero-secrets-
  # in-repo policy); a committed dummy file would fight that guard for no
  # reason when generating it at build time is just as declarative and adds
  # nothing to git. Every AI-stack service that decrypts one of these gets a
  # harmless placeholder string — the honest degraded/no-auth-to-anything-
  # real outcome for a VM with no real secrets. No network access is used
  # (age-keygen + sops --encrypt are pure local computation).
  aqosInstallVmTestSecrets = pkgs.runCommand "aqos-install-vm-ai-dev-test-secrets" {
    nativeBuildInputs = [ pkgs.sops pkgs.age ];
  } ''
    mkdir -p "$out"
    age-keygen -o "$out/key.txt"
    # age-keygen's stderr message is "Public key: ..." (capital P) but the
    # comment line it writes INTO the key file itself is "# public key: ..."
    # (lowercase) — read that instead of stderr so this doesn't depend on
    # matching age-keygen's log wording exactly.
    pub="$(grep 'public key:' "$out/key.txt" | awk '{print $NF}')"
    if [ -z "$pub" ]; then
      echo "aqosInstallVmTestSecrets: failed to extract age public key from $out/key.txt" >&2
      exit 1
    fi

    cat > plain.yaml <<'PLAINEOF'
    aq-lease-signing-key: "test-only-dummy-lease-signing-key-do-not-use"
    aq-grant-signing-key: "test-only-dummy-grant-signing-key-do-not-use"
    aidb_api_key: "test-only-dummy-aidb-api-key"
    hybrid_coordinator_api_key: "test-only-dummy-hybrid-api-key"
    embeddings_api_key: "test-only-dummy-embeddings-api-key"
    postgres_password: "test-only-dummy-postgres-password"
    redis_password: "test-only-dummy-redis-password"
    aider_wrapper_api_key: "test-only-dummy-aider-wrapper-api-key"
    github_mcp_token: "test-only-dummy-github-mcp-token"
    crowdsec_bouncer_api_key: "test-only-dummy-crowdsec-bouncer-api-key"
    lease-signing-ed25519-private-key: "test-only-dummy-lease-signing-ed25519-key"
    c6-scheduler-context-signing-key: "test-only-dummy-c6-scheduler-signing-key"
    PLAINEOF

    SOPS_AGE_KEY_FILE="$out/key.txt" sops --config /dev/null --encrypt \
      --age "$pub" --input-type yaml --output-type yaml \
      plain.yaml > "$out/secrets.sops.yaml"
  '';
in
# ---------------------------------------------------------------------------
# aqos-install-vm — disposable disk/install-MECHANICS harness host for the
# golden aqos-workstation profile (slice s1a,
# .agents/plans/aqos-installer-experience/END-TO-END-BARE-METAL-PLAN.md).
#
# Unlike nix/hosts/aqos-vm (which only proves BOOT, via
# `nixos-rebuild build-vm`'s self-synthesized disk — it never partitions
# anything), this host is the PAYLOAD for
# inputs.disko.lib.testLib.makeDiskoTest (see flake.nix
# checks.x86_64-linux.aqos-install-vm-disko-{plain,luks} and
# scripts/testing/aqos-install-vm-dogfood.sh): it is extended
# (`.extendModules`, wired in flake.nix) by disko's rootless in-VM test
# framework, which partitions/formats a REAL virtual disk inside qemu,
# nixos-enters + installs this exact closure, then reboots into it from the
# freshly-written disk — proving disk+install MECHANICS, not just boot.
#
# Golden profile imported unmodified (via facts.nix -> mySystem.profile =
# "aqos-workstation", forced in flake.nix); only VM-safe overrides below,
# modeled on nix/hosts/aqos-vm/default.nix.
# ---------------------------------------------------------------------------
{
  imports = [ ./facts.nix ];

  # Same deliberate, documented exception as aqos-vm/default.nix (see
  # nix/modules/core/users.nix's "never set initialPassword" policy):
  # throwaway VM, no prior /etc/shadow to preserve, and the harness needs to
  # be able to prove a console login after a real disko install.
  users.users.${config.mySystem.primaryUser}.initialPassword = "aqosvm";

  # No real network/hardware to reach — keep the VM guest quiet and fast.
  # mkForce (not mkDefault): nix/modules/core/network.nix already sets this
  # with mkDefault true, and two mkDefault definitions at the same priority
  # conflict rather than one silently winning.
  networking.firewall.enable = lib.mkForce false;

  # See aqosInstallVmTestSecrets above (let block) for what this wires and why.
  mySystem.secrets = lib.mkIf config.mySystem.roles.aiStack.enable {
    enable = true;
    sopsFile = "${aqosInstallVmTestSecrets}/secrets.sops.yaml";
    # ageKeyFile is intentionally left at its option default
    # (/var/lib/sops-nix/key.txt) — sops-nix's own `sops.age.keyFile` option
    # explicitly REJECTS a Nix-store-path string
    # (modules/sops/default.nix: `check = x: !lib.path.hasStorePathPrefix ...`),
    # so the test key can't just be pointed at ${aqosInstallVmTestSecrets}
    # directly. It is staged at this default path instead by the
    # generate-age-key activation-script override below — sops-nix's own
    # documented extension point for "provision the age key before secrets
    # are decrypted".
  };

  # sops-nix normally uses `sops.age.generateKey = true` to generate a
  # machine-specific key the first time a host boots (system.activationScripts
  # .generate-age-key, gated on that flag, ordered BEFORE .setupSecrets — see
  # modules/sops/default.nix). We want that same ordering guarantee but need
  # a key whose PUBLIC half we already encrypted the test secrets against
  # (aqosInstallVmTestSecrets above), not a fresh random one, so
  # generateKey=true only to pull "generate-age-key" into .setupSecrets'
  # dependency list, and mkOverride replaces sops-nix's own generation logic
  # with "copy our pre-encrypted test key into place instead". mkOverride 40
  # (< the normal-priority 100 sops-nix defines its own script at) wins the
  # module-system merge outright — this is not a conflicting-definition
  # error, it is NixOS's documented mechanism for one module to replace
  # another's definition of the same option.
  sops.age.generateKey = lib.mkIf config.mySystem.roles.aiStack.enable true;
  system.activationScripts.generate-age-key = lib.mkIf config.mySystem.roles.aiStack.enable (
    lib.mkOverride 40 (lib.stringAfter [ ] ''
      keyfile="${config.sops.age.keyFile}"
      if [ ! -f "$keyfile" ]; then
        mkdir -p "$(dirname "$keyfile")"
        install -m 0600 ${aqosInstallVmTestSecrets}/key.txt "$keyfile"
        echo "aqosInstallVmTestSecrets: staged TEST-ONLY age key -> $keyfile"
      fi
    '')
  );

  # Boot marker for the post-install, rebooted VM (checked via
  # `machine.wait_for_unit` + journalctl in flake.nix's makeDiskoTest
  # `bootCommands` — the disko test framework gives us a Python test-driver
  # `machine` object with real systemctl/journalctl access, unlike
  # aqos-vm-dogfood.sh's headless `-nographic` qemu which has to scrape
  # /dev/console instead). RemainAfterExit so a one-shot's success is
  # observable via wait_for_unit after it has already run.
  systemd.services.aqos-install-vm-dogfood-marker = {
    description = "AQOS install-VM dogfood boot marker (scripts/testing/aqos-install-vm-dogfood.sh)";
    wantedBy = [ "multi-user.target" ];
    after = [ "multi-user.target" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    script = ''
      # systemd services get a minimal PATH that excludes /run/current-system/sw/bin
      # (where systemPackages install), so check the system-profile path directly —
      # that is exactly where the golden aqos-workstation profile puts hyperfine.
      if [ -x /run/current-system/sw/bin/hyperfine ]; then
        echo "AQOS-INSTALL-VM-DOGFOOD-BOOT-OK golden_marker=hyperfine-ok"
      else
        echo "AQOS-INSTALL-VM-DOGFOOD-BOOT-OK golden_marker=MISSING"
      fi
    '';
  };

  # ---------------------------------------------------------------------------
  # s1c (END-TO-END-BARE-METAL-PLAN.md): full-factory service-TOPOLOGY marker.
  # Only active for the ai-dev/aiStack-ON variant of this host
  # (aqos-install-vm-ai-dev, auto-generated by flake.nix's host x profile
  # matrix — profiles = ["ai-dev" "gaming" "minimal"]); a no-op for the
  # plain/luks/gaming/minimal variants of this same host dir, which never
  # enable aiStack.
  #
  # Scope (owner-narrowed 2026-09-11): this VM proves the DECLARATIVE CONFIG
  # reproduces the full ai-dev service topology — it does NOT provision or
  # serve a model (model files are per-deployment runtime state, not part of
  # "the config reproduces"). llama-cpp.service is therefore asserted only as
  # DECLARED/LOADED (its unit exists in the generated system), never ACTIVE —
  # without a model file at mySystem.aiStack.llamaCpp.model it cannot reach
  # ACTIVE, and asserting otherwise would be dishonest (Rule 19: report
  # faithfully, never fake a result). AIDB, hybrid-coordinator, switchboard,
  # and the command-center dashboard (the service the 216/GROUP fix targets)
  # ARE required to reach systemd ACTIVE — that is the real "factory
  # reproduces" signal for the non-model tooling.
  # ---------------------------------------------------------------------------
  systemd.services.aqos-install-vm-ai-dev-factory-topology =
    lib.mkIf config.mySystem.roles.aiStack.enable {
      description = "AQOS install-VM ai-dev full-factory service-topology marker (s1c)";
      wantedBy = [ "multi-user.target" ];
      after = [ "multi-user.target" "ai-stack.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
      };
      path = [ pkgs.systemd pkgs.coreutils ];
      script = ''
        required_active="ai-aidb.service ai-hybrid-coordinator.service ai-switchboard.service command-center-dashboard-api.service"
        ok=1
        for unit in $required_active; do
          state="unknown"
          # Services can take up to ~2 min to bind after multi-user.target;
          # retry rather than sampling once and calling it a failure.
          for i in $(seq 1 24); do
            state="$(systemctl is-active "$unit" 2>/dev/null || true)"
            [ "$state" = "active" ] && break
            sleep 5
          done
          echo "topology: $unit=$state"
          [ "$state" = "active" ] || ok=0
        done
        llama_load="$(systemctl show -p LoadState --value llama-cpp.service 2>/dev/null || echo unknown)"
        echo "topology: llama-cpp.service load=$llama_load (asserted DECLARED only — no model provisioned in this VM)"
        [ "$llama_load" = "loaded" ] || ok=0
        if [ "$ok" -eq 1 ]; then
          echo "AQOS-INSTALL-VM-AI-DEV-FACTORY-TOPOLOGY-OK"
        else
          echo "AQOS-INSTALL-VM-AI-DEV-FACTORY-TOPOLOGY-FAIL"
        fi
      '';
    };
}
