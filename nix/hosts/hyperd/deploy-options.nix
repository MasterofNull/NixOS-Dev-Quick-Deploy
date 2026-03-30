{ lib, config, ... }:
{
  config = lib.mkIf (config.mySystem.profile == "ai-dev") {
    # Keep ai-dev self-contained for flake evaluations done outside
    # nixos-quick-deploy. deploy-options.local.nix is gitignored, so direct
    # `nixos-rebuild --flake` and deploy preflight must not rely on it for
    # enabling secrets or selecting the host secret bundle.
    mySystem.secrets.enable = lib.mkDefault true;
    mySystem.secrets.sopsFile =
      lib.mkDefault "/home/${config.mySystem.primaryUser}/.local/share/nixos-quick-deploy/secrets/${config.mySystem.hostName}/secrets.sops.yaml";
    mySystem.secrets.ageKeyFile =
      lib.mkDefault "/home/${config.mySystem.primaryUser}/.config/sops/age/keys.txt";

    # Keep unattended deploy/restart loops in tracked flake config. The
    # gitignored deploy-options.local.nix is not visible to pure flake evals.
    security.sudo.extraRules = lib.mkAfter [
      {
        users = [ config.mySystem.primaryUser ];
        commands = [
          {
            command = "/home/${config.mySystem.primaryUser}/Documents/NixOS-Dev-Quick-Deploy/nixos-quick-deploy.sh";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/nixos-rebuild";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/systemctl";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/journalctl";
            options = [ "NOPASSWD" ];
          }
          {
            command = "/run/current-system/sw/bin/flatpak";
            options = [ "NOPASSWD" ];
          }
        ];
      }
    ];
  };
}
