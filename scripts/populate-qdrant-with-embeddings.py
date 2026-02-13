#!/usr/bin/env python3
"""
Qdrant Population with Proper Semantic Embeddings
Uses sentence-transformers for generating meaningful embeddings
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from uuid import uuid4

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("⚠️  sentence-transformers not installed")
    print("   Installing for semantic embeddings...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "sentence-transformers", "-q"])
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")
QDRANT_URL = os.getenv("QDRANT_URL", f"http://{SERVICE_HOST}:6333")

# Initialize clients
qdrant = QdrantClient(url=QDRANT_URL)

# Initialize embedding model (all-MiniLM-L6-v2: 384 dimensions, fast)
print("🔄 Loading embedding model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"✅ Loaded model: all-MiniLM-L6-v2 ({embedding_model.get_sentence_embedding_dimension()} dimensions)")


def get_embedding(text: str) -> List[float]:
    """Get semantic embedding for text"""
    embedding = embedding_model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


async def populate_best_practices():
    """Populate best-practices collection with semantic embeddings"""
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
            "references": ["kustomization.yaml", "AIDB Dockerfile"],
            "endorsement_count": 5,
            "last_validated": int(Path(PROJECT_ROOT / "ai-stack/kubernetes/kustomization.yaml").stat().st_mtime)
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
        },
        {
            "category": "ai-stack",
            "title": "Ralph Wiggum Container Exit Code 2",
            "description": "When Ralph Wiggum container exits with code 2, check database connections, data directory permissions, port conflicts, and dependency imports. Try disabling the loop initially.",
            "examples": [
                "RALPH_LOOP_ENABLED=false python server.py",
                "mkdir -p /data/telemetry && chmod 777 /data/telemetry"
            ],
            "anti_patterns": [
                "Assuming all dependencies are imported correctly",
                "Not checking data directory permissions"
            ],
            "references": ["IMMEDIATE-ACTION-PLAN-2026-01-05.md"],
            "endorsement_count": 1,
            "last_validated": int(Path(PROJECT_ROOT / "IMMEDIATE-ACTION-PLAN-2026-01-05.md").stat().st_mtime) if Path(PROJECT_ROOT / "IMMEDIATE-ACTION-PLAN-2026-01-05.md").exists() else 0
        }
    ]

    points = []
    for practice in practices:
        # Create rich document text for embedding
        doc_text = f"""Title: {practice['title']}
Category: {practice['category']}

Description: {practice['description']}

Examples:
{chr(10).join('- ' + ex for ex in practice['examples'])}

Anti-patterns to avoid:
{chr(10).join('- ' + ap for ap in practice['anti_patterns'])}
"""

        # Get semantic embedding
        embedding = get_embedding(doc_text)

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
    print(f"✅ Added {len(points)} best practices with semantic embeddings")


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
        },
        {
            "error_message": "Permission denied writing to telemetry directory",
            "error_type": "filesystem_permission",
            "context": "Telemetry files owned by container UID, host user cannot write",
            "solution": "Create alternative test-telemetry directory with proper ownership, or use podman unshare to fix permissions.",
            "solution_verified": True,
            "success_count": 1,
            "failure_count": 0,
            "first_seen": int(Path(PROJECT_ROOT / "scripts/generate-test-telemetry.sh").stat().st_mtime),
            "last_used": int(Path(PROJECT_ROOT / "scripts/generate-test-telemetry.sh").stat().st_mtime),
            "confidence_score": 0.9
        }
    ]

    points = []
    for solution in solutions:
        doc_text = f"""Error: {solution['error_message']}
Type: {solution['error_type']}
Context: {solution['context']}

Solution: {solution['solution']}
Verified: {"Yes" if solution['solution_verified'] else "No"}
Confidence: {solution['confidence_score']:.0%}
"""
        embedding = get_embedding(doc_text)

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
    print(f"✅ Added {len(points)} error solutions with semantic embeddings")


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
        "DASHBOARD-COLLECTOR-INTEGRATION-2026-01-05.md",
    ]

    points = []
    for filename in key_files:
        filepath = PROJECT_ROOT / filename
        if not filepath.exists():
            print(f"  ⚠️  {filename} not found")
            continue

        content = filepath.read_text()
        # Chunk large files (max 1000 chars per chunk for better retrieval)
        chunks = [content[i:i+1000] for i in range(0, len(content), 800)]  # Overlap of 200 chars

        for chunk_idx, chunk in enumerate(chunks[:10]):  # Limit to first 10 chunks
            embedding = get_embedding(chunk)

            point = PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload={
                    "file_path": str(filepath.relative_to(PROJECT_ROOT)),
                    "content": chunk,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(chunks),
                    "file_type": "markdown",
                    "project": "NixOS-Dev-Quick-Deploy",
                    "category": "documentation",
                    "indexed_at": int(filepath.stat().st_mtime)
                }
            )
            points.append(point)

        print(f"  ✓ {filename} ({len(chunks)} chunks, indexed {min(10, len(chunks))})")

    if points:
        qdrant.upsert(
            collection_name="codebase-context",
            points=points
        )
        print(f"✅ Added {len(points)} document chunks to codebase-context")
    else:
        print("⚠️  No documents indexed")


async def test_semantic_search():
    """Test semantic search with real embeddings"""
    print("\n🔍 Testing semantic search...")

    test_queries = [
        "How do I fix container networking issues?",
        "Dashboard not updating metrics",
        "Container fails to start",
    ]

    for query in test_queries:
        query_embedding = get_embedding(query)

        # Search best-practices
        results = qdrant.search(
            collection_name="best-practices",
            query_vector=query_embedding,
            limit=2
        )

        print(f"\nQuery: '{query}'")
        if results:
            for result in results:
                print(f"  → {result.payload.get('title')} (score: {result.score:.3f})")
        else:
            print("  No results found")


async def main():
    """Main population routine"""
    print("=" * 70)
    print("🔄 Populating Qdrant with Semantic Embeddings")
    print("=" * 70)
    print(f"Qdrant URL: {QDRANT_URL}")

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

        # Test semantic search
        await test_semantic_search()

        print("\n" + "="*70)
        print("✅ Qdrant population complete with semantic embeddings!")
        print("="*70)

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
