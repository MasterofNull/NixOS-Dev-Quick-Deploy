"""
Bear researcher — builds the risk/downside investment case.
"""
from __future__ import annotations

from typing import Any

from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a bearish investment researcher (short-seller perspective).

Your role is to build the strongest possible evidence-based case AGAINST buying {ticker}.

You have access to analyst reports covering market technicals, fundamentals, news, sentiment.

Your bear case must:
1. Identify 3-5 specific downside risks with data support
2. Challenge the bull thesis with contradicting evidence
3. Highlight valuation risks, competitive threats, or sector headwinds
4. Quantify downside potential (price target, catalyst timeline)
5. Identify what could cause a significant decline

Debate rules:
- Engage DIRECTLY with bull arguments presented
- Use specific numbers — avoid vague "risks could materialize"
- Maintain intellectual honesty — acknowledge genuine bull strengths
- Focus on asymmetric risks that bulls may be underweighting

Format: structured argument with sections, end with confidence score 0-1.
"""


def run_bear_researcher(state: AgentState, llm_client: Any) -> AgentState:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")
    debate_round = state.get("debate_round", 0)

    analyst_context = _build_analyst_context(state)
    bull_arg = state.get("bull_argument", "")

    system = SYSTEM_PROMPT.format(ticker=ticker)

    user_content = f"""Ticker: {ticker}  |  Date: {trade_date}  |  Round: {debate_round}

{analyst_context}
"""
    if bull_arg:
        user_content += f"\n=== BULL ARGUMENT TO CHALLENGE ===\n{bull_arg}\n"

    user_content += "\nPresent your bear case:"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    if state.get("bear_history"):
        for prior in state["bear_history"][-2:]:
            messages.insert(-1, {"role": "assistant", "content": prior})

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.4,
            max_tokens=1500,
        )
        bear_arg = response.choices[0].message.content or ""
    except Exception as exc:
        bear_arg = f"Bear research failed: {exc}"

    updated = dict(state)
    updated["bear_argument"] = bear_arg
    updated["bear_history"] = list(state.get("bear_history", [])) + [bear_arg]
    updated["debate_history"] = list(state.get("debate_history", [])) + [
        f"[Round {debate_round} BEAR]: {bear_arg}"
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
