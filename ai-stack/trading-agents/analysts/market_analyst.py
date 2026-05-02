"""
Market analyst agent — technical indicators and price patterns.
Ported from tauricresearch/tradingagents for local llama.cpp.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from ..dataflows.interface import get_stock_data, get_indicators
from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a market analyst specializing in technical analysis.
Your task is to analyze price action and technical indicators for a given stock
and produce a comprehensive market report.

Available indicators:
- Moving Averages: SMA50, SMA200, EMA10 (trend direction, momentum)
- MACD: line, signal, histogram (momentum divergence)
- RSI: overbought >70, oversold <30 (mean reversion signals)
- Bollinger Bands: upper/mid/lower (volatility, breakout detection)
- ATR: average true range (position sizing, stop loss)

Select the most relevant indicators for current market conditions.
Choose up to 8 that provide complementary insights without redundancy.

Output requirements:
1. Trend analysis with specific price levels
2. Momentum assessment
3. Support/resistance levels
4. Volume profile commentary
5. Markdown table summarizing key findings for traders
6. Conclude with one of: BULLISH | BEARISH | NEUTRAL and confidence score 0-1

Never mention "FINAL TRANSACTION PROPOSAL" — that is the trader's role.
"""


def run_market_analyst(state: AgentState, llm_client: Any) -> AgentState:
    """
    Execute market analysis node.
    Fetches price + indicator data, calls LLM, returns updated state.
    """
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    # Fetch data
    price_data = get_stock_data(ticker, _lookback(trade_date, 90), trade_date)
    indicator_data = get_indicators(ticker, trade_date)

    # Build context
    context = _format_market_context(ticker, trade_date, price_data, indicator_data)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        report = response.choices[0].message.content or ""
    except Exception as exc:
        report = f"Market analysis failed: {exc}"

    updated = dict(state)
    updated["market_report"] = report
    return AgentState(**updated)


def _format_market_context(
    ticker: str, trade_date: str, price_data: Dict, indicator_data: Dict
) -> str:
    lines = [
        f"Ticker: {ticker}",
        f"Analysis date: {trade_date}",
        "",
        "=== PRICE DATA (last 10 periods) ===",
    ]

    dates = price_data.get("dates", [])[-10:]
    closes = price_data.get("close", [])[-10:]
    volumes = price_data.get("volume", [])[-10:]
    for d, c, v in zip(dates, closes, volumes):
        lines.append(f"  {d}: close={c:.2f}  vol={v:,.0f}")

    lines += ["", "=== TECHNICAL INDICATORS ==="]
    skip = {"ticker", "trade_date", "error"}
    for k, v in indicator_data.items():
        if k in skip:
            continue
        if isinstance(v, float):
            lines.append(f"  {k}: {v:.4f}")
        else:
            lines.append(f"  {k}: {v}")

    lines += [
        "",
        "Please produce a comprehensive market analysis report.",
    ]
    return "\n".join(lines)


def _lookback(trade_date: str, days: int) -> str:
    from datetime import datetime, timedelta
    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    return (dt - timedelta(days=days)).strftime("%Y-%m-%d")
