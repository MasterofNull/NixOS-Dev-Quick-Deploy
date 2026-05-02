"""
Portfolio manager — final trade approval/rejection gate.
"""
from __future__ import annotations

from typing import Any

from ..graph.state import AgentState


SYSTEM_PROMPT = """You are the portfolio manager. You have the final say on all trades.

You have received:
- Full analyst team reports (market, fundamentals, news, sentiment)
- Researcher debate (bull vs. bear)
- Trader's proposed decision with entry/stop/target
- Risk manager's assessment and approval/reduction recommendation

Your responsibilities:
1. Review the full picture holistically
2. Ensure the trade aligns with portfolio construction principles
3. Make the FINAL decision: APPROVED | MODIFIED | REJECTED
4. If MODIFIED: specify exact position size (0.0-1.0)
5. If REJECTED: state the specific reason

Output format:
```
PORTFOLIO DECISION: APPROVED | MODIFIED | REJECTED
Final Position Size: <0.0-1.0>
Final Action: BUY | HOLD | SELL
Rationale: <2-3 sentences>
Key Risk: <primary risk to monitor>
Review Date: <when to reassess>
```

You are accountable for this decision. Be direct.
"""


def run_portfolio_manager(state: AgentState, llm_client: Any) -> AgentState:
    context = _build_context(state)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": context},
    ]

    try:
        response = llm_client.chat.completions.create(
            model=llm_client._model,
            messages=messages,
            temperature=0.1,
            max_tokens=600,
        )
        final_decision = response.choices[0].message.content or ""
    except Exception as exc:
        final_decision = f"Portfolio decision failed: {exc}"

    # Parse position size from decision
    position_size = _parse_position_size(final_decision)
    final_action = _parse_action(final_decision)

    updated = dict(state)
    updated["final_decision"] = final_decision
    updated["position_size"] = position_size
    updated["trader_decision"] = final_action
    updated["current_phase"] = "done"
    return AgentState(**updated)


def _build_context(state: AgentState) -> str:
    ticker = state.get("ticker", "UNKNOWN")
    trade_date = state.get("trade_date", "")

    parts = [f"Ticker: {ticker}  |  Date: {trade_date}", ""]

    for key, label in [
        ("trader_decision", "TRADER PROPOSAL"),
        ("risk_assessment", "RISK ASSESSMENT"),
    ]:
        val = state.get(key, "")
        if val:
            parts.append(f"=== {label} ===\n{val[:700]}")
            parts.append("")

    parts.append("Make your final portfolio decision:")
    return "\n".join(parts)


def _parse_position_size(decision: str) -> float:
    import re
    m = re.search(r"Final Position Size:\s*([\d.]+)", decision)
    if m:
        try:
            val = float(m.group(1))
            return min(max(val, 0.0), 1.0)
        except ValueError:
            pass
    return 0.0


def _parse_action(decision: str) -> str:
    for action in ("BUY", "SELL", "HOLD"):
        if action in decision.upper():
            return action
    return "HOLD"
