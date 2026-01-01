# Vibe Coding System Architecture
**World-Class AI-Powered Development Platform**

Version: 3.0.0 - Agentic Era
Status: Production Enhancement
Created: December 31, 2025

---

## Executive Summary

This document outlines the architecture for transforming the NixOS-Dev-Quick-Deploy AI Stack into a world-class "vibe coding" platform with:

- **Autonomous Tool Discovery**: Self-discovering capabilities and MCP servers
- **Self-Healing Infrastructure**: Automatic error recovery and system repair
- **Continuous Learning**: Pattern extraction and model fine-tuning
- **Multi-Layer Security**: Zero-trust architecture with audit trails
- **Ralph Wiggum Orchestration**: Persistent autonomous development loops
- **Progressive Disclosure**: AI agents discover capabilities as needed

---

## Core Components

### 1. Ralph Wiggum Loop Engine
**Purpose**: Continuous autonomous agent orchestration

**Features**:
- While-true loop with exit code blocking
- Git-based context recovery
- Multi-agent backend support (Aider, Continue, Goose, AutoGPT, LangChain)
- Human-in-the-loop approval gates
- Telemetry and metrics collection

**Status**: ✅ Implemented
**Location**: `/ai-stack/mcp-servers/ralph-wiggum/`

**API Endpoints**:
- `POST /tasks` - Submit autonomous task
- `GET /tasks/{id}` - Get task status
- `POST /tasks/{id}/stop` - Stop running task
- `POST /tasks/{id}/approve` - Approve gated action
- `GET /stats` - Get loop statistics

---

### 2. AIDB MCP Server
**Purpose**: Central context management and tool registry

**Features**:
- Document search and RAG
- Tool registry and discovery
- Skills management system
- Google Search integration
- PostgreSQL/Redis/Qdrant backends
- Telemetry collection

**Status**: ⚙️ Deploying
**Location**: `/ai-stack/mcp-servers/aidb/`

**Key Capabilities**:
- Progressive disclosure API (4 levels: basic, standard, detailed, advanced)
- Skill loader with YAML frontmatter
- Discovery endpoints for AI agents
- Parallel inference pipeline

---

### 3. Hybrid Coordinator
**Purpose**: Federated learning and context augmentation

**Features**:
- Local/remote context coordination
- Pattern extraction from interactions
- Fine-tuning dataset generation
- Confidence-based routing
- Federation synchronization

**Status**: ⚙️ Deploying
**Location**: `/ai-stack/mcp-servers/hybrid-coordinator/`

**Workflow**:
1. Query arrives at coordinator
2. Check local context cache (Qdrant)
3. If confidence > threshold: use local
4. Else: route to remote API
5. Extract patterns for learning
6. Update fine-tuning dataset

---

### 4. Llama.cpp Inference Engine
**Purpose**: Local LLM inference with CPU optimizations

**Features**: ✅ **OPTIMIZED**
- Flash Attention enabled
- KV cache quantization (Q4)
- Sliding window via defragmentation
- Continuous batching
- NUMA-aware threading
- 8K context window
- Parallel request handling (4 slots)

**Status**: ✅ Running and Healthy
**Port**: 8080
**Model**: Qwen2.5-Coder-7B-Instruct (Q4_K_M)

**Performance**:
- RAM Usage: ~7.8GB (60% reduction with KV quantization)
- Context: 8192 tokens
- Throughput: 2-3x improvement with optimizations

---

### 5. Vector Database (Qdrant)
**Purpose**: Semantic search and context retrieval

**Features**:
- 6 pre-configured collections
- gRPC and HTTP APIs
- Persistent storage
- Health monitoring

**Status**: ✅ Running and Healthy
**Collections**:
- `skills-patterns` - Learned coding patterns
- `mcp-semantic-search` - MCP tool descriptions
- `codebase-context` - Project understanding
- `error-solutions` - Debugging knowledge
- `best-practices` - Coding standards
- `interaction-history` - Conversation memory

---

## New Features to Implement

### 6. Tool Discovery System
**Purpose**: Automatic discovery of system capabilities

**Design**:

```python
class ToolDiscoveryEngine:
    """
    Autonomous tool and skill discovery system

    Features:
    - Scans MCP servers for available tools
    - Indexes tools in Qdrant for semantic search
    - Auto-generates tool usage examples
    - Monitors for new MCP server deployments
    - Updates tool registry in real-time
    """

    async def discover_tools(self):
        # Scan all MCP servers
        servers = await self.list_mcp_servers()

        for server in servers:
            # Query server capabilities
            caps = await server.get_capabilities()

            # Extract tools and skills
            tools = caps.get("tools", [])

            # Index in Qdrant
            await self.index_tools(tools)

            # Generate usage examples via LLM
            examples = await self.generate_examples(tools)

            # Update registry
            await self.update_registry(tools, examples)

    async def semantic_tool_search(self, query: str):
        # Search Qdrant for relevant tools
        results = await qdrant.search(
            collection="mcp-semantic-search",
            query_vector=await self.embed(query),
            limit=5
        )
        return results
```

**Implementation Steps**:
1. Create `tool_discovery.py` in AIDB
2. Add background task to FastAPI server
3. Implement MCP server health monitoring
4. Create tool index schema in Qdrant
5. Add `/tools/discover` endpoint
6. Integrate with Ralph loop for autonomous discovery

**Files to Create**:
- `/ai-stack/mcp-servers/aidb/tool_discovery.py`
- `/ai-stack/mcp-servers/aidb/schemas/tool_index.py`

---

### 7. Self-Healing System
**Purpose**: Automatic error recovery and system repair

**Design**:

```python
class SelfHealingOrchestrator:
    """
    Monitors system health and performs automatic repairs

    Features:
    - Container health monitoring
    - Automatic service restart
    - Dependency resolution
    - Error pattern learning
    - Rollback on catastrophic failure
    """

    async def monitor_health(self):
        while True:
            # Check all containers
            containers = await podman.list_containers()

            for container in containers:
                if container.status == "unhealthy":
                    await self.heal_container(container)

            await asyncio.sleep(30)

    async def heal_container(self, container):
        # Log incident
        logger.warning("container_unhealthy", name=container.name)

        # Check error pattern
        logs = await container.logs(tail=100)
        error_pattern = await self.analyze_errors(logs)

        # Try known fixes
        if error_pattern in self.known_patterns:
            fix = self.known_patterns[error_pattern]
            await fix.apply(container)
        else:
            # Learn new pattern
            await self.learn_error_pattern(error_pattern, logs)

            # Default: restart container
            await container.restart()

        # Verify healing
        await asyncio.sleep(10)
        if await container.is_healthy():
            logger.info("container_healed", name=container.name)
            await self.save_success_pattern(error_pattern)
```

**Error Patterns to Handle**:
- Port conflicts
- OOM kills
- Database connection failures
- Network timeouts
- Model loading failures
- Disk space issues

**Implementation**:
- Add health monitor service
- Create error pattern database
- Implement auto-restart logic
- Add rollback capability
- Integrate with telemetry

---

### 8. Continuous Learning Pipeline
**Purpose**: Extract patterns and improve system performance

**Design**:

```python
class ContinuousLearningPipeline:
    """
    Learns from user interactions to improve system

    Features:
    - Pattern extraction from telemetry
    - Fine-tuning dataset generation
    - Model distillation for speed
    - A/B testing for improvements
    - Performance monitoring
    """

    async def process_telemetry(self):
        # Read telemetry events
        events = await self.read_telemetry()

        for event in events:
            if event["type"] == "task_completed":
                # Extract successful patterns
                pattern = await self.extract_pattern(event)

                # Add to fine-tuning dataset
                await self.add_to_dataset(pattern)

        # Periodically fine-tune
        if self.should_finetune():
            await self.trigger_finetuning()

    async def extract_pattern(self, event):
        # Analyze successful task completion
        task = event["task"]
        iterations = event["iterations"]

        if iterations < 3:  # Successful on first try
            return {
                "prompt": task["prompt"],
                "approach": task["backend"],
                "context": task["context"],
                "success_factors": await self.analyze_success(task)
            }
```

**Learning Sources**:
- Ralph loop iterations
- Successful task patterns
- Error resolutions
- User corrections
- Code review feedback

**Outputs**:
- Fine-tuning datasets (JSONL)
- Pattern catalog in Qdrant
- Performance metrics
- Improvement suggestions

---

### 9. Security Hardening
**Purpose**: Multi-layer security with zero-trust principles

**Layers**:

#### Layer 1: Container Security
- Non-root user in all containers
- Read-only root filesystem
- Capability dropping
- Seccomp profiles
- Network segmentation

#### Layer 2: Authentication & Authorization
- API key-based auth for MCP servers
- JWT tokens for user sessions
- Role-based access control (RBAC)
- Audit logging for all actions

#### Layer 3: Data Protection
- Encryption at rest (LUKS volumes)
- TLS for all network communication
- Secret management (HashiCorp Vault integration)
- PII detection and redaction

#### Layer 4: Monitoring & Auditing
- Security event logging
- Anomaly detection
- Rate limiting
- Intrusion detection

**Implementation**:

```yaml
# docker-compose.yml security additions
services:
  llama-cpp:
    security_opt:
      - no-new-privileges:true
      - seccomp:default
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,nodev,size=1g
    user: "1000:1000"
```

---

### 10. Vibe Coding Features

#### Auto-Commit Mode
Automatically create git commits after successful code changes:

```yaml
# ralph-wiggum config
auto_commit:
  enabled: true
  on_success: true
  on_iteration_threshold: 3
  commit_message_template: |
    {backend}: {summary}

    {details}

    Co-authored-by: Ralph Wiggum <ralph@vibe.codes>
    Generated with local AI stack
```

#### Context Preservation
Save and restore coding sessions:

```python
class SessionManager:
    async def save_session(self, session_id: str):
        # Save current context
        context = {
            "files_open": await self.get_open_files(),
            "cursor_positions": await self.get_cursors(),
            "terminal_state": await self.get_terminal_state(),
            "agent_context": await ralph.get_task_context(),
            "vector_context": await qdrant.export_session(session_id)
        }

        # Store in Redis
        await redis.setex(f"session:{session_id}", 86400, json.dumps(context))

    async def restore_session(self, session_id: str):
        # Load context
        context = json.loads(await redis.get(f"session:{session_id}"))

        # Restore state
        await self.open_files(context["files_open"])
        await self.set_cursors(context["cursor_positions"])
        await ralph.resume_task(context["agent_context"])
```

#### Smart Suggestions
Proactive code improvements:

```python
class SmartSuggestions:
    async def analyze_codebase(self):
        # Scan for improvement opportunities
        opportunities = []

        # Check for security issues
        security_issues = await self.scan_security()
        opportunities.extend(security_issues)

        # Check for performance issues
        perf_issues = await self.scan_performance()
        opportunities.extend(perf_issues)

        # Check for best practice violations
        style_issues = await self.scan_style()
        opportunities.extend(style_issues)

        # Rank by impact
        ranked = await self.rank_by_impact(opportunities)

        return ranked[:10]  # Top 10 suggestions
```

#### Collaboration Mode
Multi-user vibe coding:

- Shared Ralph sessions
- Collaborative task queues
- Real-time updates via WebSockets
- Conflict resolution
- Session recording and replay

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
│  (CLI, VSCode Extension, Web UI, API Clients)               │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────────┐
│                  Ralph Wiggum Orchestrator                   │
│                  (Central Control Loop)                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Task Queue   │  │ Hook System  │  │ State Mgmt   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────┬───────────────┬───────────────┬───────────────┘
             │               │               │
    ┌────────┴────────┐ ┌───┴────┐ ┌────────┴────────┐
    │                 │ │        │ │                 │
┌───┴─────┐  ┌────────┴─┴──┐  ┌──┴──────┐  ┌────────┴───┐
│  AIDB   │  │  Hybrid     │  │ Tool    │  │  Learning  │
│  MCP    │  │ Coordinator │  │Discovery│  │  Pipeline  │
└────┬────┘  └──────┬──────┘  └────┬────┘  └─────┬──────┘
     │              │              │             │
     │    ┌─────────┴──────────────┴─────┐      │
     │    │                                │      │
┌────┴────┴────┐  ┌──────────────┐  ┌─────┴──────┴────┐
│ llama.cpp    │  │   Qdrant     │  │   PostgreSQL    │
│ (Local LLM)  │  │  (Vectors)   │  │   (Telemetry)   │
└──────────────┘  └──────────────┘  └─────────────────┘
```

---

## Testing Strategy

### Phase 1: Component Testing
1. Test llama.cpp with simple completion
2. Test Qdrant vector search
3. Test PostgreSQL connectivity
4. Test Redis caching
5. Test MindsDB queries

### Phase 2: MCP Server Testing
1. Test AIDB health endpoint
2. Test Hybrid Coordinator routing
3. Test Ralph Wiggum task submission
4. Test tool discovery API
5. Test skill loading system

### Phase 3: Integration Testing
1. Submit task to Ralph → routes to Aider
2. Query AIDB → searches Qdrant → returns results
3. Trigger learning pipeline → generates dataset
4. Test self-healing → kill container → auto-restart
5. Test hooks → exit code blocking → continues loop

### Phase 4: End-to-End Testing
1. Real coding task: "Add user authentication"
2. Monitor Ralph iterations
3. Verify git commits
4. Check telemetry data
5. Validate learned patterns

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| LLM Response Time | < 2s | ~1.5s |
| Vector Search | < 100ms | ~50ms |
| Tool Discovery | < 500ms | TBD |
| Self-Heal Time | < 30s | TBD |
| Pattern Learning | 1hr batch | TBD |
| Context Retrieval | < 200ms | ~80ms |
| Concurrent Tasks | 4 parallel | 4 ✅ |

---

## Security Checklist

- [ ] All containers run as non-root
- [ ] API endpoints require authentication
- [ ] Secrets stored in environment/vault
- [ ] TLS enabled for external connections
- [ ] Audit logging enabled
- [ ] Rate limiting configured
- [ ] Input validation on all endpoints
- [ ] Output sanitization (no PII leaks)
- [ ] Network segmentation via Podman networks
- [ ] Regular security scans (Trivy, Grype)

---

## Deployment Workflow

```bash
# 1. Ensure core services are running
podman ps

# 2. Deploy MCP servers
cd ~/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/compose
podman-compose up -d aidb hybrid-coordinator ralph-wiggum

# 3. Verify health
curl http://localhost:8091/health  # AIDB
curl http://localhost:8092/health  # Hybrid Coordinator
curl http://localhost:8098/health  # Ralph Wiggum

# 4. Submit test task
curl -X POST http://localhost:8098/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a simple hello world function",
    "backend": "aider",
    "max_iterations": 5
  }'

# 5. Monitor progress
podman logs -f local-ai-ralph-wiggum
tail -f ~/.local/share/nixos-ai-stack/telemetry/ralph-events.jsonl

# 6. Test tool discovery
curl http://localhost:8091/api/v1/tools/discover

# 7. Test learning pipeline
curl http://localhost:8092/api/v1/patterns/extract
```

---

## Future Enhancements

### V3.1 - Multi-Model Support
- Add support for multiple GGUF models
- Automatic model switching based on task
- Model performance tracking

### V3.2 - IDE Integration
- VSCode extension for Ralph control
- Real-time suggestion sidebar
- Inline tool discovery

### V3.3 - Team Features
- Multi-user sessions
- Shared knowledge bases
- Team metrics dashboard

### V3.4 - Advanced Learning
- Reinforcement learning from human feedback (RLHF)
- Automatic model fine-tuning
- A/B testing framework

---

## Success Metrics

- **Autonomous Completion Rate**: >80% of tasks complete without human intervention
- **Time to First Success**: <5 minutes for simple tasks
- **Learning Improvement**: 10% performance gain per week
- **Self-Healing Success**: >95% automatic recovery
- **Developer Satisfaction**: >9/10 vibe coding experience rating

---

**Status**: Ready for Implementation
**Next Steps**: Deploy MCP servers → Test orchestration → Implement enhancements
