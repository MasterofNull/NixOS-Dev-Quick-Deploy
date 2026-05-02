# SKILL: tradingagents

**Purpose**: Multi-agent financial trading analysis framework. Deploys 5 specialized
agent teams (analysts, researchers, trader, risk management, portfolio manager) to
collaboratively analyze stocks and produce BUY/HOLD/SELL decisions.

**Source**: Adapted from tauricresearch/tradingagents
**Backend**: Local Qwen3.6-35B via llama.cpp (no remote API required)
**AIDB Project**: `trading-knowledge`
**Module**: `ai-stack/trading-agents/`

## Synopsis
```bash
# CLI
aq-trading <TICKER> <DATE> [--analysts <csv>] [--rounds <n>] [--quick]

# HTTP API (any agent/model)
GET http://127.0.0.1:8003/trading/analyze?ticker=AAPL&date=2026-05-01
GET http://127.0.0.1:8003/trading/forecast?ticker=AAPL&date=2026-05-01
GET http://127.0.0.1:8003/trading/tools
POST http://127.0.0.1:8003/trading/debate
```

## Agent Teams

| Team | Agents | Role |
|------|--------|------|
| Analysts | market, fundamentals, news, sentiment | Gather signals from 4 domains |
| Researchers | bull_researcher, bear_researcher | Debate investment case |
| Trader | trader_agent | Synthesize → BUY/HOLD/SELL proposal |
| Risk Mgmt | risk_manager | Assess volatility, liquidity, drawdown |
| Portfolio | portfolio_manager | Final approval/rejection |

## Tool Sequence (Standard)

```
Phase 1 — Discover
  GET /trading/tools                    — list all financial data tools
  GET /hints?q=trading+<ticker>         — harness hints

Phase 2 — Quick Signal
  GET /trading/forecast?ticker=X&date=Y — market technicals only (fast)

Phase 3 — Full Analysis
  GET /trading/analyze?ticker=X&date=Y&analysts=market,fundamentals,news,sentiment

Phase 4 — Retrieve Context
  POST /query {query:"<ticker> prior decisions", project:"trading-knowledge"}
  POST /memory/recall {query:"<ticker> <date>"}

Phase 5 — Validate + Capture
  POST /feedback {result, rating}
```

## Financial Data Tools

| Tool | Description |
|------|-------------|
| `get_stock_data` | OHLCV price history (yfinance or Alpha Vantage) |
| `get_indicators` | SMA, EMA, MACD, RSI, Bollinger Bands, ATR |
| `get_fundamentals` | P/E, revenue, margins, sector |
| `get_balance_sheet` | Assets, liabilities, equity, cash, debt |
| `get_cashflow` | Operating/investing/financing cash flows |
| `get_income_statement` | Revenue, gross profit, EBIT, net income |
| `get_news` | Recent ticker-specific headlines |
| `get_insider_transactions` | Insider buy/sell activity |

## Configuration
All settings via env vars (no hardcoded values):
- `LLAMA_BASE_URL` — llama.cpp endpoint (default: http://127.0.0.1:8080)
- `TRADING_DATA_VENDOR` — yfinance (default) or alpha_vantage
- `ALPHA_VANTAGE_API_KEY` — required only for alpha_vantage vendor
- `TRADING_MAX_DEBATE_ROUNDS` — researcher debate iterations (default: 1)
- `TRADING_ANALYST_TYPES` — which analysts to run (default: all 4)

## Output Format
```json
{
  "ticker": "AAPL",
  "trade_date": "2026-05-01",
  "market_report": "...",
  "fundamentals_report": "...",
  "news_report": "...",
  "sentiment_report": "...",
  "bull_argument": "...",
  "bear_argument": "...",
  "trader_decision": "FINAL TRANSACTION PROPOSAL: **BUY**\n...",
  "risk_assessment": "...",
  "final_decision": "PORTFOLIO DECISION: APPROVED\nFinal Action: BUY\n...",
  "position_size": 0.4
}
```

## All-Agent Accessibility
This skill is designed to be **agent-agnostic** and **model-agnostic**:
- All functionality exposed via HTTP REST endpoints
- No Claude Code dependency
- Callable by qwen, gemini, local llama.cpp, any future agent
- Tool discovery via `GET /trading/tools` (no source reading required)
- Results always JSON — machine-parseable by any runtime

## Exit Criteria
- [ ] `GET /trading/tools` returns tool catalog
- [ ] `GET /trading/forecast?ticker=AAPL&date=<today>` returns market signal
- [ ] `GET /trading/analyze?ticker=AAPL&date=<today>` returns final_decision
- [ ] Decision logged to `~/.tradingagents/logs/`
