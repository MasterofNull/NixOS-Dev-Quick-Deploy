# rtk — Rust Token Killer
# Pre-built static musl binary. CLI proxy that compresses shell command outputs
# before they enter the LLM context window. 60-90% token reduction, <10ms overhead.
#
# Source: https://github.com/rtk-ai/rtk
# License: MIT
#
# HOW TO UPDATE:
#   1. Set version to the new release tag (without 'v' prefix).
#   2. Run:
#        nix-prefetch-url \
#          https://github.com/rtk-ai/rtk/releases/download/v<VERSION>/rtk-x86_64-unknown-linux-musl.tar.gz
#   3. Replace the hash below with the output.
#
# NOTE: Do NOT use `cargo install rtk` — that installs "Rust Type Kit" (a different
# project that shares the crate name). Always use the GitHub binary release.
{
  lib,
  stdenv,
  fetchurl,
  autoPatchelfHook,
}:
stdenv.mkDerivation rec {
  pname = "rtk";
  version = "0.42.3";

  src = fetchurl {
    url = "https://github.com/rtk-ai/rtk/releases/download/v${version}/rtk-x86_64-unknown-linux-musl.tar.gz";
    hash = "sha256-XfdkpjNwnLhdJIJY0IXSTslfqovKDmg1qTzVfK3E654=";
  };

  nativeBuildInputs = [ autoPatchelfHook ];

  # musl static binary — tarball contains a bare 'rtk' file with no top-level directory.
  # Standard unpackPhase fails on no-directory tarballs; skip it and unpack manually.
  dontUnpack = true;
  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/bin
    tar xf $src
    install -Dm755 rtk $out/bin/rtk
    runHook postInstall
  '';

  meta = with lib; {
    description = "CLI proxy that reduces LLM token consumption 60-90% on common dev commands";
    homepage = "https://github.com/rtk-ai/rtk";
    license = licenses.mit;
    platforms = [ "x86_64-linux" ];
    mainProgram = "rtk";
  };
}
