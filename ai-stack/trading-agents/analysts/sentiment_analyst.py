"""
Sentiment analyst agent — social and market sentiment signals.
"""
from __future__ import annotations

from typing import Any

from ..dataflows.interface import get_news
from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a sentiment analyst specializing in market psychology.

Analyze available sentiment signals to assess crowd positioning and emotion.

Focus on:
1. News headline sentiment (tone, frequency, recency)
2. Implied retail vs. institutional sentiment divergence
3. Fear/greed indicators in news language
4. Contrarian signals (extreme sentiment as reversal indicator)
5. Social proof patterns in analyst commentary

Output requirements:
- Sentiment score: -1.0 (extreme fear) to +1.0 (extreme greed)
- Key sentiment drivers
- Contrarian assessment (is crowd sentiment extreme?)
- Markdown table: signal type, direction, strength, notes
- Conclude with: BULLISH | BEARISH | NEUTRAL and confidence score 0-1

Note: Without a social API key (Reddit, Twitter), use news headlines as proxy.
"""


def run_sentiment_analyst(state: AgentState, llm_client: Any) -> AgentState:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    news = get_news(ticker, max_items=20)
    headlines = [n.get("title", "") for n in news.get("news", [])]

    context = _format_context(ticker, trade_date, headlines)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.3,
            max_tokens=1200,
        )
        report = response.choices[0].message.content or ""
    except Exception as exc:
        report = f"Sentiment analysis failed: {exc}"

    updated = dict(state)
    updated["sentiment_report"] = report
    return AgentState(**updated)


def _format_context(ticker, trade_date, headlines) -> str:
    lines = [
        f"Ticker: {ticker}",
        f"Analysis date: {trade_date}",
        "",
        f"=== RECENT HEADLINES ({len(headlines)}) ===",
    ]
    for i, h in enumerate(headlines, 1):
        lines.append(f"  {i}. {h}")
    lines += ["", "Please produce a comprehensive sentiment analysis report."]
    return "\n".join(lines)
