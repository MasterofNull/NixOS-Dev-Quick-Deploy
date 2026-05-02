"""
Fundamentals analyst agent — balance sheet, cash flow, income statement.
Ported from tauricresearch/tradingagents for local llama.cpp.
"""
from __future__ import annotations

from typing import Any

from ..dataflows.interface import (
    get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement
)
from ..graph.state import AgentState


SYSTEM_PROMPT = """You are a fundamental analyst evaluating a company's financial health.

Analyze the following financial data and produce a comprehensive fundamentals report.

Focus on:
1. Revenue growth and profitability trends
2. Balance sheet strength (debt levels, cash position)
3. Cash flow quality (operating vs. free cash flow)
4. Valuation metrics (P/E, EPS, margins)
5. Key risks from the financials
6. Competitive positioning implied by the numbers

Output requirements:
- Specific, actionable insights with supporting evidence from the data
- Markdown table at the end organizing key metrics for the trading team
- Conclude with: BULLISH | BEARISH | NEUTRAL and confidence score 0-1

You are collaborating with market, news, and sentiment analysts.
The trader will synthesize all reports — do not make final trade calls here.
"""


def run_fundamentals_analyst(state: AgentState, llm_client: Any) -> AgentState:
    ticker = state.get("ticker", "UNKNOWN")

    fundamentals = get_fundamentals(ticker)
    balance_sheet = get_balance_sheet(ticker)
    cashflow = get_cashflow(ticker)
    income = get_income_statement(ticker)

    context = _format_context(ticker, fundamentals, balance_sheet, cashflow, income)

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
        report = f"Fundamentals analysis failed: {exc}"

    updated = dict(state)
    updated["fundamentals_report"] = report
    return AgentState(**updated)


def _format_context(ticker, fundamentals, balance_sheet, cashflow, income) -> str:
    def _fmt(d: dict) -> str:
        lines = []
        for k, v in d.items():
            if k in ("ticker", "error"):
                continue
            if isinstance(v, float):
                lines.append(f"  {k}: {v:,.2f}")
            elif isinstance(v, str) and len(v) > 100:
                lines.append(f"  {k}: {v[:100]}...")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    return f"""Ticker: {ticker}

=== COMPANY OVERVIEW ===
{_fmt(fundamentals)}

=== BALANCE SHEET (latest quarter) ===
{_fmt(balance_sheet)}

=== CASH FLOW STATEMENT ===
{_fmt(cashflow)}

=== INCOME STATEMENT ===
{_fmt(income)}

Please produce a comprehensive fundamentals analysis report.
"""
