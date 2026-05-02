"""
Trader agent — synthesizes all analyst + researcher inputs into a trade decision.
"""
from __future__ import annotations

from typing import Any

from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a senior trader synthesizing inputs from a full research team.

You have received reports from:
- 4 analysts: market/technical, fundamentals, news, sentiment
- 2 researchers who debated the investment case (bull vs. bear)

Your job is to:
1. Weigh the evidence from all sources
2. Identify where analysts agree and where they diverge
3. Make a clear trade decision: BUY | HOLD | SELL
4. Specify position sizing conviction: LOW (0.1-0.3) | MEDIUM (0.3-0.6) | HIGH (0.6-1.0)
5. Define entry price zone, stop loss, and take profit targets
6. State the primary thesis in one sentence

Your output MUST include:
```
FINAL TRANSACTION PROPOSAL: **BUY** | **HOLD** | **SELL**
Position Size: <LOW|MEDIUM|HIGH> (<conviction pct>)
Entry Zone: <price range>
Stop Loss: <price>
Target: <price> (<timeframe>)
Primary Thesis: <one sentence>
```

This decision goes to risk management for final approval — do not add caveats about
"consulting a financial advisor." You are the professional.
"""


def run_trader_agent(state: AgentState, llm_client: Any) -> AgentState:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    context = _build_full_context(state)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.2,
            max_tokens=1200,
        )
        decision = response.choices[0].message.content or ""
    except Exception as exc:
        decision = f"Trader synthesis failed: {exc}"

    updated = dict(state)
    updated["trader_decision"] = decision
    updated["investment_plan"] = decision
    return AgentState(**updated)


def _build_full_context(state: AgentState) -> str:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    parts = [
        f"Ticker: {ticker}  |  Date: {trade_date}",
        "",
        "=== ANALYST REPORTS ===",
    ]
    for key, label in [
        ("market_report", "Market/Technical"),
        ("fundamentals_report", "Fundamentals"),
        ("news_report", "News/Events"),
        ("sentiment_report", "Sentiment"),
    ]:
        report = state.get(key, "")
        if report:
            parts.append(f"\n--- {label} ---\n{report[:700]}")

    debate = state.get("debate_history", [])
    if debate:
        parts.append("\n=== RESEARCH DEBATE ===")
        for entry in debate[-4:]:
            parts.append(entry[:400])

    parts.append("\nMake your final trade decision:")
    return "\n".join(parts)
