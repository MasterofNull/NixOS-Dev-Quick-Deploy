#!/usr/bin/env python3
"""
Tool Discovery Daemon
Runs alongside AIDB server to automatically discover and index tools
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from tool_discovery import ToolDiscoveryEngine
from settings_loader import load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

logger = logging.getLogger("aidb.tool_discovery_daemon")


async def main():
    """Run tool discovery daemon"""
    logger.info("Starting Tool Discovery Daemon")

    # Load settings
    config_path = Path(os.getenv("AIDB_CONFIG", "/app/config/config.yaml"))
    settings = load_settings(config_path if config_path.exists() else None)

    # Initialize Qdrant client (lazy import to avoid startup dependency issues)
    try:
        from qdrant_client import AsyncQdrantClient

        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        qdrant = AsyncQdrantClient(url=qdrant_url)

        logger.info(f"Connected to Qdrant at {qdrant_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        logger.info("Tool discovery will run without Qdrant indexing")
        qdrant = None

    # Initialize PostgreSQL client (optional)
    postgres = None  # TODO: Add if needed

    # Create discovery engine
    engine = ToolDiscoveryEngine(qdrant, postgres, settings)

    # Start discovery loop
    try:
        await engine.start()
        logger.info("Tool Discovery Engine started successfully")

        # Keep running
        while True:
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        logger.info("Shutting down Tool Discovery Daemon")
        await engine.stop()
    except Exception as e:
        logger.error(f"Tool Discovery Daemon error: {e}", exc_info=True)
        await engine.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
