# Tool Selection Matrix — Agent-Agnostic Auto-Selection Guide

All tools in this matrix are accessible to **every agent and model** in the pool
via the hybrid coordinator HTTP API (`http://127.0.0.1:8003`).

No agent-specific CLIs, no hard-coded runtimes. Any agent that can make HTTP
requests can use any tool in this catalog.

---

## How Auto-Selection Works

1. Agent/orchestrator calls `GET /hints?q=<task>` → receives ranked tool recommendations
2. `tooling_manifest.py` matches task keywords → selects tool subset
3. `aq-delegate` injects tool catalog block into ALL delegated prompts
4. Agent calls appropriate HTTP endpoints directly

---

## Universal Tool Catalog

### Core Harness Tools (always available)

| Tool | Endpoint | Method | When to Use |
|------|----------|--------|-------------|
| `hints` | `/hints?q=<task>` | GET | **ALWAYS FIRST** — ranked workflow hints |
| `discovery` | `/discovery/capabilities` | GET | Discover available stack capabilities |
| `route_search` | `/query` | POST | RAG retrieval + LLM synthesis |
| `memory_recall` | `/memory/recall` | POST | Prior session memory |
| `feedback` | `/feedback` | POST | Capture corrections/ratings |
| `health` | `/health` | GET | Stack health check |
| `status` | `/status` | GET | Service status |

### Orchestration Tools

| Tool | Endpoint | Method | When to Use |
|------|----------|--------|-------------|
| `ai_coordinator_delegate` | `/control/ai-coordinator/delegate` | POST | Delegate to runtime lane |
| `loop_orchestrate` | `/workflow/orchestrate` | POST | Long-running multi-agent work |
| `loop_status` | `/workflow/orchestrate/{task_id}` | GET | Poll loop status |
| `workflow_plan` | `/workflow/plan` | POST | Structured task planning |
| `shared_skill_registry` | `/control/ai-coordinator/skills` | GET | List registered skills |

### Quality/Validation Tools

| Tool | Endpoint | Method | When to Use |
|------|----------|--------|-------------|
| `qa_check` | `mcp://run_qa_check` | - | Run aq-qa phases |
| `harness_eval` | `/harness/eval` | POST | Deterministic eval scorecard |
| `learning_stats` | `/learning/stats` | GET | Learning pipeline health |
| `agent_lessons_registry` | `/control/ai-coordinator/lessons` | GET | Inspect persisted lessons |

---

## Domain-Specific Tools

### Frontend Design (impeccable — Phase 24)

**Trigger keywords**: design, ui, ux, frontend, css, component, layout, typography,
color, animation, responsive, impeccable, audit, critique, polish, accessibility

| Tool | Endpoint | Method | Description |
|------|----------|--------|-------------|
| `impeccable_audit` | `/control/ai-coordinator/skills` | GET | Design audit/critique/polish/craft |
| `impeccable_reference` | `/query` | POST | Retrieve design reference docs from AIDB |

**Tool sequence for design tasks:**
```
1. GET  /hints?q=impeccable+<command>
2. POST /query {query:"<command> reference", project:"impeccable-design", limit:3}
3. GET  /control/ai-coordinator/skills  → find impeccable skill
4. Invoke skill command (audit|critique|polish|craft|animate|colorize|typeset)
5. npx impeccable detect <target>  (CLI anti-pattern scan)
6. POST /feedback {result, rating}
```

**35 reference domains in AIDB (project: impeccable-design)**:
typography, color-and-contrast, spatial-design, motion-design,
interaction-design, responsive-design, ux-writing, cognitive-load,
audit, critique, polish, craft, animate, colorize, typeset, layout,
shape, brand, product, heuristics-scoring, personas, delight, overdrive,
adapt, bolder, quieter, distill, harden, onboard, live, document, extract, clarify

**Design constraints always enforced**:
- OKLCH color space (never pure black/white)
- Body text ≤ 75 chars/line
- Scale ratio ≥ 1.25 between hierarchy levels
- Ease-out exponential for motion
- prefers-reduced-motion respected
- No layout property animations

**Anti-patterns that trigger a FAIL**:
gradient-text, glassmorphism-overuse, side-stripe-borders, hero-metric-template,
identical-card-grid, modal-first, layout-animation, missing-reduced-motion,
pure-black-white, system-default-font

---

### Financial Trading Analysis (tradingagents — Phase 24)

**Trigger keywords**: trade, trading, stock, ticker, market analysis, portfolio,
buy, sell, hold, financial, earnings, fundamentals, technical indicators,
bull, bear, equity, ohlcv, macd, rsi, bollinger, sentiment analysis

| Tool | Endpoint | Method | Description |
|------|----------|--------|-------------|
| `trading_tools` | `/trading/tools` | GET | Tool discovery — all financial tools |
| `trading_forecast` | `/trading/forecast?ticker=X&date=Y` | GET | Quick market signal |
| `trading_analyze` | `/trading/analyze?ticker=X&date=Y` | GET | Full 5-team analysis |
| `trading_debate` | `/trading/debate` | POST | Trigger researcher debate round |
| `trading_history` | `/trading/history?ticker=X` | GET | Past decisions for ticker |
| `route_search` | `/query` | POST | Trading knowledge from AIDB |

**Tool sequence for trading tasks:**
```
1. GET  /trading/tools                    — discover what's available
2. GET  /hints?q=trading+analysis+<TICKER>
3. GET  /trading/forecast?ticker=X&date=Y — quick signal first
4. GET  /trading/analyze?ticker=X&date=Y&analysts=market,fundamentals,news,sentiment
5. POST /memory/recall {query:"<TICKER> past decisions"}
6. POST /feedback {result, rating}
```

**5-team agent pipeline:**
```
Analysts → Researchers (debate) → Trader → Risk Manager → Portfolio Manager
```

**Financial data tools (called internally by agents):**

| Tool | Data Source | What it Returns |
|------|-------------|-----------------|
| `get_stock_data` | yfinance/Alpha Vantage | OHLCV price history |
| `get_indicators` | yfinance | SMA50/200, EMA10, MACD, RSI, Bollinger, ATR |
| `get_fundamentals` | yfinance | P/E, EPS, revenue, margins, debt/equity |
| `get_balance_sheet` | yfinance | Assets, liabilities, equity, cash |
| `get_cashflow` | yfinance | Operating/investing/financing flows |
| `get_income_statement` | yfinance | Revenue, gross profit, EBIT, net income |
| `get_news` | yfinance | Recent headlines |
| `get_insider_transactions` | yfinance | Insider buy/sell activity |

---

## Standard Tool Sequences by Task Type

### Task: Implement a feature
```
1. GET  /hints?q=<feature description>
2. POST /query {query: "<feature> existing patterns", mode: "hybrid"}
3. POST /memory/recall {query: "<feature>"}
4. Implement (aq-delegate qwen or direct)
5. POST /query (validate against known patterns)
6. GET  /harness/eval (acceptance check)
7. POST /feedback {result, rating}
```

### Task: Debug a service failure
```
1. GET  /hints?q=<error or service name>
2. GET  /health
3. GET  /status
4. POST /query {query: "<error message>", mode: "hybrid"}
5. GET  /control/ai-coordinator/lessons (prior lessons for this error type)
6. Investigate + fix
7. POST /feedback {correction, rating}
```

### Task: Design a UI component
```
1. GET  /hints?q=impeccable+audit
2. GET  /control/ai-coordinator/skills  (find impeccable skill)
3. POST /query {query: "component design reference", project: "impeccable-design"}
4. Apply impeccable principles
5. npx impeccable detect <output>
6. POST /feedback {result}
```

### Task: Analyze a stock
```
1. GET  /trading/tools                 (discover tools)
2. GET  /hints?q=trading+<TICKER>
3. GET  /trading/forecast?ticker=X&date=Y    (quick signal)
4. GET  /trading/analyze?ticker=X&date=Y     (full pipeline)
5. POST /feedback {result, rating}
```

### Task: NixOS config change
```
1. GET  /hints?q=nixos+<service or module>
2. POST /query {query: "NixOS <module> pattern"}
3. Read nix/modules/core/options.nix (single source of truth for ports/URLs)
4. Edit nix/modules/... (never hardcode values)
5. GET  /harness/eval
6. POST /feedback
```

---

## Agent Routing Guide

| Agent | Best For | Context Injection |
|-------|----------|-------------------|
| qwen (local) | Multi-file implementation, Nix config | Full context via aq-delegate |
| local llama.cpp | Direct HTTP tool calls, synthesis | HTTP API at :8003 |
| gemini | Web research, broad context | HTTP API + web research tools |
| any future model | Any task | HTTP API at :8003 — all tools accessible |

**Key principle**: No agent is hard-coded. Every agent gets the full tool catalog
via `aq-delegate` context injection and can discover tools via `GET /trading/tools`,
`GET /control/ai-coordinator/skills`, and `GET /hints`.

---

## Adding New Tools

1. Create handler in `ai-stack/mcp-servers/hybrid-coordinator/<name>_handlers.py`
2. Add `register_routes(app)` and wire in `http_server.py`
3. Add keyword detection block in `tooling_manifest.py` → `workflow_tool_catalog()`
4. Add runtime spec in `_TOOL_RUNTIME_SPECS` dict
5. Add keyword blocks in `scripts/ai/aq-delegate`
6. Create skill file in `scripts/ai/skills/<name>.skill.md`
7. Create command in `.claude/commands/<name>.md`
8. Ingest reference docs into AIDB
9. Update this matrix

**All new tools must be exposed via HTTP REST — not CLI-only or agent-specific.**
