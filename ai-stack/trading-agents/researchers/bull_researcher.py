"""
Bull researcher — builds the growth/upside investment case.
Engages in structured debate with the bear researcher.
"""
from __future__ import annotations

from typing import Any

from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a bullish investment researcher.

Your role is to build the strongest possible evidence-based case for buying {ticker}.

You have access to analyst reports covering: market technicals, company fundamentals,
recent news, and market sentiment.

Your bull case must:
1. Identify 3-5 key growth catalysts with specific data support
2. Highlight competitive advantages and moat strength
3. Address valuation — why current price is attractive
4. Refute bearish concerns directly with counter-evidence
5. Quantify upside potential (price target, timeline)

Debate rules:
- Engage DIRECTLY with any bear arguments presented
- Use specific numbers, not vague qualitative claims
- Acknowledge genuine risks but explain why they are manageable
- Maintain intellectual honesty — do not ignore strong counter-evidence

Format: structured argument with sections, end with confidence score 0-1.
"""


def run_bull_researcher(state: AgentState, llm_client: Any) -> AgentState:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    analyst_context = _build_analyst_context(state)
    bear_arg = state.get("bear_argument", "")
    debate_round = state.get("debate_round", 0)

    system = SYSTEM_PROMPT.format(ticker=ticker)

    user_content = f"""Ticker: {ticker}  |  Date: {trade_date}  |  Round: {debate_round + 1}

{analyst_context}
"""
    if bear_arg:
        user_content += f"\n=== BEAR ARGUMENT TO REFUTE ===\n{bear_arg}\n"

    user_content += "\nPresent your bull case:"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    # Include prior debate history for continuity
    if state.get("bull_history"):
        for prior in state["bull_history"][-2:]:
            messages.insert(-1, {"role": "assistant", "content": prior})

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.4,
            max_tokens=1500,
        )
        bull_arg = response.choices[0].message.content or ""
    except Exception as exc:
        bull_arg = f"Bull research failed: {exc}"

    updated = dict(state)
    updated["bull_argument"] = bull_arg
    updated["debate_round"] = debate_round + 1
    updated["bull_history"] = list(state.get("bull_history", [])) + [bull_arg]
    updated["debate_history"] = list(state.get("debate_history", [])) + [
        f"[Round {debate_round + 1} BULL]: {bull_arg}"
    ]
    return AgentState(**updated)


def _build_analyst_context(state: AgentState) -> str:
    parts = ["=== ANALYST REPORTS ==="]
    for key, label in [
        ("market_report", "Market/Technical"),
        ("fundamentals_report", "Fundamentals"),
        ("news_report", "News/Events"),
        ("sentiment_report", "Sentiment"),
    ]:
        report = state.get(key, "")
        if report:
            parts.append(f"\n--- {label} ---\n{report[:600]}")
    return "\n".join(parts)
