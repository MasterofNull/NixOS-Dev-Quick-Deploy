# Herdr v0.7.5 — source-pinned H1 package only. No upstream flake input.
{ lib, pkgs }:
let
  src = builtins.fetchTree {
    type = "github";
    owner = "herdrdev";
    repo = "herdr";
    rev = "ef4c23f5775bb8cfec05f05d0844226ff959a07a";
    narHash = "sha256-3BA8eredGku+vsL2Af7sUf43QiArR5XTHNrI+X11vFM=";
  };
  licenseHash = builtins.hashFile "sha256" (src + "/LICENSE");
  cargoLockHash = builtins.hashFile "sha256" (src + "/Cargo.lock");
  upstream = pkgs.callPackage (src + "/nix/package.nix") {};
in
assert licenseHash == "a7fa24f74382fb3e4d320a608533a7c2999dbc0f780f1f734c8b891b31f0d9bd";
assert cargoLockHash == "4d590b4abf9d6088704ae7ab9811c8bb766286ec75ca63364c7e23cb14be6ecf";
upstream.overrideAttrs (old: {
  # The upstream expression imports its own source-relative, vendored Zig
  # dependency expression.  Reusing it keeps the exact Cargo/Zig closure
  # instead of silently copying a generated dependency file into AQ-OS.
  meta = (old.meta or {}) // {
    description = "Persistent terminal workspace manager (AQ-OS H1 source-pinned package)";
    homepage = "https://github.com/herdrdev/herdr";
    license = lib.licenses.agpl3Plus;
    mainProgram = "herdr";
  };
})
