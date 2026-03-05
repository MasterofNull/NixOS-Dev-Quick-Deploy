# Pattern Extraction - Mine Reusable Solutions

**Purpose**: Extract reusable patterns from successful interactions for future use

---

## Why Extract Patterns?

**Individual solutions → Reusable patterns → System knowledge**

- 3 similar NixOS config fixes → Generic "enable service" pattern
- 5 error resolutions → Error category pattern
- Multiple code reviews → Code quality checklist

**Benefits**:
- Faster resolution of similar problems
- Accumulated system expertise
- Foundation for fine-tuning
- Reduced dependency on remote API

---

## Pattern Identification

### When to Extract

Extract patterns when:
- ✅ Same solution works 3+ times
- ✅ Value score consistently > 0.7
- ✅ Solution is generic (not specific to one case)
- ✅ Pattern would save future time/tokens

### Pattern Types

```python
PATTERN_TYPES = {
    "error-fix": {
        "description": "Known error with proven solution",
        "example": "OSError read-only /nix/store → use venv"
    },
    "config-template": {
        "description": "Configuration pattern",
        "example": "Enable systemd service in NixOS"
    },
    "code-idiom": {
        "description": "Common code pattern",
        "example": "Iterate with enumerate() instead of range(len())"
    },
    "workflow": {
        "description": "Multi-step process",
        "example": "Debug container: logs → inspect → restart"
    },
    "best-practice": {
        "description": "Recommended approach",
        "example": "Always use virtual env for Python in NixOS"
    }
}
```

---

## Extraction Process

### Step 1: Find Similar Interactions

```python
from qdrant_client import QdrantClient
from collections import defaultdict
import ollama

def find_similar_interactions(min_similarity=0.85):
    """Group similar interactions together"""

    client = QdrantClient(url="http://localhost:6333")

    # Get all interactions
    results = client.scroll(
        collection_name="interaction-history",
        limit=1000,
        with_payload=True,
        with_vectors=True
    )

    interactions = results[0]

    # Group by similarity
    groups = []
    processed = set()

    for i, interaction in enumerate(interactions):
        if i in processed:
            continue

        # Find similar interactions
        similar = [interaction]
        processed.add(i)

        for j, other in enumerate(interactions[i+1:], start=i+1):
            if j in processed:
                continue

            # Calculate cosine similarity
            similarity = cosine_similarity(
                interaction.vector,
                other.vector
            )

            if similarity >= min_similarity:
                similar.append(other)
                processed.add(j)

        # If 3+ similar interactions, consider for pattern
        if len(similar) >= 3:
            groups.append(similar)

    return groups

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity"""
    import numpy as np
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
```

### Step 2: Analyze Common Elements

```python
def analyze_pattern(interactions):
    """Extract common elements from similar interactions"""

    # Collect all queries and solutions
    queries = [i.payload["query"] for i in interactions]
    solutions = [i.payload.get("response", "") for i in interactions]

    # Identify common keywords in queries
    from collections import Counter
    import re

    all_words = []
    for query in queries:
        words = re.findall(r'\w+', query.lower())
        all_words.extend(words)

    common_keywords = [
        word for word, count in Counter(all_words).most_common(10)
        if count >= len(interactions) * 0.5  # In 50%+ of queries
    ]

    # Find common solution elements
    solution_patterns = extract_common_solution_parts(solutions)

    return {
        "query_keywords": common_keywords,
        "solution_pattern": solution_patterns,
        "occurrence_count": len(interactions),
        "avg_value_score": sum(
            i.payload.get("value_score", 0) for i in interactions
        ) / len(interactions)
    }

def extract_common_solution_parts(solutions):
    """Find common parts in solutions"""

    # Simple approach: find common substrings
    if not solutions:
        return ""

    # Use first solution as template
    template = solutions[0]

    # Find parts that appear in all solutions
    common_parts = []
    words = template.split()

    for i in range(len(words)):
        for j in range(i+1, len(words)+1):
            phrase = " ".join(words[i:j])

            # Check if phrase appears in all solutions
            if all(phrase.lower() in s.lower() for s in solutions):
                if len(phrase) > 20:  # Meaningful length
                    common_parts.append(phrase)

    return max(common_parts, key=len) if common_parts else template[:200]
```

### Step 3: Generate Pattern Template

```python
def create_pattern_template(pattern_analysis, pattern_type):
    """Create reusable pattern template"""

    template = {
        "pattern_type": pattern_type,
        "name": generate_pattern_name(pattern_analysis["query_keywords"]),
        "trigger_keywords": pattern_analysis["query_keywords"],
        "solution_template": pattern_analysis["solution_pattern"],
        "occurrence_count": pattern_analysis["occurrence_count"],
        "confidence": pattern_analysis["avg_value_score"],
        "prerequisites": extract_prerequisites(pattern_analysis),
        "variations": [],  # Can be filled with specific variations
        "examples": []     # Can be filled with actual examples
    }

    return template

def generate_pattern_name(keywords):
    """Generate descriptive pattern name"""

    # Use most significant keywords
    significant = [k for k in keywords if len(k) > 3][:3]
    return "-".join(significant) if significant else "generic-pattern"

def extract_prerequisites(pattern_analysis):
    """Extract prerequisites from pattern"""

    solution = pattern_analysis["solution_pattern"].lower()

    prerequisites = []

    # Common prerequisite indicators
    if "install" in solution or "package" in solution:
        prerequisites.append("Required packages must be installed")

    if "enable" in solution or "service" in solution:
        prerequisites.append("Service must be available in system")

    if "restart" in solution or "reload" in solution:
        prerequisites.append("May require system restart")

    return prerequisites
```

### Step 4: Store Pattern

```python
def store_pattern(pattern_template):
    """Store extracted pattern in Qdrant"""

    from qdrant_client.models import PointStruct
    import uuid

    # Create embedding from pattern name and keywords
    pattern_text = f"{pattern_template['name']} {' '.join(pattern_template['trigger_keywords'])}"

    embedding = ollama.embeddings(
        model="nomic-embed-text",
        prompt=pattern_text
    )

    # Store in skills-patterns collection
    client = QdrantClient(url="http://localhost:6333")

    client.upsert(
        collection_name="skills-patterns",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding["embedding"],
                payload=pattern_template
            )
        ]
    )

    print(f"✓ Pattern stored: {pattern_template['name']}")
    print(f"  Occurrences: {pattern_template['occurrence_count']}")
    print(f"  Confidence: {pattern_template['confidence']:.2f}")

    return pattern_template
```

---

## Complete Extraction Workflow

```python
class PatternExtractor:
    """Automated pattern extraction from interactions"""

    def __init__(self):
        self.client = QdrantClient(url="http://localhost:6333")

    def extract_all_patterns(self, min_occurrences=3, min_value=0.7):
        """Extract all patterns from interaction history"""

        print("=== Pattern Extraction ===")

        # Step 1: Find similar interaction groups
        print("Finding similar interactions...")
        groups = find_similar_interactions(min_similarity=0.85)

        print(f"Found {len(groups)} potential pattern groups")

        extracted_patterns = []

        for i, group in enumerate(groups):
            print(f"\n--- Group {i+1} ---")

            # Step 2: Analyze pattern
            analysis = analyze_pattern(group)

            # Filter by value score
            if analysis["avg_value_score"] < min_value:
                print(f"  Skipped (low value: {analysis['avg_value_score']:.2f})")
                continue

            # Filter by occurrence count
            if analysis["occurrence_count"] < min_occurrences:
                print(f"  Skipped (only {analysis['occurrence_count']} occurrences)")
                continue

            # Step 3: Determine pattern type
            pattern_type = self.classify_pattern(analysis)

            # Step 4: Create template
            template = create_pattern_template(analysis, pattern_type)

            # Step 5: Store pattern
            stored = store_pattern(template)

            extracted_patterns.append(stored)

        print(f"\n=== Extraction Complete ===")
        print(f"Total patterns extracted: {len(extracted_patterns)}")

        return extracted_patterns

    def classify_pattern(self, analysis):
        """Classify pattern type based on content"""

        keywords = " ".join(analysis["query_keywords"]).lower()
        solution = analysis["solution_pattern"].lower()

        if "error" in keywords or "fix" in keywords:
            return "error-fix"
        elif "config" in keywords or "enable" in keywords or "nixos" in keywords:
            return "config-template"
        elif "code" in keywords or "function" in keywords:
            return "code-idiom"
        elif any(word in solution for word in ["step 1", "first", "then", "finally"]):
            return "workflow"
        else:
            return "best-practice"

# Example usage
extractor = PatternExtractor()
patterns = extractor.extract_all_patterns(
    min_occurrences=3,
    min_value=0.7
)

for pattern in patterns:
    print(f"\nPattern: {pattern['name']}")
    print(f"  Type: {pattern['pattern_type']}")
    print(f"  Confidence: {pattern['confidence']:.2f}")
    print(f"  Used {pattern['occurrence_count']} times")
```

---

## Pattern Refinement

### Manual Review and Enhancement

```python
def enhance_pattern(pattern_id, enhancements):
    """Manually enhance extracted pattern"""

    client = QdrantClient(url="http://localhost:6333")

    # Retrieve pattern
    pattern = client.retrieve(
        collection_name="skills-patterns",
        ids=[pattern_id]
    )[0]

    # Add enhancements
    payload = pattern.payload
    payload.update({
        "examples": enhancements.get("examples", []),
        "variations": enhancements.get("variations", []),
        "notes": enhancements.get("notes", ""),
        "verified": True,
        "last_updated": datetime.utcnow().isoformat()
    })

    # Update in Qdrant
    from qdrant_client.models import SetPayload

    client.set_payload(
        collection_name="skills-patterns",
        payload=payload,
        points=[pattern_id]
    )

    print(f"✓ Pattern enhanced: {pattern_id}")

# Example
enhance_pattern(
    pattern_id="pattern-uuid-here",
    enhancements={
        "examples": [
            "services.docker.enable = true;",
            "services.postgresql.enable = true;"
        ],
        "variations": [
            "For user services, use home-manager instead",
            "For custom services, define systemd.services.custom"
        ],
        "notes": "Always rebuild NixOS after enabling services"
    }
)
```

### Pattern Versioning

```python
def create_pattern_version(pattern_id, updates):
    """Create new version of pattern while preserving old"""

    import uuid

    client = QdrantClient(url="http://localhost:6333")

    # Get original pattern
    original = client.retrieve(
        collection_name="skills-patterns",
        ids=[pattern_id]
    )[0]

    # Create new version
    new_payload = original.payload.copy()
    new_payload.update(updates)
    new_payload["version"] = new_payload.get("version", 1) + 1
    new_payload["previous_version"] = pattern_id
    new_payload["created"] = datetime.utcnow().isoformat()

    # Store new version
    from qdrant_client.models import PointStruct

    new_id = str(uuid.uuid4())

    client.upsert(
        collection_name="skills-patterns",
        points=[
            PointStruct(
                id=new_id,
                vector=original.vector,  # Keep same embedding
                payload=new_payload
            )
        ]
    )

    print(f"✓ New pattern version created: {new_id}")
    print(f"  Previous version: {pattern_id}")
    print(f"  Version: {new_payload['version']}")

    return new_id
```

---

## Pattern Usage

### Apply Pattern to New Query

```python
def find_and_apply_pattern(query):
    """Search for applicable pattern and apply it"""

    # Create embedding
    embedding = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )

    # Search patterns
    client = QdrantClient(url="http://localhost:6333")

    results = client.search(
        collection_name="skills-patterns",
        query_vector=embedding["embedding"],
        limit=3,
        score_threshold=0.8
    )

    if not results:
        return None

    # Get best matching pattern
    best_pattern = results[0].payload

    print(f"✓ Pattern found: {best_pattern['name']}")
    print(f"  Confidence: {results[0].score:.2f}")
    print(f"  Used successfully {best_pattern['occurrence_count']} times")

    # Apply pattern
    solution = best_pattern["solution_template"]

    # Can customize solution based on specific query
    # ...

    return {
        "pattern_name": best_pattern["name"],
        "solution": solution,
        "confidence": results[0].score,
        "prerequisites": best_pattern.get("prerequisites", [])
    }

# Example
result = find_and_apply_pattern("Enable Docker in NixOS")

if result:
    print(f"\nSolution:")
    print(result["solution"])
    print(f"\nPrerequisites:")
    for prereq in result["prerequisites"]:
        print(f"  - {prereq}")
```

---

## Pattern Analytics

### Pattern Usage Statistics

```python
def analyze_pattern_usage():
    """Analyze which patterns are most useful"""

    client = QdrantClient(url="http://localhost:6333")

    results = client.scroll(
        collection_name="skills-patterns",
        limit=100,
        with_payload=True
    )

    patterns = results[0]

    # Sort by occurrence count
    patterns.sort(
        key=lambda p: p.payload.get("occurrence_count", 0),
        reverse=True
    )

    print("=== Pattern Usage Statistics ===\n")

    for i, pattern in enumerate(patterns[:10], 1):
        payload = pattern.payload
        print(f"{i}. {payload.get('name', 'unnamed')}")
        print(f"   Type: {payload.get('pattern_type', 'unknown')}")
        print(f"   Used: {payload.get('occurrence_count', 0)} times")
        print(f"   Confidence: {payload.get('confidence', 0):.2f}")
        print()

# Run monthly
analyze_pattern_usage()
```

---

## Best Practices

1. **Extract regularly** - Weekly pattern extraction from new interactions
2. **Verify manually** - Review auto-extracted patterns before relying on them
3. **Version patterns** - Keep history when updating patterns
4. **Monitor usage** - Track which patterns are actually helpful
5. **Refine over time** - Update patterns based on feedback
6. **Document examples** - Add real examples to pattern templates

---

## Next Steps

- **Value scoring**: [Value Scoring Guide](41-VALUE-SCORING.md)
- **Store patterns**: [Qdrant Operations](30-QDRANT-OPERATIONS.md)
- **Use in workflow**: [Hybrid Workflow](40-HYBRID-WORKFLOW.md)
- **Continuous learning**: [Learning Workflow](22-CONTINUOUS-LEARNING.md)
