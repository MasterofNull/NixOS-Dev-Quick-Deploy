#!/usr/bin/env python3
"""
Continuous Learning Daemon
Processes telemetry and generates fine-tuning datasets
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from continuous_learning import ContinuousLearningPipeline
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger("hybrid_coordinator.continuous_learning_daemon")


class Settings(BaseModel):
    """Minimal settings for learning pipeline"""
    enabled: bool = True
    processing_interval: int = 3600  # 1 hour


async def main():
    """Run continuous learning daemon"""
    logger.info("Starting Continuous Learning Pipeline Daemon")

    # Load settings from environment
    settings = Settings(
        enabled=os.getenv("CONTINUOUS_LEARNING_ENABLED", "true").lower() == "true",
        processing_interval=int(os.getenv("LEARNING_PROCESSING_INTERVAL", "3600"))
    )

    if not settings.enabled:
        logger.info("Continuous learning is disabled via configuration")
        return 0

    # Initialize Qdrant client
    qdrant = None
    try:
        from qdrant_client import AsyncQdrantClient

        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        qdrant = AsyncQdrantClient(url=qdrant_url)
        logger.info(f"Connected to Qdrant at {qdrant_url}")
    except Exception as e:
        logger.warning(f"Qdrant not available: {e}. Pattern indexing disabled.")

    # PostgreSQL client (optional)
    postgres = None  # TODO: Add if needed for metrics storage

    # Create learning pipeline
    pipeline = ContinuousLearningPipeline(settings, qdrant, postgres)

    # Start pipeline
    try:
        await pipeline.start()
        logger.info("Continuous Learning Pipeline started successfully")

        # Keep running and log stats
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes

            # Log statistics
            stats = await pipeline.get_statistics()
            logger.info(
                f"Learning stats: {stats['total_patterns_learned']} patterns, "
                f"{stats['finetuning_dataset_size']} dataset examples"
            )

            # Check if ready for fine-tuning
            if await pipeline.should_trigger_finetuning():
                logger.info("🎓 Dataset ready for fine-tuning (1000+ examples)")
                logger.info("Export dataset: /data/fine-tuning/dataset.jsonl")

    except KeyboardInterrupt:
        logger.info("Shutting down Continuous Learning Pipeline")
        await pipeline.stop()
    except Exception as e:
        logger.error(f"Learning Pipeline error: {e}", exc_info=True)
        await pipeline.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
