# Full AI Stack Deployment - In Progress
**Date:** 2026-01-09
**Status:** 🚀 DEPLOYING ALL SERVICES

---

## Executive Summary

Removing confusing profile system and deploying full AI stack with all orchestration and agentic capabilities enabled by default. This includes Ralph Wiggum orchestrator, hybrid-coordinator, continuous learning, and all monitoring services.

---

## Changes Made

### 1. Removed Profile Restrictions ✅

**File:** `ai-stack/compose/docker-compose.yml`

**Services Now Enabled by Default:**
- ✅ **Open-WebUI** (line 251) - Web interface
- ✅ **Jaeger** (line 322) - Distributed tracing
- ✅ **MindsDB** (line 499) - ML/predictive analytics
- ✅ **llama.cpp** (line 634) - Local LLM inference
- ✅ **Aider-Wrapper** (line 690) - Code generation agent
- ✅ **Code Machine** (line 732) - Workflow orchestrator
- ✅ **Prometheus** (line 822) - Metrics collection
- ✅ **Grafana** (line 853) - Metrics visualization
- ✅ **NixOS-Docs** (line 877) - Documentation MCP server
- ✅ **nginx** (line 904) - Reverse proxy
- ✅ **Ralph Wiggum** (line 909) - Agentic orchestrator (HITL)

**Before:**
```yaml
mindsdb:
  profiles: ["full"]  # Only started with --profile full
```

**After:**
```yaml
mindsdb:
  # profiles: ["full"]  # Removed - enabled by default for agentic workflow
```

---

### 2. Full Stack Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        NGINX Reverse Proxy                       │
│                    https://localhost:8443                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Orchestration Layer                          │
│                                                                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ Ralph Wiggum    │  │ Hybrid-Coordinator│  │ Code Machine   │ │
│  │ (HITL Orchestr.)│  │ (Local/Cloud)    │  │ (Workflows)    │ │
│  │ Port: 8090      │  │ Port: 8092       │  │ Port: 8095     │ │
│  └─────────────────┘  └──────────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Servers                               │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ AIDB        │  │ Embeddings   │  │ NixOS-Docs   │           │
│  │ Port: 8091  │  │ Port: 8081   │  │ Port: 8094   │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      AI Execution Layer                          │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ llama.cpp   │  │ Aider        │  │ MindsDB      │           │
│  │ Port: 8080  │  │ Port: 8096   │  │ Port: 47334  │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Data & Storage Layer                        │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ PostgreSQL  │  │ Qdrant       │  │ Redis        │           │
│  │ Port: 5432  │  │ Port: 6333   │  │ Port: 6379   │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring & Observability                    │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Prometheus  │  │ Grafana      │  │ Jaeger       │           │
│  │ Port: 9090  │  │ Port: 3002   │  │ Port: 16686  │           │
│  └─────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Ralph Wiggum - Default Orchestrator

### Overview

**Ralph Wiggum** is the **Human-in-the-Loop (HITL) Orchestrator** and the default orchestration layer for all large and high-level task execution.

### Key Features

1. **Human-in-the-Loop Controls**
   ```yaml
   RALPH_REQUIRE_APPROVAL: ${RALPH_REQUIRE_APPROVAL:-false}
   RALPH_APPROVAL_THRESHOLD: ${RALPH_APPROVAL_THRESHOLD:-high}
   RALPH_AUDIT_LOG: ${RALPH_AUDIT_LOG:-true}
   ```

2. **Multi-Agent Coordination**
   - Coordinates between AIDB, Hybrid-Coordinator, and Code Machine
   - Routes complex tasks to appropriate agents
   - Manages parallel execution

3. **Container Orchestration**
   - Full podman socket access
   - Can spawn and manage containers
   - Workflow isolation and sandboxing

4. **Workspace Management**
   - Dedicated workspace volume
   - Telemetry tracking
   - Output persistence

### Configuration

**Container:** `local-ai-ralph-wiggum`
**Port:** 8090
**Resources:**
- Memory: 1GB-8GB
- CPU: 1.0-4.0 cores
**Volumes:**
- `/data` - Ralph data
- `/workspace` - Working directory
- `/data/telemetry` - Event tracking
- `/var/run/podman/podman.sock` - Container management

### Integration Points

```python
# Ralph Wiggum coordinates all major operations:
RALPH_COORDINATOR_URL: http://hybrid-coordinator:8092
RALPH_AIDB_URL: http://aidb:8091

# Human oversight for critical operations:
RALPH_REQUIRE_APPROVAL: false  # Set to true for production
RALPH_APPROVAL_THRESHOLD: high # low, medium, high
RALPH_AUDIT_LOG: true          # Always log decisions
```

---

## Deployment Status

### Currently Deploying 🚀

Running `podman-compose up -d` to start all services...

**Expected Services (20 total):**

#### Core Data Layer (3)
- [ ] PostgreSQL (postgres)
- [ ] Redis (redis)
- [ ] Qdrant (qdrant)

#### MCP Servers (4)
- [ ] AIDB (aidb)
- [ ] Embeddings (embeddings)
- [ ] NixOS-Docs (nixos-docs)
- [ ] Health Monitor (health-monitor)

#### Orchestration Layer (3)
- [ ] Ralph Wiggum (ralph-wiggum) ⭐ **Default orchestrator**
- [ ] Hybrid-Coordinator (hybrid-coordinator)
- [ ] Code Machine (code-machine)

#### AI Execution (3)
- [ ] llama.cpp (llama-cpp)
- [ ] Aider Wrapper (aider-wrapper)
- [ ] MindsDB (mindsdb)

#### Monitoring (3)
- [ ] Prometheus (prometheus)
- [ ] Grafana (grafana)
- [ ] Jaeger (jaeger)

#### Infrastructure (4)
- [ ] nginx (nginx)
- [ ] Open-WebUI (open-webui)
- [ ] Watchtower (watchtower)
- [ ] Self-Heal Manager (self-heal-manager)

---

## Port Mapping Reference

### User-Facing Services
```
8443   - nginx (HTTPS - main entry point)
8888   - System dashboard
3001   - Open-WebUI
3002   - Grafana
16686  - Jaeger UI
47334  - MindsDB HTTP API
```

### Internal Services (via nginx proxy)
```
/aidb/     → 8091  - AIDB MCP Server
/hybrid/   → 8092  - Hybrid-Coordinator
/ralph/    → 8090  - Ralph Wiggum
/code/     → 8095  - Code Machine
/nixos/    → 8094  - NixOS-Docs
/aider/    → 8096  - Aider Wrapper
```

### Direct Access (localhost only)
```
5432   - PostgreSQL
6333   - Qdrant
6379   - Redis
8080   - llama.cpp
8081   - Embeddings
9090   - Prometheus
```

---

## Resource Requirements

### Minimal Deployment (Current)
```
Services: 5 (postgres, redis, qdrant, embeddings, aidb)
Memory: ~1.2GB
CPU: ~70%
Disk: ~2GB
```

### Full Deployment (Target)
```
Services: 20 (all services enabled)
Memory: ~8-12GB
CPU: Variable (depends on workload)
Disk: ~10GB + models
```

**Recommendation:** System should have 16GB+ RAM for comfortable full stack operation

---

## Continuous Learning Features

### Enabled by Default

1. **Hybrid-Coordinator Learning**
   ```bash
   CONTINUOUS_LEARNING_ENABLED=true
   LEARNING_PROCESSING_INTERVAL=3600  # 1 hour
   LEARNING_DATASET_THRESHOLD=1000
   ```

2. **Telemetry Collection**
   - All queries tracked
   - Success/failure rates
   - Performance metrics
   - User feedback

3. **Pattern Extraction**
   - Automatic pattern recognition
   - Solution caching
   - Query optimization

4. **Fine-Tuning Data Generation**
   - Successful interactions → training data
   - Continuous model improvement
   - Federated learning support

---

## Workflow Integration

### Default Workflow: Ralph Wiggum Orchestration

```python
# User Request
"Deploy a NixOS service with monitoring"

# 1. Ralph Wiggum receives request
ralph.process_task(task)

# 2. Ralph decides routing
if requires_human_approval(task):
    await ralph.request_approval()

# 3. Ralph coordinates agents
results = await ralph.coordinate([
    aidb.query_solutions(task),
    hybrid_coordinator.route(task),
    code_machine.execute_workflow(task)
])

# 4. Ralph monitors execution
ralph.track_progress(results)

# 5. Ralph reports back
ralph.send_response(user, results)

# 6. Telemetry & Learning
ralph.log_telemetry(task, results)
hybrid_coordinator.learn_from_interaction(task, results)
```

---

## Testing Plan

### Phase 1: Verify All Services Started (15 min)

```bash
# Check all containers
podman ps --format "table {{.Names}}\t{{.Status}}"

# Check health
curl -s http://localhost:8888/dashboard.html | grep -o "service"

# Check Ralph Wiggum
podman logs local-ai-ralph-wiggum --tail 50

# Check Hybrid-Coordinator
podman exec local-ai-aidb curl -s http://local-ai-hybrid-coordinator:8092/health
```

### Phase 2: Test Orchestration (30 min)

```bash
# Test Ralph Wiggum endpoint
curl -X POST http://localhost:8090/execute \
  -H "Content-Type: application/json" \
  -d '{"task": "List available NixOS packages", "require_approval": false}'

# Test Hybrid-Coordinator routing
curl -X POST http://localhost:8092/route \
  -H "Content-Type: application/json" \
  -d '{"query": "What is NixOS?", "context": {}}'

# Test Code Machine workflow
curl -X POST http://localhost:8095/workflow \
  -H "Content-Type: application/json" \
  -d '{"workflow": "simple_query", "engines": ["qwen-coder"]}'
```

### Phase 3: Test Continuous Learning (1 hour)

```bash
# Generate test interactions
for i in {1..10}; do
  curl -X POST http://localhost:8092/route \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"Test query $i\", \"context\": {}}"
  sleep 5
done

# Check telemetry
podman exec local-ai-postgres psql -U mcp -d mcp -c \
  "SELECT COUNT(*) FROM telemetry WHERE timestamp > NOW() - INTERVAL '1 hour';"

# Check learning daemon
podman logs local-ai-hybrid-coordinator | grep "Learning"
```

### Phase 4: Integration Testing (2 hours)

```bash
# Run full P1/P2 integration tests
cd ai-stack/tests
pytest test_p1_integration.py -v
pytest test_p2_health_checks.py -v

# Run workflow tests
pytest test_workflows.py -v

# Run orchestration tests
pytest test_ralph_orchestration.py -v  # New test file needed
```

---

## Dashboard Updates Needed

### New Sections to Add

1. **Ralph Wiggum Status**
   - Active tasks
   - Approval queue
   - Audit log
   - Resource usage

2. **Orchestration Metrics**
   - Tasks routed
   - Success rate
   - Average latency
   - Agent utilization

3. **Continuous Learning**
   - Patterns learned
   - Training data size
   - Model improvements
   - Learning rate

4. **Service Map**
   - Visual network graph
   - Service dependencies
   - Health status
   - Traffic flow

---

## Known Issues & Workarounds

### Issue 1: Hybrid-Coordinator Port 8092

**Status:** Container running but not binding to port
**Cause:** Config file vs environment variable
**Workaround:** In progress - investigating startup

### Issue 2: High Memory Usage

**Expected:** Full stack will use 8-12GB RAM
**Mitigation:**
- Monitor with Prometheus
- Set resource limits per service
- Use swap if needed

### Issue 3: Slow First Start

**Expected:** 5-10 minutes for all services
**Reason:** Image pulls, model loading, DB initialization
**Mitigation:** Be patient, monitor logs

---

## Success Criteria

### All Services Healthy ✅
- [ ] All 20 containers running
- [ ] All health checks passing
- [ ] nginx routing working
- [ ] Dashboard showing all services

### Ralph Wiggum Operational ✅
- [ ] Container started
- [ ] Port 8090 listening
- [ ] Can execute test task
- [ ] Telemetry flowing

### Continuous Learning Active ✅
- [ ] Learning daemon running
- [ ] Telemetry being stored
- [ ] Patterns being extracted
- [ ] Fine-tuning data generated

### Integration Complete ✅
- [ ] All P1/P2 tests passing
- [ ] Workflow tests passing
- [ ] Dashboard showing all metrics
- [ ] Documentation updated

---

## Next Steps After Deployment

### Immediate (Today)

1. **Verify all services started**
   - Check container status
   - Test health endpoints
   - Review logs for errors

2. **Update dashboard**
   - Add Ralph Wiggum section
   - Add orchestration metrics
   - Add service map

3. **Test basic workflows**
   - Simple query through Ralph
   - Hybrid routing test
   - Code generation test

### Short-term (This Week)

4. **Configure monitoring**
   - Set up Grafana dashboards
   - Configure Prometheus alerts
   - Test Jaeger tracing

5. **Optimize performance**
   - Tune resource limits
   - Configure caching
   - Optimize database queries

6. **Documentation**
   - Update architecture docs
   - Create workflow guides
   - Document Ralph Wiggum usage

### Long-term (This Month)

7. **Production hardening**
   - Enable HITL approval for critical ops
   - Configure backup automation
   - Set up disaster recovery

8. **Advanced features**
   - Custom workflows
   - Model fine-tuning
   - Federation setup

---

## Rollback Plan

If deployment fails:

```bash
# Stop all services
cd ai-stack/compose
export AI_STACK_ENV_FILE=.env
podman-compose down

# Restore profiles (if needed)
git checkout docker-compose.yml

# Start minimal stack
podman-compose up -d postgres redis qdrant embeddings aidb

# Verify minimal stack
podman ps | grep local-ai
```

---

**Status: Full Stack Deployment In Progress**

*Removing profile restrictions and enabling all agentic capabilities by default*
*Ralph Wiggum orchestrator will be the primary execution layer*
