# Value Scoring - Identify High-Value Interactions

**Purpose**: Calculate value score (0-1) to identify which interactions to prioritize for learning

---

## Why Value Scoring?

**Not all interactions are equally valuable for learning:**

- ✅ Complex solution that works → High value, store for reuse
- ✅ Novel problem solved → High value, extract pattern
- ❌ Simple "what is X" query → Low value, don't prioritize
- ❌ Failed attempt, no resolution → Low value for fine-tuning

**Value scoring helps**:
- Prioritize storage of useful patterns
- Generate high-quality fine-tuning datasets
- Identify knowledge gaps
- Track learning effectiveness

---

## 5-Factor Scoring Algorithm

### Factor 1: Complexity (Weight: 0.2)

**Measures**: How complex was the task?

```python
def score_complexity(interaction):
    """Score 0-1 based on complexity indicators"""

    indicators = {
        # Lines of code/config involved
        "lines_of_code": min(1.0, interaction.get("lines_of_code", 0) / 100),

        # Number of files modified
        "files_modified": min(1.0, interaction.get("files_modified", 0) / 5),

        # Number of steps in solution
        "steps": min(1.0, interaction.get("solution_steps", 0) / 10),

        # Time to solve (minutes)
        "time_spent": min(1.0, interaction.get("time_minutes", 0) / 30)
    }

    # Average of indicators
    complexity = sum(indicators.values()) / len(indicators)

    return complexity

# Example
interaction = {
    "lines_of_code": 50,
    "files_modified": 3,
    "solution_steps": 5,
    "time_minutes": 20
}

score = score_complexity(interaction)
print(f"Complexity: {score:.2f}")  # 0.63
```

### Factor 2: Reusability (Weight: 0.3)

**Measures**: How likely is this solution to be reused?

```python
def score_reusability(interaction):
    """Score 0-1 based on reusability"""

    # Is solution generic or specific?
    is_generic = interaction.get("is_generic_pattern", False)

    # Applies to multiple scenarios?
    applicability = {
        "single_case": 0.2,      # Only this specific case
        "similar_cases": 0.5,    # Similar situations
        "category": 0.8,         # Entire category
        "universal": 1.0         # Broadly applicable
    }

    scope = interaction.get("applicability_scope", "single_case")
    scope_score = applicability.get(scope, 0.3)

    # Has the pattern already been seen?
    is_novel = interaction.get("is_novel_pattern", True)
    novelty_bonus = 0.3 if is_novel else 0.0

    # Uses standard tools/practices?
    uses_standard_tools = interaction.get("uses_standard_tools", True)
    standard_bonus = 0.2 if uses_standard_tools else 0.0

    # Calculate reusability
    reusability = min(1.0, scope_score + novelty_bonus + standard_bonus) / 1.5

    return reusability

# Example
interaction = {
    "is_generic_pattern": True,
    "applicability_scope": "category",  # NixOS config patterns
    "is_novel_pattern": True,
    "uses_standard_tools": True
}

score = score_reusability(interaction)
print(f"Reusability: {score:.2f}")  # 0.87
```

### Factor 3: Novelty (Weight: 0.2)

**Measures**: Is this a new problem or solution?

```python
from qdrant_client import QdrantClient
import ollama

def score_novelty(query):
    """Score 0-1 based on novelty"""

    # Search for similar past interactions
    embedding = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )

    client = QdrantClient(url="http://localhost:6333")

    results = client.search(
        collection_name="interaction-history",
        query_vector=embedding["embedding"],
        limit=5
    )

    if not results:
        # No similar interactions found - very novel
        return 1.0

    # Check similarity scores
    best_score = results[0].score

    if best_score > 0.95:
        # Almost identical interaction exists
        return 0.1
    elif best_score > 0.85:
        # Very similar interaction
        return 0.3
    elif best_score > 0.7:
        # Somewhat similar
        return 0.6
    else:
        # Quite different
        return 0.9

# Example
novelty = score_novelty("Fix GNOME keyring error in NixOS")
print(f"Novelty: {novelty:.2f}")
```

### Factor 4: User Confirmation (Weight: 0.15)

**Measures**: Did the user verify success?

```python
def score_confirmation(interaction):
    """Score 0-1 based on user confirmation"""

    confirmation_type = interaction.get("confirmation", "none")

    confirmation_scores = {
        "explicit_success": 1.0,      # User said "it works"
        "implicit_success": 0.8,      # User continued, no errors
        "partial_success": 0.5,       # Worked with modifications
        "unconfirmed": 0.3,           # No confirmation
        "explicit_failure": 0.0       # User said it failed
    }

    score = confirmation_scores.get(confirmation_type, 0.3)

    # Bonus for user providing additional context
    if interaction.get("user_provided_feedback", False):
        score = min(1.0, score + 0.1)

    return score

# Example
interaction = {
    "confirmation": "explicit_success",
    "user_provided_feedback": True
}

score = score_confirmation(interaction)
print(f"Confirmation: {score:.2f}")  # 1.0
```

### Factor 5: Impact (Weight: 0.15)

**Measures**: How important was this solution?

```python
def score_impact(interaction):
    """Score 0-1 based on impact/severity"""

    # Severity of issue resolved
    severity_scores = {
        "critical": 1.0,      # System broken, blocking work
        "high": 0.8,          # Major feature not working
        "medium": 0.5,        # Minor issue, workaround exists
        "low": 0.3,           # Nice to have, cosmetic
        "trivial": 0.1        # Documentation typo, etc
    }

    severity = interaction.get("severity", "medium")
    severity_score = severity_scores.get(severity, 0.5)

    # Impact on workflow
    blocks_work = interaction.get("blocks_work", False)
    workflow_impact = 0.2 if blocks_work else 0.0

    # Number of users affected
    user_impact = min(0.3, interaction.get("users_affected", 1) / 10)

    # Total impact
    impact = min(1.0, severity_score + workflow_impact + user_impact)

    return impact

# Example
interaction = {
    "severity": "high",
    "blocks_work": True,
    "users_affected": 1
}

score = score_impact(interaction)
print(f"Impact: {score:.2f}")  # 1.0 (capped)
```

---

## Complete Value Score Calculation

```python
def calculate_value_score(interaction):
    """Calculate overall value score (0-1) using 5 factors"""

    # Factor weights
    weights = {
        "complexity": 0.20,
        "reusability": 0.30,
        "novelty": 0.20,
        "confirmation": 0.15,
        "impact": 0.15
    }

    # Calculate each factor
    scores = {
        "complexity": score_complexity(interaction),
        "reusability": score_reusability(interaction),
        "novelty": score_novelty(interaction.get("query", "")),
        "confirmation": score_confirmation(interaction),
        "impact": score_impact(interaction)
    }

    # Weighted average
    value_score = sum(
        scores[factor] * weights[factor]
        for factor in weights
    )

    # Round to 2 decimals
    value_score = round(value_score, 2)

    # Return score and breakdown
    return {
        "value_score": value_score,
        "scores": scores,
        "weights": weights
    }

# Example: High-value interaction
interaction = {
    # Complexity factors
    "lines_of_code": 75,
    "files_modified": 4,
    "solution_steps": 7,
    "time_minutes": 25,

    # Reusability factors
    "is_generic_pattern": True,
    "applicability_scope": "category",
    "is_novel_pattern": True,
    "uses_standard_tools": True,

    # Novelty (will search Qdrant)
    "query": "Fix GNOME keyring error in NixOS",

    # Confirmation factors
    "confirmation": "explicit_success",
    "user_provided_feedback": True,

    # Impact factors
    "severity": "high",
    "blocks_work": True,
    "users_affected": 1
}

result = calculate_value_score(interaction)

print(f"\n=== Value Score Breakdown ===")
print(f"Overall Score: {result['value_score']}")
print(f"\nFactor Scores:")
for factor, score in result['scores'].items():
    weight = result['weights'][factor]
    weighted = score * weight
    print(f"  {factor:15s}: {score:.2f} (weight: {weight:.2f}) = {weighted:.3f}")

# Output example:
# Overall Score: 0.84
# Factor Scores:
#   complexity     : 0.68 (weight: 0.20) = 0.136
#   reusability    : 0.87 (weight: 0.30) = 0.261
#   novelty        : 0.90 (weight: 0.20) = 0.180
#   confirmation   : 1.00 (weight: 0.15) = 0.150
#   impact         : 1.00 (weight: 0.15) = 0.150
```

---

## Usage in Workflow

### Automatic Scoring After Interaction

```python
def store_interaction_with_value(query, response, metadata):
    """Store interaction and calculate value score"""

    # Build complete interaction record
    interaction = {
        "query": query,
        "response": response,
        **metadata  # Include all metadata
    }

    # Calculate value score
    value_data = calculate_value_score(interaction)
    interaction["value_score"] = value_data["value_score"]
    interaction["value_breakdown"] = value_data["scores"]

    # Store in Qdrant
    from qdrant_client.models import PointStruct
    import uuid

    embedding = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )

    client = QdrantClient(url="http://localhost:6333")
    client.upsert(
        collection_name="interaction-history",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding["embedding"],
                payload=interaction
            )
        ]
    )

    # If high value, also store in patterns
    if value_data["value_score"] >= 0.7:
        client.upsert(
            collection_name="skills-patterns",
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding["embedding"],
                    payload=interaction
                )
            ]
        )

        print(f"✓ High-value interaction stored (score: {value_data['value_score']})")

    return value_data
```

### Filter by Value Score

```python
def get_high_value_interactions(min_score=0.7, days=30):
    """Retrieve high-value interactions for fine-tuning"""

    from datetime import datetime, timedelta

    cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

    client = QdrantClient(url="http://localhost:6333")

    # Scroll through all interactions
    results = client.scroll(
        collection_name="interaction-history",
        limit=1000,
        with_payload=True
    )

    # Filter by value score and date
    high_value = [
        p.payload for p in results[0]
        if p.payload.get("value_score", 0) >= min_score
        and p.payload.get("timestamp", "") > cutoff_date
    ]

    # Sort by value score
    high_value.sort(key=lambda x: x["value_score"], reverse=True)

    return high_value

# Example
interactions = get_high_value_interactions(min_score=0.75, days=30)
print(f"Found {len(interactions)} high-value interactions")

for i in interactions[:5]:
    print(f"  Score: {i['value_score']:.2f} - {i['query'][:50]}...")
```

---

## Analytics & Monitoring

### Value Score Distribution

```python
def analyze_value_distribution():
    """Analyze distribution of value scores"""

    client = QdrantClient(url="http://localhost:6333")

    results = client.scroll(
        collection_name="interaction-history",
        limit=1000,
        with_payload=True
    )

    scores = [p.payload.get("value_score", 0) for p in results[0]]

    if not scores:
        print("No interactions found")
        return

    print(f"=== Value Score Distribution ===")
    print(f"Total interactions: {len(scores)}")
    print(f"Average: {sum(scores)/len(scores):.2f}")
    print(f"Min: {min(scores):.2f}")
    print(f"Max: {max(scores):.2f}")

    # Count by range
    ranges = {
        "Very High (0.8-1.0)": len([s for s in scores if s >= 0.8]),
        "High (0.6-0.8)": len([s for s in scores if 0.6 <= s < 0.8]),
        "Medium (0.4-0.6)": len([s for s in scores if 0.4 <= s < 0.6]),
        "Low (0.2-0.4)": len([s for s in scores if 0.2 <= s < 0.4]),
        "Very Low (0.0-0.2)": len([s for s in scores if s < 0.2])
    }

    print(f"\nDistribution:")
    for range_name, count in ranges.items():
        percentage = (count / len(scores)) * 100
        print(f"  {range_name}: {count} ({percentage:.1f}%)")

# Run weekly
analyze_value_distribution()
```

---

## Tuning Value Scoring

### Adjust Weights

```python
# For code-focused learning system
CODE_FOCUSED_WEIGHTS = {
    "complexity": 0.25,      # Higher weight on complexity
    "reusability": 0.35,     # Emphasize reusable patterns
    "novelty": 0.15,         # Less emphasis on novelty
    "confirmation": 0.15,
    "impact": 0.10
}

# For error-solving focus
ERROR_FOCUSED_WEIGHTS = {
    "complexity": 0.15,
    "reusability": 0.25,
    "novelty": 0.25,         # Higher - new errors are valuable
    "confirmation": 0.20,    # Higher - verify fixes work
    "impact": 0.15
}

# Use custom weights
def calculate_value_score_custom(interaction, weights=None):
    if weights is None:
        weights = CODE_FOCUSED_WEIGHTS

    # ... rest of calculation with custom weights
```

---

## Best Practices

1. **Always calculate value scores** - Every interaction should be scored
2. **Store breakdown** - Keep factor scores for analysis
3. **Review high-value interactions** - Weekly review of 0.7+ scores
4. **Tune weights** - Adjust based on your learning goals
5. **Monitor distribution** - Aim for 10-20% high-value (0.7+)

---

## Next Steps

- **Extract patterns**: [Pattern Extraction](42-PATTERN-EXTRACTION.md)
- **Continuous learning**: [Learning Workflow](22-CONTINUOUS-LEARNING.md)
- **Hybrid workflow**: [Hybrid Workflow](40-HYBRID-WORKFLOW.md)
- **Qdrant operations**: [Qdrant Guide](30-QDRANT-OPERATIONS.md)
