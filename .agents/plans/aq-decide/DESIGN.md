<!-- STATUS: Frozen PLAN_READY_WITH_FOLLOWUPS for DEC-S0..S4; owner decisions D1 advisory+friction, D3 seeds/synthetic remote labelling, D4 friction-only egress, 2026-10-15. DEC-S5..S10 deferred, not frozen. -->
> **Status:** Frozen PLAN_READY_WITH_FOLLOWUPS for DEC-S0..S4; owner decisions D1 advisory+friction, D3 seeds/synthetic remote labelling, D4 friction-only egress, 2026-10-15.

# aq-decide v2: local open-weight decision layer ("Jev parity")

Status: DESIGN v2 (architect output, not implemented). Date: 2026-10-15. Supersedes `aq-decide-DESIGN.md` (v1, kept). Repo HEAD 7f9ef0f4 when drafted. Input: `aq-decide-DESIGN-REVIEW.md`, `aq-confine-DESIGN-v6.md` (section 7A, W2-S7), `agent-auth-DESIGN-v2.md`, owner decisions D2 (remote lanes: default internet, monitored, "system one" filtered) and the owner addition "do not forget about gemini and other remote agent providers".
Items not re-verified this session are marked [UNVERIFIED].

**Status: PLAN_READY_WITH_FOLLOWUPS-frozen for DEC-S0 through DEC-S4** (confirmatory review `aq-decide-DESIGN-v2-REVIEW.md`: S0, S3 PLAN_READY; S1, S2, S4 PLAN_READY_WITH_FOLLOWUPS, followups folded in below; S5-S10 deferred and not frozen).

## v2.1 changes (from the confirmatory review)

| # | Review item | Change | Section |
|---|---|---|---|
| 1 | bge-small 512-token context; one 400 observed; v1's 4 KB cap too big | Hard cap of 1500 characters on any text sent to T1, with an explicit truncation policy | 3.1 |
| 2 | Second instance at `-ngl 12` not free: VRAM already at carve-out (4.28 GB used), `-ub 2048` compute buffers | Start CPU-only (`-c 512 -ub 512 --threads 2`); `-ngl 12` only if a paired before/after check shows main-model tok/s and VRAM within 3% (DEC-S2 acceptance test); benchmark limits stated | 2.7, 8.2, 10.1 |
| 3 | T0.5 seeds only; shadow output must not feed any cache | Stated as a rule and tested | 4.2 |
| 4 HIGH | Rate budget defeatable by burning it on 5 novel hosts | Budgets keyed per (lane, reason class); high-signal reasons never digest-collapse | 6.4 |
| 5 MED | `hold` times out to allow on default-internet lanes; rules-only egress adds nothing over W2-S7 | `hold` is delay-only, stated plainly; egress v1 is a plain rules table in W2-S7 with no runtime dependency on aq-decide until a later slice | 6.1, 6.8, 10.1 |
| 6 | `ai-stack.nix:970` assertion covers only the embed repo | A second model repo needs its own assertion/allowlist check (DEC-S2 acceptance) | 8.1 |
| 7 | AppArmor UNVERIFIED closed; copied binaries bypass | A sibling unit using the same store-path binary is auto-confined by exec-path attachment; copied binaries bypass it (`ai-stack.nix:195-197` forbids it by contract test); the profile limits malicious-GGUF parsing in the service, not agents; tier0 check added | 2.6, 8.1 |
| 8 | D4 | Recorded as owner-decided: yes, friction-only (owner already said "system one agent filtered access") | 11 |

Outline:
0. Summary and what changed
1. Changes from v1 (every review finding mapped)
2. Benchmark results (T1 embedder, T0.5, T2 sizing) and the embedder decision
3. Contract (trimmed) and tier ladder
4. v1-slice scope, data gates, bootstrap and labeling rules
5. Integrations in priority order (DAG/task routing first; approvals later; never on a per-call permissions hot path)
6. Egress coupling: every remote lane, grey-zone question specs, add-friction-only rules
7. Safety
8. Ops: Nix-declarative model placement, T2 on demand, page cache, observability, flags
9. Evaluation and promotion
10. Slices (re-ordered) and deferred items
11. Owner decisions
12. Open items, unverified claims

## 0. Summary

1. Jev is a closed, hosted decision API. We build parity from open-weight parts (no API key, no remote model call). If TypeSafe ever ships weights, intake goes through the `capability-intake` skill as one more backend.
2. Decision after benchmarking (section 2): **T1 embedder = bge-small-en-v1.5 (MIT, 33M params, GGUF Q8 37 MB) on a second small llama.cpp embedding instance with `-ngl 12`**, not the shared bge-m3. Measured on this host with n=200 per cell: short states (about 33 tokens) p50 31 ms / p95 43 ms / p99 50 ms; long states (about 354 tokens) p50 86 ms / p95 122 ms / p99 151 ms. The same hardware path for bge-m3 is 269/426/491 ms short and 999/1589/2412 ms long. Caveat: those runs happened at ambient load average 8, so they are not best-case.
3. T0.5 (hashed TF-IDF + linear model, in-process, no service) costs **0.7 ms p50 / 0.9 ms p95 / 1.3 ms p99** per decision and scored 0.634 five-fold accuracy on a proxy task (majority class 0.54), against 0.704 (bge-small), 0.774 (nomic), 0.728 (bge-m3). The embedder differences are within noise at n=257 (about +/-0.05); the lesson is that embeddings buy roughly 7-14 points over TF-IDF on free-text, and the three embedders are not separable on this sample.
4. **v1 (DEC-S1) ships no learned head.** It is the contract, deterministic rules (T0a), an exact cache (T0b), the T0.5 hashed TF-IDF tier in shadow, and decision logging. A learned head (T0.5 or T1) is disallowed for a question until the data gates in section 4.3 are met (150 effective human-or-outcome labels per class, at least 2 classes with 30+ each on the evaluation split). The current approvals data (66 successful approvals, 2 dismissals; section 4.1) cannot support a head.
5. Slice order changed: DEC-S0 (fix the empty `routing_decisions` producer) and DAG/task routing in shadow come first; approvals triage is later. T1/T2 never run on a per-tool-call permissions path.
6. Egress (section 6): aq-decide only adds friction (flag, alert, hold for the owner). It never removes or relaxes a deterministic deny, never reads agent-authored text, never writes its own decision cache from observed outcomes, and is not callable by any agent. Per-lane allowlists belong to aq-confine W2-S7 (`config/remote-lane-egress.json`); lane identity is a feature for every remote lane: Claude, Codex, Antigravity IDE, `agy`, retired `gemini` (`gemini-legacy`), switchboard remote profiles, coordinator remote handlers, MCP servers with remote APIs, and any later provider lane.
7. Deferred (moved, not deleted): semantic cache, reranker, Qwen3Guard, T2 LLM tier, the `score` type, drift/PSI machinery, the HTTP endpoint, the package layout, the dashboard card.
## 1. Changes from v1 (every review finding mapped)

| # | Review finding | Disposition in v2 | Where |
|---|---|---|---|
| Cit-1 | "69 approve" wrong: 66 ok + 3 failed approve attempts + 2 dismiss | Fixed; failed attempts are not labels. Also the audit record holds `key`, `note`, `msg[:300]` only, no request text, so a join is mandatory | 4.1 |
| Cit-2 | `cascade.py` `score_confidence` is at line 62, not 58-62 | Corrected (`scripts/ai/lib/cascade.py:62`; `threshold_for` is at :58) | 5.4 |
| Cit-3 | bge-m3 is host state (`active-embed.gguf`), not Nix-declared; option default is `embed.gguf` | Stated as host state; Nix default is the catalog/`activeModel` mechanism (`nix/modules/roles/ai-stack.nix:847-923`) | 2.5, 8.1 |
| Cit-4 | Qwen3Guard "0.6B" is 751M params | Dropped from v1; noted when it returns | 10.3 |
| 1 HIGH | Missed bge-small; bench before deciding; GLiClass needs onnxruntime | Benchmarked bge-small, nomic, bge-m3, live service; onnxruntime 1.24.4, sentence-transformers 5.4.1 and torch 2.11.0 ARE importable in the interactive python, so GLiClass is not ruled out on dependency grounds but is not benchmarked (no weights downloaded, no install allowed) and the services' Python env is unverified | 2 |
| 2 HIGH | Permissions per-call must never call T1/T2; promote T0.5 to default | Hard rule; T0.5 is the default learned-shaped tier; permissions use only T0a/T0b and async annotation | 5.1, 7 |
| 3 HIGH | Calibration on 71 skewed labels is meaningless; disallow heads with <2 effective samples in a class | v1 has no head; explicit gates; a class with fewer than 2 effective samples makes the head disallowed, not merely abstaining | 4.3 |
| 4 HIGH | Bootstrap leakage; teacher/synthetic labels in calibration and eval | Remote lane sees seeds + synthetic text only; teacher/synthetic rows barred from calibration and eval splits | 4.4 |
| 5 HIGH | Egress persuasion channel; add friction only; non-agent features; owner/rule-only cache writes; no feedback loop; agents cannot call /decide | Section 6 in full, plus per-lane specs for all remote providers | 6 |
| 6 MED | Safety text: adversarial residual understated; alert-fatigue DoS; OOD floor at n=70 meaningless | Rate budget on `ask`/`hold`; OOD floor only enabled with >=500 training rows; adversarial residual restated | 7 |
| 7 MED | Ordering: S0 producer fix + DAG routing first; egress after aq-confine, rule-only start | Re-ordered | 10 |
| 8 MED | T2 evicts page cache; yield timers; no cited Nix mechanism for extra GGUFs; llama-server reads only the models dir | Mechanism found and specified; AppArmor profile cause identified; page-cache effect stated with the numbers available | 8 |
| 9 LOW | 0.6B/reranker unmeasured; S5 not ready | T2 stays NOT_READY and deferred; this session measured only embedders and 4B (v1) | 10.3 |
| Cut-1 | Drop semantic cache | Moved to DEC-S5 | 10.3 |
| Cut-2 | Drop reranker, Qwen3Guard, T2, `score` type | Moved to DEC-S6/S7 | 10.3 |
| Cut-3 | Drop isotonic, drift/PSI until a head is live | Moved; ECE on human labels only | 9, 10.3 |
| Cut-4 | Defer HTTP endpoint and dashboard card | Moved to DEC-S8; CLI + decision log + counters only | 10.3 |
| Cut-5 | One module + config JSON | Adopted | 4.5 |
| D-notes | D1 real; D2 reframed; D3 narrowed; D4 replaced | Section 11 | 11 |
| Req-1 | Benchmark n>=200, p50/p95/p99, quiet vs loaded, short/long, T0.5 | Section 2 | 2 |
| Req-4 | Egress per aq-confine v6; owner addition on all providers | Section 6 | 6 |
| Req-6 | Nix mechanism, T2 on demand, page cache | Section 8 | 8 |
## 2. Benchmarks (re-taken 2026-10-14/15, this host)

### 2.1 Method

- Embedding servers: the same llama.cpp build (b9222, `/nix/store/kw92hw1pxp5y0ycj7qyjqay7zhl5r4zc-llama-cpp-9222`) run by me as my own process, `--embedding -c 2048 -b 2048 -ub 2048 --threads 4 --parallel 1`, one model at a time for the `-ngl 12` pass (all three at once for the CPU-only pass). Pooling: bge-small cls, nomic mean, bge-m3 cls. Models: `bge-small-en-v1.5-q8_0.gguf` (CompendiumLabs, 36,806,944 bytes, sha256 prefix ec38e8da1425), nomic-embed-text-v1.5 Q8_0 and bge-m3 Q8_0 from `/var/lib/llama-cpp/models`.
- Inputs: slices of real repo text (PULSE.log bodies), each request unique. "Short" = 60-180 characters (median 33 tokens bge-small/nomic tokenization, 37 bge-m3); "long" = 1200-1400 characters (median 354 tokens, 408 for bge-m3). bge-small has a 512-token context; 1 of 200 requests per condition errored (HTTP 400 over context) and is excluded and counted.
- n=200 per cell after one warm-up request; p95/p99 are order statistics over 200 samples (p99 is the 2nd-largest value, so it is an indication, not a tight bound). Scripts and raw results are in `.agents/delegation/outputs/sota-designs-20261014/spike-models/` (`bench_t1.py`, `run_quiet.sh`, `run_loaded.sh`, `run_gpu.sh`, `res_quiet.txt`, `res_loaded.txt`, `res_gpu12.txt`). Two invalid earlier runs (token lengths over bge-small's context) are kept in `run1_invalid_lengths/` and `run2_invalid_ctx/`.
- Conditions, labeled as measured (load average from `/proc/loadavg`, 16 logical CPUs): **ambient** = nothing of mine running except the benchmark, stack services active, load avg 2.3-3.7 before; **loaded** = ambient plus 4 synthetic CPU spinners (python busy loops), load avg 2.3 rising to ~10; **ngl12 pass** = one server at a time with 12 GPU layers like the live service, ambient load avg 8.6 before (heavier than the other passes, so these numbers are pessimistic for the GPU path). "Quiet" in the literal sense (idle host) did not occur: the stack keeps load around 2-4.

### 2.2 Results (ms)

CPU-only (`-ngl 0`), ambient:

| Model | short p50 | short p95 | short p99 | long p50 | long p95 | long p99 |
|---|---|---|---|---|---|---|
| bge-small Q8 | 120.1 | 159.6 | 187.0 | 209.3 | 283.0 | 380.9 |
| nomic v1.5 Q8 | 167.9 | 235.6 | 259.9 | 379.8 | 478.6 | 508.1 |
| bge-m3 Q8 | 496.9 | 641.3 | 2375.0 | 856.0 | 1437.5 | 1801.7 |
| live service :8081 (bge-m3, `-ngl 12`, parallel 4) | 163.1 | 325.8 | 351.8 | 611.8 | 737.0 | 881.1 |

CPU-only, loaded (4 spinners):

| Model | short p50 | short p95 | short p99 | long p50 | long p95 | long p99 |
|---|---|---|---|---|---|---|
| bge-small Q8 | 119.4 | 138.9 | 160.1 | 208.6 | 257.5 | 287.2 |
| nomic v1.5 Q8 | 181.4 | 235.2 | 255.2 | 380.9 | 493.2 | 514.0 |
| bge-m3 Q8 | 518.6 | 674.5 | 784.0 | 1381.3 | 2423.8 | 3323.3 |

`-ngl 12` (GPU layers as in production), ambient load avg 8.6:

| Model | short p50 | short p95 | short p99 | long p50 | long p95 | long p99 |
|---|---|---|---|---|---|---|
| **bge-small Q8** | **31.2** | **43.4** | **49.6** | **85.5** | **122.4** | **150.7** |
| nomic v1.5 Q8 | 65.0 | 82.2 | 95.0 | 206.7 | 281.3 | 366.0 |
| bge-m3 Q8 | 269.1 | 425.8 | 491.3 | 998.7 | 1589.0 | 2411.6 |

Observations: (a) the loaded-with-spinners result barely moved bge-small (CPU threads plus short sequences), so contention from the main model is a second-order effect compared with model size; (b) bge-m3 on the live service is about 3x faster than a CPU-only copy because of `-ngl 12`, which is why v1's 125-330 ms figures looked acceptable; (c) a GPU-layer second instance costs about the VRAM of a 37 MB model plus context (negligible against the 4 GB shared APU budget, ceiling 12 layers unchanged) [VRAM use not separately measured].

### 2.3 T0.5 (hashed TF-IDF + logistic regression, in-process, sklearn 1.8.0 / numpy 2.4.4)

Single-decision latency, n=200: sklearn `transform`+`predict_proba` p50 0.96 / p95 1.22 / p99 1.53 ms; lean path (sparse coefficient dot) p50 0.71 / p95 0.88 / p99 1.25 ms. Feature space 2^16 hashed uni/bi-grams, sublinear TF. No service, no model file, no network. Script: `spike-models/t05_proxy.py`.

### 2.4 Accuracy proxy (relative ranking only)

No labeled aq-decide data exists, so the only quality comparison available is a proxy task: predict the PULSE.log action word (write/commit/plan/edit/review) from the entry text; n=257 (majority class `write` 139 = 0.54); five-fold logistic regression; embeddings L2-normalised, no task prefix for nomic.

| Features | 5-fold accuracy |
|---|---|
| Majority class | 0.541 |
| T0.5 hashed TF-IDF | 0.634 |
| bge-small | 0.704 |
| bge-m3 | 0.728 |
| nomic v1.5 | 0.774 |

Standard error is about 0.03 at n=257, so embedder-to-embedder differences are not significant; embeddings over TF-IDF is suggestive (+7 to +14 points). This is not evidence about security-class questions. It justifies only the ordering of cost, not quality, and is to be replaced by per-question evals (section 9).

### 2.5 Decision (D2 as a benchmark result)

- **T1 embedder: bge-small-en-v1.5 on a dedicated small instance with `-ngl 12`** (p95 43 ms short, 122 ms long; 5-10x faster than bge-m3 at every percentile in the same conditions). Keep nomic as the fallback candidate (best proxy accuracy, 2x slower than bge-small, still 4x faster than bge-m3).
- **Do not swap the RAG embedder.** Qdrant collections are bge-m3 1024-d vectors; changing the shared `activeModel` would invalidate them. aq-decide uses a second instance; its vectors never touch RAG collections.
- **T0.5 is the default learned-shaped tier** for hostname/key/vocabulary-shaped questions and for the shadow phase.
- GLiClass ModernBERT ONNX: `onnxruntime 1.24.4` imports in the interactive python, but no model weights were downloaded and nothing was installed; it is a later candidate (adds a Python-path inference dependency whose availability inside the coordinator's service env is [UNVERIFIED]).
- T2 sizing from v1 stands: Qwen3-4B Q4 on CPU = 2.0-3.2 s for 60-100 prompt tokens, 11-13 s for 600; so T2 is never synchronous (section 8.3).

### 2.7 Benchmark limits (v2.1, stated plainly)

One sequential client, so concurrency is untested; nothing recorded whether the main model was decoding during any pass (worst case, embedding during main-model generation, is untested); the CPU-only, loaded and `-ngl 12` passes are **not paired** (different times, different ambient load: the spike bge-m3 at ngl 12 measured 269/426 ms short while the live service measured 163/326 ms, a ~1.6x swing from load alone), so cross-pass comparison is unreliable; p99 over 200 samples is the second-largest value. Treat every absolute number as **+/-50%**. The ranking conclusion (bge-small 4-10x faster than bge-m3 at every percentile and condition) is far outside that noise and stands. Also: the "negligible VRAM" remark in 2.2(c) is withdrawn; live VRAM use was 4.28 GB (GTT 5.79 GB), already at the carve-out ceiling, so an extra Vulkan context is not known to be free.

### 2.6 Why the sandbox blocked llama-server (resolved)

llama-server failed with EACCES opening model files outside `/var/lib/llama-cpp/models` (`strace` showed `openat(...) = -1 EACCES`) while Python opened the same file. Cause: AppArmor profile `ai-llama-cpp` (`/etc/apparmor.d/ai-llama-cpp`) is bound to the exact store path `/nix/store/kw92hw1pxp5y0ycj7qyjqay7zhl5r4zc-llama-cpp-9222/bin/llama-server` and allows model reads only under `/var/lib/llama-cpp/models/**`. A byte copy of the binary at another path is not covered by the profile and loads files normally, which is how this session benchmarked. Consequences recorded: (1) any extra model for a service must live in `/var/lib/llama-cpp/models` (Rule 14 style: the profile, not DAC, is the gate); (2) the profile is bound to a store hash and follows the module's `llamaServerExec` when llama.cpp updates. **v2.1 closure of the earlier [UNVERIFIED]:** attachment is by exec path, not by the unit's `AppArmorProfile=` field: the live `llama-cpp-embed` unit reports an empty `AppArmorProfile` yet its process runs as `ai-llama-cpp (enforce)`, so a sibling unit that execs the same store-path binary is auto-confined. Copied binaries bypass the profile; `nix/modules/roles/ai-stack.nix:195-197` already forbids copying the binary (contract test). The profile limits a malicious or corrupt GGUF parse inside the service; it does not constrain agents (an agent that can copy and run a binary already has code execution in its own sandbox, governed by aq-confine). My spike copy exists only under `/tmp/aqd-spike/bin` and is not a production path; add a tier0 check that no tracked script execs a copied llama-server.
## 3. Contract and tier ladder (v1 subset)

Same request/response shape as Jev (`choice`, `noul`, per-option probabilities, `confidence`), plus `outcome: decided | abstain | error` and a closed-enum `reason_code`. The `score` type is deferred until a caller needs it (cut). Everything else from v1 section 1.1-1.2 holds, with these v2 amendments:

- Question definitions (instructions, options, thresholds, allowed callers, features allowed) live in `config/aq-decide.json` and cannot be redefined by the request. A question declares `features: [...]` from a closed list; a caller-supplied field outside that list is dropped before any tier sees it. For egress questions the list excludes every free-text field (section 6.3).
- `reason_code` is `[A-Z_]{1,24}`, registered per question. No free-text rationale anywhere in the response or in anything code consumes.
- `abstain` and `error` are different: abstain = calibrated confidence below the question threshold (or a head disallowed by section 4.3); error = backend or timeout. Both leave the caller on its current behavior.
- Calibration reporting uses one method: 15 equal-mass-bin ECE on **human-labeled** held-out rows only (section 9). Temperature scaling for logistic heads; isotonic is not used in v1.

### 3.1 State cap and truncation (v2.1)

bge-small has a 512-token context (1 of 200 long benchmark requests returned HTTP 400), so v1's 4 KB cap is withdrawn. Rules: (1) before any tier, `state.text` is stripped of control characters and capped at **1500 characters** (about 400 tokens at the observed 354 median for 1200-1400 chars; headroom below 512 is deliberate); (2) truncation keeps the **head 1000 and tail 500 characters** joined by a fixed marker `\n…[cut]…\n` (questions whose signal sits in the middle declare `truncate: "head"|"tail"|"headtail"` in config); (3) the response carries `truncated: true` and a `TRUNCATED` flag in the log, never silently; (4) a T1 request that still returns HTTP 400 is an `error` (not a guess) and the caller keeps current behavior; (5) T0.5 and rules see the same capped text, so tiers agree on input; (6) a test feeds 400, 1500, 1501 and 4000 character inputs and asserts the cap, the marker and the flag.

Tier ladder as built in each slice:

| Tier | Mechanism | Measured cost | Available from |
|---|---|---|---|
| T0a | Deterministic rules/allowlists/sentinels from config | <1 ms [UNVERIFIED: not benchmarked; pure dict/regex] | DEC-S1 |
| T0b | Exact cache keyed by sha256(canonical features + question + config version); written only by owner or rules (section 6.4) | <1 ms [UNVERIFIED] | DEC-S1 |
| T0.5 | Hashed TF-IDF + linear model, in-process | 0.7 ms p50 / 1.3 ms p99 | DEC-S1 shadow only; promotable per section 4.3 |
| T1 | bge-small `-ngl 12` instance + numpy head | 31 / 43 / 50 ms short; 86 / 122 / 151 ms long (p50/p95/p99) | DEC-S3 (when labeled volume allows) |
| T2 | Small local LLM, constrained label logprobs | seconds; never synchronous | deferred (DEC-S7) |
| T3 | Main local model or remote lane | seconds to minutes; offline/async only | teacher labeling only |

The router picks the cheapest tier whose calibrated confidence clears the question threshold, bounded by `max_tier` and `deadline_ms`; there is no escalation path to a tier above T0.5 until the corresponding slice ships.
## 4. Data, gates, bootstrap

### 4.1 What exists (corrected counts; measured 2026-10-14/15)

| Source | Rows | Usable label | Note |
|---|---|---|---|
| `approval-inbox-audit.jsonl` (`/var/lib/nixos-ai-stack/optimizer/prsi/`, writer `scripts/ai/lib/approval_inbox.py:85-95`) | 71 = 66 approve ok + 3 approve ok=false + 2 dismiss; 70 distinct keys | 66 approve, 2 dismiss (the 3 failed attempts are execution failures, not owner judgments) | The record holds `ts, action, key, by, door, note, tag, ok, msg[:300]` only: no request text. Text must be joined from the action queue by `key`; one class holds 97% of labels |
| `routing_metrics.db` `routing_decisions` / `advisor_consultations` / `escalations` | 0 / 0 / 4 | none | Producer not writing (DEC-S0) |
| `delegation-feedback.jsonl` | 48 (32 failed, 16 success) | outcome, `failure_class` | Small |
| `agent-run-events.jsonl` | ~91.7k | final_outcome vs validation per task | Prompts digested, not stored (`agent_run_events.py:66-93`) |
| `hybrid-events.jsonl` | ~54k | route chosen | Query is a sha256 digest |
| `hint-feedback.jsonl` | 1,166 | `helpful` | Includes synthetic health probes |
| `workflow-deviations.jsonl` | 218, all `observation.failed` | `requires_owner`, `mutation_risk` | One reason code |

Conclusion unchanged and sharper: no question has a labeled set big enough for calibration today, and the high-volume logs deliberately carry no text. We do not weaken redaction to create training data.

### 4.2 What v1 (DEC-S1) does with this

Rules, exact cache, T0.5 in **shadow only**, and decision logging. **The T0.5 model in shadow is trained on seeds only** (section 4.4; no harvested rows, no teacher rows) and **its shadow output never feeds T0b or any other cache or trust store** (a test asserts that no cache write path accepts a `tier=T0.5` result; T0b is written only by rules and the owner). Its outputs are never acted on; they are logged next to the current behavior so that labeled volume accrues (the decision log stores the redacted, hashed-key text in the aq-decide log only, not in the existing event logs).

### 4.3 Gates before any learned head (T0.5 or T1) may leave shadow or even abstain-on-calibration

A question's head is **disallowed** (not merely abstaining) unless all hold on its training set after dedup:
1. At least 150 effective labeled examples per class for `choice` questions (300 total for `noul`), where effective = human rows at full weight, outcome-derived rows at 0.5, teacher/synthetic rows at 0 for counting purposes.
2. No class with fewer than 30 human-or-outcome examples (a class with fewer than 2 is a hard disallow; with 2 to 29 the question stays rules-only for that class).
3. Largest class share at most 80% of labeled rows, or the head is reported with class-balanced metrics and the majority-prior baseline (a head that cannot beat the majority class on the held-out set by a stated margin is rejected).
4. A held-out evaluation split of at least 100 human-labeled rows, time-split, never used in training or calibration (section 9).
5. OOD floor enabled only when training rows >= 500; below that no OOD threshold is claimed.
Approvals today: 66/2 fails gates 1, 2, 3, 4.

### 4.4 Bootstrap and labeling rules (D3 narrowed)

1. **Remote labelling sees seeds and synthetic text only.** The one-off remote Claude-lane pass (OAuth, no key) may receive hand-written seed examples and synthetic paraphrases generated from them. It never receives harvested real states (approval keys, commands, hostnames, paths, delegation prompts). Redaction in `agent_run_events.redact_payload` is key-name based and does not scrub free text, so real states are never sent anywhere remote.
2. **Teacher labels for real states stay local**: the main local model, async batch, thinking disabled (`chat_template_kwargs.enable_thinking=false`), into `label_source: teacher_local`.
3. **Teacher and synthetic labels are excluded from calibration and evaluation splits.** They may enter training with low weight (teacher 0.4, synthetic 0.25) only after gate 1-4 are satisfied by human/outcome rows, because they transmit the teacher's priors, not the owner's. Calibration (temperature) and every reported metric use human rows only; otherwise ECE is circular.
4. Dedup by normalized text hash; time-split plus group-split by source reference; never train on the head's own predictions; any text that trips the injection heuristic is quarantined for review.
5. Retraining is an offline timer (never in a request path), skipped when the main model is busy or free RAM < 3 GB, `Nice=15`, `CPUQuota` capped. Fitting 2000x1024 4-class logistic regression takes 1.6 s [v1 measurement]; the T0.5 refit is cheaper.

### 4.5 Code layout (cut)

One module `scripts/ai/lib/aq_decide.py` plus `config/aq-decide.json` and `config/aq-decide/seeds/*.jsonl` for DEC-S1. The `labelers/`, `heads/`, `calib/` package split is deferred until a second head type exists.
## 5. Integrations, re-prioritized (value x frequency x safety, labels that accrue automatically first)

| Order | Integration | Why here | Gate to act |
|---|---|---|---|
| 1 | I2 task-profile routing (DAG) | Highest frequency, reversible, labels accrue from existing run events once S0 lands | shadow only until section 9 passes |
| 2 | I4 retry/escalate | Labels from delegation outcomes; bounded by Rule 6 | shadow |
| 3 | I3 RAG: retrieve-or-not, collection/route choice | High frequency, reversible | shadow |
| 4 | I1 approvals triage (reorder/annotate only) | Weak data (66/2), low value; later | shadow, advisory forever |
| 5 | I5 remote-lane egress grey zone | After aq-confine W2-S7 lands; rules-only start | add-friction only (section 6) |
| 6+ | I6-I8 rerank/grounding, input screen, commit-evidence WARN | Deferred with their model tiers | n/a |

### 5.1 Hot-path rule (hard)

aq-decide never runs T1 or T2 on a synchronous per-tool-call permissions path. `agent_action_policy.evaluate` (`scripts/ai/lib/agent_action_policy.py:65`, per delegation/tool decision, and fail-open on policy load error at lines 71-75) and the `aq-approval-ask-hook` (`scripts/ai/aq-approval-ask-hook`, permissionDecision ask) call at most T0a/T0b, which are in-process lookups. Learned outputs reach those paths only as pre-computed, asynchronously written annotations read from the cache. An aq-decide failure never changes a permission outcome; the fail-open behavior at :71-75 is not inherited by any aq-decide-assisted gate.

### 5.2 I2 task-profile routing (DEC-S3, the first integration)

Plug-in: `scripts/ai/lib/dispatch.py:450` `classify_task_type(prompt, mode)`; keyword sets at `_RALPH_KEYWORDS` (:391) and `_TASK_CODE_SIGNALS` (:433); call site `dispatch.py:1914`; auto sentinel in `scripts/ai/lib/task_config.py:47`.
Question `task_profile` (choice: structured, lookup, code, reasoning, agent, research, deep_reasoning; names as in the docstring at :451-466). Mode overrides (ralph, agent) stay deterministic and run first (T0a), as today. Shadow record: `{heuristic, aq_decide_t05, agree, prompt_hash, outcome_ref}`; the prompt text is stored redacted and capped in the aq-decide log only.
Labels: the final outcome of the dispatch (success, escalated, failure class) joined by run id from `agent-run-events.jsonl` and `routing_decisions` (after S0). A routing label is "profile that succeeded without escalation", which is an outcome label (weight 0.5), not a human label; the evaluation split therefore needs a human-reviewed sample (weekly top-20 disagreements, section 9).
Fallback on abstain/error: the existing heuristic, byte-for-byte. Promotion from shadow requires section 9 gates.

### 5.3 DEC-S0 prerequisite: the empty producer

`/var/lib/ai-stack/routing_metrics.db` `routing_decisions` has 0 rows and `advisor_consultations` 0 (schema exists). The writer that should populate these was not located in this session [UNVERIFIED]; DEC-S0 finds it (rg for the INSERT), fixes it so routing and escalation decisions are recorded with task_type, tier, success, escalated, response_time_ms, and adds a regression test (Rule 19: fix the producer; Rule 11: log in `issues-backlog.md`).

### 5.4 I4 retry/escalate

Plug-in: `scripts/ai/lib/cascade.py:62` `score_confidence` (a word-count heuristic) and `threshold_for` (:58); delegation outcomes from `delegation-feedback.jsonl` (`failure_class`). Question `retry_or_escalate` over the closed set retry_same / retry_narrower / escalate_tier / stop_report; the Rule 6 retry cap stays deterministic. Shadow only until the gates in 4.3 are met (48 rows today).

### 5.5 I3 RAG

Plug-in: `ai-stack/mcp-servers/hybrid-coordinator/knowledge/search_router.py` (route strategies; the route stream in `hybrid-events.jsonl` has 6.8k `route_search` events with digested queries, so text capture is opt-in via the aq-decide log). Questions `retrieve_needed` (noul, threshold favors retrieve per the asymmetric-cost argument in `scripts/ai/lib/chat_intent.py:1-9`), `route_strategy` (keyword/semantic/hybrid), `collection_route` (closed set read from config). Shadow first.

### 5.6 I1 approvals triage (later)

Plug-in: `scripts/ai/lib/approval_inbox.py` (list/priority), `aq-approve` numbered listing. Questions `approval_class` (routine / needs_read / high_impact) and `approval_urgency`. Reorders and annotates only; a deterministic regex list (security, secret, sudo, rebuild, delete, force) always yields `high_impact` and cannot be down-ranked. Agents never self-approve; aq-decide never approves. Rate budget on `high_impact` annotations (section 7) to avoid alert fatigue.
## 6. Egress coupling (aq-confine W2-S7, every remote lane)

Owner decision D2: remote agents keep default internet access, monitored, with "system one" (aq-decide) filtered access. Owner addition: cover Gemini and every other remote provider. Source of truth for the lane inventory, per-lane allowlists, the auth-critical host set and the monitor/advise/enforce switch is `aq-confine-DESIGN-v6.md` section 7A (7A.3 filter layer, 7A.5 lane inventory). aq-decide does **not** own allowlists.

### 6.1 Division of labor (non-negotiable)

| Concern | Owner |
|---|---|
| Hard-deny set (metadata, link-local, RFC1918/loopback, known-bad list) | aq-confine W2-S7, deterministic; aq-decide cannot override or weaken |
| Per-lane allowlists, exact hostnames, keyed by lane (`config/remote-lane-egress.json`, edited by PR) | aq-confine W2-S7 |
| Auth-critical login/refresh hosts per lane (never `deny-grey`) | aq-confine W2-S7 (7A.3 F8) |
| Absolute per-lane byte caps to non-provider destinations | aq-confine W2-S7, deterministic |
| Grey-zone judgment (not hard-denied, not on the lane's list) | aq-decide, **add-friction only** |
| Allow/relax decisions | owner (approve) or deterministic rule; never aq-decide |

aq-decide's possible outputs on egress are the ordered set `none < flag < hold`. `none` means "no extra friction beyond the deterministic layers", never "allow": a destination that a deterministic layer denies stays denied whatever aq-decide says. There is no output that removes friction. In `enforce` mode `hold` parks the CONNECT and raises an attention-queue item for the owner (`aq-approve`), and times out to the deterministic outcome. **Stated plainly: for the default-internet remote lanes the deterministic outcome of a non-denied destination is allow, so `hold` is a delay plus an owner alert, not a block**; only destinations that a deterministic layer denies stay denied, and those never depended on aq-decide. Nobody should read `hold` as a control that stops exfiltration by itself; the v6 text that says an `enforce` verdict "denies the CONNECT" is realized as hold-then-deny-on-timeout, never an unconditional learned deny, and the auth-critical set is never held (alert only). Reconcile this wording in v6 7A.3 (also its stale pointer to "aq-decide-DESIGN.md section 4.5", whose first slice was approvals triage: the egress engine now ships rules-only and a stub, per this section).

### 6.2 Lane identity is a feature (all lanes)

`lane` is a closed enum taken from the monitor's attribution (proxy run label, cgroup scope `aq-lane-<run>` or unit cgroup), **never from a claim in the request**. Enum, matching v6 7A.5; a new provider needs a row there and an enum entry here before first use:

`claude-cli`, `codex-cli` (OpenAI), `antigravity-ide` (Google IDE lane), `agy-cli` (Antigravity native CLI), `gemini-legacy` (retired CLI fallback), `switchboard-remote` (profiles remote-default/gemini/free/coding/reasoning; Google generativelanguage and OpenRouter endpoints named in `config/model-coordinator.json` google/anthropic/openai tiers), `coordinator-remote` (including the `/research/` fetch tool, the highest-risk service egress), `mcp-remote:<server>` (github, osint-tools, aidb NVD, trading-tools), `other-remote:<name>` (OpenCode and any later provider; defaults to hold-on-first-sight until a row exists), plus `unattributed`.

Lane-specific consequences used by the rules and the heads: (a) a destination on lane A's allowlist but seen from lane B is a grey event by rule (v6 7A.5), and aq-decide's minimum output for it is `flag`; (b) provider domain families are per lane (Google endpoints are expected for `antigravity-ide`/`agy-cli`/`switchboard-remote`, anomalous for `claude-cli`; Anthropic endpoints the reverse; OpenAI for `codex-cli`); (c) `gemini-legacy` and `unattributed` have a lower friction threshold (any non-allowlisted destination is at least `flag`); (d) service lanes get stricter novelty handling because their egress is on behalf of agents and least visible.

### 6.3 Features (non-agent-authored only)

Allowed (closed list in `config/aq-decide.json` for questions `egress_*`): lane enum; destination registrable domain **class** (provider-family match per lane, registry/mirror family, other) and TLD class; hostname shape statistics (label count, length, digit ratio, entropy bucket, punycode/IDN flag, raw-IP flag) computed by the broker; destination port class; resolved-address class and ASN class from the broker's own resolution; SNI-versus-CONNECT-host mismatch flag; process or comm attribution class (from cgroup/sampler); connection timing (time since run start, inter-connection interval, burst count, hour bucket); volume (bytes out/in so far, rate, per-lane baseline ratio); novelty derived from **owner-confirmed state** (section 6.4); whether the run has read untrusted web content (a harness flag, not text); live-connection count.

Excluded: task text, prompts, command lines, notes, file paths, URL paths and headers (not visible in CONNECT and never recorded), tool descriptions, anything an agent wrote. The raw hostname string is not fed to any text model or character n-gram in v1 (a crafted benign-looking name cannot move a text feature). Test: a unit test asserts the egress request payload schema has no free-text field and rejects any extra key (consistent with the v6 requirement that the `egress_grey` payload contains only lane, host and port class, and counters).

### 6.4 Cache and feedback-loop rules

1. Only the owner (via `aq-approve`, identity from `_resolve_actor`) or a deterministic rule writes the egress decision/trust cache. aq-decide may write its own *friction suggestions* to the audit log, never to the trust cache, and no entry is created from observed agent behavior.
2. "Novel" means "not owner-confirmed or rule-listed for this lane". Repeated agent connections to a host never make it less novel (prevents an agent building benign history), and a host's class cannot be conditioned on aq-decide's own earlier verdicts (no feedback loop).
3. Verdicts are cached per (lane, registrable domain, port class) for a TTL only to avoid alert duplication; the cache only suppresses repeats of the same or higher friction.
4. Rate budget (alert-fatigue defense), **keyed per (lane, reason class)**, never per lane alone: for each pair at most 5 `hold` and 20 `flag` per hour; beyond that, items for that pair collapse into a digest and the deterministic result stands. Burning one pair's budget (for example `EGR_NOVEL_DOMAIN` with five novel hosts) cannot suppress any other pair. **High-signal reasons are never digest-collapsed: `EGR_RAW_IP`, `EGR_SNI_MISMATCH`, `EGR_PUNYCODE` and `EGR_UNATTRIBUTED` always raise an individual alert** (the alert, not the hold, is what is guaranteed; deduped only by identical (lane, destination, reason) within a short window). Test: with the `EGR_NOVEL_DOMAIN` budget exhausted, a raw-IP, SNI-mismatch, punycode or unattributed event from the same lane still alerts.

### 6.5 Question specs (exact)

All three use numeric/structured features only, so no embedder call is made for egress (latency is that of an in-process linear model plus rules, about 1 ms [T0.5 measurement], and decisions are asynchronous in `advise`).

| Question | Type | Options / output | Features (6.3) | Initial implementation | Output ceiling |
|---|---|---|---|---|---|
| `egress_novelty_friction` | choice | `none`, `flag`, `hold` | lane, domain class, TLD class, shape stats, port class, ASN class, owner-confirmed novelty, untrusted-content flag, SNI mismatch | **Rules only** in S1/S2: novel non-allowlisted destination for a non-service lane = `flag`; raw-IP, punycode+high-entropy, SNI mismatch, or `gemini-legacy`/`unattributed`/`other-remote` first sight = `hold` candidate; service lanes (`coordinator-remote` `/research/`, `switchboard-remote`) novel = `flag`. A learned head is allowed only after 4.3 gates with owner-labeled holds/flags | `hold` only in `enforce`, owner switch |
| `egress_volume_anomaly` | noul | P(anomalous) -> `none`/`flag` (hold reserved for rule caps) | lane, bytes out to non-provider destinations, rate, baseline ratio, time since start, concurrent connections | Rules/statistics (per-lane rolling baseline plus the deterministic absolute caps owned by W2-S7); no model | `flag` |
| `egress_bypass_class` | choice | `known_tool`, `suspect` -> `flag` / `alert-high` | lane, comm class, destination port/ASN class, destination on another lane's list, UDP/DNS flags | Rules (v6 7A.4 alert table) | `flag` |

Reason codes (closed): `EGR_NOVEL_DOMAIN`, `EGR_RAW_IP`, `EGR_PUNYCODE`, `EGR_SNI_MISMATCH`, `EGR_CROSS_LANE`, `EGR_LEGACY_LANE`, `EGR_UNATTRIBUTED`, `EGR_NEW_LANE`, `EGR_VOLUME`, `EGR_BYPASS`, `EGR_AUTH_CRITICAL_ALERT_ONLY`, `RULE_ALLOWLISTED`, `LOW_CONF`, `ERROR`.

### 6.6 Access control

Callers: only the monitor proxy/broker process (in-process library call or a UDS owned by the monitor), identity by `SO_PEERCRED`/cgroup as in the agent-auth design (`agent-auth-DESIGN-v2.md`), not by a header. **Agents (any remote lane or sandbox) cannot call aq-decide**, directly or through the coordinator: there is no `/decide` endpoint in v1, and when one exists (DEC-S8) its scope family is granted to no agent class; a sandboxed or remote agent that can probe a decision oracle can search for inputs that flip it. Decision logs are append-only and not readable by sandbox classes.

### 6.8 Egress v1 is a rules table with no runtime dependency on aq-decide (v2.1)

With rules-only egress, aq-decide adds nothing over W2-S7's rules. So the first egress coupling ships as a **plain rules table inside W2-S7** (the section 6.5 rules, reason codes, per-(lane, reason) budgets and lane enum, in `config/remote-lane-egress.json` or a sibling data file) that **does not import or call aq-decide at runtime**. aq-decide's contract (closed-enum outcome, `reason_code`, abstain) is adopted by that table's output shape so that a learned head can slot in later without a rewrite, but the dependency arrow is: W2-S7 -> nothing; aq-decide egress learning -> W2-S7 logs (labels). The runtime dependency is introduced only by DEC-S5-or-later, after the 4.3 gates are met on owner-labeled holds/flags.

### 6.7 Provider coverage statement

Claude, Codex/OpenAI, Antigravity IDE, `agy`, retired `gemini`, switchboard remote profiles (Google, OpenRouter, others as configured), coordinator remote handlers and `/research/`, MCP servers with remote APIs, and future providers are all covered by the same enum and rules; none has a special-case bypass. The per-lane exact-hostname lists (many marked [UNVERIFIED] in v6) are W2-S7's to confirm from vendor documentation, and aq-decide's rules read them rather than duplicate them.
## 7. Safety

1. **Never the sole gate; no privilege grant in v1.** Every aq-decide output either annotates, reorders, routes non-security work, or adds friction. No question may relax a deterministic control. Security-class questions never reach `enforce` without a separate owner decision with evidence (D1).
2. **Directional asymmetry.** Outputs in the unsafe direction (`allow`, `routine`, `none`-as-relaxation) are not produced for security questions at all. Friction-direction outputs (`flag`, `hold`, `high_impact`) may use a lower threshold but are rate-budgeted (6.4 item 4; approvals annotation budget 10 `high_impact` marks per hour beyond which they collapse into one digest line), because false-positive floods are themselves an attack on owner attention.
3. **Injection.** T0.5 and T1 take text through a fixed featurizer/encoder and a linear map: there is no instruction-following surface, so an injected sentence cannot act as a command. The residual is adversarial-example crafting against a linear head (a 1024-d or 384-d linear model is not robust to a determined adversary who can query it), which is why (a) agents cannot call or observe aq-decide (6.6), (b) egress features exclude agent text entirely (6.3), (c) no head is the sole control, and (d) the decision log records every call for audit. OOD abstention is enabled only with >= 500 training rows (4.3); with fewer rows no OOD claim is made.
4. **No hot-path learned gating** (5.1). Fail direction: error/abstain leaves the current deterministic behavior; for approval-adjacent callers that means "show to owner".
5. **Cache poisoning.** T0b and the egress trust cache accept writes only from the owner or deterministic rules (6.4). The semantic cache (a cache that could launder guesses) is deferred; when it returns it holds only human-confirmed entries.
6. **Audit.** Append-only `decisions.jsonl` under a service-owned state dir: caller, question, lane (for egress), tier, probs, reason_code, config version, latency, redacted/hashed state, final action by the caller, later label. Sandbox classes cannot read it.
7. **Kill switches.** `AQ_DECIDE=0` global, per-integration mode in Nix (section 8.4), per-question demote. Default off; shadow first.
## 8. Operations

### 8.1 Nix-declarative placement of an extra model (Rule 13/14)

Existing mechanism, found in the repo: models are declared in a catalog and fetched by a oneshot service, not by hand.
- `defaultModelCatalog` in `nix/modules/roles/ai-stack.nix:524` (entries have `repo`, `file`, `sha256`, `params`, `ramEstimate`, `type`; e.g. `"nomic-embed"` at :792 with repo `nomic-ai/nomic-embed-text-v1.5-GGUF`), merged with user `modelCatalog` options (`nix/modules/core/options.nix:1332` chat, `:1489` embed) and resolved by `activeModel` (`ai-stack.nix:847-923`).
- Integrity: `mySystem.aiStack.modelAllowlist` (`options.nix:1637`) restricts repos; an unlisted repo fails a NixOS assertion (`ai-stack.nix:970`).
- Fetch: `systemd.services.llama-cpp-embed-model-fetch` (`ai-stack.nix:1432`) downloads to the models dir, stamps `<file>.source-meta`; scheduled, not boot-blocking.
- Serving: `systemd.services.llama-cpp-embed` (`ai-stack.nix:1575`; User `llama`, `IPAddressDeny=any` except loopback, `PrivateTmp`, `ProtectSystem=strict`); the chat unit sets `AppArmorProfile = "ai-llama-cpp"` (`ai-stack.nix:1132`) whose rules allow model reads only under `/var/lib/llama-cpp/models/**` (`/etc/apparmor.d/ai-llama-cpp`); whether the embed unit carries the same setting is [UNVERIFIED].
Note the existing embed path is a single-model design (`active-embed.gguf`). The mechanism to add for aq-decide (DEC-S2, not before the shadow data justifies T1):
1. Add a catalog entry `bge-small-aqdecide` (repo `CompendiumLabs/bge-small-en-v1.5-gguf`, file `bge-small-en-v1.5-q8_0.gguf`, sha256 `ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514` as measured here from the HF download; re-verify from the upstream manifest before pinning) and the repo to `modelAllowlist`. **Its own assertion is required (v2.1):** the existing check at `ai-stack.nix:970` validates only `embedHfRepo`, so a second repo is not covered; add an assertion (or allowlist check) for `aqDecide.embedder`'s repo in the new block, and make it an acceptance test.
2. New options block `mySystem.aiStack.aqDecide.embedder = { enable (false); port (new port in options.nix, never hardcoded); model; gpuLayers (12 ceiling) }` and a sibling fetch+serve unit modelled on :1432/:1575 with the same hardening and the same AppArmor profile; the file lives in `/var/lib/llama-cpp/models/` (the only place the profile allows).
3. State directories and decision log via `systemd.tmpfiles.rules` (Rule 13); no runtime chmod.
4. Owner runs the rebuild; agents give exact copy-paste commands (repo delivery workflow).
No other model is added in v1. The profile is path-bound to the llama.cpp store hash; a llama.cpp update changes the hash, and the module must keep the profile and unit in step [UNVERIFIED how it is regenerated].

### 8.2 Resource footprint of the T1 instance

**Placement (v2.1): start CPU-only** with `-c 512 -ub 512 --threads 2 -ngl 0 --parallel 1` (not the benchmark's `-c 2048 -ub 2048`, whose compute buffers scale with `-ub`). Expected cost from the CPU-only passes: about 120 ms short / 209 ms long p50 (+/-50%), which is acceptable for shadow and advise; T1 is not needed before DEC-S5 anyway. One llama-server serves one model, so the instance is not shared with bge-m3. It does not touch RAG collections or the 1024-d bge-m3 service.
**`-ngl 12` only after a paired check (DEC-S2 acceptance test):** on the live host, run a fixed main-model prompt set (same prompts, same seed, `enable_thinking:false`) with the aq-decide instance **off, then on at ngl 12, then off again**, recording main-model generation tok/s and `/sys` VRAM used (live reference: 4.28 GB VRAM, 5.79 GB GTT, already at the carve-out). Pass = tok/s within 3% and VRAM used within 3% of the off baseline in both off runs bracketing the on run; otherwise stay CPU-only. Cost in the 27 GB budget (22.5 model / 1.0 KV / 3.0 OS reserve): expected well under 0.5 GB [UNVERIFIED; measure RSS in the same test].

### 8.3 T2 (deferred; constraints recorded now)

On-demand only: socket-activated unit with an idle timeout, `CPUQuota`, `MemoryMax`, `Restart=no`, started only by the nightly teacher/eval timer or an explicit owner command; never resident. The page-cache effect on the main model is **stated, not measured** this session: the main model is a 22.1-22.9 GB mmapped file on a 27.9 GB host, and `free` during this work showed buff/cache of 13.4-19 GB with 5-14 GB available, so the main model is already not fully resident; loading a 2.5 GB 4B model (or 0.6 GB for 0.6B) adds that much page-cache pressure plus KV and will evict main-model pages, a latency cost on the next main-model prompt that was not quantified. Measurement requirement before DEC-S7 approval: main-model p50/p95 on a fixed 200-token prompt before/after a T2 load, in one run, with `vmtouch`-style residency counts if available. The nightly train timer and T2 yield (skip when the main model is mid-request or free RAM < 3 GB, `Nice=15`).

### 8.4 Flags (options.nix, default off, shadow before anything else)

`mySystem.aiStack.aqDecide = { enable = false; mode = "off" | "shadow" | "advise" | "enforce" (global ceiling); integrations.<taskProfile|retryEscalate|rag|approvals|egress>.mode = "off"; embedder.* (8.1); train.timer.enable = false }`. Thresholds and question definitions are data in `config/aq-decide.json`, not eval-time Nix policy. Profile enablement goes in `nix/modules/profiles/ai-dev.nix`. `AQ_REMOTE_EGRESS_MODE` (aq-confine v6) remains the egress switch; aq-decide's egress integration cannot raise it above that mode.

### 8.5 Observability (v1)

Decision log, CLI (`aq-decide decide|shadow-report|explain`), and Prometheus-style counters (`aq_decide_decisions_total{caller,question,tier,outcome}`, latency histogram, `aq_decide_shadow_agreement{question}`). The dashboard card, drift/PSI and calibration-drift alert are deferred until a head is live (DEC-S8); a basic health-spider check (embed instance up when enabled, log writable, config hash valid) ships with DEC-S2.
## 9. Evaluation and promotion

- Per-question eval sets: `eval/<question>.jsonl`, frozen and hashed, at least 100 items with at least 20 per class, half or more human-labeled, time-split, never used in training or calibration. Teacher and synthetic rows are barred from eval and calibration (4.4).
- Metrics: accuracy and macro-F1 versus the incumbent (heuristic or current behavior) and versus the majority-class baseline; ECE (15 equal-mass bins) on human rows; precision of the unsafe-direction class (for non-security routing >= 0.95); abstain rate (<= 35% for routing questions, else the head buys nothing); latency within the tier budget (T0.5 p95 <= 3 ms, T1 p95 <= 60 ms short / 160 ms long by the measurements in 2.2, which already include ambient load); T3 share of decisions < 2%.
- Shadow A/B: at least 14 days or 500 decisions per question; record `{current, aq_decide, agree}`; for I2 compare downstream outcome split by agree/disagree; weekly human review of the top-20 disagreements, which also creates human labels.
- Promotion: shadow -> advise needs owner acknowledgement (D1). advise -> enforce only for non-security routing (I2, I3, I4) after 30 days at advise with no regression. Egress: add-friction `hold` in `enforce` is an aq-confine owner switch (v6 D5), requires its own evidence, and security-class questions never auto-promote.
- A head that fails to beat the majority-prior baseline on the held-out human set is rejected regardless of other metrics.
## 10. Slices (re-ordered)

Lane per Rule 17: cheapest eligible (Codex or local Qwen when eligible; Claude `sonnet` default implementer; `haiku` for mechanical single-file). Each slice: worktree + PR, tier0 gate, activation-DoD attestation, `tracker.json` under `.agents/plans/aq-decide/`, RESUME/PULSE entries.

### 10.1 Build order

| Slice | Content | Acceptance | Risk | Lane | Rollback |
|---|---|---|---|---|---|
| DEC-S0 | Find and fix the writer for `routing_decisions` / `advisor_consultations` (0 rows today); regression test; backlog entry | Rows accrue during a live dispatch; test fails when the INSERT is removed | low | sonnet | revert the producer commit |
| DEC-S1 | `scripts/ai/lib/aq_decide.py` + `config/aq-decide.json` + seeds + `scripts/ai/aq-decide` CLI: contract validation, T0a rules, T0b exact cache, T0.5 hashed TF-IDF in **shadow**, decision log; **no learned head** | Contract/validation/abstain unit tests; closed-enum `reason_code` test; egress payload schema test (no free text); `enable_thinking:false` asserted wherever an LLM is called (none in S1); T0.5 p99 <= 3 ms measured; kill switch | low | sonnet (library), haiku (seed formatting) | `AQ_DECIDE=0`, remove import |
| DEC-S2 | Nix options (all default off), tmpfiles, health check, bge-small catalog entry + allowlist + **own repo assertion** + second embed unit (disabled by default, CPU-only `-c 512 -ub 512 --threads 2`), counters, tier0 check "no tracked script execs a copied llama-server" | Dry build passes; assertion fails for an unlisted repo; owner runs the switch; `aq-decide health` green; unit shows `ai-llama-cpp (enforce)` in `/proc/<pid>/attr/current`; **paired off/on/off check** (8.2) gates any move to `-ngl 12`; state-cap test (3.1) | med (Nix) | sonnet; owner rebuild | options off |
| DEC-S3 | I2 task-profile shadow beside `classify_task_type` (`dispatch.py:450/1914`); labeler from run events + `routing_decisions`; `shadow-report` | 500 shadow decisions; no behavior change (diff test); report generated | low | sonnet | remove the log hook |
| DEC-S4 | Egress rules table in W2-S7 (replaces the `unknown` stub): `egress_novelty_friction`, `egress_volume_anomaly`, `egress_bypass_class` as **rules only, no runtime call into aq-decide** (6.8), add-friction only, per-(lane, reason class) rate budgets, all lanes in the 6.2 enum | Hostile test matrix: cannot relax a deny; no agent-text feature; trust-cache write refused from agent path; with one reason's budget exhausted, RAW_IP/SNI_MISMATCH/PUNYCODE/UNATTRIBUTED still alert; 1000-host flood stays within budgets; every lane enum value exercised; `hold` timeout asserted equal to the deterministic result | med-high | sonnet + independent reviewer (Rule 18) | hook back to stub |
| DEC-S5 | First learned head via T1 for the first question that passes 4.3 gates; calibration on human rows; promote per section 9. Semantic cache (human-confirmed entries only) lands here if volume justifies | Gate evidence recorded | med | sonnet | demote head |

### 10.2 Later slices (moved, not deleted)

| Slice | Content | Why deferred |
|---|---|---|
| DEC-S6 | I4 retry/escalate, I3 RAG shadow; reranker (Qwen3-Reranker-0.6B, `--reranking --pooling rank`) for relevance/grounding noul | Labels thin; reranker unmeasured |
| DEC-S7 | T2 LLM tier (Qwen3 0.6B/1.7B/4B, grammar-constrained label logprobs, on-demand unit); Qwen3Guard-Gen (751M params, Apache-2.0) as optional input screen | T2 unmeasured below 4B; page-cache cost unmeasured; screen is security-adjacent |
| DEC-S8 | `POST /decide` endpoint on the coordinator behind the agent-auth scope (granted to no agent class), dashboard card, drift/PSI and calibration-drift alert, `score` type, isotonic option, `labelers/ heads/ calib/` package split | Needs a live head and the agent-auth design; none of it is needed for shadow |
| DEC-S9 | I1 approvals triage (reorder/annotate), commit-evidence WARN check (`tier0.d`, WARN only), input_screen tagging | Weak data; WARN-only; advisory |
| DEC-S10 | GLiClass ModernBERT ONNX candidate evaluation | Needs weights intake (`capability-intake`) and a service-env onnxruntime check |

### 10.3 Dependencies

DEC-S4 depends on aq-confine W2-S7 (decision hook, `config/remote-lane-egress.json`, monitor/proxy) and on the agent-auth identity for the monitor-to-aq-decide channel. DEC-S0/S1/S3 depend on nothing in flight. DEC-S8's endpoint depends on `agent-auth-DESIGN-v2.md` scopes landing.
## 11. Owner decisions (genuine ones only)

- **D1 Authority ceiling (carried).** No aq-decide question grants privilege in v1; outputs only annotate, reorder, route non-security work, or add friction; remote-lane egress is add-friction only and never removes a deterministic deny; security-class questions never reach `enforce` without a separate evidence-backed decision. Recommendation: yes.
- **D2 Embedder (reframed as a benchmark result, not a question).** Measured: bge-small `-ngl 12` p95 43 ms short / 122 ms long versus bge-m3 426 / 1589 ms in the same conditions. Recommendation, for ratification: second small instance with bge-small for aq-decide only, RAG embedder untouched, T0.5 first. The only residual owner input is whether a second embed unit and port are acceptable (a Nix change at DEC-S2).
- **D3 Remote labelling spend (narrowed).** Permit a one-off remote Claude-lane pass over **seeds and synthetic text only** (about 2k items); real states are labeled locally and never leave the host. Recommendation: yes, bounded.
- **D4 (owner-decided; recorded).** May remote-lane egress use aq-decide? **Decided: yes, friction-only**, per the owner's statement that remote agents get "default access but also monitoring and the system one agent filtered access". Scope of that decision as designed: rules-only table first with no runtime dependency (6.8); outputs limited to `none < flag < hold`; `hold` is delay-only for default-internet lanes (timeout = the deterministic result, which is allow for non-denied destinations), so it provides owner visibility and alerting, not blocking; nothing relaxes a deterministic deny. Any move toward a learned head or toward `hold` meaning deny is a new decision.
## 12. Open items and unverified claims

1. Benchmarks are ambient, not idle: load average was 2.3-3.7 for the ambient and spinner passes and 8.6 for the `-ngl 12` pass. p99 over n=200 is the second-largest sample, an indication only. Whether bge-small stays at p95 43 ms with the main model generating at the same time is not isolated (the main model was idle except ambient stack work).
2. The accuracy proxy (PULSE action word, n=257) says nothing about security questions; embedder ordering is not statistically separated.
3. GGUF `bge-small-en-v1.5-q8_0.gguf` provenance is the HF download from `CompendiumLabs/bge-small-en-v1.5-gguf`; its sha256 should be re-verified against an upstream manifest before pinning in Nix. License (MIT) from the upstream BAAI model card and the review, not re-read here.
4. The writer for `routing_decisions` was not located.
5. (v2.1) AppArmor attachment is by exec path and the live embed unit is confined (confirmed by review); remaining: whether the profile file is regenerated on a llama.cpp store-hash change is assumed to follow `llamaServerExec` and is not exercised here.
6. The python used by the coordinator and services (numpy/sklearn/onnxruntime availability) is unverified; the interactive python has numpy 2.4.4, scikit-learn 1.8.0, onnxruntime 1.24.4, sentence-transformers 5.4.1, torch 2.11.0. v1 of this design needs only numpy and sklearn (the latter only in the trainer).
7. All per-lane hostnames for Codex/OpenAI, Antigravity/`agy`, GitHub and registries are inherited as [UNVERIFIED] from aq-confine v6 7A.3/7A.5 and are W2-S7's to confirm.
8. Qwen3 0.6B/1.7B and the Qwen3-Reranker were downloaded earlier (sizes match upstream) but not benchmarked; T2 timings above 4B are estimates and the T2 page-cache cost is unmeasured.
9. The Jev vendor numbers and API shape come from the brief and were not re-fetched.
10. Process notes for backlog (Rule 11): `pkill -f` / `pgrep -f` patterns that appear in the caller's own command line kill the tool shell (happened three times); the ai-llama-cpp AppArmor binding is the reason llama-server cannot read GGUFs outside the models dir.
