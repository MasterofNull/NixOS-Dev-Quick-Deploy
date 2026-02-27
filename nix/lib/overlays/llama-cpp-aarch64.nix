/**
  Phase 16.5.1 — aarch64 cmake flag overlay for llama.cpp.

  On aarch64 platforms (Raspberry Pi, Apple M*, Rockchip, etc.) the nixpkgs
  llama-cpp default build does not enable NEON SIMD intrinsics, resulting in
  scalar-only inference that is 3-5× slower than the optimised path.

  This overlay:
    • Forces GGML_NEON=ON   — ARM NEON SIMD (required for fast inference)
    • Forces GGML_METAL=OFF — Metal is macOS-only; causes link failure on Linux
    • Forces GGML_OPENCL=OFF — OpenCL not needed when NEON is active; avoids
                               pulling in ocl-icd and clang-opencl on SBCs

  Usage (in a NixOS module or flake):
    nixpkgs.overlays = lib.optional pkgs.stdenv.hostPlatform.isAarch64
      (import ../../nix/lib/overlays/llama-cpp-aarch64.nix);
*/
final: prev:
let
  # Flags that must be removed before adding the new values.
  aarch64Patterns = [ "GGML_NEON" "GGML_METAL" "GGML_OPENCL" ];
  stripConflicts = flags:
    builtins.filter
      (f: builtins.all (pat: !(prev.lib.hasPrefix "-D${pat}" f)) aarch64Patterns)
      flags;
in
{
  llama-cpp = prev.llama-cpp.overrideAttrs (old: {
    cmakeFlags =
      (stripConflicts (old.cmakeFlags or []))
      ++ [
        "-DGGML_NEON=ON"
        "-DGGML_METAL=OFF"
        "-DGGML_OPENCL=OFF"
      ];
  });
}
