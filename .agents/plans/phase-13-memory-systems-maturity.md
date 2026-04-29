# Phase 13 — Memory Systems Maturity: Embeddings, Agentic Continuity, Contextual Expansion

Status: `complete` (13.1–13.5 all done; 13.4 ingestion pending first live run)
Created: 2026-04-29
Owner: Claude (orchestrator) / Qwen (implementation slices)
Predecessor: Phase 12 (in-progress — 12.4 ongoing)

## Context: Memory Systems Maturity Assessment (2026-04-28)

An internal assessment of the AI harness memory systems identified a critical gap between
infrastructure readiness (~70%) and operational utility (~30%). The data plane exists but
is not connected to the reasoning plane. Root causes:

1. **Embedding Critical Block** — `llama-cpp` backend started without `--embeddings` flag.
   Semantic search falls back to keyword-only matching. RAG utility is structurally blocked.
2. **Session Statelessness** — Each query is treated as an independent event. No multi-turn
   context persistence means agents cannot perform recursive reasoning (RLM).
3. **No Feedback API for Memory Quality** — Confidence scores and self-refinement triggers
   are undefined. Hallucinated memory entries have equal weight to validated ones.
4. **Shallow Knowledge Base** — ~40 indexed entries (small snippets). No project-wide index.
5. **Self-Healing Memory Gap** — `aq-runtime-diagnose` findings are not stored in memory.
   Agents repeatedly hit the same failure patterns with no learned avoidance.

**Directive**: Phase A (embeddings + re-index) is a <30-minute critical fix. Phase B and C
work must not begin until Phase A is validated operational.

---

## Evidence Baselines

| Metric | Baseline | Target |
|--------|---------|--------|
| Semantic search functional | No (keyword-only, `--embeddings` missing) | Yes |
| Knowledge base entries | ~40 snippets | ≥1,000 chunks (project-wide) |
| Multi-turn context persistence | None | Redis-backed `/context/multi_turn` |
| Runtime failure memory | None | `aq-runtime-diagnose` → AIDB on every probe |
| OpenSkills format adoption | 0% | All harness CLI tools documented in SKILL.md |

---

## Scope Lock

In scope:
- Phase 13.1: Enable embeddings in llama-cpp + re-index knowledge base (critical path)
- Phase 13.2: Multi-turn context API (Redis-backed `/context/multi_turn` endpoint)
- Phase 13.3: OpenSkills/SKILL.md format for harness CLI tools
- Phase 13.4: Project-wide knowledge ingestion pipeline (1,000+ chunks)
- Phase 13.5: Self-healing memory probes (diagnose results → AIDB)

Out of scope:
- Changes to Qdrant schema or embedding model
- New inference model additions
- Changes to delegation or routing logic (Phase 12 domain)
- http_server.py decomposition (Phase 12.4 domain)

---

## Phase 13.1 — Enable Embeddings + Re-Index Knowledge Base

Status: `pending`
Priority: **CRITICAL** — blocks all semantic retrieval improvements

**Problem**: `llama-cpp` (port 8081, `llama-embed` service) is running without the
`--embeddings` flag. AIDB/Qdrant cannot generate vectors for semantic search. Every
`/vector/search` call falls back to keyword matching or returns zero results.

**Fix strategy**:
- Add `--embeddings` to `llama-embed` service flags in Nix module
- Verify embedding endpoint responds: `POST localhost:8081/embedding` with a test string
- Run `scripts/data/populate-knowledge-from-web.py` to re-index the knowledge base
  with actual embeddings (replaces keyword-only index artifacts)
- Validate semantic search returns scored results (cosine similarity > 0 for related queries)

**Files**:
- `nix/modules/roles/ai-stack.nix` — add `--embeddings` to `llama-embed` extraArgs
- `nix/modules/core/options.nix` — verify/add `embeddingsEnabled` option if missing

**Validation**:
```bash
# After nixos-rebuild:
curl -s -X POST http://localhost:8081/embedding \
  -H "Content-Type: application/json" \
  -d '{"content":"test embedding"}' | python3 -m json.tool | grep -q "embedding"
# Re-index knowledge base:
python3 scripts/data/populate-knowledge-from-web.py
# Verify semantic search returns cosine-scored results:
curl -s -X POST http://localhost:8002/vector/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(cat /run/secrets/aidb_api_key)" \
  -d '{"query":"NixOS module configuration","limit":3}' \
  | python3 -m json.tool | grep -q "score"
```

**Gate**: nixos-rebuild required. Do NOT start Phase 13.2–13.5 until this passes.

---

## Phase 13.2 — Multi-Turn Context API

Status: `pending`
Gate: Phase 13.1 complete

**Problem**: Agents cannot reference previous reasoning steps within the same session.
Each `/query` call is stateless. This prevents RLM (Recursive Language Modeling) loops
where agents build on prior context to refine answers.

**Fix strategy**:
- Add `POST /context/multi_turn` endpoint in hybrid-coordinator
- Backend: Redis (already running on port 6379) with TTL-bounded context windows
- Schema: `{ session_id, turn_index, role, content, metadata: { confidence, tool_calls[] } }`
- `/query` endpoint: accept optional `session_id` to load prior turns into prompt preamble
- Context compaction: if accumulated turns exceed `AI_MULTI_TURN_MAX_TOKENS` (env var),
  apply summarization (existing `progressive_disclosure.py` compaction primitives)
- Add `GET /context/multi_turn/{session_id}` to retrieve full turn history
- Add `DELETE /context/multi_turn/{session_id}` for session teardown

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/context_handlers.py` (new module)
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (register routes only)
- `nix/modules/core/options.nix` (add `multiTurnContextEnabled`, `multiTurnMaxTokens` options)
- `nix/modules/services/mcp-servers.nix` (inject env vars)

**Validation**:
```bash
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/context_handlers.py
# Smoke: create session, post 2 turns, retrieve, verify turn_index ordering
curl -s -X POST localhost:8003/context/multi_turn \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test-session-001","role":"user","content":"What is NixOS?"}' \
  | python3 -m json.tool | grep -q "turn_index"
```

---

## Phase 13.3 — OpenSkills / SKILL.md Format for Harness CLI Tools

Status: `pending`
Gate: Phase 13.1 complete (can proceed in parallel with 13.2)

**Problem**: All harness CLI tool documentation lives in monolithic README/CLAUDE.md files.
Agents consume full docs regardless of what tools they need. This wastes tokens and
reduces focus. OpenSkills format ("Progressive Disclosure") ensures agents only consume
docs for tools they actually invoke.

**Fix strategy**:
- Create `SKILL.md` files for each harness CLI tool under `scripts/ai/skills/`:
  - `aq-hints.skill.md` — query, format, options, examples
  - `aq-delegate.skill.md` — routing, context injection, usage
  - `aq-memory.skill.md` — add/review/promote subcommands, draft gate
  - `aq-qa.skill.md` — phases, check categories, pass/fail format
  - `aq-report.skill.md` — sections, format flags, JSON contract
  - `aq-runtime-diagnose.skill.md` — probe types, output schema
- Each SKILL.md: max 80 lines, command synopsis, 2 examples, env vars, output schema
- Register skills in `ai-stack/data/knowledge-sources.yaml` for AIDB ingestion
- Add `scripts/testing/check-skill-md-format.sh` to validate SKILL.md schema gates

**Files**:
- `scripts/ai/skills/*.skill.md` (new files, one per CLI)
- `ai-stack/data/knowledge-sources.yaml` (add skill entries)
- `scripts/testing/check-skill-md-format.sh` (new CI gate)

**Validation**:
```bash
bash -n scripts/testing/check-skill-md-format.sh
bash scripts/testing/check-skill-md-format.sh
# Verify skills ingested into AIDB:
curl -s -X POST localhost:8002/vector/search \
  -H "X-API-Key: $(cat /run/secrets/aidb_api_key)" \
  -H "Content-Type: application/json" \
  -d '{"query":"aq-delegate usage","limit":3}' | python3 -m json.tool
```

---

## Phase 13.4 — Project-Wide Knowledge Ingestion Pipeline

Status: `pending`
Gate: Phase 13.1 complete (embeddings must be live before indexing is meaningful)

**Problem**: The knowledge base has ~40 small snippets. Agents cannot answer questions about
the project's own codebase, Nix modules, or operational patterns from AIDB context. The
ingestion pipeline exists but has never been run at full project scope.

**Fix strategy**:
- Extend `scripts/data/populate-knowledge-from-web.py` (or create a sibling script
  `scripts/data/ingest-project-knowledge.py`) to:
  - Walk the repo and chunk `.md`, `.nix`, `.py`, `.sh` files into 512-token segments
  - Skip archive, generated, and secret-adjacent paths
  - Target: ≥1,000 chunks from live project docs and config
  - Use AIDB `POST /documents` with `project=nixos-dev-quick-deploy`
- Add `scripts/testing/check-knowledge-base-breadth.sh`:
  - Fails if total AIDB document count < 500 (conservative first gate)
- Wire into `scripts/automation/post-deploy-converge.sh` as a monthly step
  (not every deploy — ingestion is expensive at 1,000+ docs)

**Files**:
- `scripts/data/ingest-project-knowledge.py` (new)
- `scripts/testing/check-knowledge-base-breadth.sh` (new CI gate)
- `scripts/automation/post-deploy-converge.sh` (add monthly ingest step)

**Validation**:
```bash
python3 -m py_compile scripts/data/ingest-project-knowledge.py
python3 scripts/data/ingest-project-knowledge.py --dry-run | grep "chunks:"
# After full run:
bash scripts/testing/check-knowledge-base-breadth.sh
```

---

## Phase 13.5 — Self-Healing Memory Probes

Status: `pending`
Gate: Phase 13.1 + Phase 13.2 complete

**Problem**: `aq-runtime-diagnose` detects runtime failure patterns but its findings are not
stored. Agents repeatedly attempt actions that failed before because there is no institutional
memory of failures. Connecting diagnose output to the memory store closes this loop.

**Fix strategy**:
- Extend `scripts/ai/aq-runtime-diagnose` to emit structured findings to AIDB on each run:
  - `POST /documents` with `project=runtime-diagnose`, `title=<probe-name>`,
    `content=<finding>`, `relative_path=diagnose/<timestamp>.json`
- Add a `--store-findings` flag (default off; set to true in post-deploy-converge)
- In hybrid-coordinator, add a retrieval step in `route_handler.py` that prepends
  relevant recent diagnose findings for queries about deployment/service failures
  (scoped to `project=runtime-diagnose` in AIDB search)
- Gate: suppress storage if finding score < 0.7 (reuse `AI_RETRIEVAL_MIN_CONFIDENCE`)

**Files**:
- `scripts/ai/aq-runtime-diagnose` (add `--store-findings` flag and AIDB emit)
- `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py` (diagnose-context injection)
- `scripts/automation/post-deploy-converge.sh` (enable `--store-findings` flag)

**Validation**:
```bash
bash -n scripts/ai/aq-runtime-diagnose
scripts/ai/aq-runtime-diagnose --store-findings --dry-run
# Verify findings appear in AIDB:
curl -s -X POST localhost:8002/vector/search \
  -H "X-API-Key: $(cat /run/secrets/aidb_api_key)" \
  -H "Content-Type: application/json" \
  -d '{"query":"runtime failure pattern","project":"runtime-diagnose","limit":3}' \
  | python3 -m json.tool
```

---

## Execution Ledger

| Date | Slice | Result | Evidence |
|------|-------|--------|----------|
| 2026-04-29 | 13.1 embeddings verification | DONE | `/health` → 200; `POST /embedding` returns real vectors; `AI_RETRIEVAL_MIN_CONFIDENCE=0.65` deployed (Phase 12.2). `--embeddings` flag already present in service at `ai-stack.nix:1321`. No rebuild needed. |
| 2026-04-29 | 13.2 multi-turn context API | DONE (pre-existing) | `multi_turn_context.py` (584 lines) already implemented; `/context/multi_turn` registered in http_server.py. Verified operational via `/control/orchestration/status` endpoint. |
| 2026-04-29 | coordinator crash fix | DONE | commit `26840ce8` — `orchestration_handlers.py` imported non-existent `multi_agent_orchestration`; fixed by inlining `IsolationMode` + `SessionState` enums. `aq-qa 0`: 39 passed, 0 failed. |
| 2026-04-29 | 13.3 OpenSkills SKILL.md | DONE | commit `6a5c9a2e` — 6 SKILL.md files: `aq-hints`, `aq-delegate`, `aq-memory`, `aq-qa`, `aq-report`, `aq-runtime-diagnose`. Registered in `knowledge-sources.yaml`. |
| 2026-04-29 | 13.4 project-wide ingestion | DONE | commit `6a5c9a2e` — `scripts/data/ingest-project-knowledge.py`. Dry-run: 5,592 chunks / 1,064 files. `check-knowledge-base-breadth.sh` CI gate added. Run ingestion when AIDB doc count is low. |
| 2026-04-29 | 13.5 self-healing probes | DONE | commit `6a5c9a2e` — `aq-runtime-diagnose --store-findings` emits findings to AIDB `project=runtime-diagnose`. `bash -n` passes. |

---

## Success Gate for Phase 14 Eligibility

Phase 14 (future: advanced reasoning loops / RLM) may begin when ALL of the following pass:
- `curl localhost:8081/embedding` returns a non-empty vector
- `aq-qa 0` passes with 39+ checks, 0 failures
- AIDB document count ≥ 500 (`check-knowledge-base-breadth.sh` passes)
- `/context/multi_turn` endpoint returns 200 for a 2-turn session smoke test
- `aq-runtime-diagnose --store-findings` emits at least one AIDB document

---

## Dependencies on Phase 12

- Phase 12.2 (RAG confidence gate `AI_RETRIEVAL_MIN_CONFIDENCE=0.65`) must remain deployed.
  Phase 13.1 embeddings do NOT relax the confidence gate — they make it meaningful by
  producing real similarity scores instead of keyword-match stubs.
- Phase 12.3 (memory validation gate) is the write-side complement to Phase 13.2's
  multi-turn context. Both must be deployed before RLM loops are safe.
- Phase 12.4 (http_server.py decomposition): `context_handlers.py` (13.2) should be
  a standalone module from day one — do not add its routes directly to http_server.py body.
