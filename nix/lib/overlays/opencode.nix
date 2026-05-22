/**
  OpenCode CLI overlay — provides pkgs.opencode and its build dependency
  pkgs.models-dev from the in-repo .forks/nixpkgs staging area.

  Both packages are authored by anomalyco and track the opencode project;
  they are staged locally pending upstream nixpkgs inclusion.

  Applied in nix/modules/roles/ai-stack.nix alongside the llama-cpp overlay
  so the CLI is available on all AI-stack hosts without touching base.nix.
*/
final: prev: {
  models-dev = prev.callPackage ../../pkgs/by-name/models-dev/package.nix { };

  opencode = prev.callPackage ../../pkgs/by-name/opencode/package.nix {
    models-dev = final.models-dev;
  };
}
