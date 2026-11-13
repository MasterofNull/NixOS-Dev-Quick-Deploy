# Software factory SOTA comparison

Research snapshot: **2026-11-12 UTC**. Design state: **DRAFT — pending independent design review**. This compares collaborative software delivery systems and enabling runtimes, not model scores. Our design synthesis favors a controlled lifecycle: versioned work, isolated execution, explicit recovery, independent review and observable operator-controlled activation. Public sources document pieces of that lifecycle; this review establishes neither a universal winner nor complete local parity.

## Evidence and scope

Fifteen representative entries are grouped by actual scope. Vendor/maintainer documentation establishes a documented interface/design, not independently measured reliability or cost. The [coding ledger](coding-factories.md) records CF-01–15; the [runtime/local ledger](runtime-and-local-evidence.md) records RT-01–07, EV-01–02 and L01–09. External retrieval was November 12. The local researcher labelled its capture November 11 and delivered November 12; exact observation time remains ambiguous. Mutable documentation was not commit-pinned; reachable sources are not an exhaustive inventory of every future-dated release.

“Documented” means present in inspected sources; “composed” means the deployment supplies the contract; “unestablished” means insufficient proof in this source set, not an absent feature. These systems were not independently deployed or fault-injected here. Local tests/findings are attributed to their investigators. Proposed requirements are engineering judgments, not external benchmark conclusions.

## Products and factory orchestration

| System and scope | Work/delegation | Recovery and isolation | Review/operator boundary and limits |
|---|---|---|---|
| **Claude Code**, interactive teams/subagents | Separate contexts or experimental shared tasks/mail | Claims and optional worktrees; teammate resume limitations | Configurable tools/permissions/hooks. Ledger persistence is not restored teammate process. [CF-01](https://code.claude.com/docs/en/agent-teams), [CF-02](https://code.claude.com/docs/en/sub-agents) |
| **OpenAI Codex**, coding threads/automations | Parallel steerable subagents; scheduled/event runs | Parent sandbox/approval inheritance; environment varies | Stop/steer/result inspection. Readonly prompt is not readonly sandbox; no retained web worktree between runs. [CF-03](https://learn.chatgpt.com/docs/agent-configuration/subagents.md), [CF-04](https://learn.chatgpt.com/docs/automations.md) |
| **Cursor**, background cloud coding | Repository tasks and PR workflow | Isolated VM, setup, disconnect continuation | Logs/screenshots and takeover. Continuation is not proof of crash replay or independent acceptance. [CF-05](https://cursor.com/docs/cloud-agent) |
| **Factory**, Missions and Droids | Approved milestones, task delegation and validation roles | Task resume/computer scheduling; sessions can share host resources | Mission Control and autonomy/tool policy. Worktrees are not OS isolation; model fallback affects cost assumptions. [CF-06](https://docs.factory.com/harness/subagents), [CF-07](https://docs.factory.com/missions/overview), [CF-08](https://docs.factory.com/droid-computers/overview) |
| **Devin**, orchestrated coding sessions | Python workflows, child sessions, structured results | Recorded-call replay; personal Git memory | Enterprise/admin boundary. Replay requires external-effect discipline; personal memory excluded from automations. [CF-09](https://docs.devin.ai/work-with-devin/dynamic-workflows), [CF-10](https://docs.devin.ai/product-guides/memory) |
| **GitHub Copilot coding agent**, issue-to-PR | Repository issue/branch delivery | Branch/workflow protections and logs | Human acceptance; agent cannot approve/merge. Some scans/review/workflow controls are configurable. [CF-11](https://docs.github.com/en/enterprise-cloud@latest/copilot/concepts/security-governance-and-network-settings/risks-and-mitigations) |
| **OpenAI Symphony**, tracker orchestration | Versioned WORKFLOW.md and issue dispatch | Workspace reuse, retry/reconciliation and restart reconstruction | Host/operator policy composed by deployment. Engineering preview, draft spec and experimental reference, not mature turnkey platform. [CF-14](https://github.com/openai/symphony), [CF-15](https://github.com/openai/symphony/blob/main/SPEC.md) |
| **Gas Town**, open multi-agent factory | Git-backed work ledger and specialized roles | Worktrees/checkpoints, monitoring and merge coordination | Maintainer architecture; independent fleet reliability/scale unestablished. [CF-12](https://github.com/gastownhall/gastown) |
| **Overstory**, multi-runtime fleet | Adapters, mail, specs and merge queue | Worktrees, watchdogs, checkpoint/handoff | Fleet steering/runtime guards. Review/spec paths configurable; runtime equivalence unestablished. [CF-13](https://github.com/jayminwest/overstory) |

Symphony is especially relevant locally: tracker reconciliation and an inspectable workflow can recover work without claiming to restore every process. Gas Town and Overstory offer inspectable coordination designs, but their repositories do not supply comparable independent recovery or fleet-economics results. These are inferences from CF-12–15. Agent count and a persistent ledger are insufficient proxies for durable execution.

## Runtimes and evaluation

| System and scope | Documented contribution | Factory responsibility |
|---|---|---|
| **OpenHands**, coding runtime | Execution/runtime separation and environments. [RT-02](https://github.com/OpenHands/docs/blob/main/openhands/usage/architecture/runtime.mdx) | Requirement traceability, independent acceptance and activation |
| **SWE-agent / SWE-ReX**, task agent | Coding execution and inspectable trajectories. [RT-01](https://github.com/SWE-agent/SWE-agent/blob/main/docs/usage/trajectories.md) | Scheduling, PR/release policy and authorized learning |
| **LangGraph**, workflow primitives | Persistence and human interruption. [Persistence](https://langchain-ai.github.io/langgraphjs/how-tos/cross-thread-persistence-functional/), [interruption](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) | Coding state machine, authority and side-effect idempotency |
| **Microsoft Agent Framework / AutoGen**, distinct framework generations | Composition; Agent Framework checkpoints/durable integration. [Workflows](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/), [durable extension](https://learn.microsoft.com/en-us/agent-framework/integrations/durable-extension), [AutoGen](https://microsoft.github.io/autogen/stable/index.html) | Version-specific semantics, repository controls and review policy |
| **Agno**, runtime/control plane | Workflow sessions and operating surfaces. [Sessions](https://docs.agno.com/sessions/workflow-sessions), [control plane](https://docs.agno.com/agent-os/control-plane) | Exact-subject coding/test acceptance and training eligibility |
| **Temporal**, durable substrate | Durable workflow execution and Activity retry policies. [Execution](https://docs.temporal.io/workflow-execution), [retries](https://docs.temporal.io/encyclopedia/retry-policies) | Agents/workspaces/policy; nondeterministic effects in Activities, explicit idempotency |

Nine product/factory rows plus these six entries give fifteen representative entries; the Microsoft row explicitly distinguishes generations. [CrewAI tracing](https://github.com/crewAIInc/crewAI/blob/main/docs/edge/en/observability/tracing.mdx) is an additional observability reference, not another full-factory claim.

[SWE-bench](https://proceedings.iclr.cc/paper_files/paper/2024/file/edac78c3e300629acfe6cbe9ca88fb84-Paper-Conference.pdf) and [Terminal-Bench 2](https://arxiv.org/abs/2601.11868) test useful task subsets. They do not certify deployment safety, learning provenance, operator control or recovery correctness. Compare only identical task revision, model, harness, budget, network, retries and grader, with contamination/provenance disclosed. This report assigns no numerical ranks.

## Eighteen-dimension capability/evidence matrix

Local evidence here does not convert instructions/configuration into enforced runtime guarantees. IDs map to the [bounded plan](../../.agents/plans/sota-factory-parity-20261112/DESIGN.md). External evidence IDs resolve above and in the source ledgers.

| Dimension | Representative documented baseline | Local evidence and gap | Requirement |
|---|---|---|---|
| 1. PRD/spec traceability | Factory milestones; Symphony workflow | Plans/tracker policy; no demonstrated same-subject full chain | R01 |
| 2. Dependency/claim ownership | Claude tasks; Gas Town ledger | Existing agent-agnostic-factory; lease/reconciliation proof not supplied | R04 |
| 3. Delegation/model choice | Codex threads; Factory tiers | L05 policy/single local slot, realized routing unmeasured | R11 |
| 4. Restart recovery | Symphony reconciliation; Devin replay | L01 schedule/config is not restart proof | R04 |
| 5. Effect idempotency | Temporal retried Activities | No supplied duplicate-publication fault test | R05 |
| 6. Git/worktree isolation | Claude/Overstory worktrees | L02 default exists; malformed/error guard can fail open | R06 |
| 7. OS/secret/network containment | Cursor VM; Codex parent sandbox | Cooperative worktree guard; hard containment unestablished | R06 |
| 8. PR/review/test subject binding | Copilot PR; Factory validators | L03 preflight not exact-subject independent acceptance | R02 |
| 9. Reviewer independence | Copilot human merge policy | Different role/prompt is insufficient proof | R02 |
| 10. Feasibility/infra neutrality | Evaluation environment discipline | #750 attribution landed; L09 export bypass blocks acceptance | R03 |
| 11. Permissions/intervention | Cursor takeover; Mission Control | Reuse approval-control-plane; full journey not supplied | R10 |
| 12. CI/release/activation | Product PR flows; composed deploy policy | L03 gate pass differs from six-dimension activation | R12 |
| 13. Telemetry/unknown handling | Overstory fleet; Agno control plane | L04 implementation, inconclusive command; no verified panel | R10 |
| 14. Total outcome cost/latency | Factory host metrics; Overstory parsing | L05 policy not realized cost per accepted outcome | R11 |
| 15. Memory scope/provenance | Devin source session/date; Claude memory | Source/tenant authority needs end-to-end proof; hash is integrity only | R07 |
| 16. Learning authentication | No inspected full independent authorization proof | L06 caller fields; L09 unfiltered negative steering | R08 |
| 17. Benefit/regression | Retrieval is not held-out benefit proof | L07 landed attribution baseline; no held-out live benefit claim | R09 |
| 18. Evaluation/version provenance | Papers and inspectable trajectories | Exact revision/environment/issuer required; historical results not current | R01, R03 |

## Local priorities and bounded recommendation

Worktree delegation, a cooperative write guard, factory preflight, telemetry aggregation, routing policy and manual learning pipeline are useful implemented components (L02–07). This audit did not demonstrate current integrated, enabled, functionally validated, observable and intervenable operation for the full factory. The timer/service snapshot is inconclusive without unit semantics; the report timeout is inconclusive without bounded reproduction. Neither warrants restarting services.

The urgent correctness gap is **outcome eligibility across every learning sink**. Attribution #750 (`d7aa36d2f`) is landed and deployed; its reported 44 tests do not establish coverage of every sink. Independent review found negative feedback exported into durable hints without joined stored interaction eligibility in `sync_feedback_corrections_to_gaps` at `interaction_tracker.py:272` (L09). Unknown, infeasible, infrastructure, interrupted and cancelled outcomes remain diagnosable while excluded from agent-quality penalties and learning promotion. Short/partial answers are distinct from infrastructure failures and cannot become adverse learning without independently established eligibility. Caller labels and content hashes cannot confer authority. Repair this remaining export path on the landed baseline; do not infer eligibility from query-text equality.

A defensible exceeding target is a reproducible local demonstration: one frozen requirement traverses execution, interruption/recovery, exact-subject tests, independent acceptance and operator-controlled activation, while every learning sink rejects forged/neutral evidence. It exceeds what this bounded source set establishes about the combined public chain; it does not claim superiority over undocumented deployments.

1. **SF-P1: outcome/evidence contract** — extend landed #750 attribution to the L09 feedback-to-hints export; freeze neutral/impossible/infra rules and exact-subject receipts.
2. **SF-P2: recovery/isolation** — reuse agent-agnostic-factory and coordination-safety; prove one interrupted worker, reconciliation, fail-closed scope and idempotent handback. No new scheduler.
3. **SF-P3: learning promotion** — extend phase184B at ingest, capture/flush and hint sync; quarantine invalid receipts, retain raw records and require held-out evidence before one promotion path.
4. **SF-P4: operating acceptance** — connect aq-report/qa/dashboard/approval to those receipts; measure full cost and prove stop/retry/disable before staged activation.

See [DESIGN](../../.agents/plans/sota-factory-parity-20261112/DESIGN.md), [P1](../../.agents/plans/sota-factory-parity-20261112/P1-outcome-evidence.md), [P2](../../.agents/plans/sota-factory-parity-20261112/P2-recovery-isolation.md), [P3](../../.agents/plans/sota-factory-parity-20261112/P3-learning-provenance.md), [P4](../../.agents/plans/sota-factory-parity-20261112/P4-operational-acceptance.md) and [tracker](../../.agents/plans/sota-factory-parity-20261112/tracker.json). This is a research/design draft to ship inside P1’s first code PR; no docs-only PR is authorized. Scope freeze, implementation and live acceptance remain separate gates. No feature is activated by these documents.

## Feasibility and delivery boundary

Anthropic’s [alignment/security announcement](https://www.anthropic.com/news/improving-alignment-security-efforts) and [Reward Seeker experiment](https://alignment.anthropic.com/2026/reward-seeker/) motivate independent environment/grader certification before admission and recertification after changes: vulnerable or impossible-without-cheating training environments contributed disproportionately in their experiments. The deliberately selected vulnerable-environment proxy is experimental motivation, not evidence of local causality or proof that outcome neutrality prevents reward hacking. A worker cannot exempt itself by declaring a task impossible; neutral outcomes must not reward abstention, and independently verified eligible mistakes remain learning signals. These sources were supplied as verified primary retrieval by the coordinating researcher on 2026-11-12 UTC.

As of this research delivery, recovery fixes E (`95eacfc3f`, PR 748) and D (`a7b731e0a`, PR 749) are merged and, per the owner’s 2026-11-12 update, deployed or deploying alongside #752–#754; this document does not independently attest their activation. Learning attribution #750 (`d7aa36d2f`) is landed/deployed on system `60687d873`, but it is a reviewed baseline rather than end-to-end acceptance. The hook-composition prerequisite is owned by Codex and is **BLOCKED**: factory install/run evidence is missing, native/precommit composition is unsupported, and approved rollout §4.2 defers that support. The separate hook-composition design remains draft; it is a prerequisite to legitimate attribution delivery, not an available bypass or readiness claim. See the assigned [design](../../.agents/plans/sota-factory-parity-20261112/DESIGN.md) and [runtime/local evidence ledger](runtime-and-local-evidence.md) for bounded next actions and provenance limits.
