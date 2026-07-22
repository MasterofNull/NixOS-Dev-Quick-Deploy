# DESIGN — Model/Agent-Agnostic Collaborative Factory + Catch-up Queue

**Status:** PREPARED_ONLY / design — awaiting orchestrator + independent review before implementation.
**Owner directive:** 2026-07-22 — "agentic collaborative workflow patterns and roles must be model and
agent agnostic; no roles/funnels/gates permanently tied through one model/agent, so development
progresses even when one model/agent is unavailable. A cache/queue lets a returning model/agent play
catch-up and add its inputs to the dev changes it missed. Fully agentic software factory, model/agent
agnostic, locally-hosted focused."
**SSOT principle:** `memory/feedback-agent-agnostic-roles-and-catchup.md`.

## 1. Problem

Practice drifted to hard couplings: Codex = binding acceptance; Antigravity/Gemini = review/PRD/plan;
Claude-flagship = orchestrator; local Qwen = optional. Each is a single point of failure — when a lane
is down (quota, sandbox, degraded route), the pipeline stalls or scrambles. The stated policy
(`role-matrix.md`: "any model may fill any role") is not lived.

## 2. Target: roles are responsibilities; agents are interchangeable fillers

### 2.1 Role-eligibility routing (no permanent binding)

For each role instance, an **eligibility router** picks the agent at dispatch time:
- **Availability:** lane reachable, not quota-exhausted, route healthy (probe/cooldown-aware).
- **Capability + tier:** role-matrix role × `config/model-coordinator.json` tier ladder.
- **Independence:** never self-review; a fresh session distinct from the producer.
- **Cost:** cheapest eligible (Rule 17).
The router outputs `{role, chosen_agent, reason, alternates[]}`. If the first choice is down, it selects
the next eligible and **records the substitution + a catch-up entry** for the down agent. Local Qwen is
the always-available floor (never-skip-local): it always gets a parallel advisory slot even when a
remote lane fills the binding slot.

Eligibility per role (initial matrix — all fillable by ≥2 lanes):
| Role | Eligible lanes (any available, independent) |
|---|---|
| orchestrator | Claude-flagship, Codex, Gemini/Antigravity |
| architect / PRD / plan | Antigravity/Gemini, Claude-flagship, Codex, local |
| implementer | local Qwen, Codex, Claude fast/balanced, Gemini |
| reviewer (design/auth) | any flagship not the author: Opus/Fable, Codex, Gemini |
| binding acceptance | any independent flagship: Codex, Claude-flagship, Gemini, local (bounded) |

Binding acceptance is the key de-coupling: it must accept a candidate from **whichever independent
eligible lane is up**, not Codex alone.

### 2.2 Catch-up cache/queue (`AGENT-CATCHUP-QUEUE.md` + event log)

When an agent is solicited-but-unavailable for a role, its intended contribution is queued with the
exact subject (hashes/commit) and role. On return, the agent processes its catch-up entries:
- **Confirmatory audit** of an already-committed slice (advisory; closes the entry on PASS).
- **Additional findings** → a bounded follow-up slice if warranted (never rewrite committed history).
The pipeline never blocks on a down agent; the queue guarantees its input is folded in on return.

## 3. Scope (implementation slices)

1. **`aq-role-route`** — a small selector: given a role + subject, reads model-coordinator tiers +
   live availability (reuse the codex quota-cooldown probe pattern, add per-lane health checks) +
   independence constraint, returns the chosen agent + alternates + reason; records substitutions.
   LOW-MED risk, local Python/bash, no new deps.
2. **Catch-up queue writer/reader** — `aq-catchup add|list|resolve` over `AGENT-CATCHUP-QUEUE.md` +
   `a2a-events.jsonl` (reuse VF-7 append-only ledger discipline). LOW risk.
3. **Dispatch integration** — the delegate-to-* wrappers + Agent-tool dispatch consult `aq-role-route`
   instead of hardcoding a lane; on down-lane, auto-file a catch-up entry. MED risk (touches dispatch).
4. **Docs/parity** — role-matrix.md §"agnostic execution"; the Rule across all agent files (done in
   this cycle); retire lane-specific language ("the codex lane") in favor of "an eligible lane".

## 4. Constraints (honored)

- Locally-hosted focused: local Qwen is first-class and the availability floor; no design step
  *requires* a remote lane (remote improves quality/speed, never gates progress).
- No API keys (existing HARD rule); agents use their own OAuth/session.
- Independence + non-self-review preserved; binding acceptance still requires a fresh independent lane
  — just not a *specific named* one.
- Right-sized gating still applies per risk tier.

`RECORD: design-only. No code/config change proposed for immediate landing beyond the canonical
docs/parity in this cycle. Router + catch-up-queue tooling are scoped slices pending review + owner
activation.`
