/**
  Phase 20.1 — llama.cpp latest version overlay with ROCm/CUDA support.

  This overlay enables tracking the latest llama.cpp releases independent of
  nixpkgs channel updates. It reads version pins from nix/pins/llama-cpp.json
  and builds llama.cpp from source with GPU acceleration enabled.

  Features:
    • Tracks latest llama.cpp releases via pinned version file
    • Preserves fallback to previous known-good version
    • Enables ROCm (AMD GPU) or CUDA (NVIDIA GPU) acceleration
    • Integrates with existing aarch64 NEON overlay
    • Updated via scripts/ai/update-llama-cpp.sh

  Configuration (via mySystem options):
    • mySystem.aiStack.llamaCpp.trackLatest = true  — use pinned latest
    • mySystem.aiStack.llamaCpp.useFallback = true  — use fallback version
    • mySystem.aiStack.llamaCpp.trackLatest = false — use nixpkgs version

  GPU Support:
    • enableRocm = true  — AMD GPU acceleration (requires rocmPackages)
    • enableCuda = false — NVIDIA GPU (requires cudaPackages)
*/
{ pinFile, useFallback ? false, enableRocm ? false, enableCuda ? false }:

final: prev:
let
  # Read the pin file
  pins = builtins.fromJSON (builtins.readFile pinFile);

  # Select current or fallback version
  selected = if useFallback then pins.fallback else pins.current;

  # Build flags to strip when applying platform-specific patches
  platformPatterns = [ "GGML_NEON" "GGML_METAL" "GGML_OPENCL" ];
  stripConflicts = flags:
    builtins.filter
      (f: builtins.all (pat: !(prev.lib.hasPrefix "-D${pat}" f)) platformPatterns)
      flags;

  # Get the base llama-cpp with GPU support enabled
  baseLlamaCpp =
    if enableRocm then
      prev.llama-cpp.override { rocmSupport = true; }
    else if enableCuda then
      prev.llama-cpp.override { cudaSupport = true; }
    else
      prev.llama-cpp;
in
{
  llama-cpp = baseLlamaCpp.overrideAttrs (oldAttrs: {
    version = selected.version;

    src = prev.fetchFromGitHub {
      owner = "ggml-org";
      repo = "llama.cpp";
      tag = selected.rev;
      hash = selected.hash;
      # Preserve commit info for version reporting
      leaveDotGit = true;
      postFetch = ''
        git -C "$out" rev-parse --short HEAD > $out/COMMIT
        find "$out" -name .git -print0 | xargs -0 rm -rf
      '';
    };

    # Preserve cmake flags from nixpkgs, allowing further overlays to patch
    cmakeFlags = stripConflicts (oldAttrs.cmakeFlags or []);

    # Add metadata for debugging/introspection
    passthru = (oldAttrs.passthru or {}) // {
      llamaCppPin = {
        version = selected.version;
        rev = selected.rev;
        date = selected.date or "unknown";
        isFallback = useFallback;
        pinFile = toString pinFile;
        rocmEnabled = enableRocm;
        cudaEnabled = enableCuda;
      };
    };

    meta = (oldAttrs.meta or {}) // {
      description = (oldAttrs.meta.description or "llama.cpp") +
        " (pinned: ${selected.rev}${if useFallback then " [fallback]" else ""}${if enableRocm then " +rocm" else ""}${if enableCuda then " +cuda" else ""})";
    };
  });
}
