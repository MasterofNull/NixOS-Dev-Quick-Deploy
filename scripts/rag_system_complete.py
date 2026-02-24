#!/usr/bin/env python3
"""
Complete RAG System Implementation and Testing
Version: 1.0.0
Date: 2025-12-20

This script provides a complete, standalone RAG system that:
1. Tests all AI stack components (Qdrant, llama.cpp)
2. Implements semantic caching
3. Provides enhanced data structures with metadata
4. Implements value scoring and pattern extraction
5. Demonstrates model cascading
6. Tracks token usage and savings

Can run independently or integrate with existing infrastructure.
"""

import sys
import json
import uuid
import time
import hashlib
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
import sqlite3

# Configuration
SERVICE_HOST = os.getenv("SERVICE_HOST", "localhost")
CONFIG = {
    "qdrant_url": os.getenv("QDRANT_URL", "http://localhost"),
    "llama_cpp_url": os.getenv("LLAMA_URL", "http://localhost"),
    "embedding_model": "nomic-embed-text",
    "embedding_dimensions": 768,  # nomic-embed-text actual dimensions
    "local_confidence_threshold": 0.85,
    "high_value_threshold": 0.7,
    "semantic_cache_threshold": 0.95,  # Very high similarity = cache hit
    "cache_ttl_hours": 24,
    "data_dir": Path.home() / ".local/share/nixos-ai-stack",
}

# Ensure data directory exists
CONFIG["data_dir"].mkdir(parents=True, exist_ok=True)


@dataclass
class EmbeddingVector:
    """Embedding with metadata"""
    vector: List[float]
    model: str
    dimensions: int
    created_at: str


@dataclass
class EnhancedPayload:
    """Enhanced payload structure with comprehensive metadata"""
    # Core content
    content: str
    content_type: str  # code_snippet, error_solution, pattern, etc.

    # Classification
    language: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # Lineage
    file_path: Optional[str] = None
    version: str = "1.0.0"
    parent_id: Optional[str] = None
    related_ids: List[str] = field(default_factory=list)

    # Quality metrics
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    value_score: float = 0.0

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used_at: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return asdict(self)

    def update_usage(self, success: bool = True):
        """Update usage statistics"""
        self.usage_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        self.success_rate = (
            self.success_count / self.usage_count if self.usage_count > 0 else 0.0
        )
        self.last_used_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()


@dataclass
class QueryResult:
    """Search result with enhanced information"""
    id: str
    score: float
    payload: EnhancedPayload
    distance: float


@dataclass
class ValueScoreFactors:
    """5-factor value scoring system"""
    complexity: float  # 0-1, based on content length, code complexity
    reusability: float  # 0-1, how generic/reusable
    novelty: float  # 0-1, is this new or duplicate
    confirmation: float  # 0-1, user confirmed success
    impact: float  # 0-1, critical/high/medium/low

    def calculate_score(self) -> float:
        """Calculate weighted value score"""
        weights = {
            "complexity": 0.2,
            "reusability": 0.3,
            "novelty": 0.2,
            "confirmation": 0.15,
            "impact": 0.15,
        }

        score = (
            self.complexity * weights["complexity"] +
            self.reusability * weights["reusability"] +
            self.novelty * weights["novelty"] +
            self.confirmation * weights["confirmation"] +
            self.impact * weights["impact"]
        )

        return round(score, 2)


class SemanticCache:
    """Semantic caching layer using SQLite"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self._init_db()

    def _init_db(self):
        """Initialize cache database"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_cache (
                id TEXT PRIMARY KEY,
                query_hash TEXT NOT NULL,
                query_text TEXT NOT NULL,
                query_embedding TEXT NOT NULL,
                response TEXT NOT NULL,
                llm_used TEXT NOT NULL,
                tokens_saved INTEGER DEFAULT 0,
                hit_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_hit_at TEXT
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_hash ON semantic_cache(query_hash)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at ON semantic_cache(expires_at)
        """)
        self.conn.commit()

    def _query_hash(self, query: str) -> str:
        """Generate hash for exact query matching"""
        return hashlib.sha256(query.encode()).hexdigest()

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for x, y in zip(a, b):
            dot += x * y
            norm_a += x * x
            norm_b += y * y
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))

    def get(self, query: str, query_embedding: List[float]) -> Optional[Dict]:
        """Try to get cached response"""
        # First try exact match
        query_hash = self._query_hash(query)
        cursor = self.conn.execute("""
            SELECT * FROM semantic_cache
            WHERE query_hash = ? AND expires_at > ?
        """, (query_hash, datetime.utcnow().isoformat()))

        row = cursor.fetchone()
        if row:
            # Update hit count
            self.conn.execute("""
                UPDATE semantic_cache
                SET hit_count = hit_count + 1, last_hit_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), row[0]))
            self.conn.commit()

            return {
                "response": row[4],
                "llm_used": row[5],
                "cache_hit": "exact",
                "hit_count": row[6] + 1,
            }

        # Semantic similarity search using embeddings
        cursor = self.conn.execute("""
            SELECT id, query_text, query_embedding, response, llm_used, hit_count
            FROM semantic_cache
            WHERE expires_at > ?
        """, (datetime.utcnow().isoformat(),))

        best = None
        best_score = 0.0
        for row in cursor.fetchall():
            try:
                stored_embedding = json.loads(row[2])
            except Exception:
                continue
            score = self._cosine_similarity(query_embedding, stored_embedding)
            if score > best_score:
                best_score = score
                best = row

        if best and best_score >= CONFIG["semantic_cache_threshold"]:
            self.conn.execute("""
                UPDATE semantic_cache
                SET hit_count = hit_count + 1, last_hit_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), best[0]))
            self.conn.commit()

            return {
                "response": best[3],
                "llm_used": best[4],
                "cache_hit": "semantic",
                "similarity": round(best_score, 4),
                "hit_count": best[5] + 1,
            }

        return None

    def set(self, query: str, query_embedding: List[float], response: str,
            llm_used: str, tokens_saved: int = 0):
        """Cache a response"""
        query_hash = self._query_hash(query)
        cache_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        expires_at = (datetime.utcnow() + timedelta(hours=CONFIG["cache_ttl_hours"])).isoformat()

        self.conn.execute("""
            INSERT OR REPLACE INTO semantic_cache
            (id, query_hash, query_text, query_embedding, response, llm_used,
             tokens_saved, hit_count, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cache_id, query_hash, query, json.dumps(query_embedding), response,
            llm_used, tokens_saved, 0, created_at, expires_at
        ))
        self.conn.commit()

    def cleanup_expired(self):
        """Remove expired cache entries"""
        self.conn.execute("""
            DELETE FROM semantic_cache WHERE expires_at < ?
        """, (datetime.utcnow().isoformat(),))
        self.conn.commit()

    def stats(self) -> Dict:
        """Get cache statistics"""
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total_entries,
                SUM(hit_count) as total_hits,
                SUM(tokens_saved * hit_count) as total_tokens_saved,
                AVG(hit_count) as avg_hits_per_entry
            FROM semantic_cache
            WHERE expires_at > ?
        """, (datetime.utcnow().isoformat(),))

        row = cursor.fetchone()
        return {
            "total_entries": row[0] or 0,
            "total_hits": row[1] or 0,
            "total_tokens_saved": row[2] or 0,
            "avg_hits_per_entry": round(row[3] or 0, 2),
        }


class RAGSystem:
    """Complete RAG system with all advanced features"""

    def __init__(self):
        self.config = CONFIG
        self.cache = SemanticCache(CONFIG["data_dir"] / "semantic_cache.db")
        self.services_available = self._check_services()

    def _check_services(self) -> Dict[str, bool]:
        """Check which services are available"""
        services = {}

        # Check Qdrant
        try:
            response = requests.get(f"{self.config['qdrant_url']}/healthz", timeout=2)
            services["qdrant"] = response.status_code == 200
        except:
            services["qdrant"] = False

        # Check llama.cpp
        try:
            response = requests.get(f"{self.config['llama_cpp_url']}/health", timeout=2)
            services["llama_cpp"] = response.status_code == 200
        except:
            services["llama_cpp"] = False

        return services

    def generate_embedding(self, text: str) -> Optional[EmbeddingVector]:
        """Generate embedding using llama.cpp"""
        if not self.services_available["llama_cpp"]:
            print("⚠️  llama.cpp not available, cannot generate embeddings")
            return None

        try:
            response = requests.post(
                f"{self.config['llama_cpp_url']}/v1/embeddings",
                json={
                    "model": self.config["embedding_model"],
                    "input": text
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return EmbeddingVector(
                    vector=data["embedding"],
                    model=self.config["embedding_model"],
                    dimensions=len(data["embedding"]),
                    created_at=datetime.utcnow().isoformat()
                )
            else:
                print(f"❌ Embedding generation failed: HTTP {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Embedding error: {e}")
            return None

    def calculate_value_score(self, content: str, metadata: Dict) -> float:
        """Calculate value score using 5-factor algorithm"""
        # Factor 1: Complexity (based on content length and structure)
        complexity = min(1.0, len(content) / 500)  # Normalize to 500 chars

        # Factor 2: Reusability (from metadata or inferred)
        reusability = metadata.get("reusability", 0.5)
        if metadata.get("is_generic", False):
            reusability = 0.8

        # Factor 3: Novelty (from metadata)
        novelty = metadata.get("novelty", 1.0)  # Default to novel

        # Factor 4: Confirmation (user feedback)
        confirmation = 1.0 if metadata.get("user_confirmed", False) else 0.5

        # Factor 5: Impact (from severity/priority)
        impact_map = {
            "critical": 1.0,
            "high": 0.8,
            "medium": 0.5,
            "low": 0.3
        }
        impact = impact_map.get(metadata.get("severity", "medium"), 0.5)

        factors = ValueScoreFactors(
            complexity=complexity,
            reusability=reusability,
            novelty=novelty,
            confirmation=confirmation,
            impact=impact
        )

        return factors.calculate_score()

    def search_qdrant(self, query_vector: List[float], collection: str,
                     limit: int = 5, score_threshold: float = 0.7) -> List[QueryResult]:
        """Search Qdrant with enhanced filtering"""
        if not self.services_available["qdrant"]:
            print("⚠️  Qdrant not available")
            return []

        try:
            response = requests.post(
                f"{self.config['qdrant_url']}/collections/{collection}/points/search",
                json={
                    "vector": query_vector,
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "with_payload": True
                },
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                results = []

                for point in data.get("result", []):
                    payload_data = point.get("payload", {})
                    payload = EnhancedPayload(**payload_data) if payload_data else None

                    results.append(QueryResult(
                        id=str(point.get("id")),
                        score=point.get("score", 0.0),
                        payload=payload,
                        distance=1.0 - point.get("score", 0.0)
                    ))

                return results
            else:
                print(f"❌ Qdrant search failed: HTTP {response.status_code}")
                return []

        except Exception as e:
            print(f"❌ Qdrant search error: {e}")
            return []

    def query_local_llm(self, prompt: str, context: str = "") -> Optional[str]:
        """Query local LLM (llama.cpp)"""
        if not self.services_available["llama_cpp"]:
            print("⚠️  llama.cpp not available")
            return None

        full_prompt = f"Context:\n{context}\n\nQuery: {prompt}" if context else prompt

        try:
            response = requests.post(
                f"{self.config['llama_cpp_url']}/v1/completions",
                json={
                    "prompt": full_prompt,
                    "max_tokens": 500,
                    "temperature": 0.7,
                    "stop": ["\n\n"]
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("text", "").strip()
            else:
                print(f"❌ Local LLM failed: HTTP {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Local LLM error: {e}")
            return None

    def rag_query(self, query: str, collections: List[str] = None,
                  use_cache: bool = True) -> Dict:
        """Complete RAG workflow with caching and routing"""
        start_time = time.time()
        result = {
            "query": query,
            "cache_hit": False,
            "context_found": False,
            "llm_used": None,
            "response": None,
            "tokens_saved": 0,
            "processing_time": 0,
            "context_score": 0.0,
        }

        # Step 1: Check semantic cache
        if use_cache:
            embedding = self.generate_embedding(query)
            if embedding:
                cached = self.cache.get(query, embedding.vector)
                if cached:
                    result["cache_hit"] = True
                    result["response"] = cached["response"]
                    result["llm_used"] = cached["llm_used"]
                    result["tokens_saved"] = 15000  # Estimated full doc load
                    result["processing_time"] = time.time() - start_time
                    print(f"✓ Cache hit! Saved ~{result['tokens_saved']} tokens")
                    return result

        # Step 2: Generate embedding if not cached
        if not embedding:
            embedding = self.generate_embedding(query)
            if not embedding:
                result["error"] = "Could not generate embedding"
                return result

        # Step 3: Search Qdrant for context
        collections = collections or ["skills-patterns", "error-solutions", "best-practices"]
        all_results = []

        for collection in collections:
            collection_results = self.search_qdrant(
                embedding.vector,
                collection,
                limit=3,
                score_threshold=0.7
            )
            all_results.extend(collection_results)

        # Sort by score
        all_results.sort(key=lambda x: x.score, reverse=True)
        top_results = all_results[:5]

        if top_results:
            result["context_found"] = True
            result["context_score"] = top_results[0].score

            # Build context
            context_parts = []
            for r in top_results:
                if r.payload:
                    context_parts.append(r.payload.content)
            context = "\n\n".join(context_parts)
        else:
            context = ""

        # Step 4: Route to appropriate LLM
        if result["context_score"] > self.config["local_confidence_threshold"]:
            # Use local LLM
            response = self.query_local_llm(query, context)
            result["llm_used"] = "local"
            result["tokens_saved"] = 14500  # Saved remote API call
        else:
            # Would use remote API
            result["llm_used"] = "remote"
            result["response"] = "[SIMULATED] Would call remote API here"
            result["tokens_saved"] = 500 if context else 0  # Context helped

        # Step 5: Cache the result
        if use_cache and result["response"]:
            self.cache.set(
                query,
                embedding.vector,
                result["response"],
                result["llm_used"],
                result["tokens_saved"]
            )

        result["processing_time"] = time.time() - start_time
        return result

    def print_diagnostics(self):
        """Print system diagnostics"""
        print("\n" + "="*70)
        print("RAG SYSTEM DIAGNOSTICS")
        print("="*70)

        print("\n📊 Service Status:")
        for service, available in self.services_available.items():
            status = "✓ Available" if available else "✗ Unavailable"
            print(f"  {service:15s} : {status}")

        print("\n💾 Cache Statistics:")
        stats = self.cache.stats()
        for key, value in stats.items():
            print(f"  {key:25s} : {value}")

        print("\n⚙️  Configuration:")
        for key, value in self.config.items():
            if key != "data_dir":
                print(f"  {key:30s} : {value}")

        print("\n" + "="*70 + "\n")


def main():
    """Main function for testing"""
    print("🚀 Initializing Complete RAG System...")
    rag = RAGSystem()
    rag.print_diagnostics()

    if not any(rag.services_available.values()):
        print("\n❌ No AI services are available!")
        print("   Please start the AI stack first:")
        print("   ./scripts/hybrid-ai-stack.sh up")
        return 1

    # Test query
    print("\n🧪 Running test query...")
    test_query = "How to fix GNOME keyring error in NixOS?"
    result = rag.rag_query(test_query)

    print(f"\nQuery: {result['query']}")
    print(f"Cache Hit: {result['cache_hit']}")
    print(f"Context Found: {result['context_found']}")
    print(f"Context Score: {result['context_score']:.2f}")
    print(f"LLM Used: {result['llm_used']}")
    print(f"Tokens Saved: {result['tokens_saved']}")
    print(f"Processing Time: {result['processing_time']:.2f}s")

    if result.get("response"):
        print(f"\nResponse:\n{result['response']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
