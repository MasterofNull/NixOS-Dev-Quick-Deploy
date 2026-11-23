# PRD: Control-plane consolidation (bounded contexts, contracts, single-owner registry, adopt-vs-build)

Status: DRAFT for multi-lane review (architect lane, 2026-11-22). Not frozen. No code in this slice.
Tracker: `tracker.json` in this directory.
Origin: owner-trusted external review of 2026-11-22 (`.agents/delegation/outputs/external-review-20261122/INPUT.md`) plus the owner ask "how do we best incorporate this feedback into our designs, implementation, past and future work". Inputs: `CENSUS-summary.md` (Sonnet, read-only), `adopt-vs-build-20261122-gemini.md` (web research, CVE/OAuth claims pending Codex verification), `COORDINATION.md` (two orchestrators; W7 is this PRD).
Umbrella over (no duplicate plans): single-owner-guards-20261119, aq-update-unified-20261119, experience-capture-20261119. They become slices under their contexts (section "Fold-ins"). Those PRDs live only in a worktree / an origin branch and are not on main; this PRD carries their scope forward by reference, and the first code slice lands them together with this plan (docs ship with code).

## Problem

The reviewer said the number of control planes is high and that overlapping responsibilities make it hard to say which component owns a decision. The census confirms it on our own code: about 30 components decide things, and nine decisions have more than one owner.

| # | Decision | Owners today (evidence) | Cost observed 2026-11-19..22 |
|---|---|---|---|
| 1 | Model routing | `config/model-coordinator.json` is read by the coordinator, `aq-role-route`, `delegate-to-claude`, `lib/model_tiering.py` (also referenced by `aq-model-eval`, `lib/gemini-model-guard.sh`, `lib/brief_caps.py`, `governance/sweep-lanes.py`); the switchboard keeps its own profile catalog (`switchboard.py:461`); route aliases are a third source | Four readers can disagree about one model; a config edit has no single consumer to test |
| 2 | Lane availability and eligibility | wrapper cooldown files, `lane-eligibility-registry.json`, `aq-role-route`, `aq-land` reviewer choice each decide separately | Backlog LANE-AVAILABILITY-NOT-PER-MODEL: a cooldown on one model marked the whole lane down, so a healthy model was skipped |
| 3 | PR branch mutation | `aq-land`, two ad-hoc land runners, Dependabot, Gemini all write PR branches | Five mutators. LAND-RUNNER-NOT-DURABLE (an ad-hoc runner died with its session); DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH (Dependabot refuses a rebase once anyone else pushed, so the PR silently stalls) |
| 4 | Review independence | `scripts/ai/aq-land:396` compares the declared `Author-lane` string, not the commit authors | Backlog AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR: the tag can say "gemini" while Claude wrote the latest commits, so independence is a claim, not derived. Related to the fabricated-review-claims audit (about 85 PRs, 48 self-acceptances) |
| 5 | Health, QA and remediation | health-spider, health-monitor, `aq-qa`, coordinator `qa_check`, oncalld, `aq-alerts`, dashboard; four of them also remediate: auto-remediate, gap-auto-remediate, the health-spider fix pipeline, oncalld | Backlog EMBEDDER-STICKY-DEVICE-LOST: two remediators can act on one failure and neither owns the verdict |
| 6 | Loops | `aq-loop`, ralph-wiggum, `aq-agent-loop`, autonomous-improvement, PRSI, `aq-collab-round`: each has its own queue and retry policy | Rule 6 retry budget is enforced six different ways |
| 7 | Deploy | `aq-update`, `aq-deploy-current`, `nrs`/`nrb`/`nrd` aliases (no guards), `system-update-full.sh`, `aq-update-tiers` | Nine entry points; a rebuild nearly ran on a 6-day-stale lock (aq-update-unified PRD) |
| 8 | Memory | coordinator store/recall, `aq-memory`, AIDB, Qdrant, agent memory files | Writers without one API; `agent-memory-surface-registry.json` exists but is descriptive |
| 9 | Learning | `continuous_learning_daemon`, meta-optimization, `aq-local-training-loop`, federated learning, lesson tools | No single lesson/proposal schema; experience-capture found nine join gaps |

Root cause (Rule 19): ownership is documented in prose and in per-PRD "Existing owners" lists, but nothing machine-readable says "decision D belongs to component C", and no gate fails when another component mutates D. Duplicates therefore appear faster than reviews catch them. The reviewer's remedy (bounded contexts plus contracts) is right; the enforcement half (a registry plus tier0) is what we add.

Verified on origin/main at drafting time: `scripts/ai/aq-land:396` uses `author_lane`; the model-coordinator readers above exist; `config/schemas/agent-dispatch-envelope.schema.json`, `config/qa-provider-probe-contract.schema.json`, `config/agent-memory-surface-registry.json`, `config/system-state-authorities.yaml` and `scripts/governance/check-state-authorities.py` exist. NOT found on main: a `model-coordinator` schema (the contract for A1 must be written, see S3), and the four backlog ids (they live in the owner checkout's memory, not in the tree; S1 verifies them against the live backlog per the finding-freshness skill).

## Goals

1. Five bounded contexts (K1-K5) over eight aggregates (A1-A8), each aggregate with one owner component, owned decisions, a published contract, named consumers and an enforcement check.
2. A machine-readable registry `config/decision-ownership.json` plus a tier0 check that fails when code outside the owner mutates an owned decision. Highest-value checks first.
3. An adopt-vs-build decision per context with explicit criteria and the rule "replace, never run both".
4. Existing and in-flight plans fold in as slices; no second plan for the same concern.
5. Future work cannot skip this: the PRD template requires Bounded context / Contract / Owner / Adopt-vs-build justification.

## Non-goals

- A big-bang re-architecture or rewrite of working components. Each context converges by slices behind its contract; today's tree must pass every new check on day one (regression-only enforcement, exact-identity bypass lists with deadlines).
- Adopting any external framework now. Research leans are recorded as pending verification.
- New instruction lines in canon beyond what single-owner-guards R4 already budgets (zero net lines).
- UI/UX styling (Rule 23 exemption).

## Design

### Principle
Domain-Driven Design as used here: a context is a boundary of decision ownership, not a service. It may be one script and one JSON file. Contract-based design: every cross-context interaction goes through a published schema, existing ones first; a consumer never reads another context's private state (files, cooldown dirs, queues). Complexity lives in the aggregate; each context stays as simple as it can be (KISS, Rule 20b).

### The one map: five bounded contexts (K1-K5), eight aggregates (A1-A8) inside them

Reconciliation of the census (8-9 contexts) with the Codex/Gemini proposal (5 contexts). Decision: the target map is the FIVE contexts. Why: (1) the census mirrored today's tool boundaries (a context per toolchain); Codex's critique, which Gemini's synthesis converged on, derives the map from the kernel declaration (`docs/architecture/canonical-kernel-declaration.md`) and the ten `SPLIT_BRAIN` rows of `config/system-state-authorities.yaml`, so every context has ledger-row evidence and every disputed row has a destination; (2) fewer contexts means fewer cross-context contracts to publish and test (KISS, Rule 20b); (3) the census's eight are kept as AGGREGATES (A1-A8, the finer ownership units used in the tables and slices below), each nested in exactly one context, so no census finding is lost. A context owns decisions and contracts; an aggregate is where one owner and one enforcement check live.

| Context (target) | Census contexts folded in (aggregates) | Ledger rows (system-state-authorities.yaml) | Owner |
|---|---|---|---|
| K1 Work orchestration | A2 Work Dispatch & Delegation; the loops as callers | `planning-round`, `delegation-lifecycle`, `intent-resume`, `workflow-run-task` | coordinator (round store, task registry, intent interface, run store); `aq-event` is the append path, `RESUME.json`/`PULSE.log` become projections |
| K2 Model execution | A1 Model Access & Routing | `routing-model-execution` | coordinator owns the routing decision and the resolved run plan; switchboard owns generation against the accepted plan |
| K3 Trust & integration | A3 Review & Trust; A4 Integration/Landing; A9 Approval & Authority (optional aggregate) | `dashboard-operator` | operator grants (coordinator approval store is the sole writer); independent reviewers issue receipts; `aq-land` is the sole protected-branch admission path |
| K4 Host configuration & activation | A5 Deploy & Activation | `configuration` | evaluated Nix options own configuration; `aq-update` owns the activation decision and ledger |
| K5 Evidence, memory & learning | A6 Knowledge & Memory; A7 Observability & QA; A8 Learning/Experience (three separate aggregates, one owner each) | `qa-effectiveness`, `learning-eval`, `memory-rag` | evidence reducer; coordinator evaluation ledger; MemoryBroker (Qdrant is a derived index) |

Cross-context contracts (versioned, existing schemas first; these supersede the per-aggregate "published contract" column where they differ):
- K1: dispatch envelope and transition commands carrying `run_id`, `dispatch_id`, expected revision and an idempotency key (`agent-dispatch-envelope.schema.json` exists; extend additively). Wrappers submit commands and evidence through adapters.
- K2: versioned `ResolvedRunPlan` (execution profile, authentication class, fallback policy) in, versioned execution receipt out. Credentials never leave the execution lane. No `ResolvedRunPlan` schema exists yet; S3 writes it.
- K3: review receipt bound to the exact commit and reviewer lane; expiring, scoped operator grant consumed with replay protection; admission fails closed when either is missing or stale.
- K4: activation request/result binding revision, evaluated target, scope, grant and outcome (aq-update-unified ledger).
- K5: versioned evidence event (`maeah.agent-run-event.v1`) with provenance, run/dispatch id, idempotency key, redacted references and the `learning_eligible` gate; learning emits PROPOSALS to the context that owns the decision, never mutates owners directly; remediation runs through the owning context's command interface.

Disagreement recorded (honest push-back, to settle in S0): Codex says "commit authorship alone cannot establish independence" (it also needs the bound receipt and grant); Gemini's table says "verify independence via commit authors, not just `--author-lane`". Position taken here: derived commit authorship is a NECESSARY condition (S2), the exact-commit-bound receipt is the SUFFICIENT evidence (K3 contract); the declared tag is advisory.

The census's per-aggregate detail follows; read "A-n" rows as the aggregate view inside the K-contexts above.

### Aggregates (census contexts, finer ownership units)

| # | Aggregate | Single owner | Owned decisions | Published contract (existing first) | Consumers | Enforcement |
|---|---|---|---|---|---|---|
| A1 | Model Access & Routing | switchboard + `config/model-coordinator.json`; one read module (`lib/model_tiering.py` grows into it) is the only reader | which model serves a request; tier map; route aliases; fallback order | `config/model-coordinator.json` + NEW `config/schemas/model-coordinator.schema.json` + route-decision event in the agent-run-events envelope | coordinator, `aq-role-route`, `delegate-to-*`, `aq-model-eval` call the module/HTTP route and never open the JSON | tier0 DO-1: only the owner module opens `model-coordinator.json` (current readers as bypasses with deadlines); contract test: schema validates the file; switchboard catalog checked against it |
| A2 | Work Dispatch & Delegation (includes lane availability/eligibility) | delegation registry + `lane-eligibility-registry.json`; `delegate-to-*` are thin executors | task assignment; lane up/down per MODEL, not per lane; eligibility; the Rule 6 retry budget | `agent-dispatch-envelope.schema.json` (exists) + `delegation-task-record.schema.json` (exists) + availability event keyed `(lane, model)` | `aq-role-route`, `aq-land`, loops, orchestrators | tier0 DO-4: availability is read through the availability API, not wrapper cooldown files; contract test: one model down leaves its siblings up |
| A3 | Review & Trust | `aq-review-receipt` | review disposition; reviewer independence; receipt minting | review record / receipt schema (`Review-Disposition`, `Reviewed-subject-sha256`, `Reviewed-by`, `Review-Receipt`) + NEW derived `authors[]` | `aq-land`, trunk protection, dashboard | contract test: reviewer lane not in the lanes of commit authors and `Co-Authored-By` trailers since the merge base; declared `Author-lane` advisory only; tier0 DO-5 |
| A4 | Integration / Landing | `aq-land` | every write to a PR branch; merge; the branch-mutation lock; landing record; "recreate" requests for Dependabot | landing record (`outcome_receipt.record_landing`) + branch-mutation lock record | orchestrators, Dependabot flow, lanes (they hand off, never push PR branches) | tier0 DO-2 (first check built): branch pushes, `gh pr merge`, `gh pr update-branch` only in `aq-land`, via the existing authority checker's writer signatures; one durable runner |
| A5 | Deploy & Activation | `aq-update` (`aq-deploy-current` becomes its stage) | when and how the system generation changes; lock refresh; pending-reboot; activation attestation | aq-update ledger schema (aq-update-unified U-slices) + Rule 15 activation record | owner, `aq-resume`, QA | tier0 DO-3 via `check-state-authorities.py --staged-regressions` (single-owner-guards R1): raw `nixos-rebuild`, `home-manager switch`, `nix flake update` outside the owner fail; `nrs/nrb/nrd/nrs-force` listed as bypasses with deadlines |
| A6 | Knowledge & Memory | AIDB + Qdrant behind ONE memory API (the coordinator `/api/memory/*` is the facade) | where a fact/lesson/embedding lives and how it is recalled; eviction | `config/agent-memory-surface-registry.json` (exists; made normative) | all agents, `aq-memory`, hints | contract test: every memory writer appears in the surface registry; tier0 DO-7: no direct Qdrant/AIDB client outside the facade (ratchet, shrink-only) |
| A7 | Observability & QA | ONE health pipeline (health-spider sample -> verdict) with ONE remediator | health verdict; what is remediated and by whom; alert routing | `qa-provider-probe-contract.schema.json` (exists) + NEW health sample/verdict schema | dashboard, `aq-alerts`, oncalld (consumer), `aq-qa`, `qa_check` | tier0 DO-6: one component executes remediation, the rest emit a remediation REQUEST event; contract test: one failure gives one attempt |
| A8 | Learning / Experience | continuous-learning + PRSI, with the experience-capture design as its data backbone | which outcomes become lessons, priors or proposals; weights; experiments | `learning-candidate.schema.json` (exists) + lesson/proposal schema extending `check-prsi-cycle-contract.sh` + experience events (`dispatch_id == run_id`) | routing hints (advisory), reports, dashboard | contract test: only `learning_eligible == true` feeds scoring (learning-attribution gate); other loops may not write lessons |
| A9 (optional) | Approval & Authority | identity-kernel, leases, epochs, attention queue | who may perform a reserved act; lease/epoch validity | `capability-lease.schema.json` (exists) + approval envelope | all privileged actors | already enforced piecemeal; recorded as `approval.*` registry rows, no new code in MVP |

Loops (ralph-wiggum, `aq-loop`, `aq-agent-loop`, autonomous-improvement, `aq-collab-round`) are NOT a context: they are consumers of A2 (dispatch), A3 (review) and A4 (landing). Their six retry/queue policies converge on A2's one retry budget (S8), not on an adopted framework.

### Single-owner registry: `config/decision-ownership.json`
Rows: `{id, decision, context, owner_component, owner_paths[], contract, mutation_signatures[], approved_bypasses[{identity, deadline, reason}], enforcement_check}`. Example ids: `routing.model-coordinator-read`, `landing.pr-branch-write`, `deploy.system-generation`, `review.independence`, `health.remediation`, `memory.store`.
- Schema `config/schemas/decision-ownership.schema.json`, `additionalProperties: false`. One owner row per decision.
- No duplicate registry: `config/system-state-authorities.yaml` stays the SSOT for privileged state writers (system generation, flake lock, main, receipts); `decision-ownership.json` references its rows by id and adds the decisions that are not state writes (routing reads, availability, independence, remediation). The capability catalog's `concern/role/shim_of` fields (single-owner-guards O1/R2) stay the entry-point registry. One generator cross-checks the three so an owner named in one cannot differ in another.
- tier0 check `check-decision-ownership.py` (tier0.d, staged blobs, regression-only like R1: an existing violation passes only if listed by exact identity with a deadline; a new mutation outside the owner fails with a message naming the owner and how to extend it). First three rules:
  1. DO-2: only `aq-land` writes PR branches (extends R1 writer signatures to non-main branch pushes and PR-branch `gh` calls; Dependabot "recreate" becomes an `aq-land` request).
  2. DO-1: only the routing owner module reads `model-coordinator.json` (current readers listed as bypasses; deadline = S3).
  3. DO-6: one remediator (current four listed as bypasses; deadline = S6).
- Rollback is a PR revert (tier0 has no kill switch and adding one would allow skipping gates). Checks fail only on new regressions, so today's tree passes.

### Adopt-vs-build (PENDING VERIFICATION)

Reviewer claim: "Anthropic's recent guidance on factories is to prefer maintained projects over bespoke ones."
Finding (Gemini web research, not yet independently verified by Codex): no such guidance was found. The Anthropic posts located point the other way or elsewhere: "Building effective agents" (2024-12-19) cautions against heavy frameworks in production; the harness-design posts (2025-11, 2026-03) describe bespoke lightweight harnesses; "Scaling Managed Agents" (2026-04-08) recommends Anthropic's own hosted service, which conflicts with our OAuth-only/local-first/Nix constraints; one 2026-10 post describes Anthropic building bespoke internal source-control and review systems. The likely source is conflation with third-party "buy a control plane" commentary. Honest stance: the reviewer's underlying point (prefer maintained projects when they fit) is sound regardless of the citation, so we evaluate on our own criteria. The citation is recorded as "not found", not "false", because the research could not fetch every page (unverified slugs and dates are labelled in the source file).

Criteria, applied to every candidate: (a) OAuth/session auth only, no API keys; (b) local-first llama.cpp on the 4 GB shared-memory iGPU (GPU layers <= 12); (c) Nix-declarative, no mutable runtime config; (d) headless CLI; (e) maintenance (releases, bus factor, nixpkgs packaging, license); (f) security posture (CVEs, supply chain, sandbox); (g) migration cost against the component it replaces.
Rule: REPLACE, NEVER RUN BOTH. An adoption slice names the retired component, a parity test and a removal date; two live implementations of one decision is the failure this PRD exists to prevent. Adoption stays behind the context contract, so consumers do not change.

| Context | Candidate(s) | Research lean (pending verification) | Why / what would change it |
|---|---|---|---|
| A5 Deploy | nh (EUPL-1.2, v4.5.0 2026-11-12, in nixpkgs with `programs.nh`, no CVEs found); deploy-rs v1.0.0, colmena v0.5.0, devenv | nh: ADAPT/SPIKE (Codex and Gemini converge; first-pass said adopt-partially), as the build/diff/dry-activate/GC engine UNDER `aq-update` (our guards, ledger and pinned rev stay). deploy-rs, colmena, devenv: keep ours | deploy-rs and colmena pay off only with remote SSH nodes; revisit if a second host appears. nh must first verify: privilege elevation vs our sudo-is-an-owner-act rule, dry-activate with our pre/post checks, EUPL-1.2 vs the public repo's licence posture (owner decision) |
| A1 Routing | LiteLLM (MIT core; compromised v1.107.0 release 2026-10-21; JWT/auth CVEs) | keep ours (Codex: KEEP-CUSTOM/PUSHBACK) | Cannot drive headless Codex/Gemini/Claude CLI OAuth lanes without API keys; adds a master key and a DB. Changes if it gains first-class CLI-OAuth lanes and a signed-release record of 6+ months |
| A2 + loops | LangGraph (core MIT; `langgraph-api` Elastic-2.0, 2026 CVEs) | ADAPT/SPIKE, conditional on a demonstrated replay or interrupt gap (Codex and Gemini converge; first-pass research said keep ours) | Assumes API-key SDK clients; its value (durable graphs, interrupts) we partly have. Changes if a loop family needs checkpointed cyclic graphs we cannot express in the A2 retry budget; then adopt core only, behind the contract, retiring that loop |
| Agent runtime (overlaps A2/A6/A8) | OpenClaw (MIT, foundation-backed, very active; marked Insecure in nixpkgs; CVE-2026-25253, CVE-2026-62201; ClawHub "ToxicSkills" supply-chain incidents) | keep ours | Fails (a): reported Anthropic block on consumer OAuth reuse in third-party harnesses, Gemini PKCE risk; its monolithic overlap would force "run both". Changes if OAuth lanes are officially supported, the nixpkgs insecure flag clears and skills are sandboxed. Reuse ideas only (durable scheduling) |
| A3, A4, A6, A7, A8 | none evaluated | keep ours | Harness-specific trust semantics; evaluate when a concrete candidate is proposed via the `capability-intake` skill |

#### Claim-verification status (labels: VERIFIED = checked against a primary source by a lane that was not the claimant; UNVERIFIED = reported by one lane or secondary source; REFUTED = contradicted by a source). Nothing below is VERIFIED for the CVE and OAuth items yet, and no row may be upgraded without a recorded source.

| Claim | Status | Source / note |
|---|---|---|
| Anthropic "recent factory guidance prefers maintained projects over bespoke" | UNVERIFIED (no supporting publication found; Anthropic posts located say the opposite or recommend the hosted Managed Agents product) | Gemini web research (adopt-vs-build file section 1); Codex critique section 2 links the same posts; neither could fetch every raw page |
| OpenClaw MIT licence, nixpkgs-packaged but marked Insecure | UNVERIFIED | Gemini, via MyNixOS/search snippets (no direct nixpkgs fetch) |
| OpenClaw CVE-2026-25253 and CVE-2026-62201; ClawHub malicious-skill campaign | UNVERIFIED | Gemini, secondary sources; Codex has not checked the ids |
| Anthropic blocks consumer Claude OAuth reuse in third-party harnesses incl. OpenClaw | UNVERIFIED, and CONTESTED between lanes | Gemini says banned; Codex says OpenClaw OAuth and Codex-subscription support are real and documents its own credential profiles (it did not say Claude is allowed). Needs a direct check of Anthropic terms and the OpenClaw OAuth docs |
| LiteLLM 2026-10-21 compromised v1.107.0 | UNVERIFIED | Gemini, secondary sources |
| LiteLLM supports Claude Code subscription passthrough but adds virtual key + Postgres | VERIFIED by documentation read (Codex, LiteLLM tutorial link) for the passthrough and the virtual-key/DB requirement; incident claim above stays separate | Codex critique section 2 |
| LangGraph core MIT; `langgraph-api` Elastic-2.0; CVE-2026-55235/-55236/-71433 | UNVERIFIED (licence split is stated in Gemini's sheet; CVE ids not checked) | Gemini |
| nh v4.5.0 (2026-11-12), EUPL-1.2, `programs.nh`, no CVEs | UNVERIFIED (releases and licence from search snippets) | Gemini |
| deploy-rs v1.0.0 (2026-10-19), colmena v0.5.0 (2026-09-22), devenv v2.4.0 | UNVERIFIED | Gemini |
| 90-day commit counts; exact nixos-unstable versions | UNVERIFIED (explicitly labelled in the source) | Gemini |
| Ten of ten ledger rows are `SPLIT_BRAIN` | UNVERIFIED by this PRD's author (claimed in the Gemini synthesis, read from the ledger by Codex) | `config/system-state-authorities.yaml`; S1 re-reads it |
| `aq-land:396` compares the declared `Author-lane` | VERIFIED (read on origin/main at drafting time) | `scripts/ai/aq-land` |
| Parity of any candidate with session-only CLIs, zero stored API keys, AppArmor+bubblewrap, independent reviewer lanes, declarative activation and local llama.cpp on 4 GB VRAM / 27 GB RAM | UNVERIFIED (nobody has tested it); this is why every adoption is a bounded spike, not a decision | Codex critique section 2 |
| REFUTED | none yet | a claim moves here only on a contradicting primary source |

Every adoption slice must first turn the relevant rows above into VERIFIED or REFUTED with a recorded source. The nh spike is only an owner decision (D2) after that.
What would change the overall verdict: a failed verification of the OAuth blocks; a candidate that passes (a)-(d) and replaces a whole context with a net deletion of code; a second deployment host; a shift in the CVE/maintenance picture (re-run the fact sheets at the MVP boundary).

### Fold-ins (no duplicate plans)

| Existing plan / item | Becomes | Context |
|---|---|---|
| single-owner-guards R1 (privileged primitives on `system-state-authorities.yaml`) | core of S1 | registry + A4/A5 |
| single-owner-guards R2 (shim map), R3 (duplicate ratchet), R4 (zero-net canon + PRD template) | S9 | cross-cutting; the template gains this PRD's four sections |
| aq-update-unified U-slices (one `aq-update` front door; U0 flake-owned naming; U3/U4 deploy logic into `aq-update`; U7 identity ratchet; U8 deferred) | S5 | A5; nh evaluated inside U3 as the engine choice |
| experience-capture S1-S7 (S6b priors, S6c experiments) | S10 | A8, consuming A2 availability events |
| LANE-AVAILABILITY-NOT-PER-MODEL | S4 | A2 |
| AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR | S2 | A3 |
| LAND-RUNNER-NOT-DURABLE, DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH | S1b, S7 | A4 |
| EMBEDDER-STICKY-DEVICE-LOST (health-remediator overlap) | S6 | A7 |
| learning-attribution PRD gate | binding constraint of A8 | A8 |

### Past-work mapping

| Existing component | Context | Disposition |
|---|---|---|
| switchboard, `config/model-coordinator.json` | A1 | keep (owner) |
| coordinator, `aq-role-route`, `delegate-to-claude`, `aq-model-eval`, `gemini-model-guard.sh`, `brief_caps.py`, `sweep-lanes.py` | A1 | consumer (go through the owner module) |
| `model_tiering.py` | A1 | merge into the owner read module |
| `lane-eligibility-registry.json`, delegation registry, `delegate-to-*` | A2 | keep (owner + thin executors) |
| wrapper cooldown files | A2 | merge into the availability API |
| `aq-review-receipt` | A3 | keep (owner), derive authors from commits |
| `aq-land` | A4 | keep (owner) |
| two ad-hoc land runners | A4 | retire (replaced by the durable runner) |
| Dependabot, Gemini PR-branch writes | A4 | consumer: request landing or recreate via `aq-land` |
| `aq-update` | A5 | keep (owner) |
| `aq-deploy-current` | A5 | merge into `aq-update` as a stage |
| `nrs`, `nrb`, `nrd`, `nrs-force`, `system-update-full.sh` | A5 | retire to declared shims, archive (compressed) after parity |
| `aq-update-tiers`, `update-llama-cpp.sh` | A5 | consumer (refresh scopes of `aq-update`) |
| AIDB, Qdrant, coordinator memory API | A6 | keep; coordinator facade is the one API |
| `aq-memory`, agent memory files | A6 | consumer of the facade |
| health-spider sampler + verdict | A7 | keep (owner) |
| auto-remediate, gap-auto-remediate, health-spider fix pipeline, oncalld remediation | A7 | merge into ONE remediator (choice in S6 by measured behaviour); others emit requests |
| health-monitor, `aq-qa`, `qa_check`, `aq-alerts`, dashboard | A7 | consumers of the verdict |
| continuous_learning_daemon, PRSI | A8 | keep (owner) |
| meta-optimization, `aq-local-training-loop`, federated learning, lesson tools | A8 | merge or consumer, decided in S10 against the lesson schema |
| `aq-loop`, ralph-wiggum, `aq-agent-loop`, autonomous-improvement, `aq-collab-round` | consumers of A2/A3/A4 | converge retry and queue policy on A2; retire a loop only behind a parity test |
| identity-kernel, leases, epochs, attention queue | A9 | keep |

### Future-work rule
`.agent/templates/PRD.md` (created by single-owner-guards R4) gains four required sections: **Bounded context**, **Contract** (the schema or event touched or added, existing first), **Owner** (one component; a new owner only for a new decision, with its registry row), **Adopt-vs-build justification** (criteria (a)-(g) filled in for any new component, plus the "replace, never run both" retirement plan). Rule 8 review prompts (`aq-collab-round`, `aq-land`) gain the standing question "does this create a second owner for a decision in `decision-ownership.json`?" as code, not instruction lines. The PRD/tracker gate fails a new PRD missing the sections once the template ships (new PRDs only).

### Reviewer independence (recurring, so explicit)
Independence is derived, never declared: the receipt computes `authors` from commit author and `Co-Authored-By` trailers since the merge base, and the reviewer lane must not intersect them. Two orchestrators routing the same PRs is the stress case: COORDINATION.md claim rules stay in force, and a conflicting claim is settled by appending a HANDOFF line, never by acting.

### Cultivating external feedback: no new service
Constraint adopted from Codex (and Gemini's synthesis): no new service, daemon, control plane or tool unless a gap forces one (Rule 20b, Rule 23). The whole mechanism is a Markdown record plus links:
- One disposition file per external review at `docs/architecture/external-reviews/YYYY-MM-DD-<slug>.md` (Gemini's path; Codex said `docs/architecture/`, the subfolder keeps them findable), reached from the existing `aq-collab-round` round. Per claim: the reviewer's wording and provenance, the strongest version of the argument, evidence and what would change the conclusion, status from the verification table, the owner's ACCEPT / REJECT / DEFER decision with a falsifiable re-evaluation trigger, and a dated follow-through link. This review's record is created with S1 (the first code PR; no docs-only PRs).
- Past work: an accepted finding links to a `system-state-authorities.yaml` row and its observed writers; the cutover retires the writer, revokes its access and removes its dated allowance in the same change.
- In-flight PRDs: amended only where the critique changes an owner, contract or acceptance criterion; they gain the three-line header below.
- Future PRDs: required header, checked by the existing PRD/tracker gate for new PRDs: (1) Bounded context (K-n) and single decision owner; (2) Aggregate/store and versioned contract; (3) Build-vs-adopt check (why no maintained nixpkgs/OSS component fits, or the bounded spike condition). This is the "Bounded context / Contract / Owner / Adopt-vs-build justification" rule above in its minimal form.
- Gap check: nothing here needs a new component; if a later review finds the Markdown plus round link insufficient, that gap is logged and this clause is revisited, not pre-empted.

### Sequencing (adopted from Codex and Gemini)
Start after the PR queue clears (W2-W4) and the W9 rebuild completes; capture the post-rebuild boot id and live baseline first. Order: (1) land single-owner-guards with the occurrence ratchet (S1/S9 core); (2) finish aq-update-unified `U0 -> U1 -> U3 -> U2 -> U4 -> U5 -> U6`, early U7 gate, U8 deferred, removing the matching legacy allowances at U3/U4; (3) verify the merged agent-work-durability plan against that baseline (restart/reboot recovery, one protected landing per reviewed revision), which overlaps S1b/S7 here, so S1b/S7 reuse that plan's work instead of re-implementing a runner; (4) amend and finish experience-capture (the Gemini synthesis lists the REVISE findings to fold in first: outcome scoring, attribution truth table, privacy sanitizer before disk write, idempotent revisions, storage cutover; S10). Slices S2-S4 and S6-S8 interleave after step 1 as capacity allows. The ratchet is extended one ledger row at a time: compare against a protected reviewed base keyed by `(row, path, normalized operation, occurrence count)`, fail on novel, moved or extra occurrences, unreviewed allowance changes and incomplete scans; date every legacy allowance; flip a row to `SINGLE` only after reconcile, fencing, allowance removal and direct-write-rejection, concurrency and restart/replay tests; keep the `UNKNOWN` checkpointer shadow-only; use writer permissions, grants or protected refs where static matching cannot see dynamic calls.

## Slices (bounded, ordered; lane = most cost-effective correct, Rule 17, explicit model override)

| Slice | Scope | Lane suggestion | Validation | Rule 15 activation row |
|---|---|---|---|---|
| S0 | Freeze this PRD: independent scrutiny (failure modes, security, ownership-message UX), Codex verification of the research claims, owner decisions D1-D10 | Codex + Gemini reviewers (non-author); Qwen scaffold check queued | PLAN_READY[_WITH_FOLLOWUPS] recorded; verification results appended | n/a (plan) |
| S1 | `decision-ownership.json` + schema + `check-decision-ownership.py` with DO-2 on R1's authority checker; verify the backlog ids; land the three source PRD docs with it | Codex implementer (tests-first); sonnet override; Claude non-author reviewer | positive/negative/adversarial fixtures (renamed alias, second occurrence, staged vs worktree); today's tree passes | in tier0.d and ON in pre-commit; a real offending staged commit fails naming the owner; revert-intervenable; tracker live |
| S1b | `aq-land` durable runner (unit-backed, resumable) retiring the two ad-hoc runners; "recreate" request path replacing rebase-after-foreign-push | Codex; sonnet reviewer | kill the runner mid-landing and resume; foreign push then recreate on a real Dependabot PR | runner unit enabled (owner rebuild act, exact commands given); landing record observable |
| S2 | A3: derive authors in `aq-review-receipt` / `aq-land:396`; declared `Author-lane` advisory; DO-5 | Codex implementer; sonnet for the rule tests | tag says gemini but Claude committed: Claude cannot review; replay over the audited PR sample | live on the next real landing |
| S3 | A1: write the model-coordinator schema; one read module (merge `model_tiering.py`); migrate the four readers; DO-1 with readers as time-boxed bypasses | Codex for module and migration; Qwen only for decomposed single-file call-site edits | schema validates the live file; each reader's tests pass via the module; DO-1 fails a new direct read | coordinator rebuild/restart is an owner act (exact commands given) |
| S4 | A2: availability keyed `(lane, model)`, availability API replacing cooldown-file reads; `aq-role-route` and `aq-land` use it; DO-4 | Codex; sonnet reviewer | one model down leaves a sibling up (replays the Gemini incident); probe-one-other-model rule enforced in code | live in `aq-role-route`; availability event observable |
| S5 | A5: aq-update-unified U-slices in their frozen order (shims for `nrs/nrb/nrd`, `aq-deploy-current` as a stage, nh evaluation per D2); DO-3 | Codex implementer; owner acts for sudo/rebuild | that PRD's journeys; nh dry-run behind a flag first | rebuild is an owner act; ledger rows observable |
| S6 | A7: one remediator (chosen on EMBEDDER-STICKY-DEVICE-LOST behaviour), others emit requests; health sample/verdict schema; DO-6 | Codex; Qwen for the probe-contract test scaffold | one injected failure gives one remediation attempt and one verdict | service restart is an owner act |
| S7 | A4 completion: branch-mutation lock record; Gemini and Dependabot paths routed through `aq-land` | Codex | concurrent-mutation test: second writer blocked | live with S1b |
| S8 | Loop convergence: one retry budget (A2) consumed by the six loop families, one family per slice | sonnet per family (haiku only for mechanical single-file edits) | per-loop parity test before retiring any loop | per family |
| S9 | single-owner-guards R2/R3/R4 (shim map, duplicate ratchet, zero-net canon, PRD template with the four sections); canon parity across the 6 targets (Rule 16) | Codex + sonnet; `check-instruction-budget.sh` and the parity checker | zero-net-lines test; a PRD missing a section fails | template referenced from Rule 8's SSOT |
| S10 | A8: experience-capture S1-S6c, consuming A2 events; lesson/proposal schema; loops stop writing lessons directly | per that PRD (Codex implementers, sonnet for the weighting) | that PRD's journeys, real data | per that PRD |
| S11 | A6: memory facade as the only writer path, registry made normative, DO-7 ratchet | Codex | every writer in the registry; direct client use only shrinks | live on the write path |
| S12 | MVP-boundary audit: independent code and runtime review, adversarial pass, re-run of the adopt-vs-build fact sheets | independent lanes (Rule 18) | the frozen journeys with real dependencies | release acceptance needs its own evidence and an owner grant |

## MVP freeze proposal
MVP = S0 + S1 + S1b + S2 + S3 + S4. These remove the incidents of 2026-11-19..22 (five branch mutators, declared-vs-actual author lane, lane-wide availability, non-durable runner) and put the registry and the first checks under tier0. S5 (deploy), S6 (health), S8 (loops), S10 (learning) and S11 (memory) follow in that value order as already-reviewed PRDs or bounded slices (S5 and S10 reuse frozen PRDs, so no fresh full expert round per slice). MVP is declared only when frozen journeys pass on real dependencies: J1 a staged non-owner PR-branch write fails naming `aq-land`; J2 a Claude-authored commit under a "gemini" tag cannot be reviewed by Claude; J3 a down model does not take down its siblings; J4 a real model-coordinator edit reaches all consumers through the one module; J5 a killed landing run resumes.

## Risks
- **Big-bang migration.** Regression-only checks, exact-identity bypass lists with deadlines, one context per slice, parity before retirement.
- **Contract churn.** Prefer existing schemas; version every new contract; additive-only changes in MVP; contract tests are the safety net.
- **Ownership disputes between orchestrators.** The registry settles ownership once; drafting disputes go through COORDINATION.md claims and a HANDOFF line; contested rows go to the owner (decisions below), not to a vote of the lanes.
- **Check false positives** (string matching on `git push`). Bounded documented syntax per primitive, fixtures for comments and echo text, dynamic forms documented as out of scope (as in R1).
- **Research claims wrong or stale.** Treated as pending; Codex verification gates any adoption.
- **Local lane unavailable (power gate).** Recorded honestly; Qwen review is a queued catch-up, never faked.
- **Feature freeze (system-integrity-recovery P0+P1).** S1-S4 are integrity work; the rest waits for the freeze exit unless the owner decides otherwise (D9).

## Rollback
Each slice is one PR; revert it. The registry and tier0 check fail only on new regressions, so removing them restores today's behaviour. Moved readers and writers keep their old entry points as declared shims until parity is proven; nothing is deleted (Rule 12; archives compressed after parity).

## Owner decisions needed (recommended default first; merged with the Gemini GO/NO-GO list, duplicates removed)
1. **Adopt this umbrella and the five-context map (K1-K5, aggregates A1-A8); fold single-owner-guards, aq-update-unified and experience-capture in as slice groups, no separate plans.** Default: GO.
2. **Bounded `nh` spike inside aq-update-unified (ADAPT/SPIKE).** `aq-update` stays the only ledger and guard owner; `nh` replaces only the build/diff/dry-activate/GC plumbing if it keeps the pinned closure, scope, single privilege prompt and pre/post checks. Default: GO after U1/U3, after the nh claims are VERIFIED; needs your call on EUPL-1.2 for a public repo and on sudo handling. (Gemini D1, Codex.)
3. **Bounded LangGraph checkpoint spike (ADAPT/SPIKE).** Default: DEFER; authorize only if live durability tests of the coordinator run store show a replay or interrupt gap, with one authoritative store. (Gemini D2, Codex.)
4. **OpenClaw, LiteLLM, devenv, deploy-rs, colmena: confirm KEEP-CUSTOM/PUSHBACK.** Default: confirm; revisit deploy-rs vs colmena only if U8 gets a real remote deployment requirement; re-run the fact sheets at the MVP boundary. (Gemini D3, Codex.)
5. **External-critique intake convention:** `docs/architecture/external-reviews/` Markdown dispositions linked from `aq-collab-round`, plus the three-line PRD header; no new service. Default: GO. (Gemini D4, Codex.)
6. **Registry home:** new `config/decision-ownership.json` referencing `system-state-authorities.yaml` rows (default) vs extending that YAML only. Default: the new file with a cross-check generator, because several decisions are not state writes; if S1 finds the YAML sufficient, drop the file (minimal-code).
7. **Independence rule:** derived commit authorship is necessary, the exact-commit-bound receipt is sufficient, the declared `Author-lane` is advisory. Default: yes (resolves the Codex/Gemini wording difference).
8. **One remediator:** which component keeps remediation (S6). Default: the health-spider fix pipeline, others emit requests, confirmed by measured behaviour.
9. **Feature freeze (system-integrity-recovery P0+P1):** treat S1-S4 as integrity work permitted during the freeze. Default: yes; S5+ wait for the freeze exit unless you say otherwise.
10. **Orchestrator split for W7/W8 and claim verification:** Claude drafts and routes, Gemini and Codex review, Codex checks the unverified claims in the table (Rule 18, independence). Default: as stated; local Qwen review is a catch-up item once off the power gate.

## Provenance (inputs credited per lane)
- Simurg@claude/sonnet: control-plane census (`CENSUS-summary.md`), the first eight-context proposal, this PRD draft (architect lane, no code).
- Simurg@claude/opus-5.5: framing, coordination file, W7/W8 routing.
- Simurg@gemini (Gemini 4): adopt-vs-build fact sheets and the Anthropic-citation fact-check (`adopt-vs-build-20261122-gemini.md`); orchestrator synthesis (`gemini-synthesis.md`: five-context convergence, candidate verdicts, cultivation mechanism, GO/NO-GO list).
- Simurg@codex (codex-20261122-220409-i40c8q): architectural critique, ACTIONABLE_WITH_PUSHBACK (`codex-critique.md`): five-context map from the kernel declaration and ledger rows, ratchet design, no-new-service constraint, sequencing, nh/LangGraph spike verdicts.
- Local Qwen: no perspective (deferred by the 21% battery power gate); recorded, not fabricated.
- Reviewer (external, anonymized): the original feedback in `INPUT.md`.
- Existing plans carried forward: single-owner-guards-20261119, aq-update-unified-20261119, experience-capture-20261119, agent-work-durability-20261119, learning-attribution.
- Authorship caveat: the author lane of this draft is claude; independence of review requires non-claude reviewers (Codex, Gemini) per Rule 18.
