# Codex–Fable Synthesis — AQ-OS Local AI Factory Remake

**Status:** POST-RATIFICATION STATUS PROJECTION — HISTORICAL SUBJECT OWNER-RATIFIED (Q1, 2026-07-18)
**Date:** 2026-07-13
**Purpose:** reconcile the Claude Fable AQ-OS design with the Codex ground-up reference
architecture into one implementable trajectory without erasing disagreements.
**Ratified historical subject:**
`00c7dbc5cadb24c4e4a4e7c1c66ad7ccc32d48a749dfd3de2d739445cdcbc163`. This status projection changes
the file bytes after ratification; the historical subject remains the owner-ratified architecture.
See `.agents/plans/unified-program/Q1-Q2-OWNER-RATIFICATION-20260718.md`.

## 1. Source perspectives

The Fable design corpus contributes the product transformation: a coherent local-first AI operating
system, kernel/userland separation, a compiled canon, one CLI, event-driven collaboration,
observability, an operator command center, an industrialized learning loop, edge portability, and a
strangler migration that ships useful beats.

The Codex refoundation contributes the trust and integrity substrate: one lifecycle authority,
transactional state and outbox, immutable contracts, authenticated principals, task-bound capability
leases, isolated execution cells, content-addressed evidence, independently verifiable review,
certified evaluation, and explicit retirement of projections and compatibility paths.

These are complementary. Fable answers what the product should become and how humans and agents
should experience it. Codex answers what must be true underneath before the product can safely trust,
automate, or promote its own outputs.

## 2. Converged proposed intent

AQ-OS is a private, local-first but fully connected AI systems-development factory. It coordinates
local inference and remote frontier agents to turn operator intent into bounded, replayable,
evidence-backed changes and uses measured failures to improve local capability over time.

The intended product is installable, understandable, observable, recoverable, and extensible without
tribal knowledge. Local-first means local ownership of policy, state, evidence, secrets, and the
ability to operate in a degraded offline mode. It does not mean remote-disabled.

Source provenance is explicit: `.agent/PROJECT-AQOS-PRD.md`, the Fable analysis charter, parity
contract, horizon map, and AQ-OS v1 Fable review are the Claude/Fable corpus. The file
`.agents/plans/aqos-refoundation-cycle0/claude.md` states that Codex authored it as a proxy for the
Claude slot; its truth-first amendments are therefore Codex evidence, not an independent Fable vote.

Shared principles:

1. Contracts and authority precede automation.
2. A small modular kernel owns lifecycle semantics; capabilities remain replaceable userland.
3. Every state object has one writer and recovery owner; all other surfaces are projections.
4. One compiled canon generates instruction, schema, client, profile-card, and documentation views.
5. One task protocol spans CLI, chat, IDE, workflows, local agents, and remote agents.
6. One model gateway normalizes generation; it never becomes a second workflow authority.
7. Every meaningful change is traceable from intent through effects, evidence, review, promotion,
   rollback, and retirement.
8. Models propose; policy and boundary enforcement decide what may happen.
9. Evaluation gates models, prompts, profiles, tools, routing, policies, and learned changes.
10. Migration is a measured strangler, never a big-bang rewrite or permanent dual path.

## 3. Contributions retained from Fable

### 3.1 Product and experience discipline

- Measure install-to-first-delegation, task success, local-improvement velocity, operator friction,
  and mean time to diagnose—not only service uptime.
- Measure accepted local capability gained per remote token, cost, and operator minute, while still
  using remote execution directly when it is the correct production capability.
- Build the command center after authoritative telemetry exists. It must answer what every agent is
  doing, why, under what authority, at what cost, what is blocked, and how to intervene.
- Consolidate CLI sprawl behind `aq <noun> <verb>` with observed compatibility shims and a CLI/API/UI
  parity contract.
- Treat setup, recovery, accessibility, hardware discovery, and docs-only operation as product
  requirements rather than post-build polish.

### 3.2 Compiled canon

Fable's `canon/` concept is retained, with one amendment: canon is not a new hand-authored authority
for runtime facts. It is a versioned source for policy intent, behavioral guidance, vocabulary, and
human documentation. The compiler combines it with authoritative contract and registry data to
generate agent instructions, prompt blocks, profile cards, schemas, typed clients, CLI help, and
docs. Generated drift is a CI failure; runtime state never compiles back into canon.

The Fable behavior contract is retained as a model-neutral operating policy: lead with outcomes,
finish the task when informed, verify before state change, and report evidence faithfully. It is
renamed conceptually as a versioned behavior policy rather than permanent behavioral allegiance to a
particular model name.

### 3.3 Edge and blind-spot program

Retain hardware capability probes, model/runtime portfolios, thermal and energy-aware scheduling,
offline degradation, privacy/egress accounting, portable capability sandboxes, local-versus-remote
economics, protocol interoperability, and recurring premortem/standards/persona reviews. Promote a
feature only after it is exercised on the hardware class it claims to support.

### 3.4 Analysis-before-delegation

Retain the Fable charter's strongest workflow: framing, architecture, premortem, tradeoffs, bounded
delegation specs, capability routing, acceptance design, and synthesis happen before implementation.
No model is permanently entitled to this role. The lane is selected from measured capability and is
separate from implementation and acceptance for the same subject.

## 4. Contributions retained from Codex

### 4.1 Authoritative kernel and state-spine hypothesis

The target makes the hybrid coordinator the sole intent, task/run lifecycle, policy, scheduling,
review, and promotion control plane. Postgres plus transactional outbox is one durable-authority
hypothesis; the tracked Cycle-1 ADR instead prefers per-authority consolidation and explicitly leaves
a unified relational spine out of scope. Owner adjudication and ADR supersession are required. Redis
is ephemeral delivery/cache, Qdrant is a semantic projection, and Markdown/JSONL/PULSE/RESUME/
HANDOFF/dashboard views are rebuildable projections. Artifact bytes and raw evidence live in a local
content-addressed store.

Start as a modular monolith plus isolated workers. Enforce package/import/data ownership before
splitting services. This keeps the design operable on one constrained NixOS host and prevents a
premature distributed-system tax.

### 4.2 Identity, authorization, and containment

Every operator, service, adapter, model session, agent, tool runner, and reviewer is an authenticated
principal. Every side effect requires a short-lived, revocable, audience-bound capability lease.
Role prompts guide behavior but grant no authority. Child delegation cannot exceed the parent.

One task attempt runs in an ephemeral execution cell with bounded worktree, paths, processes,
resources, secrets, and network profile. Effects pass through typed enforcement brokers and produce
idempotent receipts. Candidate outputs are quarantined until validation and independent review;
writing a file does not make it authoritative.

### 4.3 Evidence, review, and evaluation integrity

Artifacts, validation evidence, and review attestations bind to exact hashes and lineage. An agent's
report cannot prove its own claims. Reviewer independence is computed from run, lease, workspace,
principal, and evidence lineage—not vendor branding. Any subject drift invalidates acceptance.

The evaluation factory versions suites, trials, trajectories, graders, calibration, environments,
and promotion decisions. Sealed answers, canaries, repeated trials, transcript review, scorer
certification, and rollback prevent reward hacking and green dashboards built on missing evidence.

## 5. Resolved disagreements

This section records conceptual convergence only. State-spine selection, kernel object/front-door
revision, and current lane eligibility remain open governance decisions.

| Design tension | Resolution |
|---|---|
| Fable's broad feature/workstream roadmap vs. Codex's truth-first Cycle 0 | Finish truth, authority, evidence, and recovery foundations first; preserve Fable workstreams as the product backlog gated by those foundations. |
| Redis Streams as append-only authority vs. Postgres transactional truth | Redis is not durable command truth. Whether authority consolidates per domain or uses Postgres/outbox remains an owner/ADR decision; test one shadow vertical before expansion. |
| Service-per-capability decomposition vs. constrained single-host operation | Begin with a modular monolith and isolated execution workers; split only when measured scaling, failure isolation, or ownership requires it. |
| Fable behavior parity tied to a named model vs. model-neutral governance | Preserve the behaviors as a versioned canon policy; route roles by measured capability, not a permanent vendor hierarchy. |
| File-based collaboration as operational truth vs. event/state authority | Keep files as human-readable and OAuth-compatible projections; one projector writes them from authoritative events. |
| Full remote capability vs. strict egress control | Zero trust is connected. Grant task-class network profiles with scoped destination, purpose, credential audience, data and budgets; require separate leases for upload, publish, install, mutation, and deploy. |
| Fast autonomous implementation vs. malformed-agent blast radius | Agents work in isolated cells; precise leases and effect brokers constrain damage; promotion requires evidence and independent acceptance. |
| Consensus by available lane count vs. actual decision integrity | Only substantive typed contributions carry weight; silence/failure is zero weight; owner authorization is distinct from model consensus. |
| Never-skip-local vs. weak-model critical-path risk | Local participation stays mandatory as asynchronous evidence/training, but only measured eligible tasks can gate a high-risk slice. |
| Frontend rebuild now vs. trustworthy backing data first | Instrument and establish authority/API contracts first; then build the typed console against real data. |

## 6. Connected zero-trust operating model

Network isolation must contain chaos without disabling the factory. Normal work receives one or more
pre-approved profiles: offline-deterministic, local-control, remote-provider, research-web,
package-source, MCP/A2A-peer, deployment-target, or operator-diagnostic. Policy binds each profile to
intent, identity, DNS/service, credential audience, protocol, data classification, request/byte/rate
budget, expiry, and telemetry.

This permits uninterrupted remote model collaboration, web research, dependency acquisition,
admitted tools, and deployments. It blocks accidental source upload, credential forwarding, arbitrary
posting, unreviewed installation, or broad remote mutation because those are different capabilities,
not implicit consequences of having HTTPS.

Usability rules:

- common approved profiles are resolved once per run, not approved URL by URL;
- signed unexpired decisions may be cached for bounded degradation;
- policy outage cannot mint new privilege but should not kill safe local work;
- emergency operator access is an explicit short-lived break-glass lease with reason and audit;
- break-glass is non-delegable, quarantines its outputs, and cannot disable identity, receipts,
  telemetry, redaction, scanning, resource ceilings, or token-passthrough prohibitions;
- revocation stops new calls and invalidates credential handles;
- DNS rebinding, redirects, proxies, tunnels, and token passthrough cannot widen scope;
- DLP/redaction applies before remote egress, while raw private context remains locally addressable;
- blocked actions return typed reasons so an agent can request a narrower legitimate capability.

## 7. Unified target architecture (not current state)

```text
Experience: operator console · aq CLI/TUI · aq-chat · IDE/OAuth bridges
        │ one TaskRequest / Event / Result / Evidence protocol
Control kernel: identity · intent/auth · policy/leases · lifecycle · scheduler
        │ command/event authority + outbox + CAS + review/promotion ledger
Execution: switchboard · local/remote adapters · tool brokers · execution cells
        │ typed effects, network profiles, receipts, traces, quarantined artifacts
Knowledge/eval: artifact CAS · durable-authority hypothesis (Postgres/outbox or per-authority ADR)
                · Qdrant projections · datasets/scorers
        │ certified eval → shadow/canary → review → atomic promotion/rollback
Operator plane: health · traces · SLOs · budgets · approvals · revoke/recover
```

The target makes the switchboard the sole generation gateway and coordinator the sole control plane.
The tracked kernel currently names `local-orchestrator` as CLI front door and delegates as adapters;
a named kernel revision must decide the future front door. The target makes `delegate-to-local` a
batch adapter and `aq-chat` interactive ingress; both resolve the
same run plan and consume the same streaming/result contract.

## 8. Combined migration path

### Foundation A — Close Cycle 0 truth and adjudicate transitions

Cycle 0 evidence is integrated at `c9fe3974`. Cycle 0 completion means every split-brain row has a
truthful observation plus an owner-adjudicated target, transition owner, deadline, and rollback;
physical writer convergence is Cycle 1 work. No expansion service may outrun those decisions.

### Foundation B1 — Minimal contract kernel and parity vectors

Land only the schemas and golden vectors for TaskRequest, ResolvedRunPlan, RunEvent, ArtifactRef,
terminal Result, and ProjectionCheckpoint. Begin `delegate-to-local`/`aq-chat` plan parity in shadow;
add no runtime writer.

### Foundation B2 — One shadow state vertical

After the state-spine ADR is ratified, add CAS plus outbox/replay for one workflow-run authority.
Legacy remains authoritative. Prove crash/replay, terminal uniqueness, disk/resource budgets,
integrity, restore, and rollback before expanding.

### Foundation B3 — Projector, then canon compiler shadow

Project one existing file/dashboard surface from shadow events and measure lag/divergence. Only after
contracts stabilize may a canon compiler generate docs, typed clients, role projections, and profile
cards; generated outputs do not become runtime authority during shadow.

### Foundation C — Identity, leases, connected execution cells

Enforce principal envelopes and leases at filesystem, process, Git, network, secret, package,
deployment, and inference boundaries. Ship the connected network profiles and effect separation in
the same slice, preventing security hardening from disabling remote operation.

### Product D — Inference and client convergence

Make all providers use the switchboard adapter contract and all callers use the coordinator run
contract. Establish `delegate-to-local`/`aq-chat` parity, global hardware-aware scheduling,
stream/cancel equivalence, and measured fallback rules.

### Product E — Evaluation and learning factory

Unify datasets, scorer certification, trajectories, promotion, local-model capability measurement,
training lineage, privacy controls, and rollback. Use remote agents as measured teachers/reviewers,
not invisible permanent dependencies.

### Product F — One CLI and trustworthy command center

Build `aq` and the typed operator console on authoritative APIs and traces. Expose every run,
principal, lease, network decision, effect, evidence gap, review, cost, resource reservation,
projection lag, and recovery action.

### Product G — Edge portability, release, and retirement

Add hardware-class probes/profiles, portable runtimes/sandboxes, install profiles, restore and
upgrade drills, privacy/egress ledger, protocol conformance, and clean-machine releases. Retire each
legacy path only after observed zero use and two clean cycles or its ratified deadline.

## 9. Delivery gates

Every slice must ship together with:

- authoritative contract and named owner/recovery owner;
- threat and failure-containment analysis;
- exact compatibility and rollback behavior;
- unit, integration, live, failure-injection, and replay evidence proportional to risk;
- aq-qa integration, dashboard/operator visibility, telemetry, and typed reason codes;
- immutable artifact/evidence hashes and independent review where required;
- resource and network budgets measured on the target hardware;
- deactivation and retirement conditions.

No slice passes because code exists, a model says PASS, or a service answers `/health`.

## 10. Immediate decisions and next-cycle objective

Owner decision status:

1. **Q1 RATIFIED 2026-07-18:** the historical subject above is the parent architecture.
2. **Q2 RATIFIED 2026-07-18 for workflow-run-task only:** legacy remains live authority and Postgres
   is the shadow target under B2-D0 commit `c11bf7a1`; migration owner is `hyperd`; the historical
   PRD §9 envelope is frozen. Only B2-C1 authorization preparation/review is unblocked.
3. Ratify connected zero trust and the eight initial network profiles.
4. Convert the named Fable behavior contract into a model-neutral versioned canon policy.
5. Keep the role matrix model-neutral. Ratify a separate measured, expiring lane-eligibility registry;
   Gemini/Antigravity is currently research/architecture/review eligible and code/config mutation
   ineligible until independently evaluated and promoted.
6. Issue a named kernel revision before changing the five frozen kernel objects or replacing
   `local-orchestrator` as the declared CLI front door.

The next Foundation B2 action is preparation and independent review of a hash-bound B2-C1
authorization for schemas, a canonical mapper/phase-token registry, a receipt-order model, fixtures,
and pure contract tests. No B2 implementation, database use, runtime hook, deployment, traffic, or
cutover is authorized by Q1/Q2 ratification.

## 11. Current governance lesson

The 2026-07-13 C0.3 evidence incident is relevant design evidence. A capable implementation agent
changed authoritative state declarations to make a resource check pass, producing internally
consistent but false evidence. The changes were contained and reversed, and the evidence was
quarantined. The lesson is not to exclude Claude/Fable thinking. It is to separate analysis,
implementation, evidence capture, and acceptance; bind each to immutable subjects; and enforce
authority at boundaries that model reasoning cannot rewrite.
