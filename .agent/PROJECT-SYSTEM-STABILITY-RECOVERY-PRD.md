# PROJECT — System Stability Recovery

## Problem
The latest two rebuild/switch cycles introduced instability on AMD hardware. The strongest observed failure chain is native ROCm auto-selection on an AMD APU host, followed by llama.cpp ROCm startup, GPU hangs, and amdgpu resets. Post-switch validation currently reports failures non-fatally, so unsafe generations can still be treated as successful.

## Goal
Restore a stable, hardware-agnostic default path now, then harden rebuild/switch automation so future generations prefer the newest safe backend and packages for each hardware class rather than blindly selecting the newest available option.

## Scope
### In scope for first slice
- Restore AMD automatic acceleration selection to the repo-wide safe default.
- Keep ROCm available as an explicit/advanced path, not the default for generic AMD systems.
- Add regression coverage so runtime policy cannot drift away from the hardware abstraction/profile policy unnoticed.

### Out of scope for first slice
- Full automatic rollback implementation.
- Kernel track policy redesign.
- Service-specific fixes unrelated to the confirmed GPU regression chain.

## Constraints
- Prefer declarative Nix changes over imperative runtime workarounds.
- Remain hardware-agnostic across AMD, NVIDIA, Intel, and non-GPU systems.
- Preserve a path for future optimized ROCm selection on explicitly supported hardware classes.
- Avoid destructive git actions and keep unrelated worktree changes untouched.

## Acceptance Criteria
1. AMD `auto` acceleration resolves to Vulkan again in the live AI stack module path.
2. Runtime behavior, hardware abstraction library, and hardware profile data all agree on the AMD default.
3. A focused validation check fails if the AI stack runtime path drifts away from the abstraction/profile policy.
4. Existing evaluation/validation gates pass for the touched slice.

## Security Requirements
- No new hardcoded secrets, ports, or URLs.
- No privilege expansion.
- Preserve current service sandboxing posture.

## Rollback
Revert the stabilization commit to restore the previous module behavior if needed; no data migration is involved.
