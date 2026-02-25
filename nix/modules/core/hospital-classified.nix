{ lib, config, ... }:
let
  cfg = config.mySystem.compliance.hospitalClassified;
  manifestRoot = cfg.kubernetes.manifestRoot;

  excludedSubpaths = lib.unique ([ "deprecated" ] ++ cfg.kubernetes.excludedSubpaths);

  pathIsExcluded = path:
    builtins.any (segment: lib.hasInfix "/${segment}/" "${path}/") excludedSubpaths;

  listYamlFiles = dir:
    let
      entries = builtins.readDir dir;
      names = builtins.attrNames entries;
      collect = name:
        let
          path = "${dir}/${name}";
          entryType = entries.${name};
        in
        if entryType == "directory" then
          if builtins.elem name excludedSubpaths then [ ] else listYamlFiles path
        else if entryType == "regular" && (lib.hasSuffix ".yaml" name || lib.hasSuffix ".yml" name) then
          if pathIsExcluded path then [ ] else [ path ]
        else
          [ ];
    in
    lib.concatLists (map collect names);

  yamlFiles = if builtins.pathExists manifestRoot then listYamlFiles manifestRoot else [ ];

  fileLines = path: lib.splitString "\n" (builtins.readFile path);

  hasRollingTag = path:
    builtins.any
      (line: lib.hasInfix "image:" line && (lib.hasInfix ":latest" line || lib.hasInfix ":main" line))
      (fileLines path);

  hasHostNetwork = path:
    builtins.any (line: lib.hasInfix "hostNetwork:" line && lib.hasInfix "true" line) (fileLines path)
    || builtins.any (line: lib.hasInfix "hostPort:" line) (fileLines path);

  relPath = path: lib.removePrefix "${manifestRoot}/" path;

  rollingTagFiles = builtins.filter hasRollingTag yamlFiles;

  unapprovedHostNetworkFiles =
    let
      allowed = lib.unique cfg.kubernetes.allowedHostNetworkManifestPaths;
    in
    builtins.filter
      (path:
        let rel = relPath path;
        in hasHostNetwork path && !(builtins.elem rel allowed))
      yamlFiles;
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
      description = "Fail evaluation if any active Kubernetes manifest uses :latest or :main image tags.";
    };

    enforceNoUnapprovedHostNetwork = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Fail evaluation if hostNetwork/hostPort is used without explicit allowlist entry.";
    };

    kubernetes = {
      manifestRoot = lib.mkOption {
        type = lib.types.path;
        default = builtins.toPath "${toString ../../..}/ai-stack/kubernetes";
        description = "Path to active Kubernetes manifests evaluated by declarative compliance assertions.";
      };

      excludedSubpaths = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ "mlops" ];
        description = "Manifest subpaths excluded from posture assertions when not part of active runtime.";
      };

      allowedHostNetworkManifestPaths = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        example = [ "kompose/container-engine-deployment.yaml" ];
        description = "Relative paths from manifestRoot allowed to use hostNetwork/hostPort temporarily.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    networking.firewall.enable = lib.mkDefault true;
    mySystem.logging.audit.enable = lib.mkDefault true;
    mySystem.logging.audit.immutableRules = lib.mkDefault true;
    mySystem.aiStack.listenOnLan = lib.mkDefault false;

    assertions = [
      {
        assertion = builtins.pathExists manifestRoot;
        message = "Hospital/classified posture enabled but Kubernetes manifest root is missing: ${toString manifestRoot}";
      }
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
      {
        assertion = !cfg.enforceNoRollingTags || rollingTagFiles == [ ];
        message = "Disallowed rolling image tags detected in active manifests: ${lib.concatStringsSep ", " (map relPath rollingTagFiles)}";
      }
      {
        assertion = !cfg.enforceNoUnapprovedHostNetwork || unapprovedHostNetworkFiles == [ ];
        message = "Unapproved hostNetwork/hostPort usage detected: ${lib.concatStringsSep ", " (map relPath unapprovedHostNetworkFiles)}";
      }
    ];
  };
}
