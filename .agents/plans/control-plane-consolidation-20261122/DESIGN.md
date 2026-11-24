# PRD: Control-plane consolidation (bounded contexts, contracts, single-owner guards, adopt-vs-build)

Status: DRAFT rev 4 (2026-11-23). Owner freeze pending. Author lanes: Claude (rev 1–3), Codex (rev 4 continuation). Independent confirmation requires an enrolled lane outside the author set; the requested Codex round-two confirmation is an additional advisory cross-check.
Tracker: `tracker.json` in this directory.
Review record: `.agents/plans/control-plane-consolidation-r1/` (`codex.md`, `gemini.md`, `README.md`). The round-two records are in `.agents/plans/control-plane-consolidation-r2/`. Dispositions are recorded below.
Origin: owner-trusted external review of 2026-11-22 (`.agents/delegation/outputs/external-review-20261122/INPUT.md`) plus the owner ask "how do we best incorporate this feedback into our designs, implementation, past and future work". Inputs: `CENSUS-summary.md`, `codex-critique.md`, `gemini-synthesis.md`, `adopt-vs-build-20261122-gemini.md`, `COORDINATION.md`.
Umbrella over (no duplicate plans): single-owner-guards-20261119, aq-update-unified-20261119, agent-work-durability-20261119 (already designed; reused, not re-specified), and experience-capture-20261119 (NOT frozen: it carries two open REVISE verdicts and is not bundled as frozen; see S10). single-owner-guards and aq-update-unified live only in worktrees and are not on main; S1 lands them with the first code.

## Problem

The reviewer said the number of control planes is high and that overlapping responsibilities make it hard to say which component owns a decision. The census confirms it: about 30 components decide things, and nine decisions have more than one owner.

| # | Decision | Owners today (evidence) | Cost observed 2026-11-19..22 |
|---|---|---|---|
| 1 | Model routing | `config/model-coordinator.json` is opened by the coordinator, `aq-role-route`, `delegate-to-claude` (and referenced by `aq-model-eval`, `scripts/ai/lib/gemini-model-guard.sh`, `scripts/ai/lib/brief_caps.py`, `scripts/governance/sweep-lanes.py`; the S3 inventory separates opens from mere references). `scripts/ai/lib/model_tiering.py` defines `MODEL_COORDINATOR` but does NOT read it: it hardcodes `_LANE_MODEL_KEYS` and `_CLAUDE_MODEL_FOR_COMPLEXITY` (`:28,38-49`), as does `aq-role-route:84-105`. The switchboard keeps its own profile catalog (`ai-stack/switchboard/switchboard.py:461`) | Parallel sources of model identity; a config edit has no single consumer to test |
| 2 | Lane availability and eligibility | wrapper cooldown files, `lane-eligibility-registry.json`, `aq-role-route`, `aq-land` reviewer choice each decide separately | Backlog LANE-AVAILABILITY-NOT-PER-MODEL: a cooldown on one model marked the whole lane down |
| 3 | PR branch mutation | `aq-land`, two ad-hoc land runners, Dependabot, Gemini all write PR branches | Five mutators. LAND-RUNNER-NOT-DURABLE; DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH (Dependabot refuses a rebase once anyone else pushed) |
| 4 | Review independence | `aq-land:396-403` and `aq-review-receipt:118,181` compare the declared `Author-lane`; receipt validation also accepts an earlier head after a clean main-only merge (`aq-land:386-413`) | Backlog AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR: the tag can say "gemini" while Claude wrote the commits; related to the fabricated-review-claims audit (about 85 PRs, 48 self-acceptances) |
| 5 | Health, QA and remediation | health-spider, health-monitor, `aq-qa`, coordinator `qa_check`, oncalld, `aq-alerts`, dashboard; four also remediate: auto-remediate, gap-auto-remediate, the health-spider fix pipeline, oncalld | Backlog EMBEDDER-STICKY-DEVICE-LOST records false-green health and missed recovery. Overlapping remediation authority is a separate risk documented in the ownership inventory. |
| 6 | Loops | `aq-loop`, ralph-wiggum, `aq-agent-loop`, autonomous-improvement, PRSI, `aq-collab-round`: six queues and retry policies | Rule 6 retry budget enforced six ways |
| 7 | Deploy | `aq-update`, `aq-deploy-current`, `nrs`/`nrb`/`nrd` (no guards), `system-update-full.sh`, `aq-update-tiers` | Nine entry points; a rebuild nearly ran on a 6-day-stale lock |
| 8 | Memory | coordinator store/recall, `aq-memory`, AIDB, Qdrant, agent memory files | Writers without one API |
| 9 | Learning | `continuous_learning_daemon`, meta-optimization, `aq-local-training-loop`, federated learning, lesson tools | No single lesson/proposal schema |

Root cause (Rule 19): ownership lives in prose and per-PRD lists. `config/system-state-authorities.yaml` already records one authority per state, but all ten rows are `SPLIT_BRAIN` with expired resolution deadlines (all dated 2026-10-09), and its checker does not yet fail on a NEW competing writer. The remedy (bounded contexts plus contracts) is right; the missing half is enforcement on the registry we already have.

Verified at drafting time (primary sources, see the claim table): the ten ledger rows; `aq-land:396`; the dispatch envelope, QA probe schema, memory registry and state-authorities checker exist. Not found: any file at the schema path `config/model-coordinator.json:7` points to (`./schemas/model-coordinator-schema.json`, a dangling reference). The five backlog IDs were verified against the primary backlog (see the claim table).

## Goals

1. Five bounded contexts (K1-K5) over nine aggregates (A1-A9); each aggregate has one owner, owned decisions, a published contract that is actually active, consumers and an enforcement check with a negative test.
2. Enforcement on the EXISTING registry (`config/system-state-authorities.yaml` and `scripts/governance/check-state-authorities.py`), no second registry.
3. An adopt-vs-build decision per context with explicit criteria and "replace, never run both" (with a sunset for any spike).
4. In-flight plans fold in as slices; no duplicate plans.
5. Future PRDs carry a three-line header: bounded context + owner, contract, build-vs-adopt check.

## Non-goals

- A big-bang rewrite. Each context converges by slices behind its contract; today's tree must pass every new check on day one (regression-only enforcement, dated exceptions).
- Adopting any external framework in the MVP. Current components are kept (D4).
- New services, daemons or state stores. If an evidence reducer needs a host it lives in an existing process; a new daemon or store is a scope decision for the owner.
- New canon instruction lines beyond single-owner-guards R4's zero-net budget; UI/UX styling (Rule 23 exemption).

## Design

### Principle
A context is a boundary of decision ownership, not a service. Cross-context interaction goes through a published, ACTIVE schema; a consumer never reads another context's private state (files, cooldown dirs, queues). Complexity lives in the aggregate; each piece stays simple (Rule 20b).

### One map: five contexts (K1-K5) over nine aggregates (A1-A9)
The target map is the five contexts (derived from the kernel declaration and the ten ledger rows; Codex and Gemini converged on it, the census's 8-9 mirrored current tool boundaries). The census contexts are kept as aggregates, each nested in exactly one context. A9 (approval and authority) is COUNTED, not optional: operator grants need a mandatory owner.

| Context | Aggregates | Ledger rows | Single owner per decision |
|---|---|---|---|
| K1 Work orchestration | A2 dispatch, delegation, lane availability and eligibility; loops are callers | `planning-round`, `delegation-lifecycle`, `intent-resume`, `workflow-run-task` | coordinator (round store, task registry, intent interface, run store); `aq-event` append path; `RESUME.json`/`PULSE.log` are projections |
| K2 Model execution | A1 routing | `routing-model-execution` | coordinator owns route SELECTION and POLICY INTERPRETATION and issues the resolved run plan; switchboard owns EXECUTION against an accepted plan and returns the execution receipt. Neither owns the other's half |
| K3 Trust and integration | A3 review, A4 landing, A9 approval | `dashboard-operator` | operator grants: coordinator approval store is the sole writer; independence verdict: `aq-review-receipt`; protected-branch admission: `aq-land` |
| K4 Host configuration and activation | A5 deploy | `configuration` | evaluated Nix options own configuration; `aq-update` owns the activation decision and ledger |
| K5 Evidence, memory and learning | A6 memory, A7 observability and QA, A8 learning (separate aggregates, one owner each) | `qa-effectiveness`, `learning-eval`, `memory-rag` | evidence reducer; coordinator evaluation ledger; MemoryBroker (Qdrant is a derived index). Learning and evidence EMIT proposals and requests; the context that owns a decision issues the authoritative command |

How K1 feeds K2: K1 publishes a per-(lane, model) availability and eligibility event; K2 consumes it when it resolves a plan. K2 never reads wrapper cooldown files.

### Aggregates

| # | Aggregate | Single owner | Published ACTIVE contract | Notes on stale contracts (r1) |
|---|---|---|---|---|
| A1 | Routing | coordinator (selection, policy, resolved plan); switchboard executes | `config/model-coordinator.json` + NEW `config/schemas/model-coordinator-schema.json` (the filename already referenced at `model-coordinator.json:7`) + `ResolvedRunPlan` v1 (execution profile, authentication class, fallback policy) + execution receipt | S3 writes the schema and `ResolvedRunPlan`; credentials stay in the execution lane |
| A2 | Dispatch, delegation, availability | delegation registry + `lane-eligibility-registry.json`; `delegate-*` are thin executors | `agent-dispatch-envelope.schema.json` (active, includes `gemini`) + availability event keyed `(lane, model)` | `delegation-task-record.schema.json` is INACTIVE (M2B not authorized, lane enum lists `antigravity`, omits `gemini`): NOT used as a contract unless S4 includes its authorization and enum update. All 25 eligible grants in `lane-eligibility-registry.json` expire 2026-11-26: renewal is a pre-S1 owner act |
| A3 | Review and trust | `aq-review-receipt` | review receipt schema-2 (exact head + tree, reviewer lane); v3 adds authenticated reviewer identity and candidate binding | existing schema-2 receipts stay verifiable (backward compatible) |
| A4 | Integration / landing | `aq-land` | landing record + branch-mutation lock; the durable runner is `aq-land-runner.service` from agent-work-durability (no second runner) | |
| A5 | Deploy | `aq-update` (`aq-deploy-current` becomes its stage) | aq-update ledger (aq-update-unified) | |
| A6 | Memory | MemoryBroker; coordinator memory API is the facade | `config/agent-memory-surface-registry.json` (made normative) | |
| A7 | Observability and QA | one health pipeline, one remediator (provisional, see D8) | `qa-provider-probe-contract.schema.json` + NEW health sample/verdict schema | the probe schema omits `gemini` (`:13`); S6 adds it |
| A8 | Learning | continuous-learning + PRSI | `learning-candidate.schema.json` + lesson/proposal schema | depends on the experience-capture revision (S10) |
| A9 | Approval and authority | coordinator approval store (operator grants); identity-kernel | approval envelope + `capability-lease.schema.json` | The lease schema describes report-only checks. Switchboard implements per-tool enforcement and its Nix service declares it enabled. Live enforcement remains unverified. S2 reserves operator grants at queue admission. |

Loops (ralph-wiggum, `aq-loop`, `aq-agent-loop`, autonomous-improvement, `aq-collab-round`) are consumers of A2/A3/A4, not a context; their retry policies converge on A2's budget (S8).

### Single-owner enforcement: extend the existing registry, no second one
Withdrawn from rev 2: the proposed decision-ownership JSON registry, `check-decision-ownership.py` and the cross-check generator. Reason (Gemini P0-2, Codex P1-3): they would duplicate `config/system-state-authorities.yaml` (10 rows, ceiling 128) and contradict single-owner-guards, which forbids a new registry. The withdrawn O1 reference (capability-catalog `concern/role/shim_of`) is also dropped: single-owner-guards R2 specifies a new entry-point shim map at `config/entry-point-shims.yaml` (NEW in S9).

S1 extends `config/system-state-authorities.yaml` and the existing schema and checker. Additive `guards[]` entries name the decision, owner, protected operation, scan scope, negative fixture and authoritative blocking point. They reference existing `observed_writers[].invocation_fingerprint`, `bypasses[].invocation_fingerprint` and `writer_signatures[].command_forms`. Source-bound exceptions use the existing `source_sha256`. Use the protected base inventory and occurrence counts. A copied invocation increases the count and fails. An incomplete scan of declared scope fails. Dynamic calls require enforcement at the authority listed below. Exception expiry warns at pre-commit and fails scheduled maintenance.

S1 runs `check-state-authorities.py --staged-regressions` through tier0 and the required `state-authority-regressions` CI check, using trusted base checker, baselines and workflow for candidate scans. Changes to authority policy receive protected review and must pass fixtures through that same trust boundary. QA and dashboard expose results as evidence. S1 acceptance verifies the required check against an actual refused candidate.

| Id | Protected operation and owner | Detection and negative test | Authoritative blocking point |
|---|---|---|---|
| DO-1 | Route selection, coordinator | Detect direct config readers and hardcoded policies in scripts and AI stack. Exercise valid keys that request a forbidden route. | S3 coordinator rejects the resolved route before dispatch. Execution receipts are evidence. Retire inventoried reader bypasses at S3 exit. |
| DO-2 | Protected-branch merge, aq-land | Detect direct protected writes and unapproved cross-owner branch writes, with scoped fingerprints for authorized topic and receipt writes. | S2 protected GitHub merge queue and required admission check. S7 adds enforcement for cross-owner and bot branches via scoped writer permissions and mutation authority. That broader boundary is deferred to S7. |
| DO-3 | Privileged host activation, aq-update | Detect alternate rebuild or switch invocations, including wrapped commands. Inventory flake updates under the static check. | S5 host sudo/polkit denies direct privileged activation and allows the approved entry point and exact approved operation. Ledger is evidence. Repository-only flake edits are governed by tier0 and protected CI. |
| DO-4 | Per-model availability, coordinator availability API | Detect direct cooldown-file reads and exercise two models on the same lane. | S4 shared admission denies a down model before dispatch and still admits its healthy sibling. Availability events are evidence. |
| DO-5 | Independent review, protected landing | Exercise the forged, stale, self-reviewed and replayed cases below. | S2 aq-land preflight and a required check on the authoritative merge-group SHA. Refusal events are evidence. |
| DO-6 | Remediation execution, designated remediator | Detect direct restart and fix invocations. Exercise a second would-be remediator. | S6 host/service permissions deny restart authority to other automation principals. Events are evidence until enforcement is activated. |
| DO-7 | Memory writes, MemoryBroker facade | Detect direct store clients and HTTP writes. Exercise an unapproved write identity. | S11 ingress and credentials deny store writes outside the facade. Registry checks establish inventory. |

S5, S6, S7 and S11 are proposed follow-ons. Reassess the deferred enforcement on 2026-12-15 and record the owner, evidence and next date in the tracker if still open.

### Shared S2 and S1b admission contract

**Candidate v3.** The canonical record binds numeric GitHub repository ID, PR number, target ref, exact base commit, head commit and tree, authenticated provenance and author-set digests, and policy revision. Introduced commits are evaluated relative to that base. Exact retry may reuse a review that is still current. Every change to a bound field, including a new base or head with an identical tree, requires fresh review. Schema-2 and earlier-head receipts are historical evidence.

**Provenance.** Each introduced commit and transition that changes the candidate needs an attestation from enrolled, lane-isolated signing material tied to the writer and operation. The protected verifier checks the signed commit/transition against the owner-controlled registry and the authenticated provider record of the update or scoped owner adjudication. The author union includes authenticated authors and mutators and verified collaborators. Declared author and co-author trailers can add exclusions. Unknown or conflicting attribution refuses admission until resolved by evidence. The same principal or lane cannot author or mutate and then review the candidate.

**Review identity.** The trusted verifier retrieves the formal APPROVED review from the canonical authenticated GitHub Reviews API. It binds numeric account ID, review ID, state, commit and canonical candidate digest. A versioned, owner-controlled registry maps distinct GitHub accounts to enrolled reviewer lanes. Accounts and credentials are isolated by lane. The verifier evaluates current formal dispositions and dismissals. A newer applicable changes-requested review or dismissal invalidates admission. The review body can carry the digest, but authority comes from the API identity and review state. Local sessions, trailers and the shared receipt branch are evidence only. `aq-review-receipt` emits and verifies this record. `aq-land`, the durable runner and `check-review-disposition.py` use the same protected verifier. [GitHub Pull Request Reviews](https://docs.github.com/en/rest/pulls/reviews)

**Protected merge.** Require a single-PR GitHub merge queue group with a required review-disposition check sourced from a trusted workflow and configured without direct or admin bypass. The protected checker obtains the queued source head from authoritative queue and PR state and checks the reviewed base against the group's base, the exact source head, ancestry and resulting group tree. Require the reviewed base to be an ancestor of the head and the group tree to match the reviewed tree. Bind a successful check to that group SHA only. A base, head, or policy change invalidates the prior decision and holds until fresh evidence is present. For automated queue admission, the checker also verifies that the authoritative queue entry can be attributed to the enrolled admission principal and its exact reserved or applied operation. Unknown queue provenance holds the merge. S2 acceptance must exercise base and head races, a queue entry without a valid operation, a reviewer dismissal after a successful check, and a policy change while queued. Required provider protection must discard the stale group or deny the write in each case. If the provider cannot enforce these post-check changes at merge time, hold automated activation. If platform capability, required protections or canonical group attribution cannot be proven, automation remains held. [GitHub merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)

**Owner grant and recovery.** A scoped operator grant authorizes one queue admission request for one actor, action and candidate. The coordinator durably reserves it with a unique operation ID and compare-and-swap before dispatch, validates scope, policy epoch, expiry and revocation before issuing the remote mutation, and records the exact external result. Queue admission is the grant-gated operation. A later protected merge still requires the current group check. Expiry or revocation denies any issuance or retry that has yet to be authorized. Revocation that must cancel a pending merge needs an authoritative queue cancellation and confirmed hold. If a grant requires a time or revocation fence through the physical merge, hold automation unless that provider boundary can enforce it.

The same operation uses `RESERVED`, `APPLIED`, `HELD` or `VOID`. A retry reconciles against the authoritative remote result before any send. An exact confirmed prior application finalizes the original operation even if the grant has since expired. Confirmed absence requires evidence that any previous sender is fenced from sending and that no matching operation was applied. Only then may the current worker revalidate the exact candidate, current GitHub protections, and current grant for the same operation. If the grant is revoked or expired, void the unapplied reservation and require a fresh scoped grant. An ambiguous response remains HELD without resending. A changed candidate voids an unapplied reservation and requires fresh review and grant where the action requires one. Cross-candidate and cross-operation replay are refused. S2 owns the verifier and reservation protocol. S1b exercises the same contract at crash and recovery points. An authoritative absence or safely fenced sender that cannot be proven is a hold.

### Adopt-vs-build

Reviewer claim: "Anthropic's recent guidance on factories is to prefer maintained projects over bespoke ones." Status: UNVERIFIED and not supported by the cited guidance (Codex checked "Building effective agents" and the Managed Agents pages: simple composable patterns; the managed offering is Anthropic's own hosted service). Recorded as "not found", not "false". The reviewer's underlying point (prefer maintained projects when they fit) stands on its own merit.

Criteria for every candidate: (a) OAuth/session auth, no API keys; (b) local-first llama.cpp on the 4 GB iGPU (GPU layers <= 12); (c) Nix-declarative; (d) headless CLI; (e) maintenance and licence; (f) security posture scoped by package and version; (g) migration cost vs the component it replaces. Rule: REPLACE, NEVER RUN BOTH: a spike names the retired component, a parity test and a SUNSET; later replacement requires read-only shadow comparison, state reconciliation, fencing the incumbent writer before cutover and a proven reverse handoff; only one writer holds authority at a time.

MVP stance (Codex P2-5): keep current components. K1 and K5 on the existing coordinator and evidence/memory paths, K2 on coordinator plus switchboard, K3 on existing trust and admission paths, K4 on evaluated Nix and `aq-update`.

| Candidate | Verdict | Condition and sunset |
|---|---|---|
| nh (EUPL-1.2) | ADAPT/SPIKE, bounded | Only as the low-level build/diff/dry-activate/GC step INSIDE `aq-update`, behind a flag in S5. Flag window: at most one full update cycle after the first live `aq-update --deploy` using it; at the end either cut over (and remove the raw `nixos-rebuild`/`home-manager switch` calls from `aq-update`) or delete the flag and the spike. Must preserve the pinned closure, scope, single privilege prompt and pre/post checks. Licence scope: invoking the unmodified `nh` binary from nixpkgs is different from linking or modifying EUPL-1.2 code; stated in D2, owner confirms |
| LangGraph | DEFER | Revisit only if live replay or interrupt tests of the coordinator run store show a gap; core only, one authoritative store; `langgraph-api` stays out (licence and advisories) |
| OpenClaw | KEEP-CUSTOM | no demonstrated boundary or containment parity (AppArmor + bubblewrap, independent reviewer lanes) |
| LiteLLM | KEEP-CUSTOM | adds a virtual key and Postgres; its supply-chain advisory (GHSA-92x9-889m-jgmw covers 1.107.0) is separate from the subscription-passthrough question |
| deploy-rs, colmena | KEEP-CUSTOM | revisit only for a real remote-fleet requirement (U8) |
| devenv | KEEP-CUSTOM | needs a concrete gap in the existing development environment |

#### Claim-verification status
Labels: VERIFIED = checked against a primary source by a lane other than the claimant (source named); UNVERIFIED = single-lane or secondary; REFUTED = contradicted by a primary source. Updates in rev 3 apply the r1 reviewers' primary-source checks.

| Claim | Status | Source |
|---|---|---|
| Ten of ten ledger rows `SPLIT_BRAIN`, all `ADJUDICATED`, all resolution deadlines expired 2026-10-09 | VERIFIED | `config/system-state-authorities.yaml` (Gemini r1; Codex confirmed all ten ids map once) |
| `aq-land:396-403` compares the declared `Author-lane`; the same check at `aq-review-receipt:118,181`; clean-merge path accepts an earlier head (`aq-land:386-413`) | VERIFIED | primary files (Gemini and Codex r1) |
| `scripts/ai/lib/model_tiering.py` reads `config/model-coordinator.json` | REFUTED | `model_tiering.py:28,38-49` defines the constant unused and hardcodes model keys (Gemini r1) |
| Switchboard profile catalog at `switchboard.py:461` | VERIFIED, path corrected | `ai-stack/switchboard/switchboard.py:461`; the ledger row still cites a stale `ai-stack/mcp-servers/...` path (S1 fixes it) |
| No model-coordinator schema exists | VERIFIED, with naming catch | `model-coordinator.json:7` references `./schemas/model-coordinator-schema.json` (hyphen), which does not exist |
| Capability catalog `concern/role/shim_of` (O1) is the entry-point registry | REFUTED | single-owner-guards withdrew O1; R2 specifies `config/entry-point-shims.yaml` (NEW in S9) |
| `delegation-task-record.schema.json` is an active contract | REFUTED | schema marks itself INACTIVE (M2B not authorized); enum omits `gemini` |
| `capability-lease.schema.json` is enforced piecemeal | VERIFIED IN SOURCE | The schema describes report-only checks. Switchboard implements and calls the per-tool evaluator (`capability_lease_gate.py:698-724`, `switchboard.py:1238-1272`); the Nix service declares enforcement enabled (`nix/modules/services/switchboard.nix:442`). Runtime activation remains unverified. |
| `qa-provider-probe-contract.schema.json` covers all lanes | REFUTED | `:13` omits `gemini` |
| OpenClaw or LiteLLM cannot use Claude/Codex subscription workflows (blanket) | REFUTED as a blanket claim; eligibility for THIS harness UNVERIFIED | upstream docs (Codex r1): OpenClaw documents Claude CLI and multiple auth modes; LiteLLM documents Claude Code subscription support and Codex support from 1.109.0. Whether provider terms, headless configuration and containment fit this harness is untested |
| Anthropic blocks consumer Claude OAuth in OpenClaw | UNVERIFIED, contested | Gemini says banned; no primary Anthropic terms source cited yet |
| LiteLLM compromised release | VERIFIED for 1.107.0 on PyPI (advisory record); Docker details UNVERIFIED | GHSA-92x9-889m-jgmw (Codex r1) |
| OpenClaw CVE-2026-25253 and CVE-2026-62201 | VERIFIED as public records; exact candidate pins UNVERIFIED | NVD and CISA bulletin (Codex r1) |
| LangGraph CVE-2026-55235 and -55236 concern `langgraph-api`; core has no intrinsic provider-key requirement | VERIFIED scoped by package; checkpoint advisories (e.g. CVE-2026-71433) evaluated only if a checkpointer is chosen | cve.org records; LangGraph Graph API docs (Codex r1) |
| nh v4.5.0, EUPL-1.2, no CVEs; deploy-rs v1.0.0; colmena v0.5.0; devenv v2.4.0; 90-day commit counts; nixpkgs versions | UNVERIFIED (Gemini search snippets) | stays so until a non-Gemini lane checks the upstream sources; absence-of-CVE claims are never VERIFIED by absence |
| Parity of any candidate with session-only CLIs, no stored API keys, AppArmor + bubblewrap, independent reviewer lanes, declarative activation and llama.cpp on 4 GB / 27 GB | UNVERIFIED (untested) | reason every adoption is a bounded spike |
| `LAND-RUNNER-NOT-DURABLE` | VERIFIED | `.agent/memory/issues-backlog.md:10713` records interruption without durable recovery. |
| `LANE-AVAILABILITY-NOT-PER-MODEL` | VERIFIED | `.agent/memory/issues-backlog.md:10887` records a model failure suppressing its sibling. |
| `AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR` | VERIFIED | `.agent/memory/issues-backlog.md:10936` records the tag and writer mismatch. |
| `EMBEDDER-STICKY-DEVICE-LOST` | VERIFIED | `.agent/memory/issues-backlog.md:10942` records health 200, embeddings 500 and missed recovery. It establishes the symptom. |
| `DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH` | VERIFIED | `.agent/memory/issues-backlog.md:10954,11063` records seven recreations and the need to preserve maintainer edits separately. |

### Fold-ins (no duplicate plans)

| Existing plan / item | Becomes | Aggregate |
|---|---|---|
| single-owner-guards R1 | core of S1 (DO-2, DO-3 on the existing checker) | registry, A4/A5 |
| single-owner-guards R2/R3/R4 | S9 | cross-cutting |
| aq-update-unified U-slices | S5 (after MVP, see order) | A5 |
| agent-work-durability (`aq-land-runner.service`, restart recovery) | S1b verifies and wires it; no new runner | A4 |
| experience-capture S1-S7 | S10, only after its REVISE verdicts are resolved | A8 |
| LANE-AVAILABILITY-NOT-PER-MODEL | S4 | A2 |
| AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR | S2 | A3 |
| LAND-RUNNER-NOT-DURABLE; DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH | S1b, S7 | A4 |
| EMBEDDER-STICKY-DEVICE-LOST | S6 | A7 |

### Past-work mapping

| Existing component | Aggregate | Disposition |
|---|---|---|
| `config/model-coordinator.json`, coordinator route policy | A1 | keep (owner of selection and policy) |
| switchboard | A1 | keep (execution of an accepted plan and its receipt; its own profile catalog is derived from or checked against the resolved plan) |
| `aq-role-route`, `delegate-to-claude`, `aq-model-eval`, `gemini-model-guard.sh`, `brief_caps.py`, `sweep-lanes.py`, `model_tiering.py` | A1 consumers | consumer: stop hardcoding model keys, call the route-policy module |
| `lane-eligibility-registry.json`, delegation registry, `delegate-*` | A2 | keep; wrapper cooldown files merge into the availability API |
| `aq-review-receipt` | A3 | keep, extended per "Independence and approval" |
| `aq-land` | A4 | keep (owner); the two ad-hoc runners retire to `aq-land-runner.service`; Dependabot/Gemini request landing or recreate via `aq-land` |
| `aq-update` | A5 | keep; `aq-deploy-current` becomes its stage; `nrs`/`nrb`/`nrd`/`nrs-force`/`system-update-full.sh` retire to declared shims, archived (compressed) after parity |
| AIDB, Qdrant, MemoryBroker/coordinator memory API | A6 | keep; the facade is the one write path |
| health-spider verdict | A7 | keep; the four remediators merge into one (provisional choice, S6); others emit requests |
| continuous_learning_daemon, PRSI | A8 | keep; others merge or become consumers in S10 |
| loops | consumers | converge retry policy on A2 behind parity tests |
| identity-kernel, leases, epochs, attention queue | A9 | keep |

### Future-work rule and cultivating external feedback (no new service)
- One Markdown disposition per external review at `docs/architecture/external-reviews/YYYY-MM-DD-<slug>.md`, reached from `aq-collab-round`: reviewer wording and provenance, strongest version of the argument, evidence and what would change the conclusion, claim status, owner ACCEPT/REJECT/DEFER with a falsifiable re-evaluation trigger, dated follow-through link. Created with S1 (no docs-only PRs).
- Accepted findings link to a ledger row; the cutover retires the writer, revokes its access and removes its dated allowance in the same change.
- New PRDs carry a three-line header (checked by the existing PRD/tracker gate, new PRDs only): (1) bounded context K-n and single decision owner; (2) aggregate/store and versioned contract; (3) build-vs-adopt check (why no maintained nixpkgs/OSS component fits, or the bounded spike condition). It is added to `.agent/templates/PRD.md` (created by single-owner-guards R4).
- If the Markdown plus round link proves insufficient, the gap is logged and this clause revisited, not pre-empted.

## Execution order (one order, used everywhere)
Start after the PR queue clears (W2-W4), the W9 rebuild completes and lane grants are renewed (expire 2026-11-26); capture the post-rebuild boot id and live baseline first. Under the system-integrity-recovery feature freeze only integrity work proceeds:

S0 (freeze) -> S1 -> S2 -> S1b -> S4 -> S3 -> S12 (MVP exit audit)  =  MVP.
Then, after the freeze exits: S5 -> S6 -> S7 -> S11 -> S8 -> S9 and S10 (S10 only after experience-capture's REVISE verdicts are resolved; S9 and S10 share the S8 prerequisite).

Reasoning: the incidents of 2026-11-19..22 are in review, landing, availability and routing, not deploy; aq-update-unified is already frozen, has its own order (`U0 -> U1 -> U3 -> U2 -> U4 -> U5 -> U6`, early U7 gate, U8 deferred) and is not needed by the MVP guards. Codex's note listed aq-update-unified second; this PRD deliberately places it after the MVP because of the feature freeze, and D9 asks the owner to confirm or reorder. S2 precedes S1b so the trust gate is live before the runner relies on it; S4 precedes S3 because K2 consumes K1's availability event.

## Slices (one author lane and one disjoint reviewer lane each, Rule 17/18; explicit model override on every dispatch)

Lane notes: author = cheapest measured eligible lane. Local Qwen takes bounded single-edit inventory and fixture work where measured capable and is NEVER trust-critical (`lane-eligibility-registry.json` grants it no reviewer eligibility; its catch-up input is advisory/architect, not a review verdict). Codex implements when capability requires. Reviewer lanes are eligible Gemini or Claude roles for Codex-authored work and eligible Codex or Gemini roles for Claude-authored work. The registry identifies Sonnet and Opus separately for eligibility. They share the Claude author exclusion; the same lane never authors and reviews one slice. Where the cheaper lane is unavailable, the substitution is recorded (Rule 18).

| Slice | Scope and dependency | Author / reviewer | Measurable exit and validation | Rule 15 activation row |
|---|---|---|---|---|
| S0 | Freeze contracts, journeys and D0–D10 after confirmation. Record Qwen input if available. | Claude / Codex authoring; independent eligible lane for confirmation | Confirmation bound to exact DESIGN.md and tracker.json; owner decisions recorded; PLAN_READY only when both are complete | n/a |
| S1 | Extend the existing registry/checker with single-owner-guards R1. Inventory baselines and repair the stale switchboard path. Link existing plans and review disposition. | local inventory and fixtures, Codex checker / Gemini | Positive, negative and adversarial fixtures. Real offending staged change and protected-CI candidate fail naming the owner. | Tier0 and required CI block static regressions; phase0 and dashboard show evidence. |
| S2 | Own shared candidate v3, review identity, provenance, grant reservation and protected group verification; migrate aq-land, aq-review-receipt and check-review-disposition.py. Depends on S1. | Codex / Gemini | Genuine approval allows protected landing; forged, stale, dismissed and self-reviewed candidates fail. Race base and head changes, test same-tree re-review and replay. Verify platform protections before enabling. | Real required group check and aq-land preflight; refusal QA, dashboard and operator hold. |
| S1b | Wire the existing durability runner after verifying its deployment. Use the S2 verifier and reservation protocol. Retire alternate runners after parity. Preserve maintainer edits outside bot branches before any authorized Dependabot recreate. Depends on S2. | Codex / Claude | Crash before send, lose response after send, expire or revoke before retry, change base, race workers; reconcile one exact remote application or hold. | Enabled runner, QA and dashboard expose operation state. Owner can hold and reconcile. |
| S4 | Per-model availability and common dispatch admission (DO-4). Retire direct cooldown reads. Depends on S1b. | Codex / Gemini | A real unhealthy model is refused and its healthy sibling is admitted. | Dispatch gate with QA, dashboard and operator hold. |
| S3 | Coordinator policy, schema, ResolvedRunPlan v1, execution receipt and call-site migration (DO-1). Depends on S4. | Codex, local for bounded call sites / Claude | Real allowed route executes and emits a receipt; a route using valid but forbidden keys is denied before dispatch. | Coordinator admission with QA, dashboard and operator hold; activation requires owner decision. |
| S12 | MVP exit audit on one integrated subject, after S3. | Independent eligible code and runtime reviewers | J1–J5 on real dependencies, including protected success, refusal and crash recovery. | Activation evidence and separate owner acceptance. |
| S5 | After S12, run frozen aq-update-unified order; optional nh with approved sunset. DO-3 host authority. | Codex / Gemini | Frozen deploy journeys, direct privileged activation denied, approved intervention exercised. | Host sudo/polkit blocks; owner activates; ledger supplies evidence. |
| S6 | After S5, select one remediator from measured embedder recovery and extend the probe schema. | Codex / Claude | One failure yields one permitted attempt and denial for a second principal. | Host permissions block; events supply evidence. |
| S7 | After S6 and S1b, scope bot and cross-owner branch writers and retire bypasses (DO-2). | Codex / Gemini | Concurrent or unauthorized external writer denied; authorized bot regeneration works. | Provider writer permissions and branch mutation authority. |
| S11 | After S7, enforce MemoryBroker facade as store writer (DO-7). | Codex / Claude | Unauthorized direct writer denied at store ingress. | Store credentials and ACLs block. |
| S8 | Loop convergence: one retry budget (A2) across the six loop families, one family per slice, parity test before retiring any loop | local or codex per family / gemini | per-loop parity | per family |
| S9 | single-owner-guards R2/R3/R4 (shim map, duplicate ratchet, zero-net canon, PRD template with the three-line header) and canon parity across the six targets (Rule 16) | codex / gemini | zero-net-lines test; a new PRD missing the header fails | template referenced from Rule 8's SSOT |
| S10 | A8: experience-capture, ONLY after its two open REVISE verdicts are resolved and it is re-reviewed; lesson/proposal schema; loops stop writing lessons directly | per that PRD / independent | that PRD's journeys, real data | per that PRD |

## MVP freeze proposal
MVP order is S0 → S1 → S2 → S1b → S4 → S3 → S12. S5, S6, S7, S11 and S8 follow in order. S9 and S10 may run in parallel after S8; S10 also requires independent clearance of experience-capture.

- J1. A new unauthorized invocation fails staged tier0 and the trusted required CI check on a real candidate; the approved path passes.
- J2. A protected merge accepts a current authenticated independent review. Impersonation, author overlap, missing provenance, stale or dismissed review, queue races and a same-tree change of candidate all fail closed.
- J3. Actual dispatch refuses an unavailable model and admits its healthy sibling. QA and dashboard report both, and the owner can intervene.
- J4. A real caller routes through the coordinator and produces an execution receipt. A structurally valid but forbidden route is refused at dispatch.
- J5. The existing runner recovers across send and persistence failures with one authoritative remote application, or holds when it cannot safely determine the result. Check exact success reconciliation, fenced retry, race, expiry, revocation and changed candidate.

## Risks
- Big-bang migration: regression-only checks, dated exceptions, one aggregate per slice, parity before retirement.
- Contract churn: ACTIVE schemas only, additive changes, versioned contracts, contract tests.
- Registry drift: eliminated by not creating a second registry.
- Check false positives: documented syntax, fixtures for comments and echo text, exempt-path list in DO-2.
- Identity enrollment, branch settings and exact queue/group behavior are S2 activation prerequisites.
- Lane eligibility grants expire 2026-11-26 (owner renewal before S1).
- Unverified research: adoption stays a bounded spike with a sunset.
- Local lane unavailable or untrusted for gates: recorded; Qwen input is advisory.
- Feature freeze: only integrity slices run before the freeze exit.

## Rollback
Each slice is one PR; revert it. Guards fail only on new regressions, so removing them restores today's behaviour. Moved readers and writers keep their old entry points as declared shims until parity is proven; nothing is deleted (Rule 12; compressed archives after parity). For any later replacement the incumbent writer is fenced before cutover and the reverse handoff is tested.

## Owner decisions (recommended default first; Gemini GO/NO-GO list merged, duplicates removed)
0. Renew only the active, needed eligibility grants due 2026-11-26. Recommended scope is the principals and roles required by the approved slices and independent confirmation. Show exact IDs, scopes and proposed expiry before changing the registry; no blanket renewal.
1. Adopt this umbrella and the five-context map (K1-K5, aggregates A1-A9); fold the three PRDs in, with experience-capture held until revised. Default: GO.
2. Bounded `nh` spike inside `aq-update` (S5) with the flag sunset above. Default: GO after the nh claim rows are VERIFIED by a non-Gemini lane. Licence note: invoking the unmodified nixpkgs `nh` binary differs from linking or modifying EUPL-1.2 code; confirm this reading and the sudo handling.
3. LangGraph: DEFER unless a replay or interrupt gap is demonstrated; core only.
4. OpenClaw, LiteLLM, devenv, deploy-rs, colmena: confirm KEEP-CUSTOM for the MVP; revisit deploy-rs vs colmena only for a real U8 remote requirement; re-run fact sheets at S12.
5. Intake convention: disposition Markdown + `aq-collab-round` link + three-line PRD header, no new service. Default: GO.
6. Registry home: extend `config/system-state-authorities.yaml` and its checker (default, changed from rev 2); no `decision-ownership.json`.
7. Adopt the shared S2 and S1b contract for authenticated identity, exact candidate protected merge, and replay-protected queue admission. Default: GO.
8. Single remediator: PROVISIONAL default is the health-spider fix pipeline; the final pick is made in S6 from measured behaviour, not frozen here.
9. Execution order: MVP (S0, S1, S2, S1b, S4, S3, S12) first under the feature freeze, S5 aq-update-unified after the freeze exit. Owner may instead pull S5 earlier (Codex's sequencing note); default as written.
10. Preserve Claude’s draft and Codex’s continuation. Use an eligible non-author lane for independent confirmation and the requested Codex follow-up as advisory. Any adoption claim needs a verifier independent of the claimant. Local Qwen is advisory.

## Review r1 disposition

Historical round-one record. The shared contract and round-two dispositions supersede earlier resolutions on the same topics.

Review r1: Codex REVISE (5 findings, numbered C1-C5; claim table C-claims) and Gemini REVISE (9 findings, numbered G1-G9). Local Qwen input was outstanding in round one. Current freeze criteria are defined in S0 and D10.

| Id | Sev | Finding | Disposition and change |
|---|---|---|---|
| G1 | P0 | K2 vs A1 routing owner conflict; `ResolvedRunPlan` missing from S3; schema filename mismatch | FIXED: coordinator owns selection and policy interpretation, switchboard executes (K2, A1, past-work map); S3 specifies `ResolvedRunPlan` v1 and the receipt; schema named `model-coordinator-schema.json` per `model-coordinator.json:7` |
| G2 | P0 | Duplicate `decision-ownership.json` registry; withdrawn O1 cited | FIXED: registry, checker and generator withdrawn; guards extend `system-state-authorities.yaml` and its checker; O1 replaced by `entry-point-shims.yaml` (R2); D6 flipped |
| G3 | P0 | Conflicting execution orders (Sequencing, MVP, D9, S1b, tracker) | FIXED: one order in "Execution order", reused in MVP freeze, D9, slice table and `tracker.json`; S1b reuses `aq-land-runner.service`; S12 is the MVP exit gate; tracker synced (D1-D10, K/A ids) |
| G4 | P1 | Stale/inactive contract references, grant expiry, Service Coverage | FIXED: A2 on the active dispatch envelope; `delegation-task-record` INACTIVE and not used unless S4 scopes its authorization; probe schema `gemini` gap goes to S6; A9 enforcement claim corrected; grants expiring 2026-11-26 noted as pre-S1 owner act; every DO registered in `phase0.py` and the dashboard |
| G5 | P1 | Rule 17/18 lanes, self-review, local reviewer seat | FIXED: one author lane and one disjoint reviewer per slice; cheapest-first; local advisory only and never trust-critical; D10 reworded |
| G6 | P1 | DO-1/2/5 specs; S2 must change both receipt sites; fail-closed on human-only author | FIXED: DO table with exempt paths for DO-2, DO-5 as a runtime admission check, DO-1 contract test over all consumer keys; S2 changes `aq-land:396` and `aq-review-receipt:118,181`; unknown provenance is unioned with the declared lane, never empty |
| G7 | P2 | nh flag window and EUPL-1.2 scope | FIXED: flag sunset in "Adopt-vs-build" and S5; licence reading stated in D2 for owner confirmation |
| G8 | P2 | Apply primary-source claim updates | FIXED: claim table rewritten (VERIFIED/REFUTED rows with sources; Gemini-only rows stay UNVERIFIED) |
| G9 | P3 | D8 provisional; do not bundle unrevised experience-capture | FIXED: D8 provisional, final in S6; experience-capture held out of the frozen set and gated at S10 |
| C1 | P1 | One owner per decision (K2/A1; K1 to K2 eligibility; A9 counted; evidence vs authoritative remediation) | FIXED: owner table; K1 publishes availability events consumed by K2; A9 counted; K5 emits proposals, owning context commands |
| C2 | P1 | Independence and approval bound to authenticated identity and admitted candidate; clean-merge path; recovery | FIXED: section "Independence and approval"; the word "authenticated" is claimed only after S2 documents the minting authentication |
| C3 | P1 | DO-1..DO-7 enforceable (reuse registry; protected op, owner, scope, negative fixture, exception identity and deadline, live control; fingerprint+count; fail on uncovered scope; maintenance expiry) | FIXED: shared guard rules plus the seven-row DO table |
| C4 | P1 | Freeze dependencies and live acceptance per slice; lanes cheapest-first; no new service | FIXED: dependencies and measurable exits per slice; real-caller receipt check in S3; S4 proves parity and retires the old reads; no new daemon, evidence reducer hosted in an existing process |
| C5 | P2 | Keep current components for the MVP; defer LangGraph; nh only as an `aq-update` detail; shadow comparison and fencing for later replacements | FIXED: MVP stance paragraph, candidate table, replacement rules |
| C-claims | n/a | Codex claim-verification results (five contexts verified; Anthropic claim unsupported; blanket OAuth denial refuted; CVEs scoped by package) | APPLIED to the claim table |
| Gemini scope note | info | the review prompt truncated at A2 (lines 65-247 read directly) | NOTED: no change |


## Review r2 disposition

| Review | Finding | Rev 4 resolution and acceptance evidence |
|---|---|---|
| Codex P1 / Gemini P1 | Identity and identical-tree exception | Shared contract names the authenticated GitHub account and formal review, enrolled writer provenance, all bound fields, and exact-candidate-only reuse. S2 tests impersonation, same-tree changes, revocation and independent positive case. |
| Codex P1 / Gemini P1 | Resume, merge races and replay | One reviewed candidate and grant protocol in S2 and S1b. A new base or head returns to review. Required group check handles merge races; S1b tests durable recovery, fencing, and ambiguity holds. |
| Codex P1 | Actual blocking points | Guard table identifies staged and trusted required CI enforcement and the authoritative runtime or provider boundary. QA, events and ledgers provide evidence. Broader enforcement is dated and deferred. |
| Codex / Gemini follow-ups | Ordering, active contracts and sources | One dependency graph, switchboard schema/runtime distinction, and five verified backlog entries. The proposed adoption spikes retain their verification conditions. |
