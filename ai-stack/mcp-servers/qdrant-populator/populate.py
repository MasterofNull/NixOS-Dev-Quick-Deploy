#!/usr/bin/env python3
"""
Qdrant Population with Proper Semantic Embeddings
Runs inside a container with sentence-transformers available
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from uuid import uuid4

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# Configuration
PROJECT_ROOT = Path("/workspace")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")

# Initialize clients
qdrant = QdrantClient(url=QDRANT_URL)

# Initialize embedding model
model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
print("🔄 Loading embedding model...")
embedding_model = SentenceTransformer(model_name)
print(f"✅ Loaded: {model_name} ({embedding_model.get_sentence_embedding_dimension()}D)")


def get_embedding(text: str) -> List[float]:
    """Get semantic embedding"""
    return embedding_model.encode(text, convert_to_numpy=True).tolist()


async def populate_best_practices():
    """Populate best-practices with semantic embeddings"""
    print("\n📚 Populating best-practices...")

    practices = [
        {
            "category": "containerization",
            "title": "Container DNS Resolution with host networking",
            "description": "Use Kubernetes Service/Ingress for host access. Avoid relying on localhost from within pods.",
            "examples": ["Expose services via ClusterIP + port-forward or Ingress"],
            "anti_patterns": ["Using bridge network for localhost DB connections"],
            "references": ["kustomization.yaml"],
            "endorsement_count": 5,
            "last_validated": 1735000000
        },
        {
            "category": "systemd",
            "title": "Reliable SystemD timer scheduling",
            "description": "Use OnCalendar for reliable periodic execution. OnUnitActiveSec only runs after successful first activation.",
            "examples": ["OnCalendar=*:0/15  # Every 15 minutes"],
            "anti_patterns": ["Relying only on OnUnitActiveSec"],
            "references": ["dashboard-collector.timer"],
            "endorsement_count": 3,
            "last_validated": 1735000000
        },
        {
            "category": "monitoring",
            "title": "SystemD services need explicit PATH",
            "description": "SystemD services don't inherit user PATH. Set Environment=PATH explicitly for commands like curl, mkdir.",
            "examples": ['Environment="PATH=/usr/local/bin:/usr/bin:/bin"'],
            "anti_patterns": ["Assuming systemd inherits user environment"],
            "references": ["dashboard-collector.service"],
            "endorsement_count": 4,
            "last_validated": 1736000000
        },
    ]

    points = []
    for p in practices:
        doc_text = f"{p['title']}\n{p['description']}\nCategory: {p['category']}"
        embedding = get_embedding(doc_text)
        points.append(PointStruct(id=str(uuid4()), vector=embedding, payload=p))
        print(f"  ✓ {p['title']}")

    qdrant.upsert(collection_name="best-practices", points=points)
    print(f"✅ Added {len(points)} best practices")


async def populate_error_solutions():
    """Populate error-solutions"""
    print("\n🔧 Populating error-solutions...")

    solutions = [
        {
            "error_message": "Container exits with code 2",
            "error_type": "container_startup_failure",
            "context": "Container builds but exits immediately without logs",
            "solution": "Check: DB connections, data directory permissions (/data/*), port conflicts, import errors. Try RALPH_LOOP_ENABLED=false.",
            "solution_verified": False,
            "success_count": 0,
            "failure_count": 1,
            "first_seen": 1736000000,
            "last_used": 1736000000,
            "confidence_score": 0.3
        },
        {
            "error_message": "Dashboard metrics not updating",
            "error_type": "monitoring_stale_data",
            "context": "Collector service running but data stale",
            "solution": "Ensure collector service has PATH set. Verify timer is active with systemctl --user status dashboard-collector.timer.",
            "solution_verified": True,
            "success_count": 1,
            "failure_count": 0,
            "first_seen": 1736000000,
            "last_used": 1736000000,
            "confidence_score": 0.95
        },
    ]

    points = []
    for s in solutions:
        doc_text = f"Error: {s['error_message']}\nType: {s['error_type']}\nSolution: {s['solution']}"
        embedding = get_embedding(doc_text)
        points.append(PointStruct(id=str(uuid4()), vector=embedding, payload=s))
        print(f"  ✓ {s['error_type']}")

    qdrant.upsert(collection_name="error-solutions", points=points)
    print(f"✅ Added {len(points)} error solutions")


async def test_semantic_search():
    """Test semantic search"""
    print("\n🔍 Testing semantic search...")

    queries = [
        "How to fix container networking?",
        "Dashboard not updating",
        "Container startup failure",
    ]

    for query in queries:
        embedding = get_embedding(query)
        results = qdrant.search(collection_name="best-practices", query_vector=embedding, limit=2)
        print(f"\nQuery: '{query}'")
        for r in results:
            print(f"  → {r.payload.get('title')} (score: {r.score:.3f})")


async def main():
    print("="*70)
    print("🔄 Populating Qdrant with Semantic Embeddings")
    print("="*70)

    try:
        collections = qdrant.get_collections()
        print(f"✅ Connected to Qdrant ({len(collections.collections)} collections)")
    except Exception as e:
        print(f"❌ Cannot connect to Qdrant: {e}")
        return 1

    try:
        await populate_best_practices()
        await populate_error_solutions()
        await test_semantic_search()

        print("\n" + "="*70)
        print("✅ Population complete!")
        print("="*70)

        for coll in ["best-practices", "error-solutions"]:
            info = qdrant.get_collection(coll)
            print(f"{coll}: {info.points_count} points")

        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
