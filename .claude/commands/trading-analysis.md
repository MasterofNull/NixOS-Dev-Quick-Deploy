<!--
Skill: trading-analysis
Role: implementer
Inputs: ticker, date (optional), options
Outputs: multi-agent stock analysis report
Example: /trading-analysis AAPL
-->
# /trading-analysis — Multi-Agent Stock Analysis Command

## Trigger
`/trading-analysis <TICKER> [DATE] [options]`

## Description
Invokes the tradingagents 5-team pipeline to analyze a stock. All agents
(market analyst, fundamentals analyst, news analyst, sentiment analyst,
bull researcher, bear researcher, trader, risk manager, portfolio manager)
collaborate to produce a final BUY/HOLD/SELL decision.

**Agent-agnostic**: all analysis happens via HTTP — callable by any runtime.

## Usage Examples
```bash
/trading-analysis AAPL
/trading-analysis NVDA 2026-05-01
/trading-analysis TSLA --analysts market,fundamentals --rounds 2
/trading-analysis MSFT --quick    # market signal only
```

## Tool Sequence

```
1. GET /trading/tools                           # discover available tools
2. GET /hints?q=trading+analysis+<TICKER>       # harness hints
3. GET /trading/forecast?ticker=X&date=Y        # quick signal (optional)
4. GET /trading/analyze?ticker=X&date=Y         # full 5-team pipeline
5. POST /memory/recall {query:"<TICKER>"}        # prior decisions context
6. POST /feedback {result, rating}              # capture outcome
```

## Full Pipeline
```
Analysts (parallel)
  ├── market_analyst      → OHLCV + technical indicators (SMA, MACD, RSI, Bollinger)
  ├── fundamentals_analyst → balance sheet, cash flow, income statement
  ├── news_analyst        → headlines, insider transactions, macro events
  └── sentiment_analyst   → headline tone, fear/greed signals

Researchers (sequential, debate loop)
  ├── bull_researcher     → growth case, competitive advantages, catalyst
  └── bear_researcher     → downside risk, valuation concerns, headwinds

Trader
  └── trader_agent        → FINAL TRANSACTION PROPOSAL: BUY/HOLD/SELL

Risk Management
  └── risk_manager        → volatility, liquidity, drawdown, stop-loss check

Portfolio Manager
  └── portfolio_manager   → PORTFOLIO DECISION: APPROVED/MODIFIED/REJECTED
```

## HTTP API (any agent)
```bash
# Full analysis
curl "http://127.0.0.1:8003/trading/analyze?ticker=AAPL&date=2026-05-01"

# Quick signal
curl "http://127.0.0.1:8003/trading/forecast?ticker=AAPL&date=2026-05-01"

# Tool discovery
curl "http://127.0.0.1:8003/trading/tools"

# Researcher debate round
curl -X POST "http://127.0.0.1:8003/trading/debate" \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL","trade_date":"2026-05-01","market_report":"..."}'
```

## CLI
```bash
# Run via aq-trading script
aq-trading AAPL 2026-05-01
aq-trading AAPL 2026-05-01 --quick
aq-trading AAPL 2026-05-01 --analysts market,fundamentals --rounds 2
```

## Output
Returns JSON with:
- All 4 analyst reports
- Debate history (bull/bear arguments)
- Trader proposal with entry/stop/target
- Risk assessment with APPROVED/REDUCED/REJECTED
- Final portfolio decision with position size

## Skill File
`scripts/ai/skills/tradingagents.skill.md`

## Source
Adapted from https://github.com/tauricresearch/tradingagents
