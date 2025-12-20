# Error Logging & Learning

**Purpose**: Track errors, store solutions, prevent recurrence

---

## Core Principle

**Every error is a learning opportunity.**

Store:
- ❌ What failed
- 🔍 Why it failed
- ✅ What fixed it
- 📝 How to prevent it

---

## Error Storage Schema

### Complete Error Record

```python
error_record = {
    "error_message": "Full error text",
    "error_type": "OSError | TypeError | ConnectionError | etc",
    "stack_trace": "Full stack trace if available",
    "context": {
        "file": "Where error occurred",
        "function": "Which function failed",
        "line_number": 42
    },
    "attempted_solutions": [
        "First thing tried",
        "Second thing tried"
    ],
    "correct_solution": "What actually worked",
    "root_cause": "Why error occurred",
    "severity": "critical | high | medium | low",
    "timestamp": "2025-12-20T10:00:00Z",
    "resolved": True
}
```

---

## Store Error with Solution

### Quick Storage

```python
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid
from datetime import datetime

def store_error_solution(error_msg, solution, root_cause=None, severity="medium"):
    """Store error and solution for future reference"""

    # Create embedding from error message
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=error_msg
    )

    # Prepare payload
    payload = {
        "error": error_msg,
        "solution": solution,
        "root_cause": root_cause or "Unknown",
        "severity": severity,
        "timestamp": datetime.utcnow().isoformat(),
        "resolved": True
    }

    # Store in Qdrant
    client = QdrantClient(url="http://localhost:6333")
    client.upsert(
        collection_name="error-solutions",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=response["embedding"],
                payload=payload
            )
        ]
    )

    print(f"✓ Error solution stored")

# Example usage
store_error_solution(
    error_msg="OSError: [Errno 30] Read-only file system: '/nix/store/...'",
    solution="Use Python virtual environment: python3 -m venv venv && source venv/bin/activate",
    root_cause="NixOS /nix/store is immutable, cannot modify system Python",
    severity="high"
)
```

### Complete Error Record

```python
def store_complete_error(error_data):
    """Store comprehensive error information"""

    # Create embedding
    embedding_text = f"{error_data['error_message']} {error_data.get('context', {}).get('function', '')}"

    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=embedding_text
    )

    # Add metadata
    payload = {
        **error_data,
        "timestamp": datetime.utcnow().isoformat(),
        "category": categorize_error(error_data["error_message"])
    }

    # Store in Qdrant
    client = QdrantClient(url="http://localhost:6333")
    client.upsert(
        collection_name="error-solutions",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=response["embedding"],
                payload=payload
            )
        ]
    )

    # Also store in PostgreSQL for structured queries
    store_error_postgres(payload)

    return payload

def categorize_error(error_msg):
    """Automatically categorize error type"""

    error_msg_lower = error_msg.lower()

    if "permission" in error_msg_lower or "access denied" in error_msg_lower:
        return "permission"
    elif "not found" in error_msg_lower or "no such file" in error_msg_lower:
        return "file_not_found"
    elif "connection" in error_msg_lower or "timeout" in error_msg_lower:
        return "network"
    elif "read-only" in error_msg_lower:
        return "nixos_immutable"
    elif "import" in error_msg_lower or "module" in error_msg_lower:
        return "python_import"
    else:
        return "general"
```

---

## Search for Known Solutions

### Quick Search

```python
def find_error_solution(error_msg):
    """Search for known solution to error"""

    # Create embedding
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=error_msg
    )

    # Search Qdrant
    client = QdrantClient(url="http://localhost:6333")
    results = client.search(
        collection_name="error-solutions",
        query_vector=response["embedding"],
        limit=3,
        score_threshold=0.75
    )

    if results and results[0].score > 0.85:
        # High confidence match
        solution = results[0].payload
        return {
            "found": True,
            "solution": solution["solution"],
            "root_cause": solution.get("root_cause"),
            "confidence": results[0].score,
            "similar_errors": [r.payload for r in results]
        }
    else:
        return {
            "found": False,
            "similar_errors": [r.payload for r in results] if results else []
        }

# Example
error = "ModuleNotFoundError: No module named 'qdrant_client'"
result = find_error_solution(error)

if result["found"]:
    print(f"✓ Solution found (confidence: {result['confidence']:.2f})")
    print(f"Solution: {result['solution']}")
    print(f"Root cause: {result['root_cause']}")
else:
    print("✗ No known solution found")
    if result["similar_errors"]:
        print("Similar errors:")
        for err in result["similar_errors"]:
            print(f"  - {err['error'][:50]}...")
```

---

## Error Tracking Workflow

### 1. Catch Error

```python
try:
    # Code that might fail
    import some_module
except Exception as e:
    # Log error details
    error_data = {
        "error_message": str(e),
        "error_type": type(e).__name__,
        "stack_trace": traceback.format_exc(),
        "context": {
            "file": __file__,
            "function": "my_function"
        }
    }

    # Search for known solution
    solution = find_error_solution(error_data["error_message"])

    if solution["found"]:
        print(f"Known solution: {solution['solution']}")
    else:
        # Log for later resolution
        log_unresolved_error(error_data)
```

### 2. Resolve and Store

```python
def resolve_and_store_error(error_id, solution, root_cause):
    """After fixing error, store the solution"""

    # Retrieve error record
    client = QdrantClient(url="http://localhost:6333")

    # Update with solution
    error_data = {
        "error_id": error_id,
        "solution": solution,
        "root_cause": root_cause,
        "resolved": True,
        "resolution_timestamp": datetime.utcnow().isoformat()
    }

    # Store complete error solution
    store_complete_error(error_data)

    print(f"✓ Error resolved and stored for future reference")
```

---

## Error Analytics

### Error Frequency

```python
def analyze_error_frequency(days=30):
    """Analyze which errors occur most frequently"""

    from datetime import timedelta
    from collections import Counter

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    client = QdrantClient(url="http://localhost:6333")
    results = client.scroll(
        collection_name="error-solutions",
        limit=1000,
        with_payload=True
    )

    # Filter recent errors
    recent_errors = [
        p.payload for p in results[0]
        if p.payload.get("timestamp", "") > cutoff
    ]

    # Count by category
    categories = Counter(
        err.get("category", "unknown") for err in recent_errors
    )

    print(f"=== Error Frequency (Last {days} days) ===\n")
    print(f"Total errors: {len(recent_errors)}\n")

    for category, count in categories.most_common():
        print(f"{category:20s}: {count}")

# Run weekly
analyze_error_frequency(days=7)
```

### Resolution Rate

```python
def calculate_resolution_rate():
    """Calculate percentage of resolved errors"""

    client = QdrantClient(url="http://localhost:6333")
    results = client.scroll(
        collection_name="error-solutions",
        limit=1000,
        with_payload=True
    )

    total = len(results[0])
    resolved = sum(1 for p in results[0] if p.payload.get("resolved", False))

    rate = (resolved / total * 100) if total > 0 else 0

    print(f"Resolution rate: {rate:.1f}% ({resolved}/{total})")

    return rate
```

---

## PostgreSQL Error Logging

### Store in Database

```python
import psycopg2

def store_error_postgres(error_data):
    """Store error in PostgreSQL for structured queries"""

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="mcp",
        user="mcp",
        password="your-password"
    )

    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_log (
            id SERIAL PRIMARY KEY,
            error_message TEXT NOT NULL,
            error_type VARCHAR(100),
            solution TEXT,
            root_cause TEXT,
            severity VARCHAR(20),
            category VARCHAR(50),
            resolved BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMP DEFAULT NOW()
        );
    """)

    # Insert error
    cursor.execute("""
        INSERT INTO error_log
        (error_message, error_type, solution, root_cause, severity, category, resolved)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (
        error_data.get("error_message"),
        error_data.get("error_type"),
        error_data.get("solution"),
        error_data.get("root_cause"),
        error_data.get("severity", "medium"),
        error_data.get("category", "general"),
        error_data.get("resolved", False)
    ))

    error_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return error_id
```

### Query Error History

```python
def get_unresolved_errors():
    """Get all unresolved errors from PostgreSQL"""

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="mcp",
        user="mcp",
        password="your-password"
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, error_message, error_type, timestamp
        FROM error_log
        WHERE resolved = FALSE
        ORDER BY timestamp DESC;
    """)

    errors = cursor.fetchall()

    cursor.close()
    conn.close()

    return errors
```

---

## Best Practices

1. **Always store solutions** - Even for simple errors
2. **Include context** - File, function, line number
3. **Categorize errors** - Makes patterns visible
4. **Search first** - Check for known solutions before debugging
5. **Update solutions** - If better fix found, update record
6. **Track severity** - Prioritize critical errors

---

## Common Error Patterns

### NixOS Immutable Store

```python
ERROR_PATTERNS = {
    "nixos_immutable": {
        "indicators": ["read-only file system", "/nix/store"],
        "solution": "Use virtual environment for Python packages",
        "command": "python3 -m venv venv && source venv/bin/activate"
    },
    "missing_package": {
        "indicators": ["ModuleNotFoundError", "No module named"],
        "solution": "Install in virtual environment",
        "command": "pip install PACKAGE_NAME"
    },
    "permission_denied": {
        "indicators": ["Permission denied", "EACCES"],
        "solution": "Check file ownership and permissions",
        "command": "ls -la FILE && chmod +x FILE"
    }
}

def match_error_pattern(error_msg):
    """Match error to known pattern"""

    error_lower = error_msg.lower()

    for pattern_name, pattern_data in ERROR_PATTERNS.items():
        if any(ind in error_lower for ind in pattern_data["indicators"]):
            return pattern_data

    return None
```

---

## Next Steps

- [Continuous Learning](22-CONTINUOUS-LEARNING.md) - Store all outcomes
- [Debugging Guide](12-DEBUGGING.md) - Troubleshooting
- [Qdrant Operations](30-QDRANT-OPERATIONS.md) - Vector storage
- [PostgreSQL Operations](31-POSTGRES-OPS.md) - Structured storage
