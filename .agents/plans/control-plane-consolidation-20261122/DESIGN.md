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

Verified on origin/main at drafting time: `scripts/ai/aq-land:396` uses `author_lane`; the model-coordinator readers above exist; `config/schemas/agent-dispatch-envelope.schema.json`, `config/qa-provider-probe-contract.schema.json`, `config/agent-memory-surface-registry.json`, `config/system-state-authorities.yaml` and `scripts/governance/check-state-authorities.py` exist. NOT found on main: a `model-coordinator` schema (the contract for C1 must be written, see S3), and the four backlog ids (they live in the owner checkout's memory, not in the tree; S1 verifies them against the live backlog per the finding-freshness skill).

## Goals

1. Eight bounded contexts, each with one owner component, owned decisions, a published contract, named consumers and an enforcement check.
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

### Bounded contexts

| # | Context | Single owner | Owned decisions | Published contract (existing first) | Consumers | Enforcement |
|---|---|---|---|---|---|---|
| C1 | Model Access & Routing | switchboard + `config/model-coordinator.json`; one read module (`lib/model_tiering.py` grows into it) is the only reader | which model serves a request; tier map; route aliases; fallback order | `config/model-coordinator.json` + NEW `config/schemas/model-coordinator.schema.json` + route-decision event in the agent-run-events envelope | coordinator, `aq-role-route`, `delegate-to-*`, `aq-model-eval` call the module/HTTP route and never open the JSON | tier0 DO-1: only the owner module opens `model-coordinator.json` (current readers as bypasses with deadlines); contract test: schema validates the file; switchboard catalog checked against it |
| C2 | Work Dispatch & Delegation (includes lane availability/eligibility) | delegation registry + `lane-eligibility-registry.json`; `delegate-to-*` are thin executors | task assignment; lane up/down per MODEL, not per lane; eligibility; the Rule 6 retry budget | `agent-dispatch-envelope.schema.json` (exists) + `delegation-task-record.schema.json` (exists) + availability event keyed `(lane, model)` | `aq-role-route`, `aq-land`, loops, orchestrators | tier0 DO-4: availability is read through the availability API, not wrapper cooldown files; contract test: one model down leaves its siblings up |
| C3 | Review & Trust | `aq-review-receipt` | review disposition; reviewer independence; receipt minting | review record / receipt schema (`Review-Disposition`, `Reviewed-subject-sha256`, `Reviewed-by`, `Review-Receipt`) + NEW derived `authors[]` | `aq-land`, trunk protection, dashboard | contract test: reviewer lane not in the lanes of commit authors and `Co-Authored-By` trailers since the merge base; declared `Author-lane` advisory only; tier0 DO-5 |
| C4 | Integration / Landing | `aq-land` | every write to a PR branch; merge; the branch-mutation lock; landing record; "recreate" requests for Dependabot | landing record (`outcome_receipt.record_landing`) + branch-mutation lock record | orchestrators, Dependabot flow, lanes (they hand off, never push PR branches) | tier0 DO-2 (first check built): branch pushes, `gh pr merge`, `gh pr update-branch` only in `aq-land`, via the existing authority checker's writer signatures; one durable runner |
| C5 | Deploy & Activation | `aq-update` (`aq-deploy-current` becomes its stage) | when and how the system generation changes; lock refresh; pending-reboot; activation attestation | aq-update ledger schema (aq-update-unified U-slices) + Rule 15 activation record | owner, `aq-resume`, QA | tier0 DO-3 via `check-state-authorities.py --staged-regressions` (single-owner-guards R1): raw `nixos-rebuild`, `home-manager switch`, `nix flake update` outside the owner fail; `nrs/nrb/nrd/nrs-force` listed as bypasses with deadlines |
| C6 | Knowledge & Memory | AIDB + Qdrant behind ONE memory API (the coordinator `/api/memory/*` is the facade) | where a fact/lesson/embedding lives and how it is recalled; eviction | `config/agent-memory-surface-registry.json` (exists; made normative) | all agents, `aq-memory`, hints | contract test: every memory writer appears in the surface registry; tier0 DO-7: no direct Qdrant/AIDB client outside the facade (ratchet, shrink-only) |
| C7 | Observability & QA | ONE health pipeline (health-spider sample -> verdict) with ONE remediator | health verdict; what is remediated and by whom; alert routing | `qa-provider-probe-contract.schema.json` (exists) + NEW health sample/verdict schema | dashboard, `aq-alerts`, oncalld (consumer), `aq-qa`, `qa_check` | tier0 DO-6: one component executes remediation, the rest emit a remediation REQUEST event; contract test: one failure gives one attempt |
| C8 | Learning / Experience | continuous-learning + PRSI, with the experience-capture design as its data backbone | which outcomes become lessons, priors or proposals; weights; experiments | `learning-candidate.schema.json` (exists) + lesson/proposal schema extending `check-prsi-cycle-contract.sh` + experience events (`dispatch_id == run_id`) | routing hints (advisory), reports, dashboard | contract test: only `learning_eligible == true` feeds scoring (learning-attribution gate); other loops may not write lessons |
| C9 (optional) | Approval & Authority | identity-kernel, leases, epochs, attention queue | who may perform a reserved act; lease/epoch validity | `capability-lease.schema.json` (exists) + approval envelope | all privileged actors | already enforced piecemeal; recorded as `approval.*` registry rows, no new code in MVP |

Loops (ralph-wiggum, `aq-loop`, `aq-agent-loop`, autonomous-improvement, `aq-collab-round`) are NOT a context: they are consumers of C2 (dispatch), C3 (review) and C4 (landing). Their six retry/queue policies converge on C2's one retry budget (S8), not on an adopted framework.

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
| C5 Deploy | nh (EUPL-1.2, v4.5.0 2026-11-12, in nixpkgs with `programs.nh`, no CVEs found); deploy-rs v1.0.0, colmena v0.5.0, devenv | nh: adopt-partially, as the build/diff/dry-activate/GC engine UNDER `aq-update` (our guards, ledger and pinned rev stay). deploy-rs, colmena, devenv: keep ours | deploy-rs and colmena pay off only with remote SSH nodes; revisit if a second host appears. nh must first verify: privilege elevation vs our sudo-is-an-owner-act rule, dry-activate with our pre/post checks, EUPL-1.2 vs the public repo's licence posture (owner decision) |
| C1 Routing | LiteLLM (MIT core; compromised v1.107.0 release 2026-10-21; JWT/auth CVEs) | keep ours | Cannot drive headless Codex/Gemini/Claude CLI OAuth lanes without API keys; adds a master key and a DB. Changes if it gains first-class CLI-OAuth lanes and a signed-release record of 6+ months |
| C2 + loops | LangGraph (core MIT; `langgraph-api` Elastic-2.0, 2026 CVEs) | keep ours | Assumes API-key SDK clients; its value (durable graphs, interrupts) we partly have. Changes if a loop family needs checkpointed cyclic graphs we cannot express in the C2 retry budget; then adopt core only, behind the contract, retiring that loop |
| Agent runtime (overlaps C2/C6/C8) | OpenClaw (MIT, foundation-backed, very active; marked Insecure in nixpkgs; CVE-2026-25253, CVE-2026-62201; ClawHub "ToxicSkills" supply-chain incidents) | keep ours | Fails (a): reported Anthropic block on consumer OAuth reuse in third-party harnesses, Gemini PKCE risk; its monolithic overlap would force "run both". Changes if OAuth lanes are officially supported, the nixpkgs insecure flag clears and skills are sandboxed. Reuse ideas only (durable scheduling) |
| C3, C4, C6, C7, C8 | none evaluated | keep ours | Harness-specific trust semantics; evaluate when a concrete candidate is proposed via the `capability-intake` skill |

Verification still owed (treat all as unverified): Codex check of the CVE ids, the OpenClaw OAuth-block claim and the LiteLLM incident; direct fetch of the Anthropic posts (the research could not fetch raw pages); exact nixpkgs versions. The nh adoption is therefore only an owner decision (D2) after that check.
What would change the overall verdict: a failed verification of the OAuth blocks; a candidate that passes (a)-(d) and replaces a whole context with a net deletion of code; a second deployment host; a shift in the CVE/maintenance picture (re-run the fact sheets at the MVP boundary).

### Fold-ins (no duplicate plans)

| Existing plan / item | Becomes | Context |
|---|---|---|
| single-owner-guards R1 (privileged primitives on `system-state-authorities.yaml`) | core of S1 | registry + C4/C5 |
| single-owner-guards R2 (shim map), R3 (duplicate ratchet), R4 (zero-net canon + PRD template) | S9 | cross-cutting; the template gains this PRD's four sections |
| aq-update-unified U-slices (one `aq-update` front door; U0 flake-owned naming; U3/U4 deploy logic into `aq-update`; U7 identity ratchet; U8 deferred) | S5 | C5; nh evaluated inside U3 as the engine choice |
| experience-capture S1-S7 (S6b priors, S6c experiments) | S10 | C8, consuming C2 availability events |
| LANE-AVAILABILITY-NOT-PER-MODEL | S4 | C2 |
| AUTHOR-LANE-TAG-NOT-COMMIT-AUTHOR | S2 | C3 |
| LAND-RUNNER-NOT-DURABLE, DEPENDABOT-REBASE-NOOP-AFTER-FOREIGN-PUSH | S1b, S7 | C4 |
| EMBEDDER-STICKY-DEVICE-LOST (health-remediator overlap) | S6 | C7 |
| learning-attribution PRD gate | binding constraint of C8 | C8 |

### Past-work mapping

| Existing component | Context | Disposition |
|---|---|---|
| switchboard, `config/model-coordinator.json` | C1 | keep (owner) |
| coordinator, `aq-role-route`, `delegate-to-claude`, `aq-model-eval`, `gemini-model-guard.sh`, `brief_caps.py`, `sweep-lanes.py` | C1 | consumer (go through the owner module) |
| `model_tiering.py` | C1 | merge into the owner read module |
| `lane-eligibility-registry.json`, delegation registry, `delegate-to-*` | C2 | keep (owner + thin executors) |
| wrapper cooldown files | C2 | merge into the availability API |
| `aq-review-receipt` | C3 | keep (owner), derive authors from commits |
| `aq-land` | C4 | keep (owner) |
| two ad-hoc land runners | C4 | retire (replaced by the durable runner) |
| Dependabot, Gemini PR-branch writes | C4 | consumer: request landing or recreate via `aq-land` |
| `aq-update` | C5 | keep (owner) |
| `aq-deploy-current` | C5 | merge into `aq-update` as a stage |
| `nrs`, `nrb`, `nrd`, `nrs-force`, `system-update-full.sh` | C5 | retire to declared shims, archive (compressed) after parity |
| `aq-update-tiers`, `update-llama-cpp.sh` | C5 | consumer (refresh scopes of `aq-update`) |
| AIDB, Qdrant, coordinator memory API | C6 | keep; coordinator facade is the one API |
| `aq-memory`, agent memory files | C6 | consumer of the facade |
| health-spider sampler + verdict | C7 | keep (owner) |
| auto-remediate, gap-auto-remediate, health-spider fix pipeline, oncalld remediation | C7 | merge into ONE remediator (choice in S6 by measured behaviour); others emit requests |
| health-monitor, `aq-qa`, `qa_check`, `aq-alerts`, dashboard | C7 | consumers of the verdict |
| continuous_learning_daemon, PRSI | C8 | keep (owner) |
| meta-optimization, `aq-local-training-loop`, federated learning, lesson tools | C8 | merge or consumer, decided in S10 against the lesson schema |
| `aq-loop`, ralph-wiggum, `aq-agent-loop`, autonomous-improvement, `aq-collab-round` | consumers of C2/C3/C4 | converge retry and queue policy on C2; retire a loop only behind a parity test |
| identity-kernel, leases, epochs, attention queue | C9 | keep |

### Future-work rule
`.agent/templates/PRD.md` (created by single-owner-guards R4) gains four required sections: **Bounded context**, **Contract** (the schema or event touched or added, existing first), **Owner** (one component; a new owner only for a new decision, with its registry row), **Adopt-vs-build justification** (criteria (a)-(g) filled in for any new component, plus the "replace, never run both" retirement plan). Rule 8 review prompts (`aq-collab-round`, `aq-land`) gain the standing question "does this create a second owner for a decision in `decision-ownership.json`?" as code, not instruction lines. The PRD/tracker gate fails a new PRD missing the sections once the template ships (new PRDs only).

### Reviewer independence (recurring, so explicit)
Independence is derived, never declared: the receipt computes `authors` from commit author and `Co-Authored-By` trailers since the merge base, and the reviewer lane must not intersect them. Two orchestrators routing the same PRs is the stress case: COORDINATION.md claim rules stay in force, and a conflicting claim is settled by appending a HANDOFF line, never by acting.

## Slices (bounded, ordered; lane = most cost-effective correct, Rule 17, explicit model override)

| Slice | Scope | Lane suggestion | Validation | Rule 15 activation row |
|---|---|---|---|---|
| S0 | Freeze this PRD: independent scrutiny (failure modes, security, ownership-message UX), Codex verification of the research claims, owner decisions D1-D8 | Codex + Gemini reviewers (non-author); Qwen scaffold check queued | PLAN_READY[_WITH_FOLLOWUPS] recorded; verification results appended | n/a (plan) |
| S1 | `decision-ownership.json` + schema + `check-decision-ownership.py` with DO-2 on R1's authority checker; verify the backlog ids; land the three source PRD docs with it | Codex implementer (tests-first); sonnet override; Claude non-author reviewer | positive/negative/adversarial fixtures (renamed alias, second occurrence, staged vs worktree); today's tree passes | in tier0.d and ON in pre-commit; a real offending staged commit fails naming the owner; revert-intervenable; tracker live |
| S1b | `aq-land` durable runner (unit-backed, resumable) retiring the two ad-hoc runners; "recreate" request path replacing rebase-after-foreign-push | Codex; sonnet reviewer | kill the runner mid-landing and resume; foreign push then recreate on a real Dependabot PR | runner unit enabled (owner rebuild act, exact commands given); landing record observable |
| S2 | C3: derive authors in `aq-review-receipt` / `aq-land:396`; declared `Author-lane` advisory; DO-5 | Codex implementer; sonnet for the rule tests | tag says gemini but Claude committed: Claude cannot review; replay over the audited PR sample | live on the next real landing |
| S3 | C1: write the model-coordinator schema; one read module (merge `model_tiering.py`); migrate the four readers; DO-1 with readers as time-boxed bypasses | Codex for module and migration; Qwen only for decomposed single-file call-site edits | schema validates the live file; each reader's tests pass via the module; DO-1 fails a new direct read | coordinator rebuild/restart is an owner act (exact commands given) |
| S4 | C2: availability keyed `(lane, model)`, availability API replacing cooldown-file reads; `aq-role-route` and `aq-land` use it; DO-4 | Codex; sonnet reviewer | one model down leaves a sibling up (replays the Gemini incident); probe-one-other-model rule enforced in code | live in `aq-role-route`; availability event observable |
| S5 | C5: aq-update-unified U-slices in their frozen order (shims for `nrs/nrb/nrd`, `aq-deploy-current` as a stage, nh evaluation per D2); DO-3 | Codex implementer; owner acts for sudo/rebuild | that PRD's journeys; nh dry-run behind a flag first | rebuild is an owner act; ledger rows observable |
| S6 | C7: one remediator (chosen on EMBEDDER-STICKY-DEVICE-LOST behaviour), others emit requests; health sample/verdict schema; DO-6 | Codex; Qwen for the probe-contract test scaffold | one injected failure gives one remediation attempt and one verdict | service restart is an owner act |
| S7 | C4 completion: branch-mutation lock record; Gemini and Dependabot paths routed through `aq-land` | Codex | concurrent-mutation test: second writer blocked | live with S1b |
| S8 | Loop convergence: one retry budget (C2) consumed by the six loop families, one family per slice | sonnet per family (haiku only for mechanical single-file edits) | per-loop parity test before retiring any loop | per family |
| S9 | single-owner-guards R2/R3/R4 (shim map, duplicate ratchet, zero-net canon, PRD template with the four sections); canon parity across the 6 targets (Rule 16) | Codex + sonnet; `check-instruction-budget.sh` and the parity checker | zero-net-lines test; a PRD missing a section fails | template referenced from Rule 8's SSOT |
| S10 | C8: experience-capture S1-S6c, consuming C2 events; lesson/proposal schema; loops stop writing lessons directly | per that PRD (Codex implementers, sonnet for the weighting) | that PRD's journeys, real data | per that PRD |
| S11 | C6: memory facade as the only writer path, registry made normative, DO-7 ratchet | Codex | every writer in the registry; direct client use only shrinks | live on the write path |
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
- **Feature freeze (system-integrity-recovery P0+P1).** S1-S4 are integrity work; the rest waits for the freeze exit unless the owner decides otherwise (D7).

## Rollback
Each slice is one PR; revert it. The registry and tier0 check fail only on new regressions, so removing them restores today's behaviour. Moved readers and writers keep their old entry points as declared shims until parity is proven; nothing is deleted (Rule 12; archives compressed after parity).

## Owner decisions needed (recommended default first)
1. **Adopt this umbrella and fold the three PRDs in** (single-owner-guards, aq-update-unified, experience-capture become slice groups; no separate plans). Default: yes.
2. **nh as the engine under `aq-update` (adopt-partially)?** Default: evaluate in S5 behind a flag after Codex verifies the research, and decide on that evidence. Needs your call on EUPL-1.2 for a public repo and on sudo handling.
3. **Keep OpenClaw, LiteLLM, LangGraph, deploy-rs, colmena and devenv out for now?** Default: keep ours; re-run the fact sheets at the MVP boundary; reconsider deploy-rs/colmena if a second host appears.
4. **Registry home:** new `config/decision-ownership.json` referencing `system-state-authorities.yaml` rows (default) vs extending that YAML only. Default: the new file with a cross-check generator, because most decisions are not state writes.
5. **Independence rule:** derived from commit authors and `Co-Authored-By`; declared `Author-lane` advisory. Default: yes.
6. **One remediator:** which component keeps remediation (S6). Default: the health-spider fix pipeline, others emit requests, confirmed by measured behaviour.
7. **Feature freeze:** treat S1-S4 as integrity work permitted during the freeze. Default: yes; S5+ wait for the freeze exit unless you say otherwise.
8. **Orchestrator split for W7/W8:** Claude drafts and routes, Gemini co-reviews, Codex verifies the research claims (Rule 18 and independence). Default: as stated.
