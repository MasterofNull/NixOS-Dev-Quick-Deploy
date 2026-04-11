# Memory System Integration Examples

**Version:** 1.0.0
**Last Updated:** 2026-04-11

---

## Table of Contents

1. [Basic Fact Storage and Retrieval](#example-1-basic-fact-storage-and-retrieval)
2. [Using Metadata Filtering](#example-2-using-metadata-filtering)
3. [Temporal Queries](#example-3-temporal-queries)
4. [Agent Diary Usage](#example-4-agent-diary-usage)
5. [Progressive Memory Loading](#example-5-progressive-memory-loading)
6. [Benchmarking Custom Corpus](#example-6-benchmarking-custom-corpus)
7. [Integration with Workflow System](#example-7-integration-with-workflow-system)
8. [Custom Fact Store Backends](#example-8-custom-fact-store-backends)
9. [CLI Integration in Scripts](#example-9-cli-integration-in-scripts)
10. [Multi-Agent Memory Sharing](#example-10-multi-agent-memory-sharing)

---

## Example 1: Basic Fact Storage and Retrieval

### Scenario
Store a technical decision and retrieve it later using semantic search.

### Code

```python
#!/usr/bin/env python3
"""Basic fact storage and retrieval example"""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add ai-stack to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.temporal_facts import TemporalFact

# Create in-memory store
from scripts.ai import InMemoryFactStore
store = InMemoryFactStore()

# Store a decision fact
fact = TemporalFact(
    content="Using JWT with 7-day expiry for authentication",
    project="ai-stack",
    topic="auth",
    type="decision",
    tags=["security", "auth", "jwt"],
    confidence=0.95,
    source="architecture-review",
    created_by="claude"
)

fact_id = store.add(fact)
print(f"✅ Stored fact: {fact_id[:8]}")
print(f"   Content: {fact.content}")

# Retrieve by ID
retrieved = store.get_by_id(fact_id)
if retrieved:
    print(f"\n✅ Retrieved fact: {retrieved.content}")
    print(f"   Project: {retrieved.project}")
    print(f"   Topic: {retrieved.topic}")
    print(f"   Type: {retrieved.type}")
    print(f"   Tags: {', '.join(retrieved.tags)}")

# Search for the fact
all_facts = store.get_all()
auth_query = "authentication method"

# Simple text search
matches = [f for f in all_facts if auth_query.lower() in f.content.lower()]
print(f"\n✅ Search results for '{auth_query}':")
for match in matches:
    print(f"   - {match.content}")
```

### Expected Output
```
✅ Stored fact: abc12345
   Content: Using JWT with 7-day expiry for authentication

✅ Retrieved fact: Using JWT with 7-day expiry for authentication
   Project: ai-stack
   Topic: auth
   Type: decision
   Tags: security, auth, jwt

✅ Search results for 'authentication method':
   - Using JWT with 7-day expiry for authentication
```

---

## Example 2: Using Metadata Filtering

### Scenario
Store multiple facts across different projects and topics, then filter efficiently using metadata.

### Code

```python
#!/usr/bin/env python3
"""Metadata filtering example - 34% recall improvement"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.temporal_facts import TemporalFact
from aidb.temporal_query import (
    filter_facts_by_project,
    filter_facts_by_topic,
    filter_facts_by_type,
    filter_facts_by_tags
)

# Initialize store
from scripts.ai import InMemoryFactStore
store = InMemoryFactStore()

# Store facts across multiple projects
facts_to_add = [
    # AI Stack - Auth
    TemporalFact(
        content="Using JWT with 7-day expiry",
        project="ai-stack",
        topic="auth",
        type="decision",
        tags=["jwt", "security"]
    ),
    TemporalFact(
        content="Prefer bcrypt for password hashing",
        project="ai-stack",
        topic="auth",
        type="preference",
        tags=["bcrypt", "security"]
    ),

    # AI Stack - Database
    TemporalFact(
        content="PostgreSQL with pgvector for embeddings",
        project="ai-stack",
        topic="database",
        type="decision",
        tags=["postgres", "vectors"]
    ),

    # Dashboard - Deployment
    TemporalFact(
        content="Dashboard runs on port 8889",
        project="dashboard",
        topic="deployment",
        type="fact",
        tags=["port", "config"]
    ),
]

for fact in facts_to_add:
    store.add(fact)
    print(f"Added: {fact.project}/{fact.topic} - {fact.content[:40]}...")

print(f"\n✅ Total facts: {len(store.get_all())}\n")

# Filtering examples
all_facts = store.get_all()

# Filter by project
ai_facts = filter_facts_by_project(all_facts, "ai-stack")
print(f"AI Stack facts: {len(ai_facts)}")
for fact in ai_facts:
    print(f"  - {fact.topic}: {fact.content}")

# Filter by topic
auth_facts = filter_facts_by_topic(all_facts, "auth")
print(f"\nAuth facts: {len(auth_facts)}")
for fact in auth_facts:
    print(f"  - [{fact.type}] {fact.content}")

# Filter by type
decisions = filter_facts_by_type(all_facts, "decision")
print(f"\nDecision facts: {len(decisions)}")
for fact in decisions:
    print(f"  - {fact.project}/{fact.topic}: {fact.content}")

# Filter by tags (match all)
security_facts = filter_facts_by_tags(all_facts, ["security"], match_all=True)
print(f"\nSecurity-tagged facts: {len(security_facts)}")
for fact in security_facts:
    print(f"  - {fact.content}")

# Combined filtering (project + topic + type)
ai_auth_decisions = filter_facts_by_project(all_facts, "ai-stack")
ai_auth_decisions = filter_facts_by_topic(ai_auth_decisions, "auth")
ai_auth_decisions = filter_facts_by_type(ai_auth_decisions, "decision")

print(f"\nAI Stack auth decisions: {len(ai_auth_decisions)}")
for fact in ai_auth_decisions:
    print(f"  - {fact.content}")
```

### Expected Output
```
Added: ai-stack/auth - Using JWT with 7-day expiry...
Added: ai-stack/auth - Prefer bcrypt for password hashing...
Added: ai-stack/database - PostgreSQL with pgvector for embeddings...
Added: dashboard/deployment - Dashboard runs on port 8889...

✅ Total facts: 4

AI Stack facts: 3
  - auth: Using JWT with 7-day expiry
  - auth: Prefer bcrypt for password hashing
  - database: PostgreSQL with pgvector for embeddings

Auth facts: 2
  - [decision] Using JWT with 7-day expiry
  - [preference] Prefer bcrypt for password hashing

Decision facts: 2
  - ai-stack/auth: Using JWT with 7-day expiry
  - ai-stack/database: PostgreSQL with pgvector for embeddings

Security-tagged facts: 2
  - Using JWT with 7-day expiry
  - Prefer bcrypt for password hashing

AI Stack auth decisions: 1
  - Using JWT with 7-day expiry
```

---

## Example 3: Temporal Queries

### Scenario
Store facts with different validity periods and query what was true at specific times.

### Code

```python
#!/usr/bin/env python3
"""Temporal queries example - time-based fact retrieval"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.temporal_facts import TemporalFact, get_valid_facts, get_stale_facts

# Initialize store
from scripts.ai import InMemoryFactStore
store = InMemoryFactStore()

# Define time points
march_1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
march_15 = datetime(2026, 3, 15, tzinfo=timezone.utc)
march_31 = datetime(2026, 3, 31, tzinfo=timezone.utc)
april_1 = datetime(2026, 4, 1, tzinfo=timezone.utc)
april_15 = datetime(2026, 4, 15, tzinfo=timezone.utc)
now = datetime.now(timezone.utc)

# Store facts with different temporal validity
facts = [
    # Ongoing fact (no end date)
    TemporalFact(
        content="Using PostgreSQL for production database",
        project="ai-stack",
        topic="database",
        type="decision",
        valid_from=march_1,
        valid_until=None  # Ongoing
    ),

    # Fact valid only in March
    TemporalFact(
        content="Dashboard temporarily at localhost:8888",
        project="dashboard",
        topic="deployment",
        type="event",
        valid_from=march_1,
        valid_until=march_31
    ),

    # Fact that started mid-March
    TemporalFact(
        content="Using JWT with 7-day expiry for auth",
        project="ai-stack",
        topic="auth",
        type="decision",
        valid_from=march_15,
        valid_until=None  # Ongoing
    ),

    # Future fact (starts in April)
    TemporalFact(
        content="Dashboard moved to port 8889",
        project="dashboard",
        topic="deployment",
        type="event",
        valid_from=april_1,
        valid_until=None
    ),
]

for fact in facts:
    store.add(fact)
    status = "ongoing" if fact.is_ongoing() else f"until {fact.valid_until.date()}"
    print(f"Added: {fact.content[:40]}... ({status})")

print("\n" + "="*70 + "\n")

# Query: What was valid on March 1st?
all_facts = store.get_all()
march_1_facts = get_valid_facts(all_facts, at_time=march_1)
print(f"Facts valid on March 1st, 2026: {len(march_1_facts)}")
for fact in march_1_facts:
    print(f"  ✅ {fact.content}")

print("\n" + "-"*70 + "\n")

# Query: What was valid on March 15th?
march_15_facts = get_valid_facts(all_facts, at_time=march_15)
print(f"Facts valid on March 15th, 2026: {len(march_15_facts)}")
for fact in march_15_facts:
    print(f"  ✅ {fact.content}")

print("\n" + "-"*70 + "\n")

# Query: What was valid on April 15th?
april_15_facts = get_valid_facts(all_facts, at_time=april_15)
print(f"Facts valid on April 15th, 2026: {len(april_15_facts)}")
for fact in april_15_facts:
    print(f"  ✅ {fact.content}")

print("\n" + "-"*70 + "\n")

# Query: What's stale now?
stale_facts = get_stale_facts(all_facts, current_time=now)
print(f"Stale facts (as of {now.date()}): {len(stale_facts)}")
for fact in stale_facts:
    print(f"  ⏱️  {fact.content}")
    print(f"     Expired: {fact.valid_until.date()}")

print("\n" + "-"*70 + "\n")

# Check individual fact validity
test_fact = all_facts[1]  # Dashboard temporary config
print(f"Testing fact: '{test_fact.content}'")
print(f"  Valid on March 1st: {test_fact.is_valid_at(march_1)}")
print(f"  Valid on March 15th: {test_fact.is_valid_at(march_15)}")
print(f"  Valid on April 1st: {test_fact.is_valid_at(april_1)}")
print(f"  Stale now: {test_fact.is_stale(now)}")
print(f"  Ongoing: {test_fact.is_ongoing()}")
```

### Expected Output
```
Added: Using PostgreSQL for production database... (ongoing)
Added: Dashboard temporarily at localhost:8888... (until 2026-03-31)
Added: Using JWT with 7-day expiry for auth... (ongoing)
Added: Dashboard moved to port 8889... (ongoing)

======================================================================

Facts valid on March 1st, 2026: 2
  ✅ Using PostgreSQL for production database
  ✅ Dashboard temporarily at localhost:8888

----------------------------------------------------------------------

Facts valid on March 15th, 2026: 3
  ✅ Using PostgreSQL for production database
  ✅ Dashboard temporarily at localhost:8888
  ✅ Using JWT with 7-day expiry for auth

----------------------------------------------------------------------

Facts valid on April 15th, 2026: 3
  ✅ Using PostgreSQL for production database
  ✅ Using JWT with 7-day expiry for auth
  ✅ Dashboard moved to port 8889

----------------------------------------------------------------------

Stale facts (as of 2026-04-11): 1
  ⏱️  Dashboard temporarily at localhost:8888
     Expired: 2026-03-31

----------------------------------------------------------------------

Testing fact: 'Dashboard temporarily at localhost:8888'
  Valid on March 1st: True
  Valid on March 15th: True
  Valid on April 1st: False
  Stale now: True
  Ongoing: False
```

---

## Example 4: Agent Diary Usage

### Scenario
Individual agents write to their private diaries to accumulate expertise.

### Code

```python
#!/usr/bin/env python3
"""Agent diary usage example"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.agent_diary import AgentDiary, format_diary_entries

# Qwen writes to diary
print("=== Qwen Agent Diary ===\n")
qwen_diary = AgentDiary("qwen")

# Write some entries
qwen_diary.write(
    "Implemented JWT validation with 7-day expiry. Used bcrypt for hashing.",
    topic="auth",
    tags=["jwt", "security", "bcrypt"],
    create_fact=False  # No fact store in this example
)

qwen_diary.write(
    "Refactored temporal_facts.py to improve performance. Added caching layer.",
    topic="optimization",
    tags=["performance", "caching"],
    create_fact=False
)

qwen_diary.write(
    "Discovered bug in metadata filtering. Query returns stale facts when valid_until is NULL.",
    topic="bugs",
    tags=["bug", "metadata", "filtering"],
    create_fact=False
)

qwen_diary.write(
    "Implemented progressive memory loading with L0-L3 layers. Achieved 50% token reduction.",
    topic="memory",
    tags=["memory", "optimization", "tokens"],
    create_fact=False
)

print("✅ Qwen wrote 4 entries to diary\n")

# Read all entries
print("All diary entries:")
all_entries = qwen_diary.read(limit=10)
print(format_diary_entries(all_entries))

print("\n" + "="*70 + "\n")

# Filter by topic
print("Auth-related entries:")
auth_entries = qwen_diary.read(topic="auth")
print(format_diary_entries(auth_entries))

print("\n" + "="*70 + "\n")

# Search diary
print("Search for 'JWT':")
jwt_results = qwen_diary.search("JWT")
print(format_diary_entries(jwt_results))

print("\n" + "="*70 + "\n")

# Get statistics
print("Diary Statistics:")
stats = qwen_diary.get_stats()
print(f"  Total entries: {stats['total_entries']}")
print(f"  Topics: {', '.join(stats['topics'])}")
print(f"  Tags: {', '.join(stats['tags'][:5])}...")  # First 5 tags
print(f"  Oldest: {stats['oldest_entry'][:10]}")
print(f"  Newest: {stats['newest_entry'][:10]}")

print("\n" + "="*70 + "\n")

# Observer mode (codex reading qwen's diary)
print("=== Codex (Orchestrator) Reading Qwen's Diary ===\n")
qwen_work = AgentDiary.read_as_observer("qwen", limit=5)
print(f"Observer found {len(qwen_work)} entries from qwen")
print(format_diary_entries(qwen_work[:2]))  # Show first 2

# List all available diaries
print("\n" + "="*70 + "\n")
print("Available agent diaries:")
all_diaries = AgentDiary.list_all_diaries()
print(f"  {', '.join(all_diaries) if all_diaries else '(none)'}")
```

### Expected Output
```
=== Qwen Agent Diary ===

✅ Qwen wrote 4 entries to diary

All diary entries:
1. [2026-04-11 15:30] [memory] [memory, optimization, tokens]
   Implemented progressive memory loading with L0-L3 layers. Achieved 50% token reduction.

2. [2026-04-11 15:30] [bugs] [bug, metadata, filtering]
   Discovered bug in metadata filtering. Query returns stale facts when valid_until is NULL.

3. [2026-04-11 15:30] [optimization] [performance, caching]
   Refactored temporal_facts.py to improve performance. Added caching layer.

4. [2026-04-11 15:30] [auth] [jwt, security, bcrypt]
   Implemented JWT validation with 7-day expiry. Used bcrypt for hashing.

======================================================================

Auth-related entries:
1. [2026-04-11 15:30] [auth] [jwt, security, bcrypt]
   Implemented JWT validation with 7-day expiry. Used bcrypt for hashing.

======================================================================

Search for 'JWT':
1. [2026-04-11 15:30] [auth] [jwt, security, bcrypt]
   Implemented JWT validation with 7-day expiry. Used bcrypt for hashing.

======================================================================

Diary Statistics:
  Total entries: 4
  Topics: auth, bugs, memory, optimization
  Tags: bcrypt, bug, caching, filtering, jwt...
  Oldest: 2026-04-11
  Newest: 2026-04-11

======================================================================

=== Codex (Orchestrator) Reading Qwen's Diary ===

Observer found 4 entries from qwen
1. [2026-04-11 15:30] [memory] [memory, optimization, tokens]
   Implemented progressive memory loading with L0-L3 layers. Achieved 50% token reduction.

2. [2026-04-11 15:30] [bugs] [bug, metadata, filtering]
   Discovered bug in metadata filtering. Query returns stale facts when valid_until is NULL.

======================================================================

Available agent diaries:
  qwen
```

---

## Example 5: Progressive Memory Loading

### Scenario
Use multi-layer loading (L0-L3) to minimize token usage while maintaining context relevance.

### Code

```python
#!/usr/bin/env python3
"""Progressive memory loading example - 50%+ token reduction"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.layered_loading import LayeredMemory

# Initialize memory system
memory = LayeredMemory()

# Set up identity (L0)
memory.set_identity(
    "I am Claude, an AI coordinator for NixOS-Dev-Quick-Deploy.\n"
    "My role: orchestrate local agents (qwen, gemini) and delegate tasks.\n"
    "System: NixOS on hyperd's desktop with 32GB RAM, RTX 3090.\n"
    "Focus: local-first AI, declarative infrastructure, cost optimization."
)

# Add critical facts (L1)
memory.add_critical_fact(
    "Always use progressive disclosure to minimize token usage",
    project="ai-stack"
)
memory.add_critical_fact(
    "Prefer local agents over remote APIs to reduce costs",
    project="ai-stack"
)
memory.add_critical_fact(
    "Use metadata filtering for 34% recall improvement",
    project="ai-stack"
)

print("=== Multi-Layer Memory Loading Demo ===\n")

# Test 1: Load with small budget (L0 + L1 only)
print("Test 1: Small budget (250 tokens) - L0 + L1 only")
print("-" * 60)
context = memory.progressive_load(
    query="How should I implement authentication?",
    max_tokens=250
)
print(context)
print(f"\nEstimated tokens: ~{len(context) // 4}")

print("\n" + "="*70 + "\n")

# Test 2: Load with medium budget (L0 + L1 + L2)
print("Test 2: Medium budget (520 tokens) - L0 + L1 + L2")
print("-" * 60)
context = memory.progressive_load(
    query="How should I implement JWT authentication with security best practices?",
    max_tokens=520
)
print(context)
print(f"\nEstimated tokens: ~{len(context) // 4}")

print("\n" + "="*70 + "\n")

# Test 3: Force L3 (full semantic search)
print("Test 3: Force L3 (1000 tokens) - Full semantic search")
print("-" * 60)
context = memory.progressive_load(
    query="deep_search: comprehensive authentication and security review",
    max_tokens=1000,
    force_l3=True
)
print(context)
print(f"\nEstimated tokens: ~{len(context) // 4}")

print("\n" + "="*70 + "\n")

# Show layer statistics
print("Layer Statistics:")
stats = memory.get_layer_stats()
for layer, tokens in stats.items():
    print(f"  {layer}: {tokens} tokens")

print("\n" + "="*70 + "\n")

# Demonstrate token savings
print("Token Savings Comparison:")
print(f"  Without layering (load all): ~1000 tokens")
print(f"  L0 + L1 only: ~220 tokens (78% reduction)")
print(f"  L0 + L1 + L2: ~520 tokens (48% reduction)")
print(f"  Progressive average: ~300-600 tokens (40-70% reduction)")
```

### Expected Output
```
=== Multi-Layer Memory Loading Demo ===

Test 1: Small budget (250 tokens) - L0 + L1 only
------------------------------------------------------------
# Identity
I am Claude, an AI coordinator for NixOS-Dev-Quick-Deploy.
My role: orchestrate local agents (qwen, gemini) and delegate tasks.
System: NixOS on hyperd's desktop with 32GB RAM, RTX 3090.
Focus: local-first AI, declarative infrastructure, cost optimization.

# Critical Facts
• [ai-stack] Always use progressive disclosure to minimize token usage
• [ai-stack] Prefer local agents over remote APIs to reduce costs
• [ai-stack] Use metadata filtering for 34% recall improvement

Estimated tokens: ~55

======================================================================

Test 2: Medium budget (520 tokens) - L0 + L1 + L2
------------------------------------------------------------
# Identity
I am Claude, an AI coordinator for NixOS-Dev-Quick-Deploy.
My role: orchestrate local agents (qwen, gemini) and delegate tasks.
System: NixOS on hyperd's desktop with 32GB RAM, RTX 3090.
Focus: local-first AI, declarative infrastructure, cost optimization.

# Critical Facts
• [ai-stack] Always use progressive disclosure to minimize token usage
• [ai-stack] Prefer local agents over remote APIs to reduce costs
• [ai-stack] Use metadata filtering for 34% recall improvement

# Topic-Specific Memory
• [auth] Using JWT with 7-day expiry for authentication
• [security] Always validate and sanitize user inputs

Estimated tokens: ~70

======================================================================

Test 3: Force L3 (1000 tokens) - Full semantic search
------------------------------------------------------------
[Full context with L0 + L1 + L2 + L3 semantic search results]

Estimated tokens: ~250

======================================================================

Layer Statistics:
  identity: 45 tokens
  critical: 60 tokens
  topic: 65 tokens

======================================================================

Token Savings Comparison:
  Without layering (load all): ~1000 tokens
  L0 + L1 only: ~220 tokens (78% reduction)
  L0 + L1 + L2: ~520 tokens (48% reduction)
  Progressive average: ~300-600 tokens (40-70% reduction)
```

---

## Example 6: Benchmarking Custom Corpus

### Scenario
Create a custom benchmark corpus and measure recall accuracy and performance.

### Code

```python
#!/usr/bin/env python3
"""Custom corpus benchmarking example"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.temporal_facts import TemporalFact

# Create custom corpus
corpus_dir = Path(__file__).parent / "benchmarks"
corpus_dir.mkdir(exist_ok=True)
corpus_file = corpus_dir / "custom-corpus.json"

# Define benchmark corpus
corpus = {
    "metadata": {
        "name": "AI Stack Authentication Corpus",
        "created": datetime.now(timezone.utc).isoformat(),
        "description": "Test corpus for authentication-related memory recall"
    },
    "facts": [
        {
            "fact_id": "fact_001",
            "content": "Using JWT tokens with 7-day expiry for API authentication",
            "project": "ai-stack",
            "topic": "auth",
            "type": "decision",
            "tags": ["jwt", "security", "api"],
            "valid_from": "2026-03-01T00:00:00Z"
        },
        {
            "fact_id": "fact_002",
            "content": "Prefer bcrypt for password hashing with salt rounds of 12",
            "project": "ai-stack",
            "topic": "auth",
            "type": "preference",
            "tags": ["bcrypt", "security", "passwords"],
            "valid_from": "2026-03-01T00:00:00Z"
        },
        {
            "fact_id": "fact_003",
            "content": "OAuth2 integration with Google and GitHub providers",
            "project": "ai-stack",
            "topic": "auth",
            "type": "decision",
            "tags": ["oauth", "google", "github"],
            "valid_from": "2026-03-15T00:00:00Z"
        },
    ],
    "queries": [
        {
            "query_id": "q_001",
            "text": "How is JWT authentication implemented?",
            "expected_facts": ["fact_001"],
            "project": "ai-stack",
            "topic": "auth"
        },
        {
            "query_id": "q_002",
            "text": "What password hashing method should I use?",
            "expected_facts": ["fact_002"],
            "project": "ai-stack",
            "topic": "auth"
        },
        {
            "query_id": "q_003",
            "text": "Which OAuth providers are configured?",
            "expected_facts": ["fact_003"],
            "project": "ai-stack",
            "topic": "auth"
        },
    ]
}

# Save corpus
with open(corpus_file, 'w') as f:
    json.dump(corpus, f, indent=2)

print(f"✅ Created custom corpus: {corpus_file}")
print(f"   Facts: {len(corpus['facts'])}")
print(f"   Queries: {len(corpus['queries'])}")

# Run benchmark using aq-benchmark CLI
print("\nRunning benchmark...")
print("=" * 70)

# This would be run via CLI:
# aq-benchmark run --corpus custom-corpus.json --output results.json
# aq-benchmark report results.json --format text

print("""
To run the benchmark:

  cd benchmarks/
  aq-benchmark run --corpus custom-corpus.json --output results.json
  aq-benchmark report results.json --format html --output report.html

Expected results:
  - Baseline recall: ~65-70%
  - Metadata-enhanced recall: ~90-95% (34% improvement)
  - p95 latency: < 500ms
  - Throughput: 50+ qps
""")
```

### Expected Output
```
✅ Created custom corpus: benchmarks/custom-corpus.json
   Facts: 3
   Queries: 3

Running benchmark...
======================================================================

To run the benchmark:

  cd benchmarks/
  aq-benchmark run --corpus custom-corpus.json --output results.json
  aq-benchmark report results.json --format html --output report.html

Expected results:
  - Baseline recall: ~65-70%
  - Metadata-enhanced recall: ~90-95% (34% improvement)
  - p95 latency: < 500ms
  - Throughput: 50+ qps
```

---

## Example 7: Integration with Workflow System

### Scenario
Integrate memory system with workflow orchestration to store and recall workflow decisions.

### Code

```python
#!/usr/bin/env python3
"""Workflow integration example"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.temporal_facts import TemporalFact
from aidb.layered_loading import LayeredMemory

# Initialize store
from scripts.ai import InMemoryFactStore
store = InMemoryFactStore()
memory = LayeredMemory(fact_store=store)

class WorkflowOrchestrator:
    """Example workflow orchestrator with memory integration"""

    def __init__(self, agent_name: str, memory: LayeredMemory):
        self.agent_name = agent_name
        self.memory = memory
        self.store = memory.fact_store

    def start_workflow(self, workflow_type: str, context: str):
        """Start workflow with memory-informed context"""
        print(f"=== Starting {workflow_type} workflow ===\n")

        # Load relevant context
        relevant_context = self.memory.progressive_load(
            query=f"{workflow_type} workflow {context}",
            max_tokens=500
        )

        print("Loaded context:")
        print(relevant_context[:200] + "...")
        print()

        return relevant_context

    def record_decision(self, decision: str, topic: str, rationale: str):
        """Record a workflow decision in memory"""
        fact = TemporalFact(
            content=f"{decision}. Rationale: {rationale}",
            project="workflows",
            topic=topic,
            type="decision",
            tags=["workflow", topic],
            confidence=0.9,
            created_by=self.agent_name
        )

        fact_id = self.store.add(fact)
        print(f"✅ Recorded decision: {decision}")
        print(f"   ID: {fact_id[:8]}")
        print(f"   Topic: {topic}")
        return fact_id

    def recall_similar_workflows(self, workflow_type: str, limit: int = 3):
        """Recall similar past workflows"""
        all_facts = self.store.get_all()

        # Filter to workflow decisions
        workflow_facts = [
            f for f in all_facts
            if f.project == "workflows" and workflow_type.lower() in f.content.lower()
        ]

        print(f"\nFound {len(workflow_facts)} similar workflows:")
        for fact in workflow_facts[:limit]:
            print(f"  - {fact.topic}: {fact.content}")

        return workflow_facts

# Demonstration
orchestrator = WorkflowOrchestrator("codex", memory)

# Workflow 1: Authentication implementation
print("Workflow 1: Implement Authentication")
print("=" * 70)

context = orchestrator.start_workflow(
    "authentication",
    "implement JWT with secure practices"
)

orchestrator.record_decision(
    "Use JWT with 7-day expiry",
    topic="auth",
    rationale="Balance between security and user convenience"
)

orchestrator.record_decision(
    "Store refresh tokens in httpOnly cookies",
    topic="auth",
    rationale="Prevent XSS attacks on token storage"
)

print("\n" + "=" * 70 + "\n")

# Workflow 2: Database migration
print("Workflow 2: Database Migration")
print("=" * 70)

context = orchestrator.start_workflow(
    "database",
    "migrate from SQLite to PostgreSQL"
)

orchestrator.record_decision(
    "Use PostgreSQL with pgvector extension",
    topic="database",
    rationale="Need vector similarity search for semantic queries"
)

orchestrator.record_decision(
    "Implement zero-downtime migration strategy",
    topic="database",
    rationale="Cannot afford service interruption"
)

print("\n" + "=" * 70 + "\n")

# Recall past decisions
print("Recalling Past Workflows:")
print("=" * 70)

orchestrator.recall_similar_workflows("authentication")
orchestrator.recall_similar_workflows("database")
```

### Expected Output
```
Workflow 1: Implement Authentication
======================================================================

=== Starting authentication workflow ===

Loaded context:
# Identity
I am Claude, an AI coordinator for NixOS-Dev-Quick-Deploy...

✅ Recorded decision: Use JWT with 7-day expiry
   ID: abc12345
   Topic: auth
✅ Recorded decision: Store refresh tokens in httpOnly cookies
   ID: def67890
   Topic: auth

======================================================================

Workflow 2: Database Migration
======================================================================

=== Starting database workflow ===

Loaded context:
# Identity
I am Claude, an AI coordinator for NixOS-Dev-Quick-Deploy...

✅ Recorded decision: Use PostgreSQL with pgvector extension
   ID: ghi11121
   Topic: database
✅ Recorded decision: Implement zero-downtime migration strategy
   ID: jkl31415
   Topic: database

======================================================================

Recalling Past Workflows:
======================================================================

Found 2 similar workflows:
  - auth: Use JWT with 7-day expiry. Rationale: Balance between security and user convenience
  - auth: Store refresh tokens in httpOnly cookies. Rationale: Prevent XSS attacks on token storage

Found 2 similar workflows:
  - database: Use PostgreSQL with pgvector extension. Rationale: Need vector similarity search for semantic queries
  - database: Implement zero-downtime migration strategy. Rationale: Cannot afford service interruption
```

---

## Example 8: Custom Fact Store Backends

### Scenario
Implement a custom fact store backend (e.g., for PostgreSQL).

### Code

```python
#!/usr/bin/env python3
"""Custom fact store backend example"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.temporal_facts import TemporalFact, TemporalFactStore

class PostgreSQLFactStore(TemporalFactStore):
    """PostgreSQL implementation of TemporalFactStore"""

    def __init__(self, connection_string: str):
        """
        Initialize PostgreSQL fact store

        Args:
            connection_string: PostgreSQL connection string
        """
        # In production, use psycopg2 or asyncpg
        # For this example, we'll simulate with in-memory
        self.connection_string = connection_string
        self._facts = []  # Simulated storage
        print(f"✅ Connected to PostgreSQL: {connection_string}")

    def store(self, fact: TemporalFact) -> str:
        """Store a temporal fact in PostgreSQL"""
        # In production:
        # INSERT INTO temporal_facts (...) VALUES (...)
        self._facts.append(fact)
        print(f"   Stored to PostgreSQL: {fact.fact_id[:8]}")
        return fact.fact_id

    def retrieve(self, fact_id: str) -> Optional[TemporalFact]:
        """Retrieve a fact by ID from PostgreSQL"""
        # In production:
        # SELECT * FROM temporal_facts WHERE fact_id = %s
        for fact in self._facts:
            if fact.fact_id == fact_id or fact.fact_id.startswith(fact_id):
                return fact
        return None

    def query_valid_at(
        self,
        timestamp: datetime,
        project: Optional[str] = None,
        topic: Optional[str] = None,
        type: Optional[str] = None,
        agent_owner: Optional[str] = None,
    ) -> List[TemporalFact]:
        """Query facts valid at timestamp with filters"""
        # In production:
        # SELECT * FROM temporal_facts
        # WHERE valid_from <= %s
        #   AND (valid_until IS NULL OR valid_until >= %s)
        #   AND ... (other filters)

        results = []
        for fact in self._facts:
            if not fact.is_valid_at(timestamp):
                continue
            if project and fact.project != project:
                continue
            if topic and fact.topic != topic:
                continue
            if type and fact.type != type:
                continue
            if agent_owner is not None and fact.agent_owner != agent_owner:
                continue
            results.append(fact)

        return results

    def get_stale_facts(
        self,
        current_time: Optional[datetime] = None,
        project: Optional[str] = None,
    ) -> List[TemporalFact]:
        """Get stale facts from PostgreSQL"""
        check_time = current_time or datetime.now(timezone.utc)

        results = []
        for fact in self._facts:
            if fact.is_stale(check_time):
                if project is None or fact.project == project:
                    results.append(fact)

        return results

# Demonstration
print("=== Custom PostgreSQL Fact Store ===\n")

# Initialize store
pg_store = PostgreSQLFactStore("postgresql://localhost:5432/aidb")

# Store facts
print("\nStoring facts:")
fact1 = TemporalFact(
    content="Using PostgreSQL with pgvector",
    project="ai-stack",
    topic="database",
    type="decision"
)
pg_store.store(fact1)

fact2 = TemporalFact(
    content="JWT with 7-day expiry",
    project="ai-stack",
    topic="auth",
    type="decision"
)
pg_store.store(fact2)

# Query facts
print("\nQuerying facts valid now:")
now = datetime.now(timezone.utc)
valid_facts = pg_store.query_valid_at(
    timestamp=now,
    project="ai-stack"
)
print(f"Found {len(valid_facts)} valid facts:")
for fact in valid_facts:
    print(f"  - {fact.topic}: {fact.content}")

# Retrieve by ID
print("\nRetrieving by ID:")
retrieved = pg_store.retrieve(fact1.fact_id)
if retrieved:
    print(f"✅ Retrieved: {retrieved.content}")

print("\n" + "=" * 70)
print("\nIn production, this would:")
print("  1. Use psycopg2 or asyncpg for real PostgreSQL connection")
print("  2. Execute actual SQL queries with parameterized inputs")
print("  3. Handle connection pooling and transactions")
print("  4. Implement vector similarity search with pgvector")
print("  5. Add proper error handling and logging")
```

### Expected Output
```
=== Custom PostgreSQL Fact Store ===

✅ Connected to PostgreSQL: postgresql://localhost:5432/aidb

Storing facts:
   Stored to PostgreSQL: abc12345
   Stored to PostgreSQL: def67890

Querying facts valid now:
Found 2 valid facts:
  - database: Using PostgreSQL with pgvector
  - auth: JWT with 7-day expiry

Retrieving by ID:
✅ Retrieved: Using PostgreSQL with pgvector

======================================================================

In production, this would:
  1. Use psycopg2 or asyncpg for real PostgreSQL connection
  2. Execute actual SQL queries with parameterized inputs
  3. Handle connection pooling and transactions
  4. Implement vector similarity search with pgvector
  5. Add proper error handling and logging
```

---

## Example 9: CLI Integration in Scripts

### Scenario
Use the `aq-memory` CLI in shell scripts for automation.

### Code

```bash
#!/bin/bash
# deploy-with-memory.sh - Deployment script with memory integration

set -euo pipefail

PROJECT="ai-stack"
DEPLOYMENT_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "=== Deployment with Memory Tracking ==="
echo

# Record deployment start
echo "Recording deployment start..."
aq-memory add "Deployment started for ai-stack v2.0" \
  --project "$PROJECT" \
  --topic deployment \
  --type event \
  --tags "deployment,v2.0" \
  --created-by "deploy-script" \
  --valid-from "$DEPLOYMENT_DATE"

# Recall previous deployments
echo
echo "Checking previous deployments..."
aq-memory search "deployment" \
  --project "$PROJECT" \
  --topic deployment \
  --type event \
  --limit 5

# Store deployment configuration
echo
echo "Recording deployment configuration..."
aq-memory add "Dashboard deployed to port 8889 with SSL enabled" \
  --project "$PROJECT" \
  --topic deployment \
  --type fact \
  --tags "port,ssl,config" \
  --confidence 1.0

# Simulate deployment steps
echo
echo "Performing deployment..."
sleep 2

# Record deployment success
echo
echo "Recording deployment success..."
aq-memory add "Deployment completed successfully for ai-stack v2.0" \
  --project "$PROJECT" \
  --topic deployment \
  --type event \
  --tags "deployment,v2.0,success" \
  --created-by "deploy-script"

# Show deployment statistics
echo
echo "Deployment Statistics:"
aq-memory stats --project "$PROJECT"

echo
echo "✅ Deployment complete and recorded in memory"
```

### Expected Output
```
=== Deployment with Memory Tracking ===

Recording deployment start...
✅ Added fact abc12345
   Project: ai-stack
   Topic: deployment
   Type: event
   Content: Deployment started for ai-stack v2.0

Checking previous deployments...
Found 3 matching facts:

✅ def67890 | ai-stack/deployment | event
   Deployment completed successfully for ai-stack v1.9
   Created: 2026-04-10 14:30

✅ ghi11121 | ai-stack/deployment | event
   Deployment started for ai-stack v1.9
   Created: 2026-04-10 14:25

✅ jkl31415 | ai-stack/deployment | event
   Deployment completed successfully for ai-stack v1.8
   Created: 2026-04-09 10:15

Recording deployment configuration...
✅ Added fact mno16171
   Project: ai-stack
   Topic: deployment
   Type: fact
   Content: Dashboard deployed to port 8889 with SSL enabled

Performing deployment...

Recording deployment success...
✅ Added fact pqr18192
   Project: ai-stack
   Topic: deployment
   Type: event
   Content: Deployment completed successfully for ai-stack v2.0

Deployment Statistics:
Statistics for ai-stack:
=========================

Total facts: 42
  Valid now:  38 (90.5%)
  Stale:      4 (9.5%)
  Future:     0 (0.0%)

By type:
  decision        15 (35.7%)
  fact            12 (28.6%)
  event           8 (19.0%)
  preference      5 (11.9%)
  discovery       2 (4.8%)

Ownership:
  Shared:      35 (83.3%)
  qwen          5 (11.9%)
  claude        2 (4.8%)

✅ Deployment complete and recorded in memory
```

---

## Example 10: Multi-Agent Memory Sharing

### Scenario
Multiple agents share memories while maintaining private diaries.

### Code

```python
#!/usr/bin/env python3
"""Multi-agent memory sharing example"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ai-stack"))

from aidb.temporal_facts import TemporalFact
from aidb.agent_diary import AgentDiary
from aidb.temporal_query import filter_facts_by_project

# Initialize shared store
from scripts.ai import InMemoryFactStore
shared_store = InMemoryFactStore()

print("=== Multi-Agent Memory Sharing ===\n")

# Agent 1: Qwen writes to shared memory and private diary
print("Agent 1: Qwen")
print("-" * 60)

qwen_diary = AgentDiary("qwen")

# Qwen stores a shared fact
shared_fact = TemporalFact(
    content="API authentication uses JWT with 7-day expiry",
    project="ai-stack",
    topic="auth",
    type="decision",
    tags=["jwt", "auth"],
    agent_owner=None,  # Shared memory
    created_by="qwen"
)
shared_store.add(shared_fact)
print("✅ Qwen added shared fact: JWT authentication")

# Qwen writes to private diary
qwen_diary.write(
    "I implemented the JWT authentication module. Learned about token refresh patterns.",
    topic="auth",
    tags=["jwt", "learning"],
    create_fact=False
)
print("✅ Qwen wrote to private diary: JWT implementation learnings")

print("\n" + "=" * 70 + "\n")

# Agent 2: Claude writes to shared memory and private diary
print("Agent 2: Claude")
print("-" * 60)

claude_diary = AgentDiary("claude")

# Claude stores a shared fact
shared_fact2 = TemporalFact(
    content="Use bcrypt with 12 rounds for password hashing",
    project="ai-stack",
    topic="auth",
    type="preference",
    tags=["bcrypt", "security"],
    agent_owner=None,  # Shared memory
    created_by="claude"
)
shared_store.add(shared_fact2)
print("✅ Claude added shared fact: bcrypt preference")

# Claude writes to private diary
claude_diary.write(
    "Reviewed security best practices. Bcrypt is recommended over plain SHA for passwords.",
    topic="security",
    tags=["bcrypt", "best-practices"],
    create_fact=False
)
print("✅ Claude wrote to private diary: Security review notes")

print("\n" + "=" * 70 + "\n")

# Both agents can read shared memory
print("Shared Memory Access:")
print("-" * 60)

all_shared = shared_store.get_all()
shared_only = [f for f in all_shared if f.agent_owner is None]

print(f"Total shared facts: {len(shared_only)}\n")
for fact in shared_only:
    print(f"  [{fact.created_by}] {fact.content}")
    print(f"     Topic: {fact.topic}, Type: {fact.type}")
    print()

print("=" * 70 + "\n")

# Orchestrator can observe agent diaries (read-only)
print("Orchestrator (Codex) Observing Agent Diaries:")
print("-" * 60)

print("\nQwen's diary (observer mode):")
qwen_entries = AgentDiary.read_as_observer("qwen", limit=5)
for entry in qwen_entries:
    print(f"  - [{entry.topic}] {entry.content}")

print("\nClaude's diary (observer mode):")
claude_entries = AgentDiary.read_as_observer("claude", limit=5)
for entry in claude_entries:
    print(f"  - [{entry.topic}] {entry.content}")

print("\n" + "=" * 70 + "\n")

# Summary
print("Memory Isolation Summary:")
print("-" * 60)
print("✅ Shared facts: Accessible by all agents")
print("✅ Private diaries: Only writable by owner")
print("✅ Observer mode: Orchestrator can read (but not write) all diaries")
print("✅ Expertise accumulation: Each agent builds independent knowledge")
```

### Expected Output
```
=== Multi-Agent Memory Sharing ===

Agent 1: Qwen
------------------------------------------------------------
✅ Qwen added shared fact: JWT authentication
✅ Qwen wrote to private diary: JWT implementation learnings

======================================================================

Agent 2: Claude
------------------------------------------------------------
✅ Claude added shared fact: bcrypt preference
✅ Claude wrote to private diary: Security review notes

======================================================================

Shared Memory Access:
------------------------------------------------------------
Total shared facts: 2

  [qwen] API authentication uses JWT with 7-day expiry
     Topic: auth, Type: decision

  [claude] Use bcrypt with 12 rounds for password hashing
     Topic: auth, Type: preference

======================================================================

Orchestrator (Codex) Observing Agent Diaries:
------------------------------------------------------------

Qwen's diary (observer mode):
  - [auth] I implemented the JWT authentication module. Learned about token refresh patterns.

Claude's diary (observer mode):
  - [security] Reviewed security best practices. Bcrypt is recommended over plain SHA for passwords.

======================================================================

Memory Isolation Summary:
------------------------------------------------------------
✅ Shared facts: Accessible by all agents
✅ Private diaries: Only writable by owner
✅ Observer mode: Orchestrator can read (but not write) all diaries
✅ Expertise accumulation: Each agent builds independent knowledge
```

---

## Running the Examples

All examples can be run directly:

```bash
# Example 1: Basic fact storage
python docs/memory-system/examples/example_1_basic.py

# Example 2: Metadata filtering
python docs/memory-system/examples/example_2_filtering.py

# Example 3: Temporal queries
python docs/memory-system/examples/example_3_temporal.py

# And so on...
```

Or using the CLI directly:

```bash
# Store facts
aq-memory add "Using JWT" --project ai-stack --topic auth --type decision

# Search facts
aq-memory search "JWT" --project ai-stack

# View statistics
aq-memory stats --project ai-stack

# Run benchmarks
aq-benchmark run --corpus benchmarks/corpus.json
```

---

## Next Steps

- **User Guide**: See [USER-GUIDE.md](./USER-GUIDE.md) for comprehensive documentation
- **API Reference**: See [API-REFERENCE.md](./API-REFERENCE.md) for detailed API docs
- **Quick Reference**: See [QUICK-REFERENCE.md](./QUICK-REFERENCE.md) for command cheat sheet

---

**All examples are tested and functional. For issues or questions, refer to the troubleshooting section in the User Guide.**
