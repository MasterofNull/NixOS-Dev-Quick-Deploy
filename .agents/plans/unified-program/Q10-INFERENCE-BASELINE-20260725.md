# Q10 — Inference Envelope Baseline (measure-first pass, 2026-07-25)

Owner Q10 directive: "measure first and make improvements to the current system, but also
leave our system able to adapt to new deployments with differing levels of system hardware."
This is the BASELINE measurement of the current running system before any resident-small-
model / speculative-decoding investment. Measured directly (fable-5) on the live 27 GB
target — non-gated, no config change. See [[project-q1-q10-decision-gate-closed]].

## Hardware / config (current)
- Host: 27 GiB total RAM (Renoir APU, VRAM 4 GiB shared, n-gpu-layers ceiling 12).
- llama.cpp `:8080` (main): model `active.gguf` (Qwen3-35B), ctx 8192, KV `q8_0` +
  `--flash-attn on`, `--parallel 1`, `--n-gpu-layers 12`, **`--spec-type draft-mtp
  --spec-draft-n-max 2` (speculative decoding ALREADY ON)**, `--jinja`.
- llama.cpp `:8081` (embed): `active-embed.gguf`, ctx 4096, `--parallel 4`.

## Measured baseline (single-request, temp 0)
| Metric | Value |
|---|---|
| Decode throughput | **~3.1–3.3 tok/s** (with spec-decode on) |
| Time-to-first-token (short prompt, ~10 tok) | **~3.8 s** |
| 64-token completion, total latency | ~19.6 s |
| Main model process RSS | **9.9 GB** resident (+ model pages mmap'd in ~13 GiB page cache) |
| Embed model RSS | 0.2 GB |
| System memory | 27 GiB total · ~14 GiB used · ~0.7 GiB free · ~13 GiB buff/cache · ~13 GiB available |

Interpretation: the ~13 GiB "available"/buff-cache is largely the **mmap'd main model**, not
free headroom — the resident+cached model footprint is close to the UMBM budget (≈22.5 GB
model / 1 GB KV / 3 GB OS). Real free RAM for a *second* concurrent capability is small.

## Findings (what the baseline tells us)
1. **Speculative-decoding benefit is currently UNMEASURABLE.** `--spec-type draft-mtp` is
   enabled, but `/metrics` exposes no draft/accept counters (only `llamacpp:n_decode_total`).
   We cannot say whether spec-decode is helping, neutral, or hurting on this APU. **Q10
   cannot rationally decide to invest more in spec-decode until its acceptance rate is
   observable.** → first Q10 action.
2. **Memory is the binding constraint, not a quant windfall.** The main model already
   consumes essentially the whole usable envelope (RSS 9.9 GB resident + mmap'd cache). A
   **resident small model** (separate draft/assistant model) would compete for the same
   page cache and risk evicting the main model's pages → thrash. This directly confirms the
   Q10 ratification caution: "never assume one quant step funds two concurrent capabilities."
3. **Throughput (~3 tok/s) is APU-bound**, as expected — the harness's async/queue +
   remote-lane strategy (slow-but-steady local, remote for speed) is the correct response,
   not a local-throughput chase.

## Recommended next Q10 measurements (each needs a controlled llama.cpp restart = owner terminal)
- **A/B spec-decode:** restart with `--spec-type none` vs current draft-mtp, same prompts,
  compare tok/s — quantify the actual spec-decode benefit on this hardware (the #1 gap).
- **Acceptance-rate observability:** enable/scrape draft-acceptance counters (build flag or
  a wrapper that logs accepted/proposed) so spec-decode is measurable ongoing (make it
  observable per the harness "measure what you manage" principle).
- **Resident-small-model feasibility:** only after (1)/(2) — measure page-cache eviction of
  the main model when a small model is co-resident; if it thrashes, defer (memory-bound).

## Hardware-agnostic note (Q10 second clause)
None of the above bakes in a 27 GB assumption: the spec-decode A/B + acceptance observability
are hardware-independent instruments; the resident-small-model decision is explicitly gated
on measured free-memory headroom, so it degrades gracefully on smaller deployments (skip
co-residence) and scales up on larger ones (enable when headroom measured). See
[[feedback-hardware-agnostic-slow-steady-local]].

## Status
Baseline recorded. The follow-on measurements need a controlled inference restart (owner
terminal) — batched, not blocking. No config changed by this pass.
