# Phase 3.3 Implementation: Expand Context-Aware Retrieval with Service and Config Data

**Date:** 2026-03-20
**Status:** COMPLETE
**Testing:** All 25 unit tests passing

## Overview

Phase 3.3 successfully integrates service-level and config-level graph coverage (from Phase 3.2) into the existing context-aware retrieval system. Operators can now search across services and configurations in addition to deployments, logs, and code.

## Changes Made

### 1. Query Intent Detection Methods (New)

Added three new static methods to `ContextStore` class:

#### `detect_service_intent(query: str) -> bool`
- Detects service-focused queries containing:
  - Service keywords: "service", "daemon", "process", "health", "status", "active", "inactive", "down", "systemd", ".service"
  - Known service names: "hybrid-coordinator", "qdrant", "dashboard", "prometheus", "switchboard", "postgres", "redis"
- Returns `True` if query is service-focused, `False` otherwise

#### `detect_config_intent(query: str) -> bool`
- Detects configuration-focused queries containing:
  - Config keywords: "config", "configuration", "setting", "settings", "parameter", "parameters", "port", "value", "nix", "yaml", "json"
- Returns `True` if query is config-focused, `False` otherwise

#### `_extract_service_names_from_query(query: str) -> List[str]`
- Extracts known service names from user queries
- Filters against known services list from GRAPH_SERVICE_HINTS
- Returns list of detected service names

#### `_resolve_service_names_from_query(query: str) -> List[str]`
- Expands service matching beyond static hints
- Resolves against service names already captured in the Phase 3.2 service graph tables
- Supports normalized matches across punctuation differences such as `hybrid coordinator` vs `hybrid-coordinator`

#### `_extract_config_keys_from_query(query: str) -> List[str]`
- Extracts configuration keys/patterns from query text
- Filters out stopwords using GRAPH_STOPWORDS and GRAPH_QUERY_STOPWORDS
- Returns up to 5 extracted config tokens

#### `_resolve_config_keys_from_query(query: str) -> List[str]`
- Expands config matching beyond literal query tokens
- Resolves against config keys already stored in the Phase 3.2 config graph tables
- Supports partial token matching so queries like `config database` can surface `database_url`

### 2. Service Context Search Method (New)

#### `search_service_context(query: str, limit: int = 8) -> List[Dict[str, Any]]`
- Searches service health timeline based on service names in query
- Uses `_resolve_service_names_from_query()` so graph-backed services can be retrieved even when not in the static hint list
- For each detected service, retrieves health timeline from Phase 3.2 data
- Returns formatted result items with:
  - `source: "service"` for filtering/ranking
  - `service_status` metadata indicating active/failed/error states
  - `health_issue` flag for failed services
  - Service-specific explanation text
  - Relevance scoring based on service health (failed/error states score higher)

**Result Structure:**
```python
{
    "id": "service:hybrid-coordinator:timestamp",
    "source": "service",
    "message": "Service hybrid-coordinator status: failed",
    "metadata": {
        "service_name": "hybrid-coordinator",
        "service_status": "failed",
        "deployment_id": "deploy-123",
        "health_issue": True,
        # ... additional metadata from Phase 3.2
    },
    "explanation": {
        "summary": "Service health status from deployment deploy-123",
        "matched_terms": ["service", "hybrid-coordinator"],
        "source_reason": "service health timeline",
        "score_hint": 1
    }
}
```

### 3. Config Context Search Method (New)

#### `search_config_context(query: str, limit: int = 8) -> List[Dict[str, Any]]`
- Searches config impact timeline based on config keys in query
- Uses `_resolve_config_keys_from_query()` so stored config keys can be matched by partial operator wording
- For each detected config key, retrieves impact timeline from Phase 3.2 data
- Returns formatted result items with:
  - `source: "config"` for filtering/ranking
  - `config_value` and `change_type` metadata
  - `validation_failed` flag for error-type changes
  - Config-specific explanation text
  - Relevance scoring based on change type (delete/error changes score higher)

**Result Structure:**
```python
{
    "id": "config:port:timestamp",
    "source": "config",
    "message": "Config port changed: 8080",
    "metadata": {
        "config_key": "port",
        "config_value": "8080",
        "change_type": "update",
        "deployment_id": "deploy-456",
        "validation_failed": False,
        # ... additional metadata from Phase 3.2
    },
    "explanation": {
        "summary": "Config change impact from deployment deploy-456",
        "matched_terms": ["config", "port"],
        "source_reason": "config impact timeline",
        "score_hint": 0
    }
}
```

### 4. Enhanced Result Ranking

Updated `_score_context_result()` method with Phase 3.3 enhancements:

```python
# Service and Config Context Ranking Enhancements
if graph_view == "services" and source == "service":
    source_base += 25
if graph_view == "services" and source == "service" and metadata.get("health_issue"):
    source_base += 15
if graph_view == "configs" and source == "config":
    source_base += 20
if graph_view == "configs" and source == "config" and metadata.get("validation_failed"):
    source_base += 18
```

**Ranking Rules:**
- Service results get +25 base boost for service-focused queries
- Service health issues (failed/inactive/error) get additional +15 boost
- Config results get +20 base boost for config-focused queries
- Config validation failures get additional +18 boost

### 5. Integration into search_deployment_context()

Modified the main context-aware search method to integrate service and config results:

```python
# Phase 3.3: Integrate Service and Config Context
service_results = []
config_results = []
if self.detect_service_intent(query):
    query_analysis["recommended_graph_view"] = "services"
    service_results = self.search_service_context(query, limit=max(3, limit // 4))
if self.detect_config_intent(query):
    query_analysis["recommended_graph_view"] = "configs"
    config_results = self.search_config_context(query, limit=max(3, limit // 4))

# Combine with existing sources
for item in deployment_results + log_results + repo_results + service_results + config_results:
    # ... ranking and deduplication logic ...
```

The service-focused path also preserves service timeline results during runtime-status answer collapsing, so status queries do not regress back to log-only output.

**Source Priority Updated:**
```python
source_priority = {
    "deployment": 0, "semantic": 0, "keyword": 1,
    "service": 2,  # NEW in Phase 3.3
    "config": 2,   # NEW in Phase 3.3
    "code": 3
}
```

**Sources Counter Updated:**
```python
sources = {
    "deployment": ...,
    "logs": ...,
    "service": sum(1 for item in combined if item.get("source") == "service"),  # NEW
    "config": sum(1 for item in combined if item.get("source") == "config"),    # NEW
    "code": ...,
}
```

## Testing

### Test Coverage
- **25 unit tests** covering all Phase 3.3 functionality
- Tests organized into 8 test classes:
  1. `TestPhase33QueryIntentDetection` - Intent detection logic
  2. `TestPhase33KeywordExtraction` - Service/config keyword extraction
  3. `TestPhase33ServiceContextSearch` - Service context search
  4. `TestPhase33ConfigContextSearch` - Config context search
  5. `TestPhase33SearchDeploymentContextIntegration` - Integration tests
  6. `TestPhase33ServiceDataStructure` - Service result structure validation
  7. `TestPhase33ConfigDataStructure` - Config result structure validation
  8. `TestPhase33RankingEnhancements` - Ranking boost validation

**All 25 tests passing:** ✓

### Test Commands
```bash
# Run all Phase 3.3 tests
pytest tests/unit/test_phase_3_3_service_config_retrieval.py -v

# Run specific test class
pytest tests/unit/test_phase_3_3_service_config_retrieval.py::TestPhase33QueryIntentDetection -v

# Run with coverage
pytest tests/unit/test_phase_3_3_service_config_retrieval.py --cov=dashboard.backend.api.services.context_store
```

## Example Usage Scenarios

### Query 1: Service Health Focus
```bash
# Query mentioning hybrid-coordinator (service)
Query: "why is hybrid-coordinator failing"

Processing:
1. detect_service_intent() returns True
2. search_service_context() extracts "hybrid-coordinator"
3. query_service_health_timeline("hybrid-coordinator") called
4. Service health results combined with deployment/log/code results
5. Service results ranked +25 base, +15 if health_issue=True
6. Results include service status, recent deployments affecting it

Output includes:
- Service hybrid-coordinator with status transitions
- Deployments that may have caused service failure
- Related log entries from affected service
- Ranking emphasizes health-critical information
```

### Query 2: Config-Focused Query
```bash
# Query mentioning configuration
Query: "port configuration issues in recent deployments"

Processing:
1. detect_config_intent() returns True
2. search_config_context() extracts "port"
3. query_config_impact_timeline("port") called
4. Config change results combined with other sources
5. Config results ranked +20 base, +18 if validation_failed=True
6. Results include config change history and deployments

Output includes:
- Config "port" with recent changes
- Deployments that changed the port setting
- Related code/config files where port is defined
- Ranking emphasizes config validation failures
```

### Query 3: Cross-Cutting Query
```bash
# Query mentioning both service and config
Query: "dashboard service configuration and health status"

Processing:
1. detect_service_intent() returns True → searches services
2. detect_config_intent() returns True → searches configs
3. Both service_results and config_results populated
4. Results combined with deployment/log/code context
5. Deduplication ensures no duplicate information
6. Ranking applied: service +25 for "services" graph view

Output includes:
- Dashboard service health timeline
- Dashboard-related configuration changes
- Recent deployments affecting both
- Comprehensive view of service+config status
```

## API Contract Changes

### New Search Response Fields
The `/deployments/search/context` endpoint response now includes:

```python
{
    "results": [...],  # Now includes service and config items
    "sources": {
        "deployment": int,
        "logs": int,
        "service": int,     # NEW - count of service results
        "config": int,      # NEW - count of config results
        "code": int,
    },
    "query_analysis": {
        # ... existing fields, now used by Phase 3.3 methods
    },
    # ... existing fields ...
}
```

### No Breaking Changes
- All existing fields remain unchanged
- New sources simply added to sources dict
- Existing result items structure preserved
- Service/config items follow same structure as existing items

## Files Modified

1. **`dashboard/backend/api/services/context_store.py`** (+183 lines)
   - Added 4 new intent detection/extraction static methods
   - Added 2 new service/config context search methods
   - Enhanced `_score_context_result()` with ranking boosts
   - Integrated service/config results into `search_deployment_context()`
   - Updated source tracking/counting logic

2. **`tests/unit/test_phase_3_3_service_config_retrieval.py`** (New file, 340 lines)
   - Comprehensive test suite for all Phase 3.3 functionality
   - 25 unit tests organized into 8 test classes
   - All tests passing

## Validation

### Code Quality
```bash
# Syntax validation
python3 -m py_compile dashboard/backend/api/services/context_store.py
✓ Passed

# Test execution
pytest tests/unit/test_phase_3_3_service_config_retrieval.py -v
✓ 25/25 tests passing
```

### Backward Compatibility
- No changes to existing method signatures
- All existing search modes (keyword, semantic, hybrid) work unchanged
- Service/config context only added when intent is detected
- Empty results when no services/configs mentioned in query
- No breaking changes to API contracts

### Integration with Phase 3.2
- Uses `query_service_health_timeline()` from Phase 3.2
- Uses `query_config_impact_timeline()` from Phase 3.2
- Uses `query_services_by_deployment()` from Phase 3.2
- Uses `query_configs_by_deployment()` from Phase 3.2
- Relies on Phase 3.2 database schema (deployment_service_states, deployment_config_changes)

## Success Criteria Met

✓ **Criterion 1:** Searches mentioning services return service health context
- Implemented `detect_service_intent()` and `search_service_context()`
- Service health timeline integrated into results
- Tested with 6+ test cases

✓ **Criterion 2:** Searches mentioning configs return config change/validation context
- Implemented `detect_config_intent()` and `search_config_context()`
- Config impact timeline integrated into results
- Tested with 5+ test cases

✓ **Criterion 3:** Query intent detection correctly identifies service vs config queries
- Service detection: checks keywords and known service names
- Config detection: checks config-related keywords
- Tested with 7 intent detection tests

✓ **Criterion 4:** Result ranking appropriately weights service and config evidence
- Service results: +25 boost for service queries, +15 for health issues
- Config results: +20 boost for config queries, +18 for validation failures
- Tested with ranking enhancement tests

✓ **Criterion 5:** Search result explanations mention service and config findings
- Service results include explanation with matched_terms, source_reason
- Config results include explanation with matched_terms, source_reason
- Both include service/config-specific summary text

✓ **Criterion 6:** No breaking changes to existing retrieval
- All existing deployment/log/code retrieval unchanged
- Service/config results only added when intent detected
- Empty results when no services/configs in query
- Backward compatible with all existing API clients

## Known Limitations & Future Work

### Current Limitations
1. Service name matching is exact substring match (case-insensitive)
   - Future: Implement fuzzy matching for service names
2. Config key extraction uses token-based approach
   - Future: Support more sophisticated config path patterns
3. Service/config results limited to health/impact timelines
   - Future: Include service dependency graph, config validation rules

### Future Enhancements
- Phase 3.4: Add service dependency context (which services depend on which)
- Phase 3.5: Add config validation rules enforcement in search results
- Phase 3.6: Machine learning-based relevance ranking using Phase 3.2+ data

## Documentation

- Implementation details in `PHASE-3-3-IMPLEMENTATION.md` (this file)
- Test examples in `tests/unit/test_phase_3_3_service_config_retrieval.py`
- Code comments in `dashboard/backend/api/services/context_store.py`

## References

- **Phase 3.2:** Service-level and config-level graph coverage
- **API Endpoint:** `/deployments/search/context` (GET)
- **Primary File:** `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/dashboard/backend/api/services/context_store.py`
- **Test File:** `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/tests/unit/test_phase_3_3_service_config_retrieval.py`
