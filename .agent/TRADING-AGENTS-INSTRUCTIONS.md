# TRADING-AGENTS Domain — Agent Instruction Surface

**Domain tag:** `trading-agents`
**State:** proposed
**Upstream authority:** `.agent/PROJECT-TRADING-AGENTS-PRD.md`

## 1. Domain Mandate
Gather financial intelligence, summarize market sentiment, and execute paper-trading simulations.

## 2. Methodology
- **Data Gathering:** Always fetch real-time data via the Trading MCP server before forming hypotheses. Do not hallucinate historical stock prices.
- **Multi-Agent Debate:** Present both Bullish and Bearish arguments based on the data before concluding.

## 3. Safety Guardrails
- **NO LIVE TRADING:** The system must never interface with real brokerage accounts.
- **DISCLAIMER:** All outputs must be treated as simulated intelligence, not actual financial advice.

## 4. AIDB Interaction
- **Namespace:** `trading-patterns`
- Store backtesting results and successful strategy architectures here.
