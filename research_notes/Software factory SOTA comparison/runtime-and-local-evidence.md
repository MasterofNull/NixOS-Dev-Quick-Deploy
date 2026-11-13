# Runtime and local evidence ledger

Saved 2026-11-12 UTC. Runtime sources were supplied by the delegated researcher, who reported November 12 access; not independently reproduced by this author. Local audit was labelled November 11 and delivered November 12: capture-time ambiguity is retained. L07 and L09 were refreshed against the reviewed rebased baseline on November 12. Source inspection is not runtime acceptance.

| ID | Primary runtime sources | Bounded use |
|---|---|---|
| RT-01 | [SWE-agent usage](https://github.com/SWE-agent/SWE-agent/blob/main/docs/usage/hello_world.md), [trajectories](https://github.com/SWE-agent/SWE-agent/blob/main/docs/usage/trajectories.md) | Coding execution and inspectable trajectories, not complete factory control plane. |
| RT-02 | [OpenHands architecture](https://github.com/OpenHands/docs/blob/main/openhands/usage/architecture/runtime.mdx), [repository](https://github.com/OpenHands/OpenHands/blob/main/README.md) | Agent/runtime separation; organizational acceptance and activation are separate. |
| RT-03 | [LangGraph persistence](https://langchain-ai.github.io/langgraphjs/how-tos/cross-thread-persistence-functional/), [interruption](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) | Checkpoint/memory/intervention primitives; application supplies coding and side-effect contracts. |
| RT-04 | [AutoGen](https://microsoft.github.io/autogen/stable/index.html), [Agent Framework workflows](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/), [checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints), [durable extension](https://learn.microsoft.com/en-us/agent-framework/integrations/durable-extension), [observability](https://learn.microsoft.com/en-us/agent-framework/workflows/observability) | Workflow composition/persistence/tracing; distinguish product generation and version. |
| RT-05 | [Agno sessions](https://docs.agno.com/sessions/workflow-sessions), [runtime](https://docs.agno.com/features/runtime), [control plane](https://docs.agno.com/agent-os/control-plane) | Runtime/control-plane building blocks; exact-subject coding acceptance unestablished. |
| RT-06 | [Temporal AI](https://docs.temporal.io/ai), [workflow execution](https://docs.temporal.io/workflow-execution), [retry policies](https://docs.temporal.io/encyclopedia/retry-policies) | Durable substrate, not coding factory. Activities retry by default; nondeterministic effects belong in Activities. Replay does not confer idempotency. |
| RT-07 | [CrewAI tracing](https://github.com/crewAIInc/crewAI/blob/main/docs/edge/en/observability/tracing.mdx) | Additional tracing reference, not independently evaluated factory. |
| EV-01 | [SWE-bench paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/edac78c3e300629acfe6cbe9ca88fb84-Paper-Conference.pdf) | Repository repair evaluation, not factory certification. |
| EV-02 | [Terminal-Bench 2 paper](https://arxiv.org/abs/2601.11868), [repository](https://github.com/harbor-framework/terminal-bench) | Compare only exact model, harness, task revision, budget, network, retries and grader. |

## Local evidence supplied by sibling and parent

| ID | Evidence locators | Meaning and boundary |
|---|---|---|
| L01 | `nix/modules/services/mcp-servers.nix:2241-2242`; timer/service/coordinator observed `active/inactive/inactive` | Scheduling only; unit type/name and observation time need checking. Not an outage diagnosis or run/recovery proof. |
| L02 | `scripts/ai/delegate-to-local:41-46,73-74,177`; `scripts/ai/aq-worktree-write-guard:49-63,73` | Worktree default and escape guard; malformed input/OSError can fail open. Cooperative path isolation is not OS containment. |
| L03 | `scripts/ai/aqd:39,841,845,1988` | Metadata-oriented preflight. Historical Wave E gate pass with independent port-SSOT finding is not current activation. HEAD advanced concurrently. |
| L04 | `scripts/ai/aq-report:86,89,136,196,205,390-398`; supplied command produced no JSON after 30.4 seconds | Aggregation/no_data implementation; live telemetry inconclusive, no dashboard or latency result established. |
| L05 | `config/model-coordinator.json:63-69,95-100,119-124,144-149` | Single local slot, ceilings and fallback policy; not realized routing or measured cost. |
| L06 | `ai-stack/local-agents/training_ingest.py:67-69,407-426,446-450`; `ai-stack/mcp-servers/hybrid-coordinator/extensions/model_optimization.py:216+` | Caller success fields influence ingestion. Capture/flush needs receipt eligibility and preserved provenance too; hashes/dedupe are not authorization. |
| L07 | #750, `d7aa36d2f` (landed/deployed); deployed system `60687d873`; 44 tests reported | The landed attribution baseline is not independent acceptance/activation and does not repair the L09 sink. |
| L08 | Historical `/tmp/aq-wave-d-tier0-20261112.log:67-72`; AIDB video 811886 | `source_url` NULL is a producer metadata bug outside factory evidence. The historical handoff observation and partial viewing cannot support a factory readiness or provenance claim. |
| L09 | Reviewed rebased baseline after #750: `ai-stack/mcp-servers/hybrid-coordinator/extensions/interaction_tracker.py:272`, `sync_feedback_corrections_to_gaps` | The function exports negative feedback without a joined stored eligibility check; this is the first repair. Block acceptance until only stored eligible agent_error exports; retain short/partial, neutral, unknown and unlinked raw data. Previous 44 tests missed this sink. Parent-reviewed, not reproduced here. |

No service was changed for these notes. Fresh branch/subject checks are required before implementation. Local line numbers are locators, not immutable citations. Preserve exact subject hashes at next-session orientation; do not turn historical gate observations into current state.
