# PRD — Ground-Up Local AI Systems Development Factory

Status: REQUEST_REVISION — architecture converged; state-spine and kernel decisions unresolved
Owner: hyperd
Prepared: 2026-07-13
Scope: local inference, agent evaluation, flat collaboration, zero-trust execution, and systems-development automation

## 1. Product definition

Build a private, local-first AI systems-development factory on NixOS: a managed control plane that
turns operator intent into bounded, replayable, evidence-backed software changes. Local and remote
agents collaborate as peer reasoning nodes, but no model, role, CLI, service, or coordinator receives
implicit authority. Every action is attributable, leased, observable, revocable, and independently
verifiable.

The system is not a collection of chat agents, an inference server with scripts around it, or an AGI
persona. It is an operating environment for engineering work with the same rigor expected from a
secure build system, workflow engine, evaluation laboratory, and production control plane.

### Intended outcomes

- One operator can safely use local, embedded, specialist, flagship, and budget models together.
- Equivalent work has equivalent routing, authority, context, result, evidence, and telemetry across
  CLI, chat, IDE, workflow, and remote-agent surfaces.
- Model, prompt, policy, tool, dataset, scorer, and runtime changes are evaluated and promoted through
  one evidence-bound lifecycle.
- Every failure is diagnosable from one trace and immutable artifacts without cross-file archaeology.
- The factory can reconstruct its decisions, recover after process death, and prove what was changed,
  by whom, under which authorization, using which inputs.

## 2. Design doctrine

1. Authority is not intelligence. Stronger models receive broader reasoning budgets, not ambient
   permissions.
2. Flat collaboration means protocol equality, not equal write or acceptance authority.
3. The model proposes; deterministic policy and tool boundaries authorize and enforce.
4. One object has one authoritative writer. Files, caches, dashboards, vectors, and reports are
   projections unless explicitly declared otherwise.
5. At-least-once delivery plus idempotent effects; never claim distributed exactly-once behavior.
6. Immutable evidence precedes interpretation. Reports reference evidence and cannot attest themselves.
7. Fail closed on unknown identity, stale policy, malformed contracts, missing telemetry, unproven
   fallback equivalence, and untrusted eval signals.
8. Content and instructions are separate trust domains. Retrieved text, tool output, websites, files,
   and messages are untrusted data even when useful.
9. Instrument before optimization. Every subsystem ships with trace, metrics, health, effectiveness,
   resource, and intervention surfaces.
10. A modular monolith is the first target. Split services only when isolation, scaling, or ownership
    evidence justifies the operational cost.
11. NixOS declares the substrate; runtime policy cannot invent ports, secrets, packages, identities,
    persistence, or privileges outside the declaration.
12. Compatibility is measured debt with an owner and expiry, never a permanent second authority.

## 3. Ground-up target topology

The diagram is target state. C0.3 established truthful current split-brain evidence; it did not
authorize or prove the target writers below. Every migration PRD must name current, target, and
transition authority explicitly.

```text
Human / CLI / aq-chat / IDE OAuth bridge / workflows / remote agents
                              │
                              ▼
                    Contract + Identity Gateway
               validate · authenticate · version · trace
                              │
                              ▼
             AQ Control Plane (sole lifecycle authority)
  intent · policy · leases · workflow · scheduler · routing · review
                              │
          ┌───────────────────┼────────────────────┐
          ▼                   ▼                    ▼
   State/Event Spine      Artifact CAS       Registry/Policy Store
 Postgres + outbox       immutable bytes     immutable versions + aliases
          │                   │                    │
          └──────────────┬────┴────────────────────┘
                         ▼
                 Switchboard Execution Gateway
        canonical payload · stream · cancel · usage · errors
             ┌───────────┼───────────┬─────────────┐
             ▼           ▼           ▼             ▼
       local llama   embedded    specialist     remote/OAuth
             │
             ▼
      Lease-Enforced Tool Runtime
 worktree · namespace · cgroup · AppArmor · egress · secret handles

Projectors: dashboard · CLI views · OTel · PULSE/RESUME/HANDOFF · Qdrant
Evaluation factory: manifests · sealed datasets · scorers · replay · promotion
```

### Authority resolution

- Hybrid coordinator/control plane owns intent, run/task lifecycle, policy decisions, leases,
  scheduling, route decisions, reviews, and promotion.
- Switchboard owns provider/model execution only. It cannot authorize tools, rewrite task state, or
  silently change capability.
- The tracked kernel currently declares `local-orchestrator` as CLI front door and every
  `delegate-to-*` script as an adapter. Making `delegate-to-local` the canonical batch ingress is a
  target hypothesis that requires a named kernel-revision decision; `aq-chat` remains interactive.
  `dispatch.py`, provider delegates, and IDE bridges are clients/adapters, never lifecycle authorities.
- Postgres plus a transactional outbox is a candidate authoritative state hypothesis. The tracked
  Cycle-1 ADR currently prefers per-authority consolidation and says a unified relational spine is
  out of scope. The owner must select/supersede that ADR before either design is implemented. Redis is
  disposable queue/cache/wakeup state. Qdrant is a rebuildable semantic projection. A local CAS holds
  immutable prompts, outputs, patches, logs, reviews, datasets, and eval evidence.

## 4. Canonical contracts

All contracts use versioned JSON Schema, reject unknown fields at security boundaries, have stable
typed errors, canonical serialization, content digests, compatibility policy, and golden vectors.

### 4.1 PrincipalEnvelope

Defines the authenticated execution principal:

- principal, human sponsor, run, parent and delegation-chain IDs;
- provider, model/build digest, agent adapter, assigned role, lane, and sandbox identity;
- prompt, policy, configuration, Nix-generation and workspace digests;
- attestation issuer, audience, issued/expiry times, revocation epoch.

Role names guide reasoning. Only the authenticated envelope and active lease participate in policy.
For a single host, start with kernel-observed process identity plus locally signed short-lived
credentials; preserve a path to SPIFFE/SPIRE workload attestation rather than deploying fleet
infrastructure prematurely.

### 4.2 Intent and Authorization

```text
DRAFT → REVIEWED → AUTHORIZED → ACTIVE → CONSUMED
                    └────────→ SUSPENDED | EXPIRED | REVOKED
```

Authorization binds objective, anti-goals, exact subject/package hash, permitted actions and paths,
eligible principals/reviewers, resource budgets, required evidence, stop conditions, rollback plan,
policy version, expiry, revision, and use count. Activation and every mutation use compare-and-swap
with a fencing token. Resuming work requires live revalidation.

### 4.3 TaskRequest and ResolvedRunPlan

TaskRequest expresses desired outcome, task class, domain, context references, artifact contract,
side effects, requested tools/profile, response mode, budgets, fallback policy, and validation needs.
The trusted resolver produces an immutable ResolvedRunPlan containing effective identity, role,
capabilities, tools, paths, model/profile, prompt/context versions, resource reservation, fallback
equivalence proof, configuration digest, reason codes, and evidence obligations.

Request priority affects scheduling only. Callers cannot assert an effective role, tool grant, write
authority, or interactive priority.

### 4.4 CapabilityLease

Every side effect requires a signed, short-lived lease containing:

```text
lease/principal/intent/run IDs · parent lease · allowed tools/actions
read/write paths · command classes · network destinations · secret handles
token/tool/time/CPU/RAM/GPU/network/cost budgets · audience · expiry
max delegation depth · policy hash · revocation epoch · idempotency nonce
```

Lease authority is monotonic: a child cannot exceed its parent; stripped authority cannot be
reacquired through fallback, retry, role text, environment, or another tool. The policy decision point
is separate from enforcement, but enforcement occurs at the actual filesystem, process, network,
secret, Git, deployment, and model-execution boundaries.

### 4.5 RunEvent, ArtifactResult, and Error

- Events are append-only, causally linked, monotonically sequenced, producer-authenticated, and
  idempotent by source/event ID.
- Each accepted run has exactly one terminal event/result: complete, partial, blocked, failed, or
  cancelled.
- Results carry the resolved plan, typed artifacts, observed/inferred/proposed claims, evidence refs,
  validation, effects, usage, timing, provenance, limitations, and stable next action.
- Errors include stable code, safe detail, retryability, failed boundary, evidence, and resolution.
- Mutable `latest` names are atomic pointers to immutable artifacts with run ID and hash.

### 4.6 ReviewAttestation

A review is signed and bound to the exact subject hash, acceptance-criteria hash, implementer lineage,
reviewer principal/lease, reproduced checks, findings, residual risk, expiry, and invalidation-on-drift.
Independence is computed from execution principal, run, lease, workspace, and evidence lineage—not
provider brand. Implementers cannot accept their own work.

### 4.7 Tool and A2A contracts

- Tools have immutable schemas, safety classes, side-effect declarations, lease claims, sandbox and
  egress needs, timeout/resource budgets, structured results, and telemetry hooks.
- MCP is the tool/resource interoperability boundary; tool annotations remain untrusted unless the
  server is admitted and authenticated. OAuth tokens are audience-bound and never passed through.
- A2A Agent Cards advertise identity, skills, endpoint and auth requirements; AQ extends the task and
  artifact exchange with lease, policy, trace, evidence, and review attestations.
- All remote and local agents consume the same TaskRequest and produce the same event/result forms.

## 5. Immutable SSOT catalog

| Authority | Owns | Generated projections |
|---|---|---|
| Kernel contract registry | object/lifecycle/schema semantics | docs, client types |
| Identity trust roots | principal/workload attestations | agent status cards |
| Policy bundle registry | eligibility, authority, review, egress, budgets | role/instruction summaries |
| Capability/tool registry | tool versions, safety class, permissions, probes | MCP catalogs, skills index |
| Model-build registry | weights/tokenizer/template/quant/runtime/hardware provenance | model aliases, cards |
| Prompt/context registry | templates, compilers, compaction/redaction rules | model-tier prompts |
| Execution-profile registry | capability semantics and equivalent fallback sets | route aliases |
| Dataset registry | cases, splits, licensing, sealed-answer hashes | suite views |
| Scorer registry | scorer code, calibration, certification, validity | scorecard labels |
| Environment registry | Nix closure, sandbox, service config, hardware fingerprint | deployment views |
| Command/event log | lifecycle and audit truth | task registry, PULSE, RESUME, dashboard |
| Artifact CAS | immutable input/output/evidence bytes | named latest pointers |
| Promotion ledger | alias changes, review, eval, soak, rollback | capability lifecycle registry |
| Memory/evidence ledger | provenance-bearing knowledge writes | AIDB/Qdrant indexes |

The port SSOT remains `nix/modules/core/options.nix`; environment-name SSOT remains
`config/env-contract.yaml`. Neither owns higher-level application behavior.

## 6. Inference subsystem

### 6.1 Model abstraction

Register a model build, not a marketing name: weight digest, architecture, quantization, tokenizer,
chat template, tool grammar, runtime version, context envelope, stop policy, license, source
provenance, measured hardware envelope, and certified task capabilities.

Aliases such as `default`, `embedded`, `coding_logic`, and `flagship` are atomic policy pointers with
promotion evidence. Profiles describe capability/SLO semantics independently from the model that
currently realizes them.

### 6.2 Prompt/context compiler

Deterministically compile canon, role projection, task, recent typed messages, memory/evidence refs,
tool schemas, output schema, and budgets into a PromptManifest. Record input digests, token accounting,
redactions, context loss, template/compiler versions, and compaction decisions. Model-tier adapters
change representation and decomposition depth, never authority.

### 6.3 Scheduling and resource arbitration

- Queue classes: interactive, validation, normal, background, batch.
- MLFQ with aging, deadlines, admission control, and reserved validation capacity.
- Reservations cover model slot, model swap, prompt/KV cache, CPU, RAM, shared VRAM, thermal, disk,
  queue time, remote quota, and cancellation budget.
- Backpressure is typed and visible. Busy local capacity queues or blocks; it never silently weakens
  capability or drops a required local consensus lane.
- Resident small models handle classification, schema repair, risk scoring, extraction, and short
  verification only after measured promotion. Large local models are session-loaded for work whose
  value justifies swap and latency cost.

### 6.4 Execution normalization

All local and remote providers implement one adapter API for final/streaming generation, usage,
cancellation, tool calls, finish reasons, retry classification, and health. Every llama-bound path
uses one canonical payload builder. Stream and final reconstruction must be content/usage equivalent.
Fallback requires a versioned equivalence proof; only explicit best-effort mode may change capability.

## 7. Zero-trust execution cells

Zero trust is not an offline-mode requirement. The factory is local-first but intentionally
connected: remote model lanes, OAuth bridges, MCP/A2A peers, research, package sources, update
channels, and operator diagnostics are product capabilities. The control objective is to prevent
ambient or unaccountable connectivity, not to prohibit connectivity.

One task attempt receives one ephemeral cell:

- isolated Git worktree and mount namespace;
- dedicated Unix identity/cgroup and bounded CPU/RAM/GPU/PIDs/time;
- AppArmor plus seccomp/systemd restrictions;
- a task-class network profile: offline-deterministic, local-control, remote-provider,
  research-web, package-source, MCP/A2A-peer, deployment-target, or operator-diagnostic;
- deny undeclared destinations and protocols, while pre-authorized profiles receive usable leased
  connectivity without per-request human prompts;
- no ambient secrets—only short-lived handle-based access;
- canonical no-follow path resolution and atomic output creation;
- immutable input mounts, quarantined outputs, malware/secret/license scans;
- bounded termination and orphan reaping on cancellation/revocation.

Shared state changes only through typed brokers with CAS, fencing tokens, idempotency receipts, and
audit events. Git commits are promoted artifacts after validation/review, not direct model authority.
Rollback is a compensating event or revert; destructive history rewriting is never an autonomous
recovery mechanism.

### 7.1 Connected zero-trust network model

The network policy decision is resolved before execution and enforced at the cell boundary. A
NetworkCapability binds principal, intent, run, purpose, protocol, DNS name and resolved-address
constraints, port/service, credential audience, request/byte/rate budget, data classification,
expiry, and audit requirements. DNS rebinding, redirects, proxies, tunnels, token passthrough, and
connection reuse cannot expand the effective destination set.

| Profile | Normal use | Default access | High-risk effects |
|---|---|---|---|
| offline-deterministic | sealed evals, static validation, cache-only builds | no network | none |
| local-control | local inference and harness coordination | only declared Unix sockets and loopback services; arbitrary localhost denied | none |
| remote-provider | Claude/Codex/Gemini and approved inference APIs | admitted provider endpoints with audience-bound OAuth/token handles | model response remains untrusted |
| research-web | standards, documentation, OSINT | brokered HTTP(S), read-only methods, download quarantine, DLP/redaction | login, posting, upload, or execution requires another lease |
| package-source | Nix, language registries, signed artifacts | pinned registries/mirrors; digest/signature verification | dependency mutation requires plan/review evidence |
| MCP/A2A-peer | admitted tools and agent peers | authenticated registered endpoints and advertised capabilities | tool side effects require their own effect lease |
| deployment-target | scoped deploy/health operations | named target and declared service API/SSH command class | destructive or broad changes require operator co-signature |
| operator-diagnostic | incident investigation | explicitly activated destinations and duration | recorded break-glass reason, bounded TTL, post-use review |

There are **eight** initial profiles in this table. Profile ratification must include enforcement,
DNS/redirect behavior, credential audience, revocation, and test ownership; a prose name alone is not
an access-control boundary.

Connectivity remains available when the policy service is temporarily impaired through signed,
cached, unexpired profile decisions with narrow offline semantics. New authority cannot be minted
while disconnected from policy authority. Emergency access is a time-boxed operator break-glass
lease, never a hidden fail-open mode. Revocation stops new connections, rotates or invalidates
credential handles, and terminates affected cells within a bounded grace period.

Provider and service credentials stay in an audience-bound broker and never enter the model cell.
Break-glass cannot disable identity, receipts, telemetry, resource limits, redaction, artifact
quarantine, or the prohibition on token passthrough. Secret access and broad web egress are not
co-located; a broker performs the narrow operation and returns a redacted typed result.

Network access alone does not authorize consequential action. For example, a research agent may
read a site but cannot publish, upload source, install a package, invoke a mutating remote tool, or
deploy merely because it has HTTPS access. Those effects require separate typed capabilities. This
separation keeps the system operable and connected while limiting a malformed agent to its cell,
budget, destinations, and explicitly leased effects.

## 8. Evaluation factory

### 8.1 Evaluation object model

- EvalSuite: objective, capability boundary, population, datasets, trials, graders, thresholds.
- EvalRunManifest: exact model, prompt, profile, policy, tools, environment, seed, budgets, and inputs.
- Trial/trajectory: complete typed events, tool receipts, artifacts, timing, and terminal result.
- ScorerCertification: known-good/known-bad discrimination, determinism, abstention, isolation,
  calibration, validity window, and producer lineage.
- EvalResult: case/trial scores, uncertainty, infra-invalid counts, first-pass and recovered quality,
  safety, resources, latency, cost, and evidence hashes.
- PromotionDecision: baseline/candidate delta, review, soak/canary, rollback pointer, alias transition.

### 8.2 Evaluation layers

1. Contract/conformance: schemas, route parity, tool-call shape, cancellation, terminal uniqueness.
2. Deterministic outcome: tests, types, static/security analysis, exact state assertions.
3. Capability: representative coding, review, retrieval, planning, tool, and recovery tasks.
4. Safety: prompt injection, path/symlink escape, confused deputy, secret exfiltration, privilege
   reacquisition, sabotage, sandbagging, grader gaming, and repeated-attempt attacks.
5. Systems: TTFT, tokens/sec, queue, RSS/VRAM, thermal, swap, cancellation, crash/replay, restore.
6. Behavioral: calibrated model graders plus human review for qualities that code cannot determine.
7. Shadow/counterfactual: replay production-shaped traces without effects, changing one versioned
   component at a time.

Use multiple trials for probabilistic behavior. Separate model failure, policy block, tool failure,
infrastructure invalidity, evaluator abstention, and recovered success. A repair or stronger fallback
does not erase first-pass weakness.

### 8.3 Eval integrity

- Golden answers are sealed from the agent namespace and referenced only by graders.
- Randomize case order and canaries; monitor contamination and memorized benchmark signatures.
- Transcript review detects loophole exploitation and grader gaming.
- Scorers cannot promote themselves; uncertified scores cannot influence training, routing, alerts, or
  promotion.
- Every promotion requires paired evidence against the current default, confidence/variance, resource
  regression checks, independent review, canary/soak, and an atomic rollback target.

## 9. Collaboration and software-factory lifecycle

```text
ORIENT → RESEARCH → INTENT/PRD → REVIEW/CONSENSUS → AUTHORIZE
→ ASSIGN → EXECUTE IN CELLS → VALIDATE → INDEPENDENT REVIEW
→ PROMOTE/COMMIT → DEPLOY/CANARY → OBSERVE/LEARN/RETIRE
```

- Each expert pass gives every eligible model the same role baseline; passes create angle diversity,
  agents create model diversity.
- Contributions, conflicts, votes, waivers, assignments, interface contracts, and verdicts are typed,
  immutable objects—not shared-file races.
- Consensus never creates operator authority. Owner authorization is a distinct attributed decision.
- Agent eligibility is discovered from admitted capabilities and current health, not hardcoded vendor
  assumptions. Gemini/Antigravity is currently reviewer/research/PRD-only until programming capability
  is separately evaluated and promoted; Claude Opus is the preferred implementation lane; local models
  receive bounded tasks matched to measured envelopes.
- Interface seams are negotiated as versioned contracts before parallel implementation. A commit queue
  serializes accepted artifacts after review.

## 10. Data, memory, learning, and retention

- Operational state, evidence, knowledge, and semantic search are distinct data classes.
- Memory writes require source, claim type, confidence, freshness, privacy, retention, and lineage.
- Qdrant/AIDB is an index, never the only copy or authority. Rebuild and freshness checkpoints are
  routine tests.
- Hot memory remains an index; warm topic files retain active detail; cold archives are immutable.
- Learning promotion is gated by certified evals, dedup/backpressure, human review where required,
  dataset lineage, contamination checks, canary, and rollback.
- Retention/GC operates from reachability and policy over the CAS; it cannot purge evidence referenced
  by active authorization, review, release, incident, or promotion records.

## 11. Observability and operator plane

Canonical events project into OpenTelemetry traces:

- top span: intent/run;
- children: policy, scheduling, prompt compile, model generation, tool execution, validation, review,
  artifact publication, and promotion;
- metrics: queue/TTFT/inference/total latency, tokens, tool use, errors, resources, fallback deltas,
  lease denials/revocations, eval quality/variance, scorer trust, and projection lag.

Prompt/tool content is opt-in, redacted, size-bounded, and separately access-controlled. Default
telemetry stores digests and safe metadata. The dashboard exposes run waterfall, queue/resources,
routing reasons, active leases, blocked effects, evidence freshness, eval comparisons, scorer
integrity, promotion history, recovery readiness, and all intervention commands. Blank required fields
are delivery failures.

## 12. Threat model and controls

| Threat | Primary containment |
|---|---|
| Role/identity spoofing | authenticated PrincipalEnvelope; role resolved by policy |
| Direct/indirect prompt injection | instruction/data separation; independent leases; adversarial evals |
| Confused deputy | audience-bound lease and explicit on-behalf-of chain |
| Stale/replayed authorization | expiry, nonce, CAS revision, revocation epoch, subject hash |
| Scope/path expansion | canonical no-follow paths, exact lease, enforcement at filesystem boundary |
| Split-brain/concurrent writers | one authority, fencing tokens, monotonic revisions, CAS |
| Fabricated evidence | independent raw capture, CAS, signed provenance, reviewer reproduction |
| Self-review/collusion | lineage-aware separation and risk-tier quorum |
| Supply-chain compromise | pinning, signatures, SBOM, Nix closure, quarantine, admission gate |
| Secret/source exfiltration | secret handles, redaction/DLP, egress allowlist |
| Resource denial/starvation | reservations, queue classes, quotas, thermal/cgroup budgets |
| Eval cheating/contamination | sealed answers, canaries, transcript audit, repeated trials |
| Recovery poisoning | signed checkpoints, replay validation, restore drills |
| Telemetry suppression | external append-only receipt path; missing evidence fails closed |
| Compromised orchestrator | cannot mint beyond parent lease; high-risk operator co-signature |

## 13. Current-system critique

Strong assets to retain:

- declarative NixOS substrate, local-first execution, secrets discipline and hardware awareness;
- coordinator, switchboard, llama.cpp, AIDB/Qdrant/Redis/Postgres foundations;
- AppArmor/systemd controls, broad QA corpus, dashboard, memory discipline and learning-loop work;
- explicit role separation, review gates, capability lifecycle, workflow canon, issue logging and
  evidence-oriented Cycle 0 refoundation.

Material gaps to close:

1. All ten cross-system state domains are currently split-brain or have unowned recovery boundaries.
2. Security policy is partly prompt/file convention and contains fail-open/privileged defaults.
3. Principal, authorization, review, and evidence identities are unsigned mutable strings/files.
4. Local/chat/delegation/remote routes do not yet share one enforced request-plan-event-result contract.
5. Routing/profile/model/payload/fallback configuration has multiple authorities and phantom profiles.
6. The eval harness is static-command oriented, while scorer certification, sealed goldens, replay,
   comparative statistics, promotion, and integrity remain fragmented plans.
7. Latest telemetry and QA projections can be overwritten or synthesize inconsistent truth.
8. Scheduler/backpressure and local model stacking are not a single measured resource authority.
9. Capability admission and lifecycle are documented more strongly than they are enforced at load/use.
10. Governance instrumentation still relies on manual PENDING/PULSE/RESUME/HANDOFF compliance.
11. Agent role/config documentation is stale: it hardcodes model/vendor abilities that conflict with
    current operator policy and measured capability.
12. The knowledge graph is useful but stale relative to current high-churn architecture work.

## 14. Migration roadmap

### Cycle 0 — Decision integrity evidence integrated; adjudication pending

C0.3 is integrated at `c9fe3974` and preserves the truthful authority inventory. Exit requires an
owner-adjudicated target, transition owner, deadline, and rollback for every split-brain/unowned row;
physical writer convergence is Cycle 1. Do not add another lifecycle/eval service.

### Cycle 1A — Minimal contract kernel and parity vectors

- Ratify only the first required schemas and canonical serialization/golden vectors.
- Add the pure local-inference resolver and batch/chat parity fixtures without moving live traffic.
- Expose contract version, schema health, parity result, freshness, and typed unavailable reasons in
  Phase 0 and an existing dashboard surface.

Exit: strict schemas and golden plans independently reviewed; no new lifecycle writer; no caller field
can self-grant clearance; exact implementation inventory and rollback policy frozen.

### Cycle 1B — One shadow state vertical (only after ADR decision)

- Select per-authority consolidation or supersede the ADR with shared-spine invariants.
- Add CAS plus outbox/replay for one workflow-run authority while legacy remains authoritative.
- Prove terminal uniqueness, deterministic reconstruction, crash/replay, disk/resource envelope,
  integrity, restore, projection lag/divergence, and rollback.

### Cycle 2 — Fail-closed identity, policy, leases, and execution cells

- Remove privileged/fail-open defaults.
- Add authenticated principal envelopes, policy decision/enforcement points, short-lived leases,
  revocation, side-effect receipts, isolated worktrees/cgroups/AppArmor/egress/secret handles.
- Put all local/remote/tool adapters behind the same boundary.

Exit: zero unauthorized effects in adversarial matrix; stripped authority cannot be reacquired;
revoke/cancel leaves no orphan or untracked mutation.

### Cycle 3 — Inference live convergence after early shadow parity

- Make switchboard the only model gateway and one canonical payload/stream/error path.
- Consolidate route/profile/model registries and explicitly retire or provision phantom profiles.
- Migrate `delegate-to-local` and `aq-chat` as coordinator clients; keep measured compatibility adapter.
- Activate global resource scheduler and reservation telemetry.

Exit: 100% route/authority/budget/fallback parity fixtures; stream/final equivalence; no silent
capability fallback; live batch/chat/cancel/recovery smokes.

### Cycle 4 — Evaluation factory baseline

- Add dataset, scorer, model-build, prompt, environment and tool registries.
- Implement EvalRunManifest, isolated executor, sealed answers, certified scorers, infra-invalid and
  abstention classes.
- Port `aq-eval`, inference bench, contract, routing, tool and security suites as plugins.

Exit: repeatability within declared tolerance; known-good/bad discrimination; no golden access;
uncertified evidence cannot influence learning or promotion.

### Cycle 5 — Replay, comparative routing, and promotion

- Counterfactual replay varies one immutable component at a time.
- Produce paired quality/safety/latency/cost/resource deltas and capability envelopes.
- Transactionally gate candidate/canary/promoted/default alias changes on certified eval, review,
  soak, and rollback.
- Admit small resident/specialist models only after hardware and capability evidence.

Exit: every alias transition has promotion-ledger evidence and atomic rollback; first-pass weakness is
never hidden by repair/fallback.

### Cycle 6 — Operator plane, recovery, and legacy retirement

- Move dashboard/CLI/report to event/eval/promotion projections and authenticated commands.
- Make PULSE/RESUME/HANDOFF, file registries and mutable latest artifacts projector-only.
- Run backup/restore, corruption, dependency-loss, model-swap and clean-install drills.
- Retire bypasses after two clean cycles or a ratified time/usage threshold.

Exit: one-trace diagnosis, no direct projection writers, no blank required metrics, tested restore and
rollback, and no compatibility path without owner/telemetry/expiry.

## 15. Delivery gates for every slice

- One named authority and recovery owner per object.
- Versioned schema, stable errors, compatibility/retirement contract, and generated clients.
- Threat analysis and fail-closed behavior at every effect boundary.
- Unit, property, adversarial, crash/replay, live integration, and resource tests proportional to risk.
- Immutable evidence with run/environment provenance; independent review bound to final subject hash.
- aq-qa integration path and dashboard/operator projection committed with the feature.
- Nix declaration, env/port contract, service hardening, backup/rollback, and restore implications.
- No new high/critical security finding, unauthorized write, stale green status, or unmeasured fallback.

## 16. Success measures

- 100% accepted runs have principal, intent, plan, lease, trace, terminal result, and evidence lineage.
- 100% side effects have a valid lease and idempotent receipt; zero unauthorized effects.
- 100% promoted aliases bind certified eval, independent review, soak and rollback evidence.
- ≥99.9% contract-valid events; exactly one terminal per accepted run.
- 100% equivalent chat/delegation fixtures match route, authority, tools, budgets and fallback.
- 0 direct writes to lifecycle projections after retirement.
- 0 missing required dashboard fields; projection lag and evidence freshness are visible.
- Recovery point and time objectives are measured in repeated restore drills.
- Local model utilization increases without starving interactive/validation work or hiding weaker
  first-pass quality.
- Operator interventions, blocked actions, false approvals, repair rate, queue time, resource pressure,
  eval variance, and promotion rollback rate trend visibly over time.

## 17. Research alignment

- NIST's 2026 agent identity concept emphasizes identification, authentication, dynamic least
  privilege, delegated authority, intent, tamper-evident audit, provenance, and prompt-injection
  containment.
- MCP requires explicit consent/tool safety and current authorization guidance adds OAuth 2.1,
  audience binding, PKCE, short-lived tokens, and no token passthrough.
- A2A separates discovery, messages, long-running tasks, streaming and artifacts; AQ should extend,
  not replace, those exchange concepts.
- OpenTelemetry GenAI conventions support agent/model/tool span trees and standardized model, token,
  finish-reason, latency and content attributes; content capture must remain privacy-gated.
- Modern agent eval guidance favors tasks, repeated trials, full trajectories, multiple grader types,
  adversarial/security scenarios, transcript review, and explicit protection against grader gaming.
- SLSA provenance reinforces server-verified configuration origins, resolved dependency digests,
  distinct builder identities for different security modes, and monotonic deny-safe extensions.

Primary references:

- https://www.nccoe.nist.gov/sites/default/files/2026-02/accelerating-the-adoption-of-software-and-ai-agent-identity-and-authorization-concept-paper.pdf
- https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations
- https://www.nist.gov/caisi/cheating-ai-agent-evaluations
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- https://a2a-protocol.org/latest/topics/key-concepts/
- https://opentelemetry.io/blog/2026/genai-observability/
- https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- https://www.anthropic.com/research/trustworthy-agents
- https://slsa.dev/spec/v1.1/provenance
- https://spiffe.io/docs/latest/spire-about/spire-concepts/
- https://www.openpolicyagent.org/docs

## 18. Ratification decisions required before Cycle 1

1. Confirm hybrid coordinator/control plane as sole lifecycle authority and switchboard as execution-only.
2. Confirm Postgres + transactional outbox + local CAS as the Cycle 1 measured hypothesis.
3. Confirm cryptographic principal/review/artifact attestations and short-lived CapabilityLease as the
   security model, with no fail-open privileged modes.
4. Confirm the evaluation factory as the universal promotion gate for models, prompts, profiles,
   policies, tools, scorers and datasets.
5. Confirm strangler migration and projector-only retirement path—no big-bang rewrite.
6. Freeze Cycle 1 exact objects, schemas, owners, files, baselines, resource budgets and rollback before
   issuing implementation authorization.

VERDICT: BUILD THE FACTORY AROUND ONE CONTROL PLANE, ONE EVENT/EVIDENCE SPINE, LEASED EFFECTS, AND
EVAL-GATED PROMOTION; MIGRATE THE EXISTING ASSETS THROUGH MEASURED SHADOW PROJECTIONS RATHER THAN
ADDING ANOTHER PARALLEL HARNESS.
