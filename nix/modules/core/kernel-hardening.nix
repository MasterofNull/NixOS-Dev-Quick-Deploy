# Kernel hardening knobs selected per flake variant (mySystem.security.*).
# Defaults suit the agent-dev workstation; a computer-lab variant can choose
# `unprivilegedUserNamespaces = "restrict"` without changing this module.
{
  lib,
  config,
  ...
}: let
  sec = config.mySystem.security;
  cells = config.mySystem.aiStack.executionCellRunner.enable or false;
in {
  config = lib.mkMerge [
    (lib.mkIf sec.kernelHardening.enable {
      boot.kernel.sysctl = {
        "kernel.kptr_restrict" = lib.mkOverride 900 2;
        "kernel.dmesg_restrict" = lib.mkOverride 900 1;
      };
    })
    (lib.mkIf (sec.unprivilegedUserNamespaces == "restrict") {
      security.allowUserNamespaces = false;
      assertions = [
        {
          assertion = !cells;
          message = "mySystem.security.unprivilegedUserNamespaces = \"restrict\" disables user namespaces, which mySystem.aiStack.executionCellRunner (bubblewrap cells) requires.";
        }
      ];
    })
  ];
}
