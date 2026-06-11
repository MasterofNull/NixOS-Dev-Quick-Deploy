# lean-ctx (LeanCTX) — context intelligence MCP server for AI agents
# Rust binary providing 62 MCP tools, 10 file read modes (signatures, map,
# lines:N-M, density, diff …), session memory, and up to 99% token savings
# for agentic file access.
#
# Source: https://github.com/yvgude/lean-ctx
# Crate:  https://crates.io/crates/lean-ctx
# License: Apache 2.0
#
# HOW TO COMPUTE HASHES after updating version:
#   src.hash:    nix-prefetch-github --owner yvgude --repo lean-ctx --rev v<VERSION>
#   cargoHash:   set to lib.fakeHash, run nixos-rebuild, copy the hash from the error
#
# ACTIVATION (run once per user after install):
#   lean-ctx init --agent claude    # registers MCP in ~/.claude.json + installs rules
#   lean-ctx setup                  # one-shot shell + editor + verification setup
{
  lib,
  rustPlatform,
  fetchFromGitHub,
  pkg-config,
  openssl,
}:
rustPlatform.buildRustPackage rec {
  pname = "lean-ctx";
  version = "3.3.7";

  src = fetchFromGitHub {
    owner = "yvgude";
    repo = "lean-ctx";
    rev = "v${version}";
    # TODO: replace with real hash:
    #   nix-prefetch-github --owner yvgude --repo lean-ctx --rev v3.3.7
    hash = lib.fakeHash;
  };

  # TODO: replace with real vendor hash from failed build output
  cargoHash = lib.fakeHash;

  nativeBuildInputs = [ pkg-config ];
  buildInputs = [ openssl ];

  # lean-ctx has its own integration tests that require a live filesystem;
  # skip during Nix sandbox build.
  doCheck = false;

  meta = with lib; {
    description = "Context intelligence MCP server: 62 tools, 10 read modes, session memory, 60-90% token savings";
    homepage = "https://github.com/yvgude/lean-ctx";
    license = licenses.asl20;
    platforms = platforms.linux ++ platforms.darwin;
    mainProgram = "lean-ctx";
  };
}
