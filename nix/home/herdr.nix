# AQ-OS Herdr H1: package/config/facade only.  Runtime is structurally inert.
{ config, lib, pkgs, ... }:
with lib; let
  cfg = config.programs.aqHerdr;
  herdr = pkgs.callPackage ../pkgs/herdr.nix {};
  facade = pkgs.writeShellApplication {
    name = "aq-herdr";
    runtimeInputs = [pkgs.coreutils];
    text = builtins.readFile ../../scripts/ai/aq-herdr;
  };
in {
  options.programs.aqHerdr = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = "Install the immutable safe config and read-only AQ facade for the H1 source-pinned Herdr build. The raw binary is not exposed in the shared user profile.";
    };
    runtimeEnable = mkOption {
      type = types.bool;
      default = false;
      description = "Reserved for a separately authorized runtime slice; H1 rejects true.";
    };
  };

  config = mkMerge [
    {
      assertions = [{
        assertion = !cfg.runtimeEnable;
        message = "AQ-OS Herdr H1 boundary: programs.aqHerdr.runtimeEnable must remain false; runtime activation requires a later owner-authorized slice.";
      }];
    }
    (mkIf cfg.enable {
      # Keep the raw upstream CLI out of the shared user PATH.  The passthru
      # binds the evaluated build identity without adding the binary to the
      # facade runtime closure; execution is reserved for a future host-owned
      # adapter boundary.
      home.packages = [
        (facade.overrideAttrs (old: {
          passthru = (old.passthru or {}) // {
            herdrBuild = herdr;
            herdrRevision = "ef4c23f5775bb8cfec05f05d0844226ff959a07a";
          };
        }))
      ];
      xdg.configFile."herdr/config.toml".text = ''
        onboarding = false
        [update]
        version_check = false
        manifest_check = false
        [session]
        resume_agents_on_restore = false
        [remote]
        manage_ssh_config = false
        [experimental]
        allow_nested = false
        pane_history = false
      '';
      # These are user-owned presentation paths only. Activation creates no
      # socket, unit, pane, process, server, or login trigger.
      home.activation.aqHerdrPrivateDirectories = lib.hm.dag.entryAfter ["writeBoundary"] ''
        $DRY_RUN_CMD ${pkgs.coreutils}/bin/install -d -m 0700 "$HOME/.config/herdr" "$HOME/.local/state/herdr"
      '';
    })
  ];
}
