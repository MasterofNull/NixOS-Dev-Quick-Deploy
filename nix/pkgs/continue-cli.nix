# Continue CLI — declarative Nix packaging
# Source: https://github.com/continuedev/continue
#
# The Continue CLI provides AI-powered coding assistance from the terminal.
# Packaged from npm registry for reliability.
#
# HOW TO COMPUTE HASHES after updating version:
#   src.hash:      nix-prefetch-url <tarball-url>
#   npmDepsHash:   nix-shell -p prefetch-npm-deps --run \
#                    "prefetch-npm-deps <source-path>/package-lock.json"
#
# Until hashes are known, lib.fakeHash causes a build-time error that
# prints the correct hash — replace lib.fakeHash with the printed hash.
{ lib, pkgs }:

pkgs.buildNpmPackage {
  pname   = "continue-cli";
  version = "1.5.45";

  src = pkgs.fetchurl {
    url = "https://registry.npmjs.org/@continuedev/cli/-/cli-1.5.45.tgz";
    hash  = "sha256-0wp33iakvn960y6572h62rildjlb43v5224xvg3fr1r33r5n8z4i=";
  };

  npmDepsHash = null;  # Pre-built npm package, no deps to hash

  sourceRoot = "package";

  makeCacheWritable = true;

  meta = {
    description  = "Continue CLI — AI-powered coding assistant for the terminal";
    homepage     = "https://continue.dev";
    license      = lib.licenses.asl20;
    mainProgram  = "cn";
    maintainers  = [ ];
  };
}
