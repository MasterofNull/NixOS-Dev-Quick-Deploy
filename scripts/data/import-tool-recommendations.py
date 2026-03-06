#!/usr/bin/env python3
"""
Import Tool Recommendations into Qdrant for PRSI Hints

Reads tool-recommendations-seed.yaml and upserts into Qdrant's
skills-patterns collection for use by the hints engine.

Environment:
  QDRANT_URL        Override Qdrant URL (default: http://localhost:6333)
  EMBEDDING_URL     Override embedding service (default: http://localhost:8081)
  VERBOSE           Enable debug output

Usage:
  python3 scripts/data/import-tool-recommendations.py
  python3 scripts/data/import-tool-recommendations.py --dry-run
  python3 scripts/data/import-tool-recommendations.py --collection tool-recommendations
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required. Install with: pip install pyyaml")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("VERBOSE") else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("import-tool-recommendations")

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SEED_FILE = REPO_ROOT / "ai-stack" / "data" / "tool-recommendations-seed.yaml"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://localhost:8081")
DEFAULT_COLLECTION = "skills-patterns"
EMBEDDING_DIM = 2560  # Qwen3-Embedding-4B dimension


def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding vector from local embedding service."""
    if not text.strip():
        return None

    payload = json.dumps({"input": text[:4096]}).encode()
    req = urllib.request.Request(
        f"{EMBEDDING_URL}/embedding",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            # Handle llama.cpp /embedding response format:
            # [{"index": 0, "embedding": [[float, ...]]}]
            if isinstance(data, list) and data:
                item = data[0]
                if isinstance(item, dict) and "embedding" in item:
                    emb = item["embedding"]
                    # embedding can be [[floats]] or [floats]
                    if isinstance(emb, list) and emb:
                        if isinstance(emb[0], list):
                            return emb[0]
                        return emb
                if isinstance(item, list):
                    return item
            if isinstance(data, dict):
                emb = data.get("embedding") or data.get("data", [{}])[0].get("embedding")
                if isinstance(emb, list) and emb and isinstance(emb[0], list):
                    return emb[0]
                return emb
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
    return None


def upsert_to_qdrant(
    collection: str,
    point_id: str,
    vector: List[float],
    payload: Dict[str, Any],
    dry_run: bool = False
) -> bool:
    """Upsert a single point to Qdrant."""
    if dry_run:
        logger.info(f"  [DRY-RUN] Would upsert: {point_id}")
        return True

    # Generate deterministic numeric ID from string ID
    numeric_id = int(hashlib.md5(point_id.encode()).hexdigest()[:16], 16)

    body = {
        "points": [
            {
                "id": numeric_id,
                "vector": vector,
                "payload": {**payload, "tool_id": point_id},
            }
        ]
    }

    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{collection}/points?wait=true",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("status") == "ok" or result.get("result", {}).get("status") == "completed"
    except urllib.error.HTTPError as e:
        logger.error(f"Qdrant upsert failed for {point_id}: {e.code} - {e.read().decode()}")
        return False
    except Exception as e:
        logger.error(f"Qdrant upsert failed for {point_id}: {e}")
        return False


def ensure_collection_exists(collection: str, dry_run: bool = False) -> bool:
    """Ensure the Qdrant collection exists."""
    if dry_run:
        logger.info(f"[DRY-RUN] Would ensure collection: {collection}")
        return True

    # Check if collection exists
    try:
        req = urllib.request.Request(f"{QDRANT_URL}/collections/{collection}")
        with urllib.request.urlopen(req, timeout=10):
            logger.info(f"✓ Collection '{collection}' exists")
            return True
    except urllib.error.HTTPError as e:
        if e.code != 404:
            logger.error(f"Error checking collection: {e}")
            return False

    # Create collection
    logger.info(f"Creating collection: {collection}")
    body = {
        "vectors": {
            "size": EMBEDDING_DIM,
            "distance": "Cosine"
        }
    }

    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{collection}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("result"):
                logger.info(f"✓ Collection '{collection}' created")
                return True
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")

    return False


def build_search_text(tool: Dict[str, Any]) -> str:
    """Build searchable text from tool metadata."""
    parts = [
        tool.get("name", ""),
        tool.get("description", ""),
        tool.get("when_to_use", ""),
        " ".join(tool.get("tags", [])),
    ]

    if tool.get("language"):
        parts.append(f"language:{tool['language']}")
    if tool.get("type"):
        parts.append(f"type:{tool['type']}")
    if tool.get("examples"):
        parts.extend(tool["examples"])
    if tool.get("commands"):
        parts.extend(tool["commands"])

    return " ".join(filter(None, parts))


def build_payload(tool: Dict[str, Any], category: str) -> Dict[str, Any]:
    """Build Qdrant payload from tool metadata."""
    return {
        "skill_name": tool.get("name", ""),
        "description": tool.get("description", ""),
        "usage_pattern": tool.get("when_to_use", ""),
        "success_examples": tool.get("examples", []),
        "failure_examples": [],
        "prerequisites": tool.get("install", "").split() if tool.get("install") else [],
        "related_skills": tool.get("tags", []),
        "value_score": 0.8 if tool.get("priority") == "high" else 0.6 if tool.get("priority") == "medium" else 0.4,
        "last_updated": 0,
        # Extended metadata
        "tool_type": tool.get("type", "cli"),
        "tool_category": category,
        "language": tool.get("language", ""),
        "install": tool.get("install", ""),
        "commands": tool.get("commands", []),
        "flags": tool.get("flags", []),
        "port": tool.get("port"),
        "endpoints": tool.get("endpoints", []),
        "transport": tool.get("transport", ""),
        "alias": tool.get("alias", ""),
        "priority": tool.get("priority", "medium"),
        "tags": tool.get("tags", []),
    }


def import_tools(
    seed_file: Path,
    collection: str,
    dry_run: bool = False
) -> Dict[str, int]:
    """Import all tools from seed file into Qdrant."""
    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    # Load seed file
    logger.info(f"Loading seed file: {seed_file}")
    try:
        with open(seed_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load seed file: {e}")
        return stats

    if not isinstance(data, dict):
        logger.error("Invalid seed file format")
        return stats

    # Ensure collection exists
    if not ensure_collection_exists(collection, dry_run):
        logger.error("Failed to ensure collection exists")
        return stats

    # Process each category
    categories = [
        "mcp_servers",
        "ai_stack_tools",
        "skills",
        "data_tools",
        "linters",
        "testing",
        "security",
        "database",
        "nixos",
        "shell_utils",
        "ai_tools",
        "rag_tools",
        "build_tools",
        "docs_tools",
        "git_tools",
        "container_tools",
    ]

    for category in categories:
        tools = data.get(category, [])
        if not tools:
            continue

        logger.info(f"\n=== Processing {category} ({len(tools)} tools) ===")

        for tool in tools:
            stats["total"] += 1
            tool_id = tool.get("id", "")
            tool_name = tool.get("name", "")

            if not tool_id:
                logger.warning(f"Skipping tool without ID: {tool_name}")
                stats["skipped"] += 1
                continue

            # Build search text and get embedding
            search_text = build_search_text(tool)
            if not search_text.strip():
                logger.warning(f"Skipping tool with empty search text: {tool_id}")
                stats["skipped"] += 1
                continue

            logger.debug(f"Processing: {tool_id} ({tool_name})")

            if not dry_run:
                vector = get_embedding(search_text)
                if not vector:
                    logger.warning(f"Failed to get embedding for: {tool_id}")
                    stats["failed"] += 1
                    continue
            else:
                vector = [0.0] * EMBEDDING_DIM  # Dummy for dry-run

            # Build payload
            payload = build_payload(tool, category)

            # Upsert to Qdrant
            if upsert_to_qdrant(collection, tool_id, vector, payload, dry_run):
                stats["success"] += 1
                logger.info(f"  ✓ {tool_name}")
            else:
                stats["failed"] += 1
                logger.error(f"  ✗ {tool_name}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Import tool recommendations into Qdrant for PRSI hints"
    )
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=SEED_FILE,
        help=f"Path to seed YAML file (default: {SEED_FILE})"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=DEFAULT_COLLECTION,
        help=f"Qdrant collection name (default: {DEFAULT_COLLECTION})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without making changes"
    )
    args = parser.parse_args()

    if not args.seed_file.exists():
        logger.error(f"Seed file not found: {args.seed_file}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Tool Recommendations Import")
    logger.info("=" * 60)
    logger.info(f"Seed file:  {args.seed_file}")
    logger.info(f"Collection: {args.collection}")
    logger.info(f"Qdrant:     {QDRANT_URL}")
    logger.info(f"Embedding:  {EMBEDDING_URL}")
    logger.info(f"Dry run:    {args.dry_run}")
    logger.info("=" * 60)

    stats = import_tools(args.seed_file, args.collection, args.dry_run)

    logger.info("\n" + "=" * 60)
    logger.info("Import Complete")
    logger.info("=" * 60)
    logger.info(f"Total tools:  {stats['total']}")
    logger.info(f"Success:      {stats['success']}")
    logger.info(f"Failed:       {stats['failed']}")
    logger.info(f"Skipped:      {stats['skipped']}")

    if stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
