"""
Risk management agent — assesses portfolio risk before final approval.
"""
from __future__ import annotations

from typing import Any

from ..dataflows.interface import get_stock_data, get_indicators
from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a risk manager responsible for protecting portfolio capital.

Review the proposed trade and assess:
1. Volatility risk (ATR, historical vol, recent range)
2. Liquidity risk (average daily volume vs. proposed position)
3. Drawdown risk (max historical drawdown, current distance from key supports)
4. Correlation risk (sector concentration if known)
5. Stop-loss adequacy (is the proposed stop logical given volatility?)
6. Position size appropriateness given risk

Output format:
- Risk scores (0=low risk, 1=high risk): volatility, liquidity, drawdown
- Overall risk rating: LOW | MEDIUM | HIGH | EXTREME
- Position size recommendation: <float 0.0-1.0>
- Red flags (if any): specific concerns
- Approval: APPROVED | REDUCED | REJECTED
  - APPROVED: proceed as proposed
  - REDUCED: proceed with smaller position (specify max %)
  - REJECTED: risk/reward unacceptable

Be specific. Use the volatility data provided, not vague estimates.
"""


def run_risk_manager(state: AgentState, llm_client: Any) -> AgentState:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    indicator_data = get_indicators(ticker, trade_date, ["atr", "bollinger", "rsi"])

    context = _build_context(state, indicator_data)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.1,
            max_tokens=800,
        )
        assessment = response.choices[0].message.content or ""
    except Exception as exc:
        assessment = f"Risk assessment failed: {exc}"

    updated = dict(state)
    updated["risk_assessment"] = assessment
    return AgentState(**updated)


def _build_context(state: AgentState, indicator_data: dict) -> str:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")
    trader_decision = state.get("trader_decision", "")

    lines = [
        f"Ticker: {ticker}  |  Date: {trade_date}",
        "",
        "=== PROPOSED TRADE ===",
        trader_decision[:800] if trader_decision else "(no decision)",
        "",
        "=== VOLATILITY DATA ===",
    ]

    skip = {"ticker", "trade_date", "error"}
    for k, v in indicator_data.items():
        if k in skip:
            continue
        if isinstance(v, float):
            lines.append(f"  {k}: {v:.4f}")

    lines.append("\nProvide your risk assessment and approval decision:")
    return "\n".join(lines)
