---
doc_type: research
title: DeepSeek Harness (dsh) — full parity comparison vs our AQ local-agent harness
status: draft
owner: hyperd
date: 2026-08-20
sources:
  - https://github.com/deepseek-ai/deepseek-harness (MIT, released 2026-08-13; ~175k stars)
  - docs/{architecture,agent-lifecycle,tool-execution-pipeline,capability-seams,defensive-patterns,config-catalog,persistence-catalog,compaction}.md
---

# DeepSeek Harness (dsh) vs AQ harness — full parity check

**What dsh is:** a TypeScript, MIT-licensed, plugin-everything agentic coding harness built on the
**Cordis** plugin framework. Every part — model adapter, tool registry, session log, the agent loop
itself — is a swappable plugin contributing services + typed events + reversible effects to a shared
context. Ships `dsh-base` / `dsh-web-app` / `dsh-headless` bundles; four run modes (Standard, **PTC =
Programmatic Tool Calling**, Minimal, Creation). `npx @deepseek-ai/dsh web` → browser UI on :3080.

**Stack reality:** dsh is TS/npm/browser; we are Python + Nix + shell + llama.cpp, local-first on an
APU. So we adopt **patterns/tactics/configs**, not code. This is a design-parity check, not a port.

## Dimension-by-dimension parity

| # | Dimension | dsh | AQ (us) | Verdict |
|---|---|---|---|---|
| 1 | **Extensibility model** | Cordis plugin tree; everything a plugin; reversible effects that unwind on unload; profiles+bundles; `cordis.patch.yml` runtime-patchable | NixOS flake modules + Python services + MCP servers; profile-driven feature flags (`ai-dev.nix`); env/Nix-options config | **dsh ahead on runtime swappability.** Ours is declarative/reproducible but not hot-swappable at the loop/tool/adapter granularity. |
| 2 | **Agent loop** | Explicit **turn/step** model; event-driven (durable `session/event` + live `agent/*`); **hook waterfalls** at every seam: `pre-step`, `request-error` (retry), `turn-stopping` | `agent_executor._execute_with_tools` monolithic loop; our re-read / no-action / edit-feedback guards are **inline bolted-on** ifs | **dsh ahead (architecture).** Their hook/waterfall seams are exactly where our interventions belong as first-class, composable, testable units. **Top adopt.** |
| 3 | **Tool calling** | **Two modes**: JSON envelope AND **PTC (model writes CODE that calls tools)**. Pipeline: `tools/pre-execute` → monotonic guards (deny/abstain) → one-shot `ctx.approval` → `tools/execute` (timeout/retry/metrics) → body → `fs/write-intent`/`fs/edit-intent` gates → `tools/post-execute` → `finalizeContent` → `tools/result` | JSON envelope + **GBNF grammar** (just fixed); single mode; inline read_file gate + no-commit + edit-feedback | **Mixed.** We just proved JSON+grammar is fragile on weak local models. **PTC is the single most interesting thing to evaluate** (see Rec 1). Their pipeline structure > our inline checks. |
| 4 | **Context / compaction** | Compaction **seam**: token-pressure summarizer (`compaction-basic`) + **model-free tool-result pruner** + `token-meter` | Pinned+sliding prune + **semantic scratchpad** (embed+Qdrant recall) + assembler front-load + read_file gate | **~Parity; we arguably lead** on retrieval-augmented context. Their model-free tool-result pruner is a cheap complement worth stealing. |
| 5 | **Sessions / persistence** | **Append-only `SessionEvent` log** as the spine (durable, replayable) + `session-persistence` (jsonl/sqlite) + `session-query-sqlite` | `PULSE.log` + `RESUME.json` + `steps.jsonl` + delegation outputs + AIDB/Qdrant; **`aq-event`** append-only log exists but isn't THE substrate | **dsh cleaner (event-sourced spine).** We have the primitive (`aq-event`) — not wired as the session substrate. Medium adopt. |
| 6 | **Capability / security** | Capability seams (`fs/*`,`tools/*`,`telemetry/*`); monotonic guards; one-shot approval; **`acp` (approval control plane)**; sandbox; credentials seam; **scrubbed env** (drop `*KEY*/*SECRET*/*TOKEN*/*PASSWORD*`) for spawned cmds; 0700 temp dirs; identity | **CapabilityLease (Foundation C)** + **ACP (we're building it)** + AppArmor + SOPS→/run/secrets + sandbox | **~Parity; we lead on substrate** (AppArmor+SOPS+Nix). Convergent ACP validates our direction. Steal: scrubbed-env + fs-intent gates + 0700-temp discipline. |
| 7 | **Defensive patterns** | Documented hard-won bug-class rules: report orthogonal outcomes independently; normalize contracts on both sides; async≠sync state; dispose-to-quiescence; contain callback exceptions; unlink link-shaped paths | `.agent/PROMOTED-BUG-PATTERNS.md` (35+); issues-backlog; WORKAROUND-REGISTER | **Both strong.** Cross-reference theirs into ours — several are new to us (orthogonal-outcome reporting, dispose-to-quiescence). Low-medium adopt. |
| 8 | **Sub-agents / interop** | External agents as plugins: `hooks-claude-code`, `hooks-codex`, `subagent-inprocess` | `delegate-to-{claude,codex,gemini,local}` + Agent tool + `aq-collab-round` | **~Parity**, different framing (plugin vs lane). We're richer on multi-lane consensus + catch-up queue. |
| 9 | **Local-model tuning** | `llm` adapter seam (`llm-deepseek`, `llm-pi-ai`, `llm-replay`); "run any model" via custom providers | llama.cpp direct; `build_llama_payload` SSOT; TASK_PROFILES; **enable_thinking/thinking_budget**; **GBNF**; APU ceilings | **We lead for edge/local.** Deeper APU/weak-model tuning. Their adapter-seam cleanliness is worth mirroring in `llm_config`. |
| 10 | **Governance / honesty** | Standard testing docs | **Activation Gate / Definition-of-Done**, honest PM projection, anti-gaming, agent-parity rules | **We lead.** No dsh equivalent to our activation/honesty governance. |

## What THEY have that we should adopt (ranked)

1. **PTC — Programmatic Tool Calling (evaluate hard).** The model writes *code* that calls tools
   instead of emitting a JSON envelope. Our entire recent session was a fight to get a weak local
   model to emit valid tool-call JSON (grammar bug, truncation, narrate-vs-act). A code-trained model
   may be *more* reliable writing `read_file("x"); edit_file(...)` than nested JSON — OR not. This is a
   **direct candidate fix for our local-agent reliability problem** and must be A/B-tested against our
   fixed-grammar baseline (~21% + edit-feedback). If PTC lifts the local rate, it's a bigger lever than
   any of our loop interventions.
2. **Formalize the loop as hook/waterfall seams** (`pre-step`, `request-error`, `turn-stopping`,
   `tools/pre|post-execute`). Our re-read / no-action / edit-feedback guards are inline ifs bolted into
   `_execute_with_tools`. Refactor them into a small hook pipeline so they're composable + testable +
   individually toggleable — and future guards mount beside them instead of editing the loop.
3. **`fs/write-intent` + `fs/edit-intent` gate pattern** — a clean, uniform seam for all filesystem
   mutations. Maps to our read_file gate + no-commit guard, but as ONE choke point every write flows
   through (approval, sandbox, no-commit, audit) instead of scattered checks.
4. **Model-free tool-result pruner** — cheap context relief (drop stale tool results without a model
   call), complements our semantic scratchpad.
5. **Event-sourced session spine** — wire `aq-event` as THE durable session log (we have the
   primitive), with jsonl/sqlite projections, instead of the current PULSE/RESUME/steps sprawl.
6. **Scrubbed-env for spawned commands** — drop `*KEY*/*SECRET*/*TOKEN*/*PASSWORD*` from the env of
   any subprocess so harness creds can't leak into tool output/spill files. Cheap, high-value hardening.
7. **Cross-reference their defensive patterns** into `PROMOTED-BUG-PATTERNS.md` (orthogonal-outcome
   reporting; dispose-to-quiescence; contain-callback-exceptions).

## What WE have that they don't (keep / don't regress)

- Deep **edge/weak-local tuning**: APU ceilings, `enable_thinking`/`thinking_budget`, GBNF, per-profile
  payloads — dsh is general-purpose, not edge-optimized.
- **NixOS declarative reproducibility** + AppArmor + SOPS secret substrate.
- **Retrieval-augmented context** (assembler + embed + Qdrant) beyond token-pressure summarization.
- **Activation-Gate / Definition-of-Done governance + honest PM projection + anti-gaming** — no dsh
  analog; this is our differentiator.
- **Multi-lane consensus + catch-up queue + agent-agnostic role routing.**

## Bottom line

We are at rough architectural parity, **ahead** on security substrate, edge/local tuning, retrieval
context, and governance; **behind** on runtime plug-swappability and loop-hook cleanliness. The single
highest-value import is **PTC as an A/B against our fixed tool-call path** — it targets the exact
local-reliability problem we've been grinding. Second is **refactoring our interventions into a hook
pipeline** (their turn/step/hook model). Neither requires adopting Cordis or TS; both are patterns we
implement in our Python loop. Recommend: (a) spike PTC for local behind an env flag and A/B it; (b)
lift the fs-intent gate + scrubbed-env hardening now (cheap, safe); (c) fold their defensive patterns
into our bug-pattern doc.

## Critical analysis: is "everything is a plugin" true, and is it effective?

### Is the claim TRUE? — Mostly, with an honest asterisk: it's a **microkernel**, not turtles-all-the-way-down.
"Everything is a plugin" holds *above* one fixed, privileged layer: **Cordis** — the DI container
(`ctx.<key>` service registry), the typed event bus (`emit`/`waterfall`/`parallel`/`serial`), and the
reversible-effect machinery (`ctx.effect()`/`ctx.on()`). Cordis itself is NOT a plugin; it's the kernel
every plugin is written against. So the accurate statement is: **"there is no privileged *application*
core — the loop, tools, adapters, and session log are all plugins — but there is a privileged
*framework* core (Cordis)."** This is the classic **microkernel + DI** pattern, well executed, not a
novel paradigm. Two further asterisks: (a) the capability-seams doc itself grades services as "core
spine" vs "swappable seam" vs "composition point" — so swappability is a *spectrum*, not uniform; (b)
`dsh-base` is a mandatory first layer of every profile. Verdict: **claim is essentially true and
honestly scoped in their own docs — but "everything" means "everything above Cordis," and not all
plugins are equally replaceable.**

### Is it EFFECTIVE? — Yes for them, largely over-engineered for us, with one part worth stealing.

**Real benefits (genuine, not marketing):**
- *One uniform extension mechanism* — add/replace anything by mounting a plugin; `inject` expresses
  load order via dependencies instead of manual boot sequencing. Lowers cognitive load *after* the
  Cordis learning curve.
- *Reversible effects* — registrations unwind cleanly on unload (no orphaned listeners/registrations).
  This is real engineering value and directly powers their "dispose to quiescence" defensive pattern.
- *Config-driven composition* — swap the agent loop or model adapter from a profile/patch with no code
  change; they explicitly use this for **benchmarking** different loops/adapters. Legitimately useful.
- *Isolation/testability* + clean external-agent interop (Claude Code/Codex as plugins).

**Real costs (the effectiveness caveats):**
- *Indirection tax* — every flow crosses the service/event bus + waterfalls; you can't just read a
  function. Their own docs say "use an agent to explore the codebase," and a whole `defensive-patterns.md`
  exists because cross-plugin waterfalls breed subtle bugs (callback-exception containment, async≠sync
  state). Emergent behavior is harder to reason about than a straight loop.
- *Kernel lock-in* — you must learn Cordis before touching anything; the entire harness's ceiling is
  Cordis's abstractions.
- *Over-generalization / YAGNI* — making the agent **loop itself** a plugin is powerful but almost
  nobody swaps it; everyone pays the abstraction cost for flexibility few exercise.
- *Runtime overhead* — event dispatch + effect tracking + waterfall middleware cost cycles vs direct
  calls. Marginal on a cloud box; **non-trivial on our APU** where we count tokens and ms.

**Effectiveness verdict — for THEM:** strong fit. A general-purpose, cloud, browser-UI coding agent
whose value proposition IS extensibility/interop/benchmarking. The indirection buys exactly what their
users want; 175k stars says the DX lands.

**Effectiveness verdict — for US:** mostly a poor fit as a wholesale model, because **our bottleneck is
local-model reliability, not extensibility.** A plugin bus does not make Qwen emit valid tool calls;
our wins this cycle came from fixing a *grammar*, a *token budget*, and a *prompt* — concrete config,
not architecture. We already get declarative composition from **Nix** (our "config-driven" layer) and
per-profile payloads from `llm_config` — without a runtime plugin kernel or its APU overhead. Adopting
Cordis-style everything-is-a-plugin would add indirection, onboarding cost, and latency to solve a
flexibility problem we don't have, while doing nothing for the reliability problem we do.

**The one part worth stealing (already Rec 2 above):** the **hook/waterfall SEAMS** on the loop
(`pre-step`, `request-error`, `turn-stopping`, `tools/pre|post-execute`). That single pattern — not the
whole microkernel — is what cleanly homes our re-read/no-action/edit-feedback interventions. We can
implement a tiny, explicit hook-list in our Python loop and get 80% of the architectural benefit for
~1% of the complexity, with zero Cordis/TS dependency and no runtime-plugin overhead.

**Net:** "Everything is a plugin" is a real, competently-built microkernel — an honest claim once you
read "everything" as "everything above Cordis." It's effective for a general extensible harness and
mostly over-engineered for a reliability-first edge harness like ours. Take the loop-hook seam; leave
the microkernel.
