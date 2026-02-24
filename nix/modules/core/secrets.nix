{ lib, config, ... }:
let
  cfg = config.mySystem;
  sec = cfg.secrets;
  secretsFileExists = builtins.pathExists sec.sopsFile;
in
{
  config = lib.mkIf sec.enable {
    assertions = [
      {
        assertion = secretsFileExists;
        message = "mySystem.secrets.enable=true but mySystem.secrets.sopsFile does not exist: ${sec.sopsFile}";
      }
    ];

    sops = {
      defaultSopsFile = sec.sopsFile;
      defaultSopsFormat = "yaml";
      age.keyFile = sec.ageKeyFile;

      # Expose runtime-decrypted secrets in /run/secrets/*.
      # Services consume these paths via *_FILE environment variables or
      # systemd LoadCredential= to avoid plaintext values in unit env blocks.
      secrets = {
        "${sec.names.aidbApiKey}" = { mode = "0400"; };
        "${sec.names.hybridApiKey}" = { mode = "0400"; };
        "${sec.names.embeddingsApiKey}" = { mode = "0400"; };
        "${sec.names.postgresPassword}" = { mode = "0400"; };
        "${sec.names.redisPassword}" = { mode = "0400"; };
      };
    };
  };
}
