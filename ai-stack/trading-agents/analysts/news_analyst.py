"""
News analyst agent — macro events, company news, insider transactions.
"""
from __future__ import annotations

from typing import Any

from ..dataflows.interface import get_news, get_global_news, get_insider_transactions
from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a news analyst monitoring macro and company-specific events.

Analyze recent news and insider activity to assess event-driven risk and opportunity.

Focus on:
1. Breaking company news (earnings, guidance, management changes, litigation)
2. Macro events affecting the sector (rates, regulation, geopolitics)
3. Insider trading patterns (buy/sell volume, timing relative to events)
4. Analyst upgrades/downgrades if mentioned
5. Sentiment tone of coverage (positive / negative / neutral)

Output requirements:
- Key events ranked by market impact potential
- Insider transaction summary with interpretation
- Markdown table of top 5 news items with date, headline, impact assessment
- Conclude with: BULLISH | BEARISH | NEUTRAL and confidence score 0-1
"""


def run_news_analyst(state: AgentState, llm_client: Any) -> AgentState:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    news = get_news(ticker, max_items=15)
    global_news = get_global_news(max_items=5)
    insider = get_insider_transactions(ticker)

    context = _format_context(ticker, trade_date, news, global_news, insider)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
        )
        report = response.choices[0].message.content or ""
    except Exception as exc:
        report = f"News analysis failed: {exc}"

    updated = dict(state)
    updated["news_report"] = report
    return AgentState(**updated)


def _format_context(ticker, trade_date, news, global_news, insider) -> str:
    news_items = news.get("news", [])
    insider_txns = insider.get("transactions", [])

    lines = [
        f"Ticker: {ticker}",
        f"Analysis date: {trade_date}",
        "",
        f"=== COMPANY NEWS ({len(news_items)} items) ===",
    ]
    for item in news_items[:10]:
        lines.append(f"  [{item.get('publisher','')}] {item.get('title','')}")
        if item.get("summary"):
            lines.append(f"    Summary: {item['summary'][:150]}")

    lines += ["", "=== INSIDER TRANSACTIONS ==="]
    for txn in insider_txns[:8]:
        lines.append(f"  {txn}")

    lines += ["", "Please produce a comprehensive news and event analysis report."]
    return "\n".join(lines)
