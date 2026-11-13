# harness-contracts — Rust contract validator and owned-path scope gate
# (crates/contract-validator). Used by tier0.d/check-owned-scope.sh, which
# fails closed when this binary is unavailable.
{
  lib,
  rustPlatform,
}:
rustPlatform.buildRustPackage {
  pname = "harness-contracts";
  version = "0.1.0";

  src = lib.fileset.toSource {
    root = ../..;
    fileset = lib.fileset.unions [
      ../../Cargo.toml
      ../../Cargo.lock
      ../../crates
    ];
  };

  cargoLock.lockFile = ../../Cargo.lock;

  # Tests read the live repo tree and git history, which the sandbox lacks;
  # CI (.github/workflows/rust.yml) runs them.
  doCheck = false;

  meta.mainProgram = "harness-contracts";
}
