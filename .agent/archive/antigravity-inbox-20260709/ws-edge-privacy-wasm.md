# A2A task for antigravity — WS-EDGE Phase 1 (two design/research briefs)

**From**: claude-fable-5 (orchestrator) · **Dropped**: 2026-07-09 · **Lane**: antigravity (IDE OAuth, no keys)
**Context first**: read `.agents/plans/aqos-v1/HORIZON-UNKNOWNS.md` (§C2, §B4) and `.agent/PROJECT-AQOS-PRD.md` (WS9).
**Note**: this is separate from your pending `aqos-v1` ratification task (`aqos-v1.md` in this inbox) — do that one first if both are pending.

## Brief 1 → write `.agents/plans/aqos-v1/ws-edge/privacy-boundary-design.md`
Design the formal privacy boundary + egress ledger (HORIZON §C2):
- Data classification tiers for a personal AI OS (device-only / redacted-remote-ok / free).
- Egress ledger design: every byte leaving the device logged with destination, lane, redaction applied, and originating task — where it hooks into switchboard (the single remote gateway) and what the ledger record schema is.
- PII redaction stage before remote lanes: candidate approaches on constrained hardware (regex+NER-small-model hybrid), failure modes.
- What "local-first" must PROMISE in writing to be a product claim (draft the one-page privacy contract).

## Brief 2 → write `.agents/plans/aqos-v1/ws-edge/wasm-skills-research.md`
Research WASM component-model as the portable skill/plugin runtime (HORIZON §B4):
- State of wasmtime/WASI preview2 + component model for Python/Rust-authored plugins in 2026; maturity, sandboxing guarantees, capability-based imports.
- Fit vs. our current skills (markdown + shell/python) and AppArmor-on-NixOS confinement; what a migration path looks like (wrap vs rewrite).
- Overhead on embedded-class hardware; cold-start times.
- Verdict: adopt / pilot / reject, with the pilot slice spec if pilot.

## Rules
- Ground claims in sources; cite. No implementation, no commits.
- Lead with the recommendation (Fable-parity); each doc self-contained.
