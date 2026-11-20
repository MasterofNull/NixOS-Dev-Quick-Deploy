# llama-cpp b12503: force --load-mode mmap (device lost on Renoir iGPU)

Date: 2026-11-19 · Lane: Simurg@claude/opus-5.5 · Host: hyperd (Ryzen 7 PRO 5850U, RADV Renoir, 4 GB VRAM + 13.9 GB GTT)

## Objective
Restore the local llama-cpp service on llama.cpp b12503. Owner directive: progress forward on the new
build, no pin revert. Since the gen-955 switch (b9222 -> b12503 from #806), every start fails while
loading `active.gguf` (Qwen3.6-35B-A3B UD-Q4_K_XL, 21.3 GiB). It fails the same way on kernel 7.3.3
(before reboot) and on 7.3.4 (after reboot):

    radv/amdgpu: Not enough memory for command submission.
    E ggml_vulkan: device lost on Vulkan0
    kernel: amdgpu ... amdgpu_vm_validate() failed

Owner directive in the same cycle: agents read upstream release notes on every version change before
a rebuild. That is now in canon `dependency-hygiene`.

## Workflow/Session IDs
- Claude Code background session 0b56dbd9 (Simurg@claude/opus-5.5), worktree `llama-cpp-fallback-b9222`, branch `fix/llama-cpp-load-mode-mmap`, PR #841.
- Backlog: `LLAMA-VULKAN-DEVICE-LOST-ON-SWITCH` in `.agent/memory/issues-backlog.md`.

## Delegation Decision
Done by the orchestrator. The diagnosis needed the live GPU, the running service's 5-minute retry
window, and side-instance bisection with the 21 GB model on this host. That host-bound live
debugging does not fit a headless delegate. The code change is one ExecStart flag. Rule 17 deviation
recorded here.

## Commands Executed
- `journalctl -u llama-cpp -b -1` / `-b`: device lost on every b12503 start; b9222 ran for days before the switch.
- Side instance (same binary `llama-cpp-12503`, live 8080 flags, `--verbose`, port 18096), run between service retries:
  - live flags -> `load_mode = none`, `Vulkan_Host model buffer size = 15581.72 MiB` + `Vulkan0 model buffer size = 6203.05 MiB` -> device lost (reproduced)
  - live flags + `--load-mode mmap` -> `CPU_Mapped model buffer size = 15581.42 MiB`, MTP draft context initialized, `listening on http://127.0.0.1:18096`
  - same + one `/v1/chat/completions` request (`enable_thinking:false`) -> correct answer
- `llama-server --mlock` -> `error: invalid argument: --mlock`
- `nix build ...#nixosConfigurations.hyperd-ai-dev.config.systemd.units."llama-cpp.service".unit` -> ExecStart contains `llama-cpp-12503`, `--load-mode mmap`, `--n-gpu-layers 12`
- `scripts/governance/tier0-validation-gate.sh --pre-commit` -> 70 passed, 0 failed
- `python3 scripts/governance/canon-compile.py --write` -> dependency-hygiene compiled into 6 agent files

## Validation Evidence
Root cause: b12503 replaced `--mmap`/`--mlock` with `--load-mode`. The default `auto` resolves to
`none` when a device reports no mmap support, and RADV Renoir does. The 30 CPU layers then go into a
pinned Vulkan_Host buffer: about 21.8 GB GPU-mapped against 13.9 GB GTT. `-fit` projected only
6533 MiB of 17406 MiB of device memory and made no changes. #806 was checked only with the embedder
(:8089), which fits on the device.

| run | flags | result |
|---|---|---|
| live | live 8080 flags | Vulkan_Host 15581 MiB -> device lost |
| mmap | + `--load-mode mmap` | CPU_Mapped + Vulkan0 6203 MiB, MTP draft up, listening |
| gen | + 1 chat completion | correct reply, draft 16/16 accepted, GTT 3.3 GB, 0 device-lost |

Cold-cache speed on a 25-token reply was 3.4 tok/s, which is not comparable with the 5.3 tok/s
baseline. The warm comparison happens after deploy. Upstream changes reviewed: llama.cpp
b9222 -> b12503 `--load-mode` (replaces mmap/mlock flags, default auto), `-fit on` default (no changes
with an explicit `--n-gpu-layers`), `--no-host` (not needed).

## Rollback Plan
Revert this PR, or set `mySystem.aiStack.llamaCpp.useFallback = true` (b9222 pin) on the host, then
rebuild. A pre-merge live trial with `nixos-rebuild test` does not persist across reboot.

Review fix (Gemini REQUEST_CHANGES on 58a4d79ea): b9222 and nixpkgs' llama-cpp reject `--load-mode`,
so the flag is gated on `lib.versionAtLeast pkgs.llama-cpp.version "12503"`. Older builds keep their
default mmap and get `--mlock` when `llamaCpp.mlock` is set. Verified with `nix derivation show` on the
llama-cpp unit: host default -> `llama-cpp-12503 ... --load-mode mmap`; `useFallback = true` ->
`llama-cpp-9222` with no `--load-mode`.

## Residual Risk
- Warm throughput on b12503 is not yet measured against the 5.3 tok/s b9222 baseline.
- Other hosts: forcing mmap restores the pre-b12503 default everywhere. The new `dio` mode and the auto behaviour are no longer used.
- The embedder (:8081) keeps `auto`. It fits on the device and works today.
- Activation: integrated in the existing unit. Goes ON at the next hyperd rebuild. Still to validate live: `:8080/health`, `aq-qa 0`, journal `load_mode = mmap`.

## Hint Feedback
The pin bump tooling (`scripts/ai/update-llama-cpp.sh`, aq-update) does not show upstream release notes
or flag removals. A closure diff plus changelog links at bump time would have caught this before the
rebuild. That is a candidate for an aq-update-unified slice, and the canon rule covers it until then.
