{ lib, config, pkgs, ... }:
let
  aqosVmTestSecrets = pkgs.runCommand "aqos-vm-ai-dev-test-secrets" {
    nativeBuildInputs = [ pkgs.sops pkgs.age ];
  } ''
    mkdir -p "$out"
    age-keygen -o "$out/key.txt"
    pub="$(grep 'public key:' "$out/key.txt" | awk '{print $NF}')"
    if [ -z "$pub" ]; then
      echo "aqosVmTestSecrets: failed to extract age public key from $out/key.txt" >&2
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
# aqos-vm — disposable dogfood host for the golden aqos-workstation profile.
#
# Built ONLY via `nixos-rebuild build-vm --flake .#aqos-vm` (see
# scripts/testing/aqos-vm-dogfood.sh). Never deployed to real hardware, never
# switched with sudo. VM-safe overrides only; all golden-profile behavior
# (roles/packages/hardening) is inherited unmodified from
# nix/modules/profiles/aqos-workstation.nix — nothing is duplicated here.
# ---------------------------------------------------------------------------
{
  imports =
    lib.optionals (builtins.pathExists ./facts.nix) [ ./facts.nix ]
    ++ lib.optionals (builtins.pathExists ./hardware-configuration.nix) [ ./hardware-configuration.nix ];

  # Deliberate, documented exception to the "never set initialPassword" policy
  # in nix/modules/core/users.nix: this is a throwaway VM with no prior
  # /etc/shadow to preserve, and the dogfood harness needs to be able to log
  # in (console/serial) to assert the booted system is coherent.
  users.users.${config.mySystem.primaryUser}.initialPassword = "aqosvm";

  # No real network/hardware to reach — keep the VM guest quiet and fast.
  # mkForce (not mkDefault): nix/modules/core/network.nix already sets this
  # with mkDefault true, and two mkDefault definitions at the same priority
  # conflict rather than one silently winning.
  networking.firewall.enable = lib.mkForce false;

  # Wire test secrets when the ai-dev profile is evaluated on this VM target.
  mySystem.secrets = lib.mkIf config.mySystem.roles.aiStack.enable {
    enable = true;
    sopsFile = "${aqosVmTestSecrets}/secrets.sops.yaml";
  };

  sops.age.generateKey = lib.mkIf config.mySystem.roles.aiStack.enable true;
  system.activationScripts.generate-age-key = lib.mkIf config.mySystem.roles.aiStack.enable (
    lib.mkOverride 40 (lib.stringAfter [ ] ''
      keyfile="${config.sops.age.keyFile}"
      if [ ! -f "$keyfile" ]; then
        mkdir -p "$(dirname "$keyfile")"
        install -m 0600 ${aqosVmTestSecrets}/key.txt "$keyfile"
        echo "aqosVmTestSecrets: staged TEST-ONLY age key -> $keyfile"
      fi
    '')
  );

  # Step B (scripts/testing/aqos-vm-dogfood.sh --full) boots this VM headless
  # (-nographic) with no way to script a login over the serial console. This
  # oneshot prints a single, greppable line to /dev/console once multi-user
  # boot is reached, proving (a) the golden profile actually boots and (b) a
  # golden-profile package (hyperfine) is really installed and on PATH — not
  # just present in the evaluated config (which Step A already checks).
  systemd.services.aqos-vm-dogfood-marker = {
    description = "AQOS VM dogfood boot marker (scripts/testing/aqos-vm-dogfood.sh)";
    wantedBy = [ "multi-user.target" ];
    after = [ "multi-user.target" ];
    serviceConfig.Type = "oneshot";
    script = ''
      # systemd services get a minimal PATH that excludes /run/current-system/sw/bin
      # (where systemPackages install), so check the system-profile path directly —
      # that is exactly where the golden aqos-workstation profile puts hyperfine.
      marker="MISSING"
      if [ -x /run/current-system/sw/bin/hyperfine ]; then marker="hyperfine-ok"; fi
      echo "AQOS-VM-DOGFOOD-BOOT-OK golden_marker=$marker" > /dev/console 2>/dev/null || true
    '';
  };
}
