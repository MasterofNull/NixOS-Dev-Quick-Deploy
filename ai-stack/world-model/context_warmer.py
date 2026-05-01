"""
Context Warmer — Phase 20: World Model Predictive Warming

Pre-loads AIDB + semantic cache for predicted queries by calling /query with
skip_gap_tracking=true. Respects a budget of max queries per run.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

logger = logging.getLogger("world-model")

_COORDINATOR_URL: str = os.environ.get("COORDINATOR_URL", "http://127.0.0.1:8003")
_WARM_THRESHOLD: float = float(os.environ.get("WORLD_MODEL_WARM_THRESHOLD", "0.4"))
_MAX_WARM: int = int(os.environ.get("WORLD_MODEL_MAX_WARM_QUERIES", "5"))
_DATA_DIR: str = os.environ.get("DATA_DIR", "/var/lib/ai-stack/hybrid")
_LOG_PATH: str = os.path.join(_DATA_DIR, "telemetry", "world-model-warm-latest.json")

_API_KEY_FILE: str = os.environ.get("HYBRID_COORDINATOR_API_KEY_FILE", "")
_API_KEY: str = os.environ.get("HYBRID_COORDINATOR_API_KEY", "")


def _get_api_key() -> str:
    if _API_KEY_FILE:
        try:
            return open(_API_KEY_FILE).read().strip()
        except OSError:
            pass
    return _API_KEY


class ContextWarmer:
    """Proactively warms the semantic cache for predicted queries."""

    def warm(
        self,
        predictions: List[Dict[str, Any]],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute warming for each prediction above threshold.

        Returns a summary log dict.
        """
        eligible = [
            p for p in predictions
            if p.get("confidence", 0.0) >= _WARM_THRESHOLD
        ][:_MAX_WARM]

        log_entries: List[Dict[str, Any]] = []
        api_key = _get_api_key()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        for pred in eligible:
            entry: Dict[str, Any] = {
                "query": pred["query"],
                "confidence": pred["confidence"],
                "source": pred.get("source", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": dry_run,
            }
            if dry_run:
                logger.info("dry_run warm: %s (%.2f)", pred["query"][:60], pred["confidence"])
                entry["status"] = "dry_run"
            else:
                try:
                    with httpx.Client(timeout=30.0) as client:
                        resp = client.post(
                            f"{_COORDINATOR_URL}/query",
                            json={
                                "query": pred["query"],
                                "skip_gap_tracking": True,
                                "context_source": "world_model_prewarm",
                                "generate_response": False,
                            },
                            headers=headers,
                        )
                        entry["status"] = "ok" if resp.status_code == 200 else f"http_{resp.status_code}"
                        entry["cache_hit"] = (
                            resp.json().get("capability_discovery", {}).get("cache_hit", False)
                            if resp.status_code == 200 else False
                        )
                except Exception as exc:
                    entry["status"] = "error"
                    entry["error"] = str(exc)[:100]
                    logger.debug("context_warmer warm error (non-fatal): %s", exc)

            log_entries.append(entry)

        summary = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "eligible": len(eligible),
            "dry_run": dry_run,
            "entries": log_entries,
        }

        # Write telemetry log
        try:
            Path(_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
            Path(_LOG_PATH).write_text(json.dumps(summary, indent=2))
        except OSError as exc:
            logger.debug("context_warmer log write failed (non-fatal): %s", exc)

        return summary
