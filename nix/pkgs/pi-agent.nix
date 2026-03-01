# pi-coding-agent — declarative Nix packaging
# Source: https://github.com/badlogic/pi-mono
#
# HOW TO COMPUTE HASHES after updating version:
#   src.hash:      nix-prefetch-github --owner badlogic --repo pi-mono --rev v<VERSION>
#   npmDepsHash:   nix-shell -p prefetch-npm-deps --run \
#                    "prefetch-npm-deps <source-path>/package-lock.json"
#
# Until hashes are known, lib.fakeHash causes a build-time error that
# prints the correct hash — replace lib.fakeHash with the printed hash.
{ lib, pkgs }:

pkgs.buildNpmPackage {
  pname   = "pi-coding-agent";
  version = "0.55.3";

  src = pkgs.fetchFromGitHub {
    owner = "badlogic";
    repo  = "pi-mono";
    rev   = "v0.55.3";
    # TODO: compute with: nix-prefetch-github --owner badlogic --repo pi-mono --rev v0.55.3
    hash  = lib.fakeHash;
  };

  npmDepsHash =
    # TODO: compute with: nix-shell -p prefetch-npm-deps --run "prefetch-npm-deps package-lock.json"
    lib.fakeHash;

  # The published package is the pi-coding-agent workspace package.
  # Install only that package's bin, not workspace root scripts.
  makeCacheWritable = true;

  meta = {
    description  = "Minimal terminal coding agent with read/write/edit/bash tools";
    homepage     = "https://github.com/badlogic/pi-mono";
    license      = lib.licenses.mit;
    mainProgram  = "pi";
    maintainers  = [];
  };
}
