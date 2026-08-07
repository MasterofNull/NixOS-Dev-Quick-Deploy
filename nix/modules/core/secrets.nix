{
  lib,
  config,
  ...
}: let
  cfg = config.mySystem;
  sec = cfg.secrets;
  swb = cfg.aiStack.switchboard;
  secretsGroup = lib.attrByPath ["users" "users" cfg.primaryUser "group"] "users" config;
  # External string paths (for strict zero-secrets-in-repo) cannot be
  # reliably validated at flake evaluation time. Validate only when this is
  # a Nix path literal; otherwise defer existence checks to deploy/bootstrap.
  secretsFileExists =
    if builtins.typeOf sec.sopsFile == "path"
    then builtins.pathExists sec.sopsFile
    else true;
  repoLocalSopsPath = builtins.match ".*/nix/hosts/[^/]+/secrets\\.sops\\.ya?ml$" sec.sopsFile != null;
  needsRemoteLlmSecret = swb.enable && swb.remoteUrl != null && swb.remoteApiKeyFile == null;
  needsCrowdsecSecret = cfg.security.crowdsec.enable && cfg.security.crowdsec.enableFirewallBouncer;
  # ALA rev4 — the asymmetric-lease private key is owned by the dedicated aq-lease-signing-authority
  # user, which only exists when the service is enabled. Gate the secret on the same flag so hosts
  # with the ai-stack secrets block but ALA off never chown to a missing user (activation failure).
  needsAlaSecret = cfg.aiStack.leaseSigningAuthority.enable;
  # C2-SCI B2 — the scheduler-lease-context issuer's OWN Ed25519 private signing key is owned by
  # the dedicated aq-c2-scheduler-context-issuer user, which only exists when the service is
  # enabled. Gate the secret on the same flag so hosts with the ai-stack secrets block but this
  # service off never chown to a missing user (activation failure). Distinct key family + distinct
  # user from needsAlaSecret above (that key authenticates the presented admission lease; this key
  # signs the minted scheduler-context).
  needsC2SciSecret = cfg.aiStack.c2SchedulerContextIssuer.enable;
in {
  config = lib.mkIf sec.enable {
    assertions = [
      {
        assertion = secretsFileExists;
        message = "mySystem.secrets.enable=true but mySystem.secrets.sopsFile does not exist: ${sec.sopsFile}";
      }
      {
        assertion = sec.allowRepoLocalSopsFile || (!repoLocalSopsPath);
        message = ''
          mySystem.secrets.sopsFile points to a repo-local path (${sec.sopsFile}).
          For strict zero-secrets-in-repo, use an external path and keep
          mySystem.secrets.allowRepoLocalSopsFile = false.
        '';
      }
    ];

    sops = {
      defaultSopsFile = sec.sopsFile;
      defaultSopsFormat = "yaml";
      age.keyFile = sec.ageKeyFile;
      # Support strict zero-secrets-in-repo by allowing external secrets files
      # (outside the Nix store).
      validateSopsFiles = false;

      # Expose runtime-decrypted secrets in /run/secrets/*.
      # Services consume these paths via *_FILE environment variables or
      # systemd LoadCredential= to avoid plaintext values in unit env blocks.
      #
      # Phase 36.4.1 — Identity segmentation: secrets are owned by root:ai-stack
      # with 0440 permissions, allowing service-scoped users in the ai-stack
      # group to read them while isolating them from the primary user.
      secrets = let
        aiGroup = "ai-stack";
        aiSvcOwner = "root";
        aiSvcGroup =
          if cfg.roles.aiStack.enable
          then aiGroup
          else secretsGroup;
        aiSvcMode =
          if cfg.roles.aiStack.enable
          then "0440"
          else "0400";
      in
        {
          # Foundation C — capability-lease HMAC signing key (C2 tool-lease
          # enforcement). Decrypts to /run/secrets/aq-lease-signing-key, which
          # capability_lease.resolve_key() reads. WITHOUT it, resolve_key falls
          # back to the DEV key and the gate degrades to safe-read (denying
          # privileged first-party tools like run_command/write_file). root:ai-stack
          # 0440 → readable by the switchboard service user (in the ai-stack group).
          "aq-lease-signing-key" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          # Foundation C — C3b R5 execution-grant Ed25519 PRIVATE signing key
          # (default-OFF CAPABILITY_CELL_ADAPTER shadow attach point).
          # Decrypts to /run/secrets/aq-grant-signing-key, read by
          # ai-stack/switchboard/execution_cell_adapter.py::load_signing_key().
          # WITHOUT it, load_signing_key() returns None and the adapter mints
          # NO grant (authority-degrade deny — never an unsigned/fallback
          # grant). The corresponding PUBLIC key is a non-secret tracked
          # value at config/grant-signing-public-key, loaded by the R3
          # runner. root:ai-stack 0440 → readable by the switchboard service
          # user (in the ai-stack group), mirrors aq-lease-signing-key.
          "aq-grant-signing-key" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          "${sec.names.aidbApiKey}" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          "${sec.names.hybridApiKey}" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          "${sec.names.embeddingsApiKey}" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          "${sec.names.postgresPassword}" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          "${sec.names.redisPassword}" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          "${sec.names.aiderWrapperApiKey}" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
          "${sec.names.githubMcpToken}" = {
            mode = "0440";
            owner = "root";
            group = secretsGroup;
          };
        }
        // lib.optionalAttrs needsRemoteLlmSecret {
          "${sec.names.remoteLlmApiKey}" = {
            mode = aiSvcMode;
            owner = aiSvcOwner;
            group = aiSvcGroup;
          };
        }
        // lib.optionalAttrs needsCrowdsecSecret {
          "${sec.names.crowdsecBouncerApiKey}" = {
            mode = "0400";
            owner = "root";
            group = "root";
          };
        }
        // lib.optionalAttrs needsAlaSecret {
          # Foundation C — ALA rev4 asymmetric-lease Ed25519 PRIVATE signing key. Decrypts to
          # /run/secrets/lease-signing-ed25519-private-key, read ONLY by the confined
          # aq-lease-signing-authority service (lease_signing_authority.py). WITHOUT it the service
          # fail-closes (signer-unavailable) and, with CAPABILITY_ASYMMETRIC_LEASE=1, the gate denies
          # ALL first-party leases (fail-closed, never HMAC fallback). 0400, owned by the dedicated
          # aq-lease-signing-authority user (NOT the ai-stack group) — the switchboard/owner uid must
          # never hold this private key (verify != forge). The matching PUBLIC key is the non-secret
          # tracked value in config/aqos/lease-signer-keys.json.
          "lease-signing-ed25519-private-key" = {
            mode = "0400";
            owner = "aq-lease-signing-authority";
            group = "aq-lease-signing-authority";
          };
        }
        // lib.optionalAttrs needsC2SciSecret {
          # Foundation C — C2-SCI B2 scheduler-lease-context issuer's OWN Ed25519 PRIVATE signing
          # key. Decrypts to /run/secrets/c6-scheduler-context-signing-key, read ONLY by the
          # confined aq-c2-scheduler-context-issuer service (scheduler_context_transport.py's
          # env-driven __main__). WITHOUT it the service fail-closes (signer-unavailable) and mints
          # no scheduler-context regardless of how many valid admission leases are presented. 0400,
          # owned by the dedicated aq-c2-scheduler-context-issuer user (NOT the ai-stack group, NOT
          # aq-lease-signing-authority) — the switchboard/owner uid and the ALA lease-signer must
          # never hold this private key. The matching PUBLIC key is the non-secret tracked value in
          # config/aqos/c6-scheduler-signer-keys.json (a DISTINCT key family from
          # config/aqos/lease-signer-keys.json, which this service reads read-only to verify the
          # PRESENTED admission lease — never to sign anything).
          "c6-scheduler-context-signing-key" = {
            mode = "0400";
            owner = "aq-c2-scheduler-context-issuer";
            group = "aq-c2-scheduler-context-issuer";
          };
        };
    };
  };
}
