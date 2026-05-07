# Embedding Cache - Local Vector Storage for Edge Devices

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-07

## Overview

The Embedding Cache is a SQLite-based vector storage system optimized for CPU-constrained edge devices. It stores pre-computed embeddings to eliminate redundant inference operations, significantly reducing CPU load for RAG (Retrieval-Augmented Generation) queries.

## Problem Statement

### Without Caching

```
User Query → Embed Query → Search Docs → Embed Each Doc → Similarity → Results
             ~2s CPU      ~0.1s        ~10s CPU          ~0.2s      
             
Total: ~12s CPU time per query
```

### With Caching

```
User Query → Embed Query → Search Docs → Lookup Cached → Similarity → Results
             ~2s CPU      ~0.1s        ~0.01s (cache)   ~0.2s
             
Total: ~2.3s CPU time per query (5.2x faster)
```

**Result**: 83% reduction in CPU usage for repeated queries

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  (RAG pipelines, semantic search, document retrieval)        │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   Embedding Cache API                        │
│  - store(doc_id, embedding, metadata)                        │
│  - get(doc_id) → (embedding, metadata)                       │
│  - search_similar(query_vec, top_k) → results               │
│  - stats() → cache metrics                                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    SQLite Database                           │
│  - Single file: /var/lib/ai-stack/embedding-cache.db        │
│  - Thread-safe with locks                                    │
│  - LRU eviction for size management                          │
│  - Indexed for fast lookups                                  │
└──────────────────────────────────────────────────────────────┘
```

## Database Schema

### embeddings table

```sql
CREATE TABLE embeddings (
    doc_id TEXT PRIMARY KEY,          -- Unique document identifier
    embedding_hash TEXT NOT NULL,     -- SHA256 hash for deduplication
    embedding BLOB NOT NULL,          -- Serialized numpy array (float32)
    dimension INTEGER NOT NULL,       -- Embedding dimension (e.g., 384, 768)
    metadata TEXT,                    -- JSON metadata
    created_at TIMESTAMP,             -- Creation timestamp
    accessed_at TIMESTAMP,            -- Last access (for LRU)
    access_count INTEGER,             -- Number of accesses (popularity)
    size_bytes INTEGER NOT NULL       -- Embedding size in bytes
);

CREATE INDEX idx_accessed_at ON embeddings(accessed_at);
CREATE INDEX idx_embedding_hash ON embeddings(embedding_hash);
```

## Usage

### Python API

```python
from embedding_cache import EmbeddingCache

# Initialize cache
cache = EmbeddingCache(
    db_path="/var/lib/ai-stack/embedding-cache.db",
    max_size_mb=500  # 500MB cache size
)

# Store embedding
import numpy as np
embedding = np.random.rand(384)  # Example 384-dim vector
cache.store(
    doc_id="nixos-manual-section-1.3",
    embedding=embedding,
    metadata={"source": "nixos-docs", "section": "1.3"}
)

# Retrieve embedding
result = cache.get("nixos-manual-section-1.3")
if result:
    embedding, metadata = result
    print(f"Retrieved {len(embedding)}-dim embedding")
    print(f"Source: {metadata['source']}")

# Search for similar embeddings
query_embedding = np.random.rand(384)
results = cache.search_similar(
    query_embedding=query_embedding,
    top_k=5,
    min_similarity=0.7
)

for doc_id, similarity, metadata in results:
    print(f"{doc_id}: {similarity:.3f} - {metadata}")

# Get cache statistics
stats = cache.stats()
print(f"Entries: {stats['entry_count']}")
print(f"Size: {stats['total_size_mb']:.2f} MB")
print(f"Utilization: {stats['utilization_percent']:.1f}%")
```

### CLI Interface

```bash
# Show cache statistics
python3 ai-stack/embedding-cache/embedding_cache.py --stats

# Clear cache
python3 ai-stack/embedding-cache/embedding_cache.py --clear

# Use custom database path
python3 ai-stack/embedding-cache/embedding_cache.py \
    --db /tmp/my-cache.db --stats
```

### Integration with RAG Pipeline

```python
# rag_pipeline.py
from embedding_cache import EmbeddingCache
from sentence_transformers import SentenceTransformer

cache = EmbeddingCache("/var/lib/ai-stack/embedding-cache.db")
model = SentenceTransformer("all-MiniLM-L6-v2")

def get_document_embedding(doc_id: str, text: str):
    """Get embedding from cache or compute if not cached."""
    
    # Try cache first
    result = cache.get(doc_id)
    if result:
        embedding, metadata = result
        print(f"Cache hit for {doc_id}")
        return embedding
    
    # Compute embedding (expensive)
    print(f"Cache miss for {doc_id}, computing...")
    embedding = model.encode(text)
    
    # Store in cache for future use
    cache.store(doc_id, embedding, metadata={"text_length": len(text)})
    
    return embedding

def semantic_search(query: str, documents: list):
    """Search documents using cached embeddings."""
    
    # Embed query (always compute, as queries are unique)
    query_embedding = model.encode(query)
    
    # Search cached embeddings
    results = cache.search_similar(query_embedding, top_k=10)
    
    return results
```

## Cache Management

### LRU Eviction

When the cache exceeds `max_size_mb`, the least recently used entries are evicted:

```python
# Eviction is automatic
cache = EmbeddingCache(max_size_mb=500)  # 500MB limit

# Store embeddings until full
for i in range(10000):
    cache.store(f"doc_{i}", embedding, metadata={})
    
# Oldest entries (by accessed_at) are evicted automatically
stats = cache.stats()
print(f"Utilization: {stats['utilization_percent']:.1f}%")  # ~100%
```

### Pre-warming

For frequently accessed documents, pre-warm the cache on startup:

```python
# prewarm_cache.py
from embedding_cache import EmbeddingCache
from sentence_transformers import SentenceTransformer
import json

cache = EmbeddingCache("/var/lib/ai-stack/embedding-cache.db")
model = SentenceTransformer("all-MiniLM-L6-v2")

# Load common documents
with open("common-docs.json") as f:
    docs = json.load(f)

# Pre-compute and cache embeddings
embeddings = []
for doc in docs:
    embedding = model.encode(doc["text"])
    embeddings.append((doc["id"], embedding, {"source": doc["source"]}))

# Batch insert
cache.prewarm(embeddings)

print(f"Pre-warmed cache with {len(embeddings)} documents")
```

Run on system startup:

```bash
# Add to systemd service
ExecStartPre=/usr/bin/python3 /opt/ai-stack/scripts/prewarm_cache.py
```

## Performance Tuning

### Cache Size

Adjust based on available storage:

```python
# Small edge device (256GB storage)
cache = EmbeddingCache(max_size_mb=500)   # 500MB cache

# Server (2TB storage)
cache = EmbeddingCache(max_size_mb=5000)  # 5GB cache

# Embedded device (32GB storage)
cache = EmbeddingCache(max_size_mb=100)   # 100MB cache
```

### Dimension Optimization

Smaller embeddings = more docs cached:

```python
# all-MiniLM-L6-v2: 384 dimensions × 4 bytes = 1.5KB per doc
# Can cache ~333K documents in 500MB

# all-mpnet-base-v2: 768 dimensions × 4 bytes = 3KB per doc
# Can cache ~166K documents in 500MB

# Choose model based on accuracy vs cache size tradeoff
```

### Thread Safety

The cache is thread-safe with Python threading locks:

```python
import threading

cache = EmbeddingCache("/var/lib/ai-stack/embedding-cache.db")

def worker(doc_id, embedding):
    cache.store(doc_id, embedding, metadata={})

# Safe to use from multiple threads
threads = []
for i in range(10):
    t = threading.Thread(target=worker, args=(f"doc_{i}", np.random.rand(384)))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
```

## Monitoring

### Cache Hit Rate

Track effectiveness:

```python
def get_embedding_with_metrics(doc_id: str):
    global cache_hits, cache_misses
    
    result = cache.get(doc_id)
    if result:
        cache_hits += 1
        return result[0]
    else:
        cache_misses += 1
        embedding = compute_embedding(doc_id)
        cache.store(doc_id, embedding, metadata={})
        return embedding

# Report metrics
hit_rate = cache_hits / (cache_hits + cache_misses) * 100
print(f"Cache hit rate: {hit_rate:.1f}%")
```

### Storage Monitoring

```bash
# Check database size
du -h /var/lib/ai-stack/embedding-cache.db

# Check cache stats
python3 -c "
from embedding_cache import EmbeddingCache
cache = EmbeddingCache('/var/lib/ai-stack/embedding-cache.db')
stats = cache.stats()
print(f\"Entries: {stats['entry_count']}\")
print(f\"Size: {stats['total_size_mb']:.2f} MB\")
print(f\"Avg accesses: {stats['avg_access_count']:.1f}\")
"
```

### Prometheus Metrics

Export metrics for monitoring (example):

```python
# metrics_exporter.py
from prometheus_client import Gauge, start_http_server
from embedding_cache import EmbeddingCache

cache = EmbeddingCache("/var/lib/ai-stack/embedding-cache.db")

cache_entries = Gauge('embedding_cache_entries', 'Number of cached embeddings')
cache_size_mb = Gauge('embedding_cache_size_mb', 'Cache size in MB')
cache_utilization = Gauge('embedding_cache_utilization_percent', 'Cache utilization %')

def update_metrics():
    stats = cache.stats()
    cache_entries.set(stats['entry_count'])
    cache_size_mb.set(stats['total_size_mb'])
    cache_utilization.set(stats['utilization_percent'])

if __name__ == "__main__":
    start_http_server(9101)
    while True:
        update_metrics()
        time.sleep(60)  # Update every minute
```

## Backup and Restore

### Backup

```bash
# Simple file copy (stop services first for consistency)
systemctl stop ai-hybrid-coordinator
cp /var/lib/ai-stack/embedding-cache.db \
   /backup/embedding-cache-$(date +%Y%m%d).db
systemctl start ai-hybrid-coordinator

# Or use SQLite backup command (hot backup, no downtime)
sqlite3 /var/lib/ai-stack/embedding-cache.db \
    ".backup /backup/embedding-cache-$(date +%Y%m%d).db"
```

### Restore

```bash
systemctl stop ai-hybrid-coordinator
cp /backup/embedding-cache-20240115.db \
   /var/lib/ai-stack/embedding-cache.db
systemctl start ai-hybrid-coordinator
```

### Replication (Optional)

For high availability, replicate cache across nodes:

```bash
# On primary node
rsync -avz /var/lib/ai-stack/embedding-cache.db \
    backup-node:/var/lib/ai-stack/

# Or use Litestream for continuous replication
litestream replicate /var/lib/ai-stack/embedding-cache.db \
    s3://my-bucket/embedding-cache
```

## Troubleshooting

### Cache Corruption

```bash
# Check database integrity
sqlite3 /var/lib/ai-stack/embedding-cache.db "PRAGMA integrity_check"

# If corrupted, rebuild from backup
systemctl stop ai-hybrid-coordinator
cp /backup/embedding-cache-latest.db /var/lib/ai-stack/embedding-cache.db
systemctl start ai-hybrid-coordinator
```

### Low Hit Rate

```python
# Analyze access patterns
import sqlite3
conn = sqlite3.connect("/var/lib/ai-stack/embedding-cache.db")
cursor = conn.cursor()

# Find rarely accessed entries
cursor.execute("""
    SELECT doc_id, access_count 
    FROM embeddings 
    WHERE access_count = 1 
    ORDER BY created_at DESC 
    LIMIT 10
""")

for doc_id, access_count in cursor.fetchall():
    print(f"{doc_id}: only accessed {access_count} time(s)")

# Consider pre-warming with more relevant documents
```

### Performance Degradation

```bash
# Vacuum database to reclaim space
sqlite3 /var/lib/ai-stack/embedding-cache.db "VACUUM"

# Rebuild indexes
sqlite3 /var/lib/ai-stack/embedding-cache.db "REINDEX"

# Clear old entries
python3 -c "
from embedding_cache import EmbeddingCache
cache = EmbeddingCache('/var/lib/ai-stack/embedding-cache.db')
cache.clear()
print('Cache cleared')
"
```

## Future Enhancements

1. **Approximate Nearest Neighbor**: Use FAISS or Annoy for faster similarity search
2. **Compression**: Apply vector quantization to reduce storage
3. **Distributed Cache**: Share embeddings across multiple nodes
4. **TTL Expiration**: Auto-expire stale embeddings based on document updates
5. **Warm/Cold Tiers**: Move rarely accessed embeddings to cheaper storage

## See Also

- [AQ Switchboard](./aq-switchboard.md)
