# RSI-Readiness — Dispatch Handoff

**Prepared**: 2026-07-09 by claude-fable-5 · **Ready to dispatch**

## One-command dispatch (ratification round)
```bash
scripts/ai/aq-collab-round open --round rsi-readiness \
  --task "$(cat .agents/plans/rsi-readiness/ROUND-PROMPT.md)" \
  --target .agents/plans/rsi-readiness \
  --local-timeout 7200
# codex (headless, own login), local (inlined, never-skip, generous timeout),
# antigravity (IDE inbox — consumption-based liveness; UNAVAILABLE if IDE not watching),
# claude (orchestrator: writes claude.md + aggregates).
scripts/ai/aq-collab-round collect   --round rsi-readiness
scripts/ai/aq-collab-round aggregate --round rsi-readiness
```

## Full lifecycle this drives (the user's ask: land concretely)
1. **Ratify** — round produces per-lane scores/amendments/slice-claims → orchestrator aggregates to `AGGREGATE.md`, consensus ≥3/4, amends the PRD.
2. **Plan** — ratified slice ownership becomes the beat plan (per lane, per R-workstream).
3. **Wire** — each claimed slice: files touched + integration into the live path.
4. **Validate** — each slice ships a test + a live check + activation-gate attestation (integrated+ON+validated+observable+intervenable).
5. **Commit** — verbose `type(scope):` commits per slice, PULSE + RESUME + ACTIVATION-AUDIT updated.

## Sequencing (from the PRD)
- **R1 first** (trustworthy eval harness) — gates all downstream automation. Codex leads the harness, claude signs off the signal is trustworthy.
- **R2 + R3 parallel** — R2 (local write-reliability: draft-only contract + tool-calling fine-tune target), R3 (SMALL_RESIDENT deploy — needs operator rebuild + model fetch).
- **R5 anytime** (trace auto-seeding — additive).
- **R4 after R1** (shadow loop efficacy — needs the trustworthy signal).
- **R6 last** (flagship: harness maintains its own issues-backlog end-to-end).

## Immediately dispatchable before ratification (no PRD dependency)
- **R5.1** (AQ_TRACE_ID auto-seeding at entrypoints) — additive, low-risk. claude.
- **R1.1** (draft golden task sets) — antigravity research lane / codex.

## Operator-gated (surface early)
- **R3.1** SMALL_RESIDENT needs a nixos-rebuild + model download (operator). model_budget verdict + draft-tune bench are prepped (`.agents/plans/aqos-v1/ws-edge/`).
- Antigravity lane responds only if the IDE is wired to watch `.agent/collaboration/antigravity-inbox/` and DELETE consumed files (the consumption-based liveness signal).

## Standing rules for every dispatched slice
PRD gate (PULSE plan line) → implement → live-test → tier0 gate → activation attestation → verbose commit → PULSE/RESUME. No autonomy granted (shadow before live). Local failures = R2 training data (never-skip-local). Archive-never-delete. Nix declaration same-cycle as runtime change.
