# God-Tier Prompt Playbook — What to Ask the Fable Agent, In Order

**Date**: 2026-07-09 · **Author**: claude-fable-5 · **For**: operator (paste-ready prompts, one slice each)
**Ordering principle**: each prompt makes every later prompt cheaper, safer, or observable. Skipping ahead re-creates the ad-hoc feel.

## How to prompt Fable for maximum leverage (meta)
- State the **outcome and acceptance criteria**, never the steps or tools — auto-assignment (commit 442785d5) picks roles/bands/skills now; the agent works out the how.
- **One slice per prompt.** Bundled asks produce bundled half-done work.
- Always end with: *"Activation-gate attestation required; live-test in the running system; log found issues."* — this converts output from 'code written' to 'capability ON'.
- Give the agent standing permission to delegate: *"fan out subtasks to codex/local/antigravity where their envelope fits."*

## The ten prompts, in order

1. **Canon compiler** (WS1.4) — "Build the canon compiler: one `canon/` source that generates CLAUDE.md, CODEX.md, GEMINI.md, LOCAL-AGENT.md, WORKFLOW-CANON.md, switchboard profile cards, and the payload prompt blocks. Migrate the Fable-parity contract as the first content. Drift between generated files becomes a build/CI failure. Rule 16 stops being a discipline and becomes a build step."
2. **Config schema + hot reload** (WS1.2/1.3) — "Give every file in config/ a pydantic schema in a contracts/ tree, a validating loader with env overlay and SIGHUP/inotify hot-reload, and adopt it in switchboard first so profile edits apply in <5s without restart. CI fails on any config that doesn't validate or round-trip."
3. **Event-bus A2A with projections** (WS2) — "Replace direct agent writes to PULSE.log/RESUME.json with an append-only Redis-Streams event log (signed envelopes, idempotency keys); a projector service renders the familiar files as read-only projections. Kill the clobber class forever: today codex overwrote my RESUME anchor mid-cycle — again."
4. **One trace id, end to end** (WS5) — "OTel-instrument the full path: CLI → bus → switchboard → model → tool calls → commit, one trace per intent, exported to a local store the dashboard can query. Exit test: pick any failed run and diagnose it from its trace alone, no journalctl."
5. **Eval-aware scheduling + regression alarm** (WS8 + today's finding) — "The eval loop scored 0/12 under slot contention and nothing alerted anyone. Make the eval runner consult scheduler-state.json and DEFER (typed state) when the slot is contended; alert on pass-rate delta beyond threshold; exclude contention-failures from training capture. The learning loop must never poison itself with timeout noise."
6. **Small-resident model decision + speculative decoding** (S1/S4-adjacent) — "Present the rebudget options (one quant step down on the 35B vs fleet-node) with measured tradeoffs, then deploy a 0.6-1.7B resident model wired to the SMALL_RESIDENT tier (concurrency 3, never holds the big slot) and enable llama.cpp --model-draft speculative decoding. Re-run bench-local-agent before/after; publish the delta."
7. **Draft-and-polish cascade** (S2/S3) — "Add a cascade mode to the collab machinery: local drafts, a verifier scores confidence, remote lanes only polish or take over below threshold. Measure remote-token savings per task class against the parallel fan-out baseline for two weeks; keep whichever wins per class."
8. **The one CLI** (WS4) — "Ship `aq` as the single entrypoint (plugin subcommands, generated completions and help, shared context/audit/rate-limit middleware once). Convert the 30 highest-traffic of the 131 scripts to subcommands with usage-logged deprecation shims; retire on telemetry, not opinion."
9. **Command Center rebuild** (WS6 — after prompt 4 exists) — "Rebuild the dashboard OpenAPI-first with a generated typed client and SSE: Fleet (live agents/leases/queue from scheduler-state), Runs (trace waterfalls from OTel), Approvals (one HITL queue for repairs/intakes/deferrals), Evals (scorecards + regression alarms), Cost/token burn. Every blank '--' is a bug; every mutating view has an aq twin."
10. **Install story** (WS-EDGE + WS10) — "Using hw_probe's generated profile, make a clean machine go from `nix run` to first successful local delegation in under an hour, documented only by the quickstart the installer generates for its own hardware class. That artifact is the productization exit test."

## Dashboard verdict (asked separately, answered here)
Yes — revamp, but **sequenced**: the full rebuild is prompt 9 and must wait for prompt 4's trace/metrics data or the new UI renders the same blanks prettier. Three cheap wins worth doing immediately, before the rebuild:
1. **Queue card**: render scheduler-state.json (bands, waits, depth) — new observable surface from slice 3.1, currently invisible in the UI.
2. **Pass-rate collapse alarm** on the Learning card (today's 0/12 sat unalerted for 20 minutes until a manual curl found it).
3. **Approvals inbox count** surfaced on the header (HITL items pending anywhere = one number the operator always sees).
Current state for the record: vanilla-JS monolith (8,040-line dashboard.js, 101KB page, 20 route modules, healthy WS) — solid data plumbing, no component model, no typed API client, alerting gaps.
