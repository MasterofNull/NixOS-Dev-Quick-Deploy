# Continue CLI — declarative Nix packaging
# Source: https://github.com/continuedev/continue
#
# The Continue CLI provides AI-powered coding assistance from the terminal.
# It integrates with the Continue.dev ecosystem for context-aware code help.
#
# HOW TO COMPUTE HASHES after updating version:
#   npmDepsHash:   nix-shell -p prefetch-npm-deps --run \
#                    "prefetch-npm-deps <source-path>/package-lock.json"
#
# Until the hash is known, lib.fakeHash causes a build-time error that
# prints the correct hash — replace lib.fakeHash with the printed hash.
{ lib, pkgs }:

pkgs.buildNpmPackage {
  pname   = "continue-cli";
  version = "1.3.32";

  src = pkgs.fetchFromGitHub {
    owner = "continuedev";
    repo  = "continue";
    rev   = "v1.3.32";
    hash  = lib.fakeHash;
  };

  sourceRoot = "continue/extensions/cli";

  npmDepsHash = lib.fakeHash;

  makeCacheWritable = true;

  meta = {
    description  = "Continue CLI — AI-powered coding assistant for the terminal";
    homepage     = "https://continue.dev";
    license      = lib.licenses.asl20;
    mainProgram  = "cn";
    maintainers  = [ ];
  };
}
