# llama.cpp bump b9222 -> b12503

## 1. Summary
Pin moved from b9222 (2026-05-18) to b12503 (2026-11-18, the newest tag at the time). It builds with the Vulkan backend, every flag the llama-cpp unit passes exists in the new `llama-server`, and a side instance on port 8089 initialised Vulkan on the Renoir APU, offloaded 12/25 layers, and answered /health and /v1/embeddings. The live 8080 server was not touched. Not validated: the main 22.85 GB model on the new binary (RAM cannot hold two copies); that happens after the reboot (section 7). Verdict: GO for including the bump in the rebuild, with the rollback in section 8.

Upstream marks every `b*` release as prerelease, so `update-llama-cpp.sh` (which selects non-prerelease tags) finds nothing without `--to-version`. b12503 was picked manually as the newest tag; it is hours old, which is why the post-reboot checks matter.

## 2. What changed in the repo
- `nix/pins/llama-cpp.json`: current = b12503 (hash `sha256-C/dVDVTen9p+pq2ydrt3FKnXIMC9HMyW9y2qYwC1aJM=`), fallback = b9222 (with its npmDepsHash). `npmDepsHash` is dropped for the new pin on purpose.
- `nix/lib/overlays/llama-cpp-latest.nix`: for a pin with no `npmDepsHash`, remove nixpkgs' `npm-config-hook`, set `npmDeps = null` and a preConfigure that only sets the build commit. Reason: upstream removed `tools/ui`, so nixpkgs' `pushd tools/ui` failed; the UI is off anyway (`LLAMA_BUILD_UI=OFF`). The patch is selected by pin (fallback keeps `allow-vulkan-igpu-offload-b9222.patch`).
- `allow-vulkan-igpu-offload.patch` re-ported: 1 of 8 Vulkan hunks and the iGPU hunk no longer applied. Only the two functional hunks are kept (always add iGPUs to the device list; init the backend before `common_params_parse` in server.cpp). The `vkdiag`/`registry-diagnostic` stderr hunks were dropped (diagnostics only, no behaviour). Upstream now adds an iGPU when no discrete GPU exists, which is this machine, so the first hunk is belt-and-braces.
- Root cause note (Rule 19): `update-llama-cpp.sh` computes the hash with `nix-prefetch-url --unpack` of the tarball, but the overlay uses `fetchFromGitHub` with `leaveDotGit` plus a COMMIT postFetch, which hashes differently (first build failed with a hash mismatch; correct value taken from the error). It also rewrites `current` without `npmDepsHash` and does not look at prerelease-flagged tags. Not fixed here (out of slice); register as a follow-up.

## 3. Notable upstream changes for us
- b12489: server returns 400 when `grammar` and `ignore_eos` are both set. `rg ignore_eos` over the repo (non-docs) finds no use, so no caller is affected.
- b12498: slot_sched fix for lora and recurrent state (relevant to slot reuse on the Qwen3.6 hybrid model).
- b12483 / b12477 / b12474: KV-pool/rotated-K reads and qwen3next weight scale; unverified for Vulkan. Check generation speed after the reboot.
- `--spec-type` now lists `draft-mtp` among many types; `--draft*` flags were removed in favour of `--spec-draft-n-max` (we already use the new name). Server version string is now `1.0.0-dev (build 12503)`.

## 4. Flag compatibility (checked against the new `llama-server --help`)
| Flag our unit passes | Present in b12503 | Note |
|---|---|---|
| --host, --port 8080 | yes | |
| --model | yes | |
| --ctx-size 8192 | yes | |
| --metrics | yes | |
| --log-verbosity 2 | yes | |
| --spec-type draft-mtp | yes | listed value |
| --spec-draft-n-max 2 | yes | default now 3 |
| --flash-attn on | yes | takes on/off/auto |
| --cache-type-k/v q8_0 | yes | |
| --timeout 3600 | yes | |
| --parallel 1 | yes | |
| --batch-size 512, --ubatch-size 256 | yes | |
| --threads 8, --threads-batch 8 | yes | |
| --n-gpu-layers 12 | yes | |
| --jinja | yes | |
| embedder: --embedding --pooling cls --ctx-size 4096 --threads --n-gpu-layers 12 --parallel 4 --ubatch-size 2048 | yes | all accepted by the smoke run |
No renamed or removed flag among those used. API fields: `chat_template_kwargs.enable_thinking=false` is unchanged in the request schema (not exercised against the main model yet); json_schema/grammar is only affected by the ignore_eos rule above.

## 5. Smoke test (side instance, port 8089, embedder, nice 19, about 40 s, stopped afterwards)
- `llama-server --list-devices`: `Vulkan0: AMD Radeon Graphics (RADV RENOIR) (18036 MiB, 7694 MiB free)`.
- Load log: `using device Vulkan0 (AMD Radeon Graphics (RADV RENOIR))`, `offloaded 12/25 layers to GPU`, `Vulkan0 model buffer size = 140.81 MiB`.
- /health: `{"status":"ok"}`; /v1/embeddings on a synthetic string: dim 1024, finite values.
- Live server at the end: 8080 and 8081 health both `ok`; the new-binary instance no longer listens on 8089.
- Build cost: the compile ran niced while other agents' work was queued; waited for load5 < 12 and no other nix build first.

## 6. Baselines for the post-reboot comparison (read from existing telemetry, no new probes)
- `/var/lib/ai-stack/hybrid/telemetry/llm-speed-probe.jsonl`, 885 probes since 2026-10-29: generation median 4.20 tok/s (max 6.97), prompt median 5.15 tok/s. Last 50: gen median 3.49, max 4.89. Last 30 probes not flagged slow: gen median 4.30, prompt median 6.25. Recent 2026-11-17 probes were flagged slow (0.5 to 2.9 tok/s gen), cause MEMORY or POWER (page-cache pressure, battery); compare like for like (AC power, performance profile, memory available above 10 GB).
- Live `/metrics` on 8080 right now: predicted_tokens_seconds 1.96, prompt_tokens_seconds 7.67 (cumulative window under load, not a clean probe).
- MTP accepted-token rate: no counter exists in `/metrics` and the journal has no accept line at the current verbosity; baseline UNKNOWN. Capture it from the first post-reboot run on the new binary and from the old generation if rolled back.

## 7. Post-reboot full-model validation (resume notes)
1. Check the service came up on the new binary: `systemctl status llama-cpp`, ExecStart path contains `llama-cpp-12503`, `curl :8080/health`.
2. Speed: with AC power, performance profile, nothing else heavy, run `aq-llm-speed-probe` (or wait for its timer) 3 times; compare gen/prompt tok/s with section 6 (regression if gen median is below about 3.5 tok/s in a non-slow state).
3. MTP: run one 256-token completion with `chat_template_kwargs:{"enable_thinking":false}`; read `draft acceptance` from the journal at `--log-verbosity 2` (or `/slots`); record the rate. A drop to zero acceptance means the draft-mtp path broke.
4. QA: `AQ_CONFINE_REQUIRE_CONTEXT=1 scripts/ai/aq-qa 0 --machine` (the llm, coordinator and delegation checks); expect no new failures against the last green run (208 passed, 0 failed, 9 skipped).
5. json_schema: one `/v1/chat/completions` request with `response_format: {type: json_schema, ...}`; expect valid JSON; also confirm a request with grammar and without ignore_eos still returns 200.
6. Offload check: journal shows `offloaded 12/N layers to GPU` on Vulkan0 and the service does not exceed 27 GB total.

## 8. Rollback and limits
- Rollback: `sudo nixos-rebuild switch --rollback` (or boot the previous generation from the boot menu); the old generation runs `llama-cpp-9222`. Alternatively set `mySystem.aiStack.llamaCpp.useFallback = true`, which now selects b9222 and its original patch, then rebuild.
- Limits: the main model, MTP and the chat template path were not run on b12503; Vulkan behaviour with the 22.85 GB model and 12 GPU layers is validated only through the embedder. The pin is a hours-old build.
