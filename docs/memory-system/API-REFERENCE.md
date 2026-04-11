# Memory System API Reference

**Version:** 1.0.0
**Last Updated:** 2026-04-11

---

## Table of Contents

- [Core Modules](#core-modules)
  - [temporal_facts.py](#temporal_factspy)
  - [temporal_query.py](#temporal_querypy)
  - [layered_loading.py](#layered_loadingpy)
  - [agent_diary.py](#agent_diarypy)
- [CLI Tools](#cli-tools)
  - [aq-memory](#aq-memory)
  - [aq-benchmark](#aq-benchmark)

---

## Core Modules

### temporal_facts.py

Module for temporal fact data structures and operations.

#### TemporalFact

A memory fact with temporal validity.

**Constructor:**
```python
TemporalFact(
    content: str,
    project: str,
    topic: Optional[str] = None,
    type: str = "fact",
    valid_from: datetime = <now>,
    valid_until: Optional[datetime] = None,
    agent_owner: Optional[str] = None,
    tags: List[str] = [],
    confidence: float = 1.0,
    source: Optional[str] = None,
    embedding_vector: Optional[List[float]] = None,
    fact_id: Optional[str] = None,
    created_at: datetime = <now>,
    created_by: Optional[str] = None,
    updated_at: datetime = <now>,
    updated_by: Optional[str] = None,
    version: int = 1
)
```

**Parameters:**
- `content` (str): The fact text (required)
- `project` (str): Top-level category (required)
- `topic` (str, optional): Subcategory
- `type` (str): One of: decision, preference, discovery, event, advice, fact (default: "fact")
- `valid_from` (datetime): When fact became valid (default: now)
- `valid_until` (datetime, optional): When fact expires (None = ongoing)
- `agent_owner` (str, optional): Agent that owns this fact (None = shared)
- `tags` (List[str]): Additional categorization tags
- `confidence` (float): Confidence score 0.0-1.0 (default: 1.0)
- `source` (str, optional): Source of this fact
- `embedding_vector` (List[float], optional): 1536-dim embedding for semantic search
- `fact_id` (str, optional): Unique identifier (auto-generated if not provided)
- `created_at` (datetime): Creation timestamp (default: now)
- `created_by` (str, optional): Creator identifier
- `updated_at` (datetime): Last update timestamp (default: now)
- `updated_by` (str, optional): Last updater identifier
- `version` (int): Version number (default: 1)

**Raises:**
- `ValueError`: If type is invalid, confidence out of range, or temporal inconsistency

**Example:**
```python
from aidb.temporal_facts import TemporalFact
from datetime import datetime, timezone

fact = TemporalFact(
    content="Using JWT with 7-day expiry",
    project="ai-stack",
    topic="auth",
    type="decision",
    tags=["security", "jwt"],
    confidence=0.95
)
```

**Methods:**

##### is_valid_at(timestamp: datetime) -> bool

Check if fact is valid at given timestamp.

**Parameters:**
- `timestamp` (datetime): The time to check validity

**Returns:**
- bool: True if fact is valid at timestamp, False otherwise

**Example:**
```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
is_valid = fact.is_valid_at(now)
```

##### is_stale(current_time: Optional[datetime] = None) -> bool

Check if fact should be updated (past valid_until).

**Parameters:**
- `current_time` (datetime, optional): Time to check against (default: now)

**Returns:**
- bool: True if fact is stale, False if still valid or ongoing

**Example:**
```python
if fact.is_stale():
    print("This fact needs updating")
```

##### is_ongoing() -> bool

Check if fact has indefinite validity (no end date).

**Returns:**
- bool: True if valid_until is None, False otherwise

**Example:**
```python
if fact.is_ongoing():
    print("This fact has no expiration")
```

##### expire(until: datetime, reason: Optional[str] = None)

Mark fact as no longer valid after given timestamp.

**Parameters:**
- `until` (datetime): When fact should expire
- `reason` (str, optional): Explanation for expiration

**Raises:**
- `ValueError`: If until is before valid_from

**Example:**
```python
from datetime import datetime, timezone

expiry = datetime(2026, 12, 31, tzinfo=timezone.utc)
fact.expire(until=expiry, reason="superseded")
```

##### to_dict() -> Dict[str, Any]

Convert to dictionary for storage.

**Returns:**
- dict: Dictionary representation of the fact

**Example:**
```python
fact_dict = fact.to_dict()
# Save to JSON or database
```

##### from_dict(data: Dict[str, Any]) -> TemporalFact (classmethod)

Create TemporalFact from dictionary.

**Parameters:**
- `data` (dict): Dictionary with fact data

**Returns:**
- TemporalFact: Reconstructed fact object

**Example:**
```python
fact_dict = {
    "content": "Using JWT",
    "project": "ai-stack",
    "valid_from": "2026-04-11T00:00:00Z",
    # ... other fields
}
fact = TemporalFact.from_dict(fact_dict)
```

**Properties:**

##### content_hash -> str

Get content hash for deduplication.

**Returns:**
- str: SHA256 hash of content

---

#### Helper Functions

##### get_valid_facts(facts: List[TemporalFact], at_time: Optional[datetime] = None) -> List[TemporalFact]

Filter facts to only those valid at given time.

**Parameters:**
- `facts` (List[TemporalFact]): List of facts to filter
- `at_time` (datetime, optional): Time to check (default: now)

**Returns:**
- List[TemporalFact]: Filtered list of valid facts

**Example:**
```python
from aidb.temporal_facts import get_valid_facts
from datetime import datetime, timezone

all_facts = store.get_all()
now = datetime.now(timezone.utc)
valid_facts = get_valid_facts(all_facts, at_time=now)
```

##### get_stale_facts(facts: List[TemporalFact], current_time: Optional[datetime] = None) -> List[TemporalFact]

Filter facts to only those that are stale.

**Parameters:**
- `facts` (List[TemporalFact]): List of facts to filter
- `current_time` (datetime, optional): Time to check (default: now)

**Returns:**
- List[TemporalFact]: Filtered list of stale facts

**Example:**
```python
from aidb.temporal_facts import get_stale_facts

stale = get_stale_facts(all_facts)
print(f"Found {len(stale)} stale facts")
```

---

### temporal_query.py

Database query interface for temporal facts with metadata filtering.

#### TemporalQueryAPI

Query interface for temporal facts database (abstract base class).

**Constructor:**
```python
TemporalQueryAPI(connection=None)
```

**Parameters:**
- `connection`: Database connection object (implementation-specific)

**Methods:**

##### query_valid_at(timestamp: Optional[datetime] = None, project: Optional[str] = None, topic: Optional[str] = None, fact_type: Optional[str] = None, agent_owner: Optional[str] = None, tags: Optional[List[str]] = None, limit: int = 100) -> List[TemporalFact]

Query facts that are valid at a specific timestamp.

**Parameters:**
- `timestamp` (datetime, optional): Time to check (default: now)
- `project` (str, optional): Filter by project
- `topic` (str, optional): Filter by topic
- `fact_type` (str, optional): Filter by type
- `agent_owner` (str, optional): Filter by agent owner
- `tags` (List[str], optional): Filter by tags (must contain all)
- `limit` (int): Maximum results (default: 100)

**Returns:**
- List[TemporalFact]: List of valid facts

**Example:**
```python
from aidb.temporal_query import TemporalQueryAPI

api = TemporalQueryAPI(connection)
facts = api.query_valid_at(
    project="ai-stack",
    fact_type="decision",
    limit=50
)
```

##### query_by_timerange(start_time: datetime, end_time: datetime, project: Optional[str] = None, topic: Optional[str] = None, fact_type: Optional[str] = None, limit: int = 100) -> List[TemporalFact]

Query facts that overlap with a time range.

**Parameters:**
- `start_time` (datetime): Start of query range
- `end_time` (datetime): End of query range
- `project` (str, optional): Filter by project
- `topic` (str, optional): Filter by topic
- `fact_type` (str, optional): Filter by type
- `limit` (int): Maximum results (default: 100)

**Returns:**
- List[TemporalFact]: Facts with overlapping validity

**Raises:**
- `ValueError`: If end_time < start_time

**Example:**
```python
from datetime import datetime, timezone

march_start = datetime(2026, 3, 1, tzinfo=timezone.utc)
march_end = datetime(2026, 3, 31, tzinfo=timezone.utc)

facts = api.query_by_timerange(
    start_time=march_start,
    end_time=march_end,
    project="ai-stack"
)
```

##### get_stale_facts(current_time: Optional[datetime] = None, project: Optional[str] = None, topic: Optional[str] = None, limit: int = 100) -> List[TemporalFact]

Get facts that are past their valid_until date.

**Parameters:**
- `current_time` (datetime, optional): Time to check (default: now)
- `project` (str, optional): Filter by project
- `topic` (str, optional): Filter by topic
- `limit` (int): Maximum results (default: 100)

**Returns:**
- List[TemporalFact]: List of stale facts

**Example:**
```python
stale = api.get_stale_facts(project="ai-stack")
```

##### semantic_search(query_text: Optional[str] = None, query_embedding: Optional[List[float]] = None, project: Optional[str] = None, topic: Optional[str] = None, fact_type: Optional[str] = None, valid_at: Optional[datetime] = None, agent_owner: Optional[str] = None, limit: int = 10, min_confidence: float = 0.0) -> List[Dict[str, Any]]

Semantic search with vector similarity and metadata filtering.

**Parameters:**
- `query_text` (str, optional): Text query for embedding
- `query_embedding` (List[float], optional): Pre-computed embedding (1536 dims)
- `project` (str, optional): Filter by project
- `topic` (str, optional): Filter by topic
- `fact_type` (str, optional): Filter by type
- `valid_at` (datetime, optional): Only return facts valid at this time
- `agent_owner` (str, optional): Filter by agent owner
- `limit` (int): Maximum results (default: 10)
- `min_confidence` (float): Minimum confidence score (default: 0.0)

**Returns:**
- List[Dict]: List of dicts with 'fact' (TemporalFact) and 'similarity' (float)

**Raises:**
- `ValueError`: If neither query_embedding nor query_text provided

**Example:**
```python
results = api.semantic_search(
    query_text="JWT token authentication",
    project="ai-stack",
    fact_type="decision",
    limit=5
)
for result in results:
    print(f"{result['similarity']:.3f}: {result['fact'].content}")
```

##### get_agent_diary(agent_name: str, valid_at: Optional[datetime] = None, topic: Optional[str] = None, fact_type: Optional[str] = None, limit: int = 100) -> List[TemporalFact]

Get facts from a specific agent's private diary.

**Parameters:**
- `agent_name` (str): Agent identifier (qwen, codex, claude, gemini)
- `valid_at` (datetime, optional): Time to check (default: now)
- `topic` (str, optional): Filter by topic
- `fact_type` (str, optional): Filter by type
- `limit` (int): Maximum results (default: 100)

**Returns:**
- List[TemporalFact]: List of agent-owned facts

**Example:**
```python
qwen_facts = api.get_agent_diary(
    agent_name="qwen",
    fact_type="discovery",
    limit=20
)
```

##### store_fact(fact: TemporalFact) -> str

Store a new temporal fact.

**Parameters:**
- `fact` (TemporalFact): Fact to store

**Returns:**
- str: The fact_id of stored fact

**Raises:**
- `NotImplementedError`: Must be implemented by subclass

##### expire_fact(fact_id: str, until: datetime, reason: Optional[str] = None, updated_by: Optional[str] = None) -> bool

Mark a fact as expired.

**Parameters:**
- `fact_id` (str): ID of fact to expire
- `until` (datetime): When fact should expire
- `reason` (str, optional): Explanation
- `updated_by` (str, optional): Agent/user making the change

**Returns:**
- bool: True if expired successfully

**Example:**
```python
api.expire_fact(
    fact_id="abc123",
    until=datetime.now(timezone.utc),
    reason="superseded",
    updated_by="claude"
)
```

#### Filter Helper Functions

##### filter_facts_by_project(facts: List[TemporalFact], project: str) -> List[TemporalFact]

Filter facts to specific project.

**Parameters:**
- `facts` (List[TemporalFact]): Facts to filter
- `project` (str): Project name

**Returns:**
- List[TemporalFact]: Filtered facts

**Example:**
```python
from aidb.temporal_query import filter_facts_by_project

ai_facts = filter_facts_by_project(all_facts, "ai-stack")
```

##### filter_facts_by_topic(facts: List[TemporalFact], topic: str) -> List[TemporalFact]

Filter facts to specific topic.

##### filter_facts_by_type(facts: List[TemporalFact], fact_type: str) -> List[TemporalFact]

Filter facts to specific type.

##### filter_facts_by_tags(facts: List[TemporalFact], tags: List[str], match_all: bool = True) -> List[TemporalFact]

Filter facts by tags.

**Parameters:**
- `facts` (List[TemporalFact]): Facts to filter
- `tags` (List[str]): Tags to match
- `match_all` (bool): If True, fact must have all tags; if False, any tag (default: True)

**Returns:**
- List[TemporalFact]: Filtered facts

**Example:**
```python
from aidb.temporal_query import filter_facts_by_tags

# Must have both tags
security_facts = filter_facts_by_tags(facts, ["security", "jwt"], match_all=True)

# Must have at least one tag
auth_facts = filter_facts_by_tags(facts, ["auth", "security"], match_all=False)
```

##### filter_facts_by_confidence(facts: List[TemporalFact], min_confidence: float = 0.0, max_confidence: float = 1.0) -> List[TemporalFact]

Filter facts by confidence score range.

**Parameters:**
- `facts` (List[TemporalFact]): Facts to filter
- `min_confidence` (float): Minimum confidence (default: 0.0)
- `max_confidence` (float): Maximum confidence (default: 1.0)

**Returns:**
- List[TemporalFact]: Filtered facts

**Example:**
```python
from aidb.temporal_query import filter_facts_by_confidence

# Only high-confidence facts
verified = filter_facts_by_confidence(facts, min_confidence=0.9)
```

---

### layered_loading.py

Multi-layer memory loading system with progressive disclosure.

#### LayeredMemory

Multi-layer memory loading with L0-L3 strategy.

**Constructor:**
```python
LayeredMemory(
    identity_file: str = "~/.aidb/identity.txt",
    critical_facts_file: str = "~/.aidb/critical_facts.json",
    fact_store=None
)
```

**Parameters:**
- `identity_file` (str): Path to identity text file (L0)
- `critical_facts_file` (str): Path to critical facts JSON (L1)
- `fact_store`: Optional fact store for L2/L3 queries

**Example:**
```python
from aidb.layered_loading import LayeredMemory

memory = LayeredMemory(fact_store=store)
```

**Methods:**

##### load_l0() -> str

Load L0: Identity layer (50 tokens).

**Returns:**
- str: Identity text (50 tokens max)

**Example:**
```python
identity = memory.load_l0()
print(identity)
```

##### load_l1() -> str

Load L1: Critical facts layer (170 tokens).

**Returns:**
- str: Critical facts formatted as text (170 tokens max)

**Example:**
```python
critical = memory.load_l1()
```

##### load_l2(topic: Optional[str] = None, topics: Optional[List[str]] = None) -> str

Load L2: Topic-specific memories (variable tokens).

**Parameters:**
- `topic` (str, optional): Single topic to load
- `topics` (List[str], optional): List of topics to load

**Returns:**
- str: Topic-specific facts formatted as text

**Example:**
```python
auth_context = memory.load_l2(topic="auth")

# Multiple topics
context = memory.load_l2(topics=["auth", "security"])
```

##### load_l3(query: str, limit: int = 10) -> str

Load L3: Full semantic search (heavy).

**Parameters:**
- `query` (str): Search query
- `limit` (int): Maximum results (default: 10)

**Returns:**
- str: Search results formatted as text

**Example:**
```python
results = memory.load_l3("JWT authentication implementation", limit=5)
```

##### progressive_load(query: str, max_tokens: int = 500, force_l3: bool = False) -> str

Load layers progressively until token budget is reached.

**Parameters:**
- `query` (str): User query to determine relevant context
- `max_tokens` (int): Maximum token budget (default: 500)
- `force_l3` (bool): Force full semantic search even if budget is tight (default: False)

**Returns:**
- str: Combined context from multiple layers

**Example:**
```python
context = memory.progressive_load(
    query="How to implement JWT authentication?",
    max_tokens=500
)
```

##### clear_cache()

Clear the layer cache.

**Example:**
```python
memory.clear_cache()
```

##### set_identity(identity_text: str)

Set and save identity text.

**Parameters:**
- `identity_text` (str): New identity text (will be truncated to 50 tokens)

**Example:**
```python
memory.set_identity(
    "I am Claude, an AI coordinator for NixOS-Dev-Quick-Deploy.\n"
    "My role: orchestrate local agents and delegate tasks."
)
```

##### add_critical_fact(content: str, project: str = "general")

Add a fact to the critical facts list.

**Parameters:**
- `content` (str): Fact content
- `project` (str): Project name (default: "general")

**Example:**
```python
memory.add_critical_fact(
    "Always use progressive disclosure to minimize tokens",
    project="ai-stack"
)
```

##### get_layer_stats() -> Dict[str, int]

Get statistics about loaded layers.

**Returns:**
- Dict[str, int]: Dictionary with token counts per layer

**Example:**
```python
stats = memory.get_layer_stats()
# {"identity": 45, "critical": 160, "topic": 250}
```

#### Convenience Function

##### load_memory_with_budget(query: str, max_tokens: int = 500, fact_store=None) -> str

Quick helper to load memory with progressive disclosure.

**Parameters:**
- `query` (str): User query
- `max_tokens` (int): Token budget (default: 500)
- `fact_store`: Optional fact store

**Returns:**
- str: Formatted memory context

**Example:**
```python
from aidb.layered_loading import load_memory_with_budget

context = load_memory_with_budget(
    "implement authentication",
    max_tokens=400
)
```

---

### agent_diary.py

Agent-specific memory diaries for expertise accumulation.

#### AgentDiary

Private memory diary for an AI agent.

**Constructor:**
```python
AgentDiary(
    agent_name: str,
    diary_dir: str = "~/.aidb/diaries",
    fact_store=None
)
```

**Parameters:**
- `agent_name` (str): Name of agent (qwen, codex, claude, gemini, remote)
- `diary_dir` (str): Directory for diary files (default: "~/.aidb/diaries")
- `fact_store`: Optional fact store for creating TemporalFacts

**Raises:**
- `ValueError`: If agent_name is invalid

**Example:**
```python
from aidb.agent_diary import AgentDiary

diary = AgentDiary("qwen")
```

**Methods:**

##### write(content: str, topic: str = "general", tags: Optional[List[str]] = None, create_fact: bool = True) -> str

Write entry to agent's diary.

**Parameters:**
- `content` (str): Entry content
- `topic` (str): Topic category (default: "general")
- `tags` (List[str], optional): Optional tags
- `create_fact` (bool): Whether to also create a TemporalFact (default: True)

**Returns:**
- str: Entry ID

**Example:**
```python
entry_id = diary.write(
    "Implemented JWT validation with bcrypt hashing",
    topic="auth",
    tags=["jwt", "security"]
)
```

##### read(topic: Optional[str] = None, since_days: Optional[int] = None, tags: Optional[List[str]] = None, limit: int = 50) -> List[DiaryEntry]

Read from agent's diary with filters.

**Parameters:**
- `topic` (str, optional): Filter by topic
- `since_days` (int, optional): Only entries from last N days
- `tags` (List[str], optional): Filter by tags (match any)
- `limit` (int): Maximum entries (default: 50)

**Returns:**
- List[DiaryEntry]: List of diary entries

**Example:**
```python
# Recent entries
recent = diary.read(limit=20)

# Topic-specific
auth_entries = diary.read(topic="auth", since_days=7)

# Tagged entries
jwt_entries = diary.read(tags=["jwt", "security"])
```

##### search(query: str, limit: int = 20) -> List[DiaryEntry]

Search diary entries.

**Parameters:**
- `query` (str): Search query
- `limit` (int): Maximum results (default: 20)

**Returns:**
- List[DiaryEntry]: Matching entries

**Example:**
```python
results = diary.search("JWT implementation")
```

##### get_topics() -> Set[str]

Get all topics in this agent's diary.

**Returns:**
- Set[str]: Set of topic names

**Example:**
```python
topics = diary.get_topics()
print(f"Topics: {', '.join(topics)}")
```

##### get_tags() -> Set[str]

Get all tags in this agent's diary.

**Returns:**
- Set[str]: Set of tags

##### get_stats() -> dict

Get statistics about this diary.

**Returns:**
- dict: Dictionary with stats (total_entries, topics, tags, oldest_entry, newest_entry)

**Example:**
```python
stats = diary.get_stats()
print(f"Total entries: {stats['total_entries']}")
```

**Class Methods:**

##### read_as_observer(agent_name: str, topic: Optional[str] = None, limit: int = 20, diary_dir: str = "~/.aidb/diaries") -> List[DiaryEntry] (classmethod)

Read another agent's diary (observer mode - read-only).

**Parameters:**
- `agent_name` (str): Agent whose diary to read
- `topic` (str, optional): Filter by topic
- `limit` (int): Maximum entries (default: 20)
- `diary_dir` (str): Directory containing diaries

**Returns:**
- List[DiaryEntry]: List of diary entries

**Example:**
```python
# Orchestrator reading qwen's diary
qwen_work = AgentDiary.read_as_observer("qwen", topic="auth", limit=10)
```

##### list_all_diaries(diary_dir: str = "~/.aidb/diaries") -> List[str] (classmethod)

List all available agent diaries.

**Parameters:**
- `diary_dir` (str): Directory containing diaries

**Returns:**
- List[str]: List of agent names with diaries

**Example:**
```python
agents = AgentDiary.list_all_diaries()
print(f"Available diaries: {agents}")
```

#### DiaryEntry

A single diary entry from an agent.

**Attributes:**
- `entry_id` (str): Unique entry ID
- `agent` (str): Agent name
- `content` (str): Entry content
- `topic` (str): Topic
- `tags` (List[str]): Tags
- `timestamp` (str): ISO timestamp
- `fact_id` (str, optional): Link to corresponding TemporalFact

**Methods:**

##### to_dict() -> dict

Convert to dictionary.

##### from_dict(data: dict) -> DiaryEntry (classmethod)

Create from dictionary.

#### Helper Function

##### format_diary_entries(entries: List[DiaryEntry]) -> str

Format diary entries as readable text.

**Parameters:**
- `entries` (List[DiaryEntry]): List of diary entries

**Returns:**
- str: Formatted text

**Example:**
```python
from aidb.agent_diary import format_diary_entries

entries = diary.read(limit=10)
print(format_diary_entries(entries))
```

---

## CLI Tools

### aq-memory

Command-line interface for memory management.

**Usage:**
```bash
aq-memory [--storage PATH] [--json] COMMAND [OPTIONS]
```

**Global Options:**
- `--storage PATH`: Path to fact storage file (default: .aidb/temporal_facts.json)
- `--json`: Output in JSON format

**Commands:**

#### add

Add a new fact.

```bash
aq-memory add CONTENT --project PROJECT [OPTIONS]
```

**Required Arguments:**
- `CONTENT`: Fact content

**Options:**
- `--project PROJECT`: Project name (required)
- `--topic TOPIC`: Topic/category
- `--type TYPE`: Fact type (decision, preference, discovery, event, advice, fact)
- `--valid-from ISO_DATE`: Start of validity
- `--valid-until ISO_DATE`: End of validity
- `--agent-owner AGENT`: Agent that owns this fact
- `--tags TAGS`: Comma-separated tags
- `--confidence FLOAT`: Confidence score 0.0-1.0
- `--source SOURCE`: Source of this fact
- `--created-by NAME`: Creator identifier

**Example:**
```bash
aq-memory add "Using JWT with 7-day expiry" \
  --project ai-stack \
  --topic auth \
  --type decision \
  --tags "security,jwt" \
  --confidence 0.95
```

#### search

Search for facts.

```bash
aq-memory search QUERY [OPTIONS]
```

**Arguments:**
- `QUERY`: Search query

**Options:**
- `--project PROJECT`: Filter by project
- `--topic TOPIC`: Filter by topic
- `--type TYPE`: Filter by type
- `--tags TAGS`: Filter by tags (comma-separated)
- `--valid-now`: Only show currently valid facts
- `--limit N`: Maximum results (default: 10)

**Example:**
```bash
aq-memory search "authentication" \
  --project ai-stack \
  --topic auth \
  --valid-now \
  --limit 5
```

#### list

List facts with filters.

```bash
aq-memory list [OPTIONS]
```

**Options:**
- `--project PROJECT`: Filter by project
- `--topic TOPIC`: Filter by topic
- `--type TYPE`: Filter by type
- `--agent-owner AGENT`: Filter by agent owner
- `--valid-now`: Only show currently valid facts
- `--stale`: Only show stale facts
- `--limit N`: Maximum results (default: 50)

**Example:**
```bash
aq-memory list --project ai-stack --type decision --valid-now
```

#### expire

Expire a fact.

```bash
aq-memory expire FACT_ID --until ISO_DATE [OPTIONS]
```

**Arguments:**
- `FACT_ID`: Fact ID (or prefix)

**Options:**
- `--until ISO_DATE`: Expiration date (required)
- `--reason REASON`: Reason for expiration
- `--updated-by NAME`: Who is expiring this fact

**Example:**
```bash
aq-memory expire abc12345 \
  --until "2026-12-31T23:59:59Z" \
  --reason "superseded by new architecture"
```

#### agent-diary

View agent diary.

```bash
aq-memory agent-diary AGENT_NAME [OPTIONS]
```

**Arguments:**
- `AGENT_NAME`: Agent name (qwen, codex, claude, gemini)

**Options:**
- `--topic TOPIC`: Filter by topic
- `--type TYPE`: Filter by type
- `--valid-now`: Only show currently valid entries
- `--limit N`: Maximum results (default: 20)

**Example:**
```bash
aq-memory agent-diary qwen --topic auth --limit 10
```

#### stats

Show statistics.

```bash
aq-memory stats [--project PROJECT]
```

**Options:**
- `--project PROJECT`: Filter by project

**Example:**
```bash
aq-memory stats --project ai-stack
```

---

### aq-benchmark

Memory benchmark CLI tool.

**Usage:**
```bash
aq-benchmark [-v|--verbose] COMMAND [OPTIONS]
```

**Global Options:**
- `-v, --verbose`: Enable verbose logging

**Commands:**

#### run

Run full benchmark suite.

```bash
aq-benchmark run [OPTIONS]
```

**Options:**
- `--corpus PATH`: Path to benchmark corpus (default: benchmarks/memory-benchmark-corpus.json)
- `--output PATH`: Output file for results
- `--limit N`: Result limit per query (default: 10)

**Example:**
```bash
aq-benchmark run \
  --corpus benchmarks/memory-benchmark-corpus.json \
  --output results.json
```

#### recall

Run recall accuracy tests.

```bash
aq-benchmark recall [OPTIONS]
```

**Options:**
- `--corpus PATH`: Path to benchmark corpus
- `--baseline`: Run baseline test only
- `--metadata`: Run metadata-enhanced test only
- `--temporal`: Run temporal test only
- `--all`: Run all recall tests
- `--limit N`: Result limit per query (default: 10)
- `--output PATH`: Output file for results

**Example:**
```bash
aq-benchmark recall --all --limit 10
```

#### perf

Run performance tests.

```bash
aq-benchmark perf [OPTIONS]
```

**Options:**
- `--corpus PATH`: Path to benchmark corpus
- `--latency`: Run latency test only
- `--throughput`: Run throughput test only
- `--concurrency`: Run concurrency test only
- `--storage`: Run storage test only
- `--memory`: Run memory test only
- `--all`: Run all performance tests
- `--queries N`: Number of queries for latency test (default: 1000)
- `--duration N`: Duration for throughput test in seconds (default: 10)
- `--workers N`: Number of workers for concurrency test (default: 10)
- `--queries-per-worker N`: Queries per worker (default: 100)
- `--cold`: Also run cold cache test
- `--output PATH`: Output file for results

**Example:**
```bash
aq-benchmark perf --all --queries 2000
```

#### report

Generate benchmark report.

```bash
aq-benchmark report RESULTS_FILE [OPTIONS]
```

**Arguments:**
- `RESULTS_FILE`: Benchmark results JSON file

**Options:**
- `--format FORMAT`: Report format: text, html, json (default: text)
- `--output PATH`: Output file (for HTML format)

**Example:**
```bash
aq-benchmark report results.json --format html --output report.html
```

---

## Error Handling

All API functions may raise the following exceptions:

- `ValueError`: Invalid parameters, temporal inconsistencies
- `NotImplementedError`: Abstract methods not implemented by subclass
- `PermissionError`: Agent attempting unauthorized diary access
- `IOError`: File system errors (identity, diary files)

**Example error handling:**
```python
try:
    fact = TemporalFact(
        content="test",
        project="ai-stack",
        type="invalid_type"  # This will raise ValueError
    )
except ValueError as e:
    print(f"Invalid fact: {e}")

try:
    diary = AgentDiary("invalid_agent")
except ValueError as e:
    print(f"Invalid agent: {e}")
```

---

## Type Hints

All modules use Python type hints for better IDE support:

```python
from typing import List, Optional, Dict, Any, Set
from datetime import datetime

def search_facts(
    query: str,
    project: Optional[str] = None,
    limit: int = 10
) -> List[TemporalFact]:
    ...
```

---

## Next Steps

- **User Guide**: See [USER-GUIDE.md](./USER-GUIDE.md) for tutorials and best practices
- **Integration Examples**: See [INTEGRATION-EXAMPLES.md](./INTEGRATION-EXAMPLES.md) for working code examples
- **Quick Reference**: See [QUICK-REFERENCE.md](./QUICK-REFERENCE.md) for command cheat sheet
