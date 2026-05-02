"""
TradingGraph — orchestrates the 5-team trading agent pipeline.
Adapted from tauricresearch/tradingagents for local llama.cpp (Qwen3.6-35B).

Pipeline: analysts → researchers (debate) → trader → risk_mgmt → portfolio
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..graph.state import AgentState, initial_state
from ..analysts.market_analyst import run_market_analyst
from ..analysts.fundamentals_analyst import run_fundamentals_analyst
from ..analysts.news_analyst import run_news_analyst
from ..analysts.sentiment_analyst import run_sentiment_analyst
from ..researchers.bull_researcher import run_bull_researcher
from ..researchers.bear_researcher import run_bear_researcher
from ..trader.trader_agent import run_trader_agent
from ..risk_mgmt.risk_manager import run_risk_manager
from ..portfolio.portfolio_manager import run_portfolio_manager


class TradingGraph:
    """
    Orchestrates the full multi-agent trading analysis pipeline.

    All LLM calls route to the local llama.cpp endpoint configured
    via environment variables (never hardcoded).

    Usage:
        graph = TradingGraph()
        result = graph.analyze("AAPL", "2026-05-01")
        print(result["final_decision"])
    """

    def __init__(self, analyst_types: Optional[List[str]] = None):
        self.config = get_config()
        self.analyst_types = analyst_types or self.config.get(
            "analyst_types", ["market", "fundamentals", "news", "sentiment"]
        )
        self._llm = self._build_llm_client()
        self._log_dir = Path(self.config["log_dir"])
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _build_llm_client(self) -> Any:
        """Build OpenAI-compatible client pointing to local llama.cpp."""
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=self.config["llm_base_url"],
                api_key=self.config["llm_api_key"],
            )
            # Attach model name for use in agent calls
            client._model = self.config["deep_think_llm"]
            return client
        except ImportError as exc:
            raise RuntimeError(
                "openai package required: pip install openai"
            ) from exc

    def analyze(
        self,
        ticker: str,
        trade_date: str,
        company_name: str = "",
        max_debate_rounds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run the full 5-team analysis pipeline.

        Args:
            ticker: Stock symbol
            trade_date: ISO date "YYYY-MM-DD"
            company_name: Optional full company name
            max_debate_rounds: Override config default

        Returns:
            Final AgentState as dict with all reports and decisions.
        """
        rounds = max_debate_rounds or self.config.get("max_debate_rounds", 1)
        state = initial_state(ticker, trade_date, company_name)

        # Phase 1: Analysts (run in logical order)
        if "market" in self.analyst_types:
            state = run_market_analyst(state, self._llm)

        if "fundamentals" in self.analyst_types:
            state = run_fundamentals_analyst(state, self._llm)

        if "news" in self.analyst_types:
            state = run_news_analyst(state, self._llm)

        if "sentiment" in self.analyst_types:
            state = run_sentiment_analyst(state, self._llm)

        # Phase 2: Researcher debate
        for _ in range(rounds):
            state = run_bull_researcher(state, self._llm)
            state = run_bear_researcher(state, self._llm)

        # Phase 3: Trader synthesis
        state = run_trader_agent(state, self._llm)

        # Phase 4: Risk management
        state = run_risk_manager(state, self._llm)

        # Phase 5: Portfolio approval
        state = run_portfolio_manager(state, self._llm)

        # Persist log
        self._log_state(state)

        return dict(state)

    def analyze_quick(self, ticker: str, trade_date: str) -> Dict[str, Any]:
        """
        Fast single-analyst signal — market technicals only.
        Used for quick forecasts without full pipeline.
        """
        state = initial_state(ticker, trade_date)
        state = run_market_analyst(state, self._llm)
        state = run_trader_agent(state, self._llm)
        return dict(state)

    def _log_state(self, state: AgentState) -> None:
        ticker = state.get("ticker", "unknown")
        trade_date = state.get("trade_date", "unknown")
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_file = self._log_dir / f"{ticker}_{trade_date}_{ts}.json"
        try:
            with open(log_file, "w") as f:
                json.dump(dict(state), f, indent=2, default=str)
        except Exception:
            pass

    def get_past_decisions(self, ticker: str, limit: int = 10) -> List[Dict]:
        """Load recent decisions from log files for context."""
        results = []
        try:
            for log_file in sorted(self._log_dir.glob(f"{ticker}_*.json"), reverse=True)[:limit]:
                with open(log_file) as f:
                    data = json.load(f)
                results.append({
                    "trade_date": data.get("trade_date"),
                    "final_decision": data.get("final_decision", ""),
                    "position_size": data.get("position_size", 0.0),
                })
        except Exception:
            pass
        return results
