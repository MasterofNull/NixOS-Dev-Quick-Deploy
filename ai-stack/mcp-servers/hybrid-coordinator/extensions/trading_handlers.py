"""
Trading agents HTTP handlers for the hybrid coordinator.
Exposes the 5-team trading analysis pipeline as HTTP endpoints
accessible to ALL agents in the pool via standard REST calls.

Routes:
  GET  /trading/analyze         — Full 5-team pipeline for a ticker
  GET  /trading/forecast        — Quick market-only signal
  POST /trading/debate          — Trigger researcher debate round
  GET  /trading/history         — Past decisions for a ticker
  GET  /trading/tools           — List available financial data tools (agent-discovery)
"""
from __future__ import annotations

import json
import sys
import os
import importlib.util
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Module globals injected by init()
# ---------------------------------------------------------------------------
_logger: Any = None
_config: Any = None


def init(logger: Any = None, config: Any = None) -> None:
    global _logger, _config
    _logger = logger
    _config = config


def register_routes(app: Any) -> None:
    app.router.add_get("/trading/analyze", handle_trading_analyze)
    app.router.add_get("/trading/forecast", handle_trading_forecast)
    app.router.add_post("/trading/debate", handle_trading_debate)
    app.router.add_get("/trading/history", handle_trading_history)
    app.router.add_get("/trading/tools", handle_trading_tools)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_trading_analyze(request: Any) -> Any:
    """
    Run the full 5-team analysis pipeline.

    Query params:
      ticker      — Stock symbol (required)
      date        — Trade date YYYY-MM-DD (required)
      company     — Company name (optional)
      analysts    — Comma-separated analyst types (default: market,fundamentals,news,sentiment)
      debate_rounds — Integer (default: 1)

    Returns JSON with all analyst reports, debate history, and final decision.
    Accessible to any agent via: GET /trading/analyze?ticker=AAPL&date=2026-05-01
    """
    from aiohttp import web

    ticker = request.rel_url.query.get("ticker", "").strip().upper()
    trade_date = request.rel_url.query.get("date", "").strip()
    company_name = request.rel_url.query.get("company", "").strip()
    analyst_types_raw = request.rel_url.query.get("analysts", "market,fundamentals,news,sentiment")
    debate_rounds = int(request.rel_url.query.get("debate_rounds", "1"))

    if not ticker or not trade_date:
        return web.Response(
            status=400,
            content_type="application/json",
            text=json.dumps({"error": "ticker and date are required"}),
        )

    analyst_types = [a.strip() for a in analyst_types_raw.split(",") if a.strip()]

    try:
        graph = _get_graph(analyst_types)
        result = graph.analyze(
            ticker=ticker,
            trade_date=trade_date,
            company_name=company_name,
            max_debate_rounds=debate_rounds,
        )
        # Strip very long internal fields for the API response
        payload = {
            "ticker": ticker,
            "trade_date": trade_date,
            "analyst_types": analyst_types,
            "market_report": result.get("market_report", "")[:1000],
            "fundamentals_report": result.get("fundamentals_report", "")[:1000],
            "news_report": result.get("news_report", "")[:1000],
            "sentiment_report": result.get("sentiment_report", "")[:1000],
            "bull_argument": result.get("bull_argument", "")[:600],
            "bear_argument": result.get("bear_argument", "")[:600],
            "trader_decision": result.get("trader_decision", ""),
            "risk_assessment": result.get("risk_assessment", "")[:600],
            "final_decision": result.get("final_decision", ""),
            "position_size": result.get("position_size", 0.0),
            "status": "ok",
        }
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps(payload),
        )
    except Exception as exc:
        if _logger:
            _logger.error("trading_analyze error: %s", exc)
        return web.Response(
            status=500,
            content_type="application/json",
            text=json.dumps({"error": str(exc)}),
        )


async def handle_trading_forecast(request: Any) -> Any:
    """
    Quick market-only signal (no full pipeline — just technicals + trader).

    Query params:
      ticker  — Stock symbol (required)
      date    — Trade date YYYY-MM-DD (required)
    """
    from aiohttp import web

    ticker = request.rel_url.query.get("ticker", "").strip().upper()
    trade_date = request.rel_url.query.get("date", "").strip()

    if not ticker or not trade_date:
        return web.Response(
            status=400,
            content_type="application/json",
            text=json.dumps({"error": "ticker and date are required"}),
        )

    try:
        graph = _get_graph(["market"])
        result = graph.analyze_quick(ticker, trade_date)
        return web.Response(
            status=200,
            content_type="application/json",
            text=json.dumps({
                "ticker": ticker,
                "trade_date": trade_date,
                "market_report": result.get("market_report", "")[:800],
                "trader_decision": result.get("trader_decision", ""),
                "status": "ok",
            }),
        )
    except Exception as exc:
        return web.Response(
            status=500,
            content_type="application/json",
            text=json.dumps({"error": str(exc)}),
        )


async def handle_trading_debate(request: Any) -> Any:
    """
    Trigger a single bull/bear debate round given existing analyst reports.

    POST body:
      ticker, trade_date, market_report, fundamentals_report, news_report,
      sentiment_report, bull_argument (optional), bear_argument (optional),
      debate_round (optional, default 0)
    """
    from aiohttp import web

    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, content_type="application/json",
                            text=json.dumps({"error": "invalid JSON body"}))

    ticker = body.get("ticker", "").strip().upper()
    trade_date = body.get("trade_date", "").strip()
    if not ticker or not trade_date:
        return web.Response(status=400, content_type="application/json",
                            text=json.dumps({"error": "ticker and trade_date required"}))

    try:
        # Build partial state from request body
        _ensure_trading_agents_package()
        from trading_agents.graph.state import AgentState  # type: ignore
        state = AgentState(**{k: v for k, v in body.items() if k in AgentState.__annotations__})

        graph = _get_graph()
        # Run one debate round
        from trading_agents.researchers.bull_researcher import run_bull_researcher  # type: ignore
        from trading_agents.researchers.bear_researcher import run_bear_researcher  # type: ignore
        state = run_bull_researcher(state, graph._llm)
        state = run_bear_researcher(state, graph._llm)

        return web.Response(status=200, content_type="application/json",
                            text=json.dumps({
                                "bull_argument": state.get("bull_argument", ""),
                                "bear_argument": state.get("bear_argument", ""),
                                "debate_round": state.get("debate_round", 1),
                                "status": "ok",
                            }))
    except Exception as exc:
        return web.Response(status=500, content_type="application/json",
                            text=json.dumps({"error": str(exc)}))


async def handle_trading_history(request: Any) -> Any:
    """
    Retrieve past trading decisions for a ticker.

    Query params:
      ticker — Stock symbol (required)
      limit  — Max results (default 10)
    """
    from aiohttp import web

    ticker = request.rel_url.query.get("ticker", "").strip().upper()
    limit = int(request.rel_url.query.get("limit", "10"))

    if not ticker:
        return web.Response(status=400, content_type="application/json",
                            text=json.dumps({"error": "ticker required"}))
    try:
        graph = _get_graph()
        history = graph.get_past_decisions(ticker, limit=limit)
        return web.Response(status=200, content_type="application/json",
                            text=json.dumps({"ticker": ticker, "decisions": history}))
    except Exception as exc:
        return web.Response(status=500, content_type="application/json",
                            text=json.dumps({"error": str(exc)}))


async def handle_trading_tools(request: Any) -> Any:
    """
    Agent-discovery endpoint: returns the full catalog of available
    financial data tools so any agent can discover them without
    reading source code.

    Accessible to ALL agents via: GET /trading/tools
    """
    from aiohttp import web

    tools = [
        {
            "name": "get_stock_data",
            "description": "OHLCV price history for a ticker",
            "params": {"ticker": "str", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD (optional)"},
            "endpoint": "/trading/analyze",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "get_indicators",
            "description": "Technical indicators: SMA, EMA, MACD, RSI, Bollinger, ATR",
            "params": {"ticker": "str", "trade_date": "YYYY-MM-DD", "indicators": "list (optional)"},
            "endpoint": "/trading/forecast",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "get_fundamentals",
            "description": "Company overview, P/E, revenue, margins, debt",
            "params": {"ticker": "str"},
            "endpoint": "/trading/analyze?analysts=fundamentals",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "get_balance_sheet",
            "description": "Assets, liabilities, equity, cash, debt",
            "params": {"ticker": "str"},
            "endpoint": "/trading/analyze?analysts=fundamentals",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "get_cashflow",
            "description": "Operating, investing, financing cash flows",
            "params": {"ticker": "str"},
            "endpoint": "/trading/analyze?analysts=fundamentals",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "get_income_statement",
            "description": "Revenue, gross profit, EBIT, net income, EPS",
            "params": {"ticker": "str"},
            "endpoint": "/trading/analyze?analysts=fundamentals",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "get_news",
            "description": "Recent ticker-specific news headlines",
            "params": {"ticker": "str", "max_items": "int (default 10)"},
            "endpoint": "/trading/analyze?analysts=news",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "get_insider_transactions",
            "description": "Recent insider buy/sell activity",
            "params": {"ticker": "str"},
            "endpoint": "/trading/analyze?analysts=news",
            "module": "ai-stack/trading-agents/dataflows/interface.py",
        },
        {
            "name": "full_pipeline",
            "description": "Complete 5-team analysis: analysts + debate + trader + risk + portfolio",
            "params": {"ticker": "str", "date": "YYYY-MM-DD", "analysts": "csv (optional)", "debate_rounds": "int (optional)"},
            "endpoint": "/trading/analyze",
            "module": "ai-stack/trading-agents/graph/trading_graph.py",
        },
        {
            "name": "quick_forecast",
            "description": "Fast market signal without full pipeline",
            "params": {"ticker": "str", "date": "YYYY-MM-DD"},
            "endpoint": "/trading/forecast",
            "module": "ai-stack/trading-agents/graph/trading_graph.py",
        },
    ]

    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps({"tools": tools, "count": len(tools), "status": "ok"}),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_graph(analyst_types: Optional[list] = None) -> Any:
    """Lazy-load the TradingGraph to avoid import cost at startup."""
    _ensure_trading_agents_package()
    from trading_agents.graph.trading_graph import TradingGraph  # type: ignore
    return TradingGraph(analyst_types=analyst_types)


def _ensure_trading_agents_package() -> None:
    """Expose the hyphenated trading-agents directory as importable trading_agents."""
    if "trading_agents" in sys.modules:
        return
    trading_agents_dir = str(Path(__file__).resolve().parents[3] / "trading-agents")

    init_file = os.path.join(trading_agents_dir, "__init__.py")
    spec = importlib.util.spec_from_file_location(
        "trading_agents",
        init_file,
        submodule_search_locations=[trading_agents_dir],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load trading_agents package from {trading_agents_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["trading_agents"] = module
    spec.loader.exec_module(module)
