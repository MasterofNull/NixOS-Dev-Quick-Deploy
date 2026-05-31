# PRD — trading-agents Domain Activation

**Domain tag:** `trading-agents`
**Status:** Proposed — Phase 60
**Authors:** Gemini 2.0 Pro (Orchestrator)

## 1. Goal
Establish `trading-agents` domain for autonomous market intelligence, sentiment analysis, and simulated paper-trading using local LLMs.

## 2. Architecture
- **Data Layer:** `yfinance` for OHLCV data, SEC EDGAR API for filings.
- **Analysis:** Multi-Agent Debate (MAD) between Bull/Bear personas running concurrently on local Qwen3-35B.
- **Execution:** Paper-trading ledger via MCP state storage.
- **AIDB Namespace:** `trading-patterns`

## 3. Acceptance Criteria
1. Domain registered in lifecycle.
2. Trading MCP server implemented (fetching ticker data).
3. Successful simulated paper trade executed and logged.
