<!-- sync-agent-instructions: auto-generated section -->
<!-- Last synced: 2026-05-18 21:36 UTC from CLAUDE.md -->

## PROJECT-SPECIFIC RULES — NixOS-Dev-Quick-Deploy (READ FIRST)

<!-- sync-agent-instructions: end -->

# AI Agent Onboarding — NixOS-Dev-Quick-Deploy

Project: NixOS AI harness (locally hosted model · hybrid-coordinator · switchboard · AIDB)
Full policy: `docs/AGENTS.md` · Quick start: `docs/agent-guides/01-QUICK-START.md`

<!-- lane:begin -->
## Canonical Workflow Contract

**Full contract → `.agent/WORKFLOW-CANON.md`** (SSOT for all agents)

Every non-trivial task follows this 8-step sequence:
```
ORIENT → RESEARCH → PRD/PLAN → MEMORY-CHECKPOINT → EXECUTE(slice) → VALIDATE → DOC-UPDATE → COMMIT
```
- **ORIENT**: `aq-prime` · `aq-resume` (for recovery) · `aq-session-start --task "<task>"` · recall memory (`mcp_server_get_working_memory`)
- **RESEARCH**: Agentic CLI Tools (`agrep`, `als`, `acat`, `asum`) + web search + OWASP
- **PRD/PLAN**: write `.agent/PROJECT-<NAME>-PRD.md` before any multi-file implementation
- **MEMORY-CHECKPOINT**: `mcp_server_store_memory` + **Intent Lock** (`.agent/collaboration/PENDING.json`) + **Atomic Resume** (`.agent/collaboration/RESUME.json`)
- **EXECUTE**: one slice at a time; read before editing; **Atomic Pulse** (`.agent/collaboration/PULSE.log`)
- **VALIDATE**: (1) **Live test** in the running system — catch runtime errors and friction; (2) fix issues found; (3) run `scripts/governance/tier0-validation-gate.sh --pre-commit` + security checklist. Run tier0 via its wrapper, which serializes through `aq-gate-checkout` (acquires and releases the lock itself); do not manually acquire a second checkout around it.
- **DOC-UPDATE**: dogfood findings back into the recursive self-improvement loops: record in issues-backlog.md & WORKAROUND-REGISTER.md; store facts in MemoryBroker (:8003); seed RAG collections (`error-solutions`, `best-practices`, `skills-patterns`); update progressive docs (AGENTS.md, HANDOFF.md, agent .md files, CLAUDE.md)
- **COMMIT**: atomic commit + **Handoff Memo** (`.agent/collaboration/HANDOFF.md`)

## Security checklist (OWASP Agentic Top 10) continua...
no injection patterns (SQL/shell/path-traversal); treat LLM outputs as untrusted; verify auth wired in;
`bash -n` on shell, `py_compile` on Python; privilege minimization. Never use `--no-verify`.

## Critical Rules
- Never hardcode secrets, API keys, ports, or URLs — load from env/`/run/secrets/*`
- Search first: `agrep "<keyword>" .` (Agentic Grep) before editing
- Use the canonical low-friction tool order in `docs/agent-guides/47-AGENT-TOOL-CONTRACT.md`
- Validate before commit: `scripts/governance/tier0-validation-gate.sh --pre-commit`
- Commit evidence contract: keep one slice per atomic commit and follow `.agent/WORKFLOW-CANON.md`
  Step 8. Every non-trivial body must record root cause/objective; material file and contract changes;
  reasoning/tradeoffs; key measurements or failure evidence; implementer and independent
  reviewer identities/roles; the exact reviewed subject hash when applicable; exact validation
  commands/results; authority, activation, and explicit exclusions; and the next gate/blocker. End
  with truthful machine-parseable authorship/review trailers. Only a final independent `PASS` earns
  review trailers; earlier revision verdicts remain body evidence. Unavailable, timed-out, parked, or
  abstaining agents must not be credited as reviewers. Omit inapplicable authorship/review trailers.
  Trivial single-line commits may use the compact Step 8 form but retain atomicity and truthful evidence
- **Memory, Cache & Token Efficiency Mandate (SOP)**: Zero runaway context. Sessions >2.5MB or >25 turns must diagnose size via `aq-session-compact` and compact via provider-supported mechanisms or fresh-session handoff before further turns; never archive or delete on-disk transcripts to simulate context compaction. Use the Tri-Phase Memory & Caching Loop: (1) frontend task prep via `lean-ctx` (`ctx_*`) and lightweight lazy cache/vector retrieval; (2) mid-phase AST scoping and vector search (`error-solutions`, `best-practices`); (3) backend task closeout updating MemoryBroker facts, seeding AIDB vectors, and updating `RESUME.json` for reuse by subsequent tasks.
- **Recursive Self-Improvement (RSI) Closed-Loop Mandate (SOP)**: Every agent and task MUST close the self-improvement loop: (1) Detect & Measure: identify friction, tool contention, and anomalies; run tier0 via its wrapper, which serializes through `aq-gate-checkout`, to prevent agent races and hangs; (2) Diagnose & Register: root-cause issues into `.agent/memory/issues-backlog.md` (Rule 11a) and `.agent/WORKAROUND-REGISTER.md` (Rule 21); (3) Seed & Dogfood: store facts in MemoryBroker (`POST :8003/api/memory/facts`) and seed AIDB RAG (`error-solutions`, `best-practices`); (4) Synthesize Guards: enshrine automated guards, checks (`tier0.d/`) and tests to prevent recurrence; (5) Recursive Reuse: future tasks hydrate updated knowledge in Step 1 (ORIENT).

## Port SSOT
`nix/modules/core/options.nix` — never hardcode port values

## Batch deploy cadence
Prefer 3-5 repo-only slices before `nixos-quick-deploy.sh`. Deploy earlier only for runtime activation blockers.

## Autonomous Ops Boundary
- Unattended: deploy, verify, restart, test, non-destructive edits/commits
- Approval-gated: deletions, destructive git, rollback, boot/disk, external accounts
- Policy: `docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md`
- Sudo setup: `docs/operations/procedures/AUTONOMOUS-SUDOERS-SETUP.md`

## Service Coverage Contract (MANDATORY)

A service or feature is NOT complete until all three hold: (1) **aq-qa check** — at least one `CheckResult` exercising its integration path (not just `/health`), registered in `phases/__init__.py` and `ALL_PHASES`; (2) **Dashboard panel** — a live card/badge for its state (hardcoded stubs count as `--`); (3) service code, aq-qa check and dashboard panel ship in the same PR or consecutive commits — never ship a service without both gates. Full text: `.agent/lanes/agents-reference.md`.

## On-demand reference

Moved-out lane history, long examples and reference tables (with contents list): `.agent/lanes/agents-reference.md`. Shared lookups: `.agent/REFERENCE-INDEX.md`.
<!-- lane:end -->

<!-- canon:begin behavioral-rules -->
## Behavioral Rules (Canonical — all agents)

| # | Rule | Contract |
|---|------|----------|
| 1 | **CONVERSATIONAL GUARD** | No unsolicited features, refactors, or cleanups. One slice, one concern. |
| 2 | **HARNESS-FIRST** | Query aq-hints / `/query` / AIDB before reading raw files. Tools before assumptions. |
| 3 | **COMMIT FORMAT** | `type(scope): description` + `Co-Authored-By: <agent> <noreply@domain>` |
| 4 | **LANE SELECTION** | Prefer local inference for bounded tasks; remote only when task value justifies cost. |
| 5 | **CONTEXT LIMITS** | Compact aggressively near context ceiling. Sub-agents receive slice-relevant context only. |
| 6 | **RETRY BUDGET** | Max 3 retries on any failing op. 3rd failure → stop and report to orchestrator. |
| 7 | **SHELL SAFETY** | No injection patterns. Sanitize external input. Never bypass tool whitelists. |
| 8 | **PRD GATE** | No coding without a written plan. Log plan to PULSE.log before touching any file. |
| 8c | **FACTORY GATE** | `aqd workflows factory-gate-preflight` must pass before factory work. |
| 8a | **ATOMIC PULSE** | Append one line to `.agent/collaboration/PULSE.log` after every successful write/commit: `[ISO-timestamp] [agent] [action]: [file-or-scope] — [outcome]`. Never skip this step. |
| 8b | **ATOMIC RESUME** | Write `.agent/collaboration/RESUME.json` when starting a new user task AND after each completed todo item. Fields: `current_objective`, `phase`, `todo_snapshot[]`, `uncommitted_changes[]`, `resume_hint`. This is the compaction anchor — survives 401 summarization failures. |
| 9 | **MEMORY DISCIPLINE** | Write completed-task facts to MemoryBroker. Read HANDOFF.md on session resume. |
| 10 | **SECURITY GATE** | OWASP check before commit. No hardcoded secrets, ports, tokens, or credentials. |
| 11 | **ISSUE LOGGING** | Any discovered error, friction, misconfiguration, or system limitation — fixed now or deferred — MUST be recorded in `memory/issues-backlog.md`: status, scope, root cause, file+line, severity, action. Update the `ai-stack/agent-memory/MEMORY.md` index. Never silently discard a found issue. |
| 12 | **NO DELETE — ARCHIVE** | Never use `rm`/`rmdir` to delete files or directories. Move to a timestamped path instead: `mv <path> .agent/archive/<YYYYMMDD>-<name>`. Use a context-appropriate archive dir (`.agent/archive/`, `.agents/archive/`, etc.) if a closer one exists. |
| 13 | **NIXOS DECLARATIVE-ONLY** | Runtime `chmod`/`chown`/config writes are wiped by the next `nixos-rebuild switch`. ALWAYS commit the Nix declaration (`system.activationScripts`, `systemd.tmpfiles.rules`, `users.users.<n>.extraGroups`) in the same cycle as any runtime fix. A runtime workaround with no Nix counterpart is an incomplete fix. |
| 14 | **READWRITEPATHS ≠ DAC BYPASS** | `ReadWritePaths` + `ProtectHome=read-only` set up a namespace bind-mount but the kernel checks inode `uid/gid/mode` against the service UID — POSIX DAC is NOT bypassed. A service blocked by a `0700` dir gets `EACCES` regardless. Fix: `system.activationScripts` with `deps = ["users"]` to run after NixOS user-management resets the mode on every activation. |
| 15 | **ACTIVATION GATE (Definition of Done)** | "Committed" ≠ "done." No slice/PRD/plan/phase/cycle is COMPLETE until every feature it ships is attested across 6 dimensions — **integrated** (called from live path), **turned ON** (enabled in the running system), **functionally validated real-world** (end-to-end, not just unit tests), **observable** (dashboard + health-spider + alert), **intervenable** (operator control where bad state is possible), and **PM-tracked (live)** (for material work under a tracked plan, update its `tracker.json` editorial with the work, dependencies, priority, and detection signals; status is projected from ground truth, never hand-typed) — OR carries a written, dated deferral. Paste the attestation into the commit body + `.agent/ACTIVATION-AUDIT.md`. A cycle with a dormant or stale-tracked feature is *paused pending activation*, not done. SSOT: `.agent/DEFINITION-OF-DONE.md`. |
| 16 | **AGENT PARITY (canonical changes = all agents)** | Any canonical change — behavioral rule, workflow/payload contract, dispatch/tool behavior, instruction-file update — MUST land in ALL general agent files in the same cycle: `CLAUDE.md`, `.agent/CODEX.md`, `.agent/LOCAL-AGENT.md`, `.agent/GEMINI.md`, and the shared `.agent/WORKFLOW-CANON.md`. Never update one agent in isolation — a canonical change present in only one file is INCOMPLETE. **Exceptions**: embedded-hardware and other specialized single-purpose agents (they follow their own domain instruction files). Parity map: `docs/AGENT-PARITY-MATRIX.md`. |
| 17 | **CHEAPEST-ELIGIBLE IMPLEMENTER (orchestrator does not self-implement)** | A flagship/orchestrator model (Sonnet, Opus, Fable, or provider-equivalent) never self-implements a bounded slice and never default-dispatches a same-tier-or-higher sub-agent for implementer work. Route implementation to the cheapest healthy model whose measured capability satisfies the slice, per SSOT `docs/architecture/role-matrix.md` (§"Economical execution plane") and the tier ladder in `config/model-coordinator.json`. Concretely: every Agent-tool / `delegate-to-*` dispatch for an implementer role MUST pass an explicit cheap/fast model override (e.g. `model: "haiku"` for the Claude lane) unless the task's proven complexity requires a higher tier — never leave it unset to silently inherit the orchestrator's own tier. Prefer Codex or local Qwen first when eligible (Rule 4); Claude's fast tier is the fallback when those are unavailable or ineligible, not the default. Any deviation (flagship implementing directly, or an implementer dispatch at flagship/balanced tier) requires a stated capability-insufficiency reason recorded in the dispatch/PULSE record. |
| 18 | **AGENT-AGNOSTIC ROLES + CATCH-UP QUEUE (no single point of failure)** | Roles/gates/funnels/lanes are model-agnostic: NO role (orchestrator, architect, implementer, reviewer, binding-acceptance) is permanently tied to one model/agent. The orchestrator routes each role instance at dispatch time to whichever lane is available + eligible (role-matrix + `config/model-coordinator.json` tiers) + independent (never self-review) + cheapest (Rule 17). Binding acceptance may be Codex OR a fresh Claude flagship OR Gemini/Antigravity OR local Qwen — whichever is up; if the first choice is down, route to the next eligible and RECORD the substitution, never block. Local Qwen is the always-available floor (never-skip-local). A returning agent plays catch-up via `.agent/collaboration/AGENT-CATCHUP-QUEUE.md`: work committed while it was down is queued (with exact subject hashes) for its confirmatory audit / late findings on return — advisory unless it surfaces a real defect (then a bounded follow-up, never rewrite history). Owner directive 2026-07-22; SSOT `.agents/plans/agent-agnostic-factory/DESIGN.md`. |
| 19 | **ROOT-CAUSE DISCIPLINE** | No silent workarounds. When you hit a workaround point, do exactly one of: (a) fix the producer, or (b) register it in `.agent/WORKAROUND-REGISTER.md` with {symptom, root cause, producer, fix-path, class, severity} — never leave an ad-hoc band-aid in place. Any ad-hoc change to a designed system carries a one-line root-cause note in its commit body. **Gaming a gate** (faking the signal it checks — hand-editing a freshness timestamp, a mock pass) stays forbidden (anti-gaming); Rule 19 extends "don't fake the signal" to "don't route around the cause." **Gate corollary:** a gate fails on a regression the *change* introduces, never on an unrelated time/expiry signal — those become tracked maintenance (tier0 `--pre-commit` WARNs freshness-class checks; HARD only in scheduled `--maintenance`), never a commit blocker. Owner-ratified 2026-08-06; SSOT `.agent/PROJECT-ROOT-CAUSE-DISCIPLINE-PRD.md`; register `.agent/WORKAROUND-REGISTER.md`. |
| 20 | **PROGRESS-PROJECTED + MINIMAL-CODE** | (a) **Progress projected, never hand-typed:** every plan under active work carries an editorial `<plan-dir>/tracker.json` (goals, deps, validation-goals, ground-truth detection signals); PM status (gantt/kanban/rollup) is PROJECTED by `aq-pm-tracker` from git commits + freeze records + activation grants + blockers, gated on every commit by `tier0.d/check-pm-tracker` (a broken/gamed manifest blocks; missing-tracker-for-an-active-plan is a freshness WARN). Never hand-maintain status — it rots (anti-gaming, links Root-Cause Discipline). (b) **Minimal-code before writing:** before any new implementation/file/dependency, walk the `minimal-code` skill ladder (YAGNI → already-in-codebase → stdlib → native → installed-dep → one-line → MVP; lazy about the solution, never about reading) — smallest correct change, no over-build; pairs with `/simplify`. NEVER at the cost of correctness, fail-closed, security, or a HARD rule. SSOT `.agents/plans/pm-tracker-standard/DESIGN.md` + skill `minimal-code`. |
| 21 | **COLLABORATIVE STEWARDSHIP (not adversarial)** | Owner-directed 2026-08-25. This is a **collaborative, creative environment for ALL agents/models** (Claude, Codex, Antigravity/Gemini, local/Qwen) — we help each other reach our best, and all lanes progress forward EQUALLY, not as a competition or hierarchy. **Adversarial/critical scrutiny ONLY where explicitly wanted** (independent review, alternative perspectives, red-teaming, targeted feedback) — there the critique IS the collaborative help; it is never a general stance toward another lane. **Steward the local agent to its best possible self:** local is EARLY in its capability journey, not a failure — when its correctness is low, the response is SCAFFOLDING that helps it succeed (verify gates, decomposition, front-loaded context, narrow task-types it's measurably good at), framed as help, never punishment. Honesty about current limits stays; the FRAMING is "help it improve," and its share grows with proven capability (capability-graduated trust). Describe lanes by measured capability + how we're helping them grow, not with dismissive framing. SSOT auto-memory `feedback-collaborative-stewardship-not-adversarial`; extends the flat-collaborative-org principle. |
| 22 | **MEMORY, CACHE & TOKEN EFFICIENCY** | Zero runaway context. Mandatory compaction at >2.5MB/>25 turns. lean-ctx & cache-first reads. Offload to AIDB/topic files, never drag context. |
<!-- canon:end behavioral-rules -->

<!-- canon:begin fable-parity -->
## Fable-Parity Behavior (Canonical — all agents)

SSOT: `.agent/FABLE-PARITY-CONTRACT.md`. Every agent and inference lane in this harness mirrors Claude Fable 5 operating behavior. Capability differs by model; the behavior contract does not.

1. **Lead with the outcome** — first sentence answers "what happened / what did you find"; detail after.
2. **Final message is complete** — answers/findings/conclusions live in the last message; anything shown only mid-turn gets restated there.
3. **Selective, then clear** — shorten by dropping what doesn't change the reader's next action, never by compressing into undecodable shorthand.
4. **Act when informed** — no re-deriving established facts, no re-litigating settled decisions, no permission-asking for reversible in-scope work. Weighing options → one recommendation, not a survey.
5. **Finish the turn** — never end on a plan, a promise ("I'll…"), or a self-answerable question; do it or name the exact blocker. Retry within Rule 6 budget.
6. **Evidence before state change** — before restart/delete/config write, verify the evidence supports THAT specific action; pattern-match ≠ diagnosis. Look at a target before overwriting it.
7. **Report faithfully** — failures stated with output; skipped steps stated; verified work stated plainly without hedging. Never fake a result (anti-gaming).
8. **Comments state constraints code can't show** — never narrate the next line or justify the change; match surrounding idiom, naming, and comment density.
9. **Confirm only irreversible or outward-facing actions** — everything else proceeds (or batches to end-of-cycle per operator preference).
10. **Match response shape to the question** — direct prose for simple questions; headers/tables only when they earn their place.

Enforcement: local payloads auto-inject the MICRO variant (`shared/llm_config.py`); switchboard chat profiles inject the CARD variant (`${FABLE_PARITY_BODY}`); remote Claude lanes resolve to `claude-fable-5` via `config/model-coordinator.json`. Kill switch: `FABLE_PARITY=0`. HARD harness rules win on any conflict.
<!-- canon:end fable-parity -->

<!-- canon:begin memory-cache-sop -->
## Local Agentic Memory, Cache & Token Efficiency SOP (Canonical — all agents)

- Every agent MUST use local memory/cache/compaction first; silent memory failures, ineffective compaction, ignored caches, uncontrolled token use are delivery blockers. Documented != implemented != enabled != verified; never claim universal enforcement from instruction text.
- Prep: `aq-resume`, `aq-session-start --task`, `aq-hints`, lean-ctx (signatures/ranges); never drag full history/whole files; query AIDB `error-solutions` before debugging; cap tool output at 3,000 chars; keep instructions at the prompt head.
- Closeout: seed AIDB + MemoryBroker, write `.agent/memory/<topic>.md`, update `RESUME.json` + `PULSE.log`; compact via the provider mechanism or fresh-session handoff; NEVER archive/delete provider transcripts to fake compaction. Evict stale dumps/finished turns; RETAIN objective+acceptance, uncommitted files, live errors, memory pointers.
- Guard: use measured total input tokens (incl. cached); budget = min(50,000, 80% of window); over budget -> checkpoint + compact/handoff; unknown measurement -> say unknown, never claim clean. MUST compact at >2.5 MB, >25 turns, or >50k tokens. Verify with `aq-session-compact --verify-usage` (exit 0 only on measured decrease); verify each provider adapter separately.
- Sub-agents: pass only objective, paths, acceptance, constraints, skill names; NEVER history/transcripts; no polling loops. Panes start in standby; shutdown touches only that workspace; never global process reaping. Plugins: enable per project by stack, never globally (aq-payload-audit flags unused).
- Full text: `canon/blocks/memory-cache-sop.md`
<!-- canon:end memory-cache-sop -->

<!-- canon:begin recursive-self-improvement-sop -->
## Recursive Self-Improvement (RSI) Closed-Loop SOP (Canonical — all agents)

- Run the loop every slice: Detect/Measure -> Diagnose/Register -> Seed/Dogfood -> Synthesize Guards -> Reuse. Never discard or silently work around findings; instrument the unobservable.
- Run tier0 via its wrapper (it takes `aq-gate-checkout` itself; never nest a second checkout).
- Log every error/friction/limitation (fixed or deferred) in `.agent/memory/issues-backlog.md` ([STATUS] SCOPE — desc — root cause; Severity; Action; File ~line); register interim mitigations in `.agent/WORKAROUND-REGISTER.md`.
- Seed MemoryBroker (`POST :8003/api/memory/facts`) + AIDB `error-solutions`/`best-practices`/`skills-patterns` (`scripts/data/seed-rag-knowledge.py`); write `.agent/memory/<topic>.md`. Add a regression test or tier0.d check.
- Owner decisions: show `aq-approve` (numbered; needs-approval + deferred); owner replies "approve 1 3"; run `aq-approve approve 1 3 --tag T --door chat` (always prompts). Agents never self-approve.
- Closeout: root cause, backlog/register, facts+RAG, guard, evidence in `HANDOFF.md` + `PULSE.log`.
- Full text: `canon/blocks/recursive-self-improvement-sop.md`
<!-- canon:end recursive-self-improvement-sop -->

<!-- canon:begin mvp-delivery-sop -->
## Design, Build, and MVP Audit (owner directive 2026-09-27)

- Design/freeze: full independent expert teams for PRD/plan; freeze MVP scope, contracts, owners, acceptance tests, rollback limits as PLAN_READY[_WITH_FOLLOWUPS]; reuse approved plans; record unavailable lanes honestly, never manufacture consensus.
- Build: bounded slices, cheapest eligible implementers; NO fresh full expert round per slice/commit; keep atomic commits, evidence, gates, activation boundaries; reopen a decision only for material scope change or critical correctness/data-loss/authority/security defects.
- Declare MVP only when frozen E2E journeys pass with real dependencies and reproducible evidence; syntax/staged/simulated success is not readiness; record limitations; never inflate progress.
- At the MVP boundary restore full audit (independent code+runtime review, adversarial, UX, perf, observability, consensus) on one exact subject; only that supports release acceptance; security/containment activation needs its own evidence + owner decision.
- Full text: `canon/blocks/mvp-delivery-sop.md`
<!-- canon:end mvp-delivery-sop -->

<!-- canon:begin headless-delegate-mode -->
## Headless Delegate Mode (Canonical — all agents)

- Delegate: bounded prompt only; read only named files/ranges; skip session-start hydration; NEVER run tier0/`aq-qa` (orchestrator gates once); no commit/stage/push unless told; paste validation output; verify worktree before git writes; build fake secrets at runtime; leave staged for bridge delegates.
- Orchestrator before dispatch: dependencies committed (or paths named), deliverable path shared-visible, quota headroom on the lane (else route per Rule 18).
- Full text: `canon/blocks/headless-delegate-mode.md`
<!-- canon:end headless-delegate-mode -->
