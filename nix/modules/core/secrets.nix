{ lib, config, ... }:
let
  cfg = config.mySystem;
  sec = cfg.secrets;
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
      secrets = {
        "${sec.names.aidbApiKey}" = { mode = "0400"; owner = secretsOwner; group = secretsGroup; };
        "${sec.names.hybridApiKey}" = { mode = "0400"; owner = secretsOwner; group = secretsGroup; };
        "${sec.names.embeddingsApiKey}" = { mode = "0400"; owner = secretsOwner; group = secretsGroup; };
        "${sec.names.postgresPassword}" = { mode = "0400"; owner = secretsOwner; group = secretsGroup; };
        "${sec.names.redisPassword}" = { mode = "0400"; owner = secretsOwner; group = secretsGroup; };
        "${sec.names.aiderWrapperApiKey}" = { mode = "0400"; owner = secretsOwner; group = secretsGroup; };
      };
    };
  };
}
