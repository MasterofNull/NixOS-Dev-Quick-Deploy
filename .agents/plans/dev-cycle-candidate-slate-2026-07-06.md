# Dev-Cycle Candidate Slate — 2026-07-06

Orchestrator: claude-opus-4-8. Purpose: derive the next dev-cycle slices + the research
topics the multi-agent expert teams (codex, claude, local[Qwen], gemini/antigravity) should
research → ground → debate → PRD → plan, per `.agent/WORKFLOW-CANON.md` Step 3 Extension.

## Grounding provenance (what this slate is derived from)
- **Claude (this session)** — delegation-boundary hardening: switchboard local-agent
  passthrough + first-token watchdog sizing (cold APU prefill); A2A safeguard suite
  (grounding SSOT, outbound secret scan, action-policy gate, dispatch budget, `aq-a2a-audit`
  viewer, shared `a2a-audit.log`); `set -e` helper-return bug pattern; generated-file-in-git
  anti-pattern (prompt-extensions → gitignored sidecar, idempotency proven).
- **Gemini/Antigravity research** — `.agent/FUTURE-AGENTIC-SURFACES.md` (9 engineering
  targets), `.agent/INDYDEVDAN-RESEARCH-SUMMARY.md` (11 videos: observability, model
  stacking, agentic security), new `scripts/ai/generate-module-dashboard.py` +
  `assets/modules/` + `verify-dashboard-apis.py`.
- **Backlog** — Software Factory Readiness Gaps (7 unchecked), open ops issues, a 5-item
  PENDING-REBUILD queue on the coordinator `/qa/check` chain.

## Convergence = priority
Themes named independently by ≥2 sources (Claude findings, Gemini research, IndyDevDan,
backlog) are the highest-signal slices. Mapped below.

---

## SLICE 0 (BLOCKING) — Coordinator bring-up debt / validation-chain green
- **Convergence**: backlog PENDING-REBUILD (5 items) + IndyDevDan #6 (harden validation gates).
- **Problem**: `/qa/check` chain has 5 fixes staged but unactivated (needs `nixos-rebuild`):
  wrapper empty-capture, drop-spec abort, tool-registry HOME, store-path exec rules, ss/proc-net
  denials. Until this is green end-to-end, no autonomous loop can trust its own validation gate.
- **Scope hypothesis**: batch the pending rebuild, verify `/qa/check` returns machine JSON from
  the coordinator sandbox, close the 5 items. Also: `delegate-to-local` `--status/--check/--cancel`
  parser drift; `sandbox-observability-contract-fragmentation` (routine host probes surface as errors).
- **Why first**: this is the "bring-up + validation" foundation the user named; everything else
  validates through this gate.
- **Expert lenses**: systems-software (NixOS/AppArmor), qa-automation.

## SLICE 1 (HIGH, STARTED) — Agentic Observability: multi-tile CLI ops window (cmux-model)
- **Convergence**: Gemini #8 + IndyDevDan #1 (CMUX) / #11 + Claude A2A audit trail + new module dashboard.
- **Reference model**: cmux (https://github.com/manaflow-ai/cmux) — "no hidden agents": every
  spawned sub-agent becomes a visible pane; observable status + attention rings/badges when a
  process needs attention or loops; each agent in its own live pane; fully programmable via CLI.
  We can't use its macOS/Ghostty GUI on NixOS, but we adopt the model in a Rich TUI.
- **Problem**: We emit rich A2A events (`a2a-audit.log`, delegation registry, switchboard routes)
  but operators can't SEE concurrent agents, per-agent live work, cost, or error-loop retries.
  Proven this session: Claude+Codex+Gemini ran concurrently with no live view.
- **Parity gap found + reused**: `scripts/ai/aq-tui-dashboard` existed as a Rich TUI scaffold with
  ENTIRELY MOCK data (hardcoded "ok"/fake agents) — a parity-gap (fake > blank). REWIRED it to
  live sources: Active Delegations (registry.jsonl running+recent), Running Processes (real pgrep,
  shows the live Codex/Gemini procs), Service Health (live probes), A2A Safeguards (audit tail),
  Ops Activity (PULSE). MVP shipped + verified against real state. `--once` snapshot / `--interval`.
- **Next iteration (cmux-aligned)**: (a) per-delegation LIVE OUTPUT pane — expand a task to tail
  `.agents/delegation/outputs/<id>.log`; (b) ATTENTION signals — highlight error-loop (>2 same
  tool/file retries), stalled, or failed delegations; (c) programmable select/drill CLI + JSON;
  (d) later: trace-chain graph, cost/compression counters (lean-ctx).
- **Expert lenses**: mobile-web/TUI, mlops (telemetry), Claude (A2A schema).
- **STATUS [DONE 2026-07-06]**: ops-window shipped (`aq-tui-dashboard` — live tiles, `--matrix`
  per-agent input+output panes, `--focus`, `--json`, attention signals; Nix-wrapped). Registry
  orphan reconciliation done. **Slice 1b (interactive intervention channel) CLOSED** — polling
  control channel first cut: `aq-agent-send <id> "message"` injects operator responses into a
  live `aq-agent-loop` between turns (`control_channel.py` + `agent_executor` poll), commit
  418f4090; docs at `docs/operations/agent-ops-window.md`. Remaining (future): trace-chain graph,
  cost/compression counters, extend control channel to external-CLI lanes + PTY hard-interrupt.

## SLICE 2 (HIGH) — Zero-Trust Sub-Agent Execution Sandboxing
- **Convergence**: Gemini #3/#6 + IndyDevDan #7 + Claude A2A safeguards (boundary gates).
- **Problem**: My safeguards gate the delegation BOUNDARY (mode auth, secret scan, budget) but
  once a sub-agent runs in `edit`/`yolo` it can execute arbitrary scripts against the host FS.
  No per-sub-agent runtime confinement; no zero-trust tool sanitization (a credential-bearing
  task can still reach `reload-model`/`proposals/apply`).
- **Scope hypothesis**: declarative AppArmor/bubblewrap profiles per sub-agent runtime scoped to
  workspace + read-only Nix store; routing-policy tool-catalog lock that strips privileged tools
  when a task touches secrets. Extends the action-policy gate into runtime enforcement.
- **Research questions**: bubblewrap vs AppArmor for the sub-agent executor under NixOS? how to
  bind the tool-catalog lock to the secret-scan finding? DAC namespace boundaries per RULE 14.
- **Expert lenses**: security-systems, systems-software (NixOS), Claude (policy continuity).

## SLICE 3 (HIGH) — Local Inference Reliability: GBNF grammar gate + model multiplexing
- **Convergence**: Gemini #1/#2 + IndyDevDan #2 + Claude switchboard/watchdog work.
- **Problem**: ~15% of local outputs yield invalid JSON tool args → tool-repair loops burn the
  single APU slot. Concurrent Qwen35B/Llama70B contend on the 12-layer/4GB partition, throttling
  <1 tok/s. Model-stacking (route trivial checks local, planning remote) is only partly realized.
- **Scope hypothesis**: wire GBNF grammar files at the switchboard boundary to coerce valid tool
  JSON; a systemd-bound model swapper watching the switchboard queue; formalize model-stacking
  routing profiles. Directly extends this session's switchboard passthrough work.
- **Research questions**: llama.cpp GBNF per-request vs per-profile? swap latency vs slot-lock on
  APU? which task classes are safe to route remote under the zero-trust lock (Slice 2)?
- **Expert lenses**: mlops (inference), Claude (switchboard), local (self-eval on its own failures).

## SLICE 4 (MED-HIGH) — Software Factory: candidate lifecycle + trust provenance
- **Convergence**: backlog readiness gaps (all 7) + Gemini #7 (maturity-tier) + Claude
  generated-state governance insight.
- **Problem**: knowledge synced to AIDB doesn't surface as `candidates.json`; no eval sandbox;
  scoring is manual/non-deterministic; proposal↔candidate lifecycle disconnected; pipeline
  invisible on dashboard; AIDB lacks trust-tier/license provenance for autonomous decisions.
- **Scope hypothesis**: candidate lifecycle state machine (proposed→evaluated→adopted) with
  deterministic scoring, an eval sandbox, trust-tier/license metadata, and dashboard visibility.
- **Research questions**: reuse `discovery_agent.py` candidates pipeline? deterministic trust
  score inputs? eval sandbox = the Slice 2 bubblewrap runtime (shared infra)?
- **Expert lenses**: mlops, Claude (governance), gemini (research-source ingestion).

## SLICE 5 (MED) — Continual Eval & Training Lifecycle
- **Convergence**: Gemini #9 + IndyDevDan #8 + Claude idempotency/generated-state work.
- **Problem**: rejected runs / tool-parse crashes aren't systematically harvested into training
  JSONL; no golden-task regression matrix gating model promotion; no state-delta assertions
  verifying a run's disk changes match intent.
- **Scope hypothesis**: fine-tuning harvest pipeline (redacted failure capture), golden-task
  pytest matrix vs `solved_tasks.json` before any weight/model scale-up, state-delta assertion
  harness around isolated-workspace evals. Ties to the Slice 0 validation gate + Slice 4 sandbox.
- **Expert lenses**: mlops, qa-automation.

## SLICE 6 (MED) — Context Economy: RAG recency decay + A2A shared cache
- **Convergence**: Gemini #4/#5 + IndyDevDan #10 + lean-ctx toolchain.
- **Problem**: stale codebase snippets contaminate RAG similarity; sub-agents duplicate
  read_file/grep for the same configs, multiplying tokens.
- **Scope hypothesis**: systemd timer hashing the workspace + cosine-distance recency decay on
  old vectors; a shared context cache (headroom proxy) for pre-warmed config reads; `ctx_delta`
  incremental diffs over full reads.
- **Expert lenses**: mlops (RAG), Claude (lean-ctx integration).

---

## Recommended sequencing
1. **Slice 0** now (blocking — clears the validation foundation; small, mostly rebuild+verify).
2. First expert-team research/debate round on the **HIGH-convergence trio: Slices 1, 2, 3**
   (observability, zero-trust sandboxing, inference reliability) — they share infra (sub-agent
   runtime, event schema) so debating them together surfaces the shared substrate.
3. Slices 4–6 in the following round (they depend on the Slice 2 sandbox + Slice 0 gate).

## Next step (per WORKFLOW-CANON Step 3 Extension)
For each launched slice: dynamic expert-team assembly → independent PRD drafts (all agents,
parallel, no cross-visibility) → consolidation → consensus sign-off → plan drafts → plan
consensus. Aggregate via `aq-collaborate`. Multi-pass for angle diversity; model diversity
comes from the agents. Respect the dispatch budget (20/agent/5min) and the active-collaborator
set (Codex + Gemini/Antigravity currently live).
