# External capability baseline

_Research date: 2026-10-06. Scope: documented capabilities of the ten projects named in the supplied post, plus the official Google always-on-memory sample. This is an evidence baseline only; it makes no claim that a capability is present in the running system and makes no installation recommendation._

## What capabilities do the cited open-source projects explicitly document?

### Takeaway

The projects cover complementary layers of an autonomous system: control flow and durable execution; typed agent interfaces; application and graph memory; browser and isolated-code execution; and tracing/evaluation. Their feature sets overlap, so the rows below should be read as capability evidence rather than a one-for-one product taxonomy.

### Cited findings

| Project | Capability baseline from primary documentation |
|---|---|
| [LangGraph](https://langchain-ai.github.io/langgraphjs/how-tos/persistence-postgres/) | Persists graph state with checkpointers for thread-scoped continuity, fault tolerance, human-in-the-loop workflows, and time travel; a store can retain facts/preferences across threads. [`interrupt()`](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph) pauses a run and resumes it from saved state, enabling review or approval of tool calls. |
| [PydanticAI](https://ai.pydantic.dev/capabilities/overview/) | Provides schema-validated structured outputs and tool arguments, managed prompts, tracing, and persistence adapters. Its [durable-execution guide](https://ai.pydantic.dev/durable_execution/overview/) describes preserving agent progress through failures/restarts and supporting long-running or human-in-the-loop work through external workflow engines. |
| [Mastra](https://mastra.ai/docs/memory/overview) | Supplies message history, persistent working memory, semantic recall, and Observational Memory, which uses background agents to maintain a dense history. Its [multi-agent guide](https://mastra.ai/docs/agents/multi-agent-systems) describes delegation and supervisor patterns; its [Studio documentation](https://mastra.ai/docs/studio/overview) covers run visualization, logs/traces, datasets, and scoring. |
| [Agno](https://docs.agno.com/examples/basics/overview) | Documents agents with tools and structured output; persistent conversation storage; user memory and session state; knowledge retrieval; guardrails including tool confirmation; multi-agent teams; workflows; and an AgentOS runtime/UI surface. |
| [Cognee](https://docs.cognee.ai/reference/colab_notebooks) | Its `cognify` pipeline chunks data, extracts entities/relationships, and stores graph plus embedding representations. Search can perform vector similarity and graph traversal for RAG, graph completion, chunks, summaries, triplets, and temporal results, as listed in its [API reference](https://docs.cognee.ai/api-reference/introduction). |
| [Graphiti](https://help.getzep.com/graphiti/getting-started/overview) | Builds a temporal knowledge graph from structured or unstructured episodes, retains provenance and historical relationships, and retrieves with time-aware, full-text, semantic, and graph search. It incrementally updates an evolving context graph rather than requiring a full rebuild. |
| [Browser Use](https://docs.browser-use.com/customize/more-examples) | Documents natural-language browser task automation through its open-source Python library or cloud API, including browser interaction examples and custom agent/tool integration. |
| [E2B](https://e2b.dev/docs/sdk-reference/js-sdk/v2.6.2/sandbox) | Provides an isolated cloud sandbox with a Linux environment, filesystem, command execution, and network access for running untrusted or agent-produced code; sandboxes can start from snapshots. |
| [Langfuse](https://langfuse.com/docs/observability/overview) | Traces LLM requests with exact prompts/responses, token usage, latency, retrieval, and tool steps. Its [metrics](https://langfuse.com/docs/metrics/overview), [prompt management](https://langfuse.com/docs/prompt-management/overview), and [experiments](https://langfuse.com/docs/evaluation/experiments/experiments-via-ui) document quality/cost dashboards, versioned prompts linked to traces, and dataset-based regression evaluation. |
| [DeepEval](https://deepeval.com/docs/metrics-introduction) | Offers local evaluation metrics for LLM applications, RAG, and complete agent trajectories; LLM-as-judge metrics return a score and reason. Its [tool-correctness metric](https://deepeval.com/docs/metrics-tool-correctness) evaluates selected tools, arguments, and (optionally) outputs against expectations. |

### Gaps and boundaries

- These references establish documented functions, not operational maturity, security posture, license compatibility, release compatibility, or performance under this repository's workload.
- A row can cover more than one layer. For example, LangGraph provides durable control flow, while Langfuse records and evaluates a run; neither claim implies that the other layer is supplied.

## How does Google’s always-on-memory sample differ from Memory Bank and Titans?

### Takeaway

The [always-on-memory-agent sample](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/agents/always-on-memory-agent/README.md) is an application-level external-memory pattern: an ADK/Gemini process writes structured records to SQLite, then periodically consolidates and queries them. It is distinct from Vertex AI Agent Engine **Memory Bank**, a managed long-term memory service, and from **Titans**, a neural architecture that learns memory at test time. The sample README does not describe an integration with either named technology.

### Cited findings

- The sample accepts text, images, audio, video, and PDFs; its ingest agent extracts structured summaries, entities, topics, and importance. A timed consolidation agent reviews unconsolidated records, links them, produces cross-cutting insights, and compresses related information. Queries synthesize an answer from stored memories and insights. The repository states that it uses no vector database or embeddings, and identifies SQLite as its persistent store. The [implementation](https://raw.githubusercontent.com/GoogleCloudPlatform/generative-ai/main/gemini/agents/always-on-memory-agent/agent.py) creates `memories`, `consolidations`, and `processed_files` tables, while using `InMemorySessionService` for ADK interaction sessions. [Sample README](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/agents/always-on-memory-agent/README.md)
- Vertex AI Agent Engine [Memory Bank](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/set-up) is a managed service associated with an Agent Engine instance. It can generate and retrieve memories; configuration includes extraction topics, an embedding model for similarity search, an LLM for generation, and retention settings. Google’s [Memory Bank overview](https://cloud.google.com/blog/products/ai-machine-learning/vertex-ai-memory-bank-in-public-preview) describes asynchronous extraction from session history, persistent scoped memories, update/consolidation, and retrieval across sessions. This is a product/service contract, not the SQLite implementation shown in the sample.
- [Titans: Learning to Memorize at Test Time](https://research.google/pubs/titans-learning-to-memorize-at-test-time/) is research on a model architecture: it augments attention with a neural long-term-memory module that learns from historical context at test time. The persistent memory is part of the model computation, rather than a separately queried SQLite record store. Google’s [research post](https://research.google/blog/titans-miras-helping-ai-have-long-term-memory/) further describes test-time memory updates and a neural MLP memory module.

### Inferences and boundaries

- The sample and Memory Bank share the **system goal** of maintaining durable, useful context beyond one prompt, but their documented mechanisms diverge: self-managed structured SQLite plus an explicit consolidator versus managed memory extraction/retrieval with configurable similarity search. This is an inference from the cited designs, not a claim of API compatibility.
- The sample’s background consolidation may resemble “learning” at the application-data layer, but it does **not** evidence Titans-style model-weight or neural-memory updates. Treating the sample as a Titans implementation would conflate external application memory with a model architecture.
- “Memory Bank” should mean the named Vertex AI service when used as a proper noun. Calling any persistent table a memory bank is only generic terminology and does not establish integration with that managed service.

### Gaps

- The reviewed sample README is the published architecture statement; it does not supply a benchmark, retention/privacy policy, access-control design, or production deployment attestation.
- This note deliberately does not assess whether the local running system has equivalent capabilities; that requires live local evidence.
