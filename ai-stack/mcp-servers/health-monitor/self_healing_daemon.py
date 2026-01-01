#!/usr/bin/env python3
"""
Self-Healing Daemon
Monitors container health and performs automatic repairs
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from self_healing import SelfHealingOrchestrator
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger("health_monitor.self_healing_daemon")


class Settings(BaseModel):
    """Minimal settings for self-healing"""
    enabled: bool = True
    check_interval: int = 30  # seconds


async def main():
    """Run self-healing daemon"""
    logger.info("Starting Self-Healing Orchestrator Daemon")

    # Load settings from environment
    settings = Settings(
        enabled=os.getenv("SELF_HEALING_ENABLED", "true").lower() == "true",
        check_interval=int(os.getenv("SELF_HEALING_CHECK_INTERVAL", "30"))
    )

    if not settings.enabled:
        logger.info("Self-healing is disabled via configuration")
        return 0

    # Initialize Qdrant client (optional, for pattern storage)
    qdrant = None
    try:
        from qdrant_client import AsyncQdrantClient

        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        qdrant = AsyncQdrantClient(url=qdrant_url)
        logger.info(f"Connected to Qdrant at {qdrant_url}")
    except Exception as e:
        logger.warning(f"Qdrant not available: {e}. Continuing without pattern storage.")

    # Create orchestrator
    orchestrator = SelfHealingOrchestrator(settings, qdrant)

    # Start monitoring
    try:
        await orchestrator.start()
        logger.info("Self-Healing Orchestrator started successfully")

        # Keep running
        while True:
            await asyncio.sleep(60)

            # Log statistics periodically
            stats = await orchestrator.get_statistics()
            if stats["total_healing_actions"] > 0:
                logger.info(
                    f"Healing stats: {stats['total_healing_actions']} actions, "
                    f"{stats['success_rate']:.1%} success rate"
                )

    except KeyboardInterrupt:
        logger.info("Shutting down Self-Healing Orchestrator")
        await orchestrator.stop()
    except Exception as e:
        logger.error(f"Self-Healing Daemon error: {e}", exc_info=True)
        await orchestrator.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
