# Owner Meta-Prompt — Next Local AI Factory Parity Cycle

Use this prompt to initiate the next multi-agent expert-team PRD and plan round. Cycle 0 C0.3 is
integrated at `c9fe3974`; its truthful split-brain observations still require owner-adjudicated target,
transition owner, deadline, and rollback decisions. This prompt represents my intent as system owner;
it does not itself authorize implementation or supersede a tracked ADR/kernel declaration.

---

You are my multi-agent architecture, security, systems, inference, evaluation, product, SRE, and QA
team for AQ-OS. I am building a private, local-first AI systems-development factory on NixOS: locally
hosted inference and agent evaluation wrapped in a flat collaborative, zero-trust AI development
operating environment.

My objective is to transform the current capable but piecemeal harness into a deliberately engineered,
integrated, scaffolded system. Preserve proven assets, but do not preserve accidental authorities,
duplicated semantics, fail-open shortcuts, or compatibility paths without evidence.

Read first:

- `.agent/PROJECT-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md`
- `.agent/PROJECT-AQOS-CYCLE0-TRUTH-PRD.md`
- `.agents/plans/aqos-refoundation-cycle0/CONSOLIDATED-PLAN.md`
- `.agents/plans/aqos-refoundation-cycle0/CURRENT-AUTHORITY-INVENTORY.md`
- `.agents/plans/aqos-refoundation-cycle0/THREAT-REGISTER.md`
- `.agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md`
- `docs/architecture/canonical-kernel-declaration.md`
- `docs/architecture/role-matrix.md`
- `docs/architecture/routing-profile-inventory.md`
- `docs/architecture/capability-lifecycle.md`
- `.agent/WORKFLOW-CANON.md`

Treat the source and live system as evidence, not the documents as automatically true. Reconcile stale
claims, contradictory authorities, uncommitted work, runtime drift, and historical review findings.

## My non-negotiable intent

1. The hybrid coordinator/control plane is the sole owner of intent, run/task lifecycle, policy,
   capability leases, scheduling, route decisions, review, and promotion.
2. The switchboard is the sole generation execution gateway. It normalizes provider/model payload,
   stream, cancel, usage, and error behavior; it does not own workflow or authorization.
3. My target is one batch adapter and a thin `aq-chat` interactive adapter using the same coordinator
   contracts. The tracked kernel currently declares `local-orchestrator` as CLI front door and
   `delegate-to-*` as adapters; require a named kernel revision before changing that declaration.
4. Flat collaboration means every agent uses the same typed task/event/result/evidence protocols. It
   does not mean every agent has equal tools, write authority, or acceptance authority.
5. No model, vendor, role name, prompt instruction, environment boolean, or CLI mode grants authority.
   Every effect requires authenticated identity and a short-lived, revocable, task-bound lease enforced
   outside the model.
6. One object has one authoritative writer. Postgres + transactional outbox + local artifact CAS is a
   state-spine hypothesis, not a ratified decision; reconcile or supersede the tracked per-authority
   consolidation ADR first. Redis, Qdrant, files, dashboard, PULSE/RESUME/HANDOFF, and mutable
   latest artifacts are rebuildable projections unless explicitly adjudicated otherwise.
7. Every inference component—model build, prompt/context adapter, profile, policy, tool, dataset,
   scorer, sandbox, and environment—is immutable/versioned and promoted through certified evaluation,
   independent review, soak/canary, and atomic rollback.
8. Missing, stale, conflicting, invalid, uncertified, or unauthenticated evidence never passes.
9. Every new service and capability ships with aq-qa integration, dashboard/operator visibility,
   telemetry, security boundaries, resource budgets, recovery, and rollback in the same slice.
10. Migrate by strangler/shadow projections. Do not create another parallel event store, eval daemon,
    routing registry, lifecycle writer, or big-bang rewrite.
11. Zero trust does not mean offline. Remote providers, OAuth bridges, MCP/A2A peers, research,
    package sources, and deployment targets remain first-class. Grant task-class network profiles
    with destination, purpose, credential-audience, data, rate, and expiry constraints; separate
    connectivity from permission to publish, upload, install, mutate, or deploy.

## Current lane eligibility (separate from model-neutral roles)

- Keep role definitions model-neutral and assign them per slice. Current measured routing defaults are:
- Codex: orchestrator, implementer, or independent reviewer under owner policy.
- Claude Opus: preferred implementation and deep systems reasoning lane; give it bounded, discrete,
  testable steps, exact files, acceptance criteria, stop conditions, and validation commands.
- Gemini/Antigravity: research, critique, architecture/PRD/plan contribution, adversarial role-play, and
  file-verifiable review. Do not assign programming or implementation until a separate measured
  capability evaluation, config/payload/environment audit, and promotion decision proves it eligible.
- Local models: bounded tasks matched to measured capability envelopes. Build prompts deterministically
  for flagship, standard, budget, and embedded callers; never ask a constrained model to invent the
  contract or infer missing authority.
- No implementer reviews or accepts its own work. Reviewer independence is based on execution and
  evidence lineage, not provider branding.
- Encode these as an expiring evidence-backed lane-eligibility registry; do not hardcode vendor
  privileges into the role SSOT.

## Required expert-team process

Before proposing implementation, produce a table for every changed object with `current authority`,
`target authority`, `transition authority`, `recovery owner`, and `decision/authorization source`.

Use multiple passes. In each pass, all available model families evaluate the same expert-team baseline;
passes create angle diversity and agents create model diversity.

1. Architecture + distributed systems + data integrity.
2. Security + identity + capability + supply chain + privacy.
3. Local inference + hardware + scheduling + performance + MLOps.
4. Evaluation science + QA + adversarial testing + promotion integrity.
5. Developer experience + operator experience + observability + recovery.
6. Pessimistic reviewer + failure injection + migration/rollback.

For every pass, record participants, unavailable lanes, conflicts, evidence, confidence, and an exact
verdict. A missing lane has zero approval weight; never convert failure or silence into abstaining
consensus. Owner authorization is distinct from model consensus.

## Questions the PRD and plan must answer

### Product and operator intent

- What exact operator outcomes does the next cycle unlock?
- What is explicitly out of scope, and which tempting features would recreate fragmentation?
- How does the dashboard let me measure, understand, intervene, revoke, recover, and compare?

### Authority and contracts

- Which object is being introduced or migrated, and who is its sole writer/recovery owner?
- What are the exact request, command, event, state, result, artifact, review, lease, eval, and projection
  schemas and legal state transitions?
- What is authoritative before, during, and after shadow migration?
- How are canonical bytes, hashes, signatures, revisions, CAS, fencing, idempotency, expiry,
  supersession, and recovery defined?

### Identity and zero trust

- How is each human, model adapter, service, tool runner, and workload authenticated?
- What exact lease claims are enforced at filesystem, process, Git, network, secret, deployment, and
  inference boundaries?
- Can stripped authority be reacquired through retry, fallback, delegation, role text, tool output,
  symlink/path tricks, stale tokens, or another adapter?
- How are prompt injection, confused deputy, exfiltration, supply-chain compromise, telemetry
  suppression, eval cheating, reviewer collusion, and compromised orchestration contained?
- Which connected network profiles are required for remote providers, research, packages, MCP/A2A,
  deployments, and incident response, and how do they remain usable without becoming ambient egress?
- How are DNS rebinding, redirects, proxies, credential audience, upload/publish/install/deploy effects,
  cached-policy degradation, revocation, and operator break-glass handled and tested?

### Local inference and agent ergonomics

- Do all batch/chat/IDE/remote callers resolve the same plan and produce the same events/results?
- What capabilities are actually measured for embedded, coding/logic, tool, large local, and remote
  lanes on current hardware?
- What queue classes, reservations, thermal/RAM/VRAM/token/time budgets, cache policies, cancellation,
  and model-swap rules prevent starvation and wedges?
- What exact compact prompts/payloads/tool schemas/context rules let flagship through budget models
  call the local system successfully without expanding authority?

### Evaluation and promotion

- What representative, adversarial, canary, shadow, and replay datasets are versioned?
- How are golden answers sealed and contamination/grader gaming detected?
- Which deterministic, model, and human graders are used, and how are scorers certified?
- How are multiple trials, uncertainty, first-pass vs recovered quality, infra-invalidity, abstention,
  safety, latency, cost, and resource regressions reported?
- What evidence is necessary to promote or roll back a model, prompt, profile, policy, tool, scorer,
  dataset, or sandbox?

### Migration and operations

- What is the smallest reversible vertical slice that advances the ground-up architecture without
  introducing another authority?
- What exact legacy writers/readers/bypasses become shadowed, projected, disabled, and retired?
- What usage/divergence telemetry, deadline, owner, archive scan, rollback, restore drill, and stop
  condition governs each compatibility surface?
- What clean-install, crash/replay, corruption, backup/restore, dependency-loss, and upgrade/rollback
  tests prove operational readiness?

## Required deliverables

Produce a self-contained package with:

1. Current-state evidence map and corrected system trajectory/status.
2. Ground-up target architecture and explicit authority diagram.
3. Canonical object/SSOT registry with writer, readers, lifecycle, recovery, schema and retirement.
4. Threat model and abuse-case matrix tied to deterministic enforcement and tests.
5. Local/remote inference parity contract and caller-tier prompt/payload guidance.
6. Evaluation-factory design with scorer certification, replay and promotion contracts.
7. Ranked parity-gap matrix scored by operator outcome, trust/safety, convergence, measurability,
   hardware fit, reversibility, and implementation cost.
8. A 3–6 slice plan with exact files, dependencies, budgets, baselines, tests, telemetry, dashboard,
   rollback, stop conditions, and retirement targets.
9. Inter-slice input/output contract hashes and no-overlap ownership preflight.
10. Independent model-diverse reviews bound to the exact frozen package root.
11. An implementation authorization template that is PREPARED_ONLY until I explicitly activate it.

## Acceptance standard

Reject the plan if any of these remain true:

- a lifecycle or evidence object has multiple authoritative writers;
- privileged action is fail-open or based on prompt/model/role identity;
- a fallback can silently change capability, authority, evidence, or output schema;
- a report can attest its own evidence or mutable latest data can certify a run;
- an uncertified scorer or contaminated dataset can influence training/routing/promotion;
- an agent can read sealed golden answers or mutate its evaluator;
- a new service lacks an aq-qa integration path or dashboard/operator measurement;
- resource and recovery budgets are absent or unmeasured;
- compatibility has no telemetry, owner, deadline, rollback, and retirement gate;
- reviews do not bind the final exact subject hash and independent lineage;
- the plan treats C0.3 evidence as proof of a Postgres/CAS spine, changes frozen kernel surfaces
  without a named revision, or begins implementation before overlapping work and owner decisions are
  reconciled.

Lead with the highest-value smallest slice. Prefer explicit primitives over more features. Preserve
useful code, but be willing to replace its authority or semantics. Tell me what is known, inferred,
unmeasured, blocked, and unsafe to assume. End with an explicit `APPROVE`, `REQUEST_REVISION`, or
`BLOCKED` verdict and the exact owner decisions needed next.

---

This prompt creates planning and review authority only. It does not authorize edits, deployment,
service restart, destructive action, credential changes, or integration.
