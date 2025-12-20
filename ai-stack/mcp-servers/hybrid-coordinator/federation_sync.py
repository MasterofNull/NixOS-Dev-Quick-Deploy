#!/usr/bin/env python3
"""
Federation Sync Service for Hybrid Learning System

Enables multiple NixOS deployments to:
- Share high-value learning data
- Aggregate patterns and skills
- Distribute model improvements
- Synchronize knowledge bases

Supports three modes:
- Peer: Equal peer-to-peer synchronization
- Hub: Central aggregation node
- Spoke: Edge node that syncs with hub
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct, Range

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("federation-sync")


# ============================================================================
# Configuration
# ============================================================================

class FederationConfig:
    """Federation configuration"""

    def __init__(self):
        self.node_id = os.getenv("FEDERATION_NODE_ID", os.uname().nodename)
        self.mode = os.getenv("FEDERATION_MODE", "peer")  # peer, hub, spoke
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.sync_port = int(os.getenv("FEDERATION_PORT", "8092"))
        self.data_dir = Path(os.getenv("HYBRID_DATA_DIR", "/var/lib/hybrid-learning"))
        self.export_dir = self.data_dir / "exports"
        self.conflict_resolution = os.getenv("CONFLICT_RESOLUTION", "highest-value")


# ============================================================================
# Data Structures
# ============================================================================

class SyncManifest:
    """Manifest of data available for synchronization"""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.timestamp = datetime.now().isoformat()
        self.collections: Dict[str, CollectionManifest] = {}

    def add_collection(self, name: str, manifest: "CollectionManifest"):
        self.collections[name] = manifest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "collections": {
                name: manifest.to_dict()
                for name, manifest in self.collections.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncManifest":
        manifest = cls(data["node_id"])
        manifest.timestamp = data["timestamp"]
        manifest.collections = {
            name: CollectionManifest.from_dict(coll_data)
            for name, coll_data in data["collections"].items()
        }
        return manifest


class CollectionManifest:
    """Manifest for a single collection"""

    def __init__(self, name: str, count: int, last_updated: str):
        self.name = name
        self.count = count
        self.last_updated = last_updated
        self.high_value_count = 0
        self.checksum = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "last_updated": self.last_updated,
            "high_value_count": self.high_value_count,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollectionManifest":
        manifest = cls(data["name"], data["count"], data["last_updated"])
        manifest.high_value_count = data.get("high_value_count", 0)
        manifest.checksum = data.get("checksum", "")
        return manifest


# ============================================================================
# Federation Sync Manager
# ============================================================================

class FederationSyncManager:
    """Manages synchronization between federation nodes"""

    def __init__(self, config: FederationConfig, nodes: List[str]):
        self.config = config
        self.nodes = nodes
        self.qdrant = QdrantClient(url=config.qdrant_url, timeout=30.0)
        self.http_client = httpx.AsyncClient(timeout=60.0)

        # Collections to sync (only high-value data)
        self.sync_collections = [
            "skills-patterns",
            "error-solutions",
            "best-practices",
            # interaction-history is node-specific, not synced
            # codebase-context is project-specific, optionally synced
        ]

    async def generate_manifest(self) -> SyncManifest:
        """Generate manifest of local data for synchronization"""
        manifest = SyncManifest(self.config.node_id)

        for collection_name in self.sync_collections:
            try:
                # Get collection info
                collection_info = self.qdrant.get_collection(collection_name)
                count = collection_info.points_count

                # Count high-value items
                high_value_filter = Filter(
                    must=[FieldCondition(key="value_score", range=Range(gte=0.7))]
                )
                high_value_results = self.qdrant.scroll(
                    collection_name=collection_name,
                    scroll_filter=high_value_filter,
                    limit=1,
                )
                high_value_count = high_value_results[1] if high_value_results else 0

                # Create collection manifest
                coll_manifest = CollectionManifest(
                    name=collection_name,
                    count=count,
                    last_updated=datetime.now().isoformat(),
                )
                coll_manifest.high_value_count = high_value_count

                # Compute checksum (simple implementation)
                checksum_data = f"{collection_name}:{count}:{high_value_count}"
                coll_manifest.checksum = hashlib.sha256(
                    checksum_data.encode()
                ).hexdigest()[:16]

                manifest.add_collection(collection_name, coll_manifest)

                logger.info(
                    f"Collection {collection_name}: {count} items, {high_value_count} high-value"
                )

            except Exception as e:
                logger.error(f"Error generating manifest for {collection_name}: {e}")

        return manifest

    async def export_collection_data(
        self, collection_name: str, min_value_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Export high-value data from a collection"""
        try:
            # Filter for high-value items
            value_filter = Filter(
                must=[FieldCondition(key="value_score", range=Range(gte=min_value_score))]
            )

            # Scroll through all high-value points
            points, _ = self.qdrant.scroll(
                collection_name=collection_name,
                scroll_filter=value_filter,
                limit=1000,
                with_vectors=True,
                with_payload=True,
            )

            # Convert to exportable format
            export_data = []
            for point in points:
                export_data.append(
                    {
                        "id": str(point.id),
                        "vector": point.vector,
                        "payload": point.payload,
                        "source_node": self.config.node_id,
                        "export_timestamp": datetime.now().isoformat(),
                    }
                )

            logger.info(f"Exported {len(export_data)} items from {collection_name}")
            return export_data

        except Exception as e:
            logger.error(f"Error exporting {collection_name}: {e}")
            return []

    async def import_collection_data(
        self, collection_name: str, data: List[Dict[str, Any]]
    ) -> int:
        """Import data into a collection with conflict resolution"""
        imported_count = 0

        for item in data:
            try:
                point_id = item["id"]
                vector = item["vector"]
                payload = item["payload"]
                source_node = item.get("source_node", "unknown")

                # Check if point already exists
                existing = None
                try:
                    existing_points = self.qdrant.retrieve(
                        collection_name=collection_name, ids=[point_id]
                    )
                    existing = existing_points[0] if existing_points else None
                except Exception:
                    pass

                # Conflict resolution
                should_import = True
                if existing:
                    should_import = self._resolve_conflict(
                        existing.payload, payload, source_node
                    )

                if should_import:
                    # Add metadata
                    payload["imported_from"] = source_node
                    payload["import_timestamp"] = datetime.now().isoformat()

                    # Upsert point
                    self.qdrant.upsert(
                        collection_name=collection_name,
                        points=[
                            PointStruct(id=point_id, vector=vector, payload=payload)
                        ],
                    )
                    imported_count += 1

            except Exception as e:
                logger.error(f"Error importing point {item.get('id', 'unknown')}: {e}")

        logger.info(f"Imported {imported_count} items into {collection_name}")
        return imported_count

    def _resolve_conflict(
        self, existing: Dict[str, Any], incoming: Dict[str, Any], source_node: str
    ) -> bool:
        """
        Resolve conflicts between existing and incoming data

        Returns True if incoming should replace existing
        """
        strategy = self.config.conflict_resolution

        if strategy == "latest":
            # Most recent update wins
            existing_time = existing.get("last_updated", existing.get("timestamp", 0))
            incoming_time = incoming.get("last_updated", incoming.get("timestamp", 0))
            return incoming_time > existing_time

        elif strategy == "highest-value":
            # Highest value score wins
            existing_value = existing.get("value_score", 0)
            incoming_value = incoming.get("value_score", 0)
            return incoming_value > existing_value

        elif strategy == "merge":
            # Merge data (simplified: update if incoming has more info)
            existing_keys = set(existing.keys())
            incoming_keys = set(incoming.keys())
            return len(incoming_keys) > len(existing_keys)

        elif strategy == "manual":
            # Manual resolution required (for now, skip)
            logger.warning(f"Manual conflict resolution required for source {source_node}")
            return False

        else:
            # Default: don't import on conflict
            return False

    async def sync_with_node(self, node_url: str) -> Dict[str, Any]:
        """Synchronize with a single node"""
        logger.info(f"Syncing with node: {node_url}")

        try:
            # 1. Get remote manifest
            response = await self.http_client.get(f"{node_url}/manifest")
            response.raise_for_status()
            remote_manifest = SyncManifest.from_dict(response.json())

            logger.info(f"Remote node: {remote_manifest.node_id}")

            # 2. Generate local manifest
            local_manifest = await self.generate_manifest()

            # 3. Determine what to sync
            sync_plan = self._create_sync_plan(local_manifest, remote_manifest)

            # 4. Execute sync plan
            sync_results = await self._execute_sync_plan(node_url, sync_plan)

            return {
                "node": node_url,
                "remote_node_id": remote_manifest.node_id,
                "status": "success",
                "results": sync_results,
            }

        except Exception as e:
            logger.error(f"Error syncing with {node_url}: {e}")
            return {"node": node_url, "status": "error", "error": str(e)}

    def _create_sync_plan(
        self, local: SyncManifest, remote: SyncManifest
    ) -> Dict[str, str]:
        """
        Create synchronization plan

        Returns dict of collection_name -> action ("pull", "push", "skip")
        """
        plan = {}

        for collection_name in self.sync_collections:
            local_coll = local.collections.get(collection_name)
            remote_coll = remote.collections.get(collection_name)

            if not local_coll and not remote_coll:
                plan[collection_name] = "skip"
            elif not local_coll:
                plan[collection_name] = "pull"  # Remote has data, we don't
            elif not remote_coll:
                plan[collection_name] = "push"  # We have data, remote doesn't
            elif local_coll.checksum != remote_coll.checksum:
                # Data differs, sync both ways
                if remote_coll.high_value_count > local_coll.high_value_count:
                    plan[collection_name] = "pull"
                else:
                    plan[collection_name] = "push"
            else:
                plan[collection_name] = "skip"  # Data is identical

        return plan

    async def _execute_sync_plan(
        self, node_url: str, plan: Dict[str, str]
    ) -> Dict[str, Any]:
        """Execute the synchronization plan"""
        results = {}

        for collection_name, action in plan.items():
            if action == "skip":
                results[collection_name] = {"action": "skip", "count": 0}
                continue

            try:
                if action == "pull":
                    # Pull data from remote node
                    response = await self.http_client.get(
                        f"{node_url}/export/{collection_name}"
                    )
                    response.raise_for_status()
                    remote_data = response.json()

                    count = await self.import_collection_data(
                        collection_name, remote_data
                    )
                    results[collection_name] = {"action": "pull", "count": count}

                elif action == "push":
                    # Push data to remote node
                    local_data = await self.export_collection_data(collection_name)

                    response = await self.http_client.post(
                        f"{node_url}/import/{collection_name}",
                        json=local_data,
                        timeout=120.0,
                    )
                    response.raise_for_status()
                    result = response.json()

                    results[collection_name] = {
                        "action": "push",
                        "count": result.get("imported", 0),
                    }

            except Exception as e:
                logger.error(f"Error syncing {collection_name}: {e}")
                results[collection_name] = {"action": action, "error": str(e)}

        return results

    async def sync_all_nodes(self) -> List[Dict[str, Any]]:
        """Synchronize with all configured nodes"""
        results = []

        for node_url in self.nodes:
            result = await self.sync_with_node(node_url)
            results.append(result)

        return results

    async def save_export_snapshot(self) -> str:
        """Save complete export snapshot for backup/transfer"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        export_path = self.config.export_dir / f"snapshot-{timestamp}.json"

        self.config.export_dir.mkdir(parents=True, exist_ok=True)

        # Generate manifest
        manifest = await self.generate_manifest()

        # Export all collections
        export_data = {"manifest": manifest.to_dict(), "collections": {}}

        for collection_name in self.sync_collections:
            data = await self.export_collection_data(collection_name)
            export_data["collections"][collection_name] = data

        # Save to file
        with open(export_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Export snapshot saved: {export_path}")
        return str(export_path)

    async def load_import_snapshot(self, snapshot_path: str) -> Dict[str, int]:
        """Load and import data from snapshot file"""
        with open(snapshot_path, "r") as f:
            import_data = json.load(f)

        results = {}
        for collection_name, data in import_data.get("collections", {}).items():
            count = await self.import_collection_data(collection_name, data)
            results[collection_name] = count

        logger.info(f"Import snapshot loaded from: {snapshot_path}")
        return results


# ============================================================================
# HTTP Server for Federation API
# ============================================================================

async def run_federation_server(manager: FederationSyncManager, port: int):
    """Run HTTP server for federation API endpoints"""
    from aiohttp import web

    async def handle_manifest(request):
        """Return current data manifest"""
        manifest = await manager.generate_manifest()
        return web.json_response(manifest.to_dict())

    async def handle_export(request):
        """Export collection data"""
        collection_name = request.match_info["collection"]
        data = await manager.export_collection_data(collection_name)
        return web.json_response(data)

    async def handle_import(request):
        """Import collection data"""
        collection_name = request.match_info["collection"]
        data = await request.json()
        count = await manager.import_collection_data(collection_name, data)
        return web.json_response({"imported": count})

    async def handle_sync_trigger(request):
        """Manually trigger sync with all nodes"""
        results = await manager.sync_all_nodes()
        return web.json_response({"results": results})

    app = web.Application()
    app.router.add_get("/manifest", handle_manifest)
    app.router.add_get("/export/{collection}", handle_export)
    app.router.add_post("/import/{collection}", handle_import)
    app.router.add_post("/sync", handle_sync_trigger)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"Federation server running on port {port}")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Federation sync service for hybrid learning"
    )
    parser.add_argument(
        "--nodes", type=str, help="Comma-separated list of node URLs"
    )
    parser.add_argument("--mode", type=str, default="peer", help="Federation mode")
    parser.add_argument(
        "--sync-interval", type=int, default=3600, help="Sync interval in seconds"
    )
    parser.add_argument("--export", type=str, help="Export snapshot to file")
    parser.add_argument("--import", type=str, dest="import_file", help="Import snapshot from file")
    parser.add_argument(
        "--server", action="store_true", help="Run federation HTTP server"
    )

    args = parser.parse_args()

    # Initialize config
    config = FederationConfig()
    if args.mode:
        config.mode = args.mode

    # Parse nodes
    nodes = []
    if args.nodes:
        nodes = [n.strip() for n in args.nodes.split(",") if n.strip()]

    # Create manager
    manager = FederationSyncManager(config, nodes)

    # Handle commands
    if args.export:
        # Export snapshot
        snapshot_path = await manager.save_export_snapshot()
        print(f"Exported to: {snapshot_path}")

    elif args.import_file:
        # Import snapshot
        results = await manager.load_import_snapshot(args.import_file)
        print(f"Imported: {results}")

    elif args.server:
        # Run federation server
        await run_federation_server(manager, config.sync_port)
        # Keep running
        while True:
            await asyncio.sleep(3600)

    else:
        # Run sync loop
        logger.info(f"Starting federation sync (mode: {config.mode})")
        logger.info(f"Nodes: {nodes}")

        while True:
            try:
                logger.info("Running synchronization...")
                results = await manager.sync_all_nodes()

                for result in results:
                    if result["status"] == "success":
                        logger.info(
                            f"Synced with {result['remote_node_id']}: {result['results']}"
                        )
                    else:
                        logger.error(
                            f"Sync failed with {result['node']}: {result.get('error', 'Unknown error')}"
                        )

                logger.info(f"Next sync in {args.sync_interval} seconds")
                await asyncio.sleep(args.sync_interval)

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
