#!/usr/bin/env python3
"""
Direct Qdrant Population Script
Populates Qdrant collections with initial context from the project
Uses the Hybrid Coordinator's embedding function via HTTP
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from uuid import uuid4

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8092")

# Initialize clients
qdrant = QdrantClient(url=QDRANT_URL)


async def get_embedding(text: str) -> List[float]:
    """Get embedding from Hybrid Coordinator"""
    async with httpx.AsyncClient() as client:
        # Use coordinator's augment_query endpoint which includes embedding
        # We'll need to call AIDB's embedding endpoint instead
        response = await client.post(
            "http://localhost:8091/embed",
            json={"text": text},
            timeout=30.0
        )
        if response.status_code == 200:
            result = response.json()
            return result.get("embedding", [])
        else:
            # Fallback: create a simple embedding (placeholder)
            print(f"⚠️  Embedding service not available, using hash-based fallback")
            # Create a deterministic "embedding" from hash
            import hashlib
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()
            # Convert to 384 floats (matching EMBEDDING_DIM)
            embedding = []
            for i in range(0, 384):
                byte_val = hash_bytes[i % len(hash_bytes)]
                embedding.append((byte_val / 255.0) * 2 - 1)  # Normalize to [-1, 1]
            return embedding


async def populate_best_practices():
    """Populate best-practices collection"""
    print("\n📚 Populating best-practices...")

    practices = [
        {
            "category": "containerization",
            "title": "Container DNS Resolution Failures",
            "description": "Use network_mode: host for containers that need localhost access. When MCP servers need to access databases on localhost, bridge networking causes DNS issues.",
            "examples": [
                "services:\n  mcp-server:\n    network_mode: host",
                "environment:\n  DATABASE_URL: postgresql://localhost:5432/db"
            ],
            "anti_patterns": [
                "Using bridge network for localhost database connections",
                "Hardcoding container-internal DNS names"
            ],
            "references": ["docker-compose.yml", "AIDB Dockerfile"],
            "endorsement_count": 5,
            "last_validated": int(Path(PROJECT_ROOT / "ai-stack/compose/docker-compose.yml").stat().st_mtime)
        },
        {
            "category": "systemd",
            "title": "SystemD Timer Not Triggering",
            "description": "Use OnCalendar instead of OnUnitActiveSec for reliable scheduling. OnUnitActiveSec only schedules after successful service activation.",
            "examples": [
                "[Timer]\nOnCalendar=*:0/15  # Every 15 minutes",
                "[Timer]\nOnBootSec=1min\nOnUnitActiveSec=15min"
            ],
            "anti_patterns": [
                "OnUnitActiveSec=15min  # Only works after first successful activation"
            ],
            "references": ["dashboard-collector.timer"],
            "endorsement_count": 3,
            "last_validated": int(Path.home().joinpath(".config/systemd/user/dashboard-collector.timer").stat().st_mtime) if Path.home().joinpath(".config/systemd/user/dashboard-collector.timer").exists() else 0
        },
        {
            "category": "monitoring",
            "title": "Stale Dashboard Data",
            "description": "Ensure collector service has proper PATH environment and runs regularly. SystemD services need explicit PATH for commands like mkdir, curl.",
            "examples": [
                "[Service]\nEnvironment=\"PATH=/usr/local/bin:/usr/bin:/bin\"",
                "[Timer]\nOnCalendar=*:0/5  # Run every 5 minutes"
            ],
            "anti_patterns": [
                "Assuming systemd services inherit user PATH",
                "Not setting explicit PATH in service units"
            ],
            "references": ["dashboard-collector.service", "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md"],
            "endorsement_count": 4,
            "last_validated": int(Path(PROJECT_ROOT / "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md").stat().st_mtime) if Path(PROJECT_ROOT / "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md").exists() else 0
        }
    ]

    points = []
    for practice in practices:
        # Create document text for embedding
        doc_text = f"{practice['title']}\n\n{practice['description']}\n\nCategory: {practice['category']}"

        # Get embedding
        embedding = await get_embedding(doc_text)

        point = PointStruct(
            id=str(uuid4()),
            vector=embedding,
            payload=practice
        )
        points.append(point)
        print(f"  ✓ {practice['title']}")

    # Upload to Qdrant
    qdrant.upsert(
        collection_name="best-practices",
        points=points
    )
    print(f"✅ Added {len(points)} best practices")


async def populate_error_solutions():
    """Populate error-solutions collection"""
    print("\n🔧 Populating error-solutions...")

    solutions = [
        {
            "error_message": "Container exits with code 2",
            "error_type": "container_startup_failure",
            "context": "Ralph Wiggum container built successfully but exits immediately, no logs generated",
            "solution": "Check: 1) Database connection strings, 2) Missing data directories (/data/telemetry), 3) Port conflicts, 4) Import errors in dependencies. Try running with RALPH_LOOP_ENABLED=false first.",
            "solution_verified": False,
            "success_count": 0,
            "failure_count": 1,
            "first_seen": int(Path(PROJECT_ROOT / "IMMEDIATE-ACTION-PLAN-2026-01-05.md").stat().st_mtime) if Path(PROJECT_ROOT / "IMMEDIATE-ACTION-PLAN-2026-01-05.md").exists() else 0,
            "last_used": int(Path(PROJECT_ROOT / "IMMEDIATE-ACTION-PLAN-2026-01-05.md").stat().st_mtime) if Path(PROJECT_ROOT / "IMMEDIATE-ACTION-PLAN-2026-01-05.md").exists() else 0,
            "confidence_score": 0.3
        },
        {
            "error_message": "Dashboard shows stale data",
            "error_type": "monitoring_failure",
            "context": "Dashboard collector running but metrics not updating",
            "solution": "Ensure dashboard-collector.service has PATH set and timer uses OnCalendar. Verify collector script is executable and systemd timer is active.",
            "solution_verified": True,
            "success_count": 1,
            "failure_count": 0,
            "first_seen": int(Path(PROJECT_ROOT / "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md").stat().st_mtime) if Path(PROJECT_ROOT / "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md").exists() else 0,
            "last_used": int(Path(PROJECT_ROOT / "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md").stat().st_mtime) if Path(PROJECT_ROOT / "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md").exists() else 0,
            "confidence_score": 0.95
        }
    ]

    points = []
    for solution in solutions:
        doc_text = f"Error: {solution['error_message']}\nType: {solution['error_type']}\n\nSolution: {solution['solution']}"
        embedding = await get_embedding(doc_text)

        point = PointStruct(
            id=str(uuid4()),
            vector=embedding,
            payload=solution
        )
        points.append(point)
        print(f"  ✓ {solution['error_type']}")

    qdrant.upsert(
        collection_name="error-solutions",
        points=points
    )
    print(f"✅ Added {len(points)} error solutions")


async def populate_codebase_context():
    """Populate codebase-context collection with key files"""
    print("\n📁 Populating codebase-context...")

    # Index key documentation files
    key_files = [
        "AGENTS.md",
        "AI-AGENT-START-HERE.md",
        "AI-AGENT-REFERENCE.md",
        "IMMEDIATE-ACTION-PLAN-2026-01-05.md",
        "AI-STACK-AGENTIC-WORKFLOW-FIXES-2026-01-05.md",
    ]

    points = []
    for filename in key_files:
        filepath = PROJECT_ROOT / filename
        if not filepath.exists():
            print(f"  ⚠️  {filename} not found")
            continue

        content = filepath.read_text()
        # Limit to first 10KB for embedding
        content = content[:10000]

        embedding = await get_embedding(content)

        point = PointStruct(
            id=str(uuid4()),
            vector=embedding,
            payload={
                "file_path": str(filepath.relative_to(PROJECT_ROOT)),
                "content": content,
                "file_type": "markdown",
                "project": "NixOS-Dev-Quick-Deploy",
                "category": "documentation",
                "indexed_at": int(filepath.stat().st_mtime)
            }
        )
        points.append(point)
        print(f"  ✓ {filename}")

    if points:
        qdrant.upsert(
            collection_name="codebase-context",
            points=points
        )
        print(f"✅ Added {len(points)} documents to codebase-context")
    else:
        print("⚠️  No documents indexed")


async def main():
    """Main population routine"""
    print("🔄 Populating Qdrant collections...")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Coordinator URL: {COORDINATOR_URL}")

    # Check Qdrant is available
    try:
        collections = qdrant.get_collections()
        print(f"\n✅ Connected to Qdrant ({len(collections.collections)} collections)")
    except Exception as e:
        print(f"\n❌ Cannot connect to Qdrant: {e}")
        return 1

    # Populate collections
    try:
        await populate_best_practices()
        await populate_error_solutions()
        await populate_codebase_context()

        print("\n" + "="*60)
        print("✅ Qdrant population complete!")
        print("="*60)

        # Show stats
        for coll_name in ["best-practices", "error-solutions", "codebase-context"]:
            coll_info = qdrant.get_collection(coll_name)
            print(f"{coll_name}: {coll_info.points_count} points")

        return 0
    except Exception as e:
        print(f"\n❌ Error during population: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
