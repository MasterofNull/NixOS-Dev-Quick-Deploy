# AQ-OS Owner Meta-Prompt — Next Architecture and Parity Cycle

**Date:** 2026-07-09  
**Mode:** Evidence-led architecture, PRD, threat analysis, and planning only  
**Authority:** Owner brief for the next flat multi-agent expert-team round  
**Protocol:** `.agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md`

## Prompt

I am the owner and operator of NixOS-Dev-Quick-Deploy. I want you to act as my
independent expert design team and help me turn this system from a capable but
piecemeal local AI harness into a deliberately engineered, integrated, testable,
and product-quality local-first AI operating platform.

Do not flatter the system, defend sunk cost, or confuse a large feature inventory
with a coherent product. Preserve what is genuinely differentiated, challenge
what is accidental, and recommend deletion, consolidation, or replacement when
that creates more value than another layer of compatibility code.

This round is for research, critique, PRD creation, and implementation planning.
Do not implement code. Do not start work merely because a plausible slice exists.
The goal is to decide what the system should become, what its smallest stable
kernel is, which current parts deserve to survive, and which parity gaps close the
distance between today's system and that clean-sheet target.

## My Product Intent

The system I am trying to build is:

- A local-first AI engineering and operations control plane on NixOS.
- A reproducible platform where human operators and multiple AI agents can plan,
  execute, review, observe, and improve technical work safely.
- A system that uses remote frontier models as optional teachers, reviewers, and
  accelerators while continuously measuring and improving local-model capability.
- A closed learning loop whose outputs are provenance-linked, eval-gated, human-
  governable, and resistant to reward corruption.
- An operator product: every important state must be discoverable, explainable,
  observable, and safely intervenable from one coherent CLI/API/console model.
- A portable foundation that can eventually scale from constrained edge hardware
  to workstations and small fleets without pretending one Renoir APU profile is a
  universal architecture.

It is not primarily:

- A chatbot.
- A collection of clever `aq-*` scripts.
- A dashboard over disconnected subsystems.
- An anthropomorphic AGI identity or affect simulator.
- A feature-maximization project.
- A microservice showcase.
- A system that calls itself autonomous because it can enqueue more work.

The core promise is: **bounded, observable, evidence-driven agent work that makes
local capability better over time without surrendering operator control.**

## Ground Truth You Must Re-Verify

Read current source and live machine evidence; do not inherit these figures as
timeless facts. At the start of this round, the evidence says:

- `aq-qa 0 --json`: 164 passed, 0 failed, 8 skipped. Infrastructure and wiring
  health are strong.
- `aq-report --machine`: overall effectiveness is `fail`; active-window
  delegation completion is 66.7%, coordinator delegate success is 56.6% over
  364 calls, and delegate p95 is measured in minutes.
- Useful-token telemetry is unavailable because agent-run events violate the
  required schema. Trace completeness is `no_data`, yet operator trust is marked
  pass. Six reviewer-gated sessions have zero completed reviews.
- RAGAS averages are approximately 0.49 answer relevance, 0.54 context precision,
  and 0.77 faithfulness. A Phase-0 RAG gate passes at any recall above zero.
- Local routing is 99.7% and embedding-cache hit rate is 92.9%; these are real
  strengths, but locality and cache hits do not prove task usefulness.
- The repo currently exposes roughly 143 `aq-*` files, 249 files under
  `scripts/ai`, 125 config files, 282 coordinator files, 49 coordinator extension
  files, 21 dashboard route modules, and several multi-thousand-line runtime
  modules. Recount with a documented method.
- The AQ-OS round is machine-marked `CONSENSUS_LOCKED` while its manifest has no
  persisted contributions or aggregate path/hash, the human aggregate was
  provisional, and the PRD remained DRAFT. This is a concrete split-brain truth
  failure, not a documentation nit.
- Event-bus v1 is a useful clobber mitigation, but its primary truth is a workspace
  JSONL file. It accepts unsigned events, uses a shared HMAC when signing is on,
  trusts producer timestamps for LWW projection, does full-file reads, lacks
  append fsync, and mirrors to Redis only best-effort.
- NixOS, SOPS, AppArmor/nsjail, local inference, brokered memory, hardware-aware
  scheduling work, activation gates, and the guarded training loop are valuable
  assets that a redesign must preserve.

Treat every green check as one of four distinct claims and verify which it proves:
**available**, **contract-conformant**, **effective**, or **reliable within SLO**.
Never let a presence check stand in for an outcome claim.

## Clean-Sheet Reference Architecture to Challenge

Use this as a falsifiable starting hypothesis, not a predetermined answer.

1. **One modular control-plane application, not dozens of new services.** It owns
   typed intent, runs, tasks, transitions, policy decisions, approvals, and
   evidence. Internal modules have enforced dependency boundaries.
2. **Postgres is durable truth.** Runs, task state, events, reviews, leases, evals,
   costs, and projection checkpoints live transactionally in Postgres. A
   transactional outbox feeds asynchronous consumers.
3. **Redis is ephemeral coordination.** Use it for cache, rate limits, wakeups,
   short-lived queues, and stream delivery—not the sole audit or workflow truth.
4. **Qdrant stores semantic projections, not authority.** Every vector has source,
   version, freshness, confidence, and lineage back to durable records/artifacts.
5. **Artifacts are content-addressed.** Prompts, patches, logs, test evidence,
   model outputs, datasets, and checkpoints have hashes, retention policy, and
   provenance; large artifacts do not live as uncontrolled repo spools.
6. **One versioned contract package.** Intents, commands, events, state
   transitions, errors, capability manifests, configs, APIs, and telemetry share
   generated schemas. Use a CloudEvents-compatible event envelope unless evidence
   favors another standard.
7. **At-least-once delivery, idempotent effects.** Do not claim exactly-once
   execution. Enforce unique idempotency keys, monotonic state revisions,
   transactional side effects, replayability, and explicit dead-letter states.
8. **One model gateway.** Switchboard owns provider/model execution only. The
   control plane owns intent, policy, workflow, and evidence. No alternate caller
   silently reimplements payload, fallback, or routing rules.
9. **Capabilities are admitted modules.** Each capability declares contracts,
   owner, version, permissions, resource budget, health, telemetry, kill switch,
   migration, and retirement criteria. Disabled is a normal state; “everything
   always enabled” is not product integration.
10. **One public API with two first-party clients.** The `aq` CLI and operator
    console call the same OpenAPI-defined API. Compatibility shims are measured
    and retired; they do not become a permanent second product.
11. **NixOS remains the substrate.** Nix declares packages, services, identities,
    secrets, ports, sandboxing, persistence, and rollback. Fast-changing behavior
    lives in versioned application data, not sprawling Nix expressions.
12. **Observability uses stable semantics.** One trace/run ID crosses intake,
    policy, queue, model, tools, review, commit, and learning. Metrics have defined
    denominators, missing-data behavior, cardinality budgets, and SLO ownership.

Explicitly compare this reference architecture with the current AQ-OS PRD's
four-plane model. Keep, amend, or reject each hypothesis with evidence.

## Threats and Failure Modes I Want Treated as First-Class

- Reward corruption: uncertified scorers, readable golden answers, timeout noise,
  duplicate failure capture, and promotion using untrusted pass rates.
- False consensus: quorum without substantive contributions, typed state that
  disagrees with human artifacts, self-review, or late lanes folded informally.
- Split-brain authority: JSON, Markdown, Redis, Postgres, Qdrant, telemetry files,
  and dashboard caches each claiming to be truth.
- Capability escalation: agents reacquiring stripped tools, shared signing keys,
  unauthenticated producers, stale leases, or policy enforced at only one layer.
- Prompt/data exfiltration: local private context crossing remote boundaries,
  injected retrieved content reaching tools, and missing egress attribution.
- Autonomous backlog amplification: fast producers overwhelming human review,
  correction, eval, or local inference consumers.
- Metric gaming and green theater: 100% adoption with no outcome link, health
  passing on file presence, missing data scored as pass, or dashboards showing
  confident composites from partial telemetry.
- Resource collapse: the 35B model, evals, indexing, tracing, and CI competing for
  the same APU/RAM/thermal envelope without admission control.
- Strangler abandonment: new and old paths both survive indefinitely, creating
  more surface area than the design removed.
- Operator bottleneck: every decision waits for one person or one orchestrator;
  alternatively, automation bypasses that person rather than presenting a useful
  bounded approval.
- Supply-chain compromise: models, GGUFs, skills, MCP servers, flake inputs, and
  generated artifacts lack provenance or admission evidence.
- Portability theater: multi-node, WASM, NATS, mobile, or fleet claims land before
  a second hardware target is continuously tested.

For each threat, produce a prevention control, detection signal, response/control,
and recovery test. A policy document alone is not a control.

## How I Want the Next Development Cycles Sequenced

Challenge this ordering, but do not reorder it merely to favor more visible work.

### Cycle 0 — Establish truthful baselines

- Fix consensus-state invariants and bind machine state to contribution/review
  evidence.
- Make effectiveness reporting fail/degrade correctly on missing evidence.
- Define outcome baselines: task completion, review completion, useful artifact
  rate, RAG quality, diagnosis time, operator interventions, and local learning
  delta.
- Inventory authorities, duplicate implementations, compatibility paths, and
  retirement candidates.

Exit: we can trust the scoreboard and replay why a round/run reached its state.

### Cycle 1 — Durable kernel and contracts

- Choose and enforce canonical objects: intent, run, task, event, artifact,
  review, capability, lease, eval, policy decision.
- Put durable workflow/event truth in a transactional store with outbox,
  idempotency, monotonic revisions, replay, and dead-letter semantics.
- Establish import/dependency boundaries for a modular control plane.
- Start schema/config/canon compilation with critical paths first.

Exit: one authoritative lifecycle survives process death and conflicting writers.

### Cycle 2 — Trust, identity, and execution safety

- Bind producer/workload identity to events and actions; assess SPIFFE-style
  short-lived workload identity versus a smaller single-host equivalent.
- Enforce capability leases at both orchestration and tool-execution boundaries.
- Implement egress policy, secret/PII redaction, sandbox evidence, revocation,
  and signed supply-chain admission.
- Make review and approval states durable, queryable, expiring, and non-bypassable.

Exit: a compromised model cannot exceed its lease or hide a privileged action.

### Cycle 3 — Reliable local intelligence and learning

- Measure and improve scheduling, task-class routing, backpressure, cancellation,
  and thermal/resource admission.
- Decide the small-resident-model question from measured memory and throughput,
  not aspiration.
- Industrialize eval isolation, scorer certification, dataset lineage, shadowing,
  promotion, rollback, dedup, and queue budgets.
- Measure whether remote-teacher work actually expands the local capability
  envelope over time.

Exit: local capability improves on a repeatable benchmark without corrupting its
own reward signal or starving interactive work.

### Cycle 4 — Coherent operator experience

- Consolidate toward `aq <noun> <verb>` and one API without breaking existing
  workflows; measure shim use and publish retirement thresholds.
- Build the console only on trustworthy run, trace, lease, eval, cost, queue, and
  approval data.
- Optimize for four questions: what is happening, why, what is at risk, and what
  can I safely do now?

Exit: a new operator can install, perform a first delegation, diagnose a failed
run, intervene, and replay evidence without grep/journal archaeology.

### Cycle 5 — Productization and portability

- Define hardware classes from live probes and benchmark packs.
- Add a second continuously tested hardware target before claiming portability.
- Consolidate tests into risk-tiered local/CI/release gates with explicit runtime
  and resource budgets.
- Practice backup/restore, upgrade/rollback, incident response, and clean-machine
  installation; publish versioned releases and migrations.

Exit: the system can be installed and upgraded from docs, restored from backup,
and its performance claims reproduce on declared hardware classes.

## Required Expert Team

Every participating model must independently simulate the same baseline team:

1. Product and operator-experience lead
2. Distributed-systems/workflow architect
3. NixOS and platform engineer
4. Local-inference/MLOps engineer
5. Data, eventing, and memory architect
6. Security, privacy, and supply-chain reviewer
7. Observability/SRE and capacity engineer
8. Eval, QA, and reliability engineer
9. Developer-experience/API/CLI architect
10. Migration and technical-debt lead

Add specialists only when the brief requires them. Record disagreements between
roles; do not average them away.

## Research Discipline

- Read `.agent/PROJECT-AQOS-PRD.md`, `.agents/plans/aqos-v1/PLAN.md`, its lane
  reviews/aggregate/round manifest, the latest full-system analysis, canonical
  kernel declaration, role matrix, activation audit, issues backlog, system
  overview, and live `aq-qa`/`aq-report` outputs.
- Use the code graph/wiki for orientation, then verify critical claims in source.
- Compare patterns—not feature counts—with durable workflow systems, CloudEvents,
  OpenTelemetry semantic conventions, SPIFFE/SPIRE, object-capability security,
  transactional outbox/event sourcing, and local inference schedulers.
- Treat external systems as references. Every dependency proposal needs a
  build-vs-adopt decision, APU resource cost, failure mode, Nix packaging path,
  security posture, migration cost, and exit strategy.
- Label claims `verified_live`, `verified_source`, `inferred`, or
  `research_required`.

## Required Deliverables From Each Independent Team

1. **One-sentence product definition** and explicit non-goals.
2. **Current-state architecture** showing actual authorities and duplicate paths.
3. **Clean-sheet architecture** with components, ownership, contracts, and data
   flow; include the smallest viable deployable shape.
4. **Parity matrix**: clean-sheet requirement, current equivalent, evidence,
   status, gap, keep/refactor/replace/retire decision, and success metric.
5. **Top 12 gaps** ranked by weighted value, with no more than three P0/P1 items.
6. **Threat model** with prevention, detection, intervention, and recovery tests.
7. **Canonical data model** for run/task/event/review/artifact/capability/lease/eval.
8. **Authority and dependency map** identifying every split-brain state owner.
9. **Migration plan** using strangler steps, dual-path telemetry, retirement gates,
   rollback, and a maximum duration for compatibility paths.
10. **Deletion/consolidation plan**: scripts, configs, services, tests, docs, and
    modules that should disappear or become generated projections.
11. **Development-cycle plan** with dependencies, exact acceptance criteria,
    live validation, observability, intervention, rollback, and resource budget.
12. **Decision log**: accepted assumptions, rejected ideas, open questions, and
    minority objections.

## Prioritization Formula

Score each candidate 0-5 on:

- Outcome/user value — 25%
- Trust, safety, or reliability risk reduced — 20%
- Architectural convergence/debt removed — 20%
- Measurability and learning value — 10%
- Hardware and operational fit — 10%
- Reversibility/migration safety — 10%
- Implementation cost — 5% (reverse-scored)

Then apply these gates:

- No metric or evidence plan: reject.
- No authority/SSOT decision: reject.
- New service without integration-path QA, dashboard/report state, alerting, and
  operator control: reject.
- New config, CLI, or document without a consolidation/retirement effect: return
  for revision.
- Claims of exactly-once, autonomous, secure, portable, healthy, or complete
  without executable evidence: reject.
- UI work before trustworthy backing telemetry: defer.
- Feature work that enlarges two competing paths: reject unless the same slice
  declares and enforces the retirement gate.

## Questions Every Team Must Answer

1. If we rebuilt only the intent—not the implementation—what are the minimum
   components we would create?
2. Which current components are true assets, which are adapters, which are
   transitional, and which are sediment?
3. What single source of truth owns each state transition and why?
4. What can we remove in the same cycle as each addition?
5. Which green metrics currently overstate readiness or effectiveness?
6. What failure cannot be diagnosed from one run/trace today?
7. Where can a model or agent exceed its authority after passing an initial gate?
8. How do we prove that remote-model use increases local-model capability rather
   than merely masking local weakness?
9. What is the resource cost on the actual APU, and what is shed first under
   pressure?
10. What would make an independent adopter abandon the system in the first hour,
    first week, or first upgrade?
11. Which compatibility path will still exist a year from now unless we impose a
    measurable removal deadline?
12. What should we deliberately not build in the next six months?

## Consensus and Output Contract

Follow the flat collaboration protocol:

1. Independent proposals first; no team reads another proposal before completing
   its own.
2. Cross-review every proposal against repo evidence and the scoring formula.
3. Surface conflicts as typed decision objects. Do not silently merge divergent
   authority, storage, security, or sequencing choices.
4. Consensus requires substantive contributions, explicit verdicts, and evidence
   hashes—not only lane status or file presence.
5. Produce one consolidated PRD, one consolidated plan, one decision log, one
   threat register, one parity matrix, and one inter-slice dependency/contract
   table.
6. Do not delegate implementation until the machine-readable round state and the
   human artifacts agree and all blocking integration contracts are signed.

Each team must end with:

`VERDICT: RATIFY | RATIFY-WITH-AMENDMENTS | REJECT — <one evidence-based sentence>`

The consolidator must end with a recommended **first development cycle containing
at most three tightly coupled slices**, the evidence that makes them first, the
capabilities they replace or retire, and the exact stop conditions that prevent
the cycle from becoming another unfinished layer.
