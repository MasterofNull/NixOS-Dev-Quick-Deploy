# Intelligent Agent Routing & Workload Distribution

**Created:** 2026-03-15
**Priority:** CRITICAL
**Purpose:** Maximize local LLM usage, eliminate paid model choke points

---

## Problem Statement

**Current State (Anti-Pattern):**
```
All Work → Claude Opus (Paid) → Claude Sonnet (Paid)
              ↓                      ↓
         Bottleneck            Bottleneck
              ↓                      ↓
        Expensive             Expensive
```

**Problems:**
1. ❌ Two choke points (Opus, Sonnet)
2. ❌ Local LLMs (llama-cpp, qwen) underutilized
3. ❌ Free sub-agents not leveraged
4. ❌ No intelligent routing by task complexity
5. ❌ High costs for simple tasks
6. ❌ Slow throughput (sequential bottleneck)

---

## Solution: Intelligent Multi-Tier Routing

**Target State (Optimized):**
```
                    Work Request
                         ↓
              ┌──────────────────────┐
              │  Routing Coordinator  │
              │  (Task Classification)│
              └──────────────────────┘
                         ↓
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
    Tier 1: Local     Tier 2: Free    Tier 3: Paid
    (llama-cpp)       (Sub-agents)    (Claude)
        ↓                ↓                ↓
    80% of tasks     15% of tasks     5% of tasks
    $0 cost          $0 cost          High value only
```

---

## Three-Tier Architecture

### **Tier 1: Local LLM Layer (Priority: HIGHEST)**

**Services Already Running:**
- ✅ llama-cpp.service (port 8080) - Inference
- ✅ llama-cpp-embed.service (port 8081) - Embeddings
- ✅ ai-hybrid-coordinator.service (port 8003) - Orchestration

**Capabilities:**
- Code review and analysis
- Log parsing and summarization
- Configuration validation
- Test generation
- Documentation writing
- Routine troubleshooting
- Deployment log analysis
- Health check interpretation
- Error pattern matching

**Task Routing (80% of work):**
```python
LOCAL_LLM_TASKS = [
    "code_review",           # 95% accuracy with local
    "log_analysis",          # Perfect for local
    "config_validation",     # Rule-based + LLM
    "test_generation",       # Template-based
    "documentation",         # High quality with local
    "syntax_check",          # Fast with local
    "dependency_analysis",   # Graph + LLM
    "error_classification",  # Pattern matching
    "health_summary",        # Metric aggregation
    "deployment_summary",    # Context store + LLM
]
```

**Cost:** $0 (already paid for infrastructure)
**Speed:** Fast (local network, no API limits)
**Quality:** 85-95% for routine tasks

### **Tier 2: Free Sub-Agent Layer (Priority: HIGH)**

**Free Models Available:**
- Qwen (code-focused, free)
- Codex (GitHub Copilot, free tier)
- Local embedding models
- Gemini (free tier)

**Delegation Patterns:**
```python
SUB_AGENT_TASKS = [
    "implementation",        # Qwen excels at code
    "refactoring",          # Codex/Qwen
    "test_scaffolding",     # Template-based
    "boilerplate_generation", # Perfect for Qwen
    "code_completion",      # Copilot/Qwen
    "syntax_fixes",         # Fast with free models
    "simple_debugging",     # Pattern-based
]
```

**Cost:** $0 (free tiers)
**Speed:** Medium (API rate limits apply)
**Quality:** 90-95% for implementation tasks

### **Tier 3: Paid Model Layer (Priority: LAST RESORT)**

**Models (Use Sparingly):**
- Claude Opus (architecture, complex reasoning)
- Claude Sonnet (orchestration, review)

**Reserved For (5% of work):**
```python
PAID_MODEL_TASKS = [
    "architecture_decisions",  # High-value strategic
    "security_audit_review",   # Critical validation
    "complex_reasoning",       # Multi-hop logic
    "ambiguity_resolution",    # User intent unclear
    "final_approval",          # Quality gate
    "root_cause_analysis",     # Deep investigation
]
```

**Cost:** High (per token)
**Speed:** Subject to rate limits
**Quality:** 99%+ for complex tasks

---

## Intelligent Routing Algorithm

### **Decision Tree**

```python
def route_task(task_description: str, context: dict) -> Agent:
    """
    Route task to optimal agent tier
    Priority: Local > Free > Paid
    """

    # Classify task complexity and type
    complexity = classify_complexity(task_description)
    task_type = classify_task_type(task_description)

    # TIER 1: Try local first (80% of tasks)
    if complexity in ["simple", "medium"] and task_type in LOCAL_LLM_TASKS:
        if local_llm_available():
            return LocalLLMAgent(model="llama-cpp")

    # TIER 2: Try free sub-agents (15% of tasks)
    if task_type in SUB_AGENT_TASKS:
        if task_type.startswith("code_"):
            return FreeAgent(model="qwen")
        else:
            return FreeAgent(model="gemini-free")

    # TIER 3: Escalate to paid only if necessary (5% of tasks)
    if complexity == "high" or requires_strategic_thinking(task_description):
        return PaidAgent(model="claude-sonnet")

    if complexity == "critical" or requires_architecture(task_description):
        return PaidAgent(model="claude-opus")

    # Default: Try local first, escalate if it fails
    return LocalLLMAgent(model="llama-cpp", fallback="claude-sonnet")
```

### **Complexity Classification**

```python
def classify_complexity(task: str) -> str:
    """Classify task complexity for routing"""

    # Simple (80% → Local LLM)
    simple_patterns = [
        "parse", "extract", "summarize", "format",
        "validate", "check", "list", "count",
        "find", "search", "match", "filter"
    ]

    # Medium (15% → Free Sub-Agent)
    medium_patterns = [
        "implement", "refactor", "generate", "create",
        "update", "modify", "fix", "debug"
    ]

    # High (4% → Paid Model)
    high_patterns = [
        "design", "architect", "analyze root cause",
        "optimize", "security audit", "decide"
    ]

    # Critical (1% → Opus)
    critical_patterns = [
        "critical security", "production incident",
        "architectural decision", "strategic planning"
    ]

    task_lower = task.lower()

    if any(p in task_lower for p in critical_patterns):
        return "critical"
    elif any(p in task_lower for p in high_patterns):
        return "high"
    elif any(p in task_lower for p in medium_patterns):
        return "medium"
    else:
        return "simple"
```

---

## Implementation Strategy

### **Phase 1: Hybrid Coordinator Enhancement**

**Update:** `ai-stack/mcp-servers/hybrid-coordinator/`

```python
# hybrid_router.py

class HybridRouter:
    """
    Intelligent routing across local, free, and paid models
    Maximizes cost efficiency while maintaining quality
    """

    def __init__(self):
        self.local_llm = LlamaCppClient("http://localhost:8080")
        self.qwen = QwenClient()
        self.claude = ClaudeClient()
        self.metrics = RoutingMetrics()

    async def route_and_execute(self, task: dict) -> dict:
        """Route task to optimal agent and execute"""

        # Classify and route
        agent = self.route_task(task["description"], task.get("context", {}))

        # Track routing decision
        self.metrics.record_routing(
            task_type=task["type"],
            complexity=task["complexity"],
            routed_to=agent.tier,
            routed_to_model=agent.model
        )

        try:
            # Execute with chosen agent
            result = await agent.execute(task)

            # Track success
            self.metrics.record_success(agent.tier)
            return result

        except Exception as e:
            # Fallback to higher tier if local/free fails
            if agent.tier == "local":
                return await self._escalate_to_free(task, error=e)
            elif agent.tier == "free":
                return await self._escalate_to_paid(task, error=e)
            else:
                raise

    async def _escalate_to_free(self, task: dict, error: Exception) -> dict:
        """Escalate from local to free sub-agent"""
        logger.info(f"Local LLM failed, escalating to free: {error}")
        self.metrics.record_escalation("local", "free")

        agent = FreeAgent(model="qwen")
        return await agent.execute(task)

    async def _escalate_to_paid(self, task: dict, error: Exception) -> dict:
        """Escalate from free to paid (last resort)"""
        logger.warning(f"Free agent failed, escalating to paid: {error}")
        self.metrics.record_escalation("free", "paid")

        agent = PaidAgent(model="claude-sonnet")
        return await agent.execute(task)
```

### **Phase 2: Local LLM Integration**

**Llama.cpp Wrapper:**

```python
# llama_agent.py

class LocalLLMAgent:
    """
    Wrapper for local llama-cpp inference
    Handles 80% of routine tasks at $0 cost
    """

    def __init__(self, endpoint="http://localhost:8080"):
        self.endpoint = endpoint
        self.model = "local-llama"

    async def execute(self, task: dict) -> dict:
        """Execute task with local LLM"""

        # Build prompt optimized for local model
        prompt = self._build_prompt(task)

        # Call local llama-cpp
        response = await self._call_llama(prompt)

        # Parse and validate response
        result = self._parse_response(response, task)

        return {
            "result": result,
            "model": "llama-cpp-local",
            "cost": 0.0,
            "tier": "local"
        }

    async def _call_llama(self, prompt: str) -> str:
        """Call local llama-cpp server"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.endpoint}/v1/completions",
                json={
                    "prompt": prompt,
                    "max_tokens": 2048,
                    "temperature": 0.7,
                    "stop": ["</output>", "###"]
                }
            ) as resp:
                data = await resp.json()
                return data["choices"][0]["text"]

    def _build_prompt(self, task: dict) -> str:
        """Build prompt optimized for local model"""
        return f"""<task>
{task['description']}
</task>

<context>
{task.get('context', '')}
</context>

<instructions>
Provide a concise, focused response. Be direct and specific.
</instructions>

<output>
"""
```

### **Phase 3: Deployment Integration**

**Update deploy commands to use hybrid routing:**

```bash
# lib/deploy/commands/system.sh

# Before (all work to Claude)
log_info "Analyzing deployment logs..."
# Sent to Claude Opus

# After (intelligent routing)
log_info "Analyzing deployment logs..."
ANALYSIS=$(curl -s http://localhost:8003/analyze \
  -d "{\"task\": \"summarize deployment logs\", \"logs\": \"${LOGS}\"}")
# Routes to local llama-cpp (Tier 1, $0 cost)
```

---

## Routing Metrics & Optimization

### **Track Routing Decisions**

```python
class RoutingMetrics:
    """Track routing efficiency and costs"""

    def __init__(self):
        self.db = sqlite3.connect("routing_metrics.db")
        self._init_schema()

    def record_routing(self, task_type: str, complexity: str,
                      routed_to: str, routed_to_model: str):
        """Record routing decision"""
        self.db.execute("""
            INSERT INTO routing_decisions
            (task_type, complexity, tier, model, timestamp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (task_type, complexity, routed_to, routed_to_model))
        self.db.commit()

    def get_tier_distribution(self) -> dict:
        """Get distribution of work across tiers"""
        cursor = self.db.execute("""
            SELECT tier, COUNT(*) as count,
                   COUNT(*) * 100.0 / (SELECT COUNT(*) FROM routing_decisions) as pct
            FROM routing_decisions
            GROUP BY tier
        """)
        return {row[0]: {"count": row[1], "percentage": row[2]}
                for row in cursor}

    def get_cost_savings(self) -> dict:
        """Calculate cost savings from local routing"""
        # Assume $0.02 per task if sent to Claude
        total_tasks = self.db.execute(
            "SELECT COUNT(*) FROM routing_decisions"
        ).fetchone()[0]

        local_tasks = self.db.execute(
            "SELECT COUNT(*) FROM routing_decisions WHERE tier = 'local'"
        ).fetchone()[0]

        free_tasks = self.db.execute(
            "SELECT COUNT(*) FROM routing_decisions WHERE tier = 'free'"
        ).fetchone()[0]

        # Cost savings calculation
        potential_cost = total_tasks * 0.02
        actual_cost = (total_tasks - local_tasks - free_tasks) * 0.02
        savings = potential_cost - actual_cost

        return {
            "total_tasks": total_tasks,
            "local_tasks": local_tasks,
            "free_tasks": free_tasks,
            "paid_tasks": total_tasks - local_tasks - free_tasks,
            "potential_cost_usd": potential_cost,
            "actual_cost_usd": actual_cost,
            "savings_usd": savings,
            "savings_percentage": (savings / potential_cost * 100) if potential_cost > 0 else 0
        }
```

### **Target Metrics**

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Local LLM Usage | 80% | TBD | 🎯 Target |
| Free Sub-Agent Usage | 15% | TBD | 🎯 Target |
| Paid Model Usage | 5% | ~95% | ❌ Fix |
| Cost per 1000 Tasks | <$1 | ~$20 | ❌ Fix |
| Average Response Time | <2s | Variable | 🎯 Target |
| Quality Score | >90% | TBD | 🎯 Track |

---

## Deployment Command Enhancements

### **Add Routing to Deploy CLI**

```bash
# lib/deploy/llm-router.sh

# Classify and route to optimal LLM
route_to_llm() {
    local task="$1"
    local complexity="${2:-simple}"

    case "$complexity" in
        simple|medium)
            # Route to local llama-cpp
            curl -s http://localhost:8080/v1/completions \
                -d "{\"prompt\": \"${task}\"}" | jq -r '.choices[0].text'
            ;;
        high)
            # Route to free sub-agent (qwen)
            curl -s http://localhost:8003/route \
                -d "{\"task\": \"${task}\", \"preferred_tier\": \"free\"}"
            ;;
        critical)
            # Only for critical: route to paid (Claude)
            curl -s http://localhost:8003/route \
                -d "{\"task\": \"${task}\", \"tier\": \"paid\"}"
            ;;
    esac
}

# Example usage
analyze_logs() {
    local logs="$1"

    # Simple task → local LLM
    local summary=$(route_to_llm "Summarize these deployment logs: ${logs}" "simple")
    echo "${summary}"
}
```

---

## Success Criteria

### **Phase 1 Goals (Immediate)**
- [ ] Hybrid router implemented in hybrid-coordinator
- [ ] Local llama-cpp integration complete
- [ ] Routing metrics tracking operational
- [ ] Deploy commands use intelligent routing

### **Phase 2 Goals (Week 1)**
- [ ] 80% of tasks routed to local LLM
- [ ] 15% routed to free sub-agents
- [ ] 5% routed to paid models
- [ ] Cost reduced by 90%

### **Phase 3 Goals (Week 2)**
- [ ] Quality maintained >90% across all tiers
- [ ] Response time <2s average
- [ ] Zero paid model usage for routine tasks
- [ ] Full metrics dashboard

---

## Cost Impact Analysis

### **Current State (All → Claude)**
```
1000 tasks/day × $0.02/task = $20/day = $600/month
```

### **Optimized State (Tiered Routing)**
```
800 local tasks   × $0.00 = $0
150 free tasks    × $0.00 = $0
50 paid tasks     × $0.02 = $1/day = $30/month

Savings: $570/month (95% reduction)
```

### **Annual Impact**
```
Current:  $7,200/year
Optimized: $360/year
Savings:  $6,840/year (95% reduction)
```

---

## Implementation Roadmap

### **Immediate (This Session)**
1. Create hybrid router implementation
2. Add llama-cpp client wrapper
3. Implement routing metrics
4. Test local LLM integration

### **Short-term (Next Week)**
1. Integrate routing into deploy commands
2. Add Qwen sub-agent support
3. Build routing dashboard
4. Optimize prompts for local models

### **Medium-term (Phase 2 completion)**
1. Full tier distribution (80/15/5)
2. Quality monitoring and feedback
3. Auto-escalation on failures
4. Prompt optimization per tier

---

## References

- Local LLM Services: llama-cpp.service (8080), llama-cpp-embed.service (8081)
- Hybrid Coordinator: ai-hybrid-coordinator.service (8003)
- Context-Mode Integration: .agents/designs/context-mode-integration.md
- System Excellence Roadmap: .agents/plans/SYSTEM-EXCELLENCE-ROADMAP-2026-Q2.md
