#!/usr/bin/env python3
"""
Local Embedding Cache - SQLite-based embedding storage for edge devices

Purpose:
  Store pre-computed embeddings for frequently accessed documents to avoid
  redundant computation on CPU-constrained edge devices.

Architecture:
  - SQLite database for persistence (single file, no server)
  - Fast vector similarity search using cosine similarity
  - LRU eviction policy for cache size management
  - Thread-safe operations for concurrent access

Usage:
  from embedding_cache import EmbeddingCache
  
  cache = EmbeddingCache("/path/to/cache.db")
  
  # Store embedding
  cache.store("doc_id", embedding_vector, metadata={"source": "nixos-docs"})
  
  # Retrieve embedding
  embedding = cache.get("doc_id")
  
  # Search similar embeddings
  results = cache.search_similar(query_embedding, top_k=5)
"""

import sqlite3
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import threading
from pathlib import Path
import hashlib


class EmbeddingCache:
    """Thread-safe SQLite-based embedding cache with LRU eviction."""
    
    def __init__(self, db_path: str, max_size_mb: int = 500):
        """
        Initialize embedding cache.
        
        Args:
            db_path: Path to SQLite database file
            max_size_mb: Maximum cache size in megabytes (default: 500MB)
        """
        self.db_path = Path(db_path)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.lock = threading.Lock()
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with self.lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Main embeddings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    doc_id TEXT PRIMARY KEY,
                    embedding_hash TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    dimension INTEGER NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 1,
                    size_bytes INTEGER NOT NULL
                )
            """)
            
            # Index for LRU eviction
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_accessed_at 
                ON embeddings(accessed_at)
            """)
            
            # Index for hash lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_embedding_hash 
                ON embeddings(embedding_hash)
            """)
            
            # Cache statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_stats (
                    stat_key TEXT PRIMARY KEY,
                    stat_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
    
    def _serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """Serialize numpy array to bytes."""
        return embedding.astype(np.float32).tobytes()
    
    def _deserialize_embedding(self, data: bytes, dimension: int) -> np.ndarray:
        """Deserialize bytes to numpy array."""
        return np.frombuffer(data, dtype=np.float32).reshape(-1, dimension)
    
    def _compute_hash(self, embedding: np.ndarray) -> str:
        """Compute hash of embedding for deduplication."""
        return hashlib.sha256(embedding.tobytes()).hexdigest()[:16]
    
    def store(self, doc_id: str, embedding: np.ndarray, 
              metadata: Optional[Dict] = None) -> bool:
        """
        Store embedding in cache.
        
        Args:
            doc_id: Unique document identifier
            embedding: Embedding vector (numpy array)
            metadata: Optional metadata dictionary
            
        Returns:
            True if stored successfully, False otherwise
        """
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Serialize embedding
                embedding_bytes = self._serialize_embedding(embedding)
                embedding_hash = self._compute_hash(embedding)
                dimension = len(embedding)
                size_bytes = len(embedding_bytes)
                metadata_json = json.dumps(metadata) if metadata else None
                
                # Check cache size and evict if necessary
                self._evict_if_needed(cursor, size_bytes)
                
                # Insert or replace
                cursor.execute("""
                    INSERT OR REPLACE INTO embeddings 
                    (doc_id, embedding_hash, embedding, dimension, metadata, 
                     created_at, accessed_at, access_count, size_bytes)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, ?)
                """, (doc_id, embedding_hash, embedding_bytes, dimension, 
                      metadata_json, size_bytes))
                
                conn.commit()
                conn.close()
                return True
                
            except Exception as e:
                print(f"Error storing embedding: {e}")
                return False
    
    def get(self, doc_id: str) -> Optional[Tuple[np.ndarray, Dict]]:
        """
        Retrieve embedding from cache.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Tuple of (embedding, metadata) if found, None otherwise
        """
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Retrieve embedding
                cursor.execute("""
                    SELECT embedding, dimension, metadata 
                    FROM embeddings 
                    WHERE doc_id = ?
                """, (doc_id,))
                
                row = cursor.fetchone()
                if not row:
                    conn.close()
                    return None
                
                embedding_bytes, dimension, metadata_json = row
                embedding = self._deserialize_embedding(embedding_bytes, dimension)[0]
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                # Update access statistics
                cursor.execute("""
                    UPDATE embeddings 
                    SET accessed_at = CURRENT_TIMESTAMP,
                        access_count = access_count + 1
                    WHERE doc_id = ?
                """, (doc_id,))
                
                conn.commit()
                conn.close()
                
                return (embedding, metadata)
                
            except Exception as e:
                print(f"Error retrieving embedding: {e}")
                return None
    
    def search_similar(self, query_embedding: np.ndarray, 
                       top_k: int = 5,
                       min_similarity: float = 0.0) -> List[Tuple[str, float, Dict]]:
        """
        Search for similar embeddings using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (0-1)
            
        Returns:
            List of (doc_id, similarity, metadata) tuples, sorted by similarity
        """
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                # Retrieve all embeddings (TODO: optimize with approximate search)
                cursor.execute("""
                    SELECT doc_id, embedding, dimension, metadata 
                    FROM embeddings
                """)
                
                results = []
                query_norm = np.linalg.norm(query_embedding)
                
                for row in cursor.fetchall():
                    doc_id, embedding_bytes, dimension, metadata_json = row
                    embedding = self._deserialize_embedding(embedding_bytes, dimension)[0]
                    
                    # Compute cosine similarity
                    similarity = np.dot(query_embedding, embedding) / (
                        query_norm * np.linalg.norm(embedding)
                    )
                    
                    if similarity >= min_similarity:
                        metadata = json.loads(metadata_json) if metadata_json else {}
                        results.append((doc_id, float(similarity), metadata))
                
                conn.close()
                
                # Sort by similarity and return top_k
                results.sort(key=lambda x: x[1], reverse=True)
                return results[:top_k]
                
            except Exception as e:
                print(f"Error searching embeddings: {e}")
                return []
    
    def _evict_if_needed(self, cursor, new_size_bytes: int):
        """Evict least recently used entries if cache is full."""
        # Check current cache size
        cursor.execute("SELECT SUM(size_bytes) FROM embeddings")
        current_size = cursor.fetchone()[0] or 0
        
        # Evict LRU entries if necessary
        while current_size + new_size_bytes > self.max_size_bytes:
            cursor.execute("""
                SELECT doc_id, size_bytes 
                FROM embeddings 
                ORDER BY accessed_at ASC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                break
            
            doc_id, size_bytes = row
            cursor.execute("DELETE FROM embeddings WHERE doc_id = ?", (doc_id,))
            current_size -= size_bytes
    
    def stats(self) -> Dict:
        """Get cache statistics."""
        with self.lock:
            try:
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*), SUM(size_bytes) FROM embeddings")
                count, total_size = cursor.fetchone()
                
                cursor.execute("SELECT AVG(access_count) FROM embeddings")
                avg_access = cursor.fetchone()[0] or 0
                
                conn.close()
                
                return {
                    "entry_count": count or 0,
                    "total_size_bytes": total_size or 0,
                    "total_size_mb": (total_size or 0) / (1024 * 1024),
                    "avg_access_count": float(avg_access),
                    "max_size_mb": self.max_size_bytes / (1024 * 1024),
                    "utilization_percent": (total_size or 0) / self.max_size_bytes * 100
                }
                
            except Exception as e:
                print(f"Error getting stats: {e}")
                return {}
    
    def clear(self):
        """Clear all entries from cache."""
        with self.lock:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM embeddings")
            conn.commit()
            conn.close()
    
    def prewarm(self, doc_embeddings: List[Tuple[str, np.ndarray, Dict]]):
        """
        Pre-warm cache with multiple embeddings (batch operation).
        
        Args:
            doc_embeddings: List of (doc_id, embedding, metadata) tuples
        """
        for doc_id, embedding, metadata in doc_embeddings:
            self.store(doc_id, embedding, metadata)


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Embedding cache management")
    parser.add_argument("--db", default="/var/lib/ai-stack/embedding-cache.db",
                        help="Path to cache database")
    parser.add_argument("--stats", action="store_true",
                        help="Show cache statistics")
    parser.add_argument("--clear", action="store_true",
                        help="Clear cache")
    
    args = parser.parse_args()
    
    cache = EmbeddingCache(args.db)
    
    if args.stats:
        stats = cache.stats()
        print("Embedding Cache Statistics:")
        print(f"  Entries: {stats['entry_count']}")
        print(f"  Size: {stats['total_size_mb']:.2f} MB / {stats['max_size_mb']:.0f} MB")
        print(f"  Utilization: {stats['utilization_percent']:.1f}%")
        print(f"  Avg Access Count: {stats['avg_access_count']:.1f}")
    
    if args.clear:
        cache.clear()
        print("Cache cleared")
