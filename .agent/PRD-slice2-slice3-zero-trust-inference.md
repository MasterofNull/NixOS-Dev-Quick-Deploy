# PRD — Slice 2 (Zero-Trust Sub-Agent Sandboxing) + Slice 3 (GBNF Grammar Gate + Model Multiplexing)

Status: Ratified v2 — APPROVE-WITH-CHANGES (3-agent consensus: claude + codex + gemini; changes folded)
Owner: AI Stack Maintainers
Last Updated: 2026-07-07

Derived from the ratified multi-agent PASS-1 consensus in
`.agents/plans/round-slice2-slice3-2026-07-06.md` (claude + codex/gpt-5.5 + gemini converged,
zero conflict; local did not contribute). This PRD formalizes that consensus into requirements,
phases, and acceptance criteria. Plan drafts + plan consensus follow.

## Context
The harness gates the delegation BOUNDARY (A2A action-policy, secret scan, dispatch budget) but
has no RUNTIME confinement for sub-agents, and local inference wastes the single APU slot on a
~15% invalid tool-JSON repair loop. Three independent expert passes converged on a layered
sandbox + a switchboard grammar/tool-lock, unified by one shared primitive.

## Keystone (build first — Phase 0)
**Per-task `zero_trust` flag.** Derived at the switchboard from `a2a_guard` `secret_findings`
(already recorded at `agent_service.py:134`). It drives BOTH slices: under `zero_trust`, the
switchboard mints a reduced immutable tool catalog (Slice 2) AND blocks/downgrades remote
routing (Slice 3). Single source of truth, two consumers. Everything else builds on it.

**Wire contract (ratified — claude C1 + gemini C3):** declare `zero_trust: bool = false` in the
base switchboard request model. ONE field, read by both the tool-filter and the router. Default
false = normal.
**FAIL-CLOSED (ratified — codex, CRITICAL):** if the `a2a_guard` result is absent, stale,
malformed, or unavailable, treat `zero_trust = true`. Degraded guard plumbing must NEVER silently
restore privileged routing.
**Re-evaluate per request (ratified — claude + codex + gemini, 3/3):** a secret entering
mid-conversation (or written to the workspace by a sub-agent) flips the flag on the next turn;
never latch it at task start.

## Goals
1. A sub-agent that runs `edit`/`yolo` cannot escape its workspace, read secrets, reach
   privileged tools, or exhaust host resources — enforced at runtime, not just at dispatch.
2. Local tool-call output is valid JSON by construction (GBNF), eliminating the repair loop.
3. The single APU slot is used efficiently via a resident-small + controlled-35B-swap model
   stack, with intent-based routing.
4. The sandbox doubles as the Slice-4 eval runtime.

## Non-goals
- Rewriting the headless dispatch model (keep it; wrap it).
- Per-request model swapping (too slow on the APU — explicitly rejected by consensus).
- Fixing the SSE malformed-chunk drop (`agent_executor.py:1741`) — tracked as a SEPARATE
  reliability item; GBNF addresses argument-JSON, not stream framing.

---
## Slice 2 — Zero-Trust Sub-Agent Sandboxing

### Requirements
- **R2.1 Layered isolation.** Bubblewrap (`bwrap`) as the per-invocation sandbox; AppArmor/
  systemd as the outer service envelope. REUSE the existing pattern at
  `ai-stack/mcp-servers/aider-wrapper/server.py:476`. bwrap: `--unshare-all --die-with-parent`,
  ro `/nix/store` + `/etc`, isolated `/tmp`, bind ONLY the task-scoped workspace, **network off
  by default**. Do NOT express per-task workspaces in AppArmor (too coarse/less revocable).
- **R2.2 Tool-catalog lock.** Enforced at the switchboard (owns tool schemas + leases at
  `switchboard.py:1008`/`:1641`); coordinator `secret_findings` = input; runtime = defense-in-depth.
  Under `zero_trust`: strip `reload-model`, `proposals/apply`, shell-like, endpoint-mutation, and
  remote-escalation tools; the runtime rejects any out-of-catalog call.
- **R2.3 DAC-correct declaration (RULE 13/14).** New `nix/modules/services/sub-agent-sandbox.nix`;
  state roots under `/var/lib`, owned by the executing user; `install -d -o <user> -m 0750`;
  `system.activationScripts` (deps=["users"]) reasserts ownership/mode every activation;
  task-scoped repo bind (NOT whole home); never rely on `ReadWritePaths` for permissions.
- **R2.4 Resource ceilings.** systemd scope `MemoryMax`/`CPUQuota`/`TasksMax` + `--die-with-parent`
  + dispatch-budget integration.
- **R2.5 Eval-sandbox reuse.** Same runtime, strictest profile (ro inputs, writable result dir
  only, no secrets/net/privileged tools) — parameterized, built once.

### Red-team acceptance (must all hold)
Path/symlink escape blocked (canonical validation + no cross-boundary binds); secret exfil
blocked (no `/run/secrets`/home/ssh binds + net-off + outbound scan); privileged-tool reach
blocked (catalog lock); resource exhaustion bounded (ceilings). A network-requiring task must
go through an explicit policy-approved capability, not default-on.

### Phases
- **2.0** Keystone `zero_trust` flag (shared).
- **2.1** bwrap executor wrapper (Nix writeShellScript) around the `edit`/`yolo` path, workspace-scoped.
- **2.2** Switchboard tool-catalog lock consuming `zero_trust` + runtime rejection.
- **2.3** `sub-agent-sandbox.nix` (state roots, activation, resource ceilings).
- **2.4** Eval-sandbox profile parameterization.

---
## Slice 3 — GBNF Grammar Gate + Model Multiplexing

### Requirements
- **R3.1 Per-request GBNF at the switchboard**, generated from the FINAL (post-filter/lease/
  `zero_trust`) tool schema set — NOT per-profile/global. Use llama.cpp `json_schema_to_grammar`;
  attach the `grammar` param after tool resolution. Coerces valid `{name, arguments}` at decode.
- **R3.2 Grammar cache** keyed by tool-set schema hash (removes per-request conversion overhead).
- **R3.3 Resident-small + controlled-35B multiplexing.** Keep a 4B/8B resident for
  trivial/validation/tool-call/JSON-repair; load 35B(-MTP) only for planning sessions; the swapper
  handles SESSION-level mode changes, never per-request. Reuse the active-model-symlink pattern
  (`ai-stack.nix:863`; catalog `:539`). MEASURE swap latency before committing swap logic.
- **R3.4 Intent routing.** 4B: JSON repair/classification/schema-validate; 8B: bounded repo Q&A/
  routine tool steps; 35B: architecture/multi-file/high-risk; remote: large-context — but
  `zero_trust` blocks/downgrades remote. Extends the existing complexity→lane routing.
- **R3.5 Measurement gate.** Golden tool-call suite (nested/arrays/enums/optional + secret-bearing
  cases) run with/without GBNF: invalid-arg rate, repair count, time-to-valid-call, tok/s, slot
  occupancy, per-tier budgets. GBNF rollout GATED on a measured invalid-rate drop; prove
  `reload-model`/`proposals/apply` are absent from the grammar under `zero_trust`.

### Phases
- **3.0** Keystone `zero_trust` flag (shared with Slice 2).
- **3.1** Golden tool-call measurement suite (baseline the current invalid-rate FIRST).
- **3.2** Per-request GBNF from tool schema + grammar cache.
- **3.3** Model-stacking routing (resident 4B/8B + 35B session load).
- **3.4** Session-level swapper (only if 3.1/measurement justifies it).

---
## Acceptance criteria (PRD-level)
- Sandbox: all R2 red-team cases pass in an automated harness; sandbox startup overhead measured
  and acceptable on the APU.
- Grammar: measured invalid-argument-JSON rate drops to near-zero under GBNF; repair-loop count → 0
  on the golden suite; no tool-call latency regression beyond a stated per-schema budget.
- Keystone: a secret-bearing task provably cannot call privileged tools OR route remote (one test
  covers both slices).

## Risks + mitigations
- bwrap friction on legit tasks (network) → explicit policy-approved capability + escape hatch.
- Grammar overhead on 35B → cache + measure; grammar is a reliability layer, not a routing layer.
- Swap slot-lock → resident-small default; swap only session-level, gated on measurement.
- Concurrency (shared registry/config writes during rollout) → reuse the atomic-write + quiescence
  patterns already established (registry reaper, prompt-ext sidecar).

## Sequencing + dependencies
Phase 0 keystone → Slice 2 (2.1–2.4) and Slice 3 (3.1–3.4) proceed in parallel after it. Slice-3.1
(measurement) lands before 3.2 so GBNF value is proven, not assumed. Slice-2 eval profile (2.4)
feeds Slice-4.

## Open questions (route to PASS-2)
- Slice 2: sandbox startup cost budget on the APU; debuggability of failures inside bwrap;
  revocation/escape-hatch UX for legit network tasks. (PASS-2 baseline: ops/failure-recovery.)
- Slice 3: exact tok/s + repair-cost numbers (needs 3.1 baseline); when remote is worth it.
  (PASS-2 baseline: tokenomics/measurement.)
- Re-engage local[Qwen] (via --mode agent or single-slice prompts) + gemini in PASS-2.

## v2 — Ratified changes (folded from the 3-agent consensus; BINDING)
Consensus verdict APPROVE-WITH-CHANGES (claude + codex + gemini; local[Qwen] excused — completes
with time but not a reviewer-tier lane for large-context review). Aggregate:
`.agents/plans/prd-consensus/AGGREGATE.md`. These amend the requirements above.

**Keystone (Phase 0):** wire contract + fail-closed + per-request re-eval — see Keystone section.

**Slice 2 (amends R2.x):**
- **V1 (R2.2)** Tool-catalog lock is IMMUTABLE per request; when `zero_trust`, strip
  reload-model/proposals/apply/shell/endpoint-mutation/remote-escalation.
- **V2 (R2.1 red-team)** Canonicalize workspace bind paths (absolute resolution); explicitly
  reject `..` / double-slash traversal before binding.
- **V3 (R2.1)** Bind `/nix/store` ROOT (ro) — never pinned hashed subpaths (break on rebuild).
- **V4 (R2.x, new)** Structured sandbox failure reason codes: `policy_denied | missing_bind |
  resource_limit | tool_catalog_denied | process_error | timeout`; STREAM categorized failures to
  `.agent/collaboration/a2a-audit.log` + dashboard. Raw stderr is insufficient.
- **V5 (R2.1)** Network OFF by default; a net-needing task presents a coordinator-SIGNED,
  time-bound token scoped by destination class + task id, revoked via the same capability state as
  the tool-catalog lock. NO global "network-enabled" profile.

**Slice 3 (amends R3.x):**
- **V6 (R3.1, new)** Grammar-gen fallback: if `json_schema_to_grammar` fails (nested anyOf/oneOf,
  recursion), degrade to unconstrained decode (log + proceed) — never block the tool-call chain.
- **V7 (R3.2)** Grammar-cache key MUST include the final post-lease tool schema, tool names,
  argument schemas, AND `zero_trust` filter state (stale grammar could re-enable stripped tools).
- **V8 (R3.3, new — gemini)** VRAM pool manager: UNLOAD inactive models before initializing a new
  session when the 4GB APU memory-headroom would be exceeded (8B+35B concurrent = thrash).
- **V9 (R3.4)** Remote downgrade deterministic fallback: large-context AND `zero_trust` → local
  chunking or an explicit refusal contract, not a bare "block" (which becomes an availability fail).

**Acceptance thresholds (numeric — replaces the vague R3.5 bar):**
- GBNF accepted only if it removes ≥90% of repair attempts on the golden suite.
- Sandbox startup p95 ≤ 750 ms (edit/yolo), ≤ 1500 ms (eval); bwrap namespace itself <5 ms.
- Grammar conversion p95 ≤ 100 ms (cache miss), ≤ 10 ms (cache hit); tool-call latency
  regression ≤ 8% (local 8B/35B).
- 35B session-load p95 > 45 s → 35B stays an explicit session mode only (resident 8B default);
  clamp swaps if tasks are queued within a 20 s active window.

## Next
Consensus RATIFIED. → plan drafts (phased, per slice) → plan consensus → implementation starting
with the Phase-0 keystone (`zero_trust` flag). Phase-0 keystone plan:
`.agents/plans/phase0-keystone-zero-trust-plan.md`.
