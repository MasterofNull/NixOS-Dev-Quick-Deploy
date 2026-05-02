"""
Financial data tool functions for trading agents.
Supports: yfinance (default) and Alpha Vantage (when key is set).
Ported from tauricresearch/tradingagents/dataflows/interface.py
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def _vendor() -> str:
    key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    forced = os.getenv("TRADING_DATA_VENDOR", "").strip().lower()
    if forced:
        return forced
    return "alpha_vantage" if key else "yfinance"


# ---------------------------------------------------------------------------
# Stock price / OHLCV
# ---------------------------------------------------------------------------

def get_stock_data(ticker: str, start_date: str, end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve OHLCV price data for a ticker.

    Args:
        ticker: Stock symbol (e.g. "AAPL")
        start_date: ISO date string "YYYY-MM-DD"
        end_date: ISO date string; defaults to start_date + 30 days

    Returns:
        dict with keys: ticker, dates, open, high, low, close, volume
    """
    if end_date is None:
        dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = (dt + timedelta(days=30)).strftime("%Y-%m-%d")

    if _vendor() == "alpha_vantage":
        return _av_stock_data(ticker, start_date, end_date)
    return _yf_stock_data(ticker, start_date, end_date)


def _yf_stock_data(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    try:
        import yfinance as yf
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if df.empty:
            return {"ticker": ticker, "error": "no data", "dates": [], "close": []}
        return {
            "ticker": ticker,
            "dates": [str(d.date()) for d in df.index],
            "open": df["Open"].tolist(),
            "high": df["High"].tolist(),
            "low": df["Low"].tolist(),
            "close": df["Close"].tolist(),
            "volume": df["Volume"].tolist(),
        }
    except ImportError:
        return {"ticker": ticker, "error": "yfinance not installed"}
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


def _av_stock_data(ticker: str, start_date: str, end_date: str) -> Dict[str, Any]:
    try:
        import requests
        key = os.environ["ALPHA_VANTAGE_API_KEY"]
        url = (
            f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
            f"&symbol={ticker}&outputsize=full&apikey={key}"
        )
        resp = requests.get(url, timeout=15)
        data = resp.json().get("Time Series (Daily)", {})
        rows = [
            (d, v) for d, v in sorted(data.items())
            if start_date <= d <= end_date
        ]
        return {
            "ticker": ticker,
            "dates": [r[0] for r in rows],
            "open": [float(r[1]["1. open"]) for r in rows],
            "high": [float(r[1]["2. high"]) for r in rows],
            "low": [float(r[1]["3. low"]) for r in rows],
            "close": [float(r[1]["4. close"]) for r in rows],
            "volume": [float(r[1]["5. volume"]) for r in rows],
        }
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


# ---------------------------------------------------------------------------
# Technical indicators
# ---------------------------------------------------------------------------

def get_indicators(ticker: str, trade_date: str, indicators: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Calculate technical indicators for the given ticker up to trade_date.

    Supported indicators: sma50, sma200, ema10, macd, rsi, bollinger, atr, vwma
    Defaults to all if not specified.
    """
    if indicators is None:
        indicators = ["sma50", "sma200", "ema10", "macd", "rsi", "bollinger", "atr"]

    dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start = (dt - timedelta(days=300)).strftime("%Y-%m-%d")
    price_data = get_stock_data(ticker, start, trade_date)

    if "error" in price_data:
        return {"ticker": ticker, "trade_date": trade_date, "error": price_data["error"]}

    try:
        import pandas as pd
        import numpy as np

        closes = pd.Series(price_data["close"])
        highs = pd.Series(price_data["high"])
        lows = pd.Series(price_data["low"])
        volumes = pd.Series(price_data["volume"])

        results: Dict[str, Any] = {"ticker": ticker, "trade_date": trade_date}

        if "sma50" in indicators and len(closes) >= 50:
            results["sma50"] = float(closes.rolling(50).mean().iloc[-1])
        if "sma200" in indicators and len(closes) >= 200:
            results["sma200"] = float(closes.rolling(200).mean().iloc[-1])
        if "ema10" in indicators and len(closes) >= 10:
            results["ema10"] = float(closes.ewm(span=10).mean().iloc[-1])
        if "macd" in indicators and len(closes) >= 26:
            ema12 = closes.ewm(span=12).mean()
            ema26 = closes.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal = macd_line.ewm(span=9).mean()
            results["macd"] = float(macd_line.iloc[-1])
            results["macd_signal"] = float(signal.iloc[-1])
            results["macd_histogram"] = float((macd_line - signal).iloc[-1])
        if "rsi" in indicators and len(closes) >= 15:
            delta = closes.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, float("nan"))
            results["rsi"] = float(100 - (100 / (1 + rs.iloc[-1])))
        if "bollinger" in indicators and len(closes) >= 20:
            ma20 = closes.rolling(20).mean()
            std20 = closes.rolling(20).std()
            results["bollinger_upper"] = float((ma20 + 2 * std20).iloc[-1])
            results["bollinger_mid"] = float(ma20.iloc[-1])
            results["bollinger_lower"] = float((ma20 - 2 * std20).iloc[-1])
        if "atr" in indicators and len(closes) >= 15:
            tr = pd.concat([
                highs - lows,
                (highs - closes.shift()).abs(),
                (lows - closes.shift()).abs(),
            ], axis=1).max(axis=1)
            results["atr"] = float(tr.rolling(14).mean().iloc[-1])

        return results

    except ImportError:
        return {"ticker": ticker, "trade_date": trade_date, "error": "pandas/numpy not installed"}
    except Exception as exc:
        return {"ticker": ticker, "trade_date": trade_date, "error": str(exc)}


# ---------------------------------------------------------------------------
# Fundamentals
# ---------------------------------------------------------------------------

def get_fundamentals(ticker: str) -> Dict[str, Any]:
    """Company overview and key financial metrics."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return {
            "ticker": ticker,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "revenue": info.get("totalRevenue"),
            "profit_margin": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "description": info.get("longBusinessSummary", "")[:500],
        }
    except ImportError:
        return {"ticker": ticker, "error": "yfinance not installed"}
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


def get_balance_sheet(ticker: str) -> Dict[str, Any]:
    try:
        import yfinance as yf
        bs = yf.Ticker(ticker).balance_sheet
        if bs is None or bs.empty:
            return {"ticker": ticker, "error": "no data"}
        latest = bs.iloc[:, 0]
        return {
            "ticker": ticker,
            "total_assets": float(latest.get("Total Assets", 0) or 0),
            "total_liabilities": float(latest.get("Total Liab", 0) or 0),
            "stockholders_equity": float(latest.get("Total Stockholder Equity", 0) or 0),
            "cash": float(latest.get("Cash", 0) or 0),
            "short_term_debt": float(latest.get("Short Long Term Debt", 0) or 0),
            "long_term_debt": float(latest.get("Long Term Debt", 0) or 0),
        }
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


def get_cashflow(ticker: str) -> Dict[str, Any]:
    try:
        import yfinance as yf
        cf = yf.Ticker(ticker).cashflow
        if cf is None or cf.empty:
            return {"ticker": ticker, "error": "no data"}
        latest = cf.iloc[:, 0]
        return {
            "ticker": ticker,
            "operating_cashflow": float(latest.get("Total Cash From Operating Activities", 0) or 0),
            "investing_cashflow": float(latest.get("Total Cashflows From Investing Activities", 0) or 0),
            "financing_cashflow": float(latest.get("Total Cash From Financing Activities", 0) or 0),
            "free_cashflow": float(latest.get("Free Cash Flow", 0) or 0),
            "capex": float(latest.get("Capital Expenditures", 0) or 0),
        }
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


def get_income_statement(ticker: str) -> Dict[str, Any]:
    try:
        import yfinance as yf
        inc = yf.Ticker(ticker).financials
        if inc is None or inc.empty:
            return {"ticker": ticker, "error": "no data"}
        latest = inc.iloc[:, 0]
        return {
            "ticker": ticker,
            "revenue": float(latest.get("Total Revenue", 0) or 0),
            "gross_profit": float(latest.get("Gross Profit", 0) or 0),
            "ebit": float(latest.get("Ebit", 0) or 0),
            "net_income": float(latest.get("Net Income", 0) or 0),
            "earnings_per_share": float(latest.get("Diluted Eps", 0) or 0),
        }
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


# ---------------------------------------------------------------------------
# News + sentiment
# ---------------------------------------------------------------------------

def get_news(ticker: str, max_items: int = 10) -> Dict[str, Any]:
    """Recent news headlines for a ticker."""
    try:
        import yfinance as yf
        news = yf.Ticker(ticker).news or []
        items = []
        for n in news[:max_items]:
            items.append({
                "title": n.get("title", ""),
                "publisher": n.get("publisher", ""),
                "published": n.get("providerPublishTime", 0),
                "url": n.get("link", ""),
                "summary": n.get("summary", ""),
            })
        return {"ticker": ticker, "news": items, "count": len(items)}
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


def get_global_news(query: str = "market", max_items: int = 5) -> Dict[str, Any]:
    """Broad market news (not ticker-specific)."""
    return {"query": query, "news": [], "note": "Configure a news API key for live data"}


def get_insider_transactions(ticker: str) -> Dict[str, Any]:
    """Recent insider buy/sell transactions."""
    try:
        import yfinance as yf
        inst = yf.Ticker(ticker).insider_transactions
        if inst is None or inst.empty:
            return {"ticker": ticker, "transactions": []}
        rows = inst.head(10).to_dict("records")
        return {"ticker": ticker, "transactions": rows}
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}
