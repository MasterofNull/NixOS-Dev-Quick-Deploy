# PROJECT ROCM TARGET AUTOMATION PRD

## Goal
Make ROCm-backed llama.cpp builds host-aware so future builds compile only the relevant AMD GPU target(s) instead of the full supported architecture matrix.

## Problem
The llama.cpp overlay currently enables ROCm support without passing a target selector, so upstream build logic compiles many HIP architectures. This makes rebuilds unnecessarily expensive after package refreshes.

## Recommended direction
- Add a declarative hardware fact for the discovered ROCm GPU target.
- Teach hardware discovery to populate that fact from `rocminfo` when available.
- Derive a build target from `mySystem.aiStack.rocmGfxOverride` when a host needs an unsupported-GPU compatibility override.
- Pass the selected target list into the llama.cpp overlay as `GPU_TARGETS` when ROCm is enabled.

## Acceptance criteria
- Hosts can declare or auto-discover `mySystem.hardware.rocmGpuTarget`.
- A host with `rocmGfxOverride = "9.0.0"` derives `gfx900` when no explicit target fact is present.
- The llama.cpp derivation receives `-DGPU_TARGETS=gfx...` for ROCm builds with a known target.
- Existing non-ROCm and unknown-target builds continue to work.
- Targeted validation and flake evaluation pass.
