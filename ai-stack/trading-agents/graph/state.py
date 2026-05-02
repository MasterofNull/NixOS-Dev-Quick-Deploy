"""
AgentState and graph message utilities for trading agents.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    # Task identity
    ticker: str
    trade_date: str
    company_name: str

    # Analyst outputs
    market_report: str
    fundamentals_report: str
    sentiment_report: str
    news_report: str

    # Researcher debate
    bull_argument: str
    bear_argument: str
    debate_history: List[str]
    debate_round: int
    bull_history: List[str]
    bear_history: List[str]

    # Trader
    investment_plan: str
    trader_decision: str

    # Risk
    risk_assessment: str
    risk_debate_history: List[str]
    risk_debate_round: int

    # Portfolio
    final_decision: str      # BUY | HOLD | SELL
    position_size: float     # 0.0 – 1.0

    # Memory
    past_decisions: List[Dict[str, Any]]
    reflection_notes: str

    # Routing
    messages: List[Dict[str, Any]]
    send_to: str
    current_phase: str       # analyst | researcher | trader | risk | portfolio | done


def initial_state(ticker: str, trade_date: str, company_name: str = "") -> AgentState:
    return AgentState(
        ticker=ticker,
        trade_date=trade_date,
        company_name=company_name or ticker,
        market_report="",
        fundamentals_report="",
        sentiment_report="",
        news_report="",
        bull_argument="",
        bear_argument="",
        debate_history=[],
        debate_round=0,
        bull_history=[],
        bear_history=[],
        investment_plan="",
        trader_decision="",
        risk_assessment="",
        risk_debate_history=[],
        risk_debate_round=0,
        final_decision="",
        position_size=0.0,
        past_decisions=[],
        reflection_notes="",
        messages=[],
        send_to="",
        current_phase="analyst",
    )
