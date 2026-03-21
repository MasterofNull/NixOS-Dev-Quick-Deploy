# Phase 4.2: Query → Agent → Storage → Learning Integration Guide

**Status:** Operational
**Owner:** AI Harness Team
**Last Updated:** 2026-03-20
**Objective**: Complete end-to-end workflow from operator queries through agent selection, interaction storage, pattern extraction, and continuous learning

## Overview

The Phase 4.2 integration implements a complete learning loop where:

1. **Queries** are routed to appropriate agents based on query analysis
2. **Interactions** (query + response) are stored in vector DB with metadata
3. **Patterns** are extracted from interactions for learning
4. **Hints** are generated from patterns to improve future agent behavior
5. **Gaps** are detected and remediation playbooks are created
6. **Quality** is continuously measured and improvements tracked

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OPERATOR INTERFACE                       │
│  (CLI, Dashboard, API)                                      │
└───────────────────┬─────────────────────────────────────────┘
                    │ Query Submission
                    ▼
┌─────────────────────────────────────────────────────────────┐
│         QUERY ROUTING SYSTEM (query-router.sh)              │
│  - Query type classification (deployment, troubleshooting)  │
│  - Complexity assessment (simple, medium, high)             │
│  - Agent capability matching                                │
│  - Load balancing & fallback routing                        │
└───────────────────┬─────────────────────────────────────────┘
                    │ Route Agent Selection
                    ▼
┌─────────────────────────────────────────────────────────────┐
│            AGENT EXECUTION LAYER                            │
│  (Local LLM, Free Agents, Paid Models)                      │
└───────────────────┬─────────────────────────────────────────┘
                    │ Query + Response
                    ▼
┌─────────────────────────────────────────────────────────────┐
│    INTERACTION STORAGE (interaction-storage.py)             │
│  - Persist query/response to local cache                    │
│  - Index in vector DB (Qdrant) for semantic search          │
│  - Capture metadata (agent, timestamp, quality)             │
│  - Link feedback for learning                               │
└───────────────────┬─────────────────────────────────────────┘
                    │ Interaction Events
                    ▼
┌─────────────────────────────────────────────────────────────┐
│     PATTERN EXTRACTION (pattern-extractor.py)               │
│  - Extract common query patterns                            │
│  - Identify successful resolution patterns                  │
│  - Detect recurring failure patterns                        │
│  - Analyze agent performance patterns                       │
└───────────────────┬─────────────────────────────────────────┘
                    │ Discovered Patterns
                    ▼
┌─────────────────────────────────────────────────────────────┐
│      LEARNING LOOP ENGINE (learning-loop.py)                │
│  - Convert patterns to hints                                │
│  - Detect knowledge gaps                                    │
│  - Create remediation playbooks                             │
│  - Track hint effectiveness                                 │
└───────────────────┬─────────────────────────────────────────┘
                    │ Hints + Gaps
                    ▼
┌─────────────────────────────────────────────────────────────┐
│   IMPROVEMENT TRACKER (improvement-tracker.sh)              │
│  - Measure quality metrics (success rate, response time)    │
│  - Detect regressions                                       │
│  - Track improvement trends                                 │
│  - Generate improvement reports                             │
└───────────────────┬─────────────────────────────────────────┘
                    │ Metrics & Reports
                    ▼
┌─────────────────────────────────────────────────────────────┐
│           DASHBOARD & REPORTING                             │
│  - Real-time learning metrics                               │
│  - Pattern discovery timeline                               │
│  - Quality improvement graphs                               │
│  - Gap resolution tracking                                  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Query Routing System (`lib/agents/query-router.sh`)

Routes operator queries to appropriate agents based on query analysis.

#### Functions

- `classify_query_type(query)`: Classify query as deployment, troubleshooting, configuration, or learning
- `assess_query_complexity(query)`: Assess complexity as simple, medium, or high
- `get_agent_for_query_type(type, complexity)`: Select agent based on query type and complexity
- `route_query(query, context)`: Main routing function returning routing decision with metadata

#### Usage

```bash
# Source the router
source lib/agents/query-router.sh

# Route a query
routing_decision=$(route_query "What is the deployment status?")
echo "${routing_decision}" | jq .agent  # Output: "deployment-specialist"

# Get routing metrics
get_routing_metrics json
```

#### Configuration

Environment variables:
- `LOCAL_LLM_ENDPOINT`: Local LLM server (default: http://localhost:8080)
- `HYBRID_COORDINATOR_ENDPOINT`: Hybrid coordinator (default: http://localhost:8003)
- `ROUTING_METRICS_DB`: SQLite database for metrics (default: ~/.cache/nixos-ai-stack/routing-metrics.db)

### 2. Interaction Storage System (`lib/agents/interaction-storage.py`)

Persists all interactions to vector DB and local cache with semantic search capability.

#### Key Classes

- `Interaction`: Represents a stored query/response interaction with metadata
- `InteractionStorageSystem`: Manages storage backends (Qdrant + local cache)

#### Methods

```python
storage = InteractionStorageSystem()
await storage.initialize()

# Store interaction
interaction = Interaction(
    interaction_id="int-123",
    query="What is the status?",
    response="The system is operational.",
    agent="deployment-specialist",
    query_type="deployment",
    complexity="simple",
    quality_score=0.95
)
await storage.store(interaction)

# Search
results = await storage.search_semantic("deployment status", limit=10)
interactions = await storage.search_by_type("deployment", limit=50)

# Get statistics
stats = await storage.get_statistics()
```

#### Storage Paths

- Local cache: `~/.local/share/nixos-ai-stack/interactions/cache.jsonl`
- Qdrant collection: `interactions`
- Metadata stored with each interaction:
  - timestamp, agent, query_type, complexity, status
  - execution_time_ms, quality_score, tags

### 3. Pattern Extraction Engine (`lib/agents/pattern-extractor.py`)

Extracts patterns from interactions for learning and improvement.

#### Pattern Types

1. **Common Query Patterns**: Frequently occurring query phrases and structures
2. **Success Patterns**: Agent/query-type combinations with high success rates
3. **Failure Patterns**: Recurring errors and failure modes
4. **Agent Performance Patterns**: Performance characteristics per agent
5. **Temporal Patterns**: Time-based trends (daily/weekly patterns)

#### Usage

```python
extractor = PatternExtractor()

# Extract all patterns
patterns = await extractor.extract_all_patterns(interactions)

# Get top patterns
top_patterns = await extractor.get_top_patterns(limit=10)

# Analyze trends
trends = await extractor.analyze_trends(interactions, days=7)

# Get statistics
stats = await extractor.get_statistics()
```

#### Pattern Structure

```json
{
  "pattern_id": "query_pattern_12345",
  "pattern_type": "common_query",
  "description": "Common query phrase: 'deployment status'",
  "frequency": 15,
  "associated_agents": ["deployment-specialist"],
  "success_rate": 0.87,
  "confidence": 0.85,
  "examples": [...]
}
```

### 4. Learning Loop Engine (`lib/agents/learning-loop.py`)

Converts patterns into hints and detects knowledge gaps.

#### Hint Types

- **ROUTING_PREFERENCE**: Route specific query types to agents with proven performance
- **QUALITY_IMPROVEMENT**: Adopt patterns from high-performing agent/query combinations
- **ERROR_AVOIDANCE**: Avoid known error patterns
- **PERFORMANCE_OPTIMIZATION**: Optimize execution time for slow agents

#### Gap Types

- **Low Success Rate**: Query types with <50% success rate
- **High Error Rate**: Error patterns occurring 5+ times
- **Agent Performance Gap**: Agents significantly underperforming on specific query types

#### Usage

```python
engine = LearningLoopEngine()

# Generate hints
hints = await engine.generate_hints_from_patterns(patterns)

# Detect gaps
gaps = await engine.detect_gaps(interactions)

# Apply hint feedback
await engine.apply_hint_feedback("hint_id", success=True)

# Resolve gap
resolution = {"steps": [...], "success_criteria": "..."}
await engine.resolve_gap("gap_id", resolution)

# Get metrics
metrics = await engine.get_learning_metrics()
```

#### Hint Effectiveness Tracking

Each hint tracks:
- `usage_count`: Number of times hint was applied
- `success_count`: Number of successful applications
- `effectiveness`: success_count / usage_count

### 5. Continuous Improvement Tracker (`lib/agents/improvement-tracker.sh`)

Tracks quality metrics and detects regressions over time.

#### Key Metrics

1. **Query Success Rate**: % of queries successfully handled
2. **Average Response Time**: ms per query
3. **Agent Selection Accuracy**: % correct agent selection
4. **Pattern Coverage**: % of new queries matching known patterns
5. **Learning Effectiveness**: Impact of applied hints on quality

#### Usage

```bash
source lib/agents/improvement-tracker.sh

# Initialize
init_metrics_db

# Record metrics
record_metric_snapshot 0.87 850 0.92 0.65 0.45 100

# Detect regressions
if detect_regressions 0.82; then
    echo "REGRESSION DETECTED"
fi

# Analyze trends
analyze_improvement_trends

# Compare with baseline
compare_with_baseline

# Generate report
generate_quality_report /tmp/quality-report.json
```

#### Regression Detection

Regression detected if success rate drops more than threshold (default: 5%):

```bash
# Set baseline
set_baseline 0.85 900 0.90 0.70 0.50

# Check for regression
detect_regressions 0.80  # Returns 0 (regression) if > 5% drop
```

## End-to-End Workflow Validation

Comprehensive test suite validates the complete flow:

```bash
scripts/testing/validate-query-agent-storage-learning.sh
```

### Test Scenarios

1. **Query Routing**: Verify query routed to correct agent
2. **Storage Integration**: Confirm interaction stored in DB
3. **Semantic Search**: Find similar past interactions
4. **Pattern Extraction**: Extract patterns from multiple similar queries
5. **Learning Statistics**: Verify learning metrics available
6. **Hints Generation**: Confirm hints generated from patterns
7. **Gap Detection**: Identify knowledge gaps
8. **Dataset Export**: Export fine-tuning examples
9. **Quality Tracking**: Measure quality improvements
10. **Comprehensive Report**: Generate learning report
11. **aq-report Integration**: Verify metrics in aq-report
12. **Regression Detection**: Confirm regression detection works

### Expected Results

```
Test Results: ✓ All 12 tests passing
Key Metrics:
  Total Interactions: 8+
  Success Rate: 70%+
  Patterns Extracted: 2+
  Active Hints: 2+
  Detected Gaps: 0-2
  Learning Examples: 5+
```

## Configuration

### Environment Variables

```bash
# Query Routing
export LOCAL_LLM_ENDPOINT="http://localhost:8080"
export HYBRID_COORDINATOR_ENDPOINT="http://localhost:8003"
export ROUTING_METRICS_DB="${HOME}/.cache/nixos-ai-stack/routing-metrics.db"

# Interaction Storage
export QDRANT_URL="http://localhost:6333"
export INTERACTION_STORAGE_DATA_ROOT="${HOME}/.local/share/nixos-ai-stack/interactions"

# Pattern Extraction
export PATTERN_EXTRACTION_DATA_ROOT="${HOME}/.local/share/nixos-ai-stack/patterns"

# Learning Loop
export LEARNING_LOOP_DATA_ROOT="${HOME}/.local/share/nixos-ai-stack/learning"

# Improvement Tracking
export METRICS_DB="${HOME}/.cache/nixos-ai-stack/improvement-metrics.json"
export BASELINE_METRICS="${HOME}/.cache/nixos-ai-stack/baseline-metrics.json"
export REGRESSION_THRESHOLD="5"  # % point drop
export QUALITY_IMPROVEMENT_TARGET="20"  # % improvement target

# Learning Configuration
export DEBUG="0"  # Set to 1 for debug output
```

### File Locations

```
~/.local/share/nixos-ai-stack/
├── interactions/
│   └── cache.jsonl           # Local interaction cache
├── patterns/
│   └── patterns.json         # Extracted patterns
└── learning/
    ├── hints.json            # Generated hints
    └── gaps.json             # Detected gaps

~/.cache/nixos-ai-stack/
├── routing-metrics.db        # Routing decisions (SQLite)
├── improvement-metrics.json  # Quality metrics snapshot
├── baseline-metrics.json     # Baseline for comparisons
└── metrics-history.jsonl     # Historical metrics (JSONL)
```

## Dashboard Integration

### API Endpoints

```
GET  /api/learning/metrics        - Current learning metrics
GET  /api/learning/patterns        - Extracted patterns with analysis
GET  /api/learning/hints           - Active hints for improvement
GET  /api/learning/improvements    - Quality improvement trends
POST /api/learning/feedback        - Submit hint effectiveness feedback
GET  /api/learning/gaps            - Knowledge gaps with remediation
GET  /api/learning/report          - Comprehensive learning report
```

### Dashboard Widgets

1. **Learning Metrics Card**
   - Success rate (target: 80%+)
   - Response time (target: <1000ms)
   - Patterns identified
   - Active hints

2. **Pattern Discovery Timeline**
   - New patterns over time
   - Pattern frequency
   - Agent performance by pattern

3. **Quality Improvement Graph**
   - Success rate trend
   - Response time trend
   - Regression alerts

4. **Hint Effectiveness Chart**
   - Hint usage count
   - Success percentage
   - Most effective hints

5. **Gap Resolution Tracking**
   - Open gaps
   - Remediation progress
   - Gap severity distribution

## Operational Procedures

### Daily Checks

```bash
# Check learning health
curl -H "X-API-Key: ${API_KEY}" http://localhost:8003/learning/stats | jq .

# Verify no regressions
lib/agents/improvement-tracker.sh && compare_with_baseline | jq .

# Check gap status
curl -H "X-API-Key: ${API_KEY}" http://localhost:8003/learning/gaps | jq '.gaps | length'
```

### Weekly Reviews

1. **Pattern Analysis**: Review patterns extracted during week
2. **Hint Effectiveness**: Evaluate hint application success rates
3. **Gap Resolution**: Track progress on open gaps
4. **Trend Analysis**: Identify improvement or degradation trends
5. **Quality Report**: Generate comprehensive weekly report

### Monthly Improvements

1. **Baseline Update**: Reset baseline if sustained improvement demonstrated
2. **Agent Optimization**: Update agent routing based on performance patterns
3. **Gap Closure**: Resolve critical gaps (severity 4+)
4. **Documentation**: Update operational guides based on learned patterns

## Troubleshooting

### No Patterns Detected

**Issue**: Pattern extraction returns empty results
**Cause**: Insufficient interaction history (< 10 interactions)
**Solution**: Run queries to accumulate interaction history, then re-extract

### Regression Detected

**Issue**: Success rate dropped significantly
**Cause**: Agent failure, routing issue, or query complexity change
**Solution**:
```bash
# Check recent failures
curl http://localhost:8003/learning/gaps | jq '.gaps[]'

# Examine recent interactions
scripts/testing/validate-query-agent-storage-learning.sh

# Review quality metrics
lib/agents/improvement-tracker.sh && generate_quality_report
```

### Hints Not Improving Quality

**Issue**: Applied hints not helping success rate
**Cause**: Hints may be based on insufficient data or incorrect patterns
**Solution**:
1. Check hint confidence (target: >0.7)
2. Review hint effectiveness: `curl http://localhost:8003/learning/hints | jq '.hints[] | select(.effectiveness < 0.5)'`
3. Disable low-confidence hints and re-collect data

### Storage Growing Too Large

**Issue**: Interaction cache consuming significant disk space
**Cause**: Insufficient cleanup of old interactions
**Solution**:
```python
# Clean up interactions older than 30 days
await storage.cleanup_old_interactions(days=30)
```

## Best Practices

### Query Formulation

- **Be specific**: "What is the deployment status?" works better than "Tell me about stuff"
- **Include context**: Mention error messages when reporting issues
- **Use consistent terminology**: Aids pattern recognition

### Feedback Quality

- **Rate truthfully**: 1-5 scale; use 5 for truly excellent responses
- **Provide corrections**: If response was wrong, suggest correct answer
- **Tag appropriately**: Use tags for categorization (deployment, security, etc.)

### Learning Optimization

- **Regular feedback**: Submit feedback within minutes of interaction for best learning
- **Diverse queries**: Test multiple query phrasings to train robust patterns
- **Monitor hints**: Review generated hints and disable low-effectiveness ones

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Query Success Rate | 80%+ | Baseline |
| Avg Response Time | <1000ms | Baseline |
| Pattern Coverage | 60%+ | ~40% |
| Hint Effectiveness | 70%+ | Building |
| Gap Resolution Rate | 80%+ | ~0% |
| Quality Improvement/Week | 3-5% | Measuring |

## References

- Query Router: `lib/agents/query-router.sh`
- Interaction Storage: `lib/agents/interaction-storage.py`
- Pattern Extractor: `lib/agents/pattern-extractor.py`
- Learning Loop: `lib/agents/learning-loop.py`
- Improvement Tracker: `lib/agents/improvement-tracker.sh`
- Validation Test: `scripts/testing/validate-query-agent-storage-learning.sh`
- Smoke Test: `scripts/testing/smoke-query-agent-storage-learning.sh`

## Support

For issues or questions:

1. Check this documentation and troubleshooting section
2. Review logs in `~/.local/share/nixos-ai-stack/logs/`
3. Run validation test: `scripts/testing/validate-query-agent-storage-learning.sh`
4. Check dashboard for visual indicators of learning health
