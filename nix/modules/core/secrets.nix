{ lib, config, ... }:
let
  cfg = config.mySystem;
  sec = cfg.secrets;
  swb = cfg.aiStack.switchboard;
  secretsOwner = cfg.primaryUser;
  secretsGroup = lib.attrByPath [ "users" "users" cfg.primaryUser "group" ] "users" config;
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
in
{
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
        aiSvcGroup = if cfg.roles.aiStack.enable then aiGroup else secretsGroup;
        aiSvcMode = if cfg.roles.aiStack.enable then "0440" else "0400";
      in {
        "${sec.names.aidbApiKey}" = { mode = aiSvcMode; owner = aiSvcOwner; group = aiSvcGroup; };
        "${sec.names.hybridApiKey}" = { mode = aiSvcMode; owner = aiSvcOwner; group = aiSvcGroup; };
        "${sec.names.embeddingsApiKey}" = { mode = aiSvcMode; owner = aiSvcOwner; group = aiSvcGroup; };
        "${sec.names.postgresPassword}" = { mode = aiSvcMode; owner = aiSvcOwner; group = aiSvcGroup; };
        "${sec.names.redisPassword}" = { mode = aiSvcMode; owner = aiSvcOwner; group = aiSvcGroup; };
        "${sec.names.aiderWrapperApiKey}" = { mode = aiSvcMode; owner = aiSvcOwner; group = aiSvcGroup; };
      } // lib.optionalAttrs needsRemoteLlmSecret {
        "${sec.names.remoteLlmApiKey}" = { mode = aiSvcMode; owner = aiSvcOwner; group = aiSvcGroup; };
      } // lib.optionalAttrs needsCrowdsecSecret {
        "${sec.names.crowdsecBouncerApiKey}" = { mode = "0400"; owner = "root"; group = "root"; };
      };
    };
  };
}
