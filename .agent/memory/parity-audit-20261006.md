# Autonomous capability parity audit — 2026-10-06

Report: `docs/architecture/capability-parity-audit-20261006.md`. Sources and archived QA JSON: `research_notes/Autonomous system capability parity/`.

Audit-only scope: ten repositories in the supplied Reddit post and Google's Always-On Memory Agent sample, with Memory Bank and Titans distinguished. No service implementation or configuration changes; no restart/fault-injection validation. Native equivalents count as overlap; installed packages, healthy units, import tests, and accepted memory writes do not establish complete behavioral parity.

Live `aq-qa` phases 0, 1, 6, 7, 55: 214 passed, 0 failed, 8 skipped. Phase 0 took 329 seconds. Initial sandbox telemetry lock write failed; approved execution resolved it. Phase 55 tests imports and supersession logic, not durable consolidation. MemoryBroker closeout returned queued ID `1112ba91-c8fe-4337-b70f-0b261259cb5e`; durability was not verified.

## Critical Findings — Consolidated Severity Matrix

### P1 — Functional dependency

| # | Finding | Agent Source | File:Line | Impact |
|---|---|---|---|---|
| P1-1 | Five-turn crystallization initializes broker=None; history crystallization returns dependencies_not_met without broker. Verify producer wiring and cross-session recall before claiming consolidation parity. Separate nightly file-session timer is active. | Codex memory audit | ai-stack/mcp-servers/hybrid-coordinator/server.py:756; memory_crystallizer.py:117 | Source-confirmed dependency gap; end-to-end session consolidation remains unproven. |

### P2 — Evidence limitations

| # | Finding | Agent Source | File:Line | Impact |
|---|---|---|---|---|
| P2-1 | Import, health, registry, and in-process supersession checks do not establish restart-safe temporal recall, background consolidation, or agent trajectory correctness. | Codex parity audit | research_notes/Autonomous system capability parity/parity-qa55-live.json | Add bounded write/supersede/historical-read and consolidation/recall acceptance journeys in a separately authorized implementation slice. |

Existing architecture warnings about split memory authority and queue acceptance preceding durable storage were observed in `config/system-state-authorities.yaml:376-406`; this audit did not re-establish their runtime extent. No interim runtime workaround applied.

Closeout: RAG seed acknowledged four records across `best-practices` and `skills-patterns` (two findings each). Initial embedding connection was sandbox-blocked; approved execution succeeded. QA0 graph-runner check is static AST/route/template validation; graph extraction produced 25,575 triples without `--ingest`, and graph-search/augmentation checks inspect source text. These passes do not prove live graph execution or persisted graph retrieval.

Validation recovery: prior final tier0 completed 53 passes/1 focused-CI failure, with QA0 passing 189 checks. Focused-CI reproduction passed on resume (including frontmatter validation), recorded in `/tmp/parity-focused-resume.json`; historical failure cause remains unestablished. Full tier0 rerun passed 54/0, including QA0 189 checks; evidence `/tmp/parity-tier0-resumed.log`.
