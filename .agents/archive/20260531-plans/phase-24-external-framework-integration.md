# Phase 24 — External Framework Integration
# impeccable (design intelligence) + tradingagents (multi-agent finance)

## Objective
Integrate features, tools, logic, and workflows from two external repos into the
local AI harness. All agent teams are pre-loaded with the correct tools and usage
order for each task, phase, and slice.

Source repos:
- https://github.com/pbakaus/impeccable  — frontend design intelligence system
- https://github.com/tauricresearch/tradingagents — multi-agent trading framework

## Acceptance Criteria
- [ ] impeccable skill callable via `/impeccable` in Claude Code
- [ ] impeccable reference docs (35 files) ingested into AIDB
- [ ] Trading agents runnable via `aq-trading <TICKER> <DATE>`
- [ ] All 5 trading teams operational (analysts, researchers, trader, risk, portfolio)
- [ ] Financial data tools registered in MCP bridge
- [ ] `tooling_manifest.py` routes design + trading tasks to correct tools
- [ ] `aq-delegate` injects tool recommendations for design/trading tasks
- [ ] Tool Selection Matrix published at `docs/agent-guides/50-TOOL-SELECTION-MATRIX.md`
- [ ] All Python files pass `python3 -m py_compile`
- [ ] All changes committed with proper Co-Author trailer

---

## P24-001 — impeccable Skill Integration
**Owner**: qwen (implementation) / Claude (review)
**Slice**: Design intelligence — skill files, command contract, AIDB ingestion

### Tasks
1. **P24-001a** — Create `.claude/skills/impeccable/SKILL.md` (import from repo)
2. **P24-001b** — Create `.claude/commands/impeccable.md` (command contract)
3. **P24-001c** — Create `scripts/ai/skills/impeccable.skill.md` (harness skill)
4. **P24-001d** — Create `scripts/ai/ingest-impeccable-references.sh` (AIDB ingestion)
5. **P24-001e** — Run ingestion, verify ≥30 docs in AIDB project `impeccable-design`

### Tool Sequence for Agents
```
1. aq-hints "impeccable design audit frontend"
2. /impeccable audit (via .claude/commands/impeccable.md)
3. POST /query {query, project: "impeccable-design", mode: "hybrid"}
4. aq-delegate qwen "apply impeccable critique to <component>"
5. aq-qa 0 (validate)
```

### Files to Create
- `.claude/skills/impeccable/SKILL.md`
- `.claude/commands/impeccable.md`
- `scripts/ai/skills/impeccable.skill.md`
- `scripts/ai/ingest-impeccable-references.sh`

---

## P24-002 — tradingagents Core Scaffold
**Owner**: qwen (implementation) / Claude (review)
**Slice**: Multi-agent trading framework — local Qwen3.6-35B adaptation

### Architecture (mirrors tradingagents repo)
```
ai-stack/trading-agents/
├── __init__.py
├── config.py                    # local LLM config (adapts from default_config.py)
├── schemas.py                   # shared state / data models
├── analysts/
│   ├── __init__.py
│   ├── market_analyst.py        # OHLCV + technical indicators
│   ├── fundamentals_analyst.py  # balance sheet, cash flow, income
│   ├── sentiment_analyst.py     # social/Reddit/news sentiment
│   └── news_analyst.py          # macro events, insider transactions
├── researchers/
│   ├── __init__.py
│   ├── bull_researcher.py       # growth case builder
│   └── bear_researcher.py       # risk/downside case builder
├── trader/
│   ├── __init__.py
│   └── trader_agent.py          # BUY/HOLD/SELL synthesizer
├── risk_mgmt/
│   ├── __init__.py
│   └── risk_manager.py          # volatility, liquidity, drawdown
├── portfolio/
│   ├── __init__.py
│   └── portfolio_manager.py     # final trade approval/rejection
├── dataflows/
│   ├── __init__.py
│   └── interface.py             # yfinance + Alpha Vantage tool functions
└── graph/
    ├── __init__.py
    ├── state.py                  # AgentState TypedDict
    ├── conditional_logic.py     # routing decisions
    └── trading_graph.py         # LangGraph-style orchestration
```

### Tasks
1. **P24-002a** — Scaffold `ai-stack/trading-agents/` directory tree
2. **P24-002b** — Implement `config.py` adapted for local llama.cpp endpoint
3. **P24-002c** — Implement `schemas.py` + `graph/state.py`
4. **P24-002d** — Implement 4 analyst agents (market, fundamentals, sentiment, news)
5. **P24-002e** — Implement 2 researcher agents (bull, bear with debate loop)
6. **P24-002f** — Implement trader, risk manager, portfolio manager
7. **P24-002g** — Implement `dataflows/interface.py` (yfinance tools)
8. **P24-002h** — Implement `graph/trading_graph.py` orchestrator
9. **P24-002i** — Create `scripts/ai/aq-trading` CLI entry point

### Tool Sequence for Agents
```
1. aq-hints "trading analysis financial agents"
2. GET /world/forecast (predict likely query patterns)
3. POST /query {query: "trading signals <TICKER>", mode: "hybrid"}
4. aq-trading <TICKER> <DATE> --analysts market,fundamentals,news,sentiment
5. POST /memory/recall {query: "prior trading decisions <TICKER>"}
6. POST /feedback {result, rating}
```

### Files to Create
- All files in `ai-stack/trading-agents/` (full tree above)
- `scripts/ai/aq-trading`

---

## P24-003 — MCP Tool Registration (Financial Data)
**Owner**: qwen (implementation) / Claude (review)
**Slice**: Register trading dataflow tools in MCP bridge

### Tasks
1. **P24-003a** — Create `ai-stack/mcp-servers/hybrid-coordinator/trading_handlers.py`
   - `GET /trading/analyze` — run full 5-team analysis for ticker
   - `GET /trading/forecast` — quick signal only (single analyst)
   - `POST /trading/debate` — trigger researcher debate round
2. **P24-003b** — Register routes in `route_handler.py`
3. **P24-003c** — Add trading tool specs to `tooling_manifest.py`

### Files to Create/Edit
- `ai-stack/mcp-servers/hybrid-coordinator/trading_handlers.py` (new)
- `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py` (edit: add register_routes)
- `ai-stack/mcp-servers/hybrid-coordinator/tooling_manifest.py` (edit: trading + design keywords)

---

## P24-004 — Tool Auto-Selection Enhancement
**Owner**: Claude (direct)
**Slice**: Enhance `aq-delegate` + `tooling_manifest` for automatic tool provision

### Tasks
1. **P24-004a** — Update `tooling_manifest.py`: add design and trading keyword blocks
2. **P24-004b** — Update `scripts/ai/aq-delegate`: inject tool manifest sections
3. **P24-004c** — Create `docs/agent-guides/50-TOOL-SELECTION-MATRIX.md`

### Design keyword triggers
```
"design", "ui", "ux", "frontend", "css", "component", "layout",
"typography", "color", "animation", "responsive", "impeccable", "audit ui"
→ tools: impeccable_audit, impeccable_critique, impeccable_polish,
         route_search (project: impeccable-design)
```

### Trading keyword triggers
```
"trade", "trading", "stock", "ticker", "market", "analyst", "portfolio",
"buy", "sell", "hold", "financial", "earnings", "fundamentals", "sentiment"
→ tools: trading_analyze, trading_forecast, trading_debate,
         route_search (project: trading-knowledge)
```

---

## P24-005 — Skill Files + Command Contracts
**Owner**: Claude (direct)
**Slice**: Wire new capabilities into harness skill registry + command system

### Tasks
1. **P24-005a** — Create `scripts/ai/skills/impeccable.skill.md`
2. **P24-005b** — Create `scripts/ai/skills/tradingagents.skill.md`
3. **P24-005c** — Create `.claude/commands/trading-analysis.md`

---

## P24-006 — AIDB Knowledge Ingestion
**Owner**: qwen (execution)
**Slice**: Ingest both repos' reference knowledge into AIDB

### Tasks
1. **P24-006a** — Ingest impeccable reference docs (35 files, project: `impeccable-design`)
2. **P24-006b** — Ingest tradingagents docs + agent prompts (project: `trading-knowledge`)
3. **P24-006c** — Verify: `GET /documents?project=impeccable-design` ≥ 30 docs
4. **P24-006d** — Verify: `GET /documents?project=trading-knowledge` ≥ 10 docs

---

## P24-007 — Validation Gate
**Owner**: Claude (direct)

### Tasks
1. **P24-007a** — `for f in ai-stack/trading-agents/**/*.py; do python3 -m py_compile "$f"; done`
2. **P24-007b** — `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/trading_handlers.py`
3. **P24-007c** — `bash -n scripts/ai/aq-trading`
4. **P24-007d** — `aq-qa 0` — all existing checks still pass
5. **P24-007e** — Commit all with: `feat(integration): impeccable + tradingagents framework integration`

---

## Delegation Map

| Slice | Delegate To | Validation |
|-------|------------|-----------|
| P24-001 impeccable skill files | Direct (Claude) | Read SKILL.md, check commands |
| P24-002 tradingagents scaffold | `aq-delegate qwen` | py_compile each file |
| P24-003 MCP handlers | `aq-delegate qwen` | py_compile, check routes |
| P24-004 manifest + delegate | Direct (Claude) | bash -n, python3 compile |
| P24-005 skill files | Direct (Claude) | Read, validate format |
| P24-006 AIDB ingestion | `aq-delegate qwen` | GET /documents count |
| P24-007 validation | Direct (Claude) | All gates pass |

---

## Status Tracker

| Task | Status | Notes |
|------|--------|-------|
| P24-001a .claude/skills/impeccable/SKILL.md | COMPLETE | |
| P24-001b .claude/commands/impeccable.md | COMPLETE | |
| P24-001c scripts/ai/skills/impeccable.skill.md | COMPLETE | |
| P24-001d ingest-impeccable-references.sh | COMPLETE | |
| P24-002a-h trading-agents scaffold | COMPLETE | |
| P24-002i aq-trading CLI | COMPLETE | |
| P24-003a-c trading_handlers.py + manifest | COMPLETE | |
| P24-004a-c auto-selection enhancement | COMPLETE | |
| P24-005a-c skill files + commands | COMPLETE | |
| P24-006a-d AIDB ingestion | PENDING | requires service |
| P24-007a-e validation + commit | PENDING | |
