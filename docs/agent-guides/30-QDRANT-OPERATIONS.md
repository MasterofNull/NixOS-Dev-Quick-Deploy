# Qdrant Vector Database Operations

**Purpose**: Store, search, and manage vector embeddings for RAG

---

## Quick Reference

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(url="http://localhost:6333")
```

---

## Collections Overview

### Available Collections

| Collection | Size | Distance | Purpose |
|-----------|------|----------|---------|
| `codebase-context` | 384 | COSINE | Code snippets, function defs |
| `skills-patterns` | 384 | COSINE | Reusable solutions |
| `error-solutions` | 384 | COSINE | Known errors and fixes |
| `best-practices` | 384 | COSINE | Curated guidelines |
| `interaction-history` | 384 | COSINE | All past interactions |

All use **nomic-embed-text** (384-dimensional embeddings).

---

## Create Collection

```python
from qdrant_client.models import Distance, VectorParams

# Create new collection
client.create_collection(
    collection_name="my-collection",
    vectors_config=VectorParams(
        size=384,  # nomic-embed-text dimensions
        distance=Distance.COSINE
    )
)

# Verify creation
info = client.get_collection("my-collection")
print(f"Vectors: {info.vectors_count}")
```

---

## Insert Data (Upsert)

### Single Point

```python
import ollama
from qdrant_client.models import PointStruct
import uuid

# Step 1: Create embedding
text = "How to enable systemd service in NixOS"
response = ollama.embeddings(
    model="nomic-embed-text",
    prompt=text
)
embedding = response["embedding"]

# Step 2: Prepare point
point = PointStruct(
    id=str(uuid.uuid4()),  # Unique ID
    vector=embedding,
    payload={
        "text": text,
        "solution": "services.myservice.enable = true;",
        "category": "nixos-config",
        "timestamp": "2025-12-20T10:00:00Z"
    }
)

# Step 3: Insert
client.upsert(
    collection_name="best-practices",
    points=[point]
)
```

### Batch Insert (Multiple Points)

```python
def batch_insert(texts, collection_name):
    """Insert multiple texts efficiently"""

    points = []
    for text in texts:
        # Create embedding
        response = ollama.embeddings(
            model="nomic-embed-text",
            prompt=text["query"]
        )

        # Create point
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=response["embedding"],
            payload=text
        )
        points.append(point)

    # Batch upsert (much faster than individual inserts)
    client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True  # Wait for indexing
    )

    print(f"✓ Inserted {len(points)} points")

# Example usage
data = [
    {"query": "Fix keyring error", "solution": "Add libsecret", "category": "error"},
    {"query": "Enable service", "solution": "services.X.enable = true", "category": "config"},
    {"query": "Install package", "solution": "environment.systemPackages", "category": "packages"}
]

batch_insert(data, "best-practices")
```

---

## Search Operations

### Basic Search

```python
# Create query embedding
query = "gnome keyring not working"
response = ollama.embeddings(
    model="nomic-embed-text",
    prompt=query
)
query_vector = response["embedding"]

# Search
results = client.search(
    collection_name="error-solutions",
    query_vector=query_vector,
    limit=5  # Top 5 results
)

# Process results
for result in results:
    print(f"Score: {result.score:.3f}")
    print(f"Solution: {result.payload.get('solution')}")
    print("---")
```

### Search with Filtering

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Search with metadata filter
results = client.search(
    collection_name="best-practices",
    query_vector=query_vector,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="category",
                match=MatchValue(value="nixos-config")
            )
        ]
    ),
    limit=5
)

# Only returns results where category == "nixos-config"
```

### Search with Score Threshold

```python
# Only return high-relevance results
results = client.search(
    collection_name="skills-patterns",
    query_vector=query_vector,
    limit=10,
    score_threshold=0.75  # Minimum similarity score
)

# Only results with score >= 0.75 returned
high_quality_results = [r for r in results if r.score >= 0.75]
```

### Multi-Collection Search

```python
def search_all_collections(query):
    """Search across multiple collections"""

    # Create embedding once
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )
    query_vector = response["embedding"]

    collections = [
        "error-solutions",
        "skills-patterns",
        "best-practices"
    ]

    all_results = []
    for collection in collections:
        results = client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=3
        )

        # Add collection name to results
        for result in results:
            result.payload["_collection"] = collection
            all_results.append(result)

    # Sort by score
    all_results.sort(key=lambda x: x.score, reverse=True)

    return all_results[:5]  # Top 5 overall
```

---

## Retrieve Operations

### Get Point by ID

```python
# Retrieve specific point
point = client.retrieve(
    collection_name="error-solutions",
    ids=["point-id-here"]
)

print(point[0].payload)
```

### Scroll Through Collection

```python
# Get all points (paginated)
points, next_offset = client.scroll(
    collection_name="skills-patterns",
    limit=100,  # Page size
    with_payload=True,
    with_vectors=False  # Don't return vectors (faster)
)

print(f"Retrieved {len(points)} points")

# Continue scrolling
if next_offset:
    more_points, _ = client.scroll(
        collection_name="skills-patterns",
        limit=100,
        offset=next_offset
    )
```

### Count Points

```python
# Get collection stats
info = client.get_collection("interaction-history")

print(f"Total points: {info.points_count}")
print(f"Indexed vectors: {info.indexed_vectors_count}")
print(f"Vector size: {info.config.params.vectors.size}")
```

---

## Update Operations

### Update Payload

```python
from qdrant_client.models import SetPayload

# Update metadata without changing vector
client.set_payload(
    collection_name="error-solutions",
    payload={
        "verified": True,
        "success_count": 5
    },
    points=["point-id"]
)
```

### Delete Points

```python
# Delete by ID
client.delete(
    collection_name="interaction-history",
    points_selector=["point-id-1", "point-id-2"]
)

# Delete by filter
from qdrant_client.models import FilterSelector, Filter, FieldCondition, MatchValue

client.delete(
    collection_name="error-solutions",
    points_selector=FilterSelector(
        filter=Filter(
            must=[
                FieldCondition(
                    key="verified",
                    match=MatchValue(value=False)
                )
            ]
        )
    )
)
```

---

## Advanced Operations

### Hybrid Search (Vector + Keywords)

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Combine semantic search with keyword filtering
results = client.search(
    collection_name="codebase-context",
    query_vector=query_vector,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="file_type",
                match=MatchValue(value="nix")
            ),
            FieldCondition(
                key="verified",
                match=MatchValue(value=True)
            )
        ]
    ),
    limit=5
)
```

### Batch Recommendations

```python
# Find similar points to a given point
results = client.recommend(
    collection_name="skills-patterns",
    positive=["known-good-point-id"],  # Similar to this
    negative=["known-bad-point-id"],   # But not this
    limit=5
)
```

### Collection Snapshots

```bash
# Create snapshot (backup)
curl -X POST http://localhost:6333/collections/error-solutions/snapshots

# List snapshots
curl http://localhost:6333/collections/error-solutions/snapshots

# Download snapshot
curl http://localhost:6333/collections/error-solutions/snapshots/snapshot-name \
  -o backup.snapshot
```

---

## Performance Optimization

### Indexing

```python
# Enable HNSW indexing for faster search
from qdrant_client.models import HnswConfig

client.update_collection(
    collection_name="large-collection",
    hnsw_config=HnswConfig(
        m=16,  # Number of edges per node
        ef_construct=100,  # Construction quality
        full_scan_threshold=10000  # When to use full scan
    )
)
```

### Batch Operations

```python
# GOOD: Batch upsert (fast)
client.upsert(
    collection_name="collection",
    points=list_of_1000_points,
    wait=False  # Don't wait for indexing
)

# BAD: Individual inserts (slow)
for point in list_of_1000_points:
    client.upsert(collection_name="collection", points=[point])  # ❌ Slow!
```

### Search Optimization

```python
# Use score threshold to reduce processing
results = client.search(
    collection_name="large-collection",
    query_vector=query_vector,
    limit=100,
    score_threshold=0.7,  # Skip low-relevance results
    with_payload=True,
    with_vectors=False  # Don't return vectors (saves bandwidth)
)
```

---

## Monitoring & Maintenance

### Health Check

```bash
# HTTP health check
curl http://localhost:6333/healthz

# Collection health
curl http://localhost:6333/collections/error-solutions | jq
```

### Collection Statistics

```python
# Get detailed stats
info = client.get_collection("interaction-history")

print(f"Points: {info.points_count}")
print(f"Indexed: {info.indexed_vectors_count}")
print(f"Segments: {info.segments_count}")
print(f"Status: {info.status}")
```

### Cleanup Old Data

```python
from datetime import datetime, timedelta

# Delete points older than 90 days
cutoff_date = (datetime.utcnow() - timedelta(days=90)).isoformat()

client.delete(
    collection_name="interaction-history",
    points_selector=FilterSelector(
        filter=Filter(
            must=[
                FieldCondition(
                    key="timestamp",
                    range={
                        "lt": cutoff_date
                    }
                )
            ]
        )
    )
)
```

---

## Common Patterns

### Pattern 1: Error Solution Lookup

```python
def find_error_solution(error_message):
    """Search for known solution to error"""

    # Create embedding
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=error_message
    )

    # Search error-solutions
    results = client.search(
        collection_name="error-solutions",
        query_vector=response["embedding"],
        limit=3,
        score_threshold=0.75
    )

    if results and results[0].score > 0.85:
        return {
            "found": True,
            "solution": results[0].payload["correct_solution"],
            "confidence": results[0].score
        }
    else:
        return {"found": False}

# Usage
result = find_error_solution("OSError: Read-only file system /nix/store")
if result["found"]:
    print(f"Solution: {result['solution']}")
```

### Pattern 2: Best Practice Retrieval

```python
def get_best_practices(task_description):
    """Retrieve best practices for a task"""

    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=task_description
    )

    results = client.search(
        collection_name="best-practices",
        query_vector=response["embedding"],
        limit=5,
        score_threshold=0.6
    )

    practices = [r.payload for r in results]
    return practices
```

### Pattern 3: Context Augmentation

```python
def augment_query_with_context(query):
    """Add relevant local context to query"""

    # Search for relevant context
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )

    results = client.search(
        collection_name="codebase-context",
        query_vector=response["embedding"],
        limit=3,
        score_threshold=0.7
    )

    if not results:
        return query  # No context found

    # Build augmented query
    context = "\n\n".join([r.payload["text"] for r in results])

    augmented = f"""
Context from previous work:
{context}

Current query: {query}
"""

    return augmented
```

---

## Troubleshooting

### Low Search Scores

**Problem**: All search results have score < 0.5

**Solutions**:
```python
# 1. Check embedding model consistency
# Make sure same model used for storage and retrieval

# 2. Verify data in collection
info = client.get_collection("collection-name")
print(f"Points: {info.points_count}")  # Should be > 0

# 3. Try different query phrasing
# "fix error" vs "error solution" may give different results
```

### Slow Searches

**Problem**: Search takes > 1 second

**Solutions**:
```python
# 1. Enable indexing
client.update_collection(
    collection_name="large-collection",
    hnsw_config=HnswConfig(m=16, ef_construct=100)
)

# 2. Reduce limit
results = client.search(limit=5)  # Not limit=1000

# 3. Add score threshold
results = client.search(score_threshold=0.7)
```

---

## Next Steps

- **Use for RAG**: [RAG Context Guide](21-RAG-CONTEXT.md)
- **Store learnings**: [Continuous Learning](22-CONTINUOUS-LEARNING.md)
- **Pattern extraction**: [Pattern Extraction](42-PATTERN-EXTRACTION.md)
- **PostgreSQL integration**: [Postgres Operations](31-POSTGRES-OPS.md)
