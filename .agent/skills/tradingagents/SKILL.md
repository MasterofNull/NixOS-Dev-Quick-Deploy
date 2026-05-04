---
name: tradingagents
description: Multi-agent financial trading analysis. Deploys 5 specialized teams (analysts, researchers, trader, risk manager, portfolio manager) on local Qwen3.6-35B to produce BUY/HOLD/SELL decisions. Agent-agnostic — all analysis via HTTP REST API at :8003.
tags: [trading, finance, stocks, market-analysis, multi-agent, llm, portfolio]
version: "1.0.0"
source_url: https://github.com/tauricresearch/tradingagents
---

# Skill: tradingagents

## Description
Multi-agent financial trading framework adapted from https://github.com/tauricresearch/tradingagents.
Runs entirely on local Qwen3.6-35B via llama.cpp — no remote API keys required (yfinance for data).
**Agent-agnostic**: all 5-team analysis accessible via HTTP REST — callable by any agent/model/runtime.

## When to Use
- Analyzing a stock for a trading decision
- Getting technical indicators, fundamentals, news, sentiment for any ticker
- Running a structured bull/bear research debate
- Risk-adjusting a proposed trade
- Any task involving: trade, trading, stock, ticker, market analysis, portfolio, BUY/HOLD/SELL,
  financial, earnings, fundamentals, technical indicators, bull/bear, equity, OHLCV, MACD, RSI

## HTTP Invocation (any agent/model)

```bash
# Discover financial data tools
GET http://127.0.0.1:8003/trading/tools

# Quick market signal (market analyst only, fast)
GET http://127.0.0.1:8003/trading/forecast?ticker=AAPL&date=2026-05-01

# Full 5-team analysis
GET http://127.0.0.1:8003/trading/analyze?ticker=AAPL&date=2026-05-01

# Partial analysis (select analysts)
GET http://127.0.0.1:8003/trading/analyze?ticker=AAPL&date=2026-05-01&analysts=market,fundamentals

# Researcher debate round
POST http://127.0.0.1:8003/trading/debate
Body: {"ticker":"AAPL","trade_date":"2026-05-01","market_report":"..."}

# Past decisions
GET http://127.0.0.1:8003/trading/history?ticker=AAPL&limit=10

# Auto-select tools for a trading task
GET http://127.0.0.1:8003/tools/auto-select?task=analyze+AAPL+stock+trading+decision
```

## CLI

```bash
aq-trading AAPL 2026-05-01                        # full pipeline
aq-trading AAPL 2026-05-01 --quick                # market signal only
aq-trading AAPL --analysts market,fundamentals    # select analysts
aq-trading --tools                                 # list financial tools
aq-trading AAPL --history                          # past decisions
```

## 5-Team Pipeline

```
Phase 1 — Analysts (run in parallel by type)
  market_analyst      → OHLCV + SMA/EMA/MACD/RSI/Bollinger/ATR
  fundamentals_analyst → balance sheet, cash flow, income statement, P/E
  news_analyst        → recent headlines, insider transactions, macro events
  sentiment_analyst   → headline tone scoring, fear/greed signals

Phase 2 — Researcher Debate
  bull_researcher → growth case, competitive advantages, catalyst
  bear_researcher → downside risk, valuation concerns, sector headwinds
  (iterate for max_debate_rounds)

Phase 3 — Trader Synthesis
  trader_agent → FINAL TRANSACTION PROPOSAL: BUY | HOLD | SELL
                 with entry zone, stop loss, price target

Phase 4 — Risk Management
  risk_manager → volatility, liquidity, drawdown assessment
                 APPROVED | REDUCED | REJECTED

Phase 5 — Portfolio Approval
  portfolio_manager → PORTFOLIO DECISION: APPROVED | MODIFIED | REJECTED
                      with final position size (0.0 – 1.0)
```

## Available Financial Data Tools

| Tool | Description | Data Source |
|------|-------------|-------------|
| `get_stock_data` | OHLCV price history | yfinance / Alpha Vantage |
| `get_indicators` | SMA50/200, EMA10, MACD, RSI, Bollinger, ATR | yfinance |
| `get_fundamentals` | P/E, EPS, revenue, margins, debt/equity | yfinance |
| `get_balance_sheet` | Assets, liabilities, equity, cash | yfinance |
| `get_cashflow` | Operating/investing/financing flows | yfinance |
| `get_income_statement` | Revenue, gross profit, EBIT, net income | yfinance |
| `get_news` | Recent ticker headlines | yfinance |
| `get_insider_transactions` | Insider buy/sell activity | yfinance |

## Agent Execution Sequence

```
1. GET  /trading/tools                              # discover available tools
2. GET  /hints?q=trading+analysis+<TICKER>          # ranked hints
3. GET  /trading/forecast?ticker=X&date=Y           # quick signal
4. GET  /trading/analyze?ticker=X&date=Y            # full pipeline
5. POST /memory/recall {query:"<TICKER> decisions"} # prior decisions
6. POST /query {query:"<TICKER>", project:"trading-knowledge"} # knowledge
7. POST /feedback {result, rating}                  # capture outcome
```

## Configuration (env vars — never hardcoded)

- `LLAMA_BASE_URL` — llama.cpp endpoint (default: http://127.0.0.1:8080)
- `TRADING_DATA_VENDOR` — yfinance (default) or alpha_vantage
- `ALPHA_VANTAGE_API_KEY` — optional; enables alpha_vantage vendor
- `TRADING_MAX_DEBATE_ROUNDS` — researcher debate iterations (default: 1)
- `TRADING_ANALYST_TYPES` — analyst selection (default: all 4)

## AIDB Knowledge Base

Trading knowledge stored in project `trading-knowledge`.

```bash
# Ingest (run once)
scripts/ai/ingest-trading-knowledge.sh

# Query from any agent
curl -s http://127.0.0.1:8002/query \
  -H "X-API-Key: <aidb_key>" \
  -d '{"query":"<topic>","project":"trading-knowledge","limit":3}'
```

## Notes

- No Claude Code dependency — purely HTTP REST
- Runs on local Qwen3.6-35B; ~10-30 min for full pipeline at current hardware
- Skill registered in AIDB and discoverable via `GET /control/ai-coordinator/skills`
- Module: `ai-stack/trading-agents/` (Python package)
