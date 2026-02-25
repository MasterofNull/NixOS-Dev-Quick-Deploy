{ lib, config, ... }:
let
  cfg = config.mySystem.compliance.hospitalClassified;
in
{
  options.mySystem.compliance.hospitalClassified = {
    enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable declarative hospital/classified posture assertions.";
    };

    enforceNoRollingTags = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Deprecated; retained for compatibility with prior option sets.";
    };

    enforceNoUnapprovedHostNetwork = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Deprecated; retained for compatibility with prior option sets.";
    };
  };

  config = lib.mkIf cfg.enable {
    networking.firewall.enable = lib.mkDefault true;
    mySystem.logging.audit.enable = lib.mkDefault true;
    mySystem.logging.audit.immutableRules = lib.mkDefault true;
    mySystem.aiStack.listenOnLan = lib.mkDefault false;

    assertions = [
      {
        assertion = config.mySystem.logging.audit.enable;
        message = "Hospital/classified posture requires mySystem.logging.audit.enable=true";
      }
      {
        assertion = config.mySystem.logging.audit.immutableRules;
        message = "Hospital/classified posture requires mySystem.logging.audit.immutableRules=true";
      }
      {
        assertion = !(config.mySystem.aiStack.listenOnLan or false);
        message = "Hospital/classified posture requires mySystem.aiStack.listenOnLan=false";
      }
      {
        assertion = config.mySystem.aiStack.llamaCpp.host == "127.0.0.1";
        message = "Hospital/classified posture requires mySystem.aiStack.llamaCpp.host=127.0.0.1";
      }
    ];
  };
}
