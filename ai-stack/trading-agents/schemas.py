"""
Shared state and data schemas for the trading agents framework.
Ported from tauricresearch/tradingagents.
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict


def _merge_dicts(a: dict, b: dict) -> dict:
    merged = dict(a)
    merged.update(b)
    return merged


def _append_list(a: list, b: list) -> list:
    return a + b


class AgentState(TypedDict, total=False):
    # Core task
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

    # Trader decision
    investment_plan: str
    trader_decision: str

    # Risk management
    risk_assessment: str
    risk_debate_history: List[str]
    risk_debate_round: int

    # Portfolio manager
    final_decision: str   # BUY | HOLD | SELL
    position_size: float  # 0.0 – 1.0

    # Memory + reflection
    past_decisions: List[Dict[str, Any]]
    reflection_notes: str

    # Control
    messages: List[Dict[str, Any]]
    send_to: str


class AnalystReport(TypedDict):
    analyst_type: str   # market | fundamentals | sentiment | news
    ticker: str
    trade_date: str
    report: str
    key_findings: List[str]
    recommendation: str   # BUY | HOLD | SELL | NEUTRAL


class TradeDecision(TypedDict):
    ticker: str
    trade_date: str
    decision: str          # BUY | HOLD | SELL
    position_size: float   # 0.0 – 1.0
    reasoning: str
    analyst_consensus: str
    risk_adjusted: bool
    portfolio_approved: bool


class DebateEntry(TypedDict):
    round: int
    side: str   # bull | bear
    argument: str


class RiskAssessment(TypedDict):
    ticker: str
    volatility_score: float   # 0.0 – 1.0
    liquidity_score: float
    drawdown_risk: float
    position_size_recommendation: float
    notes: str
