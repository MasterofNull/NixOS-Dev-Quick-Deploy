#!/usr/bin/env python3
"""
Example Skill: RF Signal Monitoring

Demonstrates RF spectrum analysis and anomaly detection skills.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json


async def analyze_rf_spectrum(
    frequency_start: float,
    frequency_end: float,
    min_power_dbm: float = -90.0,
    db_connection=None
) -> Dict[str, Any]:
    """
    Analyze RF spectrum activity in a frequency range.

    Args:
        frequency_start: Start frequency in Hz
        frequency_end: End frequency in Hz
        min_power_dbm: Minimum power threshold in dBm
        db_connection: Database connection

    Returns:
        Spectrum analysis results
    """
    query = """
    SELECT
        frequency,
        power_dbm,
        bandwidth,
        modulation,
        timestamp
    FROM rf_signals
    WHERE frequency >= $1
        AND frequency <= $2
        AND power_dbm >= $3
        AND timestamp >= NOW() - INTERVAL '1 hour'
    ORDER BY power_dbm DESC
    LIMIT 100
    """

    try:
        async with db_connection.acquire() as conn:
            rows = await conn.fetch(
                query,
                frequency_start,
                frequency_end,
                min_power_dbm
            )

            if not rows:
                return {
                    "status": "no_signals",
                    "frequency_range": {
                        "start": frequency_start,
                        "end": frequency_end
                    }
                }

            # Group by frequency bands
            signals = []
            for row in rows:
                signals.append({
                    "frequency": row['frequency'],
                    "frequency_mhz": row['frequency'] / 1e6,
                    "power_dbm": row['power_dbm'],
                    "bandwidth": row['bandwidth'],
                    "modulation": row['modulation'],
                    "timestamp": row['timestamp'].isoformat()
                })

            # Calculate statistics
            avg_power = sum(s['power_dbm'] for s in signals) / len(signals)
            max_power = max(s['power_dbm'] for s in signals)

            return {
                "status": "success",
                "frequency_range": {
                    "start": frequency_start,
                    "end": frequency_end,
                    "start_mhz": frequency_start / 1e6,
                    "end_mhz": frequency_end / 1e6
                },
                "signal_count": len(signals),
                "avg_power_dbm": round(avg_power, 2),
                "max_power_dbm": max_power,
                "signals": signals[:20],  # Top 20 by power
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


async def detect_interference(
    known_frequencies: List[float],
    tolerance_hz: float = 50000,
    db_connection=None
) -> Dict[str, Any]:
    """
    Detect potential interference near known frequencies.

    Args:
        known_frequencies: List of frequencies to monitor (Hz)
        tolerance_hz: Frequency tolerance in Hz
        db_connection: Database connection

    Returns:
        Interference detection results
    """
    results = []

    for freq in known_frequencies:
        query = """
        SELECT
            frequency,
            power_dbm,
            modulation,
            timestamp
        FROM rf_signals
        WHERE frequency >= $1
            AND frequency <= $2
            AND timestamp >= NOW() - INTERVAL '5 minutes'
        ORDER BY timestamp DESC
        LIMIT 50
        """

        try:
            async with db_connection.acquire() as conn:
                rows = await conn.fetch(
                    query,
                    freq - tolerance_hz,
                    freq + tolerance_hz
                )

                if rows:
                    # Check for signals at unexpected frequencies
                    interferers = []
                    for row in rows:
                        freq_diff = abs(row['frequency'] - freq)
                        if freq_diff > 1000:  # More than 1 kHz off
                            interferers.append({
                                "frequency": row['frequency'],
                                "frequency_mhz": row['frequency'] / 1e6,
                                "offset_hz": freq_diff,
                                "power_dbm": row['power_dbm'],
                                "modulation": row['modulation'],
                                "timestamp": row['timestamp'].isoformat()
                            })

                    results.append({
                        "target_frequency": freq,
                        "target_frequency_mhz": freq / 1e6,
                        "interference_detected": len(interferers) > 0,
                        "interference_count": len(interferers),
                        "interferers": interferers[:10]
                    })

        except Exception as e:
            results.append({
                "target_frequency": freq,
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "success",
        "monitored_frequencies": len(known_frequencies),
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
    }


async def classify_signal_types(
    frequency_range: tuple = (88e6, 108e6),
    db_connection=None
) -> Dict[str, Any]:
    """
    Classify detected signals by modulation type.

    Args:
        frequency_range: Tuple of (start_freq, end_freq) in Hz
        db_connection: Database connection

    Returns:
        Signal classification results
    """
    query = """
    SELECT
        modulation,
        COUNT(*) as count,
        AVG(power_dbm) as avg_power,
        AVG(bandwidth) as avg_bandwidth
    FROM rf_signals
    WHERE frequency >= $1
        AND frequency <= $2
        AND timestamp >= NOW() - INTERVAL '1 hour'
    GROUP BY modulation
    ORDER BY count DESC
    """

    try:
        async with db_connection.acquire() as conn:
            rows = await conn.fetch(query, frequency_range[0], frequency_range[1])

            classifications = []
            for row in rows:
                classifications.append({
                    "modulation": row['modulation'] or "unknown",
                    "count": row['count'],
                    "avg_power_dbm": round(row['avg_power'], 2),
                    "avg_bandwidth_hz": row['avg_bandwidth']
                })

            return {
                "status": "success",
                "frequency_range": {
                    "start": frequency_range[0],
                    "end": frequency_range[1],
                    "start_mhz": frequency_range[0] / 1e6,
                    "end_mhz": frequency_range[1] / 1e6
                },
                "classifications": classifications,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# Skill metadata
SKILL_METADATA = {
    "name": "rf_monitoring",
    "version": "1.0.0",
    "description": "RF spectrum analysis and interference detection",
    "category": "rf_analysis",
    "functions": [
        {
            "name": "analyze_rf_spectrum",
            "description": "Analyze RF activity in a frequency range",
            "parameters": {
                "frequency_start": {"type": "float", "required": True},
                "frequency_end": {"type": "float", "required": True},
                "min_power_dbm": {"type": "float", "default": -90.0}
            }
        },
        {
            "name": "detect_interference",
            "description": "Detect interference near known frequencies",
            "parameters": {
                "known_frequencies": {"type": "array", "required": True},
                "tolerance_hz": {"type": "float", "default": 50000}
            }
        },
        {
            "name": "classify_signal_types",
            "description": "Classify signals by modulation type",
            "parameters": {
                "frequency_range": {"type": "tuple", "default": [88e6, 108e6]}
            }
        }
    ],
    "author": "AI-Optimizer Team",
    "created": "2025-11-22",
    "tags": ["rf", "spectrum", "interference", "signals", "sdr"]
}


if __name__ == "__main__":
    print(json.dumps(SKILL_METADATA, indent=2))
