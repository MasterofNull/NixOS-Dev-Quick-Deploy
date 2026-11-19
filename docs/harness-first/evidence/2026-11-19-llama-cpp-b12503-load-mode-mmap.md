# llama-cpp b12503: force --load-mode mmap (device lost on Renoir iGPU)

Date: 2026-11-19 · Lane: Simurg@claude/opus-5.5 · Host: hyperd (Ryzen 7 PRO 5850U, RADV Renoir, 4 GB VRAM + 13.9 GB GTT)

## Symptom
After the gen-955 switch (b9222 -> b12503 from #806) every llama-cpp start fails while loading
`active.gguf` (Qwen3.6-35B-A3B UD-Q4_K_XL, 21.3 GiB). This happened on kernel 7.3.3 (before
reboot) and on 7.3.4 (after reboot):

    radv/amdgpu: Not enough memory for command submission.
    E ggml_vulkan: device lost on Vulkan0
    kernel: amdgpu ... amdgpu_vm_validate() failed

## Root cause (side instance :18096, same binary and flags, --verbose)
- b12503 reports the iGPU as one 18036 MiB device (VRAM + GTT). `-fit` projects 6533 MiB of use and
  makes no changes.
- `--load-mode auto` (new default, replaces --mmap/--mlock) resolves to `none` because the device
  reports no mmap support. The 30 CPU layers are then allocated as a pinned **Vulkan_Host model
  buffer of 15581.72 MiB**, on top of the Vulkan0 buffer of 6203.05 MiB. That is about 21.8 GB of
  GPU-mapped memory against a 13.9 GB GTT limit, so command submission fails and the device is lost.
- #806 checked b12503 only with the embedder on :8089, which fits on the device and never needs a
  host buffer.

## Fix
`nix/modules/roles/ai-stack.nix`: always pass `--load-mode mmap` (or `mmap+mlock` when
`llamaCpp.mlock = true`). This restores the always-mmap default of older builds. It also replaces
`--mlock`, which b12503 rejects (`error: invalid argument: --mlock`). The option defaults to false,
so that break was latent.

## Validation (side instance, before deploy)
| run | flags | result |
|---|---|---|
| live | live 8080 flags | Vulkan_Host 15581 MiB -> device lost (reproduced) |
| mmap | live flags + `--load-mode mmap` | CPU_Mapped 15581 MiB + Vulkan0 6203 MiB, MTP draft ctx up, `listening` |
| gen | same as mmap + 1 chat completion | correct answer, draft accepted 16/16, GTT 3.3 GB, 0 device-lost |

The cold-cache speed on a 25-token reply was 3.4 tok/s, which is not comparable with the
5.3 tok/s baseline. The warm comparison happens after deploy.

The built unit (`nix build ...systemd.units."llama-cpp.service".unit`) contains `llama-cpp-12503`,
`--load-mode mmap` and `--n-gpu-layers 12`.

## Activation (Rule 15)
- Integrated: the ExecStart of the existing llama-cpp unit. No new option.
- ON: at the next hyperd rebuild (`aq-deploy-current`). The package is unchanged, so nothing compiles.
- Validated live: pending. Check `curl :8080/health`, `aq-qa 0`, and warm tok/s against the 5.3 baseline.
- Observable: the journal shows `load_mode = mmap`. `/metrics` on :8080 is unchanged.
- Intervenable: revert this commit, or set `llamaCpp.useFallback = true` (b9222).
