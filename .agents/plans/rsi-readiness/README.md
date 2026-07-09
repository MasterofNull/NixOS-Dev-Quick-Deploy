# Collaborative Round — rsi-readiness

Opened: 2026-07-09T19:42:13Z
Target artifact (if a review round): .agents/plans/rsi-readiness

## Task
# Round: rsi-readiness — Expert-Team Collaborative Lifecycle

You are one expert lane in a flat multi-agent collaboration (claude, codex, antigravity, local/Qwen). This round turns a strategic assessment into concrete landed system changes: ratify the PRD, plan the slices, wire them, validate, and commit — the full software-factory lifecycle.

## The mandate (grounded — read these first)
1. `.agent/PROJECT-RSI-READINESS-PRD.md` — the initiative: build TRUST INFRASTRUCTURE so local agentic self-improvement can be granted autonomy *on evidence, not hope*. 7 workstreams (R1 eval harness, R2 local write-reliability, R3 SMALL_RESIDENT+cascade, R4 shadow-loop efficacy, R5 trace seeding, R6 flagship self-improvement app, R7 multi-agent coordination safety — git/index serialization + event-bus migration completion).
2. `.agent/FABLE-PARITY-CONTRACT.md` — the behavior you operate under.
3. Evidence base (verify, don't trust): the local model claimed file writes it never made (see the unbacked-write guard in `scripts/ai/aq-agent-loop`); the eval loop scored a false 0/12 under contention (see the contention guard in `scripts/ai/aq-local-training-loop`); the cascade + confidence scorer exist (`scripts/ai/lib/cascade.py`); tracing is live (`scripts/ai/lib/trace.py`, `/api/trace/{id}`); model_budget says deploy_small_resident_now (`scripts/ai/lib/model_budget.py`).

## The hard truth this round must honor
The machinery is built; the blockers are (a) local execution reliability and (b) reward-signal integrity. **R1 (trustworthy eval harness) gates everything** — no downstream automation is safe on a corruptible signal. **No autonomy is granted this cycle** — the exit is a SHADOW loop measured against a trustworthy harness. Do not propose granting the loop autonomy.

## Your task — write ONE file: `.agents/plans/rsi-readiness/<your-lane>.md`

### 1. Scores + ratification
`R1..R7: <1-10> — <one-sentence reason>`, then a verdict:
`RATIFY / RATIFY-WITH-AMENDMENTS / REJECT` + one sentence.

### 2. Top amendments (max 3)
Highest-impact changes to the PRD, each with what/why/which workstream. Especially: is R1's "trustworthy signal" acceptance criterion strong enough? Is the no-autonomy boundary right?

### 3. Risks the PRD underweights (max 3)
Where could this build trust theater instead of real trust? Where might a workstream produce a green checkmark that doesn't mean what it claims?

### 4. Slice claims + wiring plan (this is where it lands concretely)
Claim the R-slices your lane will implement, honoring the delegation defaults and your measured envelope. For each claimed slice give: the concrete files to touch, the wiring (how it integrates into the live path), the validation (test + live check), and the activation-gate attestation you'll produce. One line per slice: `<slice>: claim|pass — <files/wiring/validation in ~15 words>`.
- codex: structural/typed implementation (R1 harness, R3 Nix+wiring, R5 OTel, R7 git-lock/worktree serialization).
- claude: orchestration/integration/acceptance (R1 sign-off, R2 draft-only contract, R6 flagship).
- antigravity: research/design (R1 golden-set design, R4 efficacy-measurement methodology) — IF your inbox lane is live; else this is a design doc.
- local/Qwen: bounded audits + R2 training-data curation; your failures here ARE R2 data. Sections 1 and 5 mandatory; 2-4 best-effort.

### 5. Verdict + first commit target
State the ONE slice you would land first and its commit message type(scope): line.

## Rules
- Ground every claim in the PRD/plan/repo — no invented features; cite files.
- Lead with the outcome; self-contained (Fable-parity).
- No implementation in THIS round — this round produces the ratified plan + slice ownership. Implementation happens in the dispatched slices after aggregation.
- Do NOT commit in this round. The orchestrator aggregates → amends PRD → dispatches slices.

## Protocol
Each agent writes its OWN file here — `codex.md`, `local.md`, `antigravity.md`, `claude.md`.
NEVER append to a shared file. The orchestrator aggregates into `AGGREGATE.md`.
- local[Qwen] runs long — the round stays OPEN for it; never skipped.
- antigravity (Antigravity IDE, real Gemini via its OWN OAuth) picks up the task from the inbox
  `.agent/archive/antigravity-inbox-20260709/rsi-readiness.md` and writes `antigravity.md`. No API keys.
