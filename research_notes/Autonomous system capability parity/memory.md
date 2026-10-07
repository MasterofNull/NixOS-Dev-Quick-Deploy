# Local memory capability parity

Evidence labels: **implemented** means a source path is present and wired; **configured** means the Nix declaration is present; **historical integration result** is a repository-recorded result; **live** is a probe made for this review.  Health or unit activation is not treated as an end-to-end memory result.

## Cognee — knowledge relationships

### Takeaway

**Partial parity: a live local, non-ingesting triple-extraction run and graph-query source paths exist, while live relationship ingestion and graph retrieval remain unknown (medium confidence).** Cognee turns raw information into concepts and relationships, then combines vector similarity with graph traversal at search time. The coordinator has semantic-fact storage and a separately wired temporal triple graph, but the identified fact-ingest path writes text into semantic memory rather than extracting a relationship graph.

### Cited Findings

- Cognee documents `add` plus `cognify` as the path that extracts entities and relationships, links them into a graph, and supports graph-traversal-assisted search. [Cognee reference notebook](https://docs.cognee.ai/reference/colab_notebooks)
- **Implemented:** `POST /api/memory/facts` accepts structured facts and sends each fact's text to `MemoryBroker` as `semantic` memory; `GET` sends a semantic query to the broker and filters returned metadata. [memory_service.py:34](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory/memory_service.py:34) [memory_service.py:71](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory/memory_service.py:71) [memory_service.py:93](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory/memory_service.py:93)
- **Implemented:** the temporal graph persists explicit `(subject, predicate, object)` tuples, closes the active fact when a new fact has the same subject and predicate, and can query facts valid at a selected time. [temporal_graph.py:1](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/knowledge/temporal_graph.py:1) [temporal_graph.py:85](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/knowledge/temporal_graph.py:85) [temporal_graph.py:156](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/knowledge/temporal_graph.py:156)
- **Implemented:** the router invokes temporal-graph route registration, but registration errors are logged and skipped. [router.py:261](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/router.py:261) [router.py:296](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/router.py:296)
- **Historical integration result, limited:** Phase 56 is recorded as 16/16 passing, but the current memory-fact check only asserts that a write response reports at least one stored item; it does not retrieve the fact, create a relationship, or traverse a graph. [MEMORY.md:29](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/agent-memory/MEMORY.md:29) [_aq-qa-bash:3035](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/_aq-qa-bash:3035)
- **Live local extraction, bounded:** the current QA0 Phase 63.1 run executed `aq-index-knowledge-graph --skip-llm` and reported 25,575 triples. In that mode the tool uses regex extraction, and without `--ingest` it prints a dry-run result and returns without uploading to AIDB; therefore this proves local extraction only, not persisted graph ingestion. [parity-qa0-live.json](</home/hyperd/Documents/NixOS-Dev-Quick-Deploy/research_notes/Autonomous system capability parity/parity-qa0-live.json>) [phase0.py:3164](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/harness_qa/phases/phase0.py:3164) [aq-index-knowledge-graph:190](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/aq-index-knowledge-graph:190) [aq-index-knowledge-graph:300](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/aq-index-knowledge-graph:300)
- **Implemented; QA0 static presence only:** the graph-search module contains a vector-seeded BFS expansion and an HTTP-route registration function, and the RAG augmentor contains intent-gated graph augmentation. QA0 Phases 63.2 and 63.3 only read source and require named substrings; they neither import these modules nor invoke the route or augmentation path. [graph_search.py:74](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/knowledge/graph_search.py:74) [graph_search.py:167](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/knowledge/graph_search.py:167) [rag_augmentor.py:202](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/rag_augmentor.py:202) [phase0.py:3188](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/harness_qa/phases/phase0.py:3188) [phase0.py:3206](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/testing/harness_qa/phases/phase0.py:3206)

### Inferences

- The repository has a graph data model and a semantic-memory route, but no identified transform from `POST /api/memory/facts` free text to graph entities/edges. That is less complete than Cognee's documented raw-information-to-relationship workflow.
- The QA0 extraction result establishes that repository text can yield triples under the offline regex rule, and the source contains a GraphRAG path. It does not demonstrate that those triples were ingested, that vector seed results existed, or that a graph-enriched answer reached a caller.

### Gaps

- No fresh evidence of one raw fact producing entities/edges, followed by a relationship-aware query result.
- No live request to `/api/knowledge/graph/search` or live `graph_augment` invocation against an AIDB collection containing known triples; QA0 63.2/63.3 are static checks.
- No evidence that temporal-graph route registration succeeded in the running coordinator, or that its PostgreSQL schema is available.
- The declared memory/RAG authority still reports `SPLIT_BRAIN`: direct Qdrant writers coexist with the intended broker-led path. [system-state-authorities.yaml:376](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/system-state-authorities.yaml:376) [system-state-authorities.yaml:387](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/system-state-authorities.yaml:387)

## Graphiti — temporal facts and supersession

### Takeaway

**Strong structural parity in source, with a live but narrow fact-versioning pass; durable, cross-restart temporal behavior is unverified (medium-high confidence for implementation, medium for in-process versioning, low for durability).** The implementation contains validity intervals, event time, supersession records, and time-qualified reads. Its durable ledger depends on PostgreSQL, while the fallback ledger is process-local.

### Cited Findings

- Graphiti describes a temporal knowledge graph that tracks changing relationships with a bi-temporal model, entity/edge extraction, invalidation, and hybrid retrieval. [Graphiti overview](https://help.getzep.com/graphiti/getting-started/overview)
- **Implemented:** broker writes accept `valid_from`, `valid_until`, `event_time`, and a supersession flag; contradiction handling can resolve lineage, and metadata records event and ingestion time. [memory_broker.py:109](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_broker.py:109) [memory_broker.py:131](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_broker.py:131) [memory_broker.py:177](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_broker.py:177)
- **Implemented:** the supersession DDL records the superseded fact, replacement, reason, prior validity end, and creation time. When PostgreSQL is absent, the service retains events in an in-process list and labels the result as memory-backed. [memory_superseder.py:21](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_superseder.py:21) [memory_superseder.py:59](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_superseder.py:59) [memory_superseder.py:120](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_superseder.py:120)
- **Implemented:** semantic recall builds a retrieval plan with `valid_at`, expired-item exclusion, and superseded-item exclusion. [memory_manager.py:412](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/knowledge/memory_manager.py:412) [memory_manager.py:433](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/knowledge/memory_manager.py:433)
- **Historical integration result, limited:** Phase 55 is recorded as passing, but its smoke checks assert only `superseded: true`, an `events` list, and status-field presence. The crystallization POST check accepts either an error or an accepted response. [MEMORY.md:30](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/agent-memory/MEMORY.md:30) [_aq-qa-bash:2950](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/_aq-qa-bash:2950) [_aq-qa-bash:2960](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/_aq-qa-bash:2960)
- **Live test, narrow:** the current Phase 55 run passed 4/4: the superseder, crystallizer, and drift analyzer imported, and fact-versioning/supersession logic passed. It did not exercise a background run, a durable store, retrieval after restart, or an end-to-end consolidation loop. [parity-qa55-live.json](/tmp/parity-qa55-live.json)

### Inferences

- The temporal model covers a meaningful Graphiti subset: validity-time facts, supersession, lineage, and time-qualified filtering. The evidence does not establish automatic entity/edge extraction or a durable bi-temporal graph in the live system.
- A supersession response can be correct during one process lifetime while failing the durable-memory requirement if PostgreSQL is unavailable, because the fallback state is local process memory.

### Gaps

- No fresh write → supersede → restart → historical query evidence.
- No runtime proof that the broker's PostgreSQL-backed lineage table or temporal-graph schema is usable.
- The stated authority warns that queue acceptance precedes durable Qdrant upsert, so accepted writes alone cannot prove persistence. [system-state-authorities.yaml:405](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/system-state-authorities.yaml:405) [system-state-authorities.yaml:406](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/system-state-authorities.yaml:406)

## Google Always-On Memory Agent — ingest, consolidation, query, and durable cross-session memory

### Takeaway

**Ingest, query, and a scheduled consolidation path are implemented and currently activated; end-to-end durable consolidation is not established (high confidence for activation, medium for implementation, low for successful runtime behavior).** The main session-turn crystallization hook is initialized with no broker and its history path returns `dependencies_not_met` without one. The nightly file-session route can instead persist via the supplied insight-store function, but no completed live run was verified.

### Cited Findings

- Google's reference implementation ingests through a watcher, upload, or POST endpoint; it runs background consolidation on a timer, answers queries from stored memory and insights, and uses a durable SQLite database. [Always-On Memory Agent README](https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/agents/always-on-memory-agent/README.md)
- **Implemented:** the facts API is registered with the coordinator's router, and the GET handler exposes a cross-session recall path through the broker. [memory_service.py:185](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory/memory_service.py:185) [memory_service.py:118](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory/memory_service.py:118)
- **Configured and live activation:** Nix declares a nightly `ai-crystallize-sessions` service and timer; this review's read-only `systemctl is-active` probe returned `active` for the coordinator, AIDB service, and the crystallization timer. Activation establishes scheduling availability, not a successful consolidation run. [mcp-servers.nix:2147](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/modules/services/mcp-servers.nix:2147) [mcp-servers.nix:2181](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/nix/modules/services/mcp-servers.nix:2181)
- **Implemented with a blocking condition:** every fifth session turn creates a background crystallization task, but the crystallizer is initialized with `broker=None`; history crystallization returns `dependencies_not_met` unless both a Llama client and broker are present. [http_server_impl.py:2350](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py:2350) [server.py:756](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/server.py:756) [memory_crystallizer.py:117](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py:117)
- **Implemented:** the file-session crystallizer can send its distilled result through an injected store function and records a PostgreSQL session row when a PostgreSQL client exists. [memory_crystallizer.py:65](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py:65) [memory_crystallizer.py:93](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py:93)
- **Known runtime evidence:** the October 2 project memory records a working-memory HTTP 500 and explicitly says MemoryBroker fact-store status was unknown, while `/readyz` was 200. That confirms why health must not be read as successful durable memory. [MEMORY.md:153](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/ai-stack/agent-memory/MEMORY.md:153)

### Inferences

- This design approaches Google's four functions through separate components: facts API for ingest, Nix timer/file crystallizer for background consolidation, broker recall for query, and PostgreSQL/Qdrant for intended durability. They are not yet demonstrated as one successful durable loop.
- The live active services and timer are necessary operational evidence, but neither proves that sessions were ingested, distilled, stored, subsequently recalled, or survived a restart.

### Gaps

- No fresh end-to-end evidence: ingest a uniquely identifiable item, wait for or invoke consolidation, retrieve the resulting memory in a different session, then verify survival after process restart.
- The in-process five-turn consolidation route has an identified dependency gap (`broker=None`); this prevents parity for that route unless another initialization path wires it before use.
- The task's sandbox prevented direct inspection of unit logs and sockets before escalation; the approved service-state probe confirmed activation only. No credentials or secret-bearing configuration were read.
