# Infinity runtime intake (2026-11-03)

## Provenance and scope

This is a bounded source review, not an implementation or independent benchmark. Primary source: [AWS Open Source Blog, “Introducing Infinity: a runtime for extreme agent concurrency”](https://aws.amazon.com/blogs/opensource/introducing-infinity-a-runtime-for-extreme-agent-concurrency/), published 2026-10-23. Official project documentation reviewed: [runtime overview](https://infinity.hydro.run/docs/infinity-runtime/overview/), [architecture](https://infinity.hydro.run/docs/infinity-runtime/architecture/), [agent runtime](https://infinity.hydro.run/docs/rap/about/agent-runtime/), [step mode](https://infinity.hydro.run/docs/infinity-runtime/agent-systems/step-mode/), [model providers](https://infinity.hydro.run/docs/infinity-runtime/model-providers/), and [Infinity Code background agents](https://infinity.hydro.run/docs/infinity-code/background-agents/).

Video metadata only: [“Amazon built a new AI agent runtime in Rust”](https://youtu.be/os5eNeAVRpc), channel Let’s Get Rusty, YouTube upload date 2026-11-02, duration 426 seconds. Retrieved with bounded `yt-dlp --skip-download --print` fields (id/title/duration/channel/upload date/URL); no transcript, audio, or video was downloaded or reviewed. The video is secondary commentary, not evidence for technical claims here.

## Verified from primary sources

- Infinity is presented as an Apache-2.0 research runtime from the AWS/UC Berkeley Hydro effort. A slice loads persisted history and processes input; asynchronous tool calls end the slice, with at most one such dispatch before the tool result returns as queued input. There is an explicit exception: synchronous tools run inline and loop back to another model completion in the same slice; unknown tool names also loop back after injecting an error result. Thread turns remain ordered while separate threads can progress concurrently.
- Turn durability has a precise boundary: streamed output is buffered and committed only when a turn completes, either with no tool call or with a tool call ending the turn. If a stream fails mid-turn, the partial buffer is discarded and the completion retries. Before dispatching a tool invocation, the runtime flushes the tool-call turn to history, so the call is durable before its result can arrive.
- The serverless architecture uses durable messages (the AWS example uses SQS FIFO and one message group per thread), stable IDs/deduplication state, and persisted histories. Model inference is supplied behind a provider interface; it is not made concurrent or faster by runtime scheduling alone.
- AWS’s “80k agents” result is a simulated-model runtime benchmark: 80,000 agent threads, 3.2 million completions, 20 turns per agent, modeled short completions/tool results, one thread on an AMD EPYC 9R14, and in-memory stores. The reported ~100 KB idle-agent memory and extrapolation to about 75,000 agents in 8 GB describe runtime state under that setup. They are **not** 80,000 simultaneously running real models, nor a measurement of real provider/model token throughput.
- Official docs also describe a local daemon and persisted coding-agent sessions. These are related persistence patterns, but do not establish that this repository already persists/resumes model turn continuations.
- Infinity Code documentation specifically says its daemon can keep busy sessions running in the background, sessions can be reloaded, and conversation history persists under `~/.infinity/` across CLI shutdown/restart. This verifies a product-level persistent-session feature in that project; it does not by itself specify crash recovery semantics for an individual in-progress completion.

## Repository fit and bounded follow-up

Existing plan `.agents/plans/frontier-evidence-intake/` already owns source-verified candidates and an append-only, deduplicated `BACKLOG.jsonl` with a CLI; its tracker goal includes adding/listing/digesting/status/seeding candidates. `.agents/plans/durable-proactive-mesh/` describes durable operational state such as journald cursors and approval/pause controls. Neither inspected plan demonstrates a persisted in-flight model turn, serialized continuation state, or replay-safe tool result queue. Do not equate a durable candidate/task record with a resumable conversation continuation.

Bounded next slice: continue under the existing frontier-evidence-intake plan. Add one provenance-backed Infinity candidate to its existing backlog/schema, map the claim to a repository measurement (e.g. runtime memory per idle task and resume correctness under injected process interruption), and keep verdict at `monitor` until a local baseline and failure/replay test are designed. First inspect whether the existing backlog CLI accepts this evidence shape; do not add a runtime dependency or start runtime implementation in this intake slice. A separate implementation plan is only warranted if the existing plan explicitly accepts an approved candidate and evidence shows a real continuation-state gap.

## Unavailable / dated deferrals

- As of 2026-11-03, no local Infinity benchmark, deployment, compatibility study, or live provider-throughput comparison was run. Deferred until an approved candidate and hardware/provider-matched measurement are available.
- Video claims beyond public metadata are unverified; transcript/video review deferred (2026-11-03).
- Repository inspection was limited to the named plan files and search results; no claim is made that all runtime/task persistence paths were exhaustively inventoried.

## Source details

- Infinity architecture, “Turns and durability” and “Synchronous tools loop back” (accessed 2026-11-04): https://infinity.hydro.run/docs/infinity-runtime/architecture/ — specifies completed-turn commit, mid-stream discard/retry, persistence before tool dispatch, and synchronous/unknown-tool loop-back behavior.
