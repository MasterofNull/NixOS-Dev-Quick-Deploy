# Phase 3.3 Validation: Example Queries and Expected Behavior

## Test Queries for Phase 3.3

This document provides examples of queries that should work with Phase 3.3 and describes the expected behavior.

## Query Category 1: Service Health Queries

### Query 1A: Service Failure Investigation
```
Query: "why is hybrid-coordinator failing"

Expected Behavior:
1. Intent Detection:
   - detect_service_intent() = True (contains "hybrid-coordinator" and "failing")
   - detect_config_intent() = False

2. Service Context Search:
   - Extracts service name: "hybrid-coordinator"
   - Calls query_service_health_timeline("hybrid-coordinator")
   - Returns service health entries from Phase 3.2 database

3. Result Ranking:
   - Service results get +25 base boost (for service-focused query)
   - Any failed/error status service gets additional +15 boost
   - Final rank_score = 25 + 15 + relevance_bonus

4. Result Structure:
   - Source: "service"
   - Message: "Service hybrid-coordinator status: [status]"
   - Metadata includes: service_name, service_status, health_issue
   - Explanation: "Service health status from deployment [id]"

5. Combined Results:
   - Service results integrated with deployment/log/code results
   - Service deduplication applied
   - Final results sorted by rank_score (descending)
```

### Query 1B: Service Dependencies
```
Query: "which services depend on qdrant"

Expected Behavior:
1. Intent Detection:
   - detect_service_intent() = True (contains "services" and "qdrant")
   - detect_config_intent() = False

2. Service Context Search:
   - Extracts service name: "qdrant"
   - Calls query_service_health_timeline("qdrant")
   - Retrieves all deployments affecting qdrant
   - Note: Service dependencies from Phase 3.2 graph data

3. Result Includes:
   - Recent deployments that started/stopped/changed qdrant
   - Services that interact with qdrant (from logs/code)
   - Related configuration changes
```

### Query 1C: Multi-Service Query
```
Query: "hybrid-coordinator and qdrant health status"

Expected Behavior:
1. Intent Detection:
   - detect_service_intent() = True (multiple known service names)

2. Service Extraction:
   - _extract_service_names_from_query() returns ["hybrid-coordinator", "qdrant"]

3. Service Context Search:
   - Calls query_service_health_timeline("hybrid-coordinator", limit=4)
   - Calls query_service_health_timeline("qdrant", limit=4)
   - Returns combined service health timelines (up to 8 results)

4. Result Includes:
   - Recent status for both services
   - Interleaved timeline showing both services' health evolution
   - Cross-service impact analysis from logs
```

## Query Category 2: Configuration Queries

### Query 2A: Config Change Investigation
```
Query: "port configuration issues"

Expected Behavior:
1. Intent Detection:
   - detect_service_intent() = False
   - detect_config_intent() = True (contains "configuration" and "port")

2. Config Context Search:
   - Extracts config key: "port"
   - Calls query_config_impact_timeline("port")
   - Returns config change entries from Phase 3.2 database

3. Result Ranking:
   - Config results get +20 base boost (for config-focused query)
   - Any error/delete type change gets additional +18 boost
   - Final rank_score = 20 + 18 + relevance_bonus

4. Result Structure:
   - Source: "config"
   - Message: "Config port changed: [value]"
   - Metadata includes: config_key, config_value, change_type, validation_failed
   - Explanation: "Config change impact from deployment [id]"

5. Combined Results:
   - Config results integrated with other sources
   - Code/Nix files with "port" configuration included
   - Related deployments that changed port setting
```

### Query 2B: YAML Configuration
```
Query: "YAML configuration changes"

Expected Behavior:
1. Intent Detection:
   - detect_config_intent() = True (contains "YAML" and "configuration")

2. Config Extraction:
   - _extract_config_keys_from_query() returns ["yaml", "configuration"]
   - Filters out stopwords

3. Config Search:
   - Searches config impact timeline for "yaml" and "configuration"
   - Returns config entries with "yaml" in paths or keys
```

### Query 2C: Multi-Config Query
```
Query: "API key and database URL configuration"

Expected Behavior:
1. Intent Detection:
   - detect_config_intent() = True

2. Config Extraction:
   - _extract_config_keys_from_query() returns ["key", "database", "url", "configuration"]
   - (Actual extraction depends on stopword filtering)

3. Config Search:
   - Searches for each config key in timeline
   - Returns config changes for all matching keys
   - Limited to ~4-5 results per key
```

## Query Category 3: Cross-Cutting Queries

### Query 3A: Service and Config Together
```
Query: "why is dashboard configuration failing and service is down"

Expected Behavior:
1. Intent Detection:
   - detect_service_intent() = True (contains "dashboard", "service", "failing", "down")
   - detect_config_intent() = True (contains "configuration")

2. Dual Search:
   - search_service_context() extracts "dashboard"
   - search_config_context() extracts "configuration"
   - Both service_results and config_results populated

3. Result Ranking:
   - Service results: +25 for service queries, +15 for health issues
   - Config results: +20 for config queries, +18 for validation failures
   - Deduplication ensures no duplicates

4. Final Results:
   - Mixed results showing service health and config state
   - Related deployments affecting both
   - Comprehensive incident diagnosis perspective
```

### Query 3B: Service Health with Config Context
```
Query: "hybrid-coordinator port configuration"

Expected Behavior:
1. Intent Detection:
   - detect_service_intent() = True (contains "hybrid-coordinator")
   - detect_config_intent() = True (contains "port" and "configuration")

2. Search Results Include:
   - Service health timeline for hybrid-coordinator
   - Config changes for "port" setting
   - Deployments that changed port configuration
   - Recent logs from hybrid-coordinator service
   - Code/Nix files with "port" configuration

3. Root Cause Analysis:
   - Port configuration change may correlate with service failure
   - Ranking emphasizes both service health issues and config changes
   - Related deployment events show causal timeline
```

## Expected Source Distributions

### Service-Focused Query Results
```
Query: "hybrid-coordinator health"

Expected sources count:
{
    "deployment": 2-3   (deployments that affected the service)
    "logs": 2-3         (service logs)
    "service": 3-4      (service health timeline entries)
    "config": 1-2       (related config files, if any)
    "code": 1-2         (code handling hybrid-coordinator)
}
Total: ~10 results
```

### Config-Focused Query Results
```
Query: "port configuration"

Expected sources count:
{
    "deployment": 2-3   (deployments that changed port)
    "logs": 1-2         (related logs)
    "service": 1        (services affected by port change, if any)
    "config": 3-4       (config changes and files)
    "code": 2-3         (code with port configuration)
}
Total: ~10 results
```

### Cross-Cutting Query Results
```
Query: "dashboard service and config"

Expected sources count:
{
    "deployment": 2-3   (recent deployments)
    "logs": 2-3         (service logs)
    "service": 2-3      (dashboard service health)
    "config": 2-3       (dashboard config changes)
    "code": 1-2         (dashboard code/config files)
}
Total: ~10 results
```

## Testing These Queries

### Using curl (assuming dashboard running on localhost:8000)
```bash
# Service query
curl -s "http://localhost:8000/deployments/search/context?query=hybrid-coordinator%20failing" | jq '.sources'

# Config query
curl -s "http://localhost:8000/deployments/search/context?query=port%20configuration" | jq '.sources'

# Cross-cutting query
curl -s "http://localhost:8000/deployments/search/context?query=dashboard%20service%20and%20config" | jq '.sources'
```

### Using Python requests
```python
import requests

base_url = "http://localhost:8000"

# Service query
response = requests.get(
    f"{base_url}/deployments/search/context",
    params={"query": "hybrid-coordinator failing"}
)
sources = response.json()["sources"]
print(f"Service results: {sources}")

# Config query
response = requests.get(
    f"{base_url}/deployments/search/context",
    params={"query": "port configuration"}
)
sources = response.json()["sources"]
print(f"Config results: {sources}")
```

## Intent Detection Examples

### Service Intent Detection
These queries should trigger `detect_service_intent() = True`:
- "service status"
- "hybrid-coordinator failing"
- "daemon process crashed"
- "running service health"
- "qdrant down"
- "systemd service"

### Config Intent Detection
These queries should trigger `detect_config_intent() = True`:
- "configuration issue"
- "config changes"
- "port parameter"
- "YAML configuration"
- "nix module"
- "setting value"

### Non-Service Queries
These should return `detect_service_intent() = False`:
- "deployment logs" (no service keywords)
- "build progress" (no service keywords)
- "configuration issue" (has "issue" but no service keywords)

### Non-Config Queries
These should return `detect_config_intent() = False`:
- "deployment status" (no config keywords)
- "service health" (no config keywords)
- "log errors" (no config keywords)

## Ranking Score Examples

### Service Health Query Ranking
```
Item: Service hybrid-coordinator (failed)
source_base = 50 (for logs source)  # if logs were the source
+ 18 (service-focused recommended source boost)
+ 12 (graph_view == "services" and logs source)
= 80 base

+ Service override: +25 (graph_view == "services" and source == "service")
+ Health boost: +15 (health_issue == True)
= 120 adjusted

+ Relevance bonus: int(1) * 10 = 10
+ Matched bonus: 2 * 14 = 28
= 158 total rank_score
```

### Config Query Ranking
```
Item: Config change (port = 8080, change_type = "update")
source_base = 45 (for config source)
+ 18 (config-focused recommended source boost)
+ 22 (graph_view == "configs" and config source)
= 85 base

+ Config override: +20 (graph_view == "configs" and source == "config")
+ Validation boost: +0 (validation_failed == False)
= 105 adjusted

+ Relevance bonus: 0
+ Matched bonus: 2 * 14 = 28
= 133 total rank_score
```

## Validation Checklist

When testing Phase 3.3 implementation, verify:

- [ ] Service-focused queries return service health results
- [ ] Config-focused queries return config change results
- [ ] Cross-cutting queries return both service and config results
- [ ] Source counts show "service" and "config" fields populated
- [ ] Service health issues get high ranking scores
- [ ] Config validation failures get high ranking scores
- [ ] Results are deduplicated (no duplicate entries)
- [ ] Explanation text mentions service/config findings
- [ ] No breaking changes to existing deployment/log/code results
- [ ] API response structure unchanged (only new fields added)
- [ ] All tests passing: `pytest tests/unit/test_phase_3_3_service_config_retrieval.py`

## Performance Notes

- Service context search: O(n) where n = number of service names extracted
- Config context search: O(n) where n = number of config keys extracted
- Database queries: Indexed on (service_name, timestamp) and (config_key, timestamp)
- Result limit: Configurable, default 8 per service/config
- Combined results: Deduplication after combining all sources
- Total query time: <500ms for typical multi-service/multi-config queries
