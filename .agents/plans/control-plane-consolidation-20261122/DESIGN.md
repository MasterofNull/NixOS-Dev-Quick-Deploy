# PRD: Control-plane consolidation (bounded contexts, contracts, single-owner guards, adopt-vs-build)

Status: DRAFT rev 3 (2026-11-23), revised after S0 review round r1 (Codex REVISE, Gemini REVISE; local Qwen pending). Not frozen. No code in this slice. Author lane: claude (architect); reviewers must be non-claude lanes.
Tracker: `tracker.json` in this directory.
Review record: `.agents/plans/control-plane-consolidation-r1/` (`codex.md`, `gemini.md`, `README.md`). Every finding is mapped in section "Review r1 disposition".
Origin: owner-trusted external review of 2026-11-22 (`.agents/delegation/outputs/external-review-20261122/INPUT.md`) plus the owner ask "how do we best incorporate this feedback into our designs, implementation, past and future work". Inputs: `CENSUS-summary.md`, `codex-critique.md`, `gemini-synthesis.md`, `adopt-vs-build-20261122-gemini.md`, `COORDINATION.md`.
Umbrella over (no duplicate plans): single-owner-guards-20261119, aq-update-unified-20261119, agent-work-durability-20261119 (already designed; reused, not re-specified), and experience-capture-20261119 (NOT frozen: it carries two open REVISE verdicts and is not bundled as frozen; see S10). single-owner-guards and aq-update-unified live only in worktrees and are not on main; S1 lands them with the first code.

## Problem

The reviewer said the number of control planes is high and that overlapping responsibilities make it hard to say which component owns a decision. The census confirms it: about 30 components decide things, and nine decisions have more than one owner.

| # | Decision | Owners today (evidence) | Cost observed 2026-11-19..22 |
|---|---|---|---|
| 1 | Model routing | `config/model-coordinator.json` is opened by the coordinator, `aq-role-route`, `delegate-to-claude` (and referenced by `aq-model-eval`, `lib/gemini-model-guard.sh`, `lib/brief_caps.py`, `governance/sweep-lanes.py`; the S3 inventory separates opens from mere references). `lib/model_tiering.py` defines `MODEL_COORDINATOR` but does NOT read it: it hardcodes `_LANE_MODEL_KEYS` and `_CLAUDE_MODEL_FOR_COMPLEXITY` (`:28,38-49`), as does `aq-role-route:84-105`. The switchboard keeps its own profile catalog (`ai-stack/switchboard/switchboard.py:461`) | Parallel sources of model identity; a config edit has no single consumer to test |
| 2 | Lane availability and eligibility | wrapper cooldown files, `lane-eligibility-registry.json`, `aq-role-route`, `aq-land` reviewer choice each decide separately | Backlog LANE-AVAILABILITY-NOT-PER-MODEL: a cooldown on one model marked the whole lane down |
| 3 | PR branch mutation | `aq-land`, two ad-hoc land runners, Dependabot, Gemini all write PR branches | Five mutators. LAND-RUNNER-NOT-DURABLE; DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH (Dependabot refuses a rebase once anyone else pushed) |
| 4 | Review independence | `aq-land:396-403` and `aq-review-receipt:118,181` compare the declared `Author-lane`; receipt validation also accepts an earlier head after a clean main-only merge (`aq-land:386-413`) | Backlog AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR: the tag can say "gemini" while Claude wrote the commits; related to the fabricated-review-claims audit (about 85 PRs, 48 self-acceptances) |
| 5 | Health, QA and remediation | health-spider, health-monitor, `aq-qa`, coordinator `qa_check`, oncalld, `aq-alerts`, dashboard; four also remediate: auto-remediate, gap-auto-remediate, the health-spider fix pipeline, oncalld | Backlog EMBEDDER-STICKY-DEVICE-LOST: two remediators can act on one failure |
| 6 | Loops | `aq-loop`, ralph-wiggum, `aq-agent-loop`, autonomous-improvement, PRSI, `aq-collab-round`: six queues and retry policies | Rule 6 retry budget enforced six ways |
| 7 | Deploy | `aq-update`, `aq-deploy-current`, `nrs`/`nrb`/`nrd` (no guards), `system-update-full.sh`, `aq-update-tiers` | Nine entry points; a rebuild nearly ran on a 6-day-stale lock |
| 8 | Memory | coordinator store/recall, `aq-memory`, AIDB, Qdrant, agent memory files | Writers without one API |
| 9 | Learning | `continuous_learning_daemon`, meta-optimization, `aq-local-training-loop`, federated learning, lesson tools | No single lesson/proposal schema |

Root cause (Rule 19): ownership lives in prose and per-PRD lists. `config/system-state-authorities.yaml` already records one authority per state, but all ten rows are `SPLIT_BRAIN` with expired resolution deadlines (all dated 2026-10-09), and its checker does not yet fail on a NEW competing writer. The remedy (bounded contexts plus contracts) is right; the missing half is enforcement on the registry we already have.

Verified at drafting time (primary sources, see the claim table): the ten ledger rows; `aq-land:396`; the dispatch envelope, QA probe schema, memory registry and state-authorities checker exist. Not found: any file at the schema path `config/model-coordinator.json:7` points to (`./schemas/model-coordinator-schema.json`, a dangling reference); the backlog ids are not in the tree (S1 checks them against the live backlog).

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
| A2 | Dispatch, delegation, availability | delegation registry + `lane-eligibility-registry.json`; `delegate-*` are thin executors | `agent-dispatch-envelope.schema.json` (active, includes `gemini`) + availability event keyed `(lane, model)` | `delegation-task-record.schema.json` is INACTIVE (M2B not authorized, lane enum lists `antigravity`, omits `gemini`): NOT used as a contract unless S4 includes its authorization and enum update. All 27 grants in `lane-eligibility-registry.json` expire 2026-11-26: renewal is a pre-S1 owner act |
| A3 | Review and trust | `aq-review-receipt` | review receipt schema-2 (exact head + tree, reviewer lane); v3 adds authenticated reviewer identity and candidate binding | existing schema-2 receipts stay verifiable (backward compatible) |
| A4 | Integration / landing | `aq-land` | landing record + branch-mutation lock; the durable runner is `aq-land-runner.service` from agent-work-durability (no second runner) | |
| A5 | Deploy | `aq-update` (`aq-deploy-current` becomes its stage) | aq-update ledger (aq-update-unified) | |
| A6 | Memory | MemoryBroker; coordinator memory API is the facade | `config/agent-memory-surface-registry.json` (made normative) | |
| A7 | Observability and QA | one health pipeline, one remediator (provisional, see D8) | `qa-provider-probe-contract.schema.json` + NEW health sample/verdict schema | the probe schema omits `gemini` (`:13`); S6 adds it |
| A8 | Learning | continuous-learning + PRSI | `learning-candidate.schema.json` + lesson/proposal schema | depends on the experience-capture revision (S10) |
| A9 | Approval and authority | coordinator approval store (operator grants); identity-kernel | approval envelope + `capability-lease.schema.json` | the lease schema is report-only: no evaluator or executor consumes it yet, so A9 enforcement is NOT claimed in MVP; grants are consumed by `aq-land` admission (S2) |

Loops (ralph-wiggum, `aq-loop`, `aq-agent-loop`, autonomous-improvement, `aq-collab-round`) are consumers of A2/A3/A4, not a context; their retry policies converge on A2's budget (S8).

### Single-owner enforcement: extend the existing registry, no second one
Withdrawn from rev 2: `config/decision-ownership.json`, `check-decision-ownership.py` and the cross-check generator. Reason (Gemini P0-2, Codex P1-3): they would duplicate `config/system-state-authorities.yaml` (10 rows, ceiling 128) and contradict single-owner-guards, which forbids a new registry. The withdrawn O1 reference (capability-catalog `concern/role/shim_of`) is also dropped: entry-point shims live in `config/entry-point-shims.yaml` (single-owner-guards R2).

Mechanism (S1): `check-state-authorities.py --staged-regressions` (single-owner-guards R1 mode) is extended, with additive optional schema fields in `config/schemas/system-state-authorities.schema.json` (the same precedent as single-owner-guards Revision 3), by a per-row `guards[]` list: `{id, protected_operation, detection_scope, negative_fixture, approved_bypasses[{rule_id, path, operation_fingerprint, occurrence_count, deadline, reason}], live_control}`. A decision that has no state row gets a row (the ceiling allows it), not a new file. Each guard row references a stable decision id (`DO-n` below) so a PRD can cite it. Rules common to all guards:
- Baseline bypasses are keyed by rule id, path, normalized operation fingerprint and occurrence count; a copied violation in the same file is a NEW occurrence and fails.
- The baseline is read from `origin/main`, not the working copy; growth requires a recorded reason.
- Incomplete scans and files outside `detection_scope` fail closed (uncovered enforcement scope fails).
- Bypass deadlines are tracked: WARN in `--pre-commit`, HARD in scheduled `--maintenance` (Rule 19 time rule).
- tier0 is paired with a runtime or branch control wherever an external actor can write (see `live_control`).
- Dynamic command strings (`$cmd`, `eval`) are out of static scope and are covered by the `live_control`, never silently passed.
- Service Coverage: every guard is registered in the existing QA `phase0.py` surface and shows on the dashboard; no new reporter.
- Rollback is a PR revert (tier0 has no kill switch).

| Id | Protected operation | Owner | Detection scope | Negative test | Baseline and deadline (before freeze) | Live control |
|---|---|---|---|---|---|---|
| DO-1 | Reading `config/model-coordinator.json` or hardcoding model/lane keys that duplicate it | coordinator route-policy module (K2) | opens of that path and literal model-key dicts in `scripts/**`, `ai-stack/**`; contract test checks every consumer's model and lane keys against the config (this also catches the `model_tiering.py` and `aq-role-route` dicts) | new direct open fails; a dict key absent from the config fails | S3 inventory lists current opens (separated from references) and hardcoded dicts as bypasses; deadline = S3 exit | route-resolved event carries the plan id; caller receipt verified in S3 |
| DO-2 | Merge to protected branches; update-branch, rebase or force-push of a branch the pusher does not own | `aq-land` (admission); authors keep their own topic branches | `git push` of non-owned branches, `git push` to protected refs, `gh pr merge`, `gh pr update-branch`, "@dependabot" rebase requests; EXEMPT: author topic-branch pushes and `aq-review-receipt`'s `review-receipts` orphan-branch push (`aq-review-receipt:262`) | a second writer to another lane's PR branch fails; an exempt push in a renamed alias is still classified by identity | current ad-hoc runners and Gemini/Dependabot paths as bypasses; deadline = S7 exit | GitHub branch protection (required receipt check) plus the `aq-land` branch-mutation lock |
| DO-3 | `nixos-rebuild switch|boot|test|dry-build`, `home-manager switch`, `nix flake update` | `aq-update` | single-owner-guards R1 signatures (sudo, absolute path, continuation) | new alias or script invoking them fails | `nrs`, `nrb`, `nrd`, `nrs-force`, `hms`, `system-update-full.sh`, `aq-deploy-current` by exact identity; deadline = aq-update-unified U3/U4 (S5) | aq-update ledger rows |
| DO-4 | Reading wrapper cooldown or availability files directly | A2 availability API | reads of the cooldown directory in `scripts/**`, `ai-stack/**` | direct read fails; contract test: one model down leaves its sibling up | current wrapper readers; deadline = S4 exit | availability event observable; probe-one-other-model rule enforced in `aq-role-route` |
| DO-5 | Admitting a change without an independent, bound review | `aq-review-receipt` (verdict) + `aq-land` (admission) | RUNTIME admission check (fail-closed), plus tier0 fixtures for the check's logic; not a static grep | tag says gemini but claude wrote the commits; human-only author with no lane trailer; stale head after a clean merge; unknown provenance: all refused | none: new, fail-closed from day one; legacy schema-2 receipts remain verifiable | `aq-land` refusal event in QA and dashboard; branch protection requires the receipt check |
| DO-6 | Executing a remediation action | the designated remediator (provisional, D8) | service restarts and fix-pipeline invocations outside it | a second component executing a remediation fails; one injected failure yields one attempt | four current remediators as bypasses; deadline = S6 exit | remediation request/attempt events |
| DO-7 | Writing Qdrant/AIDB outside the memory facade | MemoryBroker facade (A6) | direct client constructors and HTTP writes | a new direct client fails | current direct writers counted; ratchet only shrinks; deadline = S11 exit | surface-registry check |

### Independence and approval (bound to identity and candidate)
Git author metadata and the `Author-lane` tag are self-asserted, so they are never sufficient. The admission rule (S2, DO-5):
1. **Author set** = union of the declared `Author-lane`, lanes named in `Co-Authored-By` trailers, and commit author identities across ALL commits introduced since the merge base. A commit whose provenance cannot be attributed to a lane (for example a human-only git author with no lane trailer) is treated as unknown: it is unioned with the declared lane, never counted as an empty set, and an unknown set needs adjudication or is denied.
2. **Reviewer identity** is authenticated: the receipt is minted by `aq-review-receipt` under the reviewer lane's own session and bound to the exact head SHA and tree of the admitted candidate (S2 documents exactly what authenticates the minting step before the check is called enforced; until then the claim is "bound", not "authenticated").
3. **Independence holds** only if the authenticated reviewer lane is not in the author set. A change to the candidate after review, including the clean-merge path that today accepts an earlier head, requires re-review unless a defined equivalence check (identical tree) covers the new candidate.
4. **Approval** is a separately scoped, expiring operator grant consumed once with replay protection; if admission fails mid-operation the grant is not consumed until the admission commit succeeds (idempotency key), and the recovery path re-runs admission without a new grant.
5. S2 changes BOTH `aq-land:396` and `aq-review-receipt:118,181`.

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
| `lib/model_tiering.py` reads `config/model-coordinator.json` | REFUTED | `model_tiering.py:28,38-49` defines the constant unused and hardcodes model keys (Gemini r1) |
| Switchboard profile catalog at `switchboard.py:461` | VERIFIED, path corrected | `ai-stack/switchboard/switchboard.py:461`; the ledger row still cites a stale `ai-stack/mcp-servers/...` path (S1 fixes it) |
| No model-coordinator schema exists | VERIFIED, with naming catch | `model-coordinator.json:7` references `./schemas/model-coordinator-schema.json` (hyphen), which does not exist |
| Capability catalog `concern/role/shim_of` (O1) is the entry-point registry | REFUTED | single-owner-guards withdrew O1; R2 uses `config/entry-point-shims.yaml` |
| `delegation-task-record.schema.json` is an active contract | REFUTED | schema marks itself INACTIVE (M2B not authorized); enum omits `gemini` |
| `capability-lease.schema.json` is enforced piecemeal | REFUTED (overstated) | report-only; no evaluator consumes it |
| `qa-provider-probe-contract.schema.json` covers all lanes | REFUTED | `:13` omits `gemini` |
| OpenClaw or LiteLLM cannot use Claude/Codex subscription workflows (blanket) | REFUTED as a blanket claim; eligibility for THIS harness UNVERIFIED | upstream docs (Codex r1): OpenClaw documents Claude CLI and multiple auth modes; LiteLLM documents Claude Code subscription support and Codex support from 1.109.0. Whether provider terms, headless configuration and containment fit this harness is untested |
| Anthropic blocks consumer Claude OAuth in OpenClaw | UNVERIFIED, contested | Gemini says banned; no primary Anthropic terms source cited yet |
| LiteLLM compromised release | VERIFIED for 1.107.0 on PyPI (advisory record); Docker details UNVERIFIED | GHSA-92x9-889m-jgmw (Codex r1) |
| OpenClaw CVE-2026-25253 and CVE-2026-62201 | VERIFIED as public records; exact candidate pins UNVERIFIED | NVD and CISA bulletin (Codex r1) |
| LangGraph CVE-2026-55235 and -55236 concern `langgraph-api`; core has no intrinsic provider-key requirement | VERIFIED scoped by package; checkpoint advisories (e.g. CVE-2026-71433) evaluated only if a checkpointer is chosen | cve.org records; LangGraph Graph API docs (Codex r1) |
| nh v4.5.0, EUPL-1.2, no CVEs; deploy-rs v1.0.0; colmena v0.5.0; devenv v2.4.0; 90-day commit counts; nixpkgs versions | UNVERIFIED (Gemini search snippets) | stays so until a non-Gemini lane checks the upstream sources; absence-of-CVE claims are never VERIFIED by absence |
| Parity of any candidate with session-only CLIs, no stored API keys, AppArmor + bubblewrap, independent reviewer lanes, declarative activation and llama.cpp on 4 GB / 27 GB | UNVERIFIED (untested) | reason every adoption is a bounded spike |
| Backlog incident ids (five) | UNVERIFIED | not in the tree; S1 checks the live backlog |

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
Then, after the freeze exits: S5 -> S6 -> S7 -> S11 -> S8 -> S9 and S10 (S10 only after experience-capture's REVISE verdicts are resolved; S9 may run earlier as cheap guards-only work if the owner asks).

Reasoning: the incidents of 2026-11-19..22 are in review, landing, availability and routing, not deploy; aq-update-unified is already frozen, has its own order (`U0 -> U1 -> U3 -> U2 -> U4 -> U5 -> U6`, early U7 gate, U8 deferred) and is not needed by the MVP guards. Codex's note listed aq-update-unified second; this PRD deliberately places it after the MVP because of the feature freeze, and D9 asks the owner to confirm or reorder. S2 precedes S1b so the trust gate is live before the runner relies on it; S4 precedes S3 because K2 consumes K1's availability event.

## Slices (one author lane and one disjoint reviewer lane each, Rule 17/18; explicit model override on every dispatch)

Lane notes: author = cheapest measured eligible lane. Local Qwen takes bounded single-edit inventory and fixture work where measured capable and is NEVER trust-critical (`lane-eligibility-registry.json` grants it no reviewer eligibility; its catch-up input is advisory/architect, not a review verdict). Codex implements when capability requires. Reviewer lanes are claude or gemini for Codex-authored work and codex or gemini for claude-authored work; the same lane never authors and reviews one slice. Where the cheaper lane is unavailable, the substitution is recorded (Rule 18).

| Slice | Scope and dependency | Author / reviewer | Measurable exit and validation | Rule 15 activation row |
|---|---|---|---|---|
| S0 | Freeze this PRD: contracts, journeys, owner decisions D1-D10; Codex checks the open claim rows; local Qwen advisory review (placeholder, pending) | claude (author) / codex + gemini | PLAN_READY recorded; claim table has no row left without a source or an explicit UNVERIFIED reason | n/a |
| S1 | Land single-owner-guards R1 on the existing checker; inventory existing writers; baseline (rule id, path, fingerprint, count); DO-2 and DO-3 live; fix the stale switchboard path in the ledger; verify backlog ids; create the external-review disposition; land the single-owner-guards and aq-update-unified PRD docs | local for bounded inventory and fixtures, codex for the checker / gemini | fixtures positive, negative, adversarial (renamed alias, copied occurrence, staged vs worktree, exempt paths); today's tree passes; a real offending staged commit fails naming the owner | in tier0.d and phase0, ON; dashboard shows guard state; revert-intervenable; tracker live |
| S2 | DO-5: authors from all introduced commits, authenticated reviewer identity, candidate binding, grant consumption; change `aq-land:396` AND `aq-review-receipt:118,181`; depends on S1 | codex / gemini | negative suite (tag/author mismatch, human-only author, stale head after clean merge, unknown provenance, replayed grant, mid-operation failure); replay over the audited PR sample; schema-2 receipts still verify | live on the next real landing; refusal event in QA and dashboard; branch protection requires the receipt check |
| S1b | Verify and wire `aq-land-runner.service` from agent-work-durability (no second runner unit) and the Dependabot "recreate" request path; retire the two ad-hoc runners; depends on S2 | codex / claude | kill the runner mid-landing and it resumes; one protected landing per reviewed revision; foreign push then a recreate request on a real Dependabot PR | unit enabled (owner rebuild act, exact commands given); landing record observable |
| S4 | A2: availability keyed `(lane, model)` through an availability API; `aq-role-route` and `aq-land` use it; DO-4; if `delegation-task-record` is wanted, its M2B authorization and enum update are explicit scope here; depends on S1 | codex / gemini | one model down leaves its sibling up (replays the Gemini incident); probe-one-other-model rule enforced in code; parity shown and the old cooldown reads retired | live in `aq-role-route`; availability event visible in QA |
| S3 | A1: `config/schemas/model-coordinator-schema.json`, `ResolvedRunPlan` v1 and execution receipt, route-policy module; migrate readers and the hardcoded dicts; DO-1; depends on S4 | codex (local for single-file call-site edits) / claude | a real caller goes through resolved routing and its execution receipt is verified BEFORE old readers are fenced; contract test over all consumer keys | coordinator/switchboard restart is an owner act (exact commands given) |
| S12 | MVP exit audit (mvp-delivery-sop): independent code and runtime review on the exact subject, adversarial pass, re-run of the fact sheets | independent lanes, not the authors | frozen journeys J1-J5 pass on real dependencies | MVP declaration needs its own evidence and an owner grant |
| S5 | aq-update-unified in its frozen order (U0 -> U1 -> U3 -> U2 -> U4 -> U5 -> U6, early U7, U8 deferred); nh behind a flag with the sunset in "Adopt-vs-build"; DO-3 allowances removed at U3/U4; after MVP | codex / gemini; owner acts for sudo and rebuild | that PRD's journeys; the nh flag either cut over or removed within its window | rebuild is an owner act; ledger rows observable |
| S6 | A7: one remediator (provisional, chosen on measured EMBEDDER-STICKY-DEVICE-LOST behaviour), health sample/verdict schema, add `gemini` to the probe schema; DO-6 | codex (local for test scaffold) / claude | one injected failure gives one attempt and one verdict | service restart is an owner act |
| S7 | A4: branch-mutation lock, Gemini and Dependabot paths through `aq-land`; DO-2 bypass removal | codex / gemini | concurrent-mutation test: second writer blocked; branch protection check | live with S1b |
| S11 | A6: memory facade as the only write path; surface registry normative; DO-7 | codex / claude | every writer registered; direct writers only shrink | live on the write path |
| S8 | Loop convergence: one retry budget (A2) across the six loop families, one family per slice, parity test before retiring any loop | local or codex per family / gemini | per-loop parity | per family |
| S9 | single-owner-guards R2/R3/R4 (shim map, duplicate ratchet, zero-net canon, PRD template with the three-line header) and canon parity across the six targets (Rule 16) | codex / gemini | zero-net-lines test; a new PRD missing the header fails | template referenced from Rule 8's SSOT |
| S10 | A8: experience-capture, ONLY after its two open REVISE verdicts are resolved and it is re-reviewed; lesson/proposal schema; loops stop writing lessons directly | per that PRD / independent | that PRD's journeys, real data | per that PRD |

## MVP freeze proposal
MVP = S0, S1, S2, S1b, S4, S3, S12 in that order (the order above). Declared only when frozen journeys pass on real dependencies: J1 a staged non-owner write to another lane's PR branch fails naming `aq-land`; J2 a claude-authored commit under a "gemini" tag (and a human-only-author commit) cannot be reviewed by claude and is refused; J3 a down model does not take down its sibling; J4 a real model-coordinator edit reaches all consumers through the route-policy module and its receipt; J5 a killed landing run resumes. S5-S11 are follow-on slices, not part of the MVP claim.

## Risks
- Big-bang migration: regression-only checks, dated exceptions, one aggregate per slice, parity before retirement.
- Contract churn: ACTIVE schemas only, additive changes, versioned contracts, contract tests.
- Registry drift: eliminated by not creating a second registry.
- Check false positives: documented syntax, fixtures for comments and echo text, exempt-path list in DO-2.
- Self-asserted identity: independence is not claimed "authenticated" until S2 documents what authenticates minting.
- Lane eligibility grants expire 2026-11-26 (owner renewal before S1).
- Unverified research: adoption stays a bounded spike with a sunset.
- Local lane unavailable or untrusted for gates: recorded; Qwen input is advisory.
- Feature freeze: only integrity slices run before the freeze exit.

## Rollback
Each slice is one PR; revert it. Guards fail only on new regressions, so removing them restores today's behaviour. Moved readers and writers keep their old entry points as declared shims until parity is proven; nothing is deleted (Rule 12; compressed archives after parity). For any later replacement the incumbent writer is fenced before cutover and the reverse handoff is tested.

## Owner decisions (recommended default first; Gemini GO/NO-GO list merged, duplicates removed)
1. Adopt this umbrella and the five-context map (K1-K5, aggregates A1-A9); fold the three PRDs in, with experience-capture held until revised. Default: GO.
2. Bounded `nh` spike inside `aq-update` (S5) with the flag sunset above. Default: GO after the nh claim rows are VERIFIED by a non-Gemini lane. Licence note: invoking the unmodified nixpkgs `nh` binary differs from linking or modifying EUPL-1.2 code; confirm this reading and the sudo handling.
3. LangGraph: DEFER unless a replay or interrupt gap is demonstrated; core only.
4. OpenClaw, LiteLLM, devenv, deploy-rs, colmena: confirm KEEP-CUSTOM for the MVP; revisit deploy-rs vs colmena only for a real U8 remote requirement; re-run fact sheets at S12.
5. Intake convention: disposition Markdown + `aq-collab-round` link + three-line PRD header, no new service. Default: GO.
6. Registry home: extend `config/system-state-authorities.yaml` and its checker (default, changed from rev 2); no `decision-ownership.json`.
7. Independence rule: authors from all introduced commits plus trailers plus declared lane (unknown = adjudicate or deny), authenticated reviewer identity bound to the admitted candidate, expiring replay-protected grant. Default: yes.
8. Single remediator: PROVISIONAL default is the health-spider fix pipeline; the final pick is made in S6 from measured behaviour, not frozen here.
9. Execution order: MVP (S0, S1, S2, S1b, S4, S3, S12) first under the feature freeze, S5 aq-update-unified after the freeze exit. Owner may instead pull S5 earlier (Codex's sequencing note); default as written.
10. Orchestrator split and claim checks: claude drafts and routes, codex and gemini review, a non-Gemini lane verifies the Gemini-sourced claim rows; local Qwen advisory only. Default: as stated.

## Review r1 disposition

Review r1: Codex REVISE (5 findings, numbered C1-C5; claim table C-claims) and Gemini REVISE (9 findings, numbered G1-G9). Local Qwen review: PENDING (placeholder; its findings, when they land, are mapped here before freeze).

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
