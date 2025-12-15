#!/usr/bin/env python3
"""
Example Skill: Market Data Analysis

This skill demonstrates how to create persistent, version-controlled
AI skills for the AIDB MCP system.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json


async def analyze_market_trends(
    symbol: str,
    timeframe_hours: int = 24,
    db_connection=None
) -> Dict[str, Any]:
    """
    Analyze market trends for a given symbol.

    Args:
        symbol: Trading symbol (e.g., 'BTC/USD')
        timeframe_hours: Number of hours to analyze
        db_connection: Database connection from MCP server

    Returns:
        Dictionary containing trend analysis
    """
    if not db_connection:
        return {"error": "Database connection required"}

    # Query market data
    query = """
    SELECT
        timestamp,
        open,
        high,
        low,
        close,
        volume
    FROM market_data
    WHERE symbol = $1
        AND timestamp >= NOW() - INTERVAL '%s hours'
    ORDER BY timestamp DESC
    """

    try:
        async with db_connection.acquire() as conn:
            rows = await conn.fetch(query, symbol, timeframe_hours)

            if not rows:
                return {
                    "symbol": symbol,
                    "status": "no_data",
                    "message": f"No data found for {symbol}"
                }

            # Calculate trend indicators
            prices = [row['close'] for row in rows]
            volumes = [row['volume'] for row in rows]

            avg_price = sum(prices) / len(prices)
            avg_volume = sum(volumes) / len(volumes)

            price_change = prices[0] - prices[-1]
            price_change_pct = (price_change / prices[-1]) * 100 if prices[-1] > 0 else 0

            # Determine trend
            if price_change_pct > 2:
                trend = "bullish"
            elif price_change_pct < -2:
                trend = "bearish"
            else:
                trend = "neutral"

            return {
                "symbol": symbol,
                "status": "success",
                "timeframe_hours": timeframe_hours,
                "data_points": len(rows),
                "current_price": prices[0],
                "avg_price": avg_price,
                "price_change": price_change,
                "price_change_pct": round(price_change_pct, 2),
                "trend": trend,
                "avg_volume": avg_volume,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        return {
            "symbol": symbol,
            "status": "error",
            "error": str(e)
        }


async def detect_volatility_spikes(
    symbol: str,
    threshold: float = 2.0,
    db_connection=None
) -> Dict[str, Any]:
    """
    Detect unusual volatility spikes in market data.

    Args:
        symbol: Trading symbol
        threshold: Volatility threshold (standard deviations)
        db_connection: Database connection

    Returns:
        Volatility analysis results
    """
    query = """
    SELECT
        timestamp,
        high - low as range,
        close
    FROM market_data
    WHERE symbol = $1
        AND timestamp >= NOW() - INTERVAL '7 days'
    ORDER BY timestamp DESC
    """

    try:
        async with db_connection.acquire() as conn:
            rows = await conn.fetch(query, symbol)

            if len(rows) < 10:
                return {"status": "insufficient_data"}

            ranges = [row['range'] for row in rows]
            avg_range = sum(ranges) / len(ranges)

            # Calculate standard deviation
            variance = sum((r - avg_range) ** 2 for r in ranges) / len(ranges)
            std_dev = variance ** 0.5

            # Find spikes
            spikes = []
            for row in rows:
                z_score = (row['range'] - avg_range) / std_dev if std_dev > 0 else 0
                if abs(z_score) > threshold:
                    spikes.append({
                        "timestamp": row['timestamp'].isoformat(),
                        "range": row['range'],
                        "z_score": round(z_score, 2),
                        "price": row['close']
                    })

            return {
                "symbol": symbol,
                "status": "success",
                "avg_range": avg_range,
                "std_dev": std_dev,
                "spike_count": len(spikes),
                "spikes": spikes[:10],  # Top 10 spikes
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# Skill metadata for MCP registration
SKILL_METADATA = {
    "name": "market_analysis",
    "version": "1.0.0",
    "description": "Analyze market trends and detect volatility anomalies",
    "category": "trading",
    "functions": [
        {
            "name": "analyze_market_trends",
            "description": "Analyze price trends for a trading symbol",
            "parameters": {
                "symbol": {"type": "string", "required": True},
                "timeframe_hours": {"type": "integer", "default": 24}
            }
        },
        {
            "name": "detect_volatility_spikes",
            "description": "Detect unusual volatility patterns",
            "parameters": {
                "symbol": {"type": "string", "required": True},
                "threshold": {"type": "float", "default": 2.0}
            }
        }
    ],
    "author": "AI-Optimizer Team",
    "created": "2025-11-22",
    "tags": ["trading", "analysis", "volatility", "trends"]
}


if __name__ == "__main__":
    # Example usage (for testing)
    print(json.dumps(SKILL_METADATA, indent=2))
