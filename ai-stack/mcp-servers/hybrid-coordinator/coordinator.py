#!/usr/bin/env python3
"""
Hybrid Coordinator MCP Server
Version: 1.0.0
Date: 2025-12-20

MCP (Model Context Protocol) server that coordinates between:
- Local LLMs (Lemonade, Ollama)
- Remote APIs (Claude, GPT)
- RAG system (Qdrant)
- Semantic caching
- Value scoring and learning storage

This is the main entry point for agents to interact with the hybrid AI stack.
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

try:
    from rag_system_complete import (
        RAGSystem, EnhancedPayload, QueryResult, ValueScoreFactors
    )
except ImportError:
    print("Error: Could not import RAG system. Ensure scripts/rag-system-complete.py exists")
    sys.exit(1)


class HybridCoordinator:
    """
    Coordinates queries between local and remote LLMs with RAG augmentation.

    This is the main orchestrator that agents interact with.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the hybrid coordinator.

        Args:
            config: Optional configuration overrides
        """
        self.config = config or {}
        self.rag_system = RAGSystem()
        self.query_history = []

        # Confidence thresholds for routing decisions
        self.thresholds = {
            "local_high_confidence": self.config.get("local_high_confidence", 0.85),
            "local_medium_confidence": self.config.get("local_medium_confidence", 0.70),
            "cache_similarity": self.config.get("cache_similarity", 0.95),
        }

        # Token usage tracking
        self.stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "local_llm_calls": 0,
            "remote_api_calls": 0,
            "total_tokens_saved": 0,
        }

    async def query(
        self,
        prompt: str,
        context_collections: Optional[List[str]] = None,
        max_context_results: int = 5,
        force_local: bool = False,
        force_remote: bool = False,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Process a query through the hybrid system.

        Args:
            prompt: The query/prompt to process
            context_collections: Which Qdrant collections to search (default: all)
            max_context_results: Maximum number of context results to use
            force_local: Force use of local LLM
            force_remote: Force use of remote API
            metadata: Additional metadata for tracking

        Returns:
            Dict containing:
                - response: The generated response
                - llm_used: "local" | "remote" | "cache"
                - confidence: Context match confidence (0-1)
                - tokens_saved: Estimated tokens saved
                - processing_time: Time taken (seconds)
                - context_used: List of context sources used
        """
        start_time = datetime.utcnow()
        self.stats["total_queries"] += 1

        # Step 1: Use RAG system for query processing
        rag_result = self.rag_system.rag_query(
            query=prompt,
            collections=context_collections,
            use_cache=not force_remote  # Don't use cache if forcing remote
        )

        # Update stats
        if rag_result.get("cache_hit"):
            self.stats["cache_hits"] += 1

        if rag_result.get("llm_used") == "local":
            self.stats["local_llm_calls"] += 1
        elif rag_result.get("llm_used") == "remote":
            self.stats["remote_api_calls"] += 1

        self.stats["total_tokens_saved"] += rag_result.get("tokens_saved", 0)

        # Build response
        response = {
            "response": rag_result.get("response"),
            "llm_used": rag_result.get("llm_used"),
            "confidence": rag_result.get("context_score", 0.0),
            "tokens_saved": rag_result.get("tokens_saved", 0),
            "processing_time": (datetime.utcnow() - start_time).total_seconds(),
            "cache_hit": rag_result.get("cache_hit", False),
            "context_found": rag_result.get("context_found", False),
        }

        # Log query for analysis
        self.query_history.append({
            "timestamp": start_time.isoformat(),
            "prompt": prompt[:100],  # Truncate for privacy
            "result": response,
            "metadata": metadata or {},
        })

        return response

    async def store_solution(
        self,
        query: str,
        solution: str,
        collection: str = "skills-patterns",
        metadata: Optional[Dict] = None,
        user_confirmed: bool = False,
    ) -> str:
        """
        Store a successful solution for future retrieval.

        Args:
            query: The original query/problem
            solution: The working solution
            collection: Which collection to store in
            metadata: Additional metadata (language, tags, etc.)
            user_confirmed: Whether user explicitly confirmed success

        Returns:
            The ID of the stored entry
        """
        # Generate embedding
        embedding = self.rag_system.generate_embedding(query)
        if not embedding:
            return None

        # Calculate value score
        meta = metadata or {}
        meta["user_confirmed"] = user_confirmed
        value_score = self.rag_system.calculate_value_score(solution, meta)

        # Create enhanced payload
        payload = EnhancedPayload(
            content=solution,
            content_type=meta.get("content_type", "solution"),
            language=meta.get("language"),
            category=meta.get("category"),
            tags=meta.get("tags", []),
            file_path=meta.get("file_path"),
            value_score=value_score,
            metadata=meta,
        )

        # Store in Qdrant
        try:
            import uuid
            from qdrant_client import QdrantClient
            from qdrant_client.models import PointStruct

            client = QdrantClient(url=self.rag_system.config["qdrant_url"])
            point_id = str(uuid.uuid4())

            client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding.vector,
                        payload=payload.to_dict(),
                    )
                ]
            )

            return point_id
        except Exception as e:
            print(f"Error storing solution: {e}")
            return None

    async def store_error_solution(
        self,
        error: str,
        attempted_solution: str,
        correct_solution: str,
        root_cause: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Store an error with its solution for future reference.

        Args:
            error: The error message/description
            attempted_solution: What was tried (that didn't work)
            correct_solution: What actually worked
            root_cause: Optional explanation of why error occurred
            metadata: Additional metadata

        Returns:
            The ID of the stored entry
        """
        # Build comprehensive error record
        error_data = {
            "error": error,
            "attempted_solution": attempted_solution,
            "correct_solution": correct_solution,
            "root_cause": root_cause or "Unknown",
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Merge with metadata
        meta = metadata or {}
        meta.update(error_data)
        meta["content_type"] = "error_solution"

        # Store using same mechanism
        return await self.store_solution(
            query=error,
            solution=correct_solution,
            collection="error-solutions",
            metadata=meta,
            user_confirmed=True,  # Errors are high-value
        )

    def get_stats(self) -> Dict:
        """Get usage statistics."""
        return {
            **self.stats,
            "cache_hit_rate": (
                self.stats["cache_hits"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0
                else 0.0
            ),
            "local_usage_rate": (
                self.stats["local_llm_calls"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0
                else 0.0
            ),
            "avg_tokens_saved": (
                self.stats["total_tokens_saved"] / self.stats["total_queries"]
                if self.stats["total_queries"] > 0
                else 0
            ),
            "rag_cache_stats": self.rag_system.cache.stats(),
        }

    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_stats()

        print("\n" + "="*70)
        print("HYBRID COORDINATOR STATISTICS")
        print("="*70)

        print(f"\n📊 Query Statistics:")
        print(f"  Total Queries:        {stats['total_queries']}")
        print(f"  Cache Hits:           {stats['cache_hits']} ({stats['cache_hit_rate']:.1%})")
        print(f"  Local LLM Calls:      {stats['local_llm_calls']} ({stats['local_usage_rate']:.1%})")
        print(f"  Remote API Calls:     {stats['remote_api_calls']}")

        print(f"\n💰 Token Savings:")
        print(f"  Total Tokens Saved:   {stats['total_tokens_saved']:,}")
        print(f"  Average per Query:    {stats['avg_tokens_saved']:.0f}")

        print(f"\n💾 Cache Performance:")
        cache_stats = stats['rag_cache_stats']
        print(f"  Cached Entries:       {cache_stats['total_entries']}")
        print(f"  Total Cache Hits:     {cache_stats['total_hits']}")
        print(f"  Avg Hits per Entry:   {cache_stats['avg_hits_per_entry']:.1f}")

        print("\n" + "="*70 + "\n")


async def main():
    """Test the hybrid coordinator."""
    print("🚀 Initializing Hybrid Coordinator...")

    coordinator = HybridCoordinator()

    # Check RAG system status
    coordinator.rag_system.print_diagnostics()

    if not any(coordinator.rag_system.services_available.values()):
        print("\n❌ No services available. Cannot run tests.")
        print("   Start AI stack: ./scripts/initialize-ai-stack.sh")
        return 1

    # Test query
    print("\n🧪 Running test query...")
    result = await coordinator.query(
        prompt="How to fix GNOME keyring error in NixOS?",
        metadata={"test": True, "source": "cli"}
    )

    print(f"\n📝 Query Result:")
    print(f"  LLM Used:        {result['llm_used']}")
    print(f"  Confidence:      {result['confidence']:.2f}")
    print(f"  Cache Hit:       {result['cache_hit']}")
    print(f"  Tokens Saved:    {result['tokens_saved']}")
    print(f"  Processing Time: {result['processing_time']:.2f}s")

    if result.get("response"):
        print(f"\n  Response:\n  {result['response'][:200]}...")

    # Print stats
    coordinator.print_stats()

    # Test storing a solution
    print("\n📦 Testing solution storage...")
    solution_id = await coordinator.store_solution(
        query="Install packages in NixOS",
        solution="Add packages to environment.systemPackages in configuration.nix, then run sudo nixos-rebuild switch",
        metadata={
            "language": "nix",
            "category": "package-management",
            "tags": ["nixos", "packages"],
            "severity": "medium",
        },
        user_confirmed=True,
    )

    if solution_id:
        print(f"✓ Solution stored with ID: {solution_id}")
    else:
        print("✗ Failed to store solution")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
