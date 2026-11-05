# AI Engineer video: graph engineering

- Video: [Make Your AI Agents Predictable with Graph Engineering](https://www.youtube.com/watch?v=g_NgCLTibiM)
- Curated record: `.agent/research/papers/videos/g_NgCLTibiM.json`
- Transcript basis: published caption mirror at https://ainotes.us/summary/make-your-ai-agents-predictable-with-graph-engineering-zachary-blumenfeld-neo4j; local `aq-transcribe` did not complete, so this is not represented as a locally generated transcript.
- Channel feed: `ai-engineer-youtube` in `ai-stack/data/knowledge-sources.yaml`; weekly Atom feed.
- Ingestion evidence: `scripts/data/sync-knowledge-sources --id ai-engineer-youtube` imported 15 records, including this video. The curated record was seeded to `skills-patterns` and `best-practices` (one record per collection).
- Research takeaway: procedural graphs and persistent execution traces may improve reusable, inspectable agent workflows. Existing AQ-OS graph and workflow components suggest a focused integration/evidence slice, not a new graph database by default. Validate current live call paths before claiming enablement.
- Follow-up candidate: select one real workflow and measure completion, latency, token use, provenance, deterministic routing, validation, and human intervention; include a live QA integration path and observable dashboard state before calling it enabled.
- Friction: `aq-transcribe` yielded metadata only and was interrupted; tracked in `.agent/memory/issues-backlog.md` as `rsi-video-ingest-transcript-20261103`. The first RAG seed call supplied a file instead of a directory; corrected invocation succeeded.
