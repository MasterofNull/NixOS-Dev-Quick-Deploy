# AQ-OS execution readiness queue

**Projection date:** 2026-07-27  
**Status:** ACTIVE EXECUTION PROJECTION — NOT AN AUTHORITY OR ACTIVATION  
**Governing architecture:** `../UNIFIED-PROGRAM-PLAN.md`  
**Status SSOT:** `config/refactor-milestones.json` through `aq-refactor-status`

This queue turns the ratified program into a dependency-ordered work supply
without creating another lifecycle authority. Source PRDs, reviewed design
packets, hash-bound authorizations, owner activation events, candidate evidence,
independent acceptance, and commits retain their existing precedence.

## State vocabulary

- `ACTIVE_AUTHORIZED`: exact authorization, HEAD, implementer, and UTC window are
  bound; implementation may run only inside its ceiling.
- `ACTIVATION_RECEIVED`: the owner explicitly approved the exact reviewed
  authorization and revision, but one or more dispatch bindings required by that
  authorization (implementer, UTC window, current-HEAD receipt, or preflight)
  are not yet recorded; implementation remains prohibited.
- `READY_FOR_PREPARATION`: bounded design/authorization preparation may begin;
  implementation is not authorized.
- `AWAITING_ACTIVATION`: design and authorization passed independent review but
  still require an exact owner activation.
- `BLOCKED_ON_ACCEPTANCE`: candidate work exists but cannot advance until an
  independent exact-subject verdict resolves it.
- `BLOCKED_ON_VALIDATION`: acceptance passed, but a required repository gate
  still fails for an explicitly recorded reason; no commit is permitted.
- `ACCEPTED_AWAITING_INTEGRATION`: exact candidate and independent acceptance
  passed; staging/commit still requires an isolated integration authority/gate.
- `DEPENDENCY_QUEUED`: intentionally ordered behind named upstream evidence.
- `ADVISORY_CATCHUP`: optional late input; never blocks active work.

`Queued` never means activated, running, accepted, committed, deployed, or live.

## Q0 — active, non-overlapping slices

| Order | Slice | State | Exact authority / assignment | Prerequisite and next action | Conflict domain | Eligible lane / reviewer | Monitoring and completion gate |
|---|---|---|---|---|---|---|---|
| 1 | Track S S0-A intake truth | `ACCEPTED_AWAITING_INTEGRATION` | AM1 exact candidate independently PASS: schema `d080957b…`, CLI `cdf59fc5…`, test `cd4aaebf…`; registry frozen `ab5d56ac…` | prepare a separate exact integration authorization after the sole staged C0.3 record is resolved; do not mix indices | capability-intake schema, CLI, and focused test; registry frozen | orchestrator integration only after independent PASS; implementer remains recused | preserve focused PASS and frozen-registry proof; isolated validation and one-slice commit required; no scanner/runtime/network action |
| 2 | C0.6-T telemetry correction | `AWAITING_ACTIVATION` | AM8 exact code candidate passed focused suites but independent review required two missing direct regression matrices; AM9 test-only revision `adf49603…` and auth `4a226775…` independently PASS | owner activates AM9 for one implementer/window; change only two test paths and stop on any production defect | two mutable tests; seven AM8 candidate paths frozen; excludes task_registry drift | economical bounded test implementer; independent flagship architecture/SRE reviewer | direct age-path and absolute-deadline matrices, frozen seven-path proof, external 02/15/16 disclosure, exact hashes and independent PASS; no Tier0/live/provider/network/stage/commit |
| 3 | C0.3 provenance reconciliation | `BLOCKED_ON_VALIDATION` | exact Stage-1 refs and record blob `205d4122…` independently PASS; commit gate reached QA but current progress-tracker check fails | restore tracker-test parity without touching the staged record; rerun the isolated commit gate | sole staged C0.3 record plus protected refs; all other staging is excluded | orchestrator owns the frozen index; independent flagship acceptance already PASS | visible QA `0.10.40` recovery and isolated Tier0 PASS; then exact one-file non-merge commit while HEAD/index/refs remain frozen |

No later queue item may overlap these inventories until its active implementer
publishes terminal evidence and the independent reviewer resolves the candidate.
Owner activation does not waive an authorization's identity, UTC-window, drift,
single-use, monitoring, or independent-acceptance conditions. S0-A AM1 is
accepted but cannot share the staged index; C0.6 AM8 is consumed/rejected and
only the separately reviewed AM9 test-only packet is eligible for a new owner
activation.

## Q1 — unblock and truth-repair queue

| Priority | Track / slice | Current state | Prerequisite | Next bounded preparation | Conflict domain | Eligible lane / reviewer | Monitoring and promotion gate |
|---|---|---|---|---|---|---|---|
| 1 | Local-Embed-Context Slice 2b | `READY_FOR_PREPARATION` | current bytes retain accepted `df4d94d9…` digest and the same acceptance record's later PASS | reconcile status/projection only; do not reapply the digest; isolate task_registry 02/15/16 as a separate reliability slice | LEC acceptance/status/tracker projections only | bounded documentation/status implementer; independent non-author reviewer for any changed acceptance claim | projector/dashboard must show the resolved truth; focused evidence and terminal receipt; no code-hook or manifest rewrite without a new authorization |
| 2 | Track V / Verified Factory | `READY_FOR_PREPARATION` | exact corrected VF `88e4051a…`, CK `8afcc7c4…`, Unified `2869e2c9…`, and frozen synthesis `67796d15…` independently PASS all ten criteria | prepare the first exact per-slice Track V activation package only; no broad Track V activation | named future slice inventory only; no runtime/check migration by this PASS | bounded role-selected implementer later; fresh independent flagship reviewer | exact activation/candidate hashes, monitoring/Service Coverage and independent PASS; Q9/model-neutral eligibility preserved |
| 3 | Progress tracker test parity | `AWAITING_ACTIVATION` | final projector-truth package independently PASS: manifest `b6117106…`, tracker `7aca33b7…`, design `9883ad9a…`, auth `9d3e4cf7…` | owner activates exact two-file test re-pin; keep C0.3 index read-only | tracker focused test plus only the Phase-0 program-progress check; C0.3 index is read-only | bounded test implementer after activation; independent flagship QA/reliability reviewer | 13/13 focused tests, source-hash reconciliation, dashboard Service Coverage, monitored receipt; then rerun C0.3 isolated Tier0 |
| 4 | Agent catch-up execution owner | `READY_FOR_PREPARATION` | C0/C0.5 contracts and broker ownership remain stable; no second lifecycle writer | prepare contract-only typed parked-task store, eligibility-triggered single-flight retry, receipts, expiry/backoff/dedup, aq-qa and dashboard design | broker lifecycle/catch-up contracts; no daemon/runtime adoption | architecture/SRE designer plus independent flagship concurrency/security reviewer | traceable parked/retry/terminal state, low-cardinality metrics, integration-path QA and dashboard contract before runtime activation |
| 5 | Sub-agent configuration parity C0 | `ACCEPTED_AWAITING_INTEGRATION` | native Codex C0 exact candidate independently PASS; effective config is repaired, root trust removed, child routing disabled, semantic/adversarial tests green | isolate and integrate the seven-file C0 candidate after C0.3 staging is resolved; separately prepare cross-provider C1 schema/model availability work | native `.codex` project/agent configs, Home Manager projection, focused tests; no external route cutover | orchestrator integration after independent PASS; external-lane C1 uses separate architect/reviewer | current hooks/multi_agent health, hostile transform fixture, role/sandbox/child-routing tests; C1 must add AQ dashboard/aq-qa lifecycle parity before external routing mutation |
| 6 | Foundation C2 lease enforcement | `AWAITING_ACTIVATION` | frozen pair `313b723b…` + `633926c…`, predecessor hashes, current HEAD, five-path non-overlap, and Q5 eligibility must reverify | prepare one current-HEAD single-use activation receipt; implementation remains flag-default-OFF | switchboard gate, lease gate library, test, decision schema, first-party tool registry | cheapest Q5-eligible implementer; independent flagship security/threat-model reviewer | monitored dispatch and per-admit audit evidence; focused parity/fail-closed tests, exact hashes, independent PASS; enabling the flag is a separate owner act |
| 7 | Antigravity and Claude Track S inputs | `ADVISORY_CATCHUP` | provider becomes eligible and a monitored inbox/parked task exists | consume the existing task only; convert actionable findings into a new bounded revision hash | review artifacts only; never the active implementation inventories | eligible reasoning lane; unavailable/timed-out lanes abstain and receive no review credit | broker/inbox receipt, expiry and terminal evidence; advisory output never activates or blocks unrelated work |

## Q2 — queued not-started program tracks

| Program order | Track | Queue state | Hard prerequisite | Next preparation slice | Conflict domain | Eligible lane / reviewer | Monitoring gate / no-activation boundary |
|---|---|---|---|---|---|---|---|
| 1 | Foundation B2 | `READY_FOR_PREPARATION` | accepted C1/M1 shadow evidence reconciled to shipping commits; active inventories disjoint; legacy remains authoritative | freeze one contract-only design for the next single workflow-run-task authority expansion/replacement | workflow-run-task state spine and evidence schema; no DDL/connect/write/cutover | migration/data architect plus bounded implementer later; independent flagship database/concurrency reviewer | shadow divergence, CAS/outbox/replay and SLO evidence must be dashboard-visible; preparation authorizes no database or runtime action |
| 2 | Foundation B3 | `READY_FOR_PREPARATION` | B1 contracts stable and shipped canon-compiler evidence reconciled to tracker truth | freeze one no-authority projector/dashboard shadow extension | canon compiler, projector schema, one dashboard surface | bounded projector implementer later; independent flagship contract/UI-observability reviewer | projector lag/error and contract health visible in aq-qa/dashboard; no runtime-authority write or activation |
| 3 | Foundation C3a | `DEPENDENCY_QUEUED` | C2 candidate accepted and committed flag-default-OFF | design pure write/secret/delegate/exec policy brokers plus deny-all network broker | effect-policy brokers and signed-A2A verify-before-write | security implementer later; independent flagship security/concurrency reviewer | every allow/deny/attenuation emits bounded audit evidence and Service Coverage; no live effect routing |
| 4 | Foundation C3b | `DEPENDENCY_QUEUED` | C3a contracts accepted; measured cell/bwrap feasibility | design lease-bound execution cells, snapshot/rollback executor, and allowed-output enforcement | bwrap cells/workspaces; no network-profile enablement | systems/security implementer later; independent flagship sandbox/SRE reviewer | cell lifecycle, escape/output rejection and rollback metrics visible; no deployment or live adoption |
| 5 | Foundation C4 | `DEPENDENCY_QUEUED` | dedicated threat pass ratifies eight connected-zero-trust profiles; C3 deny-all broker accepted | freeze network-profile evaluator and policy vectors | network broker/profile registry | network/security implementer later; independent flagship network threat-model reviewer | deny/allow/profile-drift telemetry and dashboard health; no connection policy cutover |
| 6 | Foundation C5 | `DEPENDENCY_QUEUED` | C3/C4 authoritative audit vocabulary stable | freeze OTel-span truth and audit/PULSE/matrix projection design | telemetry authority and projections | observability implementer later; independent flagship SRE/privacy reviewer | loss/cardinality/lag SLOs and dashboard coverage; no replacement of current evidence authority |
| 7 | Foundation C6 | `DEPENDENCY_QUEUED` | C2 epoch checks and C5 telemetry accepted; Product-D scheduler seam designed | freeze epoch-bump control and scheduler/F2.5 revocation seam | epoch control, scheduler cancellation/revocation | concurrency/security implementer later; independent flagship SRE/security reviewer | revocation latency, stale-lease rejection and scheduler drain evidence; no global epoch or scheduler activation |
| 8 | Product D | `DEPENDENCY_QUEUED` | B1 parity evidence and accepted C2 boundary; C6 seam coordinated | freeze D0 convergence design joining sole switchboard gateway, typed chat/batch divergences, F2.5 wiring, route/profile SSOT, and measured local hardware budgets | inference routing, scheduler/backpressure, local clients | MLOps/async implementer later; independent flagship architecture/performance reviewer | route parity, queue/backpressure, timeout, hardware and SLO telemetry in aq-qa/dashboard; no traffic cutover |
| 9 | Product E | `DEPENDENCY_QUEUED` | B2 evidence store and Foundation C integrity accepted | freeze E0 registry/promotion contract for datasets, scorers, prompts, sealed answers, replay, and model admission | eval/promotion authority | evaluation implementer later; independent flagship ML-eval/security reviewer | reproducibility, leakage, scorer certification and promotion ledger health visible; no promotion gate activation |
| 10 | Product F | `DEPENDENCY_QUEUED` | authoritative C/D telemetry and broker lifecycle accepted | freeze F0 typed `aq` gateway/command-center contract with compatibility shims and OTel/SLO views | CLI/API/dashboard surfaces | CLI/frontend implementers later in disjoint sub-slices; independent flagship architecture/UX/SRE reviewer | every command/service has integration-path aq-qa plus dashboard status; no shim retirement or gateway cutover |
| 11 | Product G | `DEPENDENCY_QUEUED` | accepted D–F evidence and two clean operating cycles | freeze G0 release-evidence, hardware-profile, restore/upgrade-drill, semver and retirement contract | deployment/release/legacy retirement | release/systems implementer later; independent flagship release/security reviewer | drill, restore, upgrade, compatibility and rollback evidence visible; no deployment, retirement, or release activation |

## Q3 — Track S continuation

| Order | Slice | State | Prerequisite | Next preparation slice | Conflict domain | Eligible lane / reviewer | Monitoring gate / no-activation boundary |
|---|---|---|---|---|---|---|---|
| 1 | S0-B typed scope/finding/evidence/disclosure contracts | `DEPENDENCY_QUEUED` | S0-A AM1 accepted and committed | freeze closed schemas, authority fields, custody/digest semantics, retention, and disclosure states | security evidence contracts only | security/schema designer; independent flagship security/legal-process reviewer | contract-health aq-qa/dashboard indicator; no scanner/tool/runtime adoption |
| 2 | S1 passive normalization | `DEPENDENCY_QUEUED` | S0-B accepted | freeze passive scanner adapters, normalized findings, dedup/severity policy, and Service Coverage audit | read-only repo/package evidence | bounded security implementer later; independent flagship AppSec/SRE reviewer | scanner freshness, coverage, false-positive and failure telemetry; no active probing |
| 3 | S2 owned-target active-validation guard | `DEPENDENCY_QUEUED` | S1 accepted; signed owned-target scope and disposable lab design | freeze deny-by-default target attestation, rate/budget, isolation, kill switch, and evidence vectors | disposable owned lab only | security systems implementer later; independent flagship threat-model/release reviewer | target identity, budget, trip, abort and evidence-custody signals visible; no external or production target access |
| 4 | S3 canaries/tripwires/containment | `DEPENDENCY_QUEUED` | S2 guard accepted and separately activated in the lab | freeze owned canary/honeypot, tripwire, containment and custody design | owned defensive sensors; no counter-action | defensive security implementer later; independent flagship incident-response/privacy reviewer | alert delivery, containment latency, evidence integrity and false-positive metrics; no hack-back, Trojan, deanonymization, or third-party access |
| 5 | S4 remediation/feedback | `DEPENDENCY_QUEUED` | accepted S1/S2 findings and S3 evidence path | freeze risk prioritization, fix verification, regression and reviewed recursive-feedback contract | local remediation and policy/prompt shadow evaluation | bounded maintainers/implementers; independent flagship security/eval reviewer | finding-to-fix age, regression, reopen and promotion metrics; raw model output cannot mutate policy/prompts |
| 6 | S5 disclosure/bounty | `DEPENDENCY_QUEUED` | S4 fix/hardening/validation complete; disclosure authority and maintainer channel identified | freeze owner-approved coordinated-disclosure package and optional bounty evidence workflow | external communication and claims | human owner/submission authority with security writer; independent flagship factual/privacy review | custody/redaction/timeline and submission receipts; every external submission and bounty claim requires a separate owner act |

Piyaz remains a cross-track pattern source for A2A collaboration, human-readable
tracking, and vector/RAG/DAG maintenance. Sn1per remains no-runtime quarantined;
RAPTOR remains source-audit-required. No queue state authorizes cloning,
installation, target scanning, hack-back, external submission, or bounty claims.

## Scheduler rules

1. Admit only a slice whose exact inventory is disjoint from all
   `ACTIVE_AUTHORIZED` inventories.
2. Prefer the cheapest currently eligible implementer; require an independent
   higher-reasoning review for security, authority, migration, release, or
   acceptance boundaries.
3. A timeout, quota limit, missing output contract, or provider failure parks or
   abstains; it never fabricates completion and never blocks unrelated work.
4. Every implementation must ship integration-path `aq-qa`, dashboard
   visibility, and the code/config change together, unless a reviewed
   contract-only slice explicitly defers Service Coverage.
5. Promote exactly one state at a time:
   `prepared -> reviewed -> activated -> candidate -> accepted -> committed`.
6. Update `config/refactor-milestones.json`, the human tracker, PULSE/RESUME, issue
   backlog, and handoff evidence at every terminal transition.
